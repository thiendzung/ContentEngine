"""Seed the bounded English post-Assertion-Audit revision registry."""

# ruff: noqa: E501

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0022"
down_revision: str | None = "20260910_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROMPT_ID = "00000000-0000-0000-0000-000000000040"
_RECIPE_ID = "00000000-0000-0000-0000-000000000040"


def _output_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["locale", "revisions"],
        "properties": {
            "locale": {"type": "string", "enum": ["en"]},
            "revisions": {
                "type": "array",
                "minItems": 5,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["segment_id", "source_text", "replacement_text"],
                    "properties": {
                        "segment_id": {"type": "string", "minLength": 1},
                        "source_text": {"type": "string", "minLength": 1},
                        "replacement_text": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    }


def upgrade() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    prompt = sa.table(
        "prompt_definitions",
        sa.column("id", sa.Uuid()),
        sa.column("prompt_key", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("purpose", sa.Text()),
        sa.column("body", sa.Text()),
        sa.column("input_contract_json", sa.JSON()),
        sa.column("output_schema_json", sa.JSON()),
        sa.column("status", sa.String()),
        sa.column("change_reason", sa.Text()),
        sa.column("approved_by", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    op.bulk_insert(
        prompt,
        [
            {
                "id": _PROMPT_ID,
                "prompt_key": "journal_post_audit_revise_en",
                "version": 1,
                "purpose": "Replace exactly five persisted unsupported English Journal assertions without rewriting the draft.",
                "body": (
                    "Return JSON only. Revise only the five exact target segments from the supplied immutable English draft. "
                    "Return exactly one replacement sentence for each target segment_id and no other fields. "
                    "Copy source_text exactly. Do not rewrite the article, title, standfirst, headings or any non-target copy. "
                    "Do not add Evidence or Originality refs, factual claims, current artwork facts, artist intent, market claims, pricing formulas, investment framing or scarcity pressure. "
                    "Recast the persisted unsupported claims as bounded reader guidance or editorial framing while preserving the supported neighboring evidence. "
                    "Use no research, Search, URL, tools, sibling draft or translation input."
                ),
                "input_contract_json": {
                    "required": [
                        "locale",
                        "source_draft_ref",
                        "source_draft",
                        "failed_assertion_audit_ref",
                        "failed_quality_evaluation_ref",
                        "target_findings",
                        "target_findings_hash",
                        "post_audit_revision_policy",
                    ],
                    "forbidden": [
                        "other_locale_draft",
                        "translation_source",
                        "raw_provider_payload",
                        "search_snippets",
                        "repository_context",
                        "secrets",
                        "tool_results",
                        "sibling_draft",
                    ],
                },
                "output_schema_json": _output_schema(),
                "status": "active",
                "change_reason": "CE05 T05.14 bounded English post-audit remediation approved through Founder merge",
                "approved_by": "founder",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    recipe = sa.table(
        "recipe_definitions",
        sa.column("id", sa.Uuid()),
        sa.column("recipe_key", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("selector_json", sa.JSON()),
        sa.column("recipe_json", sa.JSON()),
        sa.column("status", sa.String()),
        sa.column("approved_by", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    op.bulk_insert(
        recipe,
        [
            {
                "id": _RECIPE_ID,
                "recipe_key": "journal_post_audit_revise_en_v1",
                "version": 1,
                "selector_json": {
                    "content_type": "journal",
                    "locale": "en",
                    "task": "post_audit_revise_en",
                },
                "recipe_json": {
                    "strategy": "bounded_exact_five_sentence_replacements",
                    "steps": [
                        "bind_exact_source_v2",
                        "bind_persisted_failed_audit_and_quality_evaluation",
                        "return_exactly_five_replacements",
                        "apply_replacements_deterministically",
                        "validate_full_draft_and_non_target_immutability",
                        "persist_immutable_draft_v3",
                    ],
                    "constraints": [
                        "same_existing_en_writer_run",
                        "source_v2_immutable",
                        "no_new_evidence_or_originality_refs",
                        "no_research_or_tool_calls",
                        "no_sibling_locale_input",
                        "no_translation",
                        "no_manual_edit",
                        "exact_rerun_reuses_v3",
                    ],
                },
                "status": "active",
                "approved_by": "founder",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE prompt_definitions SET status = 'retired' "
            "WHERE id = CAST(:id AS uuid) AND status = 'active'"
        ).bindparams(id=_PROMPT_ID)
    )
    op.execute(
        sa.text("DELETE FROM prompt_definitions WHERE id = CAST(:id AS uuid)").bindparams(
            id=_PROMPT_ID
        )
    )
    op.execute(
        sa.text(
            "UPDATE recipe_definitions SET status = 'retired' "
            "WHERE id = CAST(:id AS uuid) AND status = 'active'"
        ).bindparams(id=_RECIPE_ID)
    )
    op.execute(
        sa.text("DELETE FROM recipe_definitions WHERE id = CAST(:id AS uuid)").bindparams(
            id=_RECIPE_ID
        )
    )
