"""Add LL-01C human learning review and application receipts.

Revision ID: 20260922_0041
Revises: 20260922_0040
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0041"
down_revision: str | None = "20260922_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION validate_learning_candidate_review()
        RETURNS trigger AS $$
        DECLARE
            candidate_project uuid;
            candidate_version integer;
            candidate_status text;
            candidate_key text;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'learning_candidate_review_update_forbidden';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'learning_candidate_review_delete_forbidden';
            END IF;

            SELECT project_id, version, status, candidate_key
            INTO candidate_project, candidate_version, candidate_status, candidate_key
            FROM learning_candidates
            WHERE id = NEW.learning_candidate_id;

            IF candidate_project IS NULL THEN
                RAISE EXCEPTION 'learning_candidate_review_candidate_not_found';
            END IF;
            IF candidate_project IS DISTINCT FROM NEW.project_id
               OR candidate_version IS DISTINCT FROM NEW.candidate_version THEN
                RAISE EXCEPTION 'learning_candidate_review_identity_mismatch';
            END IF;
            IF candidate_status IS DISTINCT FROM 'OPEN' THEN
                RAISE EXCEPTION 'learning_candidate_review_candidate_not_open';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM learning_candidates newer
                WHERE newer.project_id = candidate_project
                  AND newer.candidate_key = candidate_key
                  AND newer.version > candidate_version
            ) THEN
                RAISE EXCEPTION 'learning_candidate_review_candidate_stale';
            END IF;
            IF length(btrim(NEW.reviewed_by)) = 0
               OR length(btrim(NEW.reason)) = 0 THEN
                RAISE EXCEPTION 'learning_candidate_review_human_fields_required';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER learning_candidate_reviews_guard
        BEFORE INSERT OR UPDATE OR DELETE ON learning_candidate_reviews
        FOR EACH ROW
        EXECUTE FUNCTION validate_learning_candidate_review()
        """
    )

    op.execute(
        """
        CREATE FUNCTION validate_learning_application()
        RETURNS trigger AS $$
        DECLARE
            candidate_project uuid;
            candidate_version integer;
            candidate_status text;
            candidate_key text;
            candidate_target_type text;
            candidate_target_id uuid;
            review_project uuid;
            review_candidate uuid;
            review_version integer;
            review_decision text;
            review_snapshot text;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'learning_application_update_forbidden';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'learning_application_delete_forbidden';
            END IF;

            SELECT project_id, version, status, candidate_key, target_type, target_id
            INTO candidate_project, candidate_version, candidate_status,
                 candidate_key, candidate_target_type, candidate_target_id
            FROM learning_candidates
            WHERE id = NEW.learning_candidate_id;

            SELECT project_id, learning_candidate_id, candidate_version,
                   decision, candidate_snapshot_hash
            INTO review_project, review_candidate, review_version,
                 review_decision, review_snapshot
            FROM learning_candidate_reviews
            WHERE id = NEW.review_id;

            IF candidate_project IS NULL OR review_project IS NULL THEN
                RAISE EXCEPTION 'learning_application_lineage_not_found';
            END IF;
            IF candidate_project IS DISTINCT FROM NEW.project_id
               OR candidate_version IS DISTINCT FROM NEW.candidate_version
               OR review_project IS DISTINCT FROM NEW.project_id
               OR review_candidate IS DISTINCT FROM NEW.learning_candidate_id
               OR review_version IS DISTINCT FROM NEW.candidate_version
               OR review_snapshot IS DISTINCT FROM NEW.candidate_snapshot_hash THEN
                RAISE EXCEPTION 'learning_application_identity_mismatch';
            END IF;
            IF candidate_status IS DISTINCT FROM 'OPEN' THEN
                RAISE EXCEPTION 'learning_application_candidate_not_open';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM learning_candidates newer
                WHERE newer.project_id = candidate_project
                  AND newer.candidate_key = candidate_key
                  AND newer.version > candidate_version
            ) THEN
                RAISE EXCEPTION 'learning_application_candidate_stale';
            END IF;
            IF review_decision NOT IN ('APPROVE','NO_MAP_CHANGE') THEN
                RAISE EXCEPTION 'learning_application_review_not_applicable';
            END IF;
            IF NEW.target_type IS DISTINCT FROM candidate_target_type
               OR NEW.target_id IS DISTINCT FROM candidate_target_id THEN
                RAISE EXCEPTION 'learning_application_target_mismatch';
            END IF;
            IF review_decision = 'NO_MAP_CHANGE' THEN
                IF NEW.applied_action IS DISTINCT FROM 'no_map_change'
                   OR NEW.resulting_target_id IS NOT NULL
                   OR NEW.customer_map_snapshot_artifact_id IS NOT NULL
                   OR NEW.before_state_hash IS NOT NULL
                   OR NEW.after_state_hash IS NOT NULL THEN
                    RAISE EXCEPTION 'learning_application_no_map_change_invalid';
                END IF;
            ELSIF NEW.target_type = 'need_hypothesis'
                  AND NEW.applied_action IS DISTINCT FROM 'link_need_signals' THEN
                RAISE EXCEPTION 'learning_application_action_mismatch';
            ELSIF NEW.target_type = 'customer_insight'
                  AND NEW.applied_action IS DISTINCT FROM 'link_insight_signals' THEN
                RAISE EXCEPTION 'learning_application_action_mismatch';
            ELSIF NEW.target_type = 'new_customer_insight'
                  AND NEW.applied_action IS DISTINCT FROM 'create_candidate_insight' THEN
                RAISE EXCEPTION 'learning_application_action_mismatch';
            ELSIF NEW.target_type = 'no_map_change'
                  AND NEW.applied_action IS DISTINCT FROM 'no_map_change' THEN
                RAISE EXCEPTION 'learning_application_action_mismatch';
            END IF;
            IF length(btrim(NEW.applied_by)) = 0 THEN
                RAISE EXCEPTION 'learning_application_actor_required';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER learning_applications_guard
        BEFORE INSERT OR UPDATE OR DELETE ON learning_applications
        FOR EACH ROW
        EXECUTE FUNCTION validate_learning_application()
        """
    )


