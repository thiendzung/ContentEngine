"""Add immutable, snapshot-bound EvidenceSet approvals."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0011"
down_revision: str | None = "20260906_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_set_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evidence_set_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_set_version", sa.Integer(), nullable=False),
        sa.Column("evidence_set_content_hash", sa.String(length=64), nullable=False),
        sa.Column("approved_by", sa.String(length=200), nullable=False),
        sa.Column("approval_reason", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evidence_set_version > 0", name="ck_evidence_set_approval_version_positive"
        ),
        sa.ForeignKeyConstraint(["evidence_set_id"], ["evidence_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evidence_set_id",
            "evidence_set_version",
            "evidence_set_content_hash",
            name="uq_evidence_set_approval_snapshot",
        ),
    )
    op.create_index(
        "ix_evidence_set_approvals_evidence_set",
        "evidence_set_approvals",
        ["evidence_set_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            "CREATE FUNCTION prevent_evidence_set_approval_mutation() RETURNS trigger "
            "AS $$ BEGIN RAISE EXCEPTION 'evidence_set_approval_is_immutable'; "
            "END; $$ LANGUAGE plpgsql"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER evidence_set_approvals_immutable BEFORE UPDATE OR DELETE "
            "ON evidence_set_approvals FOR EACH ROW "
            "EXECUTE FUNCTION prevent_evidence_set_approval_mutation()"
        )
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER evidence_set_approvals_immutable ON evidence_set_approvals")
    op.execute("DROP FUNCTION prevent_evidence_set_approval_mutation()")
    op.drop_index("ix_evidence_set_approvals_evidence_set", table_name="evidence_set_approvals")
    op.drop_table("evidence_set_approvals")
