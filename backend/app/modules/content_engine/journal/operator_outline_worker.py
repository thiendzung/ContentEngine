"""Durable worker execution for the F2 Angle-to-Outline continuation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import AngleApproval, OperatorCommand
from app.modules.content_engine.journal.operator_runtime import get_operator_state
from app.modules.content_engine.journal.outline import (
    OutlineGenerationError,
    OutlineGenerator,
    OutlineInput,
    load_outline_input,
)
from app.modules.content_engine.journal.outline_agent_bridge import (
    OUTLINE_PROMPT_KEY,
    OUTLINE_RECIPE_KEY,
    OUTLINE_ROUTE_TASK_KEY,
    OUTLINE_TASK_KEY,
    create_cli_outline_model_port,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import AgentRunnerError, AgentRunnerRegistry
from app.modules.harness.models import ContentRun, ContextManifest, Job, StepRun
from app.modules.harness.persistence import complete_job, create_checkpoint, transition_run
from app.modules.harness.runtime import (
    ContextInputs,
    RuntimeConfigurationError,
    SettingsModelRouter,
    build_context_manifest,
)
from app.modules.system.settings_service import (
    SettingsResolutionError,
    active_prompt_definition,
    active_recipe_definition,
)


class OperatorOutlineWorkerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutlineWorkerExecutionResult:
    job_id: UUID
    run_id: UUID
    step_run_id: UUID
    outline_artifact_id: UUID
    outline_artifact_hash: str
    state_version: str


async def _claim_new_outline_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int,
) -> Job | None:
    if not worker_id.strip() or lease_seconds <= 0:
        raise OperatorOutlineWorkerError("operator_worker_lease_invalid")
    now = datetime.now(UTC)
    candidate = (
        select(Job.id)
        .join(StepRun, StepRun.id == Job.step_run_id)
        .where(
            Job.status == "queued",
            Job.available_at <= now,
            StepRun.step_key == OUTLINE_TASK_KEY,
            StepRun.status.in_(("pending", "running")),
        )
        .order_by(Job.available_at, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .cte("next_outline_operator_job")
    )
    statement = (
        update(Job)
        .where(Job.id == candidate.c.id)
        .values(
            status="leased",
            lease_owner=worker_id,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            updated_at=now,
        )
        .returning(Job)
    )
    job = (await session.execute(statement)).scalar_one_or_none()
    if job is None:
        return None
    await session.execute(
        update(StepRun)
        .where(StepRun.id == job.step_run_id, StepRun.status == "pending")
        .values(status="running", started_at=now, updated_at=now)
    )
    return job


async def _reclaim_expired_outline_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int,
) -> Job | None:
    if not worker_id.strip() or lease_seconds <= 0:
        raise OperatorOutlineWorkerError("operator_worker_lease_invalid")
    now = datetime.now(UTC)
    candidate = (
        select(Job.id)
        .join(StepRun, StepRun.id == Job.step_run_id)
        .where(
            Job.status == "leased",
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at < now,
            StepRun.step_key == OUTLINE_TASK_KEY,
            StepRun.status == "running",
        )
        .order_by(Job.lease_expires_at, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .cte("expired_outline_operator_job")
    )
    statement = (
        update(Job)
        .where(Job.id == candidate.c.id)
        .values(
            attempt=Job.attempt + 1,
            lease_owner=worker_id,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            updated_at=now,
        )
        .returning(Job)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def claim_or_reclaim_outline_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int = 900,
) -> Job | None:
    recovered = await _reclaim_expired_outline_job(
        session,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )
    if recovered is not None:
        return recovered
    return await _claim_new_outline_job(
        session,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )


async def _exact_angle_approval(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> AngleApproval:
    approvals = list(
        (
            await session.scalars(
                select(AngleApproval)
                .where(AngleApproval.run_id == run_id)
                .order_by(AngleApproval.created_at, AngleApproval.id)
            )
        ).all()
    )
    if len(approvals) != 1:
        raise OperatorOutlineWorkerError("operator_outline_angle_approval_conflict")
    return approvals[0]


async def _outline_manifest(
    session: AsyncSession,
    *,
    run: ContentRun,
    step: StepRun,
    prompt_version: str,
    recipe_version: str,
    outline_input: OutlineInput,
) -> ContextManifest:
    rows = list(
        (
            await session.scalars(
                select(ContextManifest)
                .where(
                    ContextManifest.run_id == run.id,
                    ContextManifest.step_run_id == step.id,
                )
                .order_by(ContextManifest.created_at, ContextManifest.id)
            )
        ).all()
    )
    if len(rows) > 1:
        raise OperatorOutlineWorkerError("operator_outline_context_manifest_conflict")
    if rows:
        manifest = rows[0]
        if manifest.prompt_version != prompt_version or manifest.recipe_version != recipe_version:
            raise OperatorOutlineWorkerError("operator_outline_registry_changed")
        return manifest

    bundle = outline_input.bundle
    upstream = bundle.context_manifest
    return await build_context_manifest(
        session,
        run_id=run.id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version=prompt_version,
            recipe_version=recipe_version,
            evidence_set_id=bundle.evidence_set_id,
            originality_pack_id=bundle.originality_pack_id,
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


async def execute_outline_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    runner_registry: AgentRunnerRegistry,
) -> OutlineWorkerExecutionResult:
    job = await session.get(Job, job_id)
    if (
        job is None
        or job.status != "leased"
        or job.lease_owner != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= datetime.now(UTC)
    ):
        raise OperatorOutlineWorkerError("operator_worker_lease_not_owned")
    step = await session.get(StepRun, job.step_run_id)
    run = await session.get(ContentRun, job.run_id)
    if step is None or run is None or step.run_id != run.id:
        raise OperatorOutlineWorkerError("operator_worker_binding_invalid")
    if step.step_key != OUTLINE_TASK_KEY or step.status != "running":
        raise OperatorOutlineWorkerError("operator_worker_stage_not_allowed")
    if run.status != "running" or run.current_step != OUTLINE_TASK_KEY:
        raise OperatorOutlineWorkerError("operator_worker_run_state_invalid")

    approval = await _exact_angle_approval(session, run_id=run.id)
    try:
        outline_input = await load_outline_input(
            session,
            angle_artifact_id=approval.angle_artifact_id,
            expected_angle_artifact_version=approval.angle_artifact_version,
            expected_angle_artifact_hash=approval.angle_artifact_hash,
            selected_angle_id=approval.selected_angle_id,
            expected_candidate_hash=approval.selected_candidate_hash,
            expected_approval_id=approval.id,
        )
    except OutlineGenerationError as exc:
        raise OperatorOutlineWorkerError("operator_outline_input_invalid") from exc
    if outline_input.approved_angle.artifact.run_id != run.id:
        raise OperatorOutlineWorkerError("operator_outline_run_mismatch")

    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None:
        raise OperatorOutlineWorkerError("operator_outline_settings_missing")
    try:
        route = SettingsModelRouter().resolve(
            task_key=OUTLINE_ROUTE_TASK_KEY,
            settings_snapshot=snapshot,
        )
    except RuntimeConfigurationError as exc:
        raise OperatorOutlineWorkerError("operator_outline_route_invalid") from exc
    if route.primary.provider != "codex_cli" or not route.primary.model.strip():
        raise OperatorOutlineWorkerError("operator_outline_route_not_allowed")

    try:
        prompt = await active_prompt_definition(session, prompt_key=OUTLINE_PROMPT_KEY)
        recipe = await active_recipe_definition(
            session,
            recipe_key=OUTLINE_RECIPE_KEY,
            content_type="journal",
            locale=outline_input.approved_angle.candidate.locale,
            task_key=OUTLINE_TASK_KEY,
        )
    except SettingsResolutionError as exc:
        raise OperatorOutlineWorkerError("operator_outline_registry_blocked") from exc
    prompt_version = f"{prompt.prompt_key}:v{prompt.version}"
    recipe_version = f"{recipe.recipe_key}:v{recipe.version}"

    try:
        runner = runner_registry.get(route.primary.provider)
        capability = await runner.preflight()
    except AgentRunnerError as exc:
        raise OperatorOutlineWorkerError("operator_outline_runner_unavailable") from exc
    if capability.provider != route.primary.provider or not capability.authenticated:
        raise OperatorOutlineWorkerError("operator_outline_runner_preflight_invalid")

    manifest = await _outline_manifest(
        session,
        run=run,
        step=step,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
        outline_input=outline_input,
    )
    port = await create_cli_outline_model_port(
        session,
        run_id=run.id,
        settings_snapshot=snapshot,
        context_manifest_id=manifest.id,
        runner_registry=runner_registry,
        locale=outline_input.approved_angle.candidate.locale,
    )
    if port.prompt_version != prompt_version or port.recipe_version != recipe_version:
        raise OperatorOutlineWorkerError("operator_outline_registry_snapshot_mismatch")

    try:
        result = await OutlineGenerator(max_attempts=2).generate_outline(
            session,
            angle_artifact_id=approval.angle_artifact_id,
            expected_angle_artifact_version=approval.angle_artifact_version,
            expected_angle_artifact_hash=approval.angle_artifact_hash,
            selected_angle_id=approval.selected_angle_id,
            expected_candidate_hash=approval.selected_candidate_hash,
            expected_approval_id=approval.id,
            model=port,
            provider=route.primary.provider,
            model_name=route.primary.model,
            context_manifest_id=manifest.id,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
        )
    except OutlineGenerationError as exc:
        raise OperatorOutlineWorkerError(exc.code) from exc

    # complete_job owns the durable StepRun -> completed transition.
    await complete_job(session, job_id=job.id, worker_id=worker_id)
    step.error_json = None
    run.failure_code = None
    run.failure_message = None
    await create_checkpoint(
        session,
        run_id=run.id,
        pending_approval={"step_key": OUTLINE_TASK_KEY, "artifact_id": str(result.artifact.id)},
    )
    await transition_run(session, run_id=run.id, status="waiting_approval")
    state = await get_operator_state(session, content_case_id=run.content_case_id)
    if state.status != "AWAITING_APPROVAL" or state.human_gate != "outline":
        raise OperatorOutlineWorkerError("operator_outline_gate_not_reached")

    receipts = list(
        (
            await session.scalars(
                select(OperatorCommand).where(
                    OperatorCommand.job_id == job.id,
                    OperatorCommand.status == "queued",
                )
            )
        ).all()
    )
    for command in receipts:
        command.status = "completed"
        command.error_code = None
        command.state_after = state.state_version
    await session.flush()
    return OutlineWorkerExecutionResult(
        job_id=job.id,
        run_id=run.id,
        step_run_id=step.id,
        outline_artifact_id=result.artifact.id,
        outline_artifact_hash=result.artifact.content_hash,
        state_version=state.state_version,
    )


async def fail_outline_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    failure_class: str,
    message: str,
) -> Job:
    now = datetime.now(UTC)
    job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if (
        job is None
        or job.status != "leased"
        or job.lease_owner != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
    ):
        raise OperatorOutlineWorkerError("operator_worker_lease_not_owned")
    step = await session.scalar(
        select(StepRun).where(StepRun.id == job.step_run_id).with_for_update()
    )
    run = await session.scalar(
        select(ContentRun).where(ContentRun.id == job.run_id).with_for_update()
    )
    if step is None or run is None or step.run_id != run.id:
        raise OperatorOutlineWorkerError("operator_worker_binding_invalid")
    if step.step_key != OUTLINE_TASK_KEY or step.status != "running":
        raise OperatorOutlineWorkerError("operator_worker_stage_not_allowed")
    if run.status != "running" or run.current_step != OUTLINE_TASK_KEY:
        raise OperatorOutlineWorkerError("operator_worker_run_state_invalid")

    safe_class = failure_class.strip()[:100] or "outline_generation_failed"
    safe_message = message.strip()[:2000] or safe_class
    job.status = "failed"
    job.lease_owner = None
    job.lease_expires_at = None
    job.updated_at = now
    step.error_json = {"class": safe_class, "message": safe_message}
    run.failure_code = safe_class
    run.failure_message = safe_message
    await session.flush()
    state = await get_operator_state(session, content_case_id=run.content_case_id)
    receipts = list(
        (
            await session.scalars(
                select(OperatorCommand).where(
                    OperatorCommand.job_id == job.id,
                    OperatorCommand.status == "queued",
                )
            )
        ).all()
    )
    for command in receipts:
        command.status = "failed"
        command.error_code = safe_class
        command.state_after = state.state_version
    await session.flush()
    return job


__all__ = [
    "OperatorOutlineWorkerError",
    "OutlineWorkerExecutionResult",
    "claim_or_reclaim_outline_job",
    "execute_outline_job",
    "fail_outline_job",
]
