"""Seed approved T05.13 bounded Journal review/revise prompts and recipes."""

# ruff: noqa: E501

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0020"
down_revision: str | None = "20260910_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROMPTS = (
    (
        "00000000-0000-0000-0000-000000000026",
        "journal_review_revise_vi",
        "Review and revise one immutable Vietnamese Journal draft without new research or facts.",
        (
            "Return JSON only. Review and revise the supplied immutable vi-VN source draft directly. "
            "This is not a translation task and you must not inspect, infer from, quote or depend on an English draft. "
            "Preserve the accepted Outline section IDs and order exactly. Copy every lead/section evidence_ref and originality_ref exactly; do not add, remove or substitute support refs. "
            "Resolve every source unresolved_factual_claim by either removing the unsupported intended factual claim or rewriting the passage as general reader guidance that does not require the missing fact. "
            "A note that specific artwork data is absent is not itself an unresolved factual claim when the revised prose does not assert that missing data. "
            "Never fabricate current artwork identity, dimensions, material, price, sale status, location, packaging/shipping/insurance amounts, artist intent, provenance, scarcity, comparisons or market conclusions. "
            "Do not create a fair-price formula, investment framing, luxury pressure or scarcity pressure. "
            "Improve native Vietnamese clarity and remove internal/technical wording where possible while preserving the low-pressure MOTGU posture and the article's practical checklist value. "
            "Every document-level and section-level unresolved_factual_claims array in the final JSON must be empty. "
            "Use only the supplied source draft, accepted Outline, EvidenceSet, OriginalityPack and LocaleVariant. No research, Search, URL or tool use."
        ),
    ),
    (
        "00000000-0000-0000-0000-000000000027",
        "journal_review_revise_en",
        "Review and revise one immutable English Journal draft without new research or facts.",
        (
            "Return JSON only. Review and revise the supplied immutable English source draft directly. "
            "This is an independent English revision task: do not translate, inspect, infer from, quote or depend on a Vietnamese draft. "
            "Preserve the accepted Outline section IDs and order exactly. Copy every lead/section evidence_ref and originality_ref exactly; do not add, remove or substitute support refs. "
            "Resolve every source unresolved_factual_claim by either removing the unsupported intended factual claim or rewriting the passage as general reader guidance that does not require the missing fact. "
            "A note that specific artwork data is absent is not itself an unresolved factual claim when the revised prose does not assert that missing data. "
            "Never fabricate current artwork identity, dimensions, material, price, sale status, location, packaging/shipping/insurance amounts, artist intent, provenance, scarcity, comparisons or market conclusions. "
            "Do not create a fair-price formula, investment framing, luxury pressure or scarcity pressure. "
            "Improve natural English and remove internal/technical wording such as implementation labels where possible while preserving the low-pressure MOTGU posture and the article's practical checklist value. "
            "Every document-level and section-level unresolved_factual_claims array in the final JSON must be empty. "
            "Use only the supplied source draft, accepted Outline, EvidenceSet, OriginalityPack and LocaleVariant. No research, Search, URL or tool use."
        ),
    ),
)

_RECIPES = (
    (
        "00000000-0000-0000-0000-000000000036",
        "journal_review_revise_vi_v1",
        "vi-VN",
        "review_revise_vi",
        "bounded_native_vi_review_revise",
    ),
    (
        "00000000-0000-0000-0000-000000000037",
        "journal_review_revise_en_v1",
        "en",
        "review_revise_en",
        "bounded_native_en_review_revise",
    ),
)


def _output_schema() -> dict[str, object]:
    unresolved = {
        "type": "array",
        "maxItems": 0,
        "items": {"type": "string", "minLength": 1},
    }
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
            "unresolved_factual_claims": unresolved,
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
            "unresolved_factual_claims": unresolved,
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
                            "independence_rule",
                            "writer_handoff_ref",
                            "journal_outline_ref",
                            "content_case",
                            "locale_variant",
                            "outline",
                            "approved_angle",
                            "opportunity",
                            "evidence_set",
                            "originality_pack",
                            "hard_guard",
                            "source_draft_ref",
                            "source_draft",
                            "source_unresolved_factual_claims",
                            "revision_policy",
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
                    "change_reason": "CE05 T05.13 bounded review/revise registry approved through Founder merge",
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
                            "bind_exact_source_draft",
                            "inspect_declared_unresolved_items",
                            "remove_or_soften_unsupported_intended_claims",
                            "preserve_exact_outline_and_support_refs",
                            "improve_native_locale_clarity",
                            "return_zero_unresolved_factual_claims",
                        ],
                        "constraints": [
                            "exact_source_draft_only",
                            "accepted_outline_only",
                            "independent_locale_revision",
                            "no_translation_source",
                            "no_new_research",
                            "no_new_support_refs",
                            "no_missing_fact_invention",
                            "no_artist_intent_invention",
                            "no_pricing_formula",
                            "no_investment_or_scarcity_claims",
                            "low_pressure_motgu_posture",
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
