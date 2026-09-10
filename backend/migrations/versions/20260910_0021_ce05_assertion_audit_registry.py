"""Seed approved T05.14 Journal assertion-audit prompts and recipes."""

# ruff: noqa: E501

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0021"
down_revision: str | None = "20260910_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROMPTS = (
    (
        "00000000-0000-0000-0000-000000000028",
        "journal_assertion_audit_vi",
        "Extract and classify assertions from one immutable Vietnamese revised Journal draft.",
        (
            "Return JSON only. Audit the supplied immutable vi-VN draft; do not rewrite it. "
            "Process source_segments in the exact supplied order and copy each segment_id and source_text exactly. "
            "Every segment with required_assertive=true must be disposition=assertive and contain at least one audited assertion. "
            "For titles/headings you may use non_assertive only when they contain no proposition; otherwise audit them. "
            "Every assertion_text must be a verbatim substring of its source_text. "
            "Classify assertion_type as fact, brand_statement, artist_intent, interpretation, opinion, visual_observation, or practical_live_information. "
            "Classify support_status as supported, unsupported, contradicted, interpretation, or opinion. "
            "Use only evidence_refs and originality_refs listed as allowed for that exact source segment. Never add or substitute a support ref. "
            "Treat evidence_catalog as bounded support only; do not infer facts beyond its claim statement/excerpt. "
            "Distinguish factual authority from editorial guidance. Generic instructions to check current listing/status are guidance, not proof of any concrete current commerce fact. "
            "A negative guard such as saying price does not prove investment value is not an investment recommendation. "
            "Do not infer artist intent, specific artwork facts, current price/availability/location, market comparisons, scarcity, investment return or a universal fair-price formula. "
            "No research, Search, URL, tools, sibling draft or translation source. The audit may fail; do not soften a classification just to produce PASS."
        ),
    ),
    (
        "00000000-0000-0000-0000-000000000029",
        "journal_assertion_audit_en",
        "Extract and classify assertions from one immutable English revised Journal draft.",
        (
            "Return JSON only. Audit the supplied immutable English draft; do not rewrite it. "
            "Process source_segments in the exact supplied order and copy each segment_id and source_text exactly. "
            "Every segment with required_assertive=true must be disposition=assertive and contain at least one audited assertion. "
            "For titles/headings you may use non_assertive only when they contain no proposition; otherwise audit them. "
            "Every assertion_text must be a verbatim substring of its source_text. "
            "Classify assertion_type as fact, brand_statement, artist_intent, interpretation, opinion, visual_observation, or practical_live_information. "
            "Classify support_status as supported, unsupported, contradicted, interpretation, or opinion. "
            "Use only evidence_refs and originality_refs listed as allowed for that exact source segment. Never add or substitute a support ref. "
            "Treat evidence_catalog as bounded support only; do not infer facts beyond its claim statement/excerpt. "
            "Distinguish factual authority from editorial guidance. The sentence about using the most recent listing information is reader guidance and cannot validate a concrete current commerce fact. "
            "The sentence that sale status/location should not create urgency and do not by themselves establish value must be classified without pretending that broader value wording is an externally proven universal fact. "
            "A negative guard such as saying price does not prove investment value is not an investment recommendation. "
            "Do not infer artist intent, specific artwork facts, current price/availability/location, market comparisons, scarcity, investment return or a universal fair-price formula. "
            "No research, Search, URL, tools, sibling draft or translation source. The audit may fail; do not soften a classification just to produce PASS."
        ),
    ),
)

_RECIPES = (
    (
        "00000000-0000-0000-0000-000000000038",
        "journal_assertion_audit_vi_v1",
        "vi-VN",
        "assertion_audit_vi",
    ),
    (
        "00000000-0000-0000-0000-000000000039",
        "journal_assertion_audit_en_v1",
        "en",
        "assertion_audit_en",
    ),
)


def _output_schema() -> dict[str, object]:
    assertion = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "assertion_text",
            "assertion_type",
            "support_status",
            "severity",
            "evidence_refs",
            "originality_refs",
            "rationale",
        ],
        "properties": {
            "assertion_text": {"type": "string", "minLength": 1},
            "assertion_type": {
                "type": "string",
                "enum": [
                    "fact",
                    "brand_statement",
                    "artist_intent",
                    "interpretation",
                    "opinion",
                    "visual_observation",
                    "practical_live_information",
                ],
            },
            "support_status": {
                "type": "string",
                "enum": ["supported", "unsupported", "contradicted", "interpretation", "opinion"],
            },
            "severity": {
                "type": "string",
                "enum": ["none", "low", "medium", "high", "critical"],
            },
            "evidence_refs": {"type": "array", "items": {"type": "string"}},
            "originality_refs": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string", "minLength": 1},
        },
    }
    segment = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "segment_id",
            "source_text",
            "disposition",
            "non_assertive_reason",
            "assertions",
        ],
        "properties": {
            "segment_id": {"type": "string", "minLength": 1},
            "source_text": {"type": "string", "minLength": 1},
            "disposition": {"type": "string", "enum": ["assertive", "non_assertive"]},
            "non_assertive_reason": {"type": "string"},
            "assertions": {
                "type": "array",
                "minItems": 0,
                "maxItems": 4,
                "items": assertion,
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["locale", "segments"],
        "properties": {
            "locale": {"type": "string", "enum": ["vi-VN", "en"]},
            "segments": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": segment,
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
                            "source_draft_ref",
                            "source_draft",
                            "source_segments",
                            "evidence_catalog",
                            "originality_pack",
                            "audit_policy",
                        ],
                        "forbidden": [
                            "other_locale_draft",
                            "translation_source",
                            "raw_provider_payload",
                            "search_snippets",
                            "repository_context",
                            "secrets",
                            "tool_results",
                        ],
                    },
                    "output_schema_json": _output_schema(),
                    "status": "active",
                    "change_reason": "CE05 T05.14 assertion-audit registry approved through Founder merge",
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
    for recipe_id, recipe_key, locale, task in _RECIPES:
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
                        "strategy": "bounded_assertion_extraction_and_deterministic_hard_gate",
                        "steps": [
                            "bind_exact_revised_draft",
                            "segment_visible_copy_deterministically",
                            "extract_and_classify_every_required_segment",
                            "map_only_location_allowed_evidence_and_originality_refs",
                            "derive_claim_refs_from_evidence_rows",
                            "apply_deterministic_critical_support_gate",
                            "persist_assertion_audit_and_quality_evaluation",
                        ],
                        "constraints": [
                            "audit_only_no_rewrite",
                            "exact_source_substrings",
                            "locked_evidence_set_only",
                            "approved_originality_pack_only",
                            "no_new_research",
                            "no_tool_calls",
                            "no_sibling_draft",
                            "no_aggregate_score_override",
                            "critical_unsupported_or_contradicted_fails",
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
    for recipe_id, _recipe_key, _locale, _task in _RECIPES:
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
