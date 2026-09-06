"""Durable outbox and reconciliation primitives for external side effects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.harness.models import ContentRun, Job, TimestampMixin, new_id, utc_now

ReconciliationOutcome = Literal[
    "confirmed_success",
    "confirmed_absent",
    "conflict",
    "unknown",
]


class OutboxIntent(TimestampMixin, Base):
    """Durable intent for one logical external side effect."""

    __tablename__ = "outbox_intents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    intent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_ref: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    external_ref: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_json: Mapped[dict[str, object] | None] = mapped_column(JSON)

    __table_args__ = (
        CheckConstraint("attempt >= 0", name="ck_outbox_intent_attempt_nonnegative"),
        CheckConstraint(
            "status in ('pending','processing','completed','failed','needs_reconciliation')",
            name="ck_outbox_intent_status",
        ),
        UniqueConstraint("idempotency_key", name="uq_outbox_intent_idempotency_key"),
    )


@dataclass(frozen=True)
class SideEffectRequest:
    intent_type: str
    idempotency_key: str
    payload_ref: str


@dataclass(frozen=True)
class SideEffectExecutionResult:
    external_ref: str


@dataclass(frozen=True)
class ReconciliationResult:
    outcome: ReconciliationOutcome
    external_ref: str | None = None
    message: str | None = None


class SideEffectAdapter(Protocol):
    """Provider-neutral side-effect seam used by workers."""

    async def execute(self, request: SideEffectRequest) -> SideEffectExecutionResult: ...

    async def reconcile(self, request: SideEffectRequest) -> ReconciliationResult: ...


class OutboxStateError(ValueError):
    """Raised when an intent cannot perform the requested lifecycle transition."""


class IdempotencyConflictError(ValueError):
    """Raised when one idempotency key is reused for a different logical intent."""


class ReconciliationRequiredError(OutboxStateError):
    """Raised when an ambiguous/processing intent must reconcile before resend."""


async def create_outbox_intent(
    session: AsyncSession,
    *,
    run_id: UUID,
    intent_type: str,
    idempotency_key: str,
    payload_ref: str,
) -> OutboxIntent:
    """Persist or reuse one logical side-effect intent by idempotency key."""

    if not intent_type:
        raise ValueError("intent_type is required")
    if not idempotency_key:
        raise ValueError("idempotency_key is required")
    if not payload_ref:
        raise ValueError("payload_ref is required")

    run = await session.get(ContentRun, run_id)
    if run is None:
        raise ValueError("ContentRun not found")
    if run.run_mode == "eval":
        raise OutboxStateError("eval ContentRun cannot create external side effects")

    statement = (
        insert(OutboxIntent)
        .values(
            run_id=run_id,
            intent_type=intent_type,
            idempotency_key=idempotency_key,
            payload_ref=payload_ref,
            status="pending",
            attempt=0,
        )
        .on_conflict_do_nothing(index_elements=[OutboxIntent.idempotency_key])
        .returning(OutboxIntent.id)
    )
    intent_id = (await session.execute(statement)).scalar_one_or_none()
    if intent_id is not None:
        intent = await session.get(OutboxIntent, intent_id)
        assert intent is not None
        return intent

    existing = await session.scalar(
        select(OutboxIntent).where(OutboxIntent.idempotency_key == idempotency_key)
    )
    assert existing is not None
    if (
        existing.run_id != run_id
        or existing.intent_type != intent_type
        or existing.payload_ref != payload_ref
    ):
        raise IdempotencyConflictError(
            "idempotency key is already bound to a different side-effect intent"
        )
    return existing


async def get_outbox_intent(session: AsyncSession, *, intent_id: UUID) -> OutboxIntent:
    intent = await session.get(OutboxIntent, intent_id)
    if intent is None:
        raise ValueError("OutboxIntent not found")
    return intent


def side_effect_request(intent: OutboxIntent) -> SideEffectRequest:
    return SideEffectRequest(
        intent_type=intent.intent_type,
        idempotency_key=intent.idempotency_key,
        payload_ref=intent.payload_ref,
    )


def requires_reconciliation(intent: OutboxIntent) -> bool:
    return intent.status in {"processing", "needs_reconciliation"}


async def prepare_outbox_dispatch(
    session: AsyncSession,
    *,
    intent_id: UUID,
    job_id: UUID,
    worker_id: str,
) -> OutboxIntent:
    """Mark one committed pending intent processing before the external call."""

    intent = await _locked_intent(session, intent_id)
    await _require_job_lease(
        session,
        job_id=job_id,
        worker_id=worker_id,
        run_id=intent.run_id,
    )
    if intent.status == "completed":
        raise OutboxStateError("completed outbox intent cannot dispatch again")
    if requires_reconciliation(intent):
        raise ReconciliationRequiredError("outbox intent must reconcile before resend")
    if intent.status != "pending":
        raise OutboxStateError(f"outbox intent cannot dispatch from status: {intent.status}")

    intent.status = "processing"
    intent.attempt += 1
    intent.error_json = None
    await session.flush()
    return intent


async def complete_outbox_intent(
    session: AsyncSession,
    *,
    intent_id: UUID,
    job_id: UUID,
    worker_id: str,
    result: SideEffectExecutionResult,
) -> OutboxIntent:
    """Persist a confirmed external result for the current leased worker."""

    if not result.external_ref:
        raise ValueError("external_ref is required for completed side effect")
    intent = await _locked_intent(session, intent_id)
    await _require_job_lease(
        session,
        job_id=job_id,
        worker_id=worker_id,
        run_id=intent.run_id,
    )
    if intent.status != "processing":
        raise OutboxStateError("only a processing intent can complete")

    intent.status = "completed"
    intent.external_ref = result.external_ref
    intent.error_json = None
    await session.flush()
    return intent


async def mark_outbox_needs_reconciliation(
    session: AsyncSession,
    *,
    intent_id: UUID,
    job_id: UUID,
    worker_id: str,
    error_class: str,
    message: str,
) -> OutboxIntent:
    """Persist an explicitly ambiguous external result instead of blind retrying."""

    intent = await _locked_intent(session, intent_id)
    await _require_job_lease(
        session,
        job_id=job_id,
        worker_id=worker_id,
        run_id=intent.run_id,
    )
    if intent.status != "processing":
        raise OutboxStateError("only a processing intent can become ambiguous")

    intent.status = "needs_reconciliation"
    intent.error_json = {"class": error_class, "message": message}
    await session.flush()
    return intent


async def apply_reconciliation_result(
    session: AsyncSession,
    *,
    intent_id: UUID,
    job_id: UUID,
    worker_id: str,
    result: ReconciliationResult,
) -> OutboxIntent:
    """Apply one external reconciliation result without silently resending."""

    intent = await _locked_intent(session, intent_id)
    await _require_job_lease(
        session,
        job_id=job_id,
        worker_id=worker_id,
        run_id=intent.run_id,
    )
    if not requires_reconciliation(intent):
        raise OutboxStateError("outbox intent is not waiting for reconciliation")

    if result.outcome == "confirmed_success":
        if not result.external_ref:
            raise ValueError("confirmed_success requires external_ref")
        intent.status = "completed"
        intent.external_ref = result.external_ref
        intent.error_json = None
    elif result.outcome == "confirmed_absent":
        intent.status = "pending"
        intent.external_ref = None
        intent.error_json = None
    elif result.outcome == "conflict":
        intent.status = "failed"
        intent.external_ref = result.external_ref
        intent.error_json = {
            "class": "publish_conflict",
            "message": result.message or "external side effect conflicts with durable intent",
        }
    elif result.outcome == "unknown":
        intent.status = "needs_reconciliation"
        intent.error_json = {
            "class": "ambiguous_side_effect",
            "message": result.message or "external side-effect outcome is still unknown",
        }
    else:  # pragma: no cover - Literal plus defensive runtime guard
        raise ValueError(f"unsupported reconciliation outcome: {result.outcome}")

    await session.flush()
    return intent


async def _locked_intent(session: AsyncSession, intent_id: UUID) -> OutboxIntent:
    intent = await session.scalar(
        select(OutboxIntent).where(OutboxIntent.id == intent_id).with_for_update()
    )
    if intent is None:
        raise ValueError("OutboxIntent not found")
    return intent


async def _require_job_lease(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    run_id: UUID,
) -> Job:
    now = utc_now()
    job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if (
        job is None
        or job.run_id != run_id
        or job.status != "leased"
        or job.lease_owner != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
    ):
        raise OutboxStateError("side effect requires the current valid job lease")
    return job
