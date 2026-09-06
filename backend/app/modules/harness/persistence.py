"""Durable state operations for the CE03 harness."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.harness.models import (
    Approval,
    Artifact,
    ContentRun,
    ContextManifest,
    Job,
    ModelCall,
    StepRun,
    ToolCall,
    utc_now,
)
from app.modules.harness.policy import (
    BudgetExtras,
    BudgetLimits,
    BudgetUsage,
    RetryPolicy,
    is_retryable_failure,
)


class InvalidStateTransitionError(ValueError):
    """Raised when a run or step attempts an unsupported state change."""


class LeaseOwnershipError(ValueError):
    """Raised when a worker tries to act on a lease it no longer owns."""


class StaleApprovalArtifactError(ValueError):
    """Raised when approval targets an artifact version that is no longer current."""


@dataclass(frozen=True)
class RetryResult:
    """Result of one durable failure/retry decision."""

    retried: bool
    failure_class: str
    step_run_id: UUID
    retry_step_run_id: UUID | None = None
    retry_job_id: UUID | None = None


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
    run = await session.scalar(select(ContentRun).where(ContentRun.id == run_id).with_for_update())
    if run is None:
        raise ValueError("ContentRun not found")
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
    step_run = await session.scalar(
        select(StepRun).where(StepRun.id == step_run_id).with_for_update()
    )
    if step_run is None:
        raise ValueError("StepRun not found")
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
    failed_step_run = await session.scalar(
        select(StepRun).where(StepRun.id == failed_step_run_id).with_for_update()
    )
    if failed_step_run is None:
        raise ValueError("StepRun not found")
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


async def create_checkpoint(
    session: AsyncSession,
    *,
    run_id: UUID,
    pending_approval: dict[str, object] | None = None,
    budget_limits: BudgetLimits | None = None,
    budget_usage: BudgetUsage | None = None,
) -> Artifact:
    """Persist an immutable, versioned snapshot of durable run state."""

    run = await session.scalar(select(ContentRun).where(ContentRun.id == run_id).with_for_update())
    if run is None:
        raise ValueError("ContentRun not found")

    steps = list(
        (
            await session.scalars(
                select(StepRun)
                .where(StepRun.run_id == run_id)
                .order_by(StepRun.step_key, StepRun.attempt)
            )
        ).all()
    )
    artifacts = list(
        (
            await session.scalars(
                select(Artifact)
                .where(Artifact.run_id == run_id, Artifact.artifact_type != "checkpoint")
                .order_by(Artifact.created_at, Artifact.id)
            )
        ).all()
    )
    approvals = list(
        (
            await session.scalars(
                select(Approval)
                .where(Approval.run_id == run_id)
                .order_by(Approval.created_at, Approval.id)
            )
        ).all()
    )
    context_manifest_ids = [
        str(value)
        for value in (
            await session.scalars(
                select(ContextManifest.id)
                .where(ContextManifest.run_id == run_id)
                .order_by(ContextManifest.created_at, ContextManifest.id)
            )
        ).all()
    ]
    model_call_ids = [
        str(value)
        for value in (
            await session.scalars(
                select(ModelCall.id)
                .where(ModelCall.run_id == run_id)
                .order_by(ModelCall.created_at, ModelCall.id)
            )
        ).all()
    ]
    tool_call_ids = [
        str(value)
        for value in (
            await session.scalars(
                select(ToolCall.id)
                .where(ToolCall.run_id == run_id)
                .order_by(ToolCall.created_at, ToolCall.id)
            )
        ).all()
    ]
    latest_manifest = await session.scalar(
        select(ContextManifest)
        .where(ContextManifest.run_id == run_id)
        .order_by(ContextManifest.created_at.desc(), ContextManifest.id.desc())
        .limit(1)
    )
    retry_counters: dict[str, int] = {}
    for step in steps:
        retry_counters[step.step_key] = max(retry_counters.get(step.step_key, 0), step.attempt)

    payload: dict[str, object] = {
        "run_id": str(run.id),
        "run_status": run.status,
        "current_step": run.current_step,
        "settings_snapshot_id": str(run.settings_snapshot_id),
        "evidence_set_id": (
            str(latest_manifest.evidence_set_id)
            if latest_manifest is not None and latest_manifest.evidence_set_id is not None
            else None
        ),
        "steps": [
            {
                "id": str(step.id),
                "step_key": step.step_key,
                "attempt": step.attempt,
                "status": step.status,
                "output_artifact_refs": step.output_artifact_refs_json,
            }
            for step in steps
        ],
        "artifact_ids": [str(artifact.id) for artifact in artifacts],
        "context_manifest_ids": context_manifest_ids,
        "model_call_ids": model_call_ids,
        "tool_call_ids": tool_call_ids,
        "approval_ids": [str(approval.id) for approval in approvals],
        "pending_approval": pending_approval,
        "retry_counters": retry_counters,
        "budget_limits": _json_safe(asdict(budget_limits)) if budget_limits is not None else None,
        "budget_usage": _json_safe(asdict(budget_usage)) if budget_usage is not None else None,
    }
    current_version = await session.scalar(
        select(func.coalesce(func.max(Artifact.version), 0)).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == "checkpoint",
        )
    )
    next_version = int(current_version or 0) + 1
    checkpoint = Artifact(
        run_id=run_id,
        artifact_type="checkpoint",
        version=next_version,
        content_json=payload,
        content_hash=_payload_hash(payload),
    )
    session.add(checkpoint)
    await session.flush()
    return checkpoint


async def get_latest_checkpoint(session: AsyncSession, *, run_id: UUID) -> Artifact | None:
    """Load the newest checkpoint without mutating durable state."""

    checkpoint: Artifact | None = await session.scalar(
        select(Artifact)
        .where(Artifact.run_id == run_id, Artifact.artifact_type == "checkpoint")
        .order_by(Artifact.version.desc())
        .limit(1)
    )
    return checkpoint


async def pause_for_approval(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_key: str,
    artifact_id: UUID,
    budget_limits: BudgetLimits | None = None,
    budget_usage: BudgetUsage | None = None,
) -> Artifact:
    """Checkpoint the exact artifact, then move the run into approval wait state."""

    artifact = await _require_run_artifact(session, run_id=run_id, artifact_id=artifact_id)
    await _require_artifact_matches_step(session, artifact=artifact, step_key=step_key)
    checkpoint = await create_checkpoint(
        session,
        run_id=run_id,
        pending_approval={"step_key": step_key, "artifact_id": str(artifact.id)},
        budget_limits=budget_limits,
        budget_usage=budget_usage,
    )
    await transition_run(session, run_id=run_id, status="waiting_approval")
    return checkpoint


async def resolve_approval(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_key: str,
    artifact_id: UUID,
    decision: str,
    actor_id: str,
    comment: str | None = None,
) -> Approval:
    """Record a durable human decision for the current artifact version."""

    if decision not in {"approved", "rejected", "changes_requested"}:
        raise ValueError(f"unsupported approval decision: {decision}")
    run = await session.scalar(select(ContentRun).where(ContentRun.id == run_id).with_for_update())
    if run is None:
        raise ValueError("ContentRun not found")
    if run.status != "waiting_approval":
        raise InvalidStateTransitionError("run is not waiting for approval")

    artifact = await _require_run_artifact(session, run_id=run_id, artifact_id=artifact_id)
    await _require_artifact_matches_step(session, artifact=artifact, step_key=step_key)
    latest_checkpoint = await get_latest_checkpoint(session, run_id=run_id)
    pending_approval = (
        latest_checkpoint.content_json.get("pending_approval")
        if latest_checkpoint is not None and latest_checkpoint.content_json is not None
        else None
    )
    if pending_approval != {"step_key": step_key, "artifact_id": str(artifact_id)}:
        raise StaleApprovalArtifactError("artifact version is no longer current")

    latest_artifact = await session.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == artifact.artifact_type,
        )
        .order_by(Artifact.version.desc())
        .limit(1)
    )
    if latest_artifact is None or latest_artifact.id != artifact.id:
        raise StaleApprovalArtifactError("artifact version is no longer current")

    approval = Approval(
        run_id=run_id,
        step_key=step_key,
        artifact_id=artifact_id,
        decision=decision,
        actor_id=actor_id,
        comment=comment,
    )
    session.add(approval)
    await session.flush()

    target_status = "cancelled" if decision == "rejected" else "running"
    await transition_run(session, run_id=run_id, status=target_status)
    await create_checkpoint(session, run_id=run_id)
    return approval


async def fail_job_and_maybe_retry(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    failure_class: str,
    message: str,
    retry_policy: RetryPolicy,
) -> RetryResult:
    """Atomically fail the leased attempt and enqueue a bounded retry when allowed."""

    retryable = is_retryable_failure(failure_class)
    now = utc_now()
    job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if (
        job is None
        or job.status != "leased"
        or job.lease_owner != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
    ):
        raise LeaseOwnershipError("job lease is no longer owned by this worker")

    step = await session.scalar(
        select(StepRun).where(StepRun.id == job.step_run_id).with_for_update()
    )
    if step is None:
        raise ValueError("StepRun not found")
    if step.status != "running":
        raise InvalidStateTransitionError("leased job step is not running")

    job.status = "failed"
    job.lease_owner = None
    job.lease_expires_at = None
    step.status = "failed"
    step.completed_at = now
    step.error_json = {"class": failure_class, "message": message}
    await session.flush()

    if retryable and step.attempt < retry_policy.max_step_attempts:
        retry = StepRun(
            run_id=step.run_id,
            step_key=step.step_key,
            attempt=step.attempt + 1,
            status="pending",
            input_artifact_refs_json=step.input_artifact_refs_json,
            output_artifact_refs_json=[],
        )
        session.add(retry)
        await session.flush()
        retry_job = await enqueue_job(
            session,
            run_id=step.run_id,
            step_run_id=retry.id,
            dedupe_key=f"retry:{step.run_id}:{step.step_key}:{retry.attempt}",
            available_at=now + timedelta(seconds=retry_policy.backoff_seconds),
        )
        return RetryResult(
            retried=True,
            failure_class=failure_class,
            step_run_id=step.id,
            retry_step_run_id=retry.id,
            retry_job_id=retry_job.id,
        )

    run = await session.scalar(
        select(ContentRun).where(ContentRun.id == step.run_id).with_for_update()
    )
    if run is None:
        raise ValueError("ContentRun not found")
    if run.status == "running":
        run.status = "failed"
        run.completed_at = now
    run.failure_code = failure_class
    run.failure_message = message
    await session.flush()
    return RetryResult(
        retried=False,
        failure_class=failure_class,
        step_run_id=step.id,
    )


async def load_budget_usage(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None = None,
    extras: BudgetExtras | None = None,
) -> BudgetUsage:
    """Read budget usage from existing ledgers plus explicit non-ledger counters."""

    extra = extras or BudgetExtras()
    model_filters = [ModelCall.run_id == run_id]
    tool_filters = [ToolCall.run_id == run_id]
    if step_run_id is not None:
        model_filters.append(ModelCall.step_run_id == step_run_id)
        tool_filters.append(ToolCall.step_run_id == step_run_id)

    model_row = (
        await session.execute(
            select(
                func.count(ModelCall.id),
                func.coalesce(func.sum(ModelCall.output_tokens), 0),
                func.coalesce(func.sum(ModelCall.cost), Decimal("0")),
            ).where(*model_filters)
        )
    ).one()
    tool_calls = await session.scalar(select(func.count(ToolCall.id)).where(*tool_filters))

    started_at: datetime | None
    if step_run_id is None:
        started_at = await session.scalar(
            select(ContentRun.started_at).where(ContentRun.id == run_id)
        )
    else:
        started_at = await session.scalar(
            select(StepRun.started_at).where(StepRun.id == step_run_id)
        )
    wall_clock_seconds = 0.0
    if started_at is not None:
        wall_clock_seconds = max(0.0, (utc_now() - started_at).total_seconds())

    return BudgetUsage(
        model_calls=int(model_row[0] or 0),
        tool_calls=int(tool_calls or 0),
        context_estimate=extra.context_estimate,
        output_tokens=int(model_row[1] or 0),
        estimated_cost=Decimal(model_row[2] or 0),
        wall_clock_seconds=wall_clock_seconds,
        research_sources=extra.research_sources,
        revise_loops=extra.revise_loops,
    )


def _next_job_query(now: datetime) -> Select[tuple[UUID]]:
    return (
        select(Job.id)
        .where(Job.status == "queued", Job.available_at <= now)
        .order_by(Job.available_at, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )


async def _require_run_artifact(
    session: AsyncSession, *, run_id: UUID, artifact_id: UUID
) -> Artifact:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None or artifact.run_id != run_id:
        raise ValueError("Artifact does not belong to ContentRun")
    return artifact


async def _require_artifact_matches_step(
    session: AsyncSession, *, artifact: Artifact, step_key: str
) -> None:
    if artifact.step_run_id is None:
        return
    step = await session.get(StepRun, artifact.step_run_id)
    if step is None or step.step_key != step_key:
        raise ValueError("Artifact does not belong to approval step")


def _payload_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_safe(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
