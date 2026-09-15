from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.harness.models import TimestampMixin, new_id


class ModelRouteDecision(TimestampMixin, Base):
    __tablename__ = "model_route_decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    model_call_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_calls.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    step_run_id: Mapped[UUID] = mapped_column(ForeignKey("step_runs.id"), nullable=False)
    settings_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("settings_snapshots.id"), nullable=False
    )
    task_key: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_key: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    capability: Mapped[str] = mapped_column(String(100), nullable=False)
    candidate_index: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_reason: Mapped[str | None] = mapped_column(String(100))
    max_escalations: Mapped[int] = mapped_column(Integer, nullable=False)
    max_model_calls_per_step: Mapped[int] = mapped_column(Integer, nullable=False)
    route_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    route_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("model_call_id", name="uq_model_route_decisions_call"),
        CheckConstraint("policy_version > 0", name="ck_model_route_policy_version_positive"),
        CheckConstraint("candidate_index >= 0", name="ck_model_route_candidate_index_nonnegative"),
        CheckConstraint("max_escalations >= 0", name="ck_model_route_max_escalations_nonnegative"),
        CheckConstraint(
            "max_model_calls_per_step > 0",
            name="ck_model_route_max_calls_positive",
        ),
        CheckConstraint(
            "route_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_model_route_snapshot_hash",
        ),
        CheckConstraint("btrim(task_key) <> ''", name="ck_model_route_task_key_required"),
        CheckConstraint("btrim(policy_key) <> ''", name="ck_model_route_policy_key_required"),
        CheckConstraint("btrim(capability) <> ''", name="ck_model_route_capability_required"),
        Index(
            "ix_model_route_decisions_step_policy",
            "step_run_id",
            "policy_key",
            "capability",
        ),
        Index("ix_model_route_decisions_settings", "settings_snapshot_id"),
    )


__all__ = ["ModelRouteDecision"]
