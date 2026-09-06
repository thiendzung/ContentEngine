"""Bind ContextManifest to the exact OriginalityPack seen by the model."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0008"
down_revision: str | None = "20260906_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "context_manifests",
        sa.Column("originality_pack_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_context_manifests_originality_pack",
        "context_manifests",
        "originality_packs",
        ["originality_pack_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_context_manifests_originality_pack",
        "context_manifests",
        type_="foreignkey",
    )
    op.drop_column("context_manifests", "originality_pack_id")
