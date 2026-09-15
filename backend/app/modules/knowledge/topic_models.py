from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.content_engine.models import TimestampMixin, new_id


class TopicNode(TimestampMixin, Base):
    __tablename__ = "topic_nodes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    canonical_key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    node_type: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            "node_type in ('pillar','cluster','topic','subtopic')",
            name="ck_topic_nodes_type",
        ),
        CheckConstraint(
            "status in ('active','retired')",
            name="ck_topic_nodes_status",
        ),
        Index(
            "uq_topic_nodes_project_key",
            "project_id",
            "canonical_key",
            unique=True,
        ),
        Index("ix_topic_nodes_project_type", "project_id", "node_type", "status"),
    )


class TopicEdge(TimestampMixin, Base):
    __tablename__ = "topic_edges"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    parent_topic_id: Mapped[UUID] = mapped_column(ForeignKey("topic_nodes.id"), nullable=False)
    child_topic_id: Mapped[UUID] = mapped_column(ForeignKey("topic_nodes.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            "relation_type in ('contains','related')",
            name="ck_topic_edges_relation_type",
        ),
        CheckConstraint(
            "parent_topic_id <> child_topic_id",
            name="ck_topic_edges_not_self",
        ),
        Index(
            "uq_topic_edges_exact",
            "project_id",
            "parent_topic_id",
            "child_topic_id",
            "relation_type",
            unique=True,
        ),
        Index("ix_topic_edges_parent", "project_id", "parent_topic_id", "relation_type"),
        Index("ix_topic_edges_child", "project_id", "child_topic_id", "relation_type"),
    )


class KnowledgeTopicLink(TimestampMixin, Base):
    __tablename__ = "knowledge_topic_links"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    topic_id: Mapped[UUID] = mapped_column(ForeignKey("topic_nodes.id"), nullable=False)
    claim_id: Mapped[UUID | None] = mapped_column(ForeignKey("claims.id"))
    knowledge_candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_candidates.id")
    )
    chunk_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_chunks.id"))
    entity_id: Mapped[UUID | None] = mapped_column(ForeignKey("entities.id"))
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    link_method: Mapped[str] = mapped_column(String(32), nullable=False)
    linked_by: Mapped[str] = mapped_column(String(200), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN claim_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN knowledge_candidate_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN chunk_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN entity_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_knowledge_topic_links_exactly_one_target",
        ),
        CheckConstraint(
            "relevance_score >= 0 and relevance_score <= 1000",
            name="ck_knowledge_topic_links_relevance",
        ),
        CheckConstraint(
            "link_method in ('manual','deterministic','model')",
            name="ck_knowledge_topic_links_method",
        ),
        Index(
            "uq_knowledge_topic_links_claim",
            "topic_id",
            "claim_id",
            unique=True,
            postgresql_where=text("claim_id IS NOT NULL"),
        ),
        Index(
            "uq_knowledge_topic_links_candidate",
            "topic_id",
            "knowledge_candidate_id",
            unique=True,
            postgresql_where=text("knowledge_candidate_id IS NOT NULL"),
        ),
        Index(
            "uq_knowledge_topic_links_chunk",
            "topic_id",
            "chunk_id",
            unique=True,
            postgresql_where=text("chunk_id IS NOT NULL"),
        ),
        Index(
            "uq_knowledge_topic_links_entity",
            "topic_id",
            "entity_id",
            unique=True,
            postgresql_where=text("entity_id IS NOT NULL"),
        ),
        Index("ix_knowledge_topic_links_project_topic", "project_id", "topic_id"),
    )
