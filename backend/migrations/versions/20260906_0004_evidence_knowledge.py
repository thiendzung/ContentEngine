"""CE02 PR-C minimum evidence and knowledge data layer."""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0004"
down_revision: str | None = "20260906_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade() -> None:
    op.create_table("sources", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("source_type", sa.String(32), nullable=False), sa.Column("title", sa.String(500)), sa.Column("publisher", sa.String(255)), sa.Column("author", sa.String(255)), sa.Column("canonical_url", sa.Text()), sa.Column("locator", sa.Text()), sa.Column("locale", sa.String(32)), sa.Column("commercial_bias", sa.String(32)), sa.Column("authority_hint", sa.String(32)), sa.Column("provenance_json", sa.JSON(), nullable=False), sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False), sa.Column("fingerprint", sa.String(128), nullable=False), *_timestamps(), sa.UniqueConstraint("project_id", "fingerprint", name="uq_source_project_fingerprint"))
    op.create_table("source_documents", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("source_id", sa.Uuid(), sa.ForeignKey("sources.id"), nullable=False), sa.Column("document_version", sa.Integer(), nullable=False), sa.Column("canonical_url", sa.Text()), sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("content_markdown", sa.Text(), nullable=False), sa.Column("metadata_json", sa.JSON(), nullable=False), sa.Column("reader", sa.String(64)), sa.Column("provider", sa.String(64)), sa.Column("supersedes_id", sa.Uuid(), sa.ForeignKey("source_documents.id")), *_timestamps(), sa.UniqueConstraint("source_id", "document_version", name="uq_source_document_version"), sa.UniqueConstraint("source_id", "content_hash", name="uq_source_document_content"))
    op.create_index("ix_source_documents_source", "source_documents", ["source_id"])
    op.create_table("knowledge_chunks", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("source_document_id", sa.Uuid(), sa.ForeignKey("source_documents.id"), nullable=False), sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("token_estimate", sa.Integer()), sa.Column("fingerprint", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("metadata_json", sa.JSON(), nullable=False), *_timestamps(), sa.UniqueConstraint("source_document_id", "ordinal", name="uq_knowledge_chunk_position"), sa.UniqueConstraint("source_document_id", "fingerprint", name="uq_knowledge_chunk_fingerprint"))
    op.create_table("entities", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("entity_type", sa.String(32), nullable=False), sa.Column("canonical_key", sa.String(255), nullable=False), sa.Column("canonical_name", sa.String(500), nullable=False), sa.Column("aliases_json", sa.JSON(), nullable=False), sa.Column("external_refs_json", sa.JSON(), nullable=False), *_timestamps(), sa.UniqueConstraint("project_id", "canonical_key", name="uq_entity_project_key"))
    op.create_table("claims", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("subject_entity_id", sa.Uuid(), sa.ForeignKey("entities.id")), sa.Column("statement", sa.Text(), nullable=False), sa.Column("claim_type", sa.String(32), nullable=False), sa.Column("importance", sa.String(16), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("confidence", sa.String(32)), sa.Column("entity_refs_json", sa.JSON(), nullable=False), *_timestamps(), sa.CheckConstraint("importance in ('low','normal','high','critical')", name="ck_claim_importance"))
    op.create_table("evidence", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("claim_id", sa.Uuid(), sa.ForeignKey("claims.id"), nullable=False), sa.Column("source_document_id", sa.Uuid(), sa.ForeignKey("source_documents.id")), sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("knowledge_chunks.id")), sa.Column("locator", sa.Text(), nullable=False), sa.Column("excerpt", sa.Text(), nullable=False), sa.Column("relation", sa.String(16), nullable=False), sa.Column("authority_level", sa.String(32)), sa.Column("quality_metadata_json", sa.JSON(), nullable=False), sa.Column("provenance_json", sa.JSON(), nullable=False), sa.Column("verified_at", sa.DateTime(timezone=True)), *_timestamps(), sa.CheckConstraint("relation in ('supports','contradicts','qualifies','context_only')", name="ck_evidence_relation"), sa.CheckConstraint("source_document_id is not null or chunk_id is not null", name="ck_evidence_source_ref"))
    op.create_table("evidence_sets", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("content_case_id", sa.Uuid(), sa.ForeignKey("content_cases.id")), sa.Column("version", sa.Integer(), nullable=False), sa.Column("evidence_ids_json", sa.JSON(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("locked_at", sa.DateTime(timezone=True)), sa.Column("locked_by", sa.String(200)), *_timestamps(), sa.UniqueConstraint("project_id", "content_case_id", "version", name="uq_evidence_set_version"), sa.CheckConstraint("status in ('draft','locked')", name="ck_evidence_set_status"), sa.CheckConstraint("status <> 'locked' or locked_at is not null", name="ck_evidence_set_locked_at"), sa.CheckConstraint("version > 0", name="ck_evidence_set_version_positive"))
    op.create_table("originality_packs", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("content_case_id", sa.Uuid(), sa.ForeignKey("content_cases.id"), nullable=False), sa.Column("item_refs_json", sa.JSON(), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("approved_at", sa.DateTime(timezone=True)), *_timestamps(), sa.CheckConstraint("status in ('draft','approved','retired')", name="ck_originality_pack_status"))
    op.create_table("knowledge_candidates", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("locale", sa.String(32)), sa.Column("statement", sa.Text(), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("source_refs_json", sa.JSON(), nullable=False), sa.Column("provenance_json", sa.JSON(), nullable=False), sa.Column("entity_refs_json", sa.JSON(), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("reviewer", sa.String(200)), sa.Column("review_reason", sa.Text()), *_timestamps(), sa.CheckConstraint("status in ('RAW','CANDIDATE','APPROVED','REJECTED','STALE')", name="ck_knowledge_candidate_status"))
    op.execute(sa.text("CREATE FUNCTION prevent_locked_evidence_set_mutation() RETURNS trigger AS $$ BEGIN IF OLD.status = 'locked' THEN RAISE EXCEPTION 'locked_evidence_set_is_immutable'; END IF; IF TG_OP = 'DELETE' THEN RETURN OLD; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"))
    op.execute(sa.text("CREATE TRIGGER evidence_sets_immutable_when_locked BEFORE UPDATE OR DELETE ON evidence_sets FOR EACH ROW EXECUTE FUNCTION prevent_locked_evidence_set_mutation()"))


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS evidence_sets_immutable_when_locked ON evidence_sets")
    op.execute("DROP FUNCTION IF EXISTS prevent_locked_evidence_set_mutation")
    op.drop_table("knowledge_candidates")
    op.drop_table("originality_packs")
    op.drop_table("evidence_sets")
    op.drop_table("evidence")
    op.drop_table("claims")
    op.drop_table("entities")
    op.drop_index("ix_source_documents_source", table_name="source_documents")
    op.drop_table("knowledge_chunks")
    op.drop_table("source_documents")
    op.drop_table("sources")
