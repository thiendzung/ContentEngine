import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text, update
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

BACKEND_DIR = Path(__file__).resolve().parents[1]


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


@pytest.mark.asyncio
async def test_concurrent_claim_uses_two_connections_and_skips_locked_job() -> None:
    async with engine.connect() as setup_connection:
        setup_session = AsyncSession(bind=setup_connection, expire_on_commit=False)
        run = await create_synthetic_run(setup_session)
        step = await create_synthetic_step(setup_session, run)
        job = await enqueue_job(
            setup_session,
            run_id=run.id,
            step_run_id=step.id,
            dedupe_key=f"concurrent:{run.id}:{step.id}",
        )
        content_case = await setup_session.get(ContentCase, run.content_case_id)
        assert content_case is not None
        opportunity_id = content_case.content_opportunity_id
        hypothesis_id = content_case.need_hypothesis_id
        await setup_session.commit()
        await setup_session.close()

    async with engine.connect() as connection_a, engine.connect() as connection_b:
        transaction_a = await connection_a.begin()
        transaction_b = await connection_b.begin()
        session_a = AsyncSession(bind=connection_a, expire_on_commit=False)
        session_b = AsyncSession(bind=connection_b, expire_on_commit=False)
        try:
            claimed_a = await claim_next_job(
                session_a, worker_id="worker-a", lease_duration=timedelta(minutes=5)
            )
            assert claimed_a is not None
            assert claimed_a.id == job.id
            claimed_b = await claim_next_job(
                session_b, worker_id="worker-b", lease_duration=timedelta(minutes=5)
            )
            assert claimed_b is None
            await transaction_a.commit()
            await transaction_b.rollback()
        finally:
            await session_a.close()
            await session_b.close()

    async with engine.connect() as reload_connection:
        leased_count = await reload_connection.scalar(
            select(func.count()).select_from(Job).where(Job.id == job.id, Job.status == "leased")
        )
        lease_owner = await reload_connection.scalar(
            select(Job.lease_owner).where(Job.id == job.id, Job.status == "leased")
        )
        assert leased_count == 1
        assert lease_owner == "worker-a"

    async with engine.begin() as cleanup_connection:
        await cleanup_connection.execute(delete(Job).where(Job.id == job.id))
        await cleanup_connection.execute(delete(StepRun).where(StepRun.id == step.id))
        await cleanup_connection.execute(delete(ContentRun).where(ContentRun.id == run.id))
        await cleanup_connection.execute(
            delete(LocaleVariant).where(LocaleVariant.id == run.locale_variant_id)
        )
        await cleanup_connection.execute(
            delete(ContentCase).where(ContentCase.id == run.content_case_id)
        )
        await cleanup_connection.execute(
            delete(ContentOpportunity).where(ContentOpportunity.id == opportunity_id)
        )
        await cleanup_connection.execute(
            delete(NeedHypothesis).where(NeedHypothesis.id == hypothesis_id)
        )
        await cleanup_connection.execute(
            text("DROP TRIGGER settings_snapshots_immutable ON settings_snapshots")
        )
        await cleanup_connection.execute(
            delete(SettingsSnapshot).where(SettingsSnapshot.id == run.settings_snapshot_id)
        )
        await cleanup_connection.execute(
            text(
                "CREATE TRIGGER settings_snapshots_immutable "
                "BEFORE UPDATE OR DELETE ON settings_snapshots FOR EACH ROW "
                "EXECUTE FUNCTION prevent_settings_snapshot_mutation()"
            )
        )


def run_alembic(*arguments: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_DIR,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.asyncio
async def test_migration_0007_translates_real_paused_run_data_safely() -> None:
    async with engine.connect() as connection:
        session = AsyncSession(bind=connection, expire_on_commit=False)
        run = await create_synthetic_run(session)
        content_case = await session.get(ContentCase, run.content_case_id)
        assert content_case is not None
        opportunity_id = content_case.content_opportunity_id
        hypothesis_id = content_case.need_hypothesis_id
        await session.commit()
        await session.close()

    identifiers = {
        "run": run.id,
        "content_case": run.content_case_id,
        "locale_variant": run.locale_variant_id,
        "opportunity": opportunity_id,
        "hypothesis": hypothesis_id,
        "snapshot": run.settings_snapshot_id,
    }
    try:
        run_alembic("downgrade", "20260906_0006")
        async with engine.begin() as connection:
            await connection.execute(
                update(ContentRun).where(ContentRun.id == run.id).values(status="paused")
            )

        run_alembic("upgrade", "20260906_0007")
        async with engine.connect() as connection:
            status = await connection.scalar(
                select(ContentRun.status).where(ContentRun.id == run.id)
            )
            assert status == "waiting_approval"

        run_alembic("downgrade", "20260906_0006")
        async with engine.connect() as connection:
            status = await connection.scalar(
                select(ContentRun.status).where(ContentRun.id == run.id)
            )
            assert status == "paused"
    finally:
        run_alembic("upgrade", "head")
        async with engine.begin() as connection:
            await connection.execute(delete(ContentRun).where(ContentRun.id == identifiers["run"]))
            await connection.execute(
                delete(LocaleVariant).where(LocaleVariant.id == identifiers["locale_variant"])
            )
            await connection.execute(
                delete(ContentCase).where(ContentCase.id == identifiers["content_case"])
            )
            await connection.execute(
                delete(ContentOpportunity).where(
                    ContentOpportunity.id == identifiers["opportunity"]
                )
            )
            await connection.execute(
                delete(NeedHypothesis).where(NeedHypothesis.id == identifiers["hypothesis"])
            )
            await connection.execute(
                text("DROP TRIGGER settings_snapshots_immutable ON settings_snapshots")
            )
            await connection.execute(
                delete(SettingsSnapshot).where(SettingsSnapshot.id == identifiers["snapshot"])
            )
            await connection.execute(
                text(
                    "CREATE TRIGGER settings_snapshots_immutable "
                    "BEFORE UPDATE OR DELETE ON settings_snapshots FOR EACH ROW "
                    "EXECUTE FUNCTION prevent_settings_snapshot_mutation()"
                )
            )
