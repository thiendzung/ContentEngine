"""Add durable Codex delegation execution telemetry."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0024"
down_revision: str | None = "20260912_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "delegation_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_run_id", sa.Uuid(), nullable=True),
        sa.Column("parent_execution_id", sa.Uuid(), nullable=True),
        sa.Column("coordinator_key", sa.String(length=100), nullable=False),
        sa.Column("worker_kind", sa.String(length=32), nullable=False),
        sa.Column("worker_key", sa.String(length=200), nullable=False),
        sa.Column("task_key", sa.String(length=100), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("external_execution_id", sa.String(length=255), nullable=True),
        sa.Column("result_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_class", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt > 0", name="ck_delegation_execution_attempt_positive"),
        sa.CheckConstraint(
            "worker_kind in ('subagent','application','tool')",
            name="ck_delegation_execution_worker_kind",
        ),
        sa.CheckConstraint(
            "status in ('queued','running','completed','failed','cancelled')",
            name="ck_delegation_execution_status",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["content_runs.id"]),
        sa.ForeignKeyConstraint(["step_run_id"], ["step_runs.id"]),
        sa.ForeignKeyConstraint(["parent_execution_id"], ["delegation_executions.id"]),
        sa.ForeignKeyConstraint(["result_artifact_id"], ["artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_delegation_execution_dedupe_key"),
    )
    op.create_index(
        "ix_delegation_execution_run",
        "delegation_executions",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_delegation_execution_step",
        "delegation_executions",
        ["step_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_delegation_execution_parent",
        "delegation_executions",
        ["parent_execution_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_delegation_execution_parent", table_name="delegation_executions")
    op.drop_index("ix_delegation_execution_step", table_name="delegation_executions")
    op.drop_index("ix_delegation_execution_run", table_name="delegation_executions")
    op.drop_table("delegation_executions")
