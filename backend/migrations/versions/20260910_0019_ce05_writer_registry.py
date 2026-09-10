"""Seed the approved T05.11/T05.12 independent Journal writer prompts and recipes."""

# ruff: noqa: E501

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0019"
down_revision: str | None = "20260910_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROMPTS = (
    (
        "00000000-0000-0000-0000-000000000024",
        "journal_writer_vi",
        "Write one native Vietnamese Journal draft directly from the accepted Outline.",
        (
            "Return JSON only. Write a natural vi-VN Journal draft directly from the supplied accepted Outline and shared evidence. "
            "This is not a translation task and you must not inspect, infer from, quote or depend on an English draft. "
            "Answer the primary reader question early, then follow the Outline section order exactly. "
            "Write for a first-time art buyer in clear, calm, personal Vietnamese: useful before poetic, low-pressure, no luxury or investment framing. "
            "For each section copy evidence_refs and originality_refs exactly from that Outline section; do not add, remove or substitute support refs. "
            "Copy the Outline primary support refs exactly into lead_evidence_refs and lead_originality_refs. "
            "Use only supplied EvidenceSet facts, approved OriginalityPack material and explicit editorial interpretation. "
            "Do not invent current artwork price, sale status, location, artist intent, provenance, scarcity, market conclusions or MOTGU pricing method. "
            "If a new factual claim would be useful but is not supported by the input, do not write it as fact; place a concise description in unresolved_factual_claims. "
            "Internal-link intents may only use targets already present in the Outline. Keep the article human, specific and free of generic AI filler."
        ),
    ),
    (
        "00000000-0000-0000-0000-000000000025",
        "journal_writer_en",
        "Write one native English Journal draft directly from the accepted Outline.",
        (
            "Return JSON only. Write a natural English Journal draft directly from the supplied accepted Outline and shared evidence. "
            "This is an independent writing task: do not translate, inspect, infer from, quote or depend on a Vietnamese draft. "
            "Answer the primary reader question early, then follow the Outline section order exactly. "
            "Write for a first-time art buyer in clear, calm, personal English: useful before poetic, low-pressure, no luxury or investment framing. "
            "For each section copy evidence_refs and originality_refs exactly from that Outline section; do not add, remove or substitute support refs. "
            "Copy the Outline primary support refs exactly into lead_evidence_refs and lead_originality_refs. "
            "Use only supplied EvidenceSet facts, approved OriginalityPack material and explicit editorial interpretation. "
            "Do not invent current artwork price, sale status, location, artist intent, provenance, scarcity, market conclusions or MOTGU pricing method. "
            "If a new factual claim would be useful but is not supported by the input, do not write it as fact; place a concise description in unresolved_factual_claims. "
            "Internal-link intents may only use targets already present in the Outline. Keep the article human, specific and free of generic AI filler."
        ),
    ),
)

_RECIPES = (
    (
        "00000000-0000-0000-0000-000000000034",
        "journal_writer_vi_v1",
        "vi-VN",
        "writer_vi",
        "native_vi_from_outline",
    ),
    (
        "00000000-0000-0000-0000-000000000035",
        "journal_writer_en_v1",
        "en",
        "writer_en",
        "native_en_from_outline",
    ),
)


def _output_schema() -> dict[str, object]:
    section = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "section_id",
            "heading",
            "body_markdown",
            "evidence_refs",
            "originality_refs",
            "unresolved_factual_claims",
        ],
        "properties": {
            "section_id": {"type": "string", "minLength": 1},
            "heading": {"type": "string", "minLength": 1},
            "body_markdown": {"type": "string", "minLength": 1},
            "evidence_refs": {"type": "array", "items": {"type": "string"}},
            "originality_refs": {"type": "array", "items": {"type": "string"}},
            "unresolved_factual_claims": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "locale",
            "title",
            "standfirst",
            "lead_markdown",
            "lead_evidence_refs",
            "lead_originality_refs",
            "sections",
            "closing_markdown",
            "internal_link_intents",
            "unresolved_factual_claims",
        ],
        "properties": {
            "locale": {"type": "string", "enum": ["vi-VN", "en"]},
            "title": {"type": "string", "minLength": 1},
            "standfirst": {"type": "string", "minLength": 1},
            "lead_markdown": {"type": "string", "minLength": 1},
            "lead_evidence_refs": {"type": "array", "items": {"type": "string"}},
            "lead_originality_refs": {"type": "array", "items": {"type": "string"}},
            "sections": {"type": "array", "minItems": 3, "maxItems": 8, "items": section},
            "closing_markdown": {"type": "string", "minLength": 1},
            "internal_link_intents": {"type": "array", "items": {"type": "string"}},
            "unresolved_factual_claims": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
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
    for prompt_id, prompt_key, purpose, body in _PROMPTS:
        op.bulk_insert(
            prompt,
            [
                {
                    "id": prompt_id,
                    "prompt_key": prompt_key,
                    "version": 1,
                    "purpose": purpose,
                    "body": body,
                    "input_contract_json": {
                        "required": [
                            "locale",
                            "journal_outline_ref",
                            "outline",
                            "approved_angle",
                            "opportunity",
                            "evidence_set",
                            "originality_pack",
                            "independence_rule",
                            "hard_guard",
                        ],
                        "forbidden": [
                            "other_locale_draft",
                            "translation_source",
                            "raw_provider_payload",
                            "search_snippets",
                            "repository_context",
                            "secrets",
                        ],
                    },
                    "output_schema_json": _output_schema(),
                    "status": "active",
                    "change_reason": "CE05 T05.11/T05.12 independent bilingual writer registry approved through Founder merge",
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
    for recipe_id, recipe_key, locale, task, strategy in _RECIPES:
        op.bulk_insert(
            recipe,
            [
                {
                    "id": recipe_id,
                    "recipe_key": recipe_key,
                    "version": 1,
                    "selector_json": {
                        "content_type": "journal",
                        "locale": locale,
                        "task": task,
                    },
                    "recipe_json": {
                        "strategy": strategy,
                        "steps": [
                            "answer_primary_question_early",
                            "follow_outline_section_order",
                            "carry_exact_support_refs",
                            "write_native_locale_prose",
                            "preserve_claim_guards",
                            "declare_unsupported_new_facts_unresolved",
                            "close_with_low_pressure_next_step",
                        ],
                        "constraints": [
                            "accepted_outline_only",
                            "independent_locale_generation",
                            "no_translation_source",
                            "no_new_research",
                            "no_new_support_refs",
                            "no_current_artwork_fact_invention",
                            "no_artist_intent_invention",
                            "no_pricing_formula",
                            "no_investment_or_scarcity_claims",
                            "no_generic_ai_filler",
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
    for prompt_id, _prompt_key, _purpose, _body in _PROMPTS:
        op.execute(
            sa.text(
                "UPDATE prompt_definitions SET status = 'retired' "
                "WHERE id = CAST(:id AS uuid) AND status = 'active'"
            ).bindparams(id=prompt_id)
        )
        op.execute(
            sa.text("DELETE FROM prompt_definitions WHERE id = CAST(:id AS uuid)").bindparams(
                id=prompt_id
            )
        )
    for recipe_id, _recipe_key, _locale, _task, _strategy in _RECIPES:
        op.execute(
            sa.text(
                "UPDATE recipe_definitions SET status = 'retired' "
                "WHERE id = CAST(:id AS uuid) AND status = 'active'"
            ).bindparams(id=recipe_id)
        )
        op.execute(
            sa.text("DELETE FROM recipe_definitions WHERE id = CAST(:id AS uuid)").bindparams(
                id=recipe_id
            )
        )
