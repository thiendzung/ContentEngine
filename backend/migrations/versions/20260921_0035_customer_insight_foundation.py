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
            CREATE FUNCTION validate_customer_insight_signal_lineage(
                p_signal_id uuid,
                p_project_id uuid
            ) RETURNS text AS $$
            DECLARE
                current_id uuid := p_signal_id;
                current_project uuid;
                parent_id uuid;
                current_group text;
                group_key text := NULL;
                visited uuid[] := ARRAY[]::uuid[];
            BEGIN
                LOOP
                    IF current_id IS NULL THEN
                        RAISE EXCEPTION
                            'customer_insight_signal_duplicate_parent_invalid';
                    END IF;
                    IF current_id = ANY(visited) THEN
                        RAISE EXCEPTION
                            'customer_insight_signal_duplicate_cycle';
                    END IF;
                    visited := array_append(visited, current_id);

                    SELECT project_id, duplicate_of_id, independence_group
                    INTO current_project, parent_id, current_group
                    FROM signals
                    WHERE id = current_id;

                    IF NOT FOUND THEN
                        RAISE EXCEPTION
                            'customer_insight_signal_duplicate_parent_invalid';
                    END IF;
                    IF current_project IS DISTINCT FROM p_project_id THEN
                        IF current_id = p_signal_id THEN
                            RAISE EXCEPTION
                                'customer_insight_signal_project_mismatch';
                        END IF;
                        RAISE EXCEPTION
                            'customer_insight_signal_duplicate_parent_invalid';
                    END IF;

                    IF current_group IS NOT NULL
                       AND btrim(current_group) <> '' THEN
                        IF group_key IS NULL THEN
                            group_key := current_group;
                        ELSIF group_key IS DISTINCT FROM current_group THEN
                            RAISE EXCEPTION
                                'customer_insight_signal_'
                                'independence_group_conflict';
                        END IF;
                    END IF;

                    IF parent_id IS NULL THEN
                        IF group_key IS NOT NULL THEN
                            RETURN 'group:' || group_key;
                        END IF;
                        RETURN 'signal:' || current_id::text;
                    END IF;

                    current_id := parent_id;
                END LOOP;
            END;
            $$ LANGUAGE plpgsql STABLE
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION customer_insight_signal_is_in_use(
                p_signal_id uuid
            ) RETURNS boolean AS $$
                WITH RECURSIVE descendants(id) AS (
                    SELECT p_signal_id
                    UNION
                    SELECT s.id
                    FROM signals s
                    JOIN descendants d
                      ON s.duplicate_of_id = d.id
                )
                SELECT EXISTS(
                    SELECT 1
                    FROM descendants d
                    JOIN customer_insight_signals cis
                      ON cis.signal_id = d.id
                )
            $$ LANGUAGE sql STABLE
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_customer_insight_signal_lineage()
            RETURNS trigger AS $$
            BEGIN
                IF (
                    OLD.project_id IS DISTINCT FROM NEW.project_id
                    OR OLD.duplicate_of_id IS DISTINCT FROM NEW.duplicate_of_id
                    OR OLD.independence_group
                       IS DISTINCT FROM NEW.independence_group
                )
                AND customer_insight_signal_is_in_use(OLD.id) THEN
                    RAISE EXCEPTION
                        'customer_insight_signal_lineage_immutable';
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
            CREATE TRIGGER customer_insight_signal_lineage_guard
            BEFORE UPDATE OF project_id, duplicate_of_id, independence_group
            ON signals
            FOR EACH ROW
            EXECUTE FUNCTION protect_customer_insight_signal_lineage()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_customer_insight_audience_scope()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.project_id IS DISTINCT FROM NEW.project_id
                   AND EXISTS(
                       SELECT 1
                       FROM customer_insights ci
                       WHERE ci.audience_hypothesis_id = OLD.id
                   ) THEN
                    RAISE EXCEPTION
                        'customer_insight_audience_project_change_forbidden';
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
            CREATE TRIGGER customer_insight_audience_scope_guard
            BEFORE UPDATE OF project_id ON audience_hypotheses
            FOR EACH ROW
            EXECUTE FUNCTION protect_customer_insight_audience_scope()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_customer_insight() RETURNS trigger AS $$
            DECLARE
                audience_project uuid;
                matching_review boolean;
                support_key text;
                support_keys text[] := ARRAY[]::text[];
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'customer_insight_delete_forbidden';
                END IF;

                IF TG_OP = 'INSERT' AND NEW.status <> 'CANDIDATE' THEN
                    RAISE EXCEPTION
                        'customer_insight_initial_status_must_be_candidate';
                END IF;

                IF NEW.audience_hypothesis_id IS NOT NULL THEN
                    SELECT project_id
                    INTO audience_project
                    FROM audience_hypotheses
                    WHERE id = NEW.audience_hypothesis_id;

                    IF audience_project IS NULL THEN
                        RAISE EXCEPTION 'customer_insight_audience_not_found';
                    END IF;
                    IF audience_project IS DISTINCT FROM NEW.project_id THEN
                        RAISE EXCEPTION
                            'customer_insight_audience_project_mismatch';
                    END IF;
                END IF;

                IF TG_OP = 'UPDATE' THEN
                    IF OLD.project_id IS DISTINCT FROM NEW.project_id
                       OR OLD.insight_key IS DISTINCT FROM NEW.insight_key
                       OR OLD.version IS DISTINCT FROM NEW.version
                       OR OLD.insight_type IS DISTINCT FROM NEW.insight_type
                       OR OLD.statement IS DISTINCT FROM NEW.statement
                       OR OLD.audience_hypothesis_id
                          IS DISTINCT FROM NEW.audience_hypothesis_id
                       OR OLD.situation IS DISTINCT FROM NEW.situation
                       OR OLD.alternative_explanations_json::jsonb
                          IS DISTINCT FROM NEW.alternative_explanations_json::jsonb
                       OR OLD.missing_evidence_json::jsonb
                          IS DISTINCT FROM NEW.missing_evidence_json::jsonb THEN
                        RAISE EXCEPTION
                            'customer_insight_version_content_immutable';
                    END IF;

                    IF OLD.status IS DISTINCT FROM NEW.status
                       OR OLD.reviewed_by IS DISTINCT FROM NEW.reviewed_by
                       OR OLD.reviewed_at IS DISTINCT FROM NEW.reviewed_at
                       OR OLD.review_reason IS DISTINCT FROM NEW.review_reason THEN
                        IF NEW.reviewed_by IS NULL
                           OR btrim(NEW.reviewed_by) = ''
                           OR NEW.reviewed_at IS NULL
                           OR NEW.review_reason IS NULL
                           OR btrim(NEW.review_reason) = '' THEN
                            RAISE EXCEPTION
                                'customer_insight_review_required';
                        END IF;

                        IF OLD.reviewed_at IS NOT NULL
                           AND NEW.reviewed_at <= OLD.reviewed_at THEN
                            RAISE EXCEPTION
                                'customer_insight_review_must_advance';
                        END IF;

                        SELECT EXISTS(
                            SELECT 1
                            FROM customer_insight_reviews cir
                            WHERE cir.customer_insight_id = NEW.id
                              AND cir.status = NEW.status
                              AND cir.reviewed_by = NEW.reviewed_by
                              AND cir.reviewed_at = NEW.reviewed_at
                              AND cir.reason = NEW.review_reason
                        )
                        INTO matching_review;

                        IF NOT matching_review THEN
                            RAISE EXCEPTION
                                'customer_insight_review_record_required';
                        END IF;
                    END IF;
                END IF;

                IF NEW.status = 'SUPPORTED' THEN
                    FOR support_key IN
                        SELECT validate_customer_insight_signal_lineage(
                            cis.signal_id,
                            NEW.project_id
                        )
                        FROM customer_insight_signals cis
                        WHERE cis.customer_insight_id = NEW.id
                          AND cis.relation = 'supports'
                    LOOP
                        IF NOT support_key = ANY(support_keys) THEN
                            support_keys := array_append(
                                support_keys,
                                support_key
                            );
                        END IF;
                    END LOOP;

                    IF COALESCE(array_length(support_keys, 1), 0) < 1 THEN
                        RAISE EXCEPTION
                            'customer_insight_support_evidence_required';
                    END IF;
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
            BEFORE INSERT OR UPDATE OR DELETE ON customer_insights
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
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'customer_insight_signal_is_immutable';
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION
                        'customer_insight_signal_delete_forbidden';
                END IF;

                SELECT project_id INTO insight_project
                FROM customer_insights
                WHERE id = NEW.customer_insight_id;

                IF insight_project IS NULL THEN
                    RAISE EXCEPTION 'customer_insight_not_found';
                END IF;

                PERFORM validate_customer_insight_signal_lineage(
                    NEW.signal_id,
                    insight_project
                );

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
            BEFORE INSERT OR UPDATE OR DELETE ON customer_insight_signals
            FOR EACH ROW EXECUTE FUNCTION validate_customer_insight_signal()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_customer_insight_review() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION
                        'customer_insight_review_is_immutable';
                END IF;
                RAISE EXCEPTION
                    'customer_insight_review_delete_forbidden';
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER customer_insight_reviews_guard
            BEFORE UPDATE OR DELETE ON customer_insight_reviews
            FOR EACH ROW EXECUTE FUNCTION protect_customer_insight_review()
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
            "insight_type in "
            "('job','pain','desire','question','fear','objection','barrier',"
            "'trigger','decision_factor','trust_builder','trust_breaker','language',"
            "'behaviour','expectation','post_purchase_need','referral_trigger',"
            "'repeat_purchase_trigger')",
            name="ck_customer_insights_type",
        ),
        sa.CheckConstraint(
            "status in "
            "('CANDIDATE','TESTING','SUPPORTED','REJECTED',"
            "'INSUFFICIENT_EVIDENCE')",
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

    op.create_table(
        "customer_insight_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_insight_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("support_signal_refs_json", sa.JSON(), nullable=False),
        sa.Column("contradict_signal_refs_json", sa.JSON(), nullable=False),
        sa.Column("context_signal_refs_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in "
            "('TESTING','SUPPORTED','REJECTED','INSUFFICIENT_EVIDENCE')",
            name="ck_customer_insight_reviews_status",
        ),
        sa.ForeignKeyConstraint(
            ["customer_insight_id"],
            ["customer_insights.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_customer_insight_reviews_insight_time",
        "customer_insight_reviews",
        ["customer_insight_id", "reviewed_at"],
        unique=False,
    )

    _create_customer_insight_guards()


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_insight_reviews_guard "
            "ON customer_insight_reviews"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS protect_customer_insight_review()")
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_insight_signals_guard "
            "ON customer_insight_signals"
        )
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS validate_customer_insight_signal()")
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_insights_guard "
            "ON customer_insights"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_customer_insight()"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_insight_audience_scope_guard "
            "ON audience_hypotheses"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS protect_customer_insight_audience_scope()"
        )
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS customer_insight_signal_lineage_guard "
            "ON signals"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS protect_customer_insight_signal_lineage()"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS customer_insight_signal_is_in_use(uuid)"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS "
            "validate_customer_insight_signal_lineage(uuid, uuid)"
        )
    )
    op.drop_index(
        "ix_customer_insight_reviews_insight_time",
        table_name="customer_insight_reviews",
    )
    op.drop_table("customer_insight_reviews")
    op.drop_index(
        "ix_customer_insight_signals_signal",
        table_name="customer_insight_signals",
    )
    op.drop_table("customer_insight_signals")
    op.drop_index(
        "ix_customer_insights_audience",
        table_name="customer_insights",
    )
    op.drop_index(
        "ix_customer_insights_project_type",
        table_name="customer_insights",
    )
    op.drop_table("customer_insights")