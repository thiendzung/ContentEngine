from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    LocaleVariant,
    NeedHypothesis,
    Project,
    SettingsSnapshot,
)
from app.modules.harness.models import (
    Approval,
    Artifact,
    ContentRun,
    Job,
    ModelCall,
    StepRun,
    ToolCall,
)
from app.modules.harness.persistence import (
    LeaseOwnershipError,
    StaleApprovalArtifactError,
    claim_next_job,
    create_checkpoint,
    enqueue_job,
    fail_job_and_maybe_retry,
    get_latest_checkpoint,
    load_budget_usage,
    pause_for_approval,
    reclaim_expired_job,
    resolve_approval,
    transition_run,
)
from app.modules.harness.policy import (
    BudgetExceededError,
    BudgetExtras,
    BudgetLimits,
    RetryPolicy,
    UnknownFailureClassError,
    enforce_budget,
    is_retryable_failure,
)
from app.modules.knowledge.persistence import content_hash


async def create_run(session: AsyncSession) -> ContentRun:
    project = (await session.execute(select(Project).where(Project.slug == "motgu"))).scalar_one()
    suffix = uuid4().hex[:8]
    hypothesis = NeedHypothesis(
        project_id=project.id,
        type="problem",
        statement=f"CE03 PR-B synthetic {suffix}",
        audience_scope="test reader",
        situation="test",
        origin="FOUNDER",
    )
    session.add(hypothesis)
    await session.flush()
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale="en",
        reader="test reader",
        situation="test",
        need="Durable orchestration",
        question="Can this run stop and resume safely?",
        intent="learn",
        promise="Preserve durable state",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Synthetic harness proof",
        next_discovery_step="None",
        decision="CREATE",
        priority="NOW",
        reasons_json=["test"],
        suggested_content_type="journal",
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=hypothesis.id,
        content_opportunity_id=opportunity.id,
        desired_action="Continue",
        content_hypothesis="Durable state protects work",
        originality_statement="Synthetic only",
        reader_before="Uncertain",
        reader_after="Confident",
    )
    session.add(content_case)
    await session.flush()
    locale_variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="primary",
        primary_question="Can this run stop and resume safely?",
        primary_intent="learn",
    )
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={"test": True},
        source_version_refs_json=["test"],
        content_hash=content_hash(f"ce03-pr-b:{suffix}"),
    )
    session.add_all([locale_variant, snapshot])
    await session.flush()
    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=locale_variant.id,
        run_mode="create",
        status="pending",
        current_step="outline",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    return run


async def create_step(session: AsyncSession, run: ContentRun, *, attempt: int = 1) -> StepRun:
    step = StepRun(
        run_id=run.id,
        step_key="outline",
        attempt=attempt,
        status="pending",
    )
    session.add(step)
    await session.flush()
    return step


async def create_artifact(
    session: AsyncSession,
    run: ContentRun,
    step: StepRun,
    *,
    version: int,
) -> Artifact:
    artifact = Artifact(
        run_id=run.id,
        step_run_id=step.id,
        artifact_type="outline",
        locale="en",
        version=version,
        content_json={"version": version},
        content_hash=content_hash(f"outline:{run.id}:{version}"),
    )
    session.add(artifact)
    await session.flush()
    return artifact


