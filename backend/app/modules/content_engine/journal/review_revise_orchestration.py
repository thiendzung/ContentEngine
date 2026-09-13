"""T05.22E bounded orchestration for the EN Journal review/revise stage only."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.review_revise import (
    ReviewReviseGenerator,
    ReviewReviseInput,
    _revision_writer_input,
    load_review_revise_input,
    unresolved_factual_claims,
)
from app.modules.content_engine.journal.review_revise_agent_bridge import (
    REVIEW_REVISE_ROUTE_TASK_KEY,
    REVIEW_REVISE_TIMEOUT_SECONDS,
    render_review_revise_prompt,
    review_revise_registry_config,
)
from app.modules.content_engine.journal.writer import (
    WriterGenerationError,
    WriterModelPort,
    _validate_model_output,
)
from app.modules.content_engine.models import PromptDefinition, RecipeDefinition, SettingsSnapshot
from app.modules.harness.agent_runner import (
    CODEX_CLI_APPROVED_VERSION,
    AgentRunnerError,
    AgentRunnerRegistry,
    AgentRunRequest,
    AgentRunResult,
)
from app.modules.harness.bounded_orchestration import (
    BoundedOrchestrationResult,
    OrchestrationObservation,
    OrchestrationOutcome,
    OrchestrationPlan,
    OrchestrationPolicyDecision,
    OrchestrationValidation,
    run_bounded_orchestration,
)
from app.modules.harness.controlled_delegation import (
    COORDINATOR_TASK_KEY,
    DELEGATION_PLAN_SCHEMA,
    ControlledDelegationBridge,
    ControlledDelegationError,
    ControlledDelegationRequest,
    ControlledDelegationResult,
    DelegationRoute,
    SettingsDelegationRouter,
    persist_delegation_plan_artifact,
)
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.models import Artifact, ContentRun, ContextManifest, ModelCall, StepRun
from app.modules.harness.persistence import transition_run, transition_step_run
from app.modules.harness.repository_snapshot import RepositorySnapshotSpec
from app.modules.harness.runtime import (
    ContextInputs,
    ModelCandidate,
    ModelResponse,
    RuntimeConfigurationError,
    SettingsModelRouter,
    build_context_manifest,
    complete_model_call,
    fail_model_call,
    start_model_call,
)
from app.modules.system.settings_service import (
    SettingsResolutionError,
    active_prompt_definition,
    active_recipe_definition,
)

REVIEW_REVISE_EN_TASK_KEY = "review_revise_en"
REVIEW_REVISE_EN_COORDINATOR_PROMPT_VERSION = "review-revise-en-orchestration:v1"
REVIEW_REVISE_EN_COORDINATOR_RECIPE_VERSION = "review-revise-en-orchestration:v1"
REVIEW_REVISE_EN_MAX_ATTEMPTS = 2
REVIEW_REVISE_EN_MAX_CYCLES = 2

_RETRYABLE_WORKER_ERRORS = {
    "agent_nonzero_exit",
    "agent_output_invalid",
    "agent_timeout",
}
_HUMAN_GATE_STEPS = {"angle", "outline", "final_review"}


class ReviewReviseOrchestrationError(ValueError):
    """Fail-closed T05.22E error with one stable safe code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReviewReviseEnRequest:
    writer_run_id: UUID
    source_draft_artifact_id: UUID
    source_draft_version: int
    source_draft_hash: str
    outline_artifact_id: UUID
    outline_artifact_version: int
    outline_artifact_hash: str
    repository: RepositorySnapshotSpec


@dataclass(frozen=True, slots=True)
class ReviewReviseEnResult:
    orchestration: BoundedOrchestrationResult
    revised_draft_artifact_id: UUID | None


@dataclass(frozen=True, slots=True)
class _PreparedStage:
    request: ReviewReviseEnRequest
    review_input: ReviewReviseInput
    run: ContentRun
    step: StepRun
    manifest: ContextManifest
    settings_snapshot: SettingsSnapshot
    prompt: PromptDefinition
    recipe: RecipeDefinition
    prompt_version: str
    recipe_version: str


@dataclass(frozen=True, slots=True)
class _ExecutionResult:
    delegated: ControlledDelegationResult | None
    error_code: str | None = None


class _StaticReviewReviseModelPort(WriterModelPort):
    """Feed delegated output into canonical Journal persistence without another model call."""

    def __init__(self, output: object, *, provider: str, model: str) -> None:
        self._output = copy.deepcopy(output)
        self._provider = provider
        self._model = model
        self.calls = 0

    def resolved_model_identity(self) -> tuple[str, str]:
        return self._provider, self._model

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        del input_bundle, attempt
        self.calls += 1
        if self.calls != 1:
            raise WriterGenerationError("review_revise_orchestration_static_model_reused")
        return copy.deepcopy(self._output)


