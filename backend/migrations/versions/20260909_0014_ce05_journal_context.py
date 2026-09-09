"""Persist CE05 journal context references in ContextManifest."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0014"
down_revision: str | None = "20260908_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "context_manifests",
        sa.Column("context_artifact_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_context_manifests_context_artifact",
        "context_manifests",
        "artifacts",
        ["context_artifact_id"],
        ["id"],
    )
    op.add_column(
        "context_manifests",
        sa.Column(
            "approved_knowledge_refs_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column("context_manifests", "approved_knowledge_refs_json", server_default=None)


def downgrade() -> None:
    op.drop_column("context_manifests", "approved_knowledge_refs_json")
    op.drop_constraint(
        "fk_context_manifests_context_artifact",
        "context_manifests",
        type_="foreignkey",
    )
    op.drop_column("context_manifests", "context_artifact_id")
