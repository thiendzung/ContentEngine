"""CE01 baseline migration.

Revision ID: 20260902_0001
Revises:
Create Date: 2026-09-02
"""

from collections.abc import Sequence

revision: str = "20260902_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Schema is intentionally empty in CE01 PR-A."""


def downgrade() -> None:
    """Schema is intentionally empty in CE01 PR-A."""
