"""Seed QA-01 Reader Value and Search/AI readiness prompt/recipe registry.

Revision ID: 20260922_0038
Revises: 20260921_0037
"""

# ruff: noqa: E501

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0038"
down_revision: str | None = "20260921_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _criteria(stage: str) -> list[str]:
    if stage == "reader_value":
        return [
            "primary_problem_answered",
            "reader_transformation",
            "practical_value",
            "non_generic",
            "originality_visible",
            "conversion_integrity",
        ]
    return [
        "intent_match",
        "title_heading_coherence",
        "answer_passage",
        "entity_clarity",
        "internal_links",
        "metadata_readiness",
        "structured_data_fit",
        "freshness",
        "keyword_stuffing",
        "fake_faq",
    ]


def _schema(stage: str, locale: str) -> dict[str, object]:
    criterion = {
        "type": "object",
        "additionalProperties": False,
        "required": ["key", "result", "finding", "repair_suggestion"],
        "properties": {
            "key": {"type": "string", "enum": _criteria(stage)},
            "result": {"type": "string", "enum": ["pass", "warn", "fail"]},
            "finding": {"type": "string", "minLength": 1},
            "repair_suggestion": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["locale", "result", "summary", "criteria"],
        "properties": {
            "locale": {"type": "string", "enum": [locale]},
            "result": {"type": "string", "enum": ["pass", "warn", "fail"]},
            "summary": {"type": "string", "minLength": 1},
            "criteria": {
                "type": "array",
                "minItems": len(_criteria(stage)),
                "maxItems": len(_criteria(stage)),
                "items": criterion,
            },
        },
    }


_READER_BODY = (
    "Return JSON only. Audit the supplied immutable Journal draft for READER VALUE; do not rewrite it. "
    "Judge the exact intended audience, situation, need, primary question, desired action and reader_before to reader_after transformation supplied in the input. "
    "Evaluate the criteria in the exact order given by evaluation_policy.criteria. "
    "primary_problem_answered: does the draft directly resolve the main reader problem/question rather than circle around it? "
    "reader_transformation: does the draft plausibly move this reader from reader_before toward reader_after without claiming behaviour that cannot be observed? "
    "practical_value: does the reader leave with a useful understanding, decision aid or next step? "
    "non_generic: fail or warn when the copy is mostly interchangeable generic advice, filler, repetition or AI-like summary. "
    "originality_visible: judge whether the supplied MOTGU originality is materially used; do not invent originality. "
    "conversion_integrity: the next step must be useful and low-pressure, not manipulative, fake scarcity or a forced sales jump. "
    "This is not a factual re-audit and not research: factual/source integrity is already handled by the upstream Assertion Audit and Source-copy gate. "
    "Do not use a numeric score. The overall result must be FAIL if any criterion fails, WARN if none fail and at least one warns, otherwise PASS. "
    "The audit may fail; never soften a finding to allow SEO or publication."
)

_SEARCH_BODY = (
    "Return JSON only. Audit the supplied immutable Journal draft for SEARCH AND AI READINESS; do not rewrite it and do not research. "
    "This stage is allowed only because Reader Value already passed or warned. It cannot override Reader Value. "
    "Evaluate criteria in the exact order given by evaluation_policy.criteria. "
    "intent_match: the visible answer matches the primary intent/query without narrowing the article into keyword bait. "
    "title_heading_coherence: title and headings describe the actual answer clearly. "
    "answer_passage: the main answer can be understood in a concise passage near where the reader needs it; do not require a forced FAQ. "
    "entity_clarity: people, places, materials, products or policies are named unambiguously when the supplied content supports them. "
    "internal_links: link intents are useful and contextual, not stuffed. "
    "metadata_readiness: judge whether the supplied title/standfirst/content can support clear metadata; do not invent metadata fields that are not present. "
    "structured_data_fit: PASS when no special structured data is needed; WARN/FAIL only when the draft itself creates a mismatch or unsupported markup expectation. "
    "freshness: flag time-sensitive claims or guidance that needs a clear refresh path; do not perform live verification. "
    "keyword_stuffing: PASS means no stuffing; WARN/FAIL means repetitive query phrasing harms the copy. "
    "fake_faq: PASS means no artificial FAQ/query fan-out; WARN/FAIL means sections exist mainly to manufacture search variants. "
    "Do not use a numeric score. Overall result is FAIL if any criterion fails, WARN if none fail and at least one warns, otherwise PASS."
)

_PROMPTS = (
    ("00000000-0000-0000-0000-000000000050", "journal_reader_value_vi", "vi-VN", "reader_value", _READER_BODY),
    ("00000000-0000-0000-0000-000000000051", "journal_reader_value_en", "en", "reader_value", _READER_BODY),
    ("00000000-0000-0000-0000-000000000052", "journal_search_ai_readiness_vi", "vi-VN", "search_ai", _SEARCH_BODY),
    ("00000000-0000-0000-0000-000000000053", "journal_search_ai_readiness_en", "en", "search_ai", _SEARCH_BODY),
)

_RECIPES = (
    ("00000000-0000-0000-0000-000000000054", "journal_reader_value_vi_v1", "vi-VN", "reader_value_vi", "reader_value"),
    ("00000000-0000-0000-0000-000000000055", "journal_reader_value_en_v1", "en", "reader_value_en", "reader_value"),
    ("00000000-0000-0000-0000-000000000056", "journal_search_ai_readiness_vi_v1", "vi-VN", "search_ai_readiness_vi", "search_ai"),
    ("00000000-0000-0000-0000-000000000057", "journal_search_ai_readiness_en_v1", "en", "search_ai_readiness_en", "search_ai"),
)


def upgrade() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    prompt_table = sa.table(
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
    for prompt_id, prompt_key, locale, stage, body in _PROMPTS:
        required = [
            "locale",
            "stage",
            "source_draft_ref",
            "source_draft",
            "content_case",
            "content_opportunity",
            "locale_variant",
            "source_copy",
            "evaluation_policy",
        ]
        if stage == "search_ai":
            required.append("reader_value")
        op.bulk_insert(
            prompt_table,
            [{
                "id": prompt_id,
                "prompt_key": prompt_key,
                "version": 1,
                "purpose": f"QA-01 {stage} audit for one immutable {locale} Journal draft.",
                "body": body,
                "input_contract_json": {
                    "required": required,
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
                "output_schema_json": _schema(stage, locale),
                "status": "active",
                "change_reason": "QA-01 Reader Value before Search/AI readiness; no aggregate score override.",
                "approved_by": "founder",
                "created_at": now,
                "updated_at": now,
            }],
        )

    recipe_table = sa.table(
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
    for recipe_id, recipe_key, locale, task_key, stage in _RECIPES:
        op.bulk_insert(
            recipe_table,
            [{
                "id": recipe_id,
                "recipe_key": recipe_key,
                "version": 1,
                "selector_json": {
                    "content_type": "journal",
                    "locale": locale,
                    "task": task_key,
                },
                "recipe_json": {
                    "strategy": f"qa01_{stage}_audit_only",
                    "criteria": _criteria(stage),
                    "constraints": [
                        "exact_immutable_draft_only",
                        "no_research",
                        "no_tools",
                        "no_rewrite",
                        "no_numeric_score",
                        "reader_value_precedes_discovery",
                        "search_ai_cannot_override_reader_value",
                        "human_final_gate_remains_required",
                    ],
                },
                "status": "active",
                "approved_by": "founder",
                "created_at": now,
                "updated_at": now,
            }],
        )


def downgrade() -> None:
    for prompt_id, _key, _locale, _stage, _body in _PROMPTS:
        op.execute(
            sa.text("DELETE FROM prompt_definitions WHERE id = CAST(:id AS uuid)").bindparams(
                id=prompt_id
            )
        )
    for recipe_id, _key, _locale, _task, _stage in _RECIPES:
        op.execute(
            sa.text("DELETE FROM recipe_definitions WHERE id = CAST(:id AS uuid)").bindparams(
                id=recipe_id
            )
        )
