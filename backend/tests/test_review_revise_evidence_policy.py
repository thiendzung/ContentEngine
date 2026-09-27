from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from app.modules.content_engine.journal.human_voice import (
    HUMAN_VOICE_POLICY_VERSION,
    HUMAN_VOICE_RENDER_PROTOCOL_VERSION,
)
from app.modules.content_engine.journal.human_voice_trace import (
    HUMAN_VOICE_TRACE_REQUIRED_REVIEW_REVISE_GENERATORS,
)
from app.modules.content_engine.journal.review_revise import (
    REVIEW_REVISE_GENERATOR_VERSION,
    _evidence_relation_policy,
    _human_voice_evidence_catalog,
    _human_voice_originality_catalog,
    _revision_model_input,
)
from app.modules.content_engine.journal.review_revise_agent_bridge import (
    render_review_revise_prompt,
)
from app.modules.content_engine.journal.writer import (
    JournalDraft,
    WriterGenerationError,
    WriterInput,
)
from app.modules.content_engine.models import PromptDefinition, RecipeDefinition
from app.modules.harness.models import Artifact


def _writer_input_with_relations(relations: list[tuple[str, str]]) -> WriterInput:
    evidence = [
        {
            "evidence_id": evidence_id,
            "relation": relation,
            "claim_id": str(uuid4()),
            "claim_statement": f"claim for {evidence_id}",
        }
        for evidence_id, relation in relations
    ]
    return cast(
        WriterInput,
        SimpleNamespace(
            model_input={
                "locale": "en",
                "evidence_set": {"evidence": evidence},
                "originality_pack": {"items": []},
            }
        ),
    )


def test_review_revise_v6_exposes_exact_evidence_relation_policy() -> None:
    writer_input = _writer_input_with_relations(
        [
            ("e-support", "supports"),
            ("e-qualify", "qualifies"),
            ("e-context", "context_only"),
            ("e-contradict", "contradicts"),
        ]
    )

    policy = _evidence_relation_policy(writer_input)

    assert REVIEW_REVISE_GENERATOR_VERSION == "ce05.journal_review_revise.v6"
    assert policy == {
        "supportive_relations": ["supports", "qualifies"],
        "non_supportive_relations": ["context_only", "contradicts"],
        "relations_by_evidence_id": {
            "e-support": "supports",
            "e-qualify": "qualifies",
            "e-context": "context_only",
            "e-contradict": "contradicts",
        },
    }


def test_review_revise_v6_rejects_unknown_or_duplicate_relation_rows() -> None:
    unknown = _writer_input_with_relations([("e-1", "maybe")])
    with pytest.raises(
        WriterGenerationError,
        match="review_revise_evidence_relation_invalid",
    ):
        _evidence_relation_policy(unknown)

    duplicate = _writer_input_with_relations(
        [("e-1", "supports"), ("e-1", "context_only")]
    )
    with pytest.raises(
        WriterGenerationError,
        match="review_revise_evidence_relation_duplicate",
    ):
        _evidence_relation_policy(duplicate)


def test_human_voice_guard_authority_excludes_claim_and_writer_instruction_text() -> None:
    writer_input = cast(
        WriterInput,
        SimpleNamespace(
            model_input={
                "locale": "en",
                "evidence_set": {
                    "evidence": [
                        {
                            "evidence_id": "e-support",
                            "relation": "supports",
                            "claim_id": str(uuid4()),
                            "claim_statement": 'Generated claim says "quoted claim" at 777 cm.',
                            "excerpt": "The reviewed source records 20 cm.",
                        },
                        {
                            "evidence_id": "e-context",
                            "relation": "context_only",
                            "claim_id": str(uuid4()),
                            "claim_statement": "Context claim 444 cm.",
                            "excerpt": "Context-only source says 555 cm.",
                        },
                    ]
                },
                "originality_pack": {
                    "items": [
                        {
                            "source_ref": "motgu:approved",
                            "material": "Approved MOTGU material records 30 cm.",
                            "writer_use": 'Instruction says use 888 cm and "guidance quote".',
                            "guardrails": "Do not invent facts.",
                        }
                    ]
                },
            }
        ),
    )

    assert _human_voice_evidence_catalog(writer_input) == {
        "e-support": ("The reviewed source records 20 cm.",),
        "e-context": (),
    }
    assert _human_voice_originality_catalog(writer_input) == {
        "motgu:approved": ("Approved MOTGU material records 30 cm.",),
    }
    assert (
        REVIEW_REVISE_GENERATOR_VERSION
        in HUMAN_VOICE_TRACE_REQUIRED_REVIEW_REVISE_GENERATORS
    )


