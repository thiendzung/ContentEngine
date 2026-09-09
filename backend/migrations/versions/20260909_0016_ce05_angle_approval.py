"""Add immutable, snapshot-bound CE05 Angle approvals."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0016"
down_revision: str | None = "20260909_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "angle_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("angle_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("angle_artifact_version", sa.Integer(), nullable=False),
        sa.Column("angle_artifact_hash", sa.String(length=64), nullable=False),
        sa.Column("selected_angle_id", sa.String(length=200), nullable=False),
        sa.Column("selected_candidate_hash", sa.String(length=64), nullable=False),
        sa.Column("approved_by", sa.String(length=200), nullable=False),
        sa.Column("approval_reason", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "angle_artifact_version > 0",
            name="ck_angle_approval_artifact_version_positive",
        ),
        sa.CheckConstraint(
            "angle_artifact_hash ~ '^[0-9a-f]{64}$'",
            name="ck_angle_approval_artifact_hash",
        ),
        sa.CheckConstraint(
            "selected_candidate_hash ~ '^[0-9a-f]{64}$'",
            name="ck_angle_approval_candidate_hash",
        ),
        sa.CheckConstraint("btrim(selected_angle_id) <> ''", name="ck_angle_approval_angle_id"),
        sa.CheckConstraint("btrim(approved_by) <> ''", name="ck_angle_approval_approved_by"),
        sa.CheckConstraint("btrim(approval_reason) <> ''", name="ck_angle_approval_reason"),
        sa.ForeignKeyConstraint(["run_id"], ["content_runs.id"]),
        sa.ForeignKeyConstraint(["angle_artifact_id"], ["artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "angle_artifact_id",
            "angle_artifact_version",
            "angle_artifact_hash",
            name="uq_angle_approval_artifact_snapshot",
        ),
    )
    op.create_index(
        "ix_angle_approvals_artifact",
        "angle_approvals",
        ["angle_artifact_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            "CREATE FUNCTION prevent_angle_approval_mutation() RETURNS trigger "
            "AS $$ BEGIN RAISE EXCEPTION 'angle_approval_is_immutable'; "
            "END; $$ LANGUAGE plpgsql"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER angle_approvals_immutable BEFORE UPDATE OR DELETE "
            "ON angle_approvals FOR EACH ROW "
            "EXECUTE FUNCTION prevent_angle_approval_mutation()"
        )
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER angle_approvals_immutable ON angle_approvals")
    op.execute("DROP FUNCTION prevent_angle_approval_mutation()")
    op.drop_index("ix_angle_approvals_artifact", table_name="angle_approvals")
    op.drop_table("angle_approvals")
