"""Bounded application-managed delegation from Codex to approved agent workers.

This bridge does not enable Codex native multi-agent, apps, plugins or tools. A child
worker can run only when an exact completed Codex delegation-plan ModelCall, immutable
plan Artifact and immutable SettingsSnapshot all agree on the same allowlisted route.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import (
    CODEX_CLI_APPROVED_VERSION,
    AgentRunnerError,
    AgentRunnerRegistry,
    AgentRunRequest,
    AgentRunResult,
)
from app.modules.harness.delegation import (
    DelegationStateError,
    bind_delegation_model_call,
    complete_delegation_execution,
    ensure_delegation_execution,
    fail_delegation_execution,
    start_delegation_execution,
)
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.models import Artifact, ContentRun, ModelCall
from app.modules.harness.repository_snapshot import RepositorySnapshotSpec
from app.modules.harness.runtime import (
    ModelCandidate,
    ModelResponse,
    RuntimeStateError,
    complete_model_call,
    fail_model_call,
    start_model_call,
)

COORDINATOR_KEY = "codex"
COORDINATOR_PROVIDER = "codex_cli"
COORDINATOR_TASK_KEY = "delegation_plan"
DELEGATION_PLAN_ARTIFACT_TYPE = "delegation_plan"
DELEGATION_RESULT_ARTIFACT_PREFIX = "delegation_output_"
_ALLOWED_WORKER_PROVIDERS = {"codex_cli", "antigravity_cli"}
_ALLOWED_PLAN_FIELDS = {
    "schema_version",
    "decision",
    "task_key",
    "worker_kind",
    "worker_key",
    "provider",
    "model",
}
_ALLOWED_ROUTE_FIELDS = {
    "worker_kind",
    "worker_key",
    "provider",
    "model",
    "runner_version",
}

DELEGATION_PLAN_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "decision",
        "task_key",
        "worker_kind",
        "worker_key",
        "provider",
        "model",
    ],
    "properties": {
        "schema_version": {"type": "integer", "const": 1},
        "decision": {"type": "string", "const": "delegate"},
        "task_key": {"type": "string", "minLength": 1, "maxLength": 100},
        "worker_kind": {"type": "string", "enum": ["subagent", "application"]},
        "worker_key": {"type": "string", "minLength": 1, "maxLength": 200},
        "provider": {"type": "string", "enum": ["codex_cli", "antigravity_cli"]},
        "model": {"type": "string", "minLength": 1, "maxLength": 100},
    },
}


class ControlledDelegationError(ValueError):
    """Fail-closed error with a stable code safe for logs and telemetry."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DelegationRoute:
    task_key: str
    worker_kind: str
    worker_key: str
    provider: str
    model: str
    runner_version: str


@dataclass(frozen=True, slots=True)
class DelegationPlan:
    task_key: str
    worker_kind: str
    worker_key: str
    provider: str
    model: str


@dataclass(frozen=True, slots=True)
class ControlledDelegationRequest:
    run_id: UUID
    step_run_id: UUID | None
    coordinator_model_call_id: UUID
    worker_context_manifest_id: UUID
    prompt_version: str
    prompt: str
    structured_output_schema: dict[str, object]
    working_context: dict[str, object]
    purpose: str
    dedupe_key: str
    parent_execution_id: UUID | None = None
    attempt: int = 1
    timeout: float = 300.0
    repository: RepositorySnapshotSpec | None = None


@dataclass(frozen=True, slots=True)
class ControlledDelegationResult:
    execution_id: UUID
    worker_model_call_id: UUID | None
    result_artifact_id: UUID | None
    status: str
    replayed: bool
    structured_output: object | None
    raw_output_hash: str | None


