"""Crash recovery for the bounded Start-to-Angle operator worker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.operator_vertical_slice import START_TO_ANGLE_STAGE
from app.modules.content_engine.journal.operator_worker import (
    OperatorWorkerError,
    claim_next_operator_job,
)
from app.modules.harness.models import Job, StepRun


async def reclaim_expired_start_to_angle_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int = 900,
) -> Job | None:
    """Reclaim only an expired lease for the allow-listed PR4.5 stage."""

    if not worker_id.strip() or lease_seconds <= 0:
        raise OperatorWorkerError("operator_worker_lease_invalid")
    now = datetime.now(UTC)
    candidate = (
        select(Job.id)
        .join(StepRun, StepRun.id == Job.step_run_id)
        .where(
            Job.status == "leased",
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at < now,
            StepRun.step_key == START_TO_ANGLE_STAGE,
            StepRun.status == "running",
        )
        .order_by(Job.lease_expires_at, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .cte("expired_start_to_angle_job")
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


async def claim_or_reclaim_operator_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int = 900,
) -> Job | None:
    """Recover an expired owned stage before claiming new queued work."""

    recovered = await reclaim_expired_start_to_angle_job(
        session,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )
    if recovered is not None:
        return recovered
    return await claim_next_operator_job(
        session,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )


__all__ = [
    "claim_or_reclaim_operator_job",
    "reclaim_expired_start_to_angle_job",
]
