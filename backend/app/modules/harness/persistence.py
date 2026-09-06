"""Small durable-state operations for the CE03 queue and worker lease core."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import Select, and_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.harness.models import ContentRun, Job, StepRun, utc_now


class InvalidStateTransitionError(ValueError):
    """Raised when a run or step attempts an unsupported state change."""


class LeaseOwnershipError(ValueError):
    """Raised when a worker tries to act on a lease it no longer owns."""


RUN_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "cancelled"},
    "running": {"waiting_approval", "completed", "failed", "cancelled"},
    "waiting_approval": {"running", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}

STEP_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running"},
    "running": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
    "skipped": set(),
}


async def transition_run(session: AsyncSession, *, run_id: UUID, status: str) -> ContentRun:
    run = await _locked_row(session, ContentRun, run_id)
    if status not in RUN_TRANSITIONS[run.status]:
        raise InvalidStateTransitionError(
            f"invalid content run transition: {run.status} -> {status}"
        )
    run.status = status
    if status in {"completed", "failed", "cancelled"}:
        run.completed_at = utc_now()
    await session.flush()
    return run


async def transition_step_run(session: AsyncSession, *, step_run_id: UUID, status: str) -> StepRun:
    step_run = await _locked_row(session, StepRun, step_run_id)
    if status not in STEP_TRANSITIONS[step_run.status]:
        raise InvalidStateTransitionError(
            f"invalid step run transition: {step_run.status} -> {status}"
        )
    step_run.status = status
    now = utc_now()
    if status == "running":
        step_run.started_at = now
    if status in {"completed", "failed"}:
        step_run.completed_at = now
    await session.flush()
    return step_run


async def create_step_retry(session: AsyncSession, *, failed_step_run_id: UUID) -> StepRun:
    failed_step_run = await _locked_row(session, StepRun, failed_step_run_id)
    if failed_step_run.status != "failed":
        raise InvalidStateTransitionError("only a failed step run can create a retry attempt")
    retry = StepRun(
        run_id=failed_step_run.run_id,
        step_key=failed_step_run.step_key,
        attempt=failed_step_run.attempt + 1,
        status="pending",
        input_artifact_refs_json=failed_step_run.input_artifact_refs_json,
        output_artifact_refs_json=[],
    )
    session.add(retry)
    await session.flush()
    return retry


async def enqueue_job(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
    dedupe_key: str,
    available_at: datetime | None = None,
) -> Job:
    available = utc_now() if available_at is None else available_at
    statement = (
        insert(Job)
        .values(
            run_id=run_id,
            step_run_id=step_run_id,
            status="queued",
            available_at=available,
            attempt=1,
            dedupe_key=dedupe_key,
        )
        .on_conflict_do_nothing(index_elements=[Job.dedupe_key])
        .returning(Job.id)
    )
    job_id = (await session.execute(statement)).scalar_one_or_none()
    if job_id is not None:
        job = await session.get(Job, job_id)
        assert job is not None
        return job
    existing = await session.scalar(select(Job).where(Job.dedupe_key == dedupe_key))
    assert existing is not None
    return existing


async def claim_next_job(
    session: AsyncSession, *, worker_id: str, lease_duration: timedelta
) -> Job | None:
    now = utc_now()
    candidate = _next_job_query(now).cte("next_job")
    statement = (
        update(Job)
        .where(Job.id == candidate.c.id)
        .values(
            status="leased",
            lease_owner=worker_id,
            lease_expires_at=now + lease_duration,
            updated_at=now,
        )
        .returning(Job)
    )
    job = (await session.execute(statement)).scalar_one_or_none()
    if job is None:
        return None
    await session.execute(
        update(StepRun)
        .where(and_(StepRun.id == job.step_run_id, StepRun.status == "pending"))
        .values(status="running", started_at=now, updated_at=now)
    )
    return job


async def heartbeat_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    extend_by: timedelta,
) -> Job:
    now = utc_now()
    statement = (
        update(Job)
        .where(
            Job.id == job_id,
            Job.status == "leased",
            Job.lease_owner == worker_id,
            Job.lease_expires_at > now,
        )
        .values(lease_expires_at=now + extend_by, updated_at=now)
        .returning(Job)
    )
    job = (await session.execute(statement)).scalar_one_or_none()
    if job is None:
        raise LeaseOwnershipError("job lease is not owned by this worker")
    return job


async def reclaim_expired_job(
    session: AsyncSession, *, worker_id: str, lease_duration: timedelta
) -> Job | None:
    now = utc_now()
    candidate = (
        select(Job.id)
        .where(Job.status == "leased", Job.lease_expires_at < now)
        .order_by(Job.lease_expires_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .cte("expired_job")
    )
    statement = (
        update(Job)
        .where(Job.id == candidate.c.id)
        .values(
            attempt=Job.attempt + 1,
            lease_owner=worker_id,
            lease_expires_at=now + lease_duration,
            updated_at=now,
        )
        .returning(Job)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def complete_job(session: AsyncSession, *, job_id: UUID, worker_id: str) -> Job:
    now = utc_now()
    statement = (
        update(Job)
        .where(
            Job.id == job_id,
            Job.status == "leased",
            Job.lease_owner == worker_id,
            Job.lease_expires_at > now,
        )
        .values(status="completed", lease_owner=None, lease_expires_at=None, updated_at=now)
        .returning(Job)
    )
    job = (await session.execute(statement)).scalar_one_or_none()
    if job is None:
        raise LeaseOwnershipError("job lease is no longer owned by this worker")
    await session.execute(
        update(StepRun)
        .where(StepRun.id == job.step_run_id)
        .values(status="completed", completed_at=now, updated_at=now)
    )
    return job


def _next_job_query(now: datetime) -> Select[tuple[UUID]]:
    return (
        select(Job.id)
        .where(Job.status == "queued", Job.available_at <= now)
        .order_by(Job.available_at, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )


async def _locked_row(session: AsyncSession, model: type[ContentRun] | type[StepRun], row_id: UUID):
    row = await session.scalar(select(model).where(model.id == row_id).with_for_update())
    if row is None:
        raise ValueError(f"{model.__name__} not found")
    return row
