"""Add durable operator command ledger for the Journal control plane."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0026"
down_revision: str | None = "20260913_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operator_commands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_case_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("step_run_id", sa.Uuid(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("result_ref_id", sa.Uuid(), nullable=True),
        sa.Column("intent", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("expected_state_version", sa.String(length=64), nullable=False),
        sa.Column("resolved_action_key", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("actor_id", sa.String(length=200), nullable=False),
        sa.Column("state_before", sa.String(length=64), nullable=False),
        sa.Column("state_after", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "intent in ('create','start','continue','resume','retry','cancel',"
            "'approve','request_changes','reject')",
            name="ck_operator_command_intent",
        ),
        sa.CheckConstraint(
            "status in ('accepted','queued','completed','rejected','failed','cancelled')",
            name="ck_operator_command_status",
        ),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'",
            name="ck_operator_command_request_hash",
        ),
        sa.CheckConstraint(
            "expected_state_version ~ '^[0-9a-f]{64}$'",
            name="ck_operator_command_expected_state",
        ),
        sa.CheckConstraint(
            "state_before ~ '^[0-9a-f]{64}$'",
            name="ck_operator_command_state_before",
        ),
        sa.CheckConstraint(
            "state_after is null or state_after ~ '^[0-9a-f]{64}$'",
            name="ck_operator_command_state_after",
        ),
        sa.ForeignKeyConstraint(["content_case_id"], ["content_cases.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["content_runs.id"]),
        sa.ForeignKeyConstraint(["step_run_id"], ["step_runs.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_operator_command_idempotency"),
    )
    op.create_index(
        "ix_operator_commands_case_status",
        "operator_commands",
        ["content_case_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_operator_commands_job",
        "operator_commands",
        ["job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_operator_commands_job", table_name="operator_commands")
    op.drop_index("ix_operator_commands_case_status", table_name="operator_commands")
    op.drop_table("operator_commands")
