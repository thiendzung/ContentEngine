"""Add durable Founder promise coverage requirements.

Revision ID: 20260925_0043
Revises: 20260923_0042
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0043"
down_revision: str | None = "20260923_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content_opportunities",
        sa.Column(
            "coverage_requirements_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )


def downgrade() -> None:
    op.drop_column("content_opportunities", "coverage_requirements_json")
