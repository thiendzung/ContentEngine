"""Add durable approval metadata and snapshot binding to OriginalityPack."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0015"
down_revision: str | None = "20260909_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "originality_packs",
        sa.Column("approved_by", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "originality_packs",
        sa.Column("approval_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "originality_packs",
        sa.Column("snapshot_hash", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_originality_pack_approval_metadata",
        "originality_packs",
        "status <> 'approved' or (approved_at is not null and "
        "approved_by is not null and btrim(approved_by) <> '' and "
        "approval_reason is not null and btrim(approval_reason) <> '' and "
        "snapshot_hash is not null and snapshot_hash ~ '^[0-9a-f]{64}$')",
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION enforce_originality_pack_approval()
            RETURNS trigger AS $$
            BEGIN
                IF NEW.status = 'approved' AND (
                    NEW.approved_at IS NULL
                    OR NEW.approved_by IS NULL
                    OR btrim(NEW.approved_by) = ''
                    OR NEW.approval_reason IS NULL
                    OR btrim(NEW.approval_reason) = ''
                    OR NEW.snapshot_hash IS NULL
                    OR NEW.snapshot_hash !~ '^[0-9a-f]{64}$'
                ) THEN
                    RAISE EXCEPTION 'approved_originality_pack_requires_exact_metadata';
                END IF;

                IF TG_OP = 'UPDATE' AND OLD.status = 'approved' AND (
                    NEW.content_case_id IS DISTINCT FROM OLD.content_case_id
                    OR NEW.item_refs_json::text IS DISTINCT FROM OLD.item_refs_json::text
                    OR NEW.summary IS DISTINCT FROM OLD.summary
                    OR NEW.status NOT IN ('approved', 'retired')
                    OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
                    OR NEW.approved_by IS DISTINCT FROM OLD.approved_by
                    OR NEW.approval_reason IS DISTINCT FROM OLD.approval_reason
                    OR NEW.snapshot_hash IS DISTINCT FROM OLD.snapshot_hash
                ) THEN
                    RAISE EXCEPTION 'approved_originality_pack_is_immutable';
                END IF;

                IF TG_OP = 'UPDATE' AND OLD.status = 'retired' AND (
                    NEW.content_case_id IS DISTINCT FROM OLD.content_case_id
                    OR NEW.item_refs_json::text IS DISTINCT FROM OLD.item_refs_json::text
                    OR NEW.summary IS DISTINCT FROM OLD.summary
                    OR NEW.status IS DISTINCT FROM OLD.status
                    OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
                    OR NEW.approved_by IS DISTINCT FROM OLD.approved_by
                    OR NEW.approval_reason IS DISTINCT FROM OLD.approval_reason
                    OR NEW.snapshot_hash IS DISTINCT FROM OLD.snapshot_hash
                ) THEN
                    RAISE EXCEPTION 'retired_originality_pack_is_immutable';
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
            CREATE TRIGGER originality_packs_approval_guard
            BEFORE INSERT OR UPDATE ON originality_packs
            FOR EACH ROW
            EXECUTE FUNCTION enforce_originality_pack_approval()
            """
        )
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER originality_packs_approval_guard ON originality_packs")
    op.execute("DROP FUNCTION enforce_originality_pack_approval()")
    op.drop_constraint(
        "ck_originality_pack_approval_metadata",
        "originality_packs",
        type_="check",
    )
    op.drop_column("originality_packs", "snapshot_hash")
    op.drop_column("originality_packs", "approval_reason")
    op.drop_column("originality_packs", "approved_by")