@pytest.mark.asyncio
async def test_checkpoint_versions_are_immutable_and_reloadable() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run = await create_run(session)
            await transition_run(session, run_id=run.id, status="running")
            first = await create_checkpoint(session, run_id=run.id)
            second = await create_checkpoint(session, run_id=run.id)
            latest = await get_latest_checkpoint(session, run_id=run.id)

            assert first.version == 1
            assert second.version == 2
            assert first.id != second.id
            assert latest is not None
            assert latest.id == second.id
            assert first.content_json is not None
            assert first.content_json["run_status"] == "running"
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_approval_pauses_resumes_and_new_artifact_invalidates_old_approval() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run = await create_run(session)
            step = await create_step(session, run)
            await transition_run(session, run_id=run.id, status="running")
            artifact_v1 = await create_artifact(session, run, step, version=1)

            checkpoint = await pause_for_approval(
                session,
                run_id=run.id,
                step_key="outline",
                artifact_id=artifact_v1.id,
            )
            await session.refresh(run)
            assert run.status == "waiting_approval"
            assert checkpoint.content_json is not None
            assert checkpoint.content_json["pending_approval"] == {
                "step_key": "outline",
                "artifact_id": str(artifact_v1.id),
            }

            approval_v1 = await resolve_approval(
                session,
                run_id=run.id,
                step_key="outline",
                artifact_id=artifact_v1.id,
                decision="approved",
                actor_id="founder",
            )
            await session.refresh(run)
            assert run.status == "running"
            assert approval_v1.artifact_id == artifact_v1.id

            artifact_v2 = await create_artifact(session, run, step, version=2)
            await pause_for_approval(
                session,
                run_id=run.id,
                step_key="outline",
                artifact_id=artifact_v2.id,
            )
            with pytest.raises(StaleApprovalArtifactError, match="no longer current"):
                await resolve_approval(
                    session,
                    run_id=run.id,
                    step_key="outline",
                    artifact_id=artifact_v1.id,
                    decision="approved",
                    actor_id="founder",
                )

            approval_v2 = await resolve_approval(
                session,
                run_id=run.id,
                step_key="outline",
                artifact_id=artifact_v2.id,
                decision="changes_requested",
                actor_id="founder",
                comment="Revise this version",
            )
            await session.refresh(run)
            assert run.status == "running"
            approvals = list(
                (
                    await session.scalars(
                        select(Approval)
                        .where(Approval.run_id == run.id)
                        .order_by(Approval.created_at)
                    )
                ).all()
            )
            assert [approval.id for approval in approvals] == [approval_v1.id, approval_v2.id]
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_reject_cancels_run_without_retry() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run = await create_run(session)
            step = await create_step(session, run)
            await transition_run(session, run_id=run.id, status="running")
            artifact = await create_artifact(session, run, step, version=1)
            await pause_for_approval(
                session,
                run_id=run.id,
                step_key="outline",
                artifact_id=artifact.id,
            )
            approval = await resolve_approval(
                session,
                run_id=run.id,
                step_key="outline",
                artifact_id=artifact.id,
                decision="rejected",
                actor_id="founder",
            )
            await session.refresh(run)
            assert approval.decision == "rejected"
            assert run.status == "cancelled"
            assert is_retryable_failure("approval_rejected") is False
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_retry_creates_new_step_and_job_but_auth_error_stops() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run = await create_run(session)
            step = await create_step(session, run)
            await transition_run(session, run_id=run.id, status="running")
            job = await enqueue_job(
                session,
                run_id=run.id,
                step_run_id=step.id,
                dedupe_key=f"first:{run.id}:{step.id}",
            )
            claimed = await claim_next_job(
                session,
                worker_id="worker-a",
                lease_duration=timedelta(minutes=5),
            )
            assert claimed is not None

            retry_result = await fail_job_and_maybe_retry(
                session,
                job_id=job.id,
                worker_id="worker-a",
                failure_class="provider_transient",
                message="temporary outage",
                retry_policy=RetryPolicy(max_step_attempts=2),
            )
            assert retry_result.retried is True
            assert retry_result.retry_step_run_id is not None
            assert retry_result.retry_job_id is not None
            await session.refresh(step)
            assert step.status == "failed"
            assert step.attempt == 1

            retry_step = await session.get(StepRun, retry_result.retry_step_run_id)
            assert retry_step is not None
            assert retry_step.attempt == 2
            retry_job = await session.get(Job, retry_result.retry_job_id)
            assert retry_job is not None
            claimed_retry = await claim_next_job(
                session,
                worker_id="worker-b",
                lease_duration=timedelta(minutes=5),
            )
            assert claimed_retry is not None
            assert claimed_retry.id == retry_job.id

            stopped = await fail_job_and_maybe_retry(
                session,
                job_id=retry_job.id,
                worker_id="worker-b",
                failure_class="provider_auth",
                message="bad credential",
                retry_policy=RetryPolicy(max_step_attempts=3),
            )
            assert stopped.retried is False
            await session.refresh(run)
            assert run.status == "failed"
            assert run.failure_code == "provider_auth"
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_stale_worker_cannot_create_retry_after_lease_reclaim() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run = await create_run(session)
            step = await create_step(session, run)
            await transition_run(session, run_id=run.id, status="running")
            job = await enqueue_job(
                session,
                run_id=run.id,
                step_run_id=step.id,
                dedupe_key=f"stale:{run.id}:{step.id}",
            )
            claimed = await claim_next_job(
                session,
                worker_id="worker-a",
                lease_duration=timedelta(minutes=5),
            )
            assert claimed is not None
            await session.execute(
                update(Job)
                .where(Job.id == job.id)
                .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            reclaimed = await reclaim_expired_job(
                session,
                worker_id="worker-b",
                lease_duration=timedelta(minutes=5),
            )
            assert reclaimed is not None
            with pytest.raises(LeaseOwnershipError, match="no longer owned"):
                await fail_job_and_maybe_retry(
                    session,
                    job_id=job.id,
                    worker_id="worker-a",
                    failure_class="provider_transient",
                    message="late failure",
                    retry_policy=RetryPolicy(max_step_attempts=2),
                )
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_budget_usage_reads_existing_ledgers_and_reports_explicit_reason() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run = await create_run(session)
            step = await create_step(session, run)
            step.started_at = datetime.now(UTC) - timedelta(seconds=1)
            model_call = ModelCall(
                run_id=run.id,
                step_run_id=step.id,
                task_key="draft",
                provider="test",
                model="test",
                purpose="test",
                prompt_version="v1",
                output_tokens=120,
                cost=Decimal("0.25"),
                status="completed",
            )
            tool_call = ToolCall(
                run_id=run.id,
                step_run_id=step.id,
                tool_key="search",
                request_fingerprint=uuid4().hex,
                status="completed",
            )
            session.add_all([model_call, tool_call])
            await session.flush()

            usage = await load_budget_usage(
                session,
                run_id=run.id,
                step_run_id=step.id,
                extras=BudgetExtras(context_estimate=500, research_sources=4, revise_loops=1),
            )
            assert usage.model_calls == 1
            assert usage.tool_calls == 1
            assert usage.output_tokens == 120
            assert usage.estimated_cost == Decimal("0.25")
            assert usage.context_estimate == 500
            assert usage.research_sources == 4
            assert usage.revise_loops == 1

            with pytest.raises(BudgetExceededError, match="max_output_tokens exceeded") as exc:
                enforce_budget(BudgetLimits(max_output_tokens=100), usage)
            assert exc.value.reasons == ("max_output_tokens exceeded: actual=120, limit=100",)
        finally:
            await session.close()
            await transaction.rollback()


def test_retry_policy_rejects_unknown_failure_class() -> None:
    with pytest.raises(UnknownFailureClassError, match="unknown failure class"):
        is_retryable_failure("mystery_failure")