class SettingsDelegationRouter:
    """Resolve one exact delegation route from the immutable SettingsSnapshot only."""

    def resolve(
        self,
        *,
        task_key: str,
        settings_snapshot: SettingsSnapshot,
    ) -> DelegationRoute:
        root = _as_dict(settings_snapshot.resolved_settings_json.get("delegation"), "delegation")
        if root.get("enabled") is not True:
            raise ControlledDelegationError("delegation_disabled")
        routes = _as_dict(root.get("routes"), "delegation.routes")
        config = _as_dict(routes.get(task_key), f"delegation.routes.{task_key}")
        if set(config) != _ALLOWED_ROUTE_FIELDS:
            raise ControlledDelegationError("delegation_route_contains_unapproved_fields")
        worker_kind = _required_string(config, "worker_kind")
        worker_key = _required_string(config, "worker_key")
        provider = _required_string(config, "provider")
        model = _required_string(config, "model")
        runner_version = _required_string(config, "runner_version")
        if worker_kind not in {"subagent", "application"}:
            raise ControlledDelegationError("delegation_worker_kind_not_allowed")
        if provider not in _ALLOWED_WORKER_PROVIDERS:
            raise ControlledDelegationError("delegation_provider_not_allowed")
        if provider == "antigravity_cli" and (
            worker_kind != "application" or worker_key != "antigravity"
        ):
            raise ControlledDelegationError("delegation_antigravity_identity_mismatch")
        if provider == "codex_cli" and worker_kind != "subagent":
            raise ControlledDelegationError("delegation_codex_worker_kind_mismatch")
        return DelegationRoute(
            task_key=task_key,
            worker_kind=worker_kind,
            worker_key=worker_key,
            provider=provider,
            model=model,
            runner_version=runner_version,
        )


