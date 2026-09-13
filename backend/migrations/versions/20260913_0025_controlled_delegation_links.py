"""Bind delegation telemetry to exact Codex decision and worker model calls."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0025"
down_revision: str | None = "20260913_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "delegation_executions",
        sa.Column("coordinator_model_call_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "delegation_executions",
        sa.Column("decision_artifact_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "delegation_executions",
        sa.Column("worker_model_call_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_delegation_execution_coordinator_model_call",
        "delegation_executions",
        "model_calls",
        ["coordinator_model_call_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_delegation_execution_decision_artifact",
        "delegation_executions",
        "artifacts",
        ["decision_artifact_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_delegation_execution_worker_model_call",
        "delegation_executions",
        "model_calls",
        ["worker_model_call_id"],
        ["id"],
    )
    op.create_index(
        "ix_delegation_execution_coordinator_model_call",
        "delegation_executions",
        ["coordinator_model_call_id"],
        unique=False,
    )
    op.create_index(
        "ix_delegation_execution_decision_artifact",
        "delegation_executions",
        ["decision_artifact_id"],
        unique=False,
    )
    op.create_index(
        "ix_delegation_execution_worker_model_call",
        "delegation_executions",
        ["worker_model_call_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_delegation_execution_worker_model_call",
        table_name="delegation_executions",
    )
    op.drop_index(
        "ix_delegation_execution_decision_artifact",
        table_name="delegation_executions",
    )
    op.drop_index(
        "ix_delegation_execution_coordinator_model_call",
        table_name="delegation_executions",
    )
    op.drop_constraint(
        "fk_delegation_execution_worker_model_call",
        "delegation_executions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_delegation_execution_decision_artifact",
        "delegation_executions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_delegation_execution_coordinator_model_call",
        "delegation_executions",
        type_="foreignkey",
    )
    op.drop_column("delegation_executions", "worker_model_call_id")
    op.drop_column("delegation_executions", "decision_artifact_id")
    op.drop_column("delegation_executions", "coordinator_model_call_id")
