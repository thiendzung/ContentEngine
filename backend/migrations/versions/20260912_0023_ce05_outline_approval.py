"""Add immutable, snapshot-bound CE05 Outline approvals."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0023"
down_revision: str | None = "20260910_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outline_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("outline_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("outline_artifact_version", sa.Integer(), nullable=False),
        sa.Column("outline_artifact_hash", sa.String(length=64), nullable=False),
        sa.Column("approved_by", sa.String(length=200), nullable=False),
        sa.Column("approval_reason", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outline_artifact_version > 0",
            name="ck_outline_approval_artifact_version_positive",
        ),
        sa.CheckConstraint(
            "outline_artifact_hash ~ '^[0-9a-f]{64}$'",
            name="ck_outline_approval_artifact_hash",
        ),
        sa.CheckConstraint("btrim(approved_by) <> ''", name="ck_outline_approval_approved_by"),
        sa.CheckConstraint(
            "btrim(approval_reason) <> ''", name="ck_outline_approval_reason"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["content_runs.id"]),
        sa.ForeignKeyConstraint(["outline_artifact_id"], ["artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "outline_artifact_id",
            "outline_artifact_version",
            "outline_artifact_hash",
            name="uq_outline_approval_artifact_snapshot",
        ),
    )
    op.create_index(
        "ix_outline_approvals_artifact",
        "outline_approvals",
        ["outline_artifact_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            "CREATE FUNCTION prevent_outline_approval_mutation() RETURNS trigger "
            "AS $$ BEGIN RAISE EXCEPTION 'outline_approval_is_immutable'; "
            "END; $$ LANGUAGE plpgsql"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER outline_approvals_immutable BEFORE UPDATE OR DELETE "
            "ON outline_approvals FOR EACH ROW "
            "EXECUTE FUNCTION prevent_outline_approval_mutation()"
        )
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER outline_approvals_immutable ON outline_approvals")
    op.execute("DROP FUNCTION prevent_outline_approval_mutation()")
    op.drop_index("ix_outline_approvals_artifact", table_name="outline_approvals")
    op.drop_table("outline_approvals")
