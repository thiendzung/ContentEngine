"""Add immutable deterministic knowledge briefs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0032"
down_revision: str | None = "20260915_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_knowledge_brief_guard() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_knowledge_brief() RETURNS trigger AS $$
            DECLARE
                plan_project uuid;
                plan_harvest uuid;
                plan_case uuid;
                plan_locale text;
                plan_hash text;
                plan_harvest_hash text;
                harvest_project uuid;
                harvest_case uuid;
                harvest_locale text;
                harvest_hash text;
            BEGIN
                IF TG_OP <> 'INSERT' THEN
                    RAISE EXCEPTION 'knowledge_brief_is_immutable';
                END IF;

                SELECT
                    kp.project_id,
                    kp.knowledge_harvest_id,
                    kp.content_case_id,
                    kp.locale,
                    kp.snapshot_hash,
                    kp.harvest_snapshot_hash
                INTO
                    plan_project,
                    plan_harvest,
                    plan_case,
                    plan_locale,
                    plan_hash,
                    plan_harvest_hash
                FROM knowledge_coverage_plans AS kp
                WHERE kp.id = NEW.knowledge_coverage_plan_id;

                IF plan_project IS NULL THEN
                    RAISE EXCEPTION 'knowledge_brief_coverage_plan_not_found';
                END IF;
                IF plan_project IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION 'knowledge_brief_project_mismatch';
                END IF;
                IF plan_harvest IS DISTINCT FROM NEW.knowledge_harvest_id THEN
                    RAISE EXCEPTION 'knowledge_brief_harvest_mismatch';
                END IF;
                IF plan_case IS DISTINCT FROM NEW.content_case_id THEN
                    RAISE EXCEPTION 'knowledge_brief_case_mismatch';
                END IF;
                IF plan_locale IS DISTINCT FROM NEW.locale THEN
                    RAISE EXCEPTION 'knowledge_brief_locale_mismatch';
                END IF;
                IF plan_hash IS DISTINCT FROM NEW.coverage_plan_snapshot_hash THEN
                    RAISE EXCEPTION 'knowledge_brief_plan_hash_mismatch';
                END IF;
                IF plan_harvest_hash IS DISTINCT FROM NEW.harvest_snapshot_hash THEN
                    RAISE EXCEPTION 'knowledge_brief_harvest_hash_mismatch';
                END IF;

                SELECT
                    kh.project_id,
                    kh.content_case_id,
                    kh.locale,
                    kh.snapshot_hash
                INTO
                    harvest_project,
                    harvest_case,
                    harvest_locale,
                    harvest_hash
                FROM knowledge_harvests AS kh
                WHERE kh.id = NEW.knowledge_harvest_id;

                IF harvest_project IS NULL THEN
                    RAISE EXCEPTION 'knowledge_brief_harvest_not_found';
                END IF;
                IF harvest_project IS DISTINCT FROM NEW.project_id
                   OR harvest_case IS DISTINCT FROM NEW.content_case_id
                   OR harvest_locale IS DISTINCT FROM NEW.locale THEN
                    RAISE EXCEPTION 'knowledge_brief_harvest_binding_mismatch';
                END IF;
                IF harvest_hash IS DISTINCT FROM NEW.harvest_snapshot_hash THEN
                    RAISE EXCEPTION 'knowledge_brief_harvest_hash_mismatch';
                END IF;

                IF NEW.brief_json->>'brief_method' IS DISTINCT FROM NEW.brief_method
                   OR NEW.brief_json->>'project_id' IS DISTINCT FROM NEW.project_id::text
                   OR NEW.brief_json->>'knowledge_coverage_plan_id'
                       IS DISTINCT FROM NEW.knowledge_coverage_plan_id::text
                   OR NEW.brief_json->>'coverage_plan_snapshot_hash'
                       IS DISTINCT FROM NEW.coverage_plan_snapshot_hash
                   OR NEW.brief_json->>'knowledge_harvest_id'
                       IS DISTINCT FROM NEW.knowledge_harvest_id::text
                   OR NEW.brief_json->>'harvest_snapshot_hash'
                       IS DISTINCT FROM NEW.harvest_snapshot_hash
                   OR NEW.brief_json->>'locale' IS DISTINCT FROM NEW.locale THEN
                    RAISE EXCEPTION 'knowledge_brief_payload_binding_mismatch';
                END IF;

                IF NEW.content_case_id IS NULL THEN
                    IF NEW.brief_json->>'content_case_id' IS NOT NULL THEN
                        RAISE EXCEPTION 'knowledge_brief_payload_case_mismatch';
                    END IF;
                ELSIF NEW.brief_json->>'content_case_id'
                    IS DISTINCT FROM NEW.content_case_id::text THEN
                    RAISE EXCEPTION 'knowledge_brief_payload_case_mismatch';
                END IF;

                IF NEW.brief_json->>'as_of' IS NULL
                   OR json_typeof(NEW.brief_json->'requested_topic_ids')
                       IS DISTINCT FROM 'array'
                   OR json_typeof(NEW.brief_json->'expanded_topic_ids')
                       IS DISTINCT FROM 'array'
                   OR json_typeof(NEW.brief_json->'topic_contexts')
                       IS DISTINCT FROM 'array'
                   OR json_typeof(NEW.brief_json->'reusable_knowledge')
                       IS DISTINCT FROM 'array'
                   OR json_typeof(NEW.brief_json->'research_targets')
                       IS DISTINCT FROM 'array'
                   OR json_typeof(NEW.brief_json->'refresh_recommendations')
                       IS DISTINCT FROM 'array'
                   OR json_typeof(NEW.brief_json->'policy_required_targets')
                       IS DISTINCT FROM 'array'
                   OR json_typeof(NEW.brief_json->'summary')
                       IS DISTINCT FROM 'object' THEN
                    RAISE EXCEPTION 'knowledge_brief_payload_shape_invalid';
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER knowledge_briefs_guard
            BEFORE INSERT OR UPDATE OR DELETE ON knowledge_briefs
            FOR EACH ROW EXECUTE FUNCTION validate_knowledge_brief()
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "knowledge_briefs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_coverage_plan_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_harvest_id", sa.Uuid(), nullable=False),
        sa.Column("content_case_id", sa.Uuid(), nullable=True),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("coverage_plan_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("harvest_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("brief_method", sa.String(length=64), nullable=False),
        sa.Column("brief_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(locale) <> ''",
            name="ck_knowledge_briefs_locale_required",
        ),
        sa.CheckConstraint(
            "btrim(created_by) <> ''",
            name="ck_knowledge_briefs_created_by_required",
        ),
        sa.CheckConstraint(
            "brief_method = 'coverage_bound_knowledge_brief_v1'",
            name="ck_knowledge_briefs_method",
        ),
        sa.CheckConstraint(
            "coverage_plan_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_briefs_plan_hash",
        ),
        sa.CheckConstraint(
            "harvest_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_briefs_harvest_hash",
        ),
        sa.CheckConstraint(
            "snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_briefs_hash",
        ),
        sa.CheckConstraint(
            "json_typeof(brief_json) = 'object'",
            name="ck_knowledge_briefs_payload_object",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["knowledge_coverage_plan_id"],
            ["knowledge_coverage_plans.id"],
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_harvest_id"],
            ["knowledge_harvests.id"],
        ),
        sa.ForeignKeyConstraint(["content_case_id"], ["content_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_knowledge_briefs_plan_method",
        "knowledge_briefs",
        ["knowledge_coverage_plan_id", "brief_method"],
        unique=True,
    )
    op.create_index(
        "uq_knowledge_briefs_project_hash",
        "knowledge_briefs",
        ["project_id", "snapshot_hash"],
        unique=True,
    )
    op.create_index(
        "ix_knowledge_briefs_project_locale",
        "knowledge_briefs",
        ["project_id", "locale"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_briefs_case",
        "knowledge_briefs",
        ["content_case_id"],
        unique=False,
    )
    _create_knowledge_brief_guard()


def downgrade() -> None:
    op.execute(
        sa.text("DROP TRIGGER IF EXISTS knowledge_briefs_guard ON knowledge_briefs")
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_knowledge_brief()"))
    op.drop_index("ix_knowledge_briefs_case", table_name="knowledge_briefs")
    op.drop_index(
        "ix_knowledge_briefs_project_locale",
        table_name="knowledge_briefs",
    )
    op.drop_index(
        "uq_knowledge_briefs_project_hash",
        table_name="knowledge_briefs",
    )
    op.drop_index(
        "uq_knowledge_briefs_plan_method",
        table_name="knowledge_briefs",
    )
    op.drop_table("knowledge_briefs")
