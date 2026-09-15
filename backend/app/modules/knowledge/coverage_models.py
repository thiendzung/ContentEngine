from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.content_engine.models import TimestampMixin, new_id


class KnowledgeCoveragePlan(TimestampMixin, Base):
    __tablename__ = "knowledge_coverage_plans"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    knowledge_harvest_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_harvests.id"), nullable=False
    )
    content_case_id: Mapped[UUID | None] = mapped_column(ForeignKey("content_cases.id"))
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    harvest_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    planner_method: Mapped[str] = mapped_column(String(64), nullable=False)
    lanes_json: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    summary_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "btrim(locale) <> ''",
            name="ck_knowledge_coverage_plans_locale_required",
        ),
        CheckConstraint(
            "btrim(created_by) <> ''",
            name="ck_knowledge_coverage_plans_created_by_required",
        ),
        CheckConstraint(
            "planner_method = 'leaf_topic_freshness_coverage_v1'",
            name="ck_knowledge_coverage_plans_method",
        ),
        CheckConstraint(
            "harvest_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_coverage_plans_harvest_hash",
        ),
        CheckConstraint(
            "snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_coverage_plans_hash",
        ),
        CheckConstraint(
            "json_typeof(lanes_json) = 'array'",
            name="ck_knowledge_coverage_plans_lanes_array",
        ),
        CheckConstraint(
            "json_array_length(lanes_json) > 0",
            name="ck_knowledge_coverage_plans_lanes_required",
        ),
        CheckConstraint(
            "json_typeof(summary_json) = 'object'",
            name="ck_knowledge_coverage_plans_summary_object",
        ),
        Index(
            "uq_knowledge_coverage_plans_harvest_method",
            "knowledge_harvest_id",
            "planner_method",
            unique=True,
        ),
        Index(
            "uq_knowledge_coverage_plans_project_hash",
            "project_id",
            "snapshot_hash",
            unique=True,
        ),
        Index(
            "ix_knowledge_coverage_plans_project_locale",
            "project_id",
            "locale",
        ),
        Index("ix_knowledge_coverage_plans_case", "content_case_id"),
    )


__all__ = ["KnowledgeCoveragePlan"]
