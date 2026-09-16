"""Durable execution for one independent F3 Writer lane."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.operator_runtime import get_operator_state
from app.modules.content_engine.journal.operator_writers import (
    WRITER_MAX_JOB_ATTEMPTS,
    WRITER_STEP_BY_LOCALE,
    exact_outline_approval,
    get_writer_lane_progress,
    settle_writer_commands,
)
from app.modules.content_engine.journal.writer import (
    WriterGenerationError,
    WriterGenerator,
    load_writer_input,
)
from app.modules.content_engine.journal.writer_agent_bridge import (
    WRITER_ROUTE_TASK_KEY,
    create_cli_writer_model_port,
    writer_registry_config,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import AgentRunnerError, AgentRunnerRegistry
from app.modules.harness.models import Artifact, ContentRun, Job, StepRun
from app.modules.harness.persistence import (
    complete_job,
    create_checkpoint,
    transition_run,
)
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


class OperatorWriterWorkerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class WriterWorkerExecutionResult:
    job_id: UUID
    run_id: UUID
    step_run_id: UUID
    locale: str
    draft_artifact_id: UUID
    draft_artifact_hash: str
    state_version: str


async def _claim_new_writer_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int,
) -> Job | None:
    if not worker_id.strip() or lease_seconds <= 0:
        raise OperatorWriterWorkerError("operator_worker_lease_invalid")
    now = datetime.now(UTC)
    candidate = (
        select(Job)
        .join(StepRun, StepRun.id == Job.step_run_id)
        .where(
            Job.status == "queued",
            Job.available_at <= now,
            StepRun.step_key.in_(tuple(WRITER_STEP_BY_LOCALE.values())),
            StepRun.status.in_(("pending", "running")),
        )
        .order_by(Job.available_at, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .cte("next_writer_operator_job")
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


async def _reclaim_expired_writer_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int,
) -> Job | None:
    if not worker_id.strip() or lease_seconds <= 0:
        raise OperatorWriterWorkerError("operator_worker_lease_invalid")
    now = datetime.now(UTC)
    candidate = (
        select(Job)
        .join(StepRun, StepRun.id == Job.step_run_id)
        .where(
            Job.status == "leased",
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at < now,
            StepRun.step_key.in_(tuple(WRITER_STEP_BY_LOCALE.values())),
            StepRun.status == "running",
        )
        .order_by(Job.lease_expires_at, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = (await session.scalars(candidate)).first()
    if job is None:
        return None
    if job.attempt >= WRITER_MAX_JOB_ATTEMPTS:
        step = await session.get(StepRun, job.step_run_id)
        run = await session.get(ContentRun, job.run_id)
        job.status = "failed"
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = now
        if step is not None:
            step.status = "failed"
            step.error_json = {
                "class": "operator_writer_retry_exhausted",
                "message": "Expired Writer lease reached the bounded attempt limit.",
            }
        if run is not None:
            run.failure_code = "operator_writer_retry_exhausted"
            run.failure_message = "Expired Writer lease reached the bounded attempt limit."
        await session.flush()
        if run is not None:
            state = await get_operator_state(session, content_case_id=run.content_case_id)
            progress = await get_writer_lane_progress(
                session,
                content_case_id=run.content_case_id,
                source_run_id=state.current_run_id,
            )
            await settle_writer_commands(
                session,
                content_case_id=run.content_case_id,
                progress=progress,
                state_version=state.state_version,
            )
            await session.flush()
        return None
    job.attempt += 1
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.updated_at = now
    await session.flush()
    return job


async def claim_or_reclaim_writer_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int = 900,
) -> Job | None:
    recovered = await _reclaim_expired_writer_job(
        session,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )
    if recovered is not None:
        return recovered
    return await _claim_new_writer_job(
        session,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )


def _ref_id(refs: list[str], prefix: str) -> UUID:
    values = [value.removeprefix(prefix) for value in refs if value.startswith(prefix)]
    if len(values) != 1:
        raise OperatorWriterWorkerError("operator_writer_input_binding_invalid")
    try:
        return UUID(values[0])
    except ValueError as exc:
        raise OperatorWriterWorkerError("operator_writer_input_binding_invalid") from exc


async def execute_writer_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    runner_registry: AgentRunnerRegistry,
) -> WriterWorkerExecutionResult:
    job = await session.get(Job, job_id)
    if (
        job is None
        or job.status != "leased"
        or job.lease_owner != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= datetime.now(UTC)
    ):
        raise OperatorWriterWorkerError("operator_worker_lease_not_owned")
    step = await session.get(StepRun, job.step_run_id)
    run = await session.get(ContentRun, job.run_id)
    if step is None or run is None or step.run_id != run.id:
        raise OperatorWriterWorkerError("operator_worker_binding_invalid")
    if step.step_key not in WRITER_STEP_BY_LOCALE.values() or step.status != "running":
        raise OperatorWriterWorkerError("operator_writer_stage_not_allowed")
    if run.run_mode != "localize" or run.status != "running":
        raise OperatorWriterWorkerError("operator_writer_run_state_invalid")
    locale = next(
        (value for value, key in WRITER_STEP_BY_LOCALE.items() if key == step.step_key),
        None,
    )
    if locale is None:
        raise OperatorWriterWorkerError("operator_writer_locale_unsupported")
    outline_approval_id = _ref_id(step.input_artifact_refs_json, "outline_approval:")
    handoffs = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == run.id,
                    Artifact.artifact_type == "writer_handoff",
                )
            )
        ).all()
    )
    if len(handoffs) != 1 or not isinstance(handoffs[0].content_json, dict):
        raise OperatorWriterWorkerError("operator_writer_handoff_conflict")
    raw_source_run_id = handoffs[0].content_json.get("source_run_id")
    if not isinstance(raw_source_run_id, str):
        raise OperatorWriterWorkerError("operator_writer_handoff_invalid")
    try:
        source_run_id = UUID(raw_source_run_id)
    except ValueError as exc:
        raise OperatorWriterWorkerError("operator_writer_handoff_invalid") from exc
    approval, outline_artifact = await exact_outline_approval(
        session,
        run_id=source_run_id,
    )
    if approval.id != outline_approval_id:
        raise OperatorWriterWorkerError("operator_writer_approval_binding_invalid")
    try:
        writer_input = await load_writer_input(
            session,
            writer_run_id=run.id,
            outline_artifact_id=outline_artifact.id,
            expected_outline_version=outline_artifact.version,
            expected_outline_hash=outline_artifact.content_hash,
            outline_approval_id=approval.id,
            locale=locale,
        )
    except WriterGenerationError as exc:
        raise OperatorWriterWorkerError(exc.code) from exc

    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None:
        raise OperatorWriterWorkerError("operator_writer_settings_missing")
    try:
        config = writer_registry_config(locale)
        prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=config.recipe_key,
            content_type="journal",
            locale=config.locale,
            task_key=config.task_key,
        )
        route = SettingsModelRouter().resolve(
            task_key=WRITER_ROUTE_TASK_KEY,
            settings_snapshot=snapshot,
        )
    except (SettingsResolutionError, RuntimeConfigurationError) as exc:
        raise OperatorWriterWorkerError("operator_writer_registry_blocked") from exc
    if route.primary.provider != "codex_cli" or not route.primary.model.strip():
        raise OperatorWriterWorkerError("operator_writer_route_not_allowed")
    try:
        runner = runner_registry.get(route.primary.provider)
        capability = await runner.preflight()
    except AgentRunnerError as exc:
        raise OperatorWriterWorkerError("operator_writer_runner_unavailable") from exc
    if capability.provider != route.primary.provider or not capability.authenticated:
        raise OperatorWriterWorkerError("operator_writer_runner_preflight_invalid")

    upstream = writer_input.outline_input.bundle.context_manifest
    manifest = await build_context_manifest(
        session,
        run_id=run.id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version=f"{prompt.prompt_key}:v{prompt.version}",
            recipe_version=f"{recipe.recipe_key}:v{recipe.version}",
            evidence_set_id=writer_input.outline_input.bundle.evidence_set_id,
            originality_pack_id=writer_input.outline_input.bundle.originality_pack_id,
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
    try:
        port = await create_cli_writer_model_port(
            session,
            run_id=run.id,
            settings_snapshot=snapshot,
            context_manifest_id=manifest.id,
            runner_registry=runner_registry,
            locale=locale,
        )
        result = await WriterGenerator(max_attempts=2).generate_draft(
            session,
            writer_run_id=run.id,
            outline_artifact_id=outline_artifact.id,
            expected_outline_version=outline_artifact.version,
            expected_outline_hash=outline_artifact.content_hash,
            outline_approval_id=approval.id,
            locale=locale,
            model=port,
            provider=route.primary.provider,
            model_name=route.primary.model,
            context_manifest_id=manifest.id,
            prompt_version=f"{prompt.prompt_key}:v{prompt.version}",
            recipe_version=f"{recipe.recipe_key}:v{recipe.version}",
        )
    except WriterGenerationError as exc:
        raise OperatorWriterWorkerError(exc.code) from exc

    await complete_job(session, job_id=job.id, worker_id=worker_id)
    step.error_json = None
    run.failure_code = None
    run.failure_message = None
    await create_checkpoint(
        session,
        run_id=run.id,
        pending_approval={"step_key": step.step_key, "artifact_id": str(result.artifact.id)},
    )
    await transition_run(session, run_id=run.id, status="waiting_approval")
    progress = await get_writer_lane_progress(
        session,
        content_case_id=run.content_case_id,
        source_run_id=source_run_id,
    )
    state = await get_operator_state(session, content_case_id=run.content_case_id)
    await settle_writer_commands(
        session,
        progress=progress,
        content_case_id=run.content_case_id,
        state_version=state.state_version,
    )
    await session.flush()
    return WriterWorkerExecutionResult(
        job_id=job.id,
        run_id=run.id,
        step_run_id=step.id,
        locale=locale,
        draft_artifact_id=result.artifact.id,
        draft_artifact_hash=result.artifact.content_hash,
        state_version=state.state_version,
    )


async def fail_writer_job(
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
        raise OperatorWriterWorkerError("operator_worker_lease_not_owned")
    step = await session.scalar(
        select(StepRun).where(StepRun.id == job.step_run_id).with_for_update()
    )
    run = await session.scalar(
        select(ContentRun).where(ContentRun.id == job.run_id).with_for_update()
    )
    if step is None or run is None or step.run_id != run.id:
        raise OperatorWriterWorkerError("operator_worker_binding_invalid")
    if step.step_key not in WRITER_STEP_BY_LOCALE.values() or step.status != "running":
        raise OperatorWriterWorkerError("operator_writer_stage_not_allowed")
    safe_class = failure_class.strip()[:100] or "writer_generation_failed"
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
    progress = await get_writer_lane_progress(
        session,
        content_case_id=run.content_case_id,
        source_run_id=state.current_run_id,
    )
    await settle_writer_commands(
        session,
        progress=progress,
        content_case_id=run.content_case_id,
        state_version=state.state_version,
    )
    await session.flush()
    return job


__all__ = [
    "OperatorWriterWorkerError",
    "WriterWorkerExecutionResult",
    "claim_or_reclaim_writer_job",
    "execute_writer_job",
    "fail_writer_job",
]
