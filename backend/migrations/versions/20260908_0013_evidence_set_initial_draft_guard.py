"""Require every newly inserted EvidenceSet to start as a clean draft."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0013"
down_revision: str | None = "20260908_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION enforce_evidence_set_initial_draft()
            RETURNS trigger AS $$
            BEGIN
                IF NEW.status <> 'draft'
                   OR NEW.locked_at IS NOT NULL
                   OR NEW.locked_by IS NOT NULL THEN
                    RAISE EXCEPTION 'evidence_set_must_start_draft';
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
            CREATE TRIGGER evidence_sets_initial_draft_guard
            BEFORE INSERT ON evidence_sets
            FOR EACH ROW
            EXECUTE FUNCTION enforce_evidence_set_initial_draft()
            """
        )
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER evidence_sets_initial_draft_guard ON evidence_sets")
    op.execute("DROP FUNCTION enforce_evidence_set_initial_draft()")
