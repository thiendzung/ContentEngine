from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from app.modules.content_engine.journal.review_revise import (
    REVIEW_REVISE_GENERATOR_VERSION,
    _evidence_relation_policy,
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


def test_review_revise_v2_exposes_exact_evidence_relation_policy() -> None:
    writer_input = _writer_input_with_relations(
        [
            ("e-support", "supports"),
            ("e-qualify", "qualifies"),
            ("e-context", "context_only"),
            ("e-contradict", "contradicts"),
        ]
    )

    policy = _evidence_relation_policy(writer_input)

    assert REVIEW_REVISE_GENERATOR_VERSION == "ce05.journal_review_revise.v2"
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


def test_review_revise_v2_rejects_unknown_or_duplicate_relation_rows() -> None:
    unknown = _writer_input_with_relations([("e-1", "maybe")])
    with pytest.raises(WriterGenerationError, match="review_revise_evidence_relation_invalid"):
        _evidence_relation_policy(unknown)

    duplicate = _writer_input_with_relations(
        [("e-1", "supports"), ("e-1", "context_only")]
    )
    with pytest.raises(WriterGenerationError, match="review_revise_evidence_relation_duplicate"):
        _evidence_relation_policy(duplicate)


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
            unresolved_factual_claims=(),
            sections=(),
            to_dict=lambda: {"locale": "en", "unresolved_factual_claims": [], "sections": []},
        ),
    )

    model_input = _revision_model_input(
        writer_input=writer_input,
        source_artifact=source_artifact,
        source_draft=source_draft,
    )
    revision_policy = cast(dict[str, object], model_input["revision_policy"])
    relation_policy = cast(dict[str, object], revision_policy["evidence_relation_policy"])
    requirements = cast(list[str], revision_policy["requirements"])

    assert relation_policy["relations_by_evidence_id"] == {
        "e-support": "supports",
        "e-context": "context_only",
    }
    assert "review_every_factual_visual_and_live_claim_not_only_declared_unresolved_items" in requirements
    assert (
        "context_only_and_contradicts_relations_are_never_support_for_factual_visual_or_live_claims"
        in requirements
    )
    assert (
        "rewrite_unsupported_broad_universal_or_epistemic_claims_as_bounded_reader_guidance"
        in requirements
    )


def test_review_revise_prompt_states_fail_closed_support_boundary() -> None:
    prompt = cast(PromptDefinition, SimpleNamespace(body="Base approved review prompt."))
    recipe = cast(RecipeDefinition, SimpleNamespace(recipe_json={"strategy": "fixture"}))

    rendered = render_review_revise_prompt(
        prompt,
        recipe,
        review_model_input={"locale": "en"},
        attempt=1,
    )

    assert "Only Evidence rows whose exact relation is supports or qualifies count as support" in rendered
    assert "relation=context_only" in rendered
    assert "relation=contradicts never count as supportive evidence" in rendered
    assert "rewrite the passage as bounded reader guidance" in rendered
    assert "Do not replace an unsupported fact with a broad universal or epistemic claim" in rendered
    assert "Preserve the accepted section IDs/order and exact evidence/originality ref arrays" in rendered