def test_revision_model_input_binds_relation_policy_and_full_prose_review_rules() -> None:
    writer_input = _writer_input_with_relations(
        [("e-support", "supports"), ("e-context", "context_only")]
    )
    source_artifact = cast(
        Artifact,
        SimpleNamespace(id=uuid4(), version=1, content_hash="a" * 64),
    )
    source_draft = cast(
        JournalDraft,
        SimpleNamespace(
            lead_evidence_refs=("e-support",),
            lead_originality_refs=(),
            unresolved_factual_claims=(),
            sections=(),
            to_dict=lambda: {
                "locale": "en",
                "lead_evidence_refs": ["e-support"],
                "lead_originality_refs": [],
                "unresolved_factual_claims": [],
                "sections": [],
            },
        ),
    )

    model_input = _revision_model_input(
        writer_input=writer_input,
        source_artifact=source_artifact,
        source_draft=source_draft,
    )
    human_voice_policy = cast(dict[str, object], model_input["human_voice_policy"])
    assert human_voice_policy["version"] == HUMAN_VOICE_POLICY_VERSION
    assert human_voice_policy["mode"] == "truth_preserving_native_rewrite"
    assert (
        human_voice_policy["render_protocol_version"]
        == HUMAN_VOICE_RENDER_PROTOCOL_VERSION
    )
    assert human_voice_policy["post_rewrite_assertion_audit_required"] is True
    assert human_voice_policy["authorship_detection"] == "not_part_of_task"
    assert human_voice_policy["humanization_percentage"] == "forbidden"
    assert human_voice_policy["extra_model_call"] is False
    assert "artist_intent" in cast(list[str], human_voice_policy["forbidden_inventions"])
    assert "price" in cast(list[str], human_voice_policy["forbidden_inventions"])

    revision_policy = cast(dict[str, object], model_input["revision_policy"])
    relation_policy = cast(dict[str, object], revision_policy["evidence_relation_policy"])
    segment_policy = cast(dict[str, object], revision_policy["segment_support_policy"])
    title_policy = cast(dict[str, object], segment_policy["title"])
    standfirst_policy = cast(dict[str, object], segment_policy["standfirst"])
    lead_policy = cast(dict[str, object], segment_policy["lead_markdown"])
    closing_policy = cast(dict[str, object], segment_policy["closing_markdown"])
    requirements = cast(list[str], revision_policy["requirements"])

    assert relation_policy["relations_by_evidence_id"] == {
        "e-support": "supports",
        "e-context": "context_only",
    }
    assert title_policy == {
        "allowed_evidence_refs": [],
        "allowed_originality_refs": [],
        "require_non_assertive": True,
        "reason": "writer_schema_has_no_title_support_ref_fields",
    }
    assert standfirst_policy == {
        "allowed_evidence_refs": ["e-support"],
        "allowed_originality_refs": [],
    }
    assert lead_policy == {
        "allowed_evidence_refs": ["e-support"],
        "allowed_originality_refs": [],
    }
    assert closing_policy == {
        "allowed_evidence_refs": [],
        "allowed_originality_refs": [],
        "require_non_assertive": True,
        "reason": "writer_schema_has_no_closing_support_ref_fields",
    }
    assert (
        "review_every_factual_visual_and_live_claim_not_only_declared_unresolved_items"
        in requirements
    )
    assert (
        "context_only_and_contradicts_relations_are_never_support_for_"
        "factual_visual_or_live_claims"
        in requirements
    )
    assert (
        "rewrite_unsupported_broad_universal_or_epistemic_claims_as_"
        "bounded_reader_guidance"
        in requirements
    )
    assert (
        "title_has_no_support_ref_fields_and_must_not_contain_"
        "unsupported_factual_brand_visual_or_live_claims"
        in requirements
    )
    assert (
        "rewrite_unsupported_title_as_non_assertive_reader_guidance_or_topic_label"
        in requirements
    )
    assert (
        "avoid_unsupported_geographic_origin_provenance_authorship_or_"
        "local_making_propositions_in_title"
        in requirements
    )
    assert (
        "closing_markdown_has_no_support_ref_fields_and_must_not_contain_"
        "factual_brand_visual_or_live_claims"
        in requirements
    )
    assert (
        "keep_supported_factual_closing_points_in_an_existing_ref_bound_"
        "section_and_rewrite_closing_as_non_assertive_reader_guidance"
        in requirements
    )


def test_review_revise_prompt_states_fail_closed_support_boundary() -> None:
    prompt = cast(
        PromptDefinition,
        SimpleNamespace(body="Base approved review prompt."),
    )
    recipe = cast(
        RecipeDefinition,
        SimpleNamespace(recipe_json={"strategy": "fixture"}),
    )

    rendered = render_review_revise_prompt(
        prompt,
        recipe,
        review_model_input={"locale": "en"},
        attempt=1,
    )

    assert (
        "Only Evidence rows whose exact relation is supports or qualifies count as support"
        in rendered
    )
    assert "relation=context_only" in rendered
    assert "relation=contradicts never count as supportive evidence" in rendered
    assert "rewrite the passage as bounded reader guidance" in rendered
    assert (
        "Do not replace an unsupported fact with a broad universal or epistemic claim"
        in rendered
    )
    assert (
        "Preserve the accepted section IDs/order and exact evidence/originality ref arrays"
        in rendered
    )
    assert "TITLE SUPPORT CONTRACT:" in rendered
    assert "title zero allowed support refs" in rendered
    assert "do not state or imply geographic origin" in rendered
    assert "rewrite it as reader guidance or a neutral topic label" in rendered
    assert "Do not invent title support refs" in rendered
    assert "CLOSING SUPPORT CONTRACT:" in rendered
    assert "closing sentences zero allowed support refs" in rendered
    assert "closing_markdown must not contain factual" in rendered
    assert "Rewrite the closing as non-assertive reader guidance" in rendered
    assert f"HUMAN VOICE CONTRACT ({HUMAN_VOICE_RENDER_PROTOCOL_VERSION}):" in rendered
    assert "do not add a second rewrite stage" in rendered
    assert "artist intent or quotes" in rendered
    assert "customer stories" in rendered
    assert "New numeric tokens and direct quotes" in rendered
    assert "must pass Assertion Audit" in rendered
    assert "humanization percentages are not part of this task" in rendered