class ControlledDelegationBridge:
    """Execute one settings-authorized child worker with durable provenance."""

    def __init__(self, runner_registry: AgentRunnerRegistry) -> None:
        self._runner_registry = runner_registry
        self._router = SettingsDelegationRouter()

    async def execute(
        self,
        session: AsyncSession,
        *,
        request: ControlledDelegationRequest,
    ) -> ControlledDelegationResult:
        run, coordinator, plan_artifact, plan, route = await _resolve_controlled_plan(
            session,
            request=request,
            router=self._router,
        )
        execution = await ensure_delegation_execution(
            session,
            run_id=run.id,
            step_run_id=request.step_run_id,
            parent_execution_id=request.parent_execution_id,
            coordinator_key=COORDINATOR_KEY,
            coordinator_model_call_id=coordinator.id,
            decision_artifact_id=plan_artifact.id,
            worker_kind=route.worker_kind,
            worker_key=route.worker_key,
            task_key=route.task_key,
            dedupe_key=request.dedupe_key,
            attempt=request.attempt,
        )
        if execution.status == "completed":
            return await _replay_completed_execution(session, execution=execution)
        if execution.status == "running":
            raise ControlledDelegationError("delegation_already_running")
        if execution.status in {"failed", "cancelled"}:
            raise ControlledDelegationError("delegation_terminal_retry_requires_new_attempt")

        await start_delegation_execution(session, execution_id=execution.id)
        try:
            runner = self._runner_registry.get(route.provider)
            capability = await runner.preflight()
        except AgentRunnerError as exc:
            await fail_delegation_execution(
                session,
                execution_id=execution.id,
                error_class=exc.code,
            )
            raise ControlledDelegationError(exc.code) from exc
        if capability.provider != route.provider or capability.version != route.runner_version:
            await fail_delegation_execution(
                session,
                execution_id=execution.id,
                error_class="delegation_runner_identity_mismatch",
            )
            raise ControlledDelegationError("delegation_runner_identity_mismatch")

        try:
            call = await start_model_call(
                session,
                run_id=run.id,
                step_run_id=request.step_run_id,
                context_manifest_id=request.worker_context_manifest_id,
                task_key=plan.task_key,
                route=ModelCandidate(provider=route.provider, model=route.model),
                purpose=request.purpose,
                prompt_version=request.prompt_version,
            )
            await bind_delegation_model_call(
                session,
                execution_id=execution.id,
                model_call_id=call.id,
            )
        except (RuntimeStateError, DelegationStateError) as exc:
            await fail_delegation_execution(
                session,
                execution_id=execution.id,
                error_class="delegation_worker_model_call_invalid",
            )
            raise ControlledDelegationError("delegation_worker_model_call_invalid") from exc

        agent_request = AgentRunRequest(
            provider=route.provider,
            model=route.model,
            prompt=request.prompt,
            structured_output_schema=request.structured_output_schema,
            working_context=request.working_context,
            timeout=request.timeout,
            repository=request.repository,
        )
        try:
            result = await runner.run(agent_request)
        except AgentRunnerError as exc:
            await fail_model_call(
                session,
                call_id=call.id,
                error_class=exc.code,
                runtime_metadata={
                    "delegation_execution_id": str(execution.id),
                    "runner_error": exc.code,
                },
            )
            await fail_delegation_execution(
                session,
                execution_id=execution.id,
                error_class=exc.code,
            )
            raise ControlledDelegationError(exc.code) from exc
        if result.provider != route.provider or result.model != route.model:
            await fail_model_call(
                session,
                call_id=call.id,
                error_class="delegation_result_route_mismatch",
                runtime_metadata={
                    "delegation_execution_id": str(execution.id),
                    "runner_version": result.runner_version,
                },
            )
            await fail_delegation_execution(
                session,
                execution_id=execution.id,
                error_class="delegation_result_route_mismatch",
            )
            raise ControlledDelegationError("delegation_result_route_mismatch")

        try:
            result_artifact, response_content = await _persist_worker_result(
                session,
                execution_id=execution.id,
                run_id=run.id,
                step_run_id=request.step_run_id,
                task_key=plan.task_key,
                structured_output=result.structured_output,
            )
        except (TypeError, ValueError) as exc:
            await fail_model_call(
                session,
                call_id=call.id,
                error_class="delegation_worker_output_not_json",
                runtime_metadata={"delegation_execution_id": str(execution.id)},
            )
            await fail_delegation_execution(
                session,
                execution_id=execution.id,
                error_class="delegation_worker_output_not_json",
            )
            raise ControlledDelegationError("delegation_worker_output_not_json") from exc

        await complete_model_call(
            session,
            call_id=call.id,
            response=ModelResponse(
                content=response_content,
                input_tokens=_integer_usage(result.usage, "input_tokens"),
                output_tokens=_integer_usage(result.usage, "output_tokens"),
                cost=_decimal_usage(result.usage, "cost"),
                latency_ms=result.duration_ms,
                finish_reason="stop",
            ),
            result_artifact_id=result_artifact.id,
            runtime_metadata=_runtime_metadata(result, execution_id=execution.id),
        )
        completed = await complete_delegation_execution(
            session,
            execution_id=execution.id,
            result_artifact_id=result_artifact.id,
            external_execution_id=result.session_id,
        )
        return ControlledDelegationResult(
            execution_id=completed.id,
            worker_model_call_id=call.id,
            result_artifact_id=result_artifact.id,
            status=completed.status,
            replayed=False,
            structured_output=result.structured_output,
            raw_output_hash=result.raw_output_hash,
        )


async def persist_delegation_plan_artifact(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    plan: object,
    version: int = 1,
) -> Artifact:
    """Persist only the bounded plan contract; free-form rationale is rejected."""

    normalized = _parse_plan(plan)
    payload: dict[str, object] = {
        "schema_version": 1,
        "decision": "delegate",
        "task_key": normalized.task_key,
        "worker_kind": normalized.worker_kind,
        "worker_key": normalized.worker_key,
        "provider": normalized.provider,
        "model": normalized.model,
    }
    artifact = Artifact(
        run_id=run_id,
        step_run_id=step_run_id,
        artifact_type=DELEGATION_PLAN_ARTIFACT_TYPE,
        locale=None,
        version=version,
        content_json=payload,
        content_hash=_stable_hash(payload),
    )
    session.add(artifact)
    await session.flush()
    return artifact


