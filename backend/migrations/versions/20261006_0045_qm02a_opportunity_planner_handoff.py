"""Add immutable QM-02A opportunity planner handoff lineage.

Revision ID: 20261006_0045
Revises: 20260926_0044
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0045"
down_revision: str | None = "20260926_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_planner_handoffs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "need_hypothesis_id",
            sa.Uuid(),
            sa.ForeignKey("need_hypotheses.id"),
            nullable=False,
        ),
        sa.Column(
            "content_opportunity_id",
            sa.Uuid(),
            sa.ForeignKey("content_opportunities.id"),
            nullable=False,
        ),
        sa.Column(
            "human_selection_id",
            sa.Uuid(),
            sa.ForeignKey("human_selections.id"),
        ),
        sa.Column("locale", sa.String(32), nullable=False),
        sa.Column("cluster_key", sa.String(100), nullable=False),
        sa.Column(
            "planner_policy_version",
            sa.String(100),
            nullable=False,
        ),
        sa.Column(
            "planner_snapshot_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "question_coverage_snapshot_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "recommendation_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column("need_version", sa.Integer(), nullable=False),
        sa.Column(
            "idempotency_key",
            sa.String(200),
            nullable=False,
        ),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("resolution", sa.String(16), nullable=False),
        sa.Column("selected_by", sa.String(200), nullable=False),
        sa.Column("selection_reason", sa.Text(), nullable=False),
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
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_opportunity_planner_handoffs_idempotency_key",
        ),
        sa.UniqueConstraint(
            "project_id",
            "planner_snapshot_hash",
            "cluster_key",
            name="uq_opportunity_planner_handoff_snapshot_cluster",
        ),
        sa.UniqueConstraint(
            "human_selection_id",
            name="uq_opportunity_planner_handoff_human_selection",
        ),
        sa.CheckConstraint(
            "planner_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_opportunity_planner_handoff_planner_hash",
        ),
        sa.CheckConstraint(
            "question_coverage_snapshot_hash ~ '^[0-9a-f]{64}$'",
            name="ck_opportunity_planner_handoff_coverage_hash",
        ),
        sa.CheckConstraint(
            "recommendation_hash ~ '^[0-9a-f]{64}$'",
            name="ck_opportunity_planner_handoff_recommendation_hash",
        ),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'",
            name="ck_opportunity_planner_handoff_request_hash",
        ),
        sa.CheckConstraint(
            "need_version > 0",
            name="ck_opportunity_planner_handoff_need_version_positive",
        ),
        sa.CheckConstraint(
            "resolution in ('SELECTED','REUSED')",
            name="ck_opportunity_planner_handoff_resolution",
        ),
        sa.CheckConstraint(
            "resolution <> 'SELECTED' or human_selection_id is not null",
            name="ck_opportunity_planner_handoff_selected_selection",
        ),
        sa.CheckConstraint(
            "btrim(cluster_key) <> ''",
            name="ck_opportunity_planner_handoff_cluster_key",
        ),
        sa.CheckConstraint(
            "btrim(idempotency_key) <> ''",
            name="ck_opportunity_planner_handoff_idempotency_key",
        ),
        sa.CheckConstraint(
            "btrim(selected_by) <> ''",
            name="ck_opportunity_planner_handoff_selected_by",
        ),
        sa.CheckConstraint(
            "btrim(selection_reason) <> ''",
            name="ck_opportunity_planner_handoff_selection_reason",
        ),
    )
    op.create_index(
        "ix_opportunity_planner_handoffs_opportunity",
        "opportunity_planner_handoffs",
        ["content_opportunity_id"],
    )
    op.create_index(
        "ix_opportunity_planner_handoffs_need_locale",
        "opportunity_planner_handoffs",
        ["need_hypothesis_id", "locale"],
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION prevent_opportunity_planner_handoff_mutation()
            RETURNS trigger AS $qm02a$
            BEGIN
                RAISE EXCEPTION 'opportunity_planner_handoff_is_immutable';
            END;
            $qm02a$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER opportunity_planner_handoffs_immutable
            BEFORE UPDATE OR DELETE ON opportunity_planner_handoffs
            FOR EACH ROW
            EXECUTE FUNCTION prevent_opportunity_planner_handoff_mutation()
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS opportunity_planner_handoffs_immutable "
            "ON opportunity_planner_handoffs"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS prevent_opportunity_planner_handoff_mutation()"
        )
    )
    op.drop_index(
        "ix_opportunity_planner_handoffs_need_locale",
        table_name="opportunity_planner_handoffs",
    )
    op.drop_index(
        "ix_opportunity_planner_handoffs_opportunity",
        table_name="opportunity_planner_handoffs",
    )
    op.drop_table("opportunity_planner_handoffs")
