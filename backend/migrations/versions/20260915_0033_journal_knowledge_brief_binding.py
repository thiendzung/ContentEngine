"""Bind one exact immutable KnowledgeBrief to one Journal ContentRun."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0033"
down_revision: str | None = "20260915_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "journal_knowledge_brief_bindings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("content_runs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "content_case_id",
            sa.Uuid(),
            sa.ForeignKey("content_cases.id"),
            nullable=False,
        ),
        sa.Column(
            "locale_variant_id",
            sa.Uuid(),
            sa.ForeignKey("locale_variants.id"),
            nullable=False,
        ),
        sa.Column(
            "knowledge_brief_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_briefs.id"),
            nullable=False,
        ),
        sa.Column("knowledge_brief_hash", sa.String(64), nullable=False),
        sa.Column("bound_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "knowledge_brief_hash ~ '^[0-9a-f]{64}$'",
            name="ck_journal_knowledge_brief_binding_hash",
        ),
        sa.CheckConstraint(
            "btrim(bound_by) <> ''",
            name="ck_journal_knowledge_brief_binding_actor",
        ),
    )
    op.create_index(
        "ix_journal_knowledge_brief_binding_case",
        "journal_knowledge_brief_bindings",
        ["content_case_id"],
    )
    op.create_index(
        "ix_journal_knowledge_brief_binding_brief",
        "journal_knowledge_brief_bindings",
        ["knowledge_brief_id"],
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION validate_journal_knowledge_brief_binding()
            RETURNS trigger AS $$
            DECLARE
                run_project uuid;
                run_case uuid;
                run_variant uuid;
                variant_case uuid;
                variant_locale text;
                brief_project uuid;
                brief_case uuid;
                brief_locale text;
                brief_hash text;
            BEGIN
                IF TG_OP <> 'INSERT' THEN
                    RAISE EXCEPTION 'journal_knowledge_brief_binding_is_immutable';
                END IF;

                SELECT project_id, content_case_id, locale_variant_id
                INTO run_project, run_case, run_variant
                FROM content_runs WHERE id = NEW.run_id;
                IF run_project IS NULL THEN
                    RAISE EXCEPTION 'journal_knowledge_brief_binding_run_not_found';
                END IF;
                IF run_case IS DISTINCT FROM NEW.content_case_id
                   OR run_variant IS DISTINCT FROM NEW.locale_variant_id THEN
                    RAISE EXCEPTION 'journal_knowledge_brief_binding_run_mismatch';
                END IF;

                SELECT content_case_id, locale
                INTO variant_case, variant_locale
                FROM locale_variants WHERE id = NEW.locale_variant_id;
                IF variant_case IS NULL OR variant_case IS DISTINCT FROM NEW.content_case_id THEN
                    RAISE EXCEPTION 'journal_knowledge_brief_binding_variant_mismatch';
                END IF;

                SELECT project_id, content_case_id, locale, snapshot_hash
                INTO brief_project, brief_case, brief_locale, brief_hash
                FROM knowledge_briefs WHERE id = NEW.knowledge_brief_id;
                IF brief_project IS NULL THEN
                    RAISE EXCEPTION 'journal_knowledge_brief_binding_brief_not_found';
                END IF;
                IF brief_project IS DISTINCT FROM run_project
                   OR brief_case IS DISTINCT FROM run_case
                   OR brief_locale IS DISTINCT FROM variant_locale
                   OR brief_hash IS DISTINCT FROM NEW.knowledge_brief_hash THEN
                    RAISE EXCEPTION 'journal_knowledge_brief_binding_brief_mismatch';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER journal_knowledge_brief_binding_guard
            BEFORE INSERT OR UPDATE OR DELETE ON journal_knowledge_brief_bindings
            FOR EACH ROW EXECUTE FUNCTION validate_journal_knowledge_brief_binding()
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS journal_knowledge_brief_binding_guard "
            "ON journal_knowledge_brief_bindings"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS validate_journal_knowledge_brief_binding()"))
    op.drop_index(
        "ix_journal_knowledge_brief_binding_brief",
        table_name="journal_knowledge_brief_bindings",
    )
    op.drop_index(
        "ix_journal_knowledge_brief_binding_case",
        table_name="journal_knowledge_brief_bindings",
    )
    op.drop_table("journal_knowledge_brief_bindings")
