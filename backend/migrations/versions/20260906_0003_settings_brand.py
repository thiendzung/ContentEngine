"""CE02 PR-B settings, registry, DNA and calibration storage."""
# ruff: noqa: E501

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0003"
down_revision: str | None = "20260906_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade() -> None:
    op.create_table("settings_versions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id")), sa.Column("scope_type", sa.String(32), nullable=False), sa.Column("scope_key", sa.String(100), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("settings_json", sa.JSON(), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("change_reason", sa.Text(), nullable=False), sa.Column("approved_by", sa.String(200)), *_timestamps(), sa.UniqueConstraint("project_id", "scope_type", "scope_key", "version", name="uq_settings_version"), sa.CheckConstraint("scope_type in ('system','project','content_type','locale')", name="ck_settings_scope"), sa.CheckConstraint("status in ('draft','active','retired')", name="ck_settings_status"), sa.CheckConstraint("version > 0", name="ck_settings_version_positive"))
    op.create_table("settings_snapshots", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("resolved_settings_json", sa.JSON(), nullable=False), sa.Column("source_version_refs_json", sa.JSON(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False), *_timestamps())
    op.create_table("prompt_definitions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("prompt_key", sa.String(100), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("purpose", sa.Text(), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("input_contract_json", sa.JSON(), nullable=False), sa.Column("output_schema_json", sa.JSON(), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("change_reason", sa.Text(), nullable=False), sa.Column("approved_by", sa.String(200)), *_timestamps(), sa.UniqueConstraint("prompt_key", "version", name="uq_prompt_definition_version"), sa.CheckConstraint("status in ('draft','active','retired')", name="ck_prompt_status"), sa.CheckConstraint("version > 0", name="ck_prompt_version_positive"))
    op.create_table("recipe_definitions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("recipe_key", sa.String(100), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("selector_json", sa.JSON(), nullable=False), sa.Column("recipe_json", sa.JSON(), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("approved_by", sa.String(200)), *_timestamps(), sa.UniqueConstraint("recipe_key", "version", name="uq_recipe_definition_version"), sa.CheckConstraint("status in ('draft','active','retired')", name="ck_recipe_status"), sa.CheckConstraint("version > 0", name="ck_recipe_version_positive"))
    op.create_table("calibration_examples", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False), sa.Column("locale", sa.String(32), nullable=False), sa.Column("content_type", sa.String(32)), sa.Column("intent", sa.String(64)), sa.Column("example_type", sa.String(32), nullable=False), sa.Column("polarity", sa.String(16), nullable=False), sa.Column("content_text", sa.Text(), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("approved_by", sa.String(200)), *_timestamps(), sa.CheckConstraint("polarity in ('positive','negative')", name="ck_calibration_polarity"), sa.CheckConstraint("status in ('candidate','approved','retired')", name="ck_calibration_status"))
    op.execute(sa.text("CREATE FUNCTION prevent_settings_snapshot_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'settings_snapshots_are_immutable'; END; $$ LANGUAGE plpgsql"))
    op.execute(sa.text("CREATE TRIGGER settings_snapshots_immutable BEFORE UPDATE OR DELETE ON settings_snapshots FOR EACH ROW EXECUTE FUNCTION prevent_settings_snapshot_mutation()"))

    now = datetime.now(UTC).replace(tzinfo=None)
    project_id = "00000000-0000-0000-0000-000000000001"
    projects = sa.table("projects", sa.column("id", sa.Uuid()), sa.column("slug", sa.String()), sa.column("name", sa.String()), sa.column("status", sa.String()), sa.column("default_locale", sa.String()), sa.column("created_at", sa.DateTime()), sa.column("updated_at", sa.DateTime()))
    op.bulk_insert(projects, [{"id": project_id, "slug": "motgu", "name": "MOTGU", "status": "active", "default_locale": "vi-VN", "created_at": now, "updated_at": now}])
    settings = sa.table("settings_versions", sa.column("id", sa.Uuid()), sa.column("project_id", sa.Uuid()), sa.column("scope_type", sa.String()), sa.column("scope_key", sa.String()), sa.column("version", sa.Integer()), sa.column("settings_json", sa.JSON()), sa.column("status", sa.String()), sa.column("change_reason", sa.Text()), sa.column("approved_by", sa.String()), sa.column("created_at", sa.DateTime()), sa.column("updated_at", sa.DateTime()))
    brand = {"identity": {"category": "artist house", "positioning": "A warm, evidence-first artist house in Hanoi.", "promise": "Make art easier to approach without flattening its meaning."}, "voice": {"calm": "high", "intimate": "high", "poetic": "medium", "commercial": "low", "academic": "low"}, "boundaries": {"avoid": ["fake scarcity", "invented artist intention", "inflated luxury language", "generic AI cliches"]}, "proof_preferences": {"prefer": ["first-party facts", "artist quotes with provenance", "artwork-specific observation", "studio/process evidence"]}}
    def language(locale: str, audience_context: str) -> dict[str, object]:
        return {"language_dna": {"locale": locale, "audience_context": audience_context, "vocabulary": {"complexity": "simple_to_moderate", "preferred_terms": [], "banned_phrases": []}, "rhythm": {"sentence_length": "varied", "paragraph_density": "light"}, "sensory_language": {"enabled": True, "intensity": "moderate"}, "rhetorical_questions": {"frequency": "low"}, "metaphor": {"frequency": "low_to_moderate", "must_be_grounded": True}, "direct_answer": {"preferred": True}, "cta": {"tone": "invitational", "pressure": "low"}}}
    op.bulk_insert(settings, [{"id": "00000000-0000-0000-0000-000000000011", "project_id": project_id, "scope_type": "project", "scope_key": "motgu", "version": 1, "settings_json": {"brand": brand, "project": {"canonical_domain": "motgu.com", "supported_locales": ["vi-VN", "en"]}}, "status": "active", "change_reason": "CE02 default MOTGU brand DNA", "approved_by": "seed", "created_at": now, "updated_at": now}, {"id": "00000000-0000-0000-0000-000000000012", "project_id": project_id, "scope_type": "locale", "scope_key": "vi-VN", "version": 1, "settings_json": language("vi-VN", "người Việt quan tâm nghệ thuật và trải nghiệm tại Hà Nội"), "status": "active", "change_reason": "CE02 Vietnamese language DNA", "approved_by": "seed", "created_at": now, "updated_at": now}, {"id": "00000000-0000-0000-0000-000000000013", "project_id": project_id, "scope_type": "locale", "scope_key": "en", "version": 1, "settings_json": language("en", "international traveller and art-curious reader"), "status": "active", "change_reason": "CE02 English language DNA", "approved_by": "seed", "created_at": now, "updated_at": now}])
    prompts = sa.table("prompt_definitions", sa.column("id", sa.Uuid()), sa.column("prompt_key", sa.String()), sa.column("version", sa.Integer()), sa.column("purpose", sa.Text()), sa.column("body", sa.Text()), sa.column("input_contract_json", sa.JSON()), sa.column("output_schema_json", sa.JSON()), sa.column("status", sa.String()), sa.column("change_reason", sa.Text()), sa.column("approved_by", sa.String()), sa.column("created_at", sa.DateTime()), sa.column("updated_at", sa.DateTime()))
    op.bulk_insert(prompts, [{"id": "00000000-0000-0000-0000-000000000021", "prompt_key": "journal_draft", "version": 1, "purpose": "Draft a reviewed Journal candidate from approved context.", "body": "Use only the supplied brief, evidence and approved MOTGU context.", "input_contract_json": {"required": ["brief", "evidence", "brand_dna", "language_dna"]}, "output_schema_json": {"type": "object", "required": ["title", "body"]}, "status": "active", "change_reason": "CE02 minimum registry seed", "approved_by": "seed", "created_at": now, "updated_at": now}])
    recipes = sa.table("recipe_definitions", sa.column("id", sa.Uuid()), sa.column("recipe_key", sa.String()), sa.column("version", sa.Integer()), sa.column("selector_json", sa.JSON()), sa.column("recipe_json", sa.JSON()), sa.column("status", sa.String()), sa.column("approved_by", sa.String()), sa.column("created_at", sa.DateTime()), sa.column("updated_at", sa.DateTime()))
    op.bulk_insert(recipes, [{"id": "00000000-0000-0000-0000-000000000031", "recipe_key": "journal_direct_answer_story", "version": 1, "selector_json": {"content_type": "journal", "intent": ["learn", "understand"]}, "recipe_json": {"steps": ["answer_first", "context", "concrete_example", "MOTGU_specific_value", "next_useful_step"]}, "status": "active", "approved_by": "seed", "created_at": now, "updated_at": now}])


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS settings_snapshots_immutable ON settings_snapshots")
    op.execute("DROP FUNCTION IF EXISTS prevent_settings_snapshot_mutation")
    op.drop_table("calibration_examples")
    op.drop_table("recipe_definitions")
    op.drop_table("prompt_definitions")
    op.drop_table("settings_snapshots")
    op.drop_table("settings_versions")