async def _resolve_controlled_plan(
    session: AsyncSession,
    *,
    request: ControlledDelegationRequest,
    router: SettingsDelegationRouter,
) -> tuple[ContentRun, ModelCall, Artifact, DelegationPlan, DelegationRoute]:
    run = await session.get(ContentRun, request.run_id)
    if run is None:
        raise ControlledDelegationError("delegation_run_not_found")
    coordinator = await session.get(ModelCall, request.coordinator_model_call_id)
    if (
        coordinator is None
        or coordinator.run_id != run.id
        or coordinator.step_run_id != request.step_run_id
    ):
        raise ControlledDelegationError("delegation_coordinator_call_mismatch")
    if (
        coordinator.status != "completed"
        or coordinator.provider != COORDINATOR_PROVIDER
        or coordinator.task_key != COORDINATOR_TASK_KEY
        or coordinator.result_artifact_id is None
    ):
        raise ControlledDelegationError("delegation_coordinator_call_invalid")
    metadata = coordinator.runtime_metadata_json or {}
    if metadata.get("runner_version") != CODEX_CLI_APPROVED_VERSION:
        raise ControlledDelegationError("delegation_coordinator_runner_not_approved")

    artifact = await session.get(Artifact, coordinator.result_artifact_id)
    if (
        artifact is None
        or artifact.run_id != run.id
        or artifact.step_run_id != request.step_run_id
        or artifact.artifact_type != DELEGATION_PLAN_ARTIFACT_TYPE
        or artifact.version != 1
        or artifact.content_json is None
    ):
        raise ControlledDelegationError("delegation_decision_artifact_invalid")
    if artifact.content_hash != _stable_hash(artifact.content_json):
        raise ControlledDelegationError("delegation_decision_artifact_hash_mismatch")
    plan = _parse_plan(artifact.content_json)
    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None:
        raise ControlledDelegationError("delegation_settings_snapshot_missing")
    route = router.resolve(task_key=plan.task_key, settings_snapshot=snapshot)
    if (
        plan.worker_kind,
        plan.worker_key,
        plan.provider,
        plan.model,
    ) != (
        route.worker_kind,
        route.worker_key,
        route.provider,
        route.model,
    ):
        raise ControlledDelegationError("delegation_plan_route_mismatch")
    return run, coordinator, artifact, plan, route


