"""Add CustomerInsight foundation.

Revision ID: 20260921_0035
Revises: 20260915_0034
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_0035"
down_revision: str | None = "20260915_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_customer_insight_guards() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_customer_insight() RETURNS trigger AS $$
            DECLARE
                audience_project uuid;
            BEGIN
                IF NEW.audience_hypothesis_id IS NOT NULL THEN
                    SELECT project_id
                    INTO audience_project
                    FROM audience_hypotheses
                    WHERE id = NEW.audience_hypothesis_id;

                    IF audience_project IS NULL THEN
                        RAISE EXCEPTION 'customer_insight_audience_not_found';
                    END IF;
                    IF audience_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION 'customer_insight_audience_project_mismatch';
                    END IF;
                END IF;

                IF TG_OP = 'UPDATE' THEN
                    IF OLD.project_id IS DISTINCT FROM NEW.project_id
                       OR OLD.insight_key IS DISTINCT FROM NEW.insight_key
                       OR OLD.version IS DISTINCT FROM NEW.version
                       OR OLD.insight_type IS DISTINCT FROM NEW.insight_type
                       OR OLD.statement IS DISTINCT FROM NEW.statement
                       OR OLD.audience_hypothesis_id IS DISTINCT FROM NEW.audience_hypothesis_id
                       OR OLD.situation IS DISTINCT FROM NEW.situation
                       OR OLD.alternative_explanations_json IS DISTINCT FROM NEW.alternative_explanations_json
                       OR OLD.missing_evidence_json IS DISTINCT FROM NEW.missing_evidence_json THEN
                        RAISE EXCEPTION 'customer_insight_version_content_immutable';
                    END IF;
                END IF;

                IF NEW.status IN ('SUPPORTED','REJECTED')
                   AND (
                       NEW.reviewed_by IS NULL
                       OR NEW.reviewed_at IS NULL
                       OR NEW.review_reason IS NULL
                       OR btrim(NEW.review_reason) = ''
                   ) THEN
                    RAISE EXCEPTION 'customer_insight_review_required';
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
            CREATE TRIGGER customer_insights_guard
            BEFORE INSERT OR UPDATE ON customer_insights
            FOR EACH ROW EXECUTE FUNCTION validate_customer_insight()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_customer_insight_signal() RETURNS trigger AS $$
            DECLARE
                insight_project uuid;
                signal_project uuid;
            BEGIN
                SELECT project_id INTO insight_project
                FROM customer_insights
                WHERE id = NEW.customer_insight_id;

                SELECT project_id INTO signal_project
                FROM signals
                WHERE id = NEW.signal_id;

                IF insight_project IS NULL THEN
                    RAISE EXCEPTION 'customer_insight_not_found';
                END IF;
                IF signal_project IS NULL THEN
                    RAISE EXCEPTION 'customer_insight_signal_not_found';
                END IF;
                IF insight_project IS DISTINCT FROM signal_project THEN
                    RAISE EXCEPTION 'customer_insight_signal_project_mismatch';
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
            CREATE TRIGGER customer_insight_signals_guard
            BEFORE INSERT OR UPDATE ON customer_insight_signals
            FOR EACH ROW EXECUTE FUNCTION validate_customer_insight_signal()
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "customer_insights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("insight_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("audience_hypothesis_id", sa.Uuid(), nullable=True),
        sa.Column("insight_type", sa.String(length=32), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("situation", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("alternative_explanations_json", sa.JSON(), nullable=False),
        sa.Column("missing_evidence_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=200), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "insight_key ~ '^[0-9a-f]{64}$'",
            name="ck_customer_insights_key",
        ),
        sa.CheckConstraint(
            "insight_type in ('job','pain','desire','question','fear','objection','barrier',"
            "'trigger','decision_factor','trust_builder','trust_breaker','language','behaviour',"
            "'expectation','post_purchase_need','referral_trigger','repeat_purchase_trigger')",
            name="ck_customer_insights_type",
        ),
        sa.CheckConstraint(
            "status in ('CANDIDATE','TESTING','SUPPORTED','REJECTED','INSUFFICIENT_EVIDENCE')",
            name="ck_customer_insights_status",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_customer_insights_version_positive",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["audience_hypothesis_id"],
            ["audience_hypotheses.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "insight_key",
            "version",
            name="uq_customer_insight_project_key_version",
        ),
    )
    op.create_index(
        "ix_customer_insights_project_type",
        "customer_insights",
        ["project_id", "insight_type", "status"],
        unique=False,
    )
    op.create_index(
        "ix_customer_insights_audience",
        "customer_insights",
        ["audience_hypothesis_id"],
        unique=False,
    )

    op.create_table(
        "customer_insight_signals",
        sa.Column("customer_insight_id", sa.Uuid(), nullable=False),
        sa.Column("signal_id", sa.Uuid(), nullable=False),
        sa.Column("relation", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "relation in ('supports','contradicts','context')",
            name="ck_customer_insight_signals_relation",
        ),
        sa.ForeignKeyConstraint(
            ["customer_insight_id"],
            ["customer_insights.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["signal_id"],
            ["signals.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("customer_insight_id", "signal_id"),
    )
    op.create_index(
        "ix_customer_insight_signals_signal",
        "customer_insight_signals",
        ["signal_id", "relation"],
        unique=False,
    )

    _create_customer_insight_guards()


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_insight_signals_guard "
            "ON customer_insight_signals"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_customer_insight_signal()"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_insights_guard ON customer_insights"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_customer_insight()"))
    op.drop_index(
        "ix_customer_insight_signals_signal",
        table_name="customer_insight_signals",
    )
    op.drop_table("customer_insight_signals")
    op.drop_index("ix_customer_insights_audience", table_name="customer_insights")
    op.drop_index(
        "ix_customer_insights_project_type",
        table_name="customer_insights",
    )
    op.drop_table("customer_insights")
