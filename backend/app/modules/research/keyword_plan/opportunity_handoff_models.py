"""Durable lineage for QM-02A planner selection handoffs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.harness.models import TimestampMixin, new_id


class OpportunityPlannerHandoff(TimestampMixin, Base):
    __tablename__ = "opportunity_planner_handoffs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
    )
    need_hypothesis_id: Mapped[UUID] = mapped_column(
        ForeignKey("need_hypotheses.id"),
        nullable=False,
    )
    content_opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_opportunities.id"),
        nullable=False,
    )
    human_selection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("human_selections.id")
    )
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    cluster_key: Mapped[str] = mapped_column(String(100), nullable=False)
    planner_policy_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    planner_snapshot_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    question_coverage_snapshot_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    recommendation_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    need_version: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
    )
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    resolution: Mapped[str] = mapped_column(String(16), nullable=False)
    selected_by: Mapped[str] = mapped_column(String(200), nullable=False)
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "planner_snapshot_hash",
            "cluster_key",
            name="uq_opportunity_planner_handoff_snapshot_cluster",
        ),
        CheckConstraint(
            "planner_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_opportunity_planner_handoff_planner_hash",
        ),
        CheckConstraint(
            "question_coverage_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_opportunity_planner_handoff_coverage_hash",
        ),
        CheckConstraint(
            "recommendation_hash ~ '^[0-9a-f]{64}$'",
            name="ck_opportunity_planner_handoff_recommendation_hash",
        ),
        CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'",
            name="ck_opportunity_planner_handoff_request_hash",
        ),
        CheckConstraint(
            "need_version > 0",
            name="ck_opportunity_planner_handoff_need_version_positive",
        ),
        CheckConstraint(
            "resolution in ('SELECTED','REUSED')",
            name="ck_opportunity_planner_handoff_resolution",
        ),
        CheckConstraint(
            "resolution <> 'SELECTED' or human_selection_id is not null",
            name="ck_opportunity_planner_handoff_selected_selection",
        ),
        CheckConstraint(
            "btrim(cluster_key) <> ''",
            name="ck_opportunity_planner_handoff_cluster_key",
        ),
        CheckConstraint(
            "btrim(idempotency_key) <> ''",
            name="ck_opportunity_planner_handoff_idempotency_key",
        ),
        CheckConstraint(
            "btrim(selected_by) <> ''",
            name="ck_opportunity_planner_handoff_selected_by",
        ),
        CheckConstraint(
            "btrim(selection_reason) <> ''",
            name="ck_opportunity_planner_handoff_selection_reason",
        ),
        Index(
            "ix_opportunity_planner_handoffs_opportunity",
            "content_opportunity_id",
        ),
        Index(
            "ix_opportunity_planner_handoffs_need_locale",
            "need_hypothesis_id",
            "locale",
        ),
    )


__all__ = ["OpportunityPlannerHandoff"]
