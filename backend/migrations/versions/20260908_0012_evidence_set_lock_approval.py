"""Require an exact EvidenceSetApproval for new EvidenceSet locks."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0012"
down_revision: str | None = "20260908_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION enforce_evidence_set_lock_approval()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.status = 'draft' AND NEW.status = 'locked' THEN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM evidence_set_approvals approval
                        WHERE approval.evidence_set_id = NEW.id
                          AND approval.evidence_set_version = NEW.version
                          AND approval.evidence_set_content_hash = NEW.content_hash
                    ) THEN
                        RAISE EXCEPTION 'evidence_set_lock_requires_exact_approval';
                    END IF;
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM evidence_set_approvals approval
                    WHERE approval.evidence_set_id = OLD.id
                      AND approval.evidence_set_version = OLD.version
                      AND approval.evidence_set_content_hash = OLD.content_hash
                ) AND (
                    NEW.version IS DISTINCT FROM OLD.version
                    OR NEW.evidence_ids_json::text IS DISTINCT FROM OLD.evidence_ids_json::text
                    OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
                    OR NEW.project_id IS DISTINCT FROM OLD.project_id
                    OR NEW.content_case_id IS DISTINCT FROM OLD.content_case_id
                ) THEN
                    RAISE EXCEPTION 'approved_evidence_set_snapshot_is_immutable';
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
            CREATE TRIGGER evidence_sets_lock_approval_guard
            BEFORE UPDATE ON evidence_sets
            FOR EACH ROW
            EXECUTE FUNCTION enforce_evidence_set_lock_approval()
            """
        )
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER evidence_sets_lock_approval_guard ON evidence_sets")
    op.execute("DROP FUNCTION enforce_evidence_set_lock_approval()")
