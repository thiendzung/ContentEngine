from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> UUID:
    return uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    publisher: Mapped[str | None] = mapped_column(String(255))
    author: Mapped[str | None] = mapped_column(String(255))
    canonical_url: Mapped[str | None] = mapped_column(Text)
    locator: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str | None] = mapped_column(String(32))
    commercial_bias: Mapped[str | None] = mapped_column(String(32))
    authority_hint: Mapped[str | None] = mapped_column(String(32))
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "fingerprint", name="uq_source_project_fingerprint"),
    )


class SourceDocument(TimestampMixin, Base):
    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    document_version: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    reader: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(64))
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_documents.id"))

    __table_args__ = (
        UniqueConstraint("source_id", "document_version", name="uq_source_document_version"),
        UniqueConstraint("source_id", "content_hash", name="uq_source_document_content"),
        Index("ix_source_documents_source", "source_id"),
    )


class KnowledgeChunk(TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    source_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_documents.id"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int | None] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_document_id", "ordinal", name="uq_knowledge_chunk_position"),
        UniqueConstraint(
            "source_document_id", "fingerprint", name="uq_knowledge_chunk_fingerprint"
        ),
    )


class Entity(TimestampMixin, Base):
    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_key: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(500), nullable=False)
    aliases_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    external_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "canonical_key", name="uq_entity_project_key"),
    )


class Claim(TimestampMixin, Base):
    __tablename__ = "claims"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    subject_entity_id: Mapped[UUID | None] = mapped_column(ForeignKey("entities.id"))
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    importance: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unverified")
    confidence: Mapped[str | None] = mapped_column(String(32))
    entity_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "importance in ('low','normal','high','critical')", name="ck_claim_importance"
        ),
    )


class Evidence(TimestampMixin, Base):
    __tablename__ = "evidence"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("claims.id"), nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_documents.id"))
    chunk_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_chunks.id"))
    locator: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    relation: Mapped[str] = mapped_column(String(16), nullable=False)
    authority_level: Mapped[str | None] = mapped_column(String(32))
    quality_metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "relation in ('supports','contradicts','qualifies','context_only')",
            name="ck_evidence_relation",
        ),
        CheckConstraint(
            "source_document_id is not null or chunk_id is not null", name="ck_evidence_source_ref"
        ),
    )


class EvidenceSet(TimestampMixin, Base):
    __tablename__ = "evidence_sets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    content_case_id: Mapped[UUID | None] = mapped_column(ForeignKey("content_cases.id"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint(
            "project_id", "content_case_id", "version", name="uq_evidence_set_version"
        ),
        CheckConstraint("status in ('draft','locked')", name="ck_evidence_set_status"),
        CheckConstraint(
            "status <> 'locked' or locked_at is not null",
            name="ck_evidence_set_locked_at",
        ),
        CheckConstraint("version > 0", name="ck_evidence_set_version_positive"),
    )


class OriginalityPack(TimestampMixin, Base):
    __tablename__ = "originality_packs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    content_case_id: Mapped[UUID] = mapped_column(ForeignKey("content_cases.id"), nullable=False)
    item_refs_json: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status in ('draft','approved','retired')", name="ck_originality_pack_status"
        ),
    )


class KnowledgeCandidate(TimestampMixin, Base):
    __tablename__ = "knowledge_candidates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    locale: Mapped[str | None] = mapped_column(String(32))
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    entity_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RAW")
    reviewer: Mapped[str | None] = mapped_column(String(200))
    review_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status in ('RAW','CANDIDATE','APPROVED','REJECTED','STALE')",
            name="ck_knowledge_candidate_status",
        ),
    )
