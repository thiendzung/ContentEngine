"""Add canonical Journal intake scope and required-locale ledger."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0027"
down_revision: str | None = "20260914_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "journal_intake_specs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_case_id", sa.Uuid(), nullable=False),
        sa.Column("source_locale", sa.String(length=32), nullable=False),
        sa.Column("research_country", sa.String(length=8), nullable=False),
        sa.Column("intake_hash", sa.String(length=64), nullable=False),
        sa.Column("submitted_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("btrim(source_locale) <> ''", name="ck_journal_intake_source_locale"),
        sa.CheckConstraint("btrim(research_country) <> ''", name="ck_journal_intake_research_country"),
        sa.CheckConstraint("intake_hash ~ '^[0-9a-f]{64}$'", name="ck_journal_intake_hash"),
        sa.CheckConstraint("btrim(submitted_by) <> ''", name="ck_journal_intake_submitted_by"),
        sa.ForeignKeyConstraint(["content_case_id"], ["content_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_case_id", name="uq_journal_intake_specs_content_case_id"),
        sa.UniqueConstraint("intake_hash", name="uq_journal_intake_specs_intake_hash"),
    )
    op.create_index(
        "ix_journal_intake_specs_case",
        "journal_intake_specs",
        ["content_case_id"],
        unique=False,
    )
    op.create_table(
        "journal_required_locales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_case_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("declared_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role in ('source','translation')", name="ck_journal_required_locale_role"),
        sa.CheckConstraint("btrim(locale) <> ''", name="ck_journal_required_locale_value"),
        sa.CheckConstraint("btrim(declared_by) <> ''", name="ck_journal_required_locale_declared_by"),
        sa.ForeignKeyConstraint(["content_case_id"], ["content_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_case_id", "locale", name="uq_journal_required_locale_case_locale"),
    )
    op.create_index(
        "ix_journal_required_locales_case",
        "journal_required_locales",
        ["content_case_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_journal_required_locales_case", table_name="journal_required_locales")
    op.drop_table("journal_required_locales")
    op.drop_index("ix_journal_intake_specs_case", table_name="journal_intake_specs")
    op.drop_table("journal_intake_specs")
