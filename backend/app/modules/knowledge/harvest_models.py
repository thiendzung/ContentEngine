from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.content_engine.models import TimestampMixin, new_id


class KnowledgeHarvest(TimestampMixin, Base):
    __tablename__ = "knowledge_harvests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    content_case_id: Mapped[UUID | None] = mapped_column(ForeignKey("content_cases.id"))
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_topic_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    expanded_topic_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    scope_graph_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    items_json: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    harvest_method: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "btrim(locale) <> ''",
            name="ck_knowledge_harvests_locale_required",
        ),
        CheckConstraint(
            "btrim(created_by) <> ''",
            name="ck_knowledge_harvests_created_by_required",
        ),
        CheckConstraint(
            "harvest_method = 'approved_candidate_topic_scope_v1'",
            name="ck_knowledge_harvests_method",
        ),
        CheckConstraint(
            "snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_harvests_hash",
        ),
        CheckConstraint(
            "json_array_length(requested_topic_ids_json) > 0",
            name="ck_knowledge_harvests_requested_topics",
        ),
        CheckConstraint(
            "json_array_length(expanded_topic_ids_json) > 0",
            name="ck_knowledge_harvests_expanded_topics",
        ),
        CheckConstraint(
            "json_typeof(scope_graph_json) = 'object'",
            name="ck_knowledge_harvests_scope_graph_object",
        ),
        Index(
            "uq_knowledge_harvests_project_hash",
            "project_id",
            "snapshot_hash",
            unique=True,
        ),
        Index(
            "ix_knowledge_harvests_project_locale_time",
            "project_id",
            "locale",
            "as_of",
        ),
        Index("ix_knowledge_harvests_case", "content_case_id"),
    )


__all__ = ["KnowledgeHarvest"]
