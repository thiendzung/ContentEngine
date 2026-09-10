"""Seed the approved T05.10 Journal Outline prompt and recipe."""

# ruff: noqa: E501

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0018"
down_revision: str | None = "20260909_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROMPT_ID = "00000000-0000-0000-0000-000000000023"
_RECIPE_ID = "00000000-0000-0000-0000-000000000033"


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
    ]
    op.bulk_insert(
        prompt,
        [
            {
                "id": _PROMPT_ID,
                "prompt_key": "journal_outline",
                "version": 1,
                "purpose": "Generate one grounded Journal Outline from an exact human-approved Angle.",
                "body": (
                    "Return JSON only. Build one practical Journal Outline for the exact approved Angle. "
                    "Answer the reader's primary question immediately in primary_answer, then structure 3 to 8 meaningful sections. "
                    "Use only the supplied approved Angle, Opportunity, locked EvidenceSet, approved OriginalityPack and upstream context. "
                    "Every factual support ref and MOTGU-original ref must be copied exactly from supplied input. "
                    "Classify each answer/section as factual, motgu_original, editorial or mixed. "
                    "Factual sections require evidence refs; MOTGU-original sections require originality refs; mixed sections require both. "
                    "Every section needs a purpose, answer direction, claim guard and reader movement. "
                    "Internal-link targets are optional and must be useful, never quota-driven. "
                    "Do not invent MOTGU facts, artist intent, market formulas, investment claims, scarcity, sources or approval. "
                    "Do not merge other candidate Angles into a new primary direction. Avoid generic art-market filler and keyword-stuffed structure."
                ),
                "input_contract_json": {
                    "required": [
                        "approved_angle",
                        "journal_input_bundle_ref",
                        "opportunity",
                        "evidence_set",
                        "originality_pack",
                    ],
                    "forbidden": [
                        "raw_provider_payload",
                        "search_snippets",
                        "repository_context",
                        "secrets",
                    ],
                },
                "output_schema_json": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "primary_answer",
                        "primary_answer_support_type",
                        "primary_answer_evidence_refs",
                        "primary_answer_originality_refs",
                        "primary_answer_claim_guard",
                        "sections",
                    ],
                    "properties": {
                        "primary_answer": {"type": "string", "minLength": 1},
                        "primary_answer_support_type": {
                            "type": "string",
                            "enum": ["factual", "motgu_original", "editorial", "mixed"],
                        },
                        "primary_answer_evidence_refs": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                        },
                        "primary_answer_originality_refs": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                        },
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
                                    "support_type": {
                                        "type": "string",
                                        "enum": ["factual", "motgu_original", "editorial", "mixed"],
                                    },
                                    "evidence_refs": {
                                        "type": "array",
                                        "items": {"type": "string", "minLength": 1},
                                    },
                                    "originality_refs": {
                                        "type": "array",
                                        "items": {"type": "string", "minLength": 1},
                                    },
                                    "claim_guards": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {"type": "string", "minLength": 1},
                                    },
                                    "reader_movement": {"type": "string", "minLength": 1},
                                    "internal_link_targets": {
                                        "type": "array",
                                        "items": {"type": "string", "minLength": 1},
                                    },
                                },
                            },
                        },
                    },
                },
                "status": "active",
                "change_reason": "CE05 T05.10 exact Outline registry approved by Founder through merge of the implementation PR",
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
                "recipe_key": "journal_outline_v1",
                "version": 1,
                "selector_json": {"content_type": "journal", "task": "outline"},
                "recipe_json": {
                    "steps": [
                        "answer_primary_question_first",
                        "organize_reader_decision_path",
                        "map_factual_sections_to_evidence",
                        "map_motgu_specific_sections_to_originality",
                        "carry_claim_guards",
                        "encode_reader_movement",
                        "suggest_only_useful_internal_links",
                    ],
                    "constraints": [
                        "exact_approved_angle_only",
                        "grounded_in_locked_evidence",
                        "grounded_in_approved_originality",
                        "no_new_research",
                        "no_factual_invention",
                        "no_artist_intent_invention",
                        "no_pricing_formula",
                        "no_investment_or_scarcity_claims",
                        "human_first_machine_legible",
                        "usable_by_independent_vi_and_en_writers",
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