def _stable_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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


def _runner_metadata(result: AgentRunResult, *, state_version: str) -> dict[str, object]:
    metadata: dict[str, object] = {
        "runner_version": result.runner_version,
        "raw_output_hash": result.raw_output_hash,
        "duration_ms": result.duration_ms,
        "orchestration_action_key": REVIEW_REVISE_EN_TASK_KEY,
        "orchestration_state_version": state_version,
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


def _human_gate(run: ContentRun) -> str | None:
    if run.status == "waiting_approval" and run.current_step in _HUMAN_GATE_STEPS:
        return run.current_step
    return None


def _state_version(prepared: _PreparedStage) -> str:
    review_input = prepared.review_input
    run = prepared.run
    step = prepared.step
    return _stable_hash(
        {
            "content_case_id": str(run.content_case_id),
            "content_run_id": str(run.id),
            "locale_variant_id": str(run.locale_variant_id),
            "run_status": run.status,
            "current_step": run.current_step,
            "step_run_id": str(step.id),
            "step_status": step.status,
            "settings_snapshot_id": str(prepared.settings_snapshot.id),
            "settings_snapshot_hash": prepared.settings_snapshot.content_hash,
            "context_manifest_id": str(prepared.manifest.id),
            "context_manifest_hash": prepared.manifest.content_hash,
            "source_draft_artifact_id": str(review_input.source_artifact.id),
            "source_draft_version": review_input.source_artifact.version,
            "source_draft_hash": review_input.source_artifact.content_hash,
            "outline_artifact_id": str(review_input.writer_input.outline_artifact.id),
            "outline_artifact_version": review_input.writer_input.outline_artifact.version,
            "outline_artifact_hash": review_input.writer_input.outline_artifact.content_hash,
            "output_artifact_refs": step.output_artifact_refs_json,
        }
    )


def _retry_marker(step: StepRun) -> tuple[int, str] | None:
    error_json = step.error_json
    if not isinstance(error_json, dict):
        return None
    raw = error_json.get("orchestration")
    if not isinstance(raw, dict) or raw.get("status") != "retry_pending":
        return None
    attempt = raw.get("last_attempt")
    dedupe_key = raw.get("last_dedupe_key")
    if (
        not isinstance(attempt, int)
        or isinstance(attempt, bool)
        or attempt < 1
        or not isinstance(dedupe_key, str)
        or not dedupe_key
    ):
        raise ReviewReviseOrchestrationError("review_revise_retry_marker_invalid")
    return attempt, dedupe_key


async def _delegation_attempts(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
) -> list[DelegationExecution]:
    return list(
        (
            await session.scalars(
                select(DelegationExecution)
                .where(
                    DelegationExecution.run_id == run_id,
                    DelegationExecution.step_run_id == step_run_id,
                    DelegationExecution.task_key == REVIEW_REVISE_EN_TASK_KEY,
                )
                .order_by(DelegationExecution.attempt)
            )
        ).all()
    )


async def _expected_attempt(session: AsyncSession, *, prepared: _PreparedStage) -> int:
    marker = _retry_marker(prepared.step)
    if marker is not None:
        return marker[0] + 1
    attempts = await _delegation_attempts(
        session,
        run_id=prepared.run.id,
        step_run_id=prepared.step.id,
    )
    if not attempts:
        return 1
    latest = attempts[-1]
    if latest.status == "completed":
        return latest.attempt
    if latest.status in {"failed", "cancelled"}:
        return latest.attempt + 1
    if latest.status in {"queued", "running"}:
        return latest.attempt
    raise ReviewReviseOrchestrationError("review_revise_delegation_status_invalid")


async def _load_exact_stage(
    session: AsyncSession,
    *,
    prepared: _PreparedStage,
) -> _PreparedStage:
    review_input = await load_review_revise_input(
        session,
        writer_run_id=prepared.request.writer_run_id,
        source_draft_artifact_id=prepared.request.source_draft_artifact_id,
        expected_source_draft_version=prepared.request.source_draft_version,
        expected_source_draft_hash=prepared.request.source_draft_hash,
        outline_artifact_id=prepared.request.outline_artifact_id,
        expected_outline_version=prepared.request.outline_artifact_version,
        expected_outline_hash=prepared.request.outline_artifact_hash,
        locale="en",
    )
    run = await session.get(ContentRun, prepared.run.id)
    step = await session.get(StepRun, prepared.step.id)
    manifest = await session.get(ContextManifest, prepared.manifest.id)
    snapshot = await session.get(SettingsSnapshot, prepared.settings_snapshot.id)
    if run is None or run.id != review_input.writer_input.writer_run.id:
        raise ReviewReviseOrchestrationError("review_revise_run_stale")
    if step is None or step.run_id != run.id or step.step_key != REVIEW_REVISE_EN_TASK_KEY:
        raise ReviewReviseOrchestrationError("review_revise_step_stale")
    if manifest is None or manifest.run_id != run.id or manifest.step_run_id != step.id:
        raise ReviewReviseOrchestrationError("review_revise_manifest_stale")
    if snapshot is None or snapshot.id != run.settings_snapshot_id:
        raise ReviewReviseOrchestrationError("review_revise_settings_snapshot_stale")
    if manifest.settings_snapshot_id != snapshot.id:
        raise ReviewReviseOrchestrationError("review_revise_manifest_settings_mismatch")
    if manifest.prompt_version != prepared.prompt_version:
        raise ReviewReviseOrchestrationError("review_revise_prompt_snapshot_mismatch")
    if manifest.recipe_version != prepared.recipe_version:
        raise ReviewReviseOrchestrationError("review_revise_recipe_snapshot_mismatch")
    return _PreparedStage(
        request=prepared.request,
        review_input=review_input,
        run=run,
        step=step,
        manifest=manifest,
        settings_snapshot=snapshot,
        prompt=prepared.prompt,
        recipe=prepared.recipe,
        prompt_version=prepared.prompt_version,
        recipe_version=prepared.recipe_version,
    )


async def _find_manifest(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
    prompt_version: str,
    recipe_version: str,
) -> ContextManifest | None:
    rows = list(
        (
            await session.scalars(
                select(ContextManifest).where(
                    ContextManifest.run_id == run_id,
                    ContextManifest.step_run_id == step_run_id,
                    ContextManifest.prompt_version == prompt_version,
                    ContextManifest.recipe_version == recipe_version,
                )
            )
        ).all()
    )
    if len(rows) > 1:
        raise ReviewReviseOrchestrationError("review_revise_context_manifest_duplicate")
    return rows[0] if rows else None


async def prepare_review_revise_en_orchestration(
    session: AsyncSession,
    *,
    request: ReviewReviseEnRequest,
) -> _PreparedStage:
    """Load exact lineage and create/reuse only the stage-owned StepRun/manifest."""

    review_input = await load_review_revise_input(
        session,
        writer_run_id=request.writer_run_id,
        source_draft_artifact_id=request.source_draft_artifact_id,
        expected_source_draft_version=request.source_draft_version,
        expected_source_draft_hash=request.source_draft_hash,
        outline_artifact_id=request.outline_artifact_id,
        expected_outline_version=request.outline_artifact_version,
        expected_outline_hash=request.outline_artifact_hash,
        locale="en",
    )
    run = review_input.writer_input.writer_run
    if review_input.writer_input.locale != "en":
        raise ReviewReviseOrchestrationError("review_revise_en_locale_required")
    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None:
        raise ReviewReviseOrchestrationError("review_revise_settings_snapshot_missing")

    config = review_revise_registry_config("en")
    try:
        prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=config.recipe_key,
            content_type="journal",
            locale="en",
            task_key=config.task_key,
        )
    except SettingsResolutionError as exc:
        raise ReviewReviseOrchestrationError("review_revise_registry_missing") from exc
    prompt_version = f"{prompt.prompt_key}:v{prompt.version}"
    recipe_version = f"{recipe.recipe_key}:v{recipe.version}"

    steps = list(
        (
            await session.scalars(
                select(StepRun)
                .where(
                    StepRun.run_id == run.id,
                    StepRun.step_key == REVIEW_REVISE_EN_TASK_KEY,
                )
                .order_by(StepRun.attempt)
            )
        ).all()
    )
    if len(steps) > 1:
        raise ReviewReviseOrchestrationError("review_revise_step_attempt_conflict")
    if steps:
        step = steps[0]
        if step.status in {"failed", "skipped"}:
            raise ReviewReviseOrchestrationError("review_revise_step_terminal_not_reusable")
    else:
        step = StepRun(
            run_id=run.id,
            step_key=REVIEW_REVISE_EN_TASK_KEY,
            attempt=1,
            status="pending",
            input_artifact_refs_json=[
                str(review_input.source_artifact.id),
                str(review_input.writer_input.handoff_artifact.id),
                str(review_input.writer_input.outline_artifact.id),
            ],
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()

    manifest = await _find_manifest(
        session,
        run_id=run.id,
        step_run_id=step.id,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )
    if manifest is None:
        if step.status == "completed":
            raise ReviewReviseOrchestrationError("review_revise_context_manifest_missing")
        upstream = review_input.writer_input.outline_input.bundle.context_manifest
        manifest = await build_context_manifest(
            session,
            run_id=run.id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                evidence_set_id=review_input.writer_input.outline_input.bundle.evidence_set_id,
                originality_pack_id=(
                    review_input.writer_input.outline_input.bundle.originality_pack_id
                ),
                approved_knowledge_refs=(
                    tuple(upstream.approved_knowledge_refs_json) if upstream is not None else ()
                ),
                knowledge_chunk_refs=(
                    tuple(upstream.knowledge_chunk_refs_json) if upstream is not None else ()
                ),
                golden_example_refs=(
                    tuple(upstream.golden_example_refs_json) if upstream is not None else ()
                ),
                tool_result_refs=(
                    tuple(upstream.tool_result_refs_json) if upstream is not None else ()
                ),
            ),
        )

    gate = _human_gate(run)
    if gate is None and step.status == "pending":
        if run.status not in {"pending", "waiting_approval"}:
            raise ReviewReviseOrchestrationError("review_revise_run_state_invalid")
        await transition_run(session, run_id=run.id, status="running")
        run.current_step = REVIEW_REVISE_EN_TASK_KEY
        await transition_step_run(session, step_run_id=step.id, status="running")
    elif gate is None and step.status == "running":
        if run.status != "running" or run.current_step != REVIEW_REVISE_EN_TASK_KEY:
            raise ReviewReviseOrchestrationError("review_revise_running_state_mismatch")
    elif gate is None and step.status == "completed" and not step.output_artifact_refs_json:
        raise ReviewReviseOrchestrationError("review_revise_completed_output_missing")

    await session.flush()
    return _PreparedStage(
        request=request,
        review_input=review_input,
        run=run,
        step=step,
        manifest=manifest,
        settings_snapshot=snapshot,
        prompt=prompt,
        recipe=recipe,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )


class ReviewReviseEnOrchestrationAdapter:
    """Journal-owned adapter for the single T05.22E EN review/revise stage."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        prepared: _PreparedStage,
        runner_registry: AgentRunnerRegistry,
        max_attempts: int = REVIEW_REVISE_EN_MAX_ATTEMPTS,
    ) -> None:
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError("max_attempts must be between 1 and 3")
        self._session = session
        self._prepared = prepared
        self._runner_registry = runner_registry
        self._bridge = ControlledDelegationBridge(runner_registry)
        self._delegation_router = SettingsDelegationRouter()
        self._max_attempts = max_attempts

    async def _reload(self) -> _PreparedStage:
        self._prepared = await _load_exact_stage(self._session, prepared=self._prepared)
        return self._prepared

    async def observe(self) -> OrchestrationObservation:
        prepared = await self._reload()
        gate = _human_gate(prepared.run)
        terminal = False
        if prepared.step.status == "completed":
            if len(prepared.step.output_artifact_refs_json) != 1:
                raise ReviewReviseOrchestrationError("review_revise_completed_output_invalid")
            try:
                artifact_id = UUID(prepared.step.output_artifact_refs_json[0])
            except ValueError as exc:
                raise ReviewReviseOrchestrationError(
                    "review_revise_completed_output_invalid"
                ) from exc
            artifact = await self._session.get(Artifact, artifact_id)
            if (
                artifact is None
                or artifact.run_id != prepared.run.id
                or artifact.artifact_type != "journal_draft"
                or artifact.locale != "en"
            ):
                raise ReviewReviseOrchestrationError("review_revise_completed_output_invalid")
            terminal = True
        return OrchestrationObservation(
            state_version=_state_version(prepared),
            terminal=terminal,
            human_gate=gate,
        )

    def _authorized_route(self, prepared: _PreparedStage) -> DelegationRoute:
        try:
            return self._delegation_router.resolve(
                task_key=REVIEW_REVISE_EN_TASK_KEY,
                settings_snapshot=prepared.settings_snapshot,
            )
        except ControlledDelegationError as exc:
            raise ReviewReviseOrchestrationError(exc.code) from exc

    async def _coordinator_manifest(self, prepared: _PreparedStage) -> ContextManifest:
        manifest = await _find_manifest(
            self._session,
            run_id=prepared.run.id,
            step_run_id=prepared.step.id,
            prompt_version=REVIEW_REVISE_EN_COORDINATOR_PROMPT_VERSION,
            recipe_version=REVIEW_REVISE_EN_COORDINATOR_RECIPE_VERSION,
        )
        if manifest is not None:
            return manifest
        worker_manifest = prepared.manifest
        return await build_context_manifest(
            self._session,
            run_id=prepared.run.id,
            step_run_id=prepared.step.id,
            inputs=ContextInputs(
                prompt_version=REVIEW_REVISE_EN_COORDINATOR_PROMPT_VERSION,
                recipe_version=REVIEW_REVISE_EN_COORDINATOR_RECIPE_VERSION,
                evidence_set_id=worker_manifest.evidence_set_id,
                originality_pack_id=worker_manifest.originality_pack_id,
                context_artifact_id=worker_manifest.context_artifact_id,
                approved_knowledge_refs=tuple(worker_manifest.approved_knowledge_refs_json),
                knowledge_chunk_refs=tuple(worker_manifest.knowledge_chunk_refs_json),
                golden_example_refs=tuple(worker_manifest.golden_example_refs_json),
                tool_result_refs=tuple(worker_manifest.tool_result_refs_json),
            ),
        )

    async def _completed_coordinator_call(
        self,
        prepared: _PreparedStage,
        *,
        state_version: str,
    ) -> ModelCall | None:
        calls = list(
            (
                await self._session.scalars(
                    select(ModelCall)
                    .where(
                        ModelCall.run_id == prepared.run.id,
                        ModelCall.step_run_id == prepared.step.id,
                        ModelCall.task_key == COORDINATOR_TASK_KEY,
                    )
                    .order_by(ModelCall.created_at)
                )
            ).all()
        )
        completed: list[ModelCall] = []
        for call in calls:
            metadata = call.runtime_metadata_json or {}
            if metadata.get("orchestration_action_key") != REVIEW_REVISE_EN_TASK_KEY:
                continue
            if call.status == "running":
                raise ReviewReviseOrchestrationError("review_revise_coordinator_already_running")
            if call.status == "completed":
                completed.append(call)
        if len(completed) > 1:
            raise ReviewReviseOrchestrationError("review_revise_coordinator_duplicate")
        if not completed:
            return None
        call = completed[0]
        metadata = call.runtime_metadata_json or {}
        if metadata.get("orchestration_state_version") != state_version:
            raise ReviewReviseOrchestrationError("review_revise_coordinator_state_stale")
        return call

    async def _create_coordinator_call(
        self,
        prepared: _PreparedStage,
        *,
        state_version: str,
    ) -> ModelCall:
        route = self._authorized_route(prepared)
        try:
            coordinator_route = SettingsModelRouter().resolve(
                task_key=REVIEW_REVISE_ROUTE_TASK_KEY,
                settings_snapshot=prepared.settings_snapshot,
            )
        except RuntimeConfigurationError as exc:
            raise ReviewReviseOrchestrationError("review_revise_coordinator_route_missing") from exc
        if coordinator_route.primary.provider != "codex_cli":
            raise ReviewReviseOrchestrationError("review_revise_coordinator_must_be_codex")
        try:
            runner = self._runner_registry.get("codex_cli")
        except AgentRunnerError as exc:
            raise ReviewReviseOrchestrationError(exc.code) from exc

        manifest = await self._coordinator_manifest(prepared)
        call = await start_model_call(
            self._session,
            run_id=prepared.run.id,
            step_run_id=prepared.step.id,
            context_manifest_id=manifest.id,
            task_key=COORDINATOR_TASK_KEY,
            route=ModelCandidate(
                provider=coordinator_route.primary.provider,
                model=coordinator_route.primary.model,
            ),
            purpose="Choose the single bounded T05.22E delegated action",
            prompt_version=REVIEW_REVISE_EN_COORDINATOR_PROMPT_VERSION,
        )
        request = AgentRunRequest(
            provider="codex_cli",
            model=coordinator_route.primary.model,
            prompt=(
                "Return only the structural delegation JSON required by the output schema. "
                "This bounded slice permits exactly one executable action: review_revise_en. "
                "Do not return rationale or chain-of-thought."
            ),
            structured_output_schema=cast(dict[str, object], DELEGATION_PLAN_SCHEMA),
            working_context={
                "orchestration": {
                    "state_version": state_version,
                    "content_case_id": str(prepared.run.content_case_id),
                    "content_run_id": str(prepared.run.id),
                    "locale_variant_id": str(prepared.run.locale_variant_id),
                    "step_run_id": str(prepared.step.id),
                    "allowed_action": REVIEW_REVISE_EN_TASK_KEY,
                    "authorized_route": {
                        "worker_kind": route.worker_kind,
                        "worker_key": route.worker_key,
                        "provider": route.provider,
                        "model": route.model,
                    },
                }
            },
            timeout=REVIEW_REVISE_TIMEOUT_SECONDS,
            repository=prepared.request.repository,
        )
        try:
            result = await runner.run(request)
        except AgentRunnerError as exc:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class=exc.code,
                runtime_metadata={
                    "orchestration_action_key": REVIEW_REVISE_EN_TASK_KEY,
                    "orchestration_state_version": state_version,
                    "runner_error": exc.code,
                },
            )
            raise ReviewReviseOrchestrationError(exc.code) from exc
        if result.provider != request.provider or result.model != request.model:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class="review_revise_coordinator_result_route_mismatch",
            )
            raise ReviewReviseOrchestrationError(
                "review_revise_coordinator_result_route_mismatch"
            )
        if result.runner_version != CODEX_CLI_APPROVED_VERSION:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class="agent_runner_version_not_approved",
            )
            raise ReviewReviseOrchestrationError("agent_runner_version_not_approved")
        try:
            artifact = await persist_delegation_plan_artifact(
                self._session,
                run_id=prepared.run.id,
                step_run_id=prepared.step.id,
                plan=result.structured_output,
            )
        except ControlledDelegationError as exc:
            await fail_model_call(
                self._session,
                call_id=call.id,
                error_class=exc.code,
                runtime_metadata=_runner_metadata(result, state_version=state_version),
            )
            raise ReviewReviseOrchestrationError(exc.code) from exc
        await complete_model_call(
            self._session,
            call_id=call.id,
            response=ModelResponse(
                content=json.dumps(
                    artifact.content_json,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                input_tokens=_integer_usage(result.usage, "input_tokens"),
                output_tokens=_integer_usage(result.usage, "output_tokens"),
                cost=_decimal_usage(result.usage, "cost"),
                latency_ms=result.duration_ms,
                finish_reason="stop",
            ),
            result_artifact_id=artifact.id,
            runtime_metadata=_runner_metadata(result, state_version=state_version),
        )
        return call

    async def _coordinator_call(
        self,
        prepared: _PreparedStage,
        *,
        state_version: str,
    ) -> ModelCall:
        existing = await self._completed_coordinator_call(
            prepared,
            state_version=state_version,
        )
        if existing is not None:
            return existing
        return await self._create_coordinator_call(prepared, state_version=state_version)

    async def plan(self, observation: OrchestrationObservation) -> OrchestrationPlan:
        prepared = await self._reload()
        current = _state_version(prepared)
        if current != observation.state_version:
            raise ReviewReviseOrchestrationError("review_revise_observation_stale")
        coordinator = await self._coordinator_call(prepared, state_version=current)
        if coordinator.result_artifact_id is None:
            raise ReviewReviseOrchestrationError("review_revise_coordinator_plan_missing")
        artifact = await self._session.get(Artifact, coordinator.result_artifact_id)
        if artifact is None or not isinstance(artifact.content_json, dict):
            raise ReviewReviseOrchestrationError("review_revise_coordinator_plan_missing")
        action_key = artifact.content_json.get("task_key")
        if not isinstance(action_key, str) or not action_key:
            raise ReviewReviseOrchestrationError("review_revise_coordinator_plan_invalid")
        attempt = await _expected_attempt(self._session, prepared=prepared)
        dedupe_key = (
            f"journal:{prepared.run.id}:review-revise-en:{current[:20]}:attempt:{attempt}"
        )
        return OrchestrationPlan(
            action_key=action_key,
            dedupe_key=dedupe_key,
            attempt=attempt,
            max_attempts=self._max_attempts,
        )

    async def policy_check(
        self,
        observation: OrchestrationObservation,
        plan: OrchestrationPlan,
    ) -> OrchestrationPolicyDecision:
        prepared = await self._reload()
        if _state_version(prepared) != observation.state_version:
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="review_revise_state_version_stale",
            )
        if plan.action_key != REVIEW_REVISE_EN_TASK_KEY:
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="review_revise_action_not_allowed",
            )
        expected_attempt = await _expected_attempt(self._session, prepared=prepared)
        if plan.attempt != expected_attempt:
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="review_revise_attempt_stale",
            )
        if plan.attempt > self._max_attempts:
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="review_revise_retry_budget_exhausted",
            )
        try:
            route = self._delegation_router.resolve(
                task_key=REVIEW_REVISE_EN_TASK_KEY,
                settings_snapshot=prepared.settings_snapshot,
            )
        except ControlledDelegationError as exc:
            return OrchestrationPolicyDecision(allowed=False, error_code=exc.code)
        if route.provider == "antigravity_cli":
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="agent_repository_isolation_unproven",
            )
        if route.provider != "codex_cli" or route.worker_kind != "subagent":
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="review_revise_worker_route_not_allowed",
            )
        coordinator = await self._completed_coordinator_call(
            prepared,
            state_version=observation.state_version,
        )
        if coordinator is None or coordinator.result_artifact_id is None:
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="review_revise_coordinator_plan_missing",
            )
        artifact = await self._session.get(Artifact, coordinator.result_artifact_id)
        payload = artifact.content_json if artifact is not None else None
        if not isinstance(payload, dict):
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="review_revise_coordinator_plan_missing",
            )
        if (
            payload.get("task_key"),
            payload.get("worker_kind"),
            payload.get("worker_key"),
            payload.get("provider"),
            payload.get("model"),
        ) != (
            route.task_key,
            route.worker_kind,
            route.worker_key,
            route.provider,
            route.model,
        ):
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="review_revise_plan_route_mismatch",
            )
        running = await self._session.scalar(
            select(DelegationExecution).where(
                DelegationExecution.dedupe_key == plan.dedupe_key,
                DelegationExecution.status == "running",
            )
        )
        if running is not None:
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="delegation_already_running",
            )
        return OrchestrationPolicyDecision(allowed=True)

    async def execute(self, plan: OrchestrationPlan) -> _ExecutionResult:
        prepared = await self._reload()
        state_version = _state_version(prepared)
        coordinator = await self._completed_coordinator_call(
            prepared,
            state_version=state_version,
        )
        if coordinator is None:
            return _ExecutionResult(None, "review_revise_coordinator_plan_missing")
        prompt = render_review_revise_prompt(
            prepared.prompt,
            prepared.recipe,
            review_model_input=prepared.review_input.model_input,
            attempt=plan.attempt,
        )
        try:
            delegated = await self._bridge.execute(
                self._session,
                request=ControlledDelegationRequest(
                    run_id=prepared.run.id,
                    step_run_id=prepared.step.id,
                    coordinator_model_call_id=coordinator.id,
                    worker_context_manifest_id=prepared.manifest.id,
                    prompt_version=prepared.prompt_version,
                    prompt=prompt,
                    structured_output_schema=prepared.prompt.output_schema_json,
                    working_context={
                        "review_revise_model_input": copy.deepcopy(
                            prepared.review_input.model_input
                        )
                    },
                    purpose="Review and revise the EN Journal draft",
                    dedupe_key=plan.dedupe_key,
                    attempt=plan.attempt,
                    timeout=REVIEW_REVISE_TIMEOUT_SECONDS,
                    repository=prepared.request.repository,
                ),
            )
        except ControlledDelegationError as exc:
            return _ExecutionResult(None, exc.code)
        return _ExecutionResult(delegated=delegated)

    async def validate(
        self,
        plan: OrchestrationPlan,
        result: object,
    ) -> OrchestrationValidation:
        del plan
        if not isinstance(result, _ExecutionResult):
            return OrchestrationValidation(
                accepted=False,
                retryable=False,
                error_code="review_revise_execution_result_invalid",
            )
        if result.error_code is not None:
            return OrchestrationValidation(
                accepted=False,
                retryable=result.error_code in _RETRYABLE_WORKER_ERRORS,
                error_code=result.error_code,
            )
        if result.delegated is None or result.delegated.structured_output is None:
            return OrchestrationValidation(
                accepted=False,
                retryable=False,
                error_code="review_revise_delegated_output_missing",
            )
        prepared = await self._reload()
        writer_input = _revision_writer_input(prepared.review_input)
        try:
            draft = _validate_model_output(
                result.delegated.structured_output,
                writer_input=writer_input,
            )
            if unresolved_factual_claims(draft):
                raise WriterGenerationError("review_revise_unresolved_remaining")
        except WriterGenerationError as exc:
            return OrchestrationValidation(
                accepted=False,
                retryable=True,
                error_code=exc.code,
            )
        return OrchestrationValidation(accepted=True)

    async def persist(
        self,
        observation: OrchestrationObservation,
        plan: OrchestrationPlan,
        result: object,
        validation: OrchestrationValidation,
        outcome: OrchestrationOutcome,
    ) -> None:
        prepared = await self._reload()
        if _state_version(prepared) != observation.state_version:
            raise ReviewReviseOrchestrationError("review_revise_persist_state_stale")
        if not isinstance(result, _ExecutionResult):
            raise ReviewReviseOrchestrationError("review_revise_execution_result_invalid")
        if outcome == OrchestrationOutcome.ADVANCE:
            if not validation.accepted or result.delegated is None:
                raise ReviewReviseOrchestrationError("review_revise_advance_without_output")
            route = self._authorized_route(prepared)
            model = _StaticReviewReviseModelPort(
                result.delegated.structured_output,
                provider=route.provider,
                model=route.model,
            )
            canonical = await ReviewReviseGenerator(max_attempts=1).revise_draft(
                self._session,
                writer_run_id=prepared.run.id,
                source_draft_artifact_id=prepared.review_input.source_artifact.id,
                expected_source_draft_version=prepared.review_input.source_artifact.version,
                expected_source_draft_hash=prepared.review_input.source_artifact.content_hash,
                outline_artifact_id=prepared.review_input.writer_input.outline_artifact.id,
                expected_outline_version=(
                    prepared.review_input.writer_input.outline_artifact.version
                ),
                expected_outline_hash=(
                    prepared.review_input.writer_input.outline_artifact.content_hash
                ),
                locale="en",
                model=model,
                provider=route.provider,
                model_name=route.model,
                context_manifest_id=prepared.manifest.id,
                prompt_version=prepared.prompt_version,
                recipe_version=prepared.recipe_version,
            )
            prepared.step.output_artifact_refs_json = [str(canonical.artifact.id)]
            prepared.step.error_json = None
            if prepared.step.status == "running":
                await transition_step_run(
                    self._session,
                    step_run_id=prepared.step.id,
                    status="completed",
                )
            if prepared.run.status == "running":
                await transition_run(
                    self._session,
                    run_id=prepared.run.id,
                    status="waiting_approval",
                )
            await self._session.flush()
            return

        error_code = validation.error_code or result.error_code or "review_revise_validation_failed"
        prepared.step.error_json = {
            "orchestration": {
                "status": "retry_pending" if outcome == OrchestrationOutcome.RETRY else "blocked",
                "last_attempt": plan.attempt,
                "last_dedupe_key": plan.dedupe_key,
                "error_code": error_code,
            }
        }
        if outcome == OrchestrationOutcome.BLOCKED:
            if prepared.step.status == "running":
                await transition_step_run(
                    self._session,
                    step_run_id=prepared.step.id,
                    status="failed",
                )
            if prepared.run.status == "running":
                prepared.run.failure_code = "review_revise_en_blocked"
                prepared.run.failure_message = error_code
                await transition_run(
                    self._session,
                    run_id=prepared.run.id,
                    status="failed",
                )
        await self._session.flush()


async def _completed_output_artifact_id(
    session: AsyncSession,
    *,
    prepared: _PreparedStage,
) -> UUID | None:
    stage = await _load_exact_stage(session, prepared=prepared)
    if stage.step.status != "completed" or len(stage.step.output_artifact_refs_json) != 1:
        return None
    try:
        artifact_id = UUID(stage.step.output_artifact_refs_json[0])
    except ValueError as exc:
        raise ReviewReviseOrchestrationError("review_revise_completed_output_invalid") from exc
    artifact = await session.get(Artifact, artifact_id)
    if (
        artifact is None
        or artifact.run_id != stage.run.id
        or artifact.artifact_type != "journal_draft"
        or artifact.locale != "en"
    ):
        raise ReviewReviseOrchestrationError("review_revise_completed_output_invalid")
    return artifact.id


async def run_review_revise_en_orchestration(
    session: AsyncSession,
    *,
    request: ReviewReviseEnRequest,
    runner_registry: AgentRunnerRegistry,
    max_attempts: int = REVIEW_REVISE_EN_MAX_ATTEMPTS,
) -> ReviewReviseEnResult:
    """Run exactly one real EN review/revise stage through the bounded harness."""

    prepared = await prepare_review_revise_en_orchestration(session, request=request)
    adapter = ReviewReviseEnOrchestrationAdapter(
        session,
        prepared=prepared,
        runner_registry=runner_registry,
        max_attempts=max_attempts,
    )
    result = await run_bounded_orchestration(
        adapter,
        max_cycles=max(max_attempts, REVIEW_REVISE_EN_MAX_CYCLES),
    )
    artifact_id = await _completed_output_artifact_id(session, prepared=prepared)
    return ReviewReviseEnResult(
        orchestration=result,
        revised_draft_artifact_id=artifact_id,
    )


__all__ = [
    "REVIEW_REVISE_EN_MAX_ATTEMPTS",
    "REVIEW_REVISE_EN_TASK_KEY",
    "ReviewReviseEnOrchestrationAdapter",
    "ReviewReviseEnRequest",
    "ReviewReviseEnResult",
    "ReviewReviseOrchestrationError",
    "prepare_review_revise_en_orchestration",
    "run_review_revise_en_orchestration",
]