def upgrade() -> None:
    op.create_table(
        "learning_candidate_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("learning_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("candidate_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("target_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision in "
            "('APPROVE','REJECT','REQUEST_MORE_EVIDENCE','NO_MAP_CHANGE')",
            name="ck_learning_candidate_reviews_decision",
        ),
        sa.CheckConstraint(
            "candidate_version > 0",
            name="ck_learning_candidate_reviews_version",
        ),
        sa.CheckConstraint(
            "candidate_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_learning_candidate_reviews_snapshot_hash",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["learning_candidate_id"],
            ["learning_candidates.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learning_candidate_id",
            name="uq_learning_candidate_review_candidate",
        ),
    )
    op.create_index(
        "ix_learning_candidate_reviews_project_time",
        "learning_candidate_reviews",
        ["project_id", "reviewed_at"],
        unique=False,
    )

    op.create_table(
        "learning_applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("learning_candidate_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_version", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("resulting_target_id", sa.Uuid(), nullable=True),
        sa.Column("applied_action", sa.String(length=32), nullable=False),
        sa.Column("applied_signal_refs_json", sa.JSON(), nullable=False),
        sa.Column("frozen_scope_json", sa.JSON(), nullable=False),
        sa.Column("before_state_hash", sa.String(length=64), nullable=True),
        sa.Column("after_state_hash", sa.String(length=64), nullable=True),
        sa.Column("customer_map_snapshot_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("change_report_json", sa.JSON(), nullable=True),
        sa.Column("applied_by", sa.String(length=200), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "candidate_version > 0",
            name="ck_learning_applications_version",
        ),
        sa.CheckConstraint(
            "candidate_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_learning_applications_snapshot_hash",
        ),
        sa.CheckConstraint(
            "target_type in "
            "('customer_insight','need_hypothesis','new_customer_insight','no_map_change')",
            name="ck_learning_applications_target_type",
        ),
        sa.CheckConstraint(
            "applied_action in "
            "('link_need_signals','link_insight_signals',"
            "'create_candidate_insight','no_map_change')",
            name="ck_learning_applications_action",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["learning_candidate_id"],
            ["learning_candidates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["learning_candidate_reviews.id"],
        ),
        sa.ForeignKeyConstraint(
            ["customer_map_snapshot_artifact_id"],
            ["artifacts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "review_id",
            name="uq_learning_application_review",
        ),
    )
    op.create_index(
        "ix_learning_applications_candidate",
        "learning_applications",
        ["learning_candidate_id", "candidate_version"],
        unique=False,
    )
    op.create_index(
        "ix_learning_applications_project_time",
        "learning_applications",
        ["project_id", "applied_at"],
        unique=False,
    )

    _create_guards()


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS learning_applications_guard "
        "ON learning_applications"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_learning_application()")
    op.execute(
        "DROP TRIGGER IF EXISTS learning_candidate_reviews_guard "
        "ON learning_candidate_reviews"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_learning_candidate_review()")

    op.drop_index(
        "ix_learning_applications_project_time",
        table_name="learning_applications",
    )
    op.drop_index(
        "ix_learning_applications_candidate",
        table_name="learning_applications",
    )
    op.drop_table("learning_applications")

    op.drop_index(
        "ix_learning_candidate_reviews_project_time",
        table_name="learning_candidate_reviews",
    )
    op.drop_table("learning_candidate_reviews")
