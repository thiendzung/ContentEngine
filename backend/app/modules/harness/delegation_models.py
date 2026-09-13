"""Durable Codex delegation telemetry records.

These records capture safe execution hierarchy only. They intentionally exclude
prompts, provider payloads, chain-of-thought and other sensitive content.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.harness.models import TimestampMixin, new_id


class DelegationExecution(TimestampMixin, Base):
    __tablename__ = "delegation_executions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    step_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("step_runs.id"))
    parent_execution_id: Mapped[UUID | None] = mapped_column(ForeignKey("delegation_executions.id"))
    coordinator_key: Mapped[str] = mapped_column(String(100), nullable=False, default="codex")
    worker_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    worker_key: Mapped[str] = mapped_column(String(200), nullable=False)
    task_key: Mapped[str] = mapped_column(String(100), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    external_execution_id: Mapped[str | None] = mapped_column(String(255))
    result_artifact_id: Mapped[UUID | None] = mapped_column(ForeignKey("artifacts.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_class: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint("attempt > 0", name="ck_delegation_execution_attempt_positive"),
        CheckConstraint(
            "worker_kind in ('subagent','application','tool')",
            name="ck_delegation_execution_worker_kind",
        ),
        CheckConstraint(
            "status in ('queued','running','completed','failed','cancelled')",
            name="ck_delegation_execution_status",
        ),
        UniqueConstraint("dedupe_key", name="uq_delegation_execution_dedupe_key"),
        Index("ix_delegation_execution_run", "run_id"),
        Index("ix_delegation_execution_step", "step_run_id"),
        Index("ix_delegation_execution_parent", "parent_execution_id"),
    )


__all__ = ["DelegationExecution"]
