"""Add durable Founder coverage requirements and coverage-aware Angle/Outline contracts."""

# ruff: noqa: E501

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0035"
down_revision: str | None = "20260915_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANGLE_PROMPT_ID = "7d90f444-d78e-4bf5-8dc9-7f184f9e4b01"
_ANGLE_RECIPE_ID = "7d90f444-d78e-4bf5-8dc9-7f184f9e4b02"
_OUTLINE_PROMPT_ID = "7d90f444-d78e-4bf5-8dc9-7f184f9e4b03"
_OUTLINE_RECIPE_ID = "7d90f444-d78e-4bf5-8dc9-7f184f9e4b04"


def upgrade() -> None:
    op.add_column(
        "content_opportunities",
        sa.Column(
            "coverage_requirements_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )

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
    coverage_item = {
        "type": "object",
        "additionalProperties": False,
        "required": ["requirement_id", "status", "rationale"],
        "properties": {
            "requirement_id": {"type": "string", "minLength": 1},
            "status": {"type": "string", "enum": ["covered", "reduced"]},
            "rationale": {"type": "string", "minLength": 1},
        },
    }
    section_fields = [
        "section_id",
        "heading",
        "purpose",
        "answer_direction",
        "support_type",
        "evidence_refs",
        "originality_refs",
        "claim_guards",
        "reader_movement",
        "internal_link_targets",
        "coverage_requirement_ids",
    ]
    op.bulk_insert(
        prompt,
        [
            {
                "id": _ANGLE_PROMPT_ID,
                "prompt_key": "journal_angle_candidates",
                "version": 2,
                "purpose": "Generate grounded Journal Angle candidates with explicit Founder-promise coverage.",
                "body": (
                    "Return JSON only. Generate 3 to 5 meaningfully different Angle candidates. "
                    "Use only the supplied Opportunity, locked EvidenceSet, approved OriginalityPack and ContextManifest references. "
                    "For every supplied opportunity.coverage_requirements item, every candidate must return exactly one coverage row with the same requirement_id. "
                    "Use status covered when the candidate commits to satisfy that requirement; use reduced only when the candidate intentionally narrows it, and explain the reduction in rationale. "
                    "Never silently omit a Founder coverage requirement. Founder will see and approve any reduction explicitly. "
                    "Do not invent facts, claims, sources, approval or coverage requirement IDs. "
                    "Every evidence_refs and originality_refs value must be copied from supplied input."
                ),
                "input_contract_json": {
                    "required": ["input_bundle_ref", "opportunity", "evidence_set", "originality_pack"],
                    "forbidden": ["raw_provider_payload", "search_snippets", "repository_context", "secrets"],
                },
                "output_schema_json": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["candidates"],
                    "properties": {
                        "candidates": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 5,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "angle_id", "working_title", "reader_problem", "central_question",
                                    "core_promise", "point_of_view", "why_now", "evidence_refs",
                                    "originality_refs", "excluded_claims", "risks", "confidence", "locale",
                                    "coverage",
                                ],
                                "properties": {
                                    "angle_id": {"type": "string", "minLength": 1},
                                    "working_title": {"type": "string", "minLength": 1},
                                    "reader_problem": {"type": "string", "minLength": 1},
                                    "central_question": {"type": "string", "minLength": 1},
                                    "core_promise": {"type": "string", "minLength": 1},
                                    "point_of_view": {"type": "string", "minLength": 1},
                                    "why_now": {"type": "string", "minLength": 1},
                                    "evidence_refs": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                                    "originality_refs": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                                    "excluded_claims": {"type": "array", "items": {"type": "string"}},
                                    "risks": {"type": "array", "items": {"type": "string"}},
                                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                    "locale": {"type": "string", "minLength": 1},
                                    "coverage": {"type": "array", "items": coverage_item},
                                },
                            },
                        }
                    },
                },
                "status": "draft",
                "change_reason": "F7 real-pilot finding: make Founder promise reductions explicit before Angle approval.",
                "approved_by": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _OUTLINE_PROMPT_ID,
                "prompt_key": "journal_outline",
                "version": 2,
                "purpose": "Generate one grounded Journal Outline that preserves the approved Angle coverage commitments.",
                "body": (
                    "Return JSON only. Build one practical Journal Outline for the exact approved Angle. "
                    "Answer the reader's primary question immediately, then structure 3 to 8 meaningful sections. "
                    "Every Founder coverage requirement marked covered in approved_angle.candidate.coverage must be mapped to at least one section through coverage_requirement_ids. "
                    "Do not map requirements marked reduced, invent requirement IDs, or silently drop a covered requirement. "
                    "A section may map zero or multiple covered requirements. "
                    "Use only supplied evidence/originality refs and preserve claim guards. "
                    "Do not merge other candidate Angles into a new primary direction."
                ),
                "input_contract_json": {
                    "required": ["approved_angle", "journal_input_bundle_ref", "opportunity", "evidence_set", "originality_pack"],
                    "forbidden": ["raw_provider_payload", "search_snippets", "repository_context", "secrets"],
                },
                "output_schema_json": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "primary_answer", "primary_answer_support_type",
                        "primary_answer_evidence_refs", "primary_answer_originality_refs",
                        "primary_answer_claim_guard", "sections",
                    ],
                    "properties": {
                        "primary_answer": {"type": "string", "minLength": 1},
                        "primary_answer_support_type": {"type": "string", "enum": ["factual", "motgu_original", "editorial", "mixed"]},
                        "primary_answer_evidence_refs": {"type": "array", "items": {"type": "string", "minLength": 1}},
                        "primary_answer_originality_refs": {"type": "array", "items": {"type": "string", "minLength": 1}},
                        "primary_answer_claim_guard": {"type": "string", "minLength": 1},
                        "sections": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 8,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": section_fields,
                                "properties": {
                                    "section_id": {"type": "string", "minLength": 1},
                                    "heading": {"type": "string", "minLength": 1},
                                    "purpose": {"type": "string", "minLength": 1},
                                    "answer_direction": {"type": "string", "minLength": 1},
                                    "support_type": {"type": "string", "enum": ["factual", "motgu_original", "editorial", "mixed"]},
                                    "evidence_refs": {"type": "array", "items": {"type": "string", "minLength": 1}},
                                    "originality_refs": {"type": "array", "items": {"type": "string", "minLength": 1}},
                                    "claim_guards": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                                    "reader_movement": {"type": "string", "minLength": 1},
                                    "internal_link_targets": {"type": "array", "items": {"type": "string", "minLength": 1}},
                                    "coverage_requirement_ids": {"type": "array", "items": {"type": "string", "minLength": 1}},
                                },
                            },
                        },
                    },
                },
                "status": "draft",
                "change_reason": "F7 real-pilot finding: fail closed when Outline drops an approved Founder promise commitment.",
                "approved_by": None,
                "created_at": now,
                "updated_at": now,
            },
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
                "id": _ANGLE_RECIPE_ID,
                "recipe_key": "journal_angle_v1",
                "version": 2,
                "selector_json": {"content_type": "journal", "task": "angle"},
                "recipe_json": {
                    "steps": ["reader_problem", "central_question", "core_promise", "map_founder_coverage", "point_of_view", "why_now"],
                    "constraints": ["grounded_in_supplied_evidence", "grounded_in_approved_originality", "explicit_scope_reduction", "no_silent_promise_drop"],
                },
                "status": "draft",
                "approved_by": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _OUTLINE_RECIPE_ID,
                "recipe_key": "journal_outline_v1",
                "version": 2,
                "selector_json": {"content_type": "journal", "task": "outline"},
                "recipe_json": {
                    "steps": ["answer_primary_question_first", "organize_reader_decision_path", "map_covered_requirements_to_sections", "map_factual_sections_to_evidence", "carry_claim_guards"],
                    "constraints": ["exact_approved_angle_only", "no_silent_promise_drop", "grounded_in_locked_evidence", "no_new_research", "human_first_machine_legible"],
                },
                "status": "draft",
                "approved_by": None,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    op.execute(sa.text("UPDATE prompt_definitions SET status='retired', updated_at=:now WHERE id IN (CAST(:a AS uuid), CAST(:o AS uuid)) AND status='active'").bindparams(now=now, a=_ANGLE_PROMPT_ID, o=_OUTLINE_PROMPT_ID))
    op.execute(sa.text("UPDATE recipe_definitions SET status='retired', updated_at=:now WHERE id IN (CAST(:a AS uuid), CAST(:o AS uuid)) AND status='active'").bindparams(now=now, a=_ANGLE_RECIPE_ID, o=_OUTLINE_RECIPE_ID))
    op.execute(sa.text("DELETE FROM prompt_definitions WHERE id IN (CAST(:a AS uuid), CAST(:o AS uuid))").bindparams(a=_ANGLE_PROMPT_ID, o=_OUTLINE_PROMPT_ID))
    op.execute(sa.text("DELETE FROM recipe_definitions WHERE id IN (CAST(:a AS uuid), CAST(:o AS uuid))").bindparams(a=_ANGLE_RECIPE_ID, o=_OUTLINE_RECIPE_ID))
    op.execute(sa.text("UPDATE prompt_definitions SET status='active', updated_at=:now WHERE prompt_key IN ('journal_angle_candidates','journal_outline') AND version=1 AND status='retired'").bindparams(now=now))
    op.execute(sa.text("UPDATE recipe_definitions SET status='active', updated_at=:now WHERE recipe_key IN ('journal_angle_v1','journal_outline_v1') AND version=1 AND status='retired'").bindparams(now=now))
    op.drop_column("content_opportunities", "coverage_requirements_json")
