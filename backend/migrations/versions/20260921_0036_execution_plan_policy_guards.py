"""Protect AU-01 execution plans and settings snapshots.

Revision ID: 20260921_0036
Revises: 20260921_0035
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_0036"
down_revision: str | None = "20260921_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_settings_snapshot_immutable()
            RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION 'settings_snapshot_is_immutable';
                END IF;
                RAISE EXCEPTION 'settings_snapshot_delete_forbidden';
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER settings_snapshot_immutable_guard
            BEFORE UPDATE OR DELETE ON settings_snapshots
            FOR EACH ROW EXECUTE FUNCTION protect_settings_snapshot_immutable()
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_execution_plan_artifact()
            RETURNS trigger AS $
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    IF OLD.artifact_type LIKE 'execution_plan_%'
                       OR NEW.artifact_type LIKE 'execution_plan_%' THEN
                        RAISE EXCEPTION 'execution_plan_artifact_is_immutable';
                    END IF;
                    RETURN NEW;
                END IF;

                IF OLD.artifact_type LIKE 'execution_plan_%' THEN
                    RAISE EXCEPTION 'execution_plan_artifact_delete_forbidden';
                END IF;
                RETURN OLD;
            END;
            $ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER execution_plan_artifact_immutable_guard
            BEFORE UPDATE OR DELETE ON artifacts
            FOR EACH ROW EXECUTE FUNCTION protect_execution_plan_artifact()
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS execution_plan_artifact_immutable_guard "
            "ON artifacts"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS protect_execution_plan_artifact()"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS settings_snapshot_immutable_guard "
            "ON settings_snapshots"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS protect_settings_snapshot_immutable()"))