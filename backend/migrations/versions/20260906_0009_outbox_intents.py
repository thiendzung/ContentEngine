"""Add durable outbox intents for CE03 side effects."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0009"
down_revision: str | None = "20260906_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_intents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("intent_type", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("payload_ref", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("external_ref", sa.Text()),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("error_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt >= 0", name="ck_outbox_intent_attempt_nonnegative"),
        sa.CheckConstraint(
            "status in ('pending','processing','completed','failed','needs_reconciliation')",
            name="ck_outbox_intent_status",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_outbox_intent_idempotency_key"),
    )


def downgrade() -> None:
    op.drop_table("outbox_intents")
