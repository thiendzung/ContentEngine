"""Add CustomerInsight to NeedHypothesis Living Map links.

Revision ID: 20260921_0036
Revises: 20260921_0035
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_0036"
down_revision: str | None = "20260921_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_insight_need_links",
        sa.Column("customer_insight_id", sa.Uuid(), nullable=False),
        sa.Column("need_hypothesis_id", sa.Uuid(), nullable=False),
        sa.Column("relation", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "relation in ('supports','contradicts','context')",
            name="ck_customer_insight_need_links_relation",
        ),
        sa.ForeignKeyConstraint(
            ["customer_insight_id"],
            ["customer_insights.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["need_hypothesis_id"],
            ["need_hypotheses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "customer_insight_id",
            "need_hypothesis_id",
        ),
    )
    op.create_index(
        "ix_customer_insight_need_links_need",
        "customer_insight_need_links",
        ["need_hypothesis_id", "relation"],
        unique=False,
    )

    op.create_table(
        "customer_need_journey_stage_links",
        sa.Column("need_hypothesis_id", sa.Uuid(), nullable=False),
        sa.Column("stage_key", sa.String(length=64), nullable=False),
        sa.Column("linked_by", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "stage_key ~ '^[a-z0-9][a-z0-9_-]{0,63}            RETURNS trigger AS $$
            DECLARE
                insight_project uuid;
                insight_audience uuid;
                need_project uuid;
                need_audience uuid;
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'customer_insight_need_link_is_immutable';
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION
                        'customer_insight_need_link_delete_forbidden';
                END IF;

                SELECT project_id, audience_hypothesis_id
                INTO insight_project, insight_audience
                FROM customer_insights
                WHERE id = NEW.customer_insight_id;

                SELECT project_id, audience_hypothesis_id
                INTO need_project, need_audience
                FROM need_hypotheses
                WHERE id = NEW.need_hypothesis_id;

                IF insight_project IS NULL THEN
                    RAISE EXCEPTION 'customer_map_insight_not_found';
                END IF;
                IF need_project IS NULL THEN
                    RAISE EXCEPTION 'customer_map_need_not_found';
                END IF;
                IF insight_project IS DISTINCT FROM need_project THEN
                    RAISE EXCEPTION
                        'customer_map_insight_need_project_mismatch';
                END IF;
                IF insight_audience IS NOT NULL
                   AND need_audience IS NOT NULL
                   AND insight_audience IS DISTINCT FROM need_audience THEN
                    RAISE EXCEPTION
                        'customer_map_insight_need_audience_mismatch';
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
            CREATE TRIGGER customer_insight_need_links_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON customer_insight_need_links
            FOR EACH ROW
            EXECUTE FUNCTION validate_customer_insight_need_link()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_customer_need_journey_stage_link()
            RETURNS trigger AS $
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'customer_need_journey_stage_link_is_immutable';
                END IF;
                RAISE EXCEPTION
                    'customer_need_journey_stage_link_delete_forbidden';
            END;
            $ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER customer_need_journey_stage_links_guard
            BEFORE UPDATE OR DELETE
            ON customer_need_journey_stage_links
            FOR EACH ROW
            EXECUTE FUNCTION protect_customer_need_journey_stage_link()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_customer_map_need_scope()
            RETURNS trigger AS $$
            DECLARE
                audience_project uuid;
            BEGIN
                IF NEW.audience_hypothesis_id IS NOT NULL THEN
                    SELECT project_id
                    INTO audience_project
                    FROM audience_hypotheses
                    WHERE id = NEW.audience_hypothesis_id;

                    IF audience_project IS NULL THEN
                        RAISE EXCEPTION 'customer_map_need_audience_not_found';
                    END IF;
                    IF audience_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION
                            'customer_map_need_audience_project_mismatch';
                    END IF;
                END IF;

                IF TG_OP = 'UPDATE'
                   AND (
                       OLD.project_id IS DISTINCT FROM NEW.project_id
                       OR OLD.audience_hypothesis_id
                          IS DISTINCT FROM NEW.audience_hypothesis_id
                   )
                   AND (
                       EXISTS(
                           SELECT 1
                           FROM customer_insight_need_links cinl
                           WHERE cinl.need_hypothesis_id = OLD.id
                       )
                       OR EXISTS(
                           SELECT 1
                           FROM customer_need_journey_stage_links cnjsl
                           WHERE cnjsl.need_hypothesis_id = OLD.id
                       )
                   ) THEN
                    RAISE EXCEPTION
                        'customer_map_linked_need_scope_immutable';
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
            CREATE TRIGGER customer_map_need_scope_guard
            BEFORE INSERT OR UPDATE OF project_id, audience_hypothesis_id
            ON need_hypotheses
            FOR EACH ROW EXECUTE FUNCTION validate_customer_map_need_scope()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_customer_map_audience_scope()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.project_id IS DISTINCT FROM NEW.project_id
                   AND EXISTS(
                       SELECT 1
                       FROM need_hypotheses nh
                       WHERE nh.audience_hypothesis_id = OLD.id
                   ) THEN
                    RAISE EXCEPTION
                        'customer_map_audience_project_change_forbidden';
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
            CREATE TRIGGER customer_map_audience_scope_guard
            BEFORE UPDATE OF project_id ON audience_hypotheses
            FOR EACH ROW
            EXECUTE FUNCTION protect_customer_map_audience_scope()
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_need_journey_stage_links_guard "
            "ON customer_need_journey_stage_links"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS protect_customer_need_journey_stage_link()"
        )
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_map_audience_scope_guard "
            "ON audience_hypotheses"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS protect_customer_map_audience_scope()"
        )
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_map_need_scope_guard "
            "ON need_hypotheses"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS validate_customer_map_need_scope()")
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_insight_need_links_guard "
            "ON customer_insight_need_links"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS validate_customer_insight_need_link()"
        )
    )
    op.drop_index(
        "ix_customer_insight_need_links_need",
        table_name="customer_insight_need_links",
    )
    op.drop_table("customer_insight_need_links")",
            name="ck_customer_need_journey_stage_key",
        ),
        sa.ForeignKeyConstraint(
            ["need_hypothesis_id"],
            ["need_hypotheses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("need_hypothesis_id", "stage_key"),
    )
    op.create_index(
        "ix_customer_need_journey_stage",
        "customer_need_journey_stage_links",
        ["stage_key", "need_hypothesis_id"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_customer_insight_need_link()
            RETURNS trigger AS $$
            DECLARE
                insight_project uuid;
                insight_audience uuid;
                need_project uuid;
                need_audience uuid;
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'customer_insight_need_link_is_immutable';
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION
                        'customer_insight_need_link_delete_forbidden';
                END IF;

                SELECT project_id, audience_hypothesis_id
                INTO insight_project, insight_audience
                FROM customer_insights
                WHERE id = NEW.customer_insight_id;

                SELECT project_id, audience_hypothesis_id
                INTO need_project, need_audience
                FROM need_hypotheses
                WHERE id = NEW.need_hypothesis_id;

                IF insight_project IS NULL THEN
                    RAISE EXCEPTION 'customer_map_insight_not_found';
                END IF;
                IF need_project IS NULL THEN
                    RAISE EXCEPTION 'customer_map_need_not_found';
                END IF;
                IF insight_project IS DISTINCT FROM need_project THEN
                    RAISE EXCEPTION
                        'customer_map_insight_need_project_mismatch';
                END IF;
                IF insight_audience IS NOT NULL
                   AND need_audience IS NOT NULL
                   AND insight_audience IS DISTINCT FROM need_audience THEN
                    RAISE EXCEPTION
                        'customer_map_insight_need_audience_mismatch';
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
            CREATE TRIGGER customer_insight_need_links_guard
            BEFORE INSERT OR UPDATE OR DELETE
            ON customer_insight_need_links
            FOR EACH ROW
            EXECUTE FUNCTION validate_customer_insight_need_link()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_customer_map_need_scope()
            RETURNS trigger AS $$
            DECLARE
                audience_project uuid;
            BEGIN
                IF NEW.audience_hypothesis_id IS NOT NULL THEN
                    SELECT project_id
                    INTO audience_project
                    FROM audience_hypotheses
                    WHERE id = NEW.audience_hypothesis_id;

                    IF audience_project IS NULL THEN
                        RAISE EXCEPTION 'customer_map_need_audience_not_found';
                    END IF;
                    IF audience_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION
                            'customer_map_need_audience_project_mismatch';
                    END IF;
                END IF;

                IF TG_OP = 'UPDATE'
                   AND (
                       OLD.project_id IS DISTINCT FROM NEW.project_id
                       OR OLD.audience_hypothesis_id
                          IS DISTINCT FROM NEW.audience_hypothesis_id
                   )
                   AND EXISTS(
                       SELECT 1
                       FROM customer_insight_need_links cinl
                       WHERE cinl.need_hypothesis_id = OLD.id
                   ) THEN
                    RAISE EXCEPTION
                        'customer_map_linked_need_scope_immutable';
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
            CREATE TRIGGER customer_map_need_scope_guard
            BEFORE INSERT OR UPDATE OF project_id, audience_hypothesis_id
            ON need_hypotheses
            FOR EACH ROW EXECUTE FUNCTION validate_customer_map_need_scope()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_customer_map_audience_scope()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.project_id IS DISTINCT FROM NEW.project_id
                   AND EXISTS(
                       SELECT 1
                       FROM need_hypotheses nh
                       WHERE nh.audience_hypothesis_id = OLD.id
                   ) THEN
                    RAISE EXCEPTION
                        'customer_map_audience_project_change_forbidden';
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
            CREATE TRIGGER customer_map_audience_scope_guard
            BEFORE UPDATE OF project_id ON audience_hypotheses
            FOR EACH ROW
            EXECUTE FUNCTION protect_customer_map_audience_scope()
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_map_audience_scope_guard "
            "ON audience_hypotheses"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS protect_customer_map_audience_scope()"
        )
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_map_need_scope_guard "
            "ON need_hypotheses"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS validate_customer_map_need_scope()")
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_insight_need_links_guard "
            "ON customer_insight_need_links"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS validate_customer_insight_need_link()"
        )
    )
    op.drop_index(
        "ix_customer_insight_need_links_need",
        table_name="customer_insight_need_links",
    )
    op.drop_table("customer_insight_need_links")