async def _persist_worker_result(
    session: AsyncSession,
    *,
    execution_id: UUID,
    run_id: UUID,
    step_run_id: UUID | None,
    task_key: str,
    structured_output: object,
) -> tuple[Artifact, str]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "delegation_execution_id": str(execution_id),
        "task_key": task_key,
        "structured_output": structured_output,
    }
    response_content = json.dumps(
        structured_output,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    artifact = Artifact(
        run_id=run_id,
        step_run_id=step_run_id,
        artifact_type=_result_artifact_type(execution_id),
        locale=None,
        version=1,
        content_json=payload,
        content_hash=_stable_hash(payload),
    )
    session.add(artifact)
    await session.flush()
    return artifact, response_content


async def _replay_completed_execution(
    session: AsyncSession,
    *,
    execution: DelegationExecution,
) -> ControlledDelegationResult:
    if execution.worker_model_call_id is None or execution.result_artifact_id is None:
        raise ControlledDelegationError("delegation_completed_result_missing")
    call = await session.get(ModelCall, execution.worker_model_call_id)
    artifact = await session.get(Artifact, execution.result_artifact_id)
    if (
        call is None
        or call.status != "completed"
        or call.result_artifact_id != execution.result_artifact_id
        or artifact is None
        or artifact.run_id != execution.run_id
        or artifact.step_run_id != execution.step_run_id
        or artifact.artifact_type != _result_artifact_type(execution.id)
        or artifact.content_json is None
        or artifact.content_hash != _stable_hash(artifact.content_json)
    ):
        raise ControlledDelegationError("delegation_completed_result_invalid")
    payload = artifact.content_json
    if (
        payload.get("schema_version") != 1
        or payload.get("delegation_execution_id") != str(execution.id)
        or payload.get("task_key") != execution.task_key
        or "structured_output" not in payload
    ):
        raise ControlledDelegationError("delegation_completed_result_invalid")
    raw_output_hash: str | None = None
    metadata = call.runtime_metadata_json or {}
    candidate_hash = metadata.get("raw_output_hash")
    if isinstance(candidate_hash, str):
        raw_output_hash = candidate_hash
    return ControlledDelegationResult(
        execution_id=execution.id,
        worker_model_call_id=call.id,
        result_artifact_id=artifact.id,
        status=execution.status,
        replayed=True,
        structured_output=payload["structured_output"],
        raw_output_hash=raw_output_hash,
    )


def _parse_plan(value: object) -> DelegationPlan:
    if not isinstance(value, dict):
        raise ControlledDelegationError("delegation_plan_invalid")
    if set(value) != _ALLOWED_PLAN_FIELDS:
        raise ControlledDelegationError("delegation_plan_contains_unapproved_fields")
    if value.get("schema_version") != 1 or value.get("decision") != "delegate":
        raise ControlledDelegationError("delegation_plan_invalid")
    task_key = _required_string(value, "task_key")
    worker_kind = _required_string(value, "worker_kind")
    worker_key = _required_string(value, "worker_key")
    provider = _required_string(value, "provider")
    model = _required_string(value, "model")
    if worker_kind not in {"subagent", "application"}:
        raise ControlledDelegationError("delegation_worker_kind_not_allowed")
    if provider not in _ALLOWED_WORKER_PROVIDERS:
        raise ControlledDelegationError("delegation_provider_not_allowed")
    return DelegationPlan(
        task_key=task_key,
        worker_kind=worker_kind,
        worker_key=worker_key,
        provider=provider,
        model=model,
    )


def _as_dict(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ControlledDelegationError(f"{path}_invalid")
    return value


def _required_string(value: dict[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ControlledDelegationError(f"delegation_{key}_invalid")
    return item.strip()


def _result_artifact_type(execution_id: UUID) -> str:
    return f"{DELEGATION_RESULT_ARTIFACT_PREFIX}{execution_id.hex}"


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _integer_usage(usage: dict[str, object] | None, key: str) -> int | None:
    if usage is None:
        return None
    value = usage.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _decimal_usage(usage: dict[str, object] | None, key: str) -> Decimal | None:
    if usage is None:
        return None
    value = usage.get(key)
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _runtime_metadata(
    result: AgentRunResult,
    *,
    execution_id: UUID,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "delegation_execution_id": str(execution_id),
        "runner_version": result.runner_version,
        "exit_code": result.exit_code,
        "raw_output_hash": result.raw_output_hash,
        "duration_ms": result.duration_ms,
    }
    if result.session_id is not None:
        metadata["session_id"] = result.session_id
    if result.usage is not None:
        metadata["usage"] = result.usage
    if result.repository_revision is not None:
        metadata["repository_revision"] = result.repository_revision
    if result.repository_tree_hash is not None:
        metadata["repository_tree_hash"] = result.repository_tree_hash
    return metadata


__all__ = [
    "COORDINATOR_KEY",
    "COORDINATOR_PROVIDER",
    "COORDINATOR_TASK_KEY",
    "DELEGATION_PLAN_ARTIFACT_TYPE",
    "DELEGATION_PLAN_SCHEMA",
    "DELEGATION_RESULT_ARTIFACT_PREFIX",
    "ControlledDelegationBridge",
    "ControlledDelegationError",
    "ControlledDelegationRequest",
    "ControlledDelegationResult",
    "DelegationPlan",
    "DelegationRoute",
    "SettingsDelegationRouter",
    "persist_delegation_plan_artifact",
]
