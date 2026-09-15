"""Add immutable deterministic knowledge harvest snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0030"
down_revision: str | None = "20260915_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_harvest_guard() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_knowledge_harvest() RETURNS trigger AS $$
            DECLARE
                case_project uuid;
                raw_topic_id text;
                topic_uuid uuid;
                topic_project uuid;
                topic_status text;
                item json;
                candidate_uuid uuid;
                candidate_project uuid;
                candidate_status text;
                candidate_locale text;
            BEGIN
                IF TG_OP <> 'INSERT' THEN
                    RAISE EXCEPTION 'knowledge_harvest_is_immutable';
                END IF;

                IF NEW.content_case_id IS NOT NULL THEN
                    SELECT project_id INTO case_project
                    FROM content_cases WHERE id = NEW.content_case_id;
                    IF case_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION 'knowledge_harvest_case_project_mismatch';
                    END IF;
                END IF;

                FOR raw_topic_id IN
                    SELECT value FROM json_array_elements_text(NEW.requested_topic_ids_json)
                LOOP
                    BEGIN
                        topic_uuid := raw_topic_id::uuid;
                    EXCEPTION WHEN invalid_text_representation THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_id_invalid';
                    END;
                    SELECT project_id, status INTO topic_project, topic_status
                    FROM topic_nodes WHERE id = topic_uuid;
                    IF topic_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_project_mismatch';
                    END IF;
                    IF topic_status <> 'active' THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_not_active';
                    END IF;
                END LOOP;

                FOR raw_topic_id IN
                    SELECT value FROM json_array_elements_text(NEW.expanded_topic_ids_json)
                LOOP
                    BEGIN
                        topic_uuid := raw_topic_id::uuid;
                    EXCEPTION WHEN invalid_text_representation THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_id_invalid';
                    END;
                    SELECT project_id, status INTO topic_project, topic_status
                    FROM topic_nodes WHERE id = topic_uuid;
                    IF topic_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_project_mismatch';
                    END IF;
                    IF topic_status <> 'active' THEN
                        RAISE EXCEPTION 'knowledge_harvest_topic_not_active';
                    END IF;
                END LOOP;

                FOR item IN SELECT value FROM json_array_elements(NEW.items_json)
                LOOP
                    IF item->>'candidate_id' IS NULL THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_id_required';
                    END IF;
                    BEGIN
                        candidate_uuid := (item->>'candidate_id')::uuid;
                    EXCEPTION WHEN invalid_text_representation THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_id_invalid';
                    END;
                    SELECT project_id, status, locale
                    INTO candidate_project, candidate_status, candidate_locale
                    FROM knowledge_candidates WHERE id = candidate_uuid;
                    IF candidate_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_project_mismatch';
                    END IF;
                    IF candidate_status <> 'APPROVED' THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_not_approved';
                    END IF;
                    IF candidate_locale IS DISTINCT FROM NEW.locale THEN
                        RAISE EXCEPTION 'knowledge_harvest_candidate_locale_mismatch';
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
            CREATE TRIGGER knowledge_harvests_guard
            BEFORE INSERT OR UPDATE OR DELETE ON knowledge_harvests
            FOR EACH ROW EXECUTE FUNCTION validate_knowledge_harvest()
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "knowledge_harvests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("content_case_id", sa.Uuid(), nullable=True),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_topic_ids_json", sa.JSON(), nullable=False),
        sa.Column("expanded_topic_ids_json", sa.JSON(), nullable=False),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("harvest_method", sa.String(length=64), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(locale) <> ''",
            name="ck_knowledge_harvests_locale_required",
        ),
        sa.CheckConstraint(
            "harvest_method = 'approved_candidate_topic_scope_v1'",
            name="ck_knowledge_harvests_method",
        ),
        sa.CheckConstraint(
            "snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_harvests_hash",
        ),
        sa.CheckConstraint(
            "json_array_length(requested_topic_ids_json) > 0",
            name="ck_knowledge_harvests_requested_topics",
        ),
        sa.CheckConstraint(
            "json_array_length(expanded_topic_ids_json) > 0",
            name="ck_knowledge_harvests_expanded_topics",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["content_case_id"], ["content_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_knowledge_harvests_project_hash",
        "knowledge_harvests",
        ["project_id", "snapshot_hash"],
        unique=True,
    )
    op.create_index(
        "ix_knowledge_harvests_project_locale_time",
        "knowledge_harvests",
        ["project_id", "locale", "as_of"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_harvests_case",
        "knowledge_harvests",
        ["content_case_id"],
        unique=False,
    )
    _create_harvest_guard()


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS knowledge_harvests_guard ON knowledge_harvests"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_knowledge_harvest()"))
    op.drop_index("ix_knowledge_harvests_case", table_name="knowledge_harvests")
    op.drop_index(
        "ix_knowledge_harvests_project_locale_time",
        table_name="knowledge_harvests",
    )
    op.drop_index(
        "uq_knowledge_harvests_project_hash",
        table_name="knowledge_harvests",
    )
    op.drop_table("knowledge_harvests")
