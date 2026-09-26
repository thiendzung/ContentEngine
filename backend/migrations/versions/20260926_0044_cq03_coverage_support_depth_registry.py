"""Seed CQ-03 coverage support-depth prompt/recipe registry.

Revision ID: 20260926_0044
Revises: 20260925_0043
"""

# ruff: noqa: E501

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0044"
down_revision: str | None = "20260925_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BODY = (
    "Return JSON only. Assess whether each exact Founder coverage requirement has sufficient semantic support BEFORE Angle generation. "
    "Use only the supplied locked EvidenceSet rows and approved MOTGU-owned Originality items. "
    "Do not research, browse, use tools, infer hidden facts, invent artist intent, or convert search rank/context into factual support. "
    "For each coverage requirement return exactly one status: evidence_supported, originality_supported, mixed, or unresolved. "
    "evidence_supported requires one or more supplied evidence_refs whose relation is supports. "
    "originality_supported requires one or more supplied MOTGU originality source_refs and means first-party support, not external factual proof. "
    "mixed requires both. "
    "Use caveat_evidence_refs for qualifies, contradicts, or context_only evidence. "
    "Any contradiction that materially conflicts with the claimed support must leave the requirement unresolved. "
    "Lexical overlap alone is never semantic proof. Do not use numeric scores. "
    "Every requirement must appear exactly once; cite only exact supplied refs. "
    "For unresolved requirements provide one or more concrete gaps needed before Angle may proceed."
)


def _schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "items"],
        "properties": {
            "schema_version": {"type": "integer", "enum": [1]},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "requirement_id",
                        "status",
                        "evidence_refs",
                        "caveat_evidence_refs",
                        "originality_refs",
                        "rationale",
                        "gaps",
                    ],
                    "properties": {
                        "requirement_id": {"type": "string", "minLength": 1},
                        "status": {
                            "type": "string",
                            "enum": [
                                "evidence_supported",
                                "originality_supported",
                                "mixed",
                                "unresolved",
                            ],
                        },
                        "evidence_refs": {
                            "type": "array",
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1},
                        },
                        "caveat_evidence_refs": {
                            "type": "array",
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1},
                        },
                        "originality_refs": {
                            "type": "array",
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1},
                        },
                        "rationale": {"type": "string", "minLength": 1},
                        "gaps": {
                            "type": "array",
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
        },
    }


_PROMPTS = (
    (
        "c0030000-0000-4000-8000-000000000001",
        "journal_coverage_support_depth_en",
        "en",
    ),
    (
        "c0030000-0000-4000-8000-000000000002",
        "journal_coverage_support_depth_vi",
        "vi-VN",
    ),
)

_RECIPES = (
    (
        "c0030000-0000-4000-8000-000000000003",
        "journal_coverage_support_depth_en_v1",
        "en",
    ),
    (
        "c0030000-0000-4000-8000-000000000004",
        "journal_coverage_support_depth_vi_v1",
        "vi-VN",
    ),
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
    for prompt_id, prompt_key, locale in _PROMPTS:
        op.bulk_insert(
            prompt_table,
            [{
                "id": prompt_id,
                "prompt_key": prompt_key,
                "version": 1,
                "purpose": f"CQ-03 exact coverage support-depth assessment for {locale} Journal input.",
                "body": _BODY,
                "input_contract_json": {
                    "required": [
                        "schema_version",
                        "coverage_requirements",
                        "evidence_set",
                        "evidence",
                        "originality_pack",
                        "assessment_policy",
                    ],
                    "forbidden": [
                        "raw_provider_payload",
                        "search_snippets",
                        "repository_context",
                        "secrets",
                        "tool_results",
                    ],
                },
                "output_schema_json": _schema(),
                "status": "active",
                "change_reason": "CQ-03 bounded semantic support gate before Angle; no numeric score or research.",
                "approved_by": "mg",
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
    for recipe_id, recipe_key, locale in _RECIPES:
        op.bulk_insert(
            recipe_table,
            [{
                "id": recipe_id,
                "recipe_key": recipe_key,
                "version": 1,
                "selector_json": {
                    "content_type": "journal",
                    "locale": locale,
                    "task": "coverage_support_depth",
                },
                "recipe_json": {
                    "strategy": "cq03_exact_coverage_support_depth",
                    "constraints": [
                        "locked_evidence_only",
                        "approved_originality_only",
                        "exact_refs_only",
                        "no_research",
                        "no_tools",
                        "no_rewrite",
                        "no_numeric_score",
                        "lexical_overlap_not_semantic_proof",
                        "unresolved_blocks_angle",
                    ],
                },
                "status": "active",
                "approved_by": "mg",
                "created_at": now,
                "updated_at": now,
            }],
        )


def downgrade() -> None:
    for prompt_id, _key, _locale in _PROMPTS:
        op.execute(
            sa.text(
                "UPDATE prompt_definitions SET status = 'retired' "
                "WHERE id = CAST(:id AS uuid) AND status = 'active'"
            ).bindparams(id=prompt_id)
        )
        op.execute(
            sa.text(
                "DELETE FROM prompt_definitions "
                "WHERE id = CAST(:id AS uuid) AND status = 'retired'"
            ).bindparams(id=prompt_id)
        )
    for recipe_id, _key, _locale in _RECIPES:
        op.execute(
            sa.text(
                "UPDATE recipe_definitions SET status = 'retired' "
                "WHERE id = CAST(:id AS uuid) AND status = 'active'"
            ).bindparams(id=recipe_id)
        )
        op.execute(
            sa.text(
                "DELETE FROM recipe_definitions "
                "WHERE id = CAST(:id AS uuid) AND status = 'retired'"
            ).bindparams(id=recipe_id)
        )
