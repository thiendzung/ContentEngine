from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
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
from app.modules.harness.models import ContentRun, Job, StepRun
from app.modules.harness.persistence import (
    InvalidStateTransitionError,
    LeaseOwnershipError,
    claim_next_job,
    complete_job,
    create_step_retry,
    enqueue_job,
    heartbeat_job,
    reclaim_expired_job,
    transition_run,
    transition_step_run,
)
from app.modules.knowledge.persistence import content_hash


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


async def create_synthetic_run(session: AsyncSession) -> ContentRun:
    project = (await session.execute(select(Project).where(Project.slug == "motgu"))).scalar_one()
    suffix = uuid4().hex[:8]
    hypothesis = NeedHypothesis(
        project_id=project.id,
        type="problem",
        statement=f"Synthetic durable step {suffix}",
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
        need="Durable execution",
        question="Can work resume?",
        intent="learn",
        promise="Keep durable state",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Lease proof",
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
        content_hypothesis="A durable queue preserves work",
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
        primary_question="Can work resume?",
        primary_intent="learn",
    )
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={"test": True},
        source_version_refs_json=["test"],
        content_hash=content_hash(f"queue-settings:{suffix}"),
    )
    session.add_all([locale_variant, snapshot])
    await session.flush()
    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=locale_variant.id,
        run_mode="create",
        status="pending",
        current_step="synthetic",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    return run


async def create_synthetic_step(session: AsyncSession, run: ContentRun) -> StepRun:
    step = StepRun(run_id=run.id, step_key="synthetic", attempt=1, status="pending")
    session.add(step)
    await session.flush()
    return step


@pytest.mark.asyncio
async def test_run_and_step_state_machines_preserve_attempt_history() -> None:
    async with isolated_session() as session:
        run = await create_synthetic_run(session)
        await transition_run(session, run_id=run.id, status="running")
        await transition_run(session, run_id=run.id, status="waiting_approval")
        await transition_run(session, run_id=run.id, status="running")
        completed = await transition_run(session, run_id=run.id, status="completed")
        assert completed.completed_at is not None
        with pytest.raises(InvalidStateTransitionError, match="completed -> running"):
            await transition_run(session, run_id=run.id, status="running")
        with pytest.raises(DBAPIError, match="invalid_content_run_status_transition"):
            async with session.begin_nested():
                await session.execute(
                    update(ContentRun).where(ContentRun.id == run.id).values(status="running")
                )

        step_one = await create_synthetic_step(session, run)
        await transition_step_run(session, step_run_id=step_one.id, status="running")
        failed = await transition_step_run(session, step_run_id=step_one.id, status="failed")
        retry = await create_step_retry(session, failed_step_run_id=failed.id)
        assert failed.attempt == 1
        assert failed.status == "failed"
        assert retry.attempt == 2
        assert retry.status == "pending"
        await transition_step_run(session, step_run_id=retry.id, status="running")
        assert (
            await transition_step_run(session, step_run_id=retry.id, status="completed")
        ).status == "completed"


@pytest.mark.asyncio
async def test_durable_job_claim_heartbeat_complete_and_reload() -> None:
    async with isolated_session() as session:
        run = await create_synthetic_run(session)
        step = await create_synthetic_step(session, run)
        job = await enqueue_job(
            session,
            run_id=run.id,
            step_run_id=step.id,
            dedupe_key=f"synthetic:{run.id}:{step.id}",
        )
        duplicate = await enqueue_job(
            session,
            run_id=run.id,
            step_run_id=step.id,
            dedupe_key=job.dedupe_key,
        )
        assert duplicate.id == job.id

        claimed = await claim_next_job(
            session, worker_id="worker-a", lease_duration=timedelta(minutes=5)
        )
        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.status == "leased"
        assert claimed.lease_owner == "worker-a"
        assert claimed.lease_expires_at is not None
        assert (
            await claim_next_job(session, worker_id="worker-b", lease_duration=timedelta(minutes=5))
        ) is None
        extended = await heartbeat_job(
            session,
            job_id=job.id,
            worker_id="worker-a",
            extend_by=timedelta(minutes=5),
        )
        assert extended.lease_owner == "worker-a"
        with pytest.raises(LeaseOwnershipError, match="not owned"):
            await heartbeat_job(
                session,
                job_id=job.id,
                worker_id="worker-b",
                extend_by=timedelta(minutes=5),
            )
        completed = await complete_job(session, job_id=job.id, worker_id="worker-a")
        assert completed.status == "completed"
        assert completed.lease_owner is None
        assert (await session.get(StepRun, step.id)).status == "completed"
        assert (
            await reclaim_expired_job(
                session, worker_id="worker-b", lease_duration=timedelta(minutes=5)
            )
        ) is None

        session.expunge_all()
        reloaded = await session.get(Job, job.id)
        assert reloaded is not None
        assert reloaded.status == "completed"


@pytest.mark.asyncio
async def test_expired_lease_reclaims_for_new_worker_and_rejects_stale_completion() -> None:
    async with isolated_session() as session:
        run = await create_synthetic_run(session)
        step = await create_synthetic_step(session, run)
        job = await enqueue_job(
            session,
            run_id=run.id,
            step_run_id=step.id,
            dedupe_key=f"expired:{run.id}:{step.id}",
        )
        claimed = await claim_next_job(
            session, worker_id="worker-a", lease_duration=timedelta(minutes=5)
        )
        assert claimed is not None
        await session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        reclaimed = await reclaim_expired_job(
            session, worker_id="worker-b", lease_duration=timedelta(minutes=5)
        )
        assert reclaimed is not None
        assert reclaimed.id == job.id
        assert reclaimed.attempt == 2
        assert reclaimed.lease_owner == "worker-b"
        with pytest.raises(LeaseOwnershipError, match="no longer owned"):
            await complete_job(session, job_id=job.id, worker_id="worker-a")
        assert (
            await complete_job(session, job_id=job.id, worker_id="worker-b")
        ).status == "completed"
