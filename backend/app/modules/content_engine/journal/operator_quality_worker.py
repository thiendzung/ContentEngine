"""Durable workers for the F4 Review -> Audit -> Source-copy lanes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.assertion_audit import (
    AssertionAuditGenerator,
    AssertionAuditInput,
    load_assertion_audit_input,
)
from app.modules.content_engine.journal.assertion_audit_agent_bridge import (
    assertion_audit_registry_config,
    create_cli_assertion_audit_model_port,
)
from app.modules.content_engine.journal.assertion_audit_execution import prepare_assertion_audit_run
from app.modules.content_engine.journal.operator_quality import (
    QUALITY_AUDIT_TASK_KEYS,
    QUALITY_MAX_JOB_ATTEMPTS,
    QUALITY_REVIEW_TASK_KEYS,
    get_quality_progress,
    prepare_final_gates,
    settle_quality_command,
)
from app.modules.content_engine.journal.review_revise import (
    ReviewReviseGenerator,
    ReviewReviseInput,
    load_review_revise_input,
)
from app.modules.content_engine.journal.review_revise_agent_bridge import (
    create_cli_review_revise_model_port,
    review_revise_registry_config,
)
from app.modules.content_engine.journal.source_copy import (
    SOURCE_COPY_TASK_KEYS,
    ensure_source_copy_run,
    execute_source_copy,
    load_source_copy_input,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import Artifact, ContentRun, ContextManifest, Job, StepRun, utc_now
from app.modules.harness.persistence import (
    complete_job,
    enqueue_job,
    transition_run,
)
from app.modules.harness.runtime import ContextInputs, SettingsModelRouter, build_context_manifest
from app.modules.system.settings_service import active_prompt_definition, active_recipe_definition

QUALITY_STEP_KEYS = tuple(
    {
        *QUALITY_REVIEW_TASK_KEYS.values(),
        *QUALITY_AUDIT_TASK_KEYS.values(),
        *SOURCE_COPY_TASK_KEYS.values(),
    }
)


class OperatorQualityWorkerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


async def _claim_quality_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int,
) -> Job | None:
    now = datetime.now(UTC)
    candidate = (
        select(Job)
        .join(StepRun, StepRun.id == Job.step_run_id)
        .where(
            Job.status == "queued",
            Job.available_at <= now,
            StepRun.step_key.in_(QUALITY_STEP_KEYS),
            StepRun.status == "pending",
        )
        .order_by(Job.available_at, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .cte("next_quality_job")
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
    run = await session.get(ContentRun, job.run_id)
    if run is None or run.status not in {"pending", "running"}:
        raise OperatorQualityWorkerError("operator_quality_run_state_invalid")
    if run.status == "pending":
        await transition_run(session, run_id=run.id, status="running")
    await session.flush()
    return job


async def _reclaim_quality_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int,
) -> Job | None:
    now = datetime.now(UTC)
    job = await session.scalar(
        select(Job)
        .join(StepRun, StepRun.id == Job.step_run_id)
        .where(
            Job.status == "leased",
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at < now,
            StepRun.step_key.in_(QUALITY_STEP_KEYS),
            StepRun.status == "running",
        )
        .order_by(Job.lease_expires_at, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    if job.attempt >= QUALITY_MAX_JOB_ATTEMPTS:
        await _settle_expired_quality_job(
            session, job=job, message="Quality lease expired at the bounded attempt limit."
        )
        return None
    job.attempt += 1
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.updated_at = now
    await session.flush()
    return job


async def claim_or_reclaim_quality_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int = 900,
) -> Job | None:
    if not worker_id.strip() or lease_seconds <= 0:
        raise OperatorQualityWorkerError("operator_quality_lease_invalid")
    job = await _claim_quality_job(session, worker_id=worker_id, lease_seconds=lease_seconds)
    if job is not None:
        return job
    return await _reclaim_quality_job(session, worker_id=worker_id, lease_seconds=lease_seconds)


async def _owned_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
) -> tuple[Job, StepRun, ContentRun]:
    job = await session.get(Job, job_id)
    step = await session.get(StepRun, job.step_run_id) if job is not None else None
    run = await session.get(ContentRun, job.run_id) if job is not None else None
    if (
        job is None
        or step is None
        or run is None
        or step.run_id != run.id
        or job.status != "leased"
        or job.lease_owner != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= datetime.now(UTC)
        or step.status != "running"
        or step.step_key not in QUALITY_STEP_KEYS
    ):
        raise OperatorQualityWorkerError("operator_quality_lease_not_owned")
    return job, step, run


async def _review_binding(
    session: AsyncSession,
    *,
    writer_run: ContentRun,
    review_step: StepRun,
    locale: str,
) -> tuple[ReviewReviseInput, UUID, str, SettingsSnapshot]:
    if len(review_step.input_artifact_refs_json) != 3:
        raise OperatorQualityWorkerError("operator_quality_review_input_refs_invalid")
    source_id, outline_id, handoff_id = (
        UUID(value) for value in review_step.input_artifact_refs_json
    )
    source = await session.get(Artifact, source_id)
    outline = await session.get(Artifact, outline_id)
    handoff = await session.get(Artifact, handoff_id)
    if source is None or outline is None or handoff is None:
        raise OperatorQualityWorkerError("operator_quality_review_input_missing")
    try:
        review_input = await load_review_revise_input(
            session,
            writer_run_id=writer_run.id,
            source_draft_artifact_id=source.id,
            expected_source_draft_version=source.version,
            expected_source_draft_hash=source.content_hash,
            outline_artifact_id=outline.id,
            expected_outline_version=outline.version,
            expected_outline_hash=outline.content_hash,
            locale=locale,
        )
        config = review_revise_registry_config(locale)
        prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=config.recipe_key,
            content_type="journal",
            locale=locale,
            task_key=config.task_key,
        )
    except Exception as exc:
        raise OperatorQualityWorkerError("operator_quality_review_input_invalid") from exc
    snapshot = await session.get(SettingsSnapshot, writer_run.settings_snapshot_id)
    if snapshot is None:
        raise OperatorQualityWorkerError("operator_quality_settings_missing")
    del handoff, prompt, recipe
    return review_input, source.id, source.content_hash, snapshot


async def _execute_review(
    session: AsyncSession,
    *,
    job: Job,
    step: StepRun,
    run: ContentRun,
    locale: str,
    runner_registry: AgentRunnerRegistry,
) -> None:
    review_input, source_id, source_hash, snapshot = await _review_binding(
        session, writer_run=run, review_step=step, locale=locale
    )
    source = await session.get(Artifact, source_id)
    assert source is not None
    outline = await session.get(Artifact, UUID(step.input_artifact_refs_json[1]))
    assert outline is not None
    config = review_revise_registry_config(locale)
    prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
    recipe = await active_recipe_definition(
        session,
        recipe_key=config.recipe_key,
        content_type="journal",
        locale=locale,
        task_key=config.task_key,
    )
    route = SettingsModelRouter().resolve(task_key="angle", settings_snapshot=snapshot).primary
    manifest = await build_context_manifest(
        session,
        run_id=run.id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version=f"{prompt.prompt_key}:v{prompt.version}",
            recipe_version=f"{recipe.recipe_key}:v{recipe.version}",
            evidence_set_id=review_input.writer_input.outline_input.bundle.evidence_set_id,
            originality_pack_id=review_input.writer_input.outline_input.bundle.originality_pack_id,
        ),
    )
    del source_hash
    port = await create_cli_review_revise_model_port(
        session,
        run_id=run.id,
        settings_snapshot=snapshot,
        context_manifest_id=manifest.id,
        runner_registry=runner_registry,
        locale=locale,
    )
    result = await ReviewReviseGenerator(max_attempts=2).revise_draft(
        session,
        writer_run_id=run.id,
        source_draft_artifact_id=source.id,
        expected_source_draft_version=source.version,
        expected_source_draft_hash=source.content_hash,
        outline_artifact_id=outline.id,
        expected_outline_version=outline.version,
        expected_outline_hash=outline.content_hash,
        locale=locale,
        model=port,
        provider=route.provider,
        model_name=route.model,
        context_manifest_id=manifest.id,
        prompt_version=f"{prompt.prompt_key}:v{prompt.version}",
        recipe_version=f"{recipe.recipe_key}:v{recipe.version}",
    )
    step.output_artifact_refs_json = [*step.output_artifact_refs_json, str(result.artifact.id)]
    # The existing Audit contract accepts a completed Writer lane in approval-wait
    # state.  The review step is still on the same Writer run and keeps its lineage.
    if run.status == "running":
        await transition_run(session, run_id=run.id, status="waiting_approval")
    audit_input = await load_assertion_audit_input(
        session,
        writer_run_id=run.id,
        revised_draft_artifact_id=result.artifact.id,
        expected_revised_draft_version=result.artifact.version,
        expected_revised_draft_hash=result.artifact.content_hash,
        outline_artifact_id=outline.id,
        expected_outline_version=outline.version,
        expected_outline_hash=outline.content_hash,
        locale=locale,
    )
    audit_config = assertion_audit_registry_config(locale)
    audit_prompt = await active_prompt_definition(session, prompt_key=audit_config.prompt_key)
    audit_recipe = await active_recipe_definition(
        session,
        recipe_key=audit_config.recipe_key,
        content_type="journal",
        locale=locale,
        task_key=audit_config.task_key,
    )
    audit_route = (
        SettingsModelRouter().resolve(task_key="angle", settings_snapshot=snapshot).primary
    )
    audit_context = await prepare_assertion_audit_run(
        session,
        source_input=audit_input,
        task_key=audit_config.task_key,
        prompt_version=f"{audit_prompt.prompt_key}:v{audit_prompt.version}",
        recipe_version=f"{audit_recipe.recipe_key}:v{audit_recipe.version}",
        provider=audit_route.provider,
        model=audit_route.model,
    )
    audit_step = audit_context.step_run
    if audit_step.status == "pending":
        # The next Job owns execution; leave its durable StepRun pending.
        pass
    await enqueue_job(
        session,
        run_id=audit_context.audit_run.id,
        step_run_id=audit_step.id,
        dedupe_key=f"operator:quality:audit:{run.id}:{locale}:{result.artifact.id}",
    )


async def _audit_binding(
    session: AsyncSession,
    *,
    run: ContentRun,
    step: StepRun,
) -> tuple[AssertionAuditInput, UUID, UUID, str, str, SettingsSnapshot]:
    if len(step.input_artifact_refs_json) < 3:
        raise OperatorQualityWorkerError("operator_quality_audit_input_refs_invalid")
    handoff_id = UUID(step.input_artifact_refs_json[0])
    handoff = await session.get(Artifact, handoff_id)
    if handoff is None or not isinstance(handoff.content_json, dict):
        raise OperatorQualityWorkerError("operator_quality_audit_handoff_missing")
    payload = handoff.content_json
    if not isinstance(payload, dict):
        raise OperatorQualityWorkerError("operator_quality_source_copy_handoff_invalid")
    source = payload.get("source_draft")
    outline = payload.get("journal_outline")
    if not isinstance(source, dict) or not isinstance(outline, dict):
        raise OperatorQualityWorkerError("operator_quality_audit_handoff_invalid")
    try:
        source_id = UUID(cast(str, source["id"]))
        outline_id = UUID(cast(str, outline["id"]))
        locale_value = payload.get("locale")
        if not isinstance(locale_value, str):
            locale_value = handoff.locale
        if not isinstance(locale_value, str):
            raise OperatorQualityWorkerError("operator_quality_audit_locale_missing")
        locale = locale_value
        source_writer = payload.get("source_writer_run")
        if not isinstance(source_writer, dict) or not isinstance(source_writer.get("id"), str):
            raise OperatorQualityWorkerError("operator_quality_audit_writer_missing")
        audit_input = await load_assertion_audit_input(
            session,
            writer_run_id=UUID(cast(str, source_writer["id"])),
            revised_draft_artifact_id=source_id,
            expected_revised_draft_version=cast(int, source["version"]),
            expected_revised_draft_hash=cast(str, source["content_hash"]),
            outline_artifact_id=outline_id,
            expected_outline_version=cast(int, outline["version"]),
            expected_outline_hash=cast(str, outline["content_hash"]),
            locale=locale,
        )
    except Exception as exc:
        raise OperatorQualityWorkerError("operator_quality_audit_input_invalid") from exc
    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None:
        raise OperatorQualityWorkerError("operator_quality_settings_missing")
    return (
        audit_input,
        source_id,
        outline_id,
        locale,
        handoff.content_hash,
        snapshot,
    )


async def _execute_audit(
    session: AsyncSession,
    *,
    job: Job,
    step: StepRun,
    run: ContentRun,
    runner_registry: AgentRunnerRegistry,
) -> None:
    audit_input, _source_id, _outline_id, locale, _handoff_hash, snapshot = await _audit_binding(
        session, run=run, step=step
    )
    config = assertion_audit_registry_config(locale)
    prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
    recipe = await active_recipe_definition(
        session,
        recipe_key=config.recipe_key,
        content_type="journal",
        locale=locale,
        task_key=config.task_key,
    )
    manifest = await session.scalar(
        select(ContextManifest).where(
            ContextManifest.run_id == run.id,
            ContextManifest.step_run_id == step.id,
        )
    )
    if manifest is None:
        raise OperatorQualityWorkerError("operator_quality_audit_manifest_missing")
    route = SettingsModelRouter().resolve(task_key="angle", settings_snapshot=snapshot).primary
    port = await create_cli_assertion_audit_model_port(
        session,
        run_id=run.id,
        settings_snapshot=snapshot,
        context_manifest_id=manifest.id,
        runner_registry=runner_registry,
        locale=locale,
    )
    result = await AssertionAuditGenerator(max_attempts=2).audit_draft(
        session,
        writer_run_id=audit_input.writer_input.writer_run.id,
        revised_draft_artifact_id=audit_input.source_artifact.id,
        expected_revised_draft_version=audit_input.source_artifact.version,
        expected_revised_draft_hash=audit_input.source_artifact.content_hash,
        outline_artifact_id=audit_input.writer_input.outline_artifact.id,
        expected_outline_version=audit_input.writer_input.outline_artifact.version,
        expected_outline_hash=audit_input.writer_input.outline_artifact.content_hash,
        locale=locale,
        model=port,
        provider=route.provider,
        model_name=route.model,
        context_manifest_id=manifest.id,
        prompt_version=f"{prompt.prompt_key}:v{prompt.version}",
        recipe_version=f"{recipe.recipe_key}:v{recipe.version}",
        execution_run_id=run.id,
    )
    step.output_artifact_refs_json = [*step.output_artifact_refs_json, str(result.artifact.id)]
    if run.status == "running":
        await transition_run(session, run_id=run.id, status="completed")
    if (
        result.result == "fail"
        or result.critical_unsupported_count > 0
        or result.critical_contradicted_count > 0
    ):
        return
    source_input = await load_source_copy_input(
        session,
        writer_run_id=audit_input.writer_input.writer_run.id,
        source_draft_artifact_id=audit_input.source_artifact.id,
        expected_source_draft_version=audit_input.source_artifact.version,
        expected_source_draft_hash=audit_input.source_artifact.content_hash,
        assertion_audit_artifact_id=result.artifact.id,
        expected_assertion_audit_version=result.artifact.version,
        expected_assertion_audit_hash=result.artifact.content_hash,
        assertion_audit_quality_evaluation_id=result.evaluation.id,
        outline_artifact_id=audit_input.writer_input.outline_artifact.id,
        expected_outline_version=audit_input.writer_input.outline_artifact.version,
        expected_outline_hash=audit_input.writer_input.outline_artifact.content_hash,
        locale=locale,
    )
    source_run, source_handoff, _ = await ensure_source_copy_run(
        session,
        source_input=source_input,
        task_key=SOURCE_COPY_TASK_KEYS[locale],
    )
    source_step = await session.scalar(
        select(StepRun).where(
            StepRun.run_id == source_run.id,
            StepRun.step_key == SOURCE_COPY_TASK_KEYS[locale],
        )
    )
    if source_step is None:
        source_step = StepRun(
            run_id=source_run.id,
            step_key=SOURCE_COPY_TASK_KEYS[locale],
            attempt=1,
            status="pending",
            input_artifact_refs_json=[
                str(source_handoff.id),
                str(source_input.source_artifact.id),
                str(source_input.assertion_audit_artifact.id),
                str(source_input.writer_input.outline_artifact.id),
            ],
            output_artifact_refs_json=[],
        )
        session.add(source_step)
        await session.flush()
    await enqueue_job(
        session,
        run_id=source_run.id,
        step_run_id=source_step.id,
        dedupe_key=f"operator:quality:source-copy:{source_run.id}:{locale}:{result.artifact.id}",
    )


async def _execute_source_copy(
    session: AsyncSession,
    *,
    job: Job,
    step: StepRun,
    run: ContentRun,
) -> None:
    if (
        not isinstance(step.input_artifact_refs_json, list)
        or len(step.input_artifact_refs_json) != 4
    ):
        raise OperatorQualityWorkerError("operator_quality_source_copy_input_refs_invalid")
    handoff_id, draft_id, audit_id, outline_id = (
        UUID(value) for value in step.input_artifact_refs_json
    )
    handoff = await session.get(Artifact, handoff_id)
    draft = await session.get(Artifact, draft_id)
    audit = await session.get(Artifact, audit_id)
    evaluation_id = None
    if handoff is not None and isinstance(handoff.content_json, dict):
        audit_ref = handoff.content_json.get("assertion_audit")
        if isinstance(audit_ref, dict):
            evaluation_id = audit_ref.get("quality_evaluation_id")
    if handoff is None or draft is None or audit is None or not isinstance(evaluation_id, str):
        raise OperatorQualityWorkerError("operator_quality_source_copy_input_missing")
    payload = handoff.content_json
    if not isinstance(payload, dict):
        raise OperatorQualityWorkerError("operator_quality_source_copy_handoff_invalid")
    # The source-copy handoff names the Writer run explicitly; do not infer it from
    # timestamps or from a sibling locale.
    raw_writer = payload.get("source_writer_run_id") if isinstance(payload, dict) else None
    writer_run = (
        await session.get(ContentRun, UUID(raw_writer)) if isinstance(raw_writer, str) else None
    )
    if writer_run is None:
        raise OperatorQualityWorkerError("operator_quality_source_copy_writer_missing")
    if not isinstance(handoff.locale, str):
        raise OperatorQualityWorkerError("operator_quality_source_copy_locale_missing")
    locale = handoff.locale
    outline_ref = payload.get("journal_outline")
    if not isinstance(outline_ref, dict):
        raise OperatorQualityWorkerError("operator_quality_source_copy_outline_missing")
    source_input = await load_source_copy_input(
        session,
        writer_run_id=writer_run.id,
        source_draft_artifact_id=draft.id,
        expected_source_draft_version=draft.version,
        expected_source_draft_hash=draft.content_hash,
        assertion_audit_artifact_id=audit.id,
        expected_assertion_audit_version=audit.version,
        expected_assertion_audit_hash=audit.content_hash,
        assertion_audit_quality_evaluation_id=UUID(evaluation_id),
        outline_artifact_id=outline_id,
        expected_outline_version=cast(int, outline_ref["version"]),
        expected_outline_hash=cast(str, outline_ref["content_hash"]),
        locale=locale,
    )
    result = await execute_source_copy(
        session, source_input=source_input, task_key=SOURCE_COPY_TASK_KEYS[locale]
    )
    # execute_source_copy owns deterministic evaluation and persistence.  Completing
    # the queue receipt is the worker's only additional side effect.
    await complete_job(session, job_id=job.id, worker_id=cast(str, job.lease_owner))
    del result


async def _settle_expired_quality_job(
    session: AsyncSession,
    *,
    job: Job,
    message: str,
) -> None:
    now = utc_now()
    step = await session.get(StepRun, job.step_run_id)
    run = await session.get(ContentRun, job.run_id)
    job.status = "failed"
    job.lease_owner = None
    job.lease_expires_at = None
    job.updated_at = now
    if step is not None:
        step.status = "failed"
        step.error_json = {"class": "operator_quality_retry_exhausted", "message": message}
    if run is not None:
        run.failure_code = "operator_quality_retry_exhausted"
        run.failure_message = message[:2000]
        if run.status == "running":
            await transition_run(session, run_id=run.id, status="failed")
    await session.flush()
    if run is not None:
        from app.modules.content_engine.journal.operator_runtime import get_operator_state

        progress = await get_quality_progress(
            session, content_case_id=run.content_case_id, source_run_id=None
        )
        state = await get_operator_state(session, content_case_id=run.content_case_id)
        await settle_quality_command(session, progress=progress, state_version=state.state_version)


async def fail_quality_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    failure_class: str,
    message: str,
) -> None:
    """Settle technical failure separately from persisted content-quality failure."""

    now = utc_now()
    job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    step = (
        await session.scalar(select(StepRun).where(StepRun.id == job.step_run_id).with_for_update())
        if job is not None
        else None
    )
    run = (
        await session.scalar(
            select(ContentRun).where(ContentRun.id == job.run_id).with_for_update()
        )
        if job is not None
        else None
    )
    if (
        job is None
        or step is None
        or run is None
        or job.status != "leased"
        or job.lease_owner != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
        or step.run_id != run.id
        or step.step_key not in QUALITY_STEP_KEYS
        or step.status not in {"running", "failed"}
    ):
        raise OperatorQualityWorkerError("operator_quality_lease_not_owned")
    job.status = "failed"
    job.lease_owner = None
    job.lease_expires_at = None
    if step.status == "running":
        step.status = "failed"
        step.completed_at = now
        step.error_json = {"class": failure_class[:100], "message": message[:2000]}
    elif step.error_json is None:
        step.error_json = {"class": failure_class[:100], "message": message[:2000]}
    if step.step_key in QUALITY_REVIEW_TASK_KEYS.values():
        if step.attempt >= QUALITY_MAX_JOB_ATTEMPTS or job.attempt >= QUALITY_MAX_JOB_ATTEMPTS:
            run.failure_code = "operator_quality_retry_exhausted"
            run.failure_message = message[:2000]
            if run.status == "running":
                await transition_run(session, run_id=run.id, status="failed")
    else:
        eval_run_count = (
            await session.scalar(
                select(func.count(ContentRun.id)).where(
                    ContentRun.content_case_id == run.content_case_id,
                    ContentRun.locale_variant_id == run.locale_variant_id,
                    ContentRun.run_mode == "eval",
                    ContentRun.current_step == step.step_key,
                )
            )
            or 1
        )
        if eval_run_count >= QUALITY_MAX_JOB_ATTEMPTS or job.attempt >= QUALITY_MAX_JOB_ATTEMPTS:
            run.failure_code = "operator_quality_retry_exhausted"
        else:
            run.failure_code = failure_class[:100]
        run.failure_message = message[:2000]
        if run.status == "running":
            await transition_run(session, run_id=run.id, status="failed")
    await session.flush()
    from app.modules.content_engine.journal.operator_runtime import get_operator_state

    progress = await get_quality_progress(
        session, content_case_id=run.content_case_id, source_run_id=None
    )
    state = await get_operator_state(session, content_case_id=run.content_case_id)
    await settle_quality_command(session, progress=progress, state_version=state.state_version)


async def execute_quality_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    runner_registry: AgentRunnerRegistry,
) -> None:
    job, step, run = await _owned_job(session, job_id=job_id, worker_id=worker_id)
    if step.step_key in QUALITY_REVIEW_TASK_KEYS.values():
        locale = next(
            locale for locale, key in QUALITY_REVIEW_TASK_KEYS.items() if key == step.step_key
        )
        await _execute_review(
            session,
            job=job,
            step=step,
            run=run,
            locale=locale,
            runner_registry=runner_registry,
        )
        await complete_job(session, job_id=job.id, worker_id=worker_id)
    elif step.step_key in QUALITY_AUDIT_TASK_KEYS.values():
        await _execute_audit(session, job=job, step=step, run=run, runner_registry=runner_registry)
        await complete_job(session, job_id=job.id, worker_id=worker_id)
    else:
        await _execute_source_copy(session, job=job, step=step, run=run)
    if run.status == "failed":
        return
    progress = await get_quality_progress(
        session, content_case_id=run.content_case_id, source_run_id=None
    )
    if progress is not None and progress.all_qualified and not progress.final_gate_ready:
        await prepare_final_gates(
            session,
            content_case_id=run.content_case_id,
            progress=progress,
        )
    from app.modules.content_engine.journal.operator_runtime import get_operator_state

    progress = await get_quality_progress(
        session, content_case_id=run.content_case_id, source_run_id=None
    )
    state = await get_operator_state(session, content_case_id=run.content_case_id)
    await settle_quality_command(
        session,
        progress=progress,
        state_version=state.state_version,
    )


__all__ = [
    "OperatorQualityWorkerError",
    "QUALITY_STEP_KEYS",
    "claim_or_reclaim_quality_job",
    "execute_quality_job",
    "fail_quality_job",
]
