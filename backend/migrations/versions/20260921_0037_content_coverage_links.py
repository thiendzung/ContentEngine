"""Add Content Coverage supporting-need and journey links.

Revision ID: 20260921_0037
Revises: 20260921_0036
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_0037"
down_revision: str | None = "20260921_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_case_supporting_needs",
        sa.Column("content_case_id", sa.Uuid(), nullable=False),
        sa.Column("need_hypothesis_id", sa.Uuid(), nullable=False),
        sa.Column("linked_by", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(linked_by)) > 0",
            name="ck_content_case_supporting_need_actor",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) > 0",
            name="ck_content_case_supporting_need_reason",
        ),
        sa.ForeignKeyConstraint(
            ["content_case_id"],
            ["content_cases.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["need_hypothesis_id"],
            ["need_hypotheses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "content_case_id",
            "need_hypothesis_id",
        ),
    )
    op.create_index(
        "ix_content_case_supporting_needs_need",
        "content_case_supporting_needs",
        ["need_hypothesis_id", "content_case_id"],
        unique=False,
    )

    op.create_table(
        "content_item_journey_stages",
        sa.Column("content_item_id", sa.Uuid(), nullable=False),
        sa.Column("stage_key", sa.String(length=64), nullable=False),
        sa.Column("linked_by", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "stage_key ~ '^[a-z0-9][a-z0-9_-]{0,63}$'",
            name="ck_content_item_journey_stage_key",
        ),
        sa.CheckConstraint(
            "length(btrim(linked_by)) > 0",
            name="ck_content_item_journey_stage_actor",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) > 0",
            name="ck_content_item_journey_stage_reason",
        ),
        sa.ForeignKeyConstraint(
            ["content_item_id"],
            ["content_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("content_item_id", "stage_key"),
    )
    op.create_index(
        "ix_content_item_journey_stage",
        "content_item_journey_stages",
        ["stage_key", "content_item_id"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_content_case_supporting_need_link()
            RETURNS trigger AS $$
            DECLARE
                case_project uuid;
                case_audience uuid;
                primary_need uuid;
                need_project uuid;
                need_audience uuid;
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'content_case_supporting_need_is_immutable';
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION
                        'content_case_supporting_need_delete_forbidden';
                END IF;

                SELECT project_id, audience_hypothesis_id, need_hypothesis_id
                INTO case_project, case_audience, primary_need
                FROM content_cases
                WHERE id = NEW.content_case_id;

                SELECT project_id, audience_hypothesis_id
                INTO need_project, need_audience
                FROM need_hypotheses
                WHERE id = NEW.need_hypothesis_id;

                IF case_project IS NULL THEN
                    RAISE EXCEPTION 'content_coverage_case_not_found';
                END IF;
                IF need_project IS NULL THEN
                    RAISE EXCEPTION 'content_coverage_need_not_found';
                END IF;
                IF NEW.need_hypothesis_id = primary_need THEN
                    RAISE EXCEPTION
                        'content_coverage_supporting_need_is_primary';
                END IF;
                IF case_project IS DISTINCT FROM need_project THEN
                    RAISE EXCEPTION
                        'content_coverage_supporting_need_project_mismatch';
                END IF;
                IF case_audience IS NOT NULL
                   AND need_audience IS NOT NULL
                   AND case_audience IS DISTINCT FROM need_audience THEN
                    RAISE EXCEPTION
                        'content_coverage_supporting_need_audience_mismatch';
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
            CREATE TRIGGER content_case_supporting_needs_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON content_case_supporting_needs
            FOR EACH ROW
            EXECUTE FUNCTION validate_content_case_supporting_need_link()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_content_item_journey_stage_link()
            RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'content_item_journey_stage_is_immutable';
                END IF;
                RAISE EXCEPTION
                    'content_item_journey_stage_delete_forbidden';
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER content_item_journey_stages_guard
            BEFORE UPDATE OR DELETE
            ON content_item_journey_stages
            FOR EACH ROW
            EXECUTE FUNCTION protect_content_item_journey_stage_link()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_content_coverage_case_scope()
            RETURNS trigger AS $$
            DECLARE
                need_project uuid;
                need_audience uuid;
            BEGIN
                IF TG_OP = 'UPDATE'
                   AND OLD.need_hypothesis_id
                       IS DISTINCT FROM NEW.need_hypothesis_id THEN
                    RAISE EXCEPTION
                        'content_coverage_primary_need_immutable';
                END IF;

                IF TG_OP = 'UPDATE'
                   AND (
                       OLD.project_id IS DISTINCT FROM NEW.project_id
                       OR OLD.audience_hypothesis_id
                          IS DISTINCT FROM NEW.audience_hypothesis_id
                   )
                   AND EXISTS(
                       SELECT 1
                       FROM content_case_supporting_needs ccsn
                       WHERE ccsn.content_case_id = OLD.id
                   ) THEN
                    RAISE EXCEPTION
                        'content_coverage_linked_case_scope_immutable';
                END IF;

                SELECT project_id, audience_hypothesis_id
                INTO need_project, need_audience
                FROM need_hypotheses
                WHERE id = NEW.need_hypothesis_id;

                IF need_project IS NULL THEN
                    RAISE EXCEPTION 'content_coverage_primary_need_not_found';
                END IF;
                IF need_project IS DISTINCT FROM NEW.project_id THEN
                    RAISE EXCEPTION
                        'content_coverage_primary_need_project_mismatch';
                END IF;
                IF NEW.audience_hypothesis_id IS NOT NULL
                   AND need_audience IS NOT NULL
                   AND NEW.audience_hypothesis_id
                       IS DISTINCT FROM need_audience THEN
                    RAISE EXCEPTION
                        'content_coverage_primary_need_audience_mismatch';
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
            CREATE TRIGGER content_coverage_case_scope_guard
            BEFORE INSERT OR UPDATE OF
                project_id, audience_hypothesis_id, need_hypothesis_id
            ON content_cases
            FOR EACH ROW
            EXECUTE FUNCTION validate_content_coverage_case_scope()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_content_coverage_need_scope()
            RETURNS trigger AS $$
            BEGIN
                IF (
                    OLD.project_id IS DISTINCT FROM NEW.project_id
                    OR OLD.audience_hypothesis_id
                       IS DISTINCT FROM NEW.audience_hypothesis_id
                   )
                   AND (
                       EXISTS(
                           SELECT 1
                           FROM content_cases cc
                           WHERE cc.need_hypothesis_id = OLD.id
                       )
                       OR EXISTS(
                           SELECT 1
                           FROM content_case_supporting_needs ccsn
                           WHERE ccsn.need_hypothesis_id = OLD.id
                       )
                   ) THEN
                    RAISE EXCEPTION
                        'content_coverage_linked_need_scope_immutable';
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
            CREATE TRIGGER zz_content_coverage_need_scope_guard
            BEFORE UPDATE OF project_id, audience_hypothesis_id
            ON need_hypotheses
            FOR EACH ROW
            EXECUTE FUNCTION protect_content_coverage_need_scope()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_content_coverage_item_scope()
            RETURNS trigger AS $$
            DECLARE
                case_project uuid;
                variant_case uuid;
            BEGIN
                IF TG_OP = 'UPDATE'
                   AND (
                       OLD.project_id IS DISTINCT FROM NEW.project_id
                       OR OLD.content_case_id IS DISTINCT FROM NEW.content_case_id
                       OR OLD.locale_variant_id
                          IS DISTINCT FROM NEW.locale_variant_id
                   )
                   AND EXISTS(
                       SELECT 1
                       FROM content_item_journey_stages cijs
                       WHERE cijs.content_item_id = OLD.id
                   ) THEN
                    RAISE EXCEPTION
                        'content_coverage_linked_item_scope_immutable';
                END IF;

                SELECT project_id
                INTO case_project
                FROM content_cases
                WHERE id = NEW.content_case_id;

                SELECT content_case_id
                INTO variant_case
                FROM locale_variants
                WHERE id = NEW.locale_variant_id;

                IF case_project IS NULL THEN
                    RAISE EXCEPTION 'content_coverage_item_case_not_found';
                END IF;
                IF variant_case IS NULL THEN
                    RAISE EXCEPTION 'content_coverage_item_variant_not_found';
                END IF;
                IF NEW.project_id IS DISTINCT FROM case_project THEN
                    RAISE EXCEPTION
                        'content_coverage_item_project_mismatch';
                END IF;
                IF NEW.content_case_id IS DISTINCT FROM variant_case THEN
                    RAISE EXCEPTION
                        'content_coverage_item_variant_case_mismatch';
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
            CREATE TRIGGER content_coverage_item_scope_guard
            BEFORE INSERT OR UPDATE OF
                project_id, content_case_id, locale_variant_id
            ON content_items
            FOR EACH ROW
            EXECUTE FUNCTION validate_content_coverage_item_scope()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_content_coverage_audience_scope()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.project_id IS DISTINCT FROM NEW.project_id
                   AND EXISTS(
                       SELECT 1
                       FROM content_cases cc
                       WHERE cc.audience_hypothesis_id = OLD.id
                   ) THEN
                    RAISE EXCEPTION
                        'content_coverage_audience_project_change_forbidden';
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
            CREATE TRIGGER zz_content_coverage_audience_scope_guard
            BEFORE UPDATE OF project_id ON audience_hypotheses
            FOR EACH ROW
            EXECUTE FUNCTION protect_content_coverage_audience_scope()
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS zz_content_coverage_audience_scope_guard "
            "ON audience_hypotheses"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS protect_content_coverage_audience_scope()"
        )
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS content_coverage_item_scope_guard "
            "ON content_items"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS validate_content_coverage_item_scope()")
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS zz_content_coverage_need_scope_guard "
            "ON need_hypotheses"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS protect_content_coverage_need_scope()")
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS content_coverage_case_scope_guard "
            "ON content_cases"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS validate_content_coverage_case_scope()")
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS content_item_journey_stages_guard "
            "ON content_item_journey_stages"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS protect_content_item_journey_stage_link()"
        )
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS content_case_supporting_needs_guard "
            "ON content_case_supporting_needs"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS validate_content_case_supporting_need_link()"
        )
    )
    op.drop_index(
        "ix_content_item_journey_stage",
        table_name="content_item_journey_stages",
    )
    op.drop_table("content_item_journey_stages")
    op.drop_index(
        "ix_content_case_supporting_needs_need",
        table_name="content_case_supporting_needs",
    )
    op.drop_table("content_case_supporting_needs")
