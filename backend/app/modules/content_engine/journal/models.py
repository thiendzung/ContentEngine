"""Durable CE05 Journal approval records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.harness.models import TimestampMixin, new_id


class AngleApproval(TimestampMixin, Base):
    """One immutable human decision for one exact Angle artifact snapshot."""

    __tablename__ = "angle_approvals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    angle_artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False
    )
    angle_artifact_version: Mapped[int] = mapped_column(nullable=False)
    angle_artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_angle_id: Mapped[str] = mapped_column(String(200), nullable=False)
    selected_candidate_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(200), nullable=False)
    approval_reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "angle_artifact_id",
            "angle_artifact_version",
            "angle_artifact_hash",
            name="uq_angle_approval_artifact_snapshot",
        ),
        CheckConstraint(
            "angle_artifact_version > 0",
            name="ck_angle_approval_artifact_version_positive",
        ),
        CheckConstraint(
            "angle_artifact_hash ~ '^[0-9a-f]{64}$'",
            name="ck_angle_approval_artifact_hash",
        ),
        CheckConstraint(
            "selected_candidate_hash ~ '^[0-9a-f]{64}$'",
            name="ck_angle_approval_candidate_hash",
        ),
        CheckConstraint("btrim(selected_angle_id) <> ''", name="ck_angle_approval_angle_id"),
        CheckConstraint("btrim(approved_by) <> ''", name="ck_angle_approval_approved_by"),
        CheckConstraint("btrim(approval_reason) <> ''", name="ck_angle_approval_reason"),
        Index("ix_angle_approvals_artifact", "angle_artifact_id"),
    )


__all__ = ["AngleApproval"]
