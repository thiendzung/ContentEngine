"""CE02 closeout media and content-version lineage."""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0006"
down_revision: str | None = "20260906_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("entity_id", sa.Uuid(), sa.ForeignKey("entities.id")),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("rights_status", sa.String(32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("source_id", "content_hash", name="uq_media_asset_source_content"),
    )
    op.create_table(
        "media_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("media_asset_id", sa.Uuid(), sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column("observation_text", sa.Text(), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("confidence", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("approved_by", sa.String(200)),
        *_timestamps(),
        sa.CheckConstraint("method in ('human','model','metadata')", name="ck_media_observation_method"),
        sa.CheckConstraint("status in ('candidate','approved','rejected')", name="ck_media_observation_status"),
        sa.CheckConstraint("status <> 'approved' or approved_by is not null", name="ck_media_observation_approved_by"),
    )
    op.add_column("evidence", sa.Column("media_observation_id", sa.Uuid()))
    op.create_foreign_key("fk_evidence_media_observation", "evidence", "media_observations", ["media_observation_id"], ["id"])
    op.drop_constraint("ck_evidence_source_ref", "evidence", type_="check")
    op.create_check_constraint("ck_evidence_source_ref", "evidence", "source_document_id is not null or chunk_id is not null or media_observation_id is not null")
    op.execute(sa.text("CREATE FUNCTION validate_evidence_media_observation() RETURNS trigger AS $$ BEGIN IF NEW.media_observation_id IS NOT NULL AND NEW.relation <> 'context_only' AND NOT EXISTS (SELECT 1 FROM media_observations WHERE id = NEW.media_observation_id AND status = 'approved' AND approved_by IS NOT NULL) THEN RAISE EXCEPTION 'unapproved_media_observation_cannot_be_factual_evidence'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"))
    op.execute(sa.text("CREATE TRIGGER evidence_media_observation_guard BEFORE INSERT OR UPDATE ON evidence FOR EACH ROW EXECUTE FUNCTION validate_evidence_media_observation()"))
    op.add_column("content_versions", sa.Column("created_by_run_id", sa.Uuid()))
    op.create_foreign_key("fk_content_version_created_by_run", "content_versions", "content_runs", ["created_by_run_id"], ["id"])
    op.add_column("content_versions", sa.Column("final_artifact_id", sa.Uuid()))
    op.create_foreign_key("fk_content_version_final_artifact", "content_versions", "artifacts", ["final_artifact_id"], ["id"])
    op.execute(sa.text("CREATE FUNCTION prevent_content_version_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'content_version_is_immutable'; END; $$ LANGUAGE plpgsql"))
    op.execute(sa.text("CREATE TRIGGER content_versions_immutable BEFORE UPDATE OR DELETE ON content_versions FOR EACH ROW EXECUTE FUNCTION prevent_content_version_mutation()"))


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS evidence_media_observation_guard ON evidence")
    op.execute("DROP FUNCTION IF EXISTS validate_evidence_media_observation")
    op.execute("DROP TRIGGER IF EXISTS content_versions_immutable ON content_versions")
    op.execute("DROP FUNCTION IF EXISTS prevent_content_version_mutation")
    op.drop_constraint("fk_content_version_final_artifact", "content_versions", type_="foreignkey")
    op.drop_column("content_versions", "final_artifact_id")
    op.drop_constraint("fk_content_version_created_by_run", "content_versions", type_="foreignkey")
    op.drop_column("content_versions", "created_by_run_id")
    op.drop_constraint("ck_evidence_source_ref", "evidence", type_="check")
    op.create_check_constraint("ck_evidence_source_ref", "evidence", "source_document_id is not null or chunk_id is not null")
    op.drop_constraint("fk_evidence_media_observation", "evidence", type_="foreignkey")
    op.drop_column("evidence", "media_observation_id")
    op.drop_table("media_observations")
    op.drop_table("media_assets")
