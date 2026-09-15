from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.content_engine.models import TimestampMixin, new_id


class KnowledgeBrief(TimestampMixin, Base):
    __tablename__ = "knowledge_briefs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    knowledge_coverage_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_coverage_plans.id"),
        nullable=False,
    )
    knowledge_harvest_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_harvests.id"),
        nullable=False,
    )
    content_case_id: Mapped[UUID | None] = mapped_column(ForeignKey("content_cases.id"))
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    coverage_plan_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    harvest_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    brief_method: Mapped[str] = mapped_column(String(64), nullable=False)
    brief_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "btrim(locale) <> ''",
            name="ck_knowledge_briefs_locale_required",
        ),
        CheckConstraint(
            "btrim(created_by) <> ''",
            name="ck_knowledge_briefs_created_by_required",
        ),
        CheckConstraint(
            "brief_method = 'coverage_bound_knowledge_brief_v1'",
            name="ck_knowledge_briefs_method",
        ),
        CheckConstraint(
            "coverage_plan_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_briefs_plan_hash",
        ),
        CheckConstraint(
            "harvest_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_briefs_harvest_hash",
        ),
        CheckConstraint(
            "snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_briefs_hash",
        ),
        CheckConstraint(
            "json_typeof(brief_json) = 'object'",
            name="ck_knowledge_briefs_payload_object",
        ),
        Index(
            "uq_knowledge_briefs_plan_method",
            "knowledge_coverage_plan_id",
            "brief_method",
            unique=True,
        ),
        Index(
            "uq_knowledge_briefs_project_hash",
            "project_id",
            "snapshot_hash",
            unique=True,
        ),
        Index(
            "ix_knowledge_briefs_project_locale",
            "project_id",
            "locale",
        ),
        Index("ix_knowledge_briefs_case", "content_case_id"),
    )


__all__ = ["KnowledgeBrief"]
