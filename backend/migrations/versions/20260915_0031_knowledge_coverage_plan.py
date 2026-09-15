"""Add immutable deterministic knowledge coverage plans."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0031"
down_revision: str | None = "20260915_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_coverage_plan_guard() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_knowledge_coverage_plan() RETURNS trigger AS $$
            DECLARE
                harvest_project uuid;
                harvest_case uuid;
                harvest_locale text;
                harvest_hash text;
                harvest_topics json;
                lane json;
                raw_topic_id text;
                topic_uuid uuid;
            BEGIN
                IF TG_OP <> 'INSERT' THEN
                    RAISE EXCEPTION 'knowledge_coverage_plan_is_immutable';
                END IF;

                SELECT
                    kh.project_id,
                    kh.content_case_id,
                    kh.locale,
                    kh.snapshot_hash,
                    kh.expanded_topic_ids_json
                INTO
                    harvest_project,
                    harvest_case,
                    harvest_locale,
                    harvest_hash,
                    harvest_topics
                FROM knowledge_harvests AS kh
                WHERE kh.id = NEW.knowledge_harvest_id;

                IF harvest_project IS NULL THEN
                    RAISE EXCEPTION 'knowledge_coverage_plan_harvest_not_found';
                END IF;
                IF harvest_project IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION 'knowledge_coverage_plan_project_mismatch';
                END IF;
                IF harvest_case IS DISTINCT FROM NEW.content_case_id THEN
                    RAISE EXCEPTION 'knowledge_coverage_plan_case_mismatch';
                END IF;
                IF harvest_locale IS DISTINCT FROM NEW.locale THEN
                    RAISE EXCEPTION 'knowledge_coverage_plan_locale_mismatch';
                END IF;
                IF harvest_hash IS DISTINCT FROM NEW.harvest_snapshot_hash THEN
                    RAISE EXCEPTION 'knowledge_coverage_plan_harvest_hash_mismatch';
                END IF;

                IF json_array_length(NEW.lanes_json) IS DISTINCT FROM
                    json_array_length(harvest_topics) THEN
                    RAISE EXCEPTION 'knowledge_coverage_plan_lane_set_mismatch';
                END IF;
                IF (
                    SELECT count(DISTINCT value->>'topic_id')
                    FROM json_array_elements(NEW.lanes_json)
                ) IS DISTINCT FROM json_array_length(NEW.lanes_json) THEN
                    RAISE EXCEPTION 'knowledge_coverage_plan_lane_duplicate';
                END IF;
                IF NEW.lanes_json::jsonb IS DISTINCT FROM (
                    SELECT jsonb_agg(value ORDER BY value->>'topic_id')
                    FROM jsonb_array_elements(NEW.lanes_json::jsonb)
                ) THEN
                    RAISE EXCEPTION 'knowledge_coverage_plan_lanes_not_canonical';
                END IF;

                FOR lane IN SELECT value FROM json_array_elements(NEW.lanes_json)
                LOOP
                    raw_topic_id := lane->>'topic_id';
                    IF raw_topic_id IS NULL THEN
                        RAISE EXCEPTION 'knowledge_coverage_plan_lane_topic_required';
                    END IF;
                    BEGIN
                        topic_uuid := raw_topic_id::uuid;
                    EXCEPTION WHEN invalid_text_representation THEN
                        RAISE EXCEPTION 'knowledge_coverage_plan_lane_topic_invalid';
                    END;
                    IF raw_topic_id IS DISTINCT FROM topic_uuid::text THEN
                        RAISE EXCEPTION 'knowledge_coverage_plan_lane_topic_invalid';
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1
                        FROM json_array_elements_text(harvest_topics) AS topic(value)
                        WHERE topic.value = raw_topic_id
                    ) THEN
                        RAISE EXCEPTION 'knowledge_coverage_plan_lane_topic_outside_harvest';
                    END IF;
                    IF lane->>'coverage_role' NOT IN ('target', 'context') THEN
                        RAISE EXCEPTION 'knowledge_coverage_plan_lane_role_invalid';
                    END IF;
                    IF json_typeof(lane->'child_topic_ids') IS DISTINCT FROM 'array'
                       OR json_typeof(lane->'fresh_candidate_ids') IS DISTINCT FROM 'array'
                       OR json_typeof(lane->'due_candidate_ids') IS DISTINCT FROM 'array'
                       OR json_typeof(lane->'stale_candidate_ids') IS DISTINCT FROM 'array'
                       OR json_typeof(lane->'unknown_candidate_ids') IS DISTINCT FROM 'array'
                       OR json_typeof(lane->'unclassified_candidate_ids')
                           IS DISTINCT FROM 'array'
                       OR json_typeof(lane->'reuse_candidate_ids') IS DISTINCT FROM 'array'
                       OR json_typeof(lane->'research_candidate_ids') IS DISTINCT FROM 'array'
                       OR json_typeof(lane->'reason_codes') IS DISTINCT FROM 'array' THEN
                        RAISE EXCEPTION 'knowledge_coverage_plan_lane_array_invalid';
                    END IF;
                    IF json_typeof(lane->'reuse_ready') IS DISTINCT FROM 'boolean'
                       OR json_typeof(lane->'research_required') IS DISTINCT FROM 'boolean'
                       OR json_typeof(lane->'refresh_recommended') IS DISTINCT FROM 'boolean'
                       OR json_typeof(lane->'policy_required') IS DISTINCT FROM 'boolean' THEN
                        RAISE EXCEPTION 'knowledge_coverage_plan_lane_flag_invalid';
                    END IF;
                END LOOP;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER knowledge_coverage_plans_guard
            BEFORE INSERT OR UPDATE OR DELETE ON knowledge_coverage_plans
            FOR EACH ROW EXECUTE FUNCTION validate_knowledge_coverage_plan()
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "knowledge_coverage_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_harvest_id", sa.Uuid(), nullable=False),
        sa.Column("content_case_id", sa.Uuid(), nullable=True),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("harvest_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("planner_method", sa.String(length=64), nullable=False),
        sa.Column("lanes_json", sa.JSON(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(locale) <> ''",
            name="ck_knowledge_coverage_plans_locale_required",
        ),
        sa.CheckConstraint(
            "btrim(created_by) <> ''",
            name="ck_knowledge_coverage_plans_created_by_required",
        ),
        sa.CheckConstraint(
            "planner_method = 'leaf_topic_freshness_coverage_v1'",
            name="ck_knowledge_coverage_plans_method",
        ),
        sa.CheckConstraint(
            "harvest_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_coverage_plans_harvest_hash",
        ),
        sa.CheckConstraint(
            "snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_coverage_plans_hash",
        ),
        sa.CheckConstraint(
            "json_typeof(lanes_json) = 'array'",
            name="ck_knowledge_coverage_plans_lanes_array",
        ),
        sa.CheckConstraint(
            "json_array_length(lanes_json) > 0",
            name="ck_knowledge_coverage_plans_lanes_required",
        ),
        sa.CheckConstraint(
            "json_typeof(summary_json) = 'object'",
            name="ck_knowledge_coverage_plans_summary_object",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["knowledge_harvest_id"],
            ["knowledge_harvests.id"],
        ),
        sa.ForeignKeyConstraint(["content_case_id"], ["content_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_knowledge_coverage_plans_harvest_method",
        "knowledge_coverage_plans",
        ["knowledge_harvest_id", "planner_method"],
        unique=True,
    )
    op.create_index(
        "uq_knowledge_coverage_plans_project_hash",
        "knowledge_coverage_plans",
        ["project_id", "snapshot_hash"],
        unique=True,
    )
    op.create_index(
        "ix_knowledge_coverage_plans_project_locale",
        "knowledge_coverage_plans",
        ["project_id", "locale"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_coverage_plans_case",
        "knowledge_coverage_plans",
        ["content_case_id"],
        unique=False,
    )
    _create_coverage_plan_guard()


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS knowledge_coverage_plans_guard "
            "ON knowledge_coverage_plans"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_knowledge_coverage_plan()"))
    op.drop_index(
        "ix_knowledge_coverage_plans_case",
        table_name="knowledge_coverage_plans",
    )
    op.drop_index(
        "ix_knowledge_coverage_plans_project_locale",
        table_name="knowledge_coverage_plans",
    )
    op.drop_index(
        "uq_knowledge_coverage_plans_project_hash",
        table_name="knowledge_coverage_plans",
    )
    op.drop_index(
        "uq_knowledge_coverage_plans_harvest_method",
        table_name="knowledge_coverage_plans",
    )
    op.drop_table("knowledge_coverage_plans")
