from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.review_revise import (
    ReviewReviseGenerator,
    _revision_writer_input,
    unresolved_factual_claims,
)
from app.modules.content_engine.journal.review_revise_agent_bridge import (
    REVIEW_REVISE_ROUTE_TASK_KEY,
    REVIEW_REVISE_TIMEOUT_SECONDS,
    render_review_revise_prompt,
)
from app.modules.content_engine.journal.writer import (
    WriterGenerationError,
    WriterModelPort,
    _validate_model_output,
)
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
from app.modules.harness.models import Artifact, ContextManifest, ModelCall
from app.modules.harness.persistence import transition_run, transition_step_run
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

from .state import (
    REVIEW_REVISE_EN_COORDINATOR_PROMPT_VERSION,
    REVIEW_REVISE_EN_COORDINATOR_RECIPE_VERSION,
    REVIEW_REVISE_EN_MAX_ATTEMPTS,
    REVIEW_REVISE_EN_MAX_CYCLES,
    REVIEW_REVISE_EN_TASK_KEY,
    PreparedStage,
    ReviewReviseEnRequest,
    ReviewReviseEnResult,
    ReviewReviseOrchestrationError,
    completed_output_artifact_id,
    expected_attempt,
    find_manifest,
    human_gate,
    load_exact_stage,
    prepare_review_revise_en_orchestration,
    state_version,
)

_RETRYABLE_WORKER_ERRORS = {"agent_nonzero_exit", "agent_output_invalid", "agent_timeout"}


@dataclass(frozen=True, slots=True)
class _ExecutionResult:
    delegated: ControlledDelegationResult | None
    error_code: str | None = None


class _StaticReviewReviseModelPort(WriterModelPort):
    """Feed accepted delegated output into canonical persistence without another call."""

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


def _runner_metadata(result: AgentRunResult, *, observed_state: str) -> dict[str, object]:
    metadata: dict[str, object] = {
        "runner_version": result.runner_version,
        "raw_output_hash": result.raw_output_hash,
        "duration_ms": result.duration_ms,
        "orchestration_action_key": REVIEW_REVISE_EN_TASK_KEY,
        "orchestration_state_version": observed_state,
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


class ReviewReviseEnOrchestrationAdapter:
    """Journal-owned adapter for the single T05.22E EN review/revise stage."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        prepared: PreparedStage,
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

    async def _reload(self) -> PreparedStage:
        self._prepared = await load_exact_stage(self._session, prepared=self._prepared)
        return self._prepared

    async def observe(self) -> OrchestrationObservation:
        prepared = await self._reload()
        gate = human_gate(prepared.run)
        terminal = False
        if prepared.step.status == "completed":
            artifact_id = await completed_output_artifact_id(self._session, prepared=prepared)
            if artifact_id is None:
                raise ReviewReviseOrchestrationError("review_revise_completed_output_invalid")
            terminal = True
        return OrchestrationObservation(
            state_version=state_version(prepared),
            terminal=terminal,
            human_gate=gate,
        )

    def _authorized_route(self, prepared: PreparedStage) -> DelegationRoute:
        try:
            return self._delegation_router.resolve(
                task_key=REVIEW_REVISE_EN_TASK_KEY,
                settings_snapshot=prepared.settings_snapshot,
            )
        except ControlledDelegationError as exc:
            raise ReviewReviseOrchestrationError(exc.code) from exc

    async def _coordinator_manifest(self, prepared: PreparedStage) -> ContextManifest:
        manifest = await find_manifest(
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
        prepared: PreparedStage,
        *,
        observed_state: str,
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
        if metadata.get("orchestration_state_version") != observed_state:
            raise ReviewReviseOrchestrationError("review_revise_coordinator_state_stale")
        return call

    async def _create_coordinator_call(
        self,
        prepared: PreparedStage,
        *,
        observed_state: str,
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
            structured_output_schema=DELEGATION_PLAN_SCHEMA,
            working_context={
                "orchestration": {
                    "state_version": observed_state,
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
                    "orchestration_state_version": observed_state,
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
                runtime_metadata=_runner_metadata(result, observed_state=observed_state),
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
            runtime_metadata=_runner_metadata(result, observed_state=observed_state),
        )
        return call

    async def _coordinator_call(
        self,
        prepared: PreparedStage,
        *,
        observed_state: str,
    ) -> ModelCall:
        existing = await self._completed_coordinator_call(
            prepared,
            observed_state=observed_state,
        )
        if existing is not None:
            return existing
        return await self._create_coordinator_call(prepared, observed_state=observed_state)

    async def plan(self, observation: OrchestrationObservation) -> OrchestrationPlan:
        prepared = await self._reload()
        current = state_version(prepared)
        if current != observation.state_version:
            raise ReviewReviseOrchestrationError("review_revise_observation_stale")
        coordinator = await self._coordinator_call(prepared, observed_state=current)
        if coordinator.result_artifact_id is None:
            raise ReviewReviseOrchestrationError("review_revise_coordinator_plan_missing")
        artifact = await self._session.get(Artifact, coordinator.result_artifact_id)
        if artifact is None or not isinstance(artifact.content_json, dict):
            raise ReviewReviseOrchestrationError("review_revise_coordinator_plan_missing")
        action_key = artifact.content_json.get("task_key")
        if not isinstance(action_key, str) or not action_key:
            raise ReviewReviseOrchestrationError("review_revise_coordinator_plan_invalid")
        attempt = await expected_attempt(self._session, prepared=prepared)
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
        if state_version(prepared) != observation.state_version:
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="review_revise_state_version_stale",
            )
        if plan.action_key != REVIEW_REVISE_EN_TASK_KEY:
            return OrchestrationPolicyDecision(
                allowed=False,
                error_code="review_revise_action_not_allowed",
            )
        expected = await expected_attempt(self._session, prepared=prepared)
        if plan.attempt != expected:
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
            observed_state=observation.state_version,
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
        current = state_version(prepared)
        coordinator = await self._completed_coordinator_call(
            prepared,
            observed_state=current,
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
        if state_version(prepared) != observation.state_version:
            raise ReviewReviseOrchestrationError("review_revise_persist_state_stale")
        if not isinstance(result, _ExecutionResult):
            raise ReviewReviseOrchestrationError("review_revise_execution_result_invalid")
        if outcome == OrchestrationOutcome.ADVANCE:
            await self._persist_accepted(prepared, result, validation)
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
                await transition_run(self._session, run_id=prepared.run.id, status="failed")
        await self._session.flush()

    async def _persist_accepted(
        self,
        prepared: PreparedStage,
        result: _ExecutionResult,
        validation: OrchestrationValidation,
    ) -> None:
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
            expected_outline_version=prepared.review_input.writer_input.outline_artifact.version,
            expected_outline_hash=prepared.review_input.writer_input.outline_artifact.content_hash,
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
    orchestration: BoundedOrchestrationResult = await run_bounded_orchestration(
        adapter,
        max_cycles=max(max_attempts, REVIEW_REVISE_EN_MAX_CYCLES),
    )
    artifact_id = await completed_output_artifact_id(session, prepared=prepared)
    return ReviewReviseEnResult(
        orchestration=orchestration,
        revised_draft_artifact_id=artifact_id,
    )
