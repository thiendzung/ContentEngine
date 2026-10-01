from __future__ import annotations

import pytest

from app.modules.content_engine.journal.coverage_support_depth_eval import (
    COVERAGE_SUPPORT_MODEL_INPUT_MAX_BYTES,
    CoverageSupportDepthRuntimeError,
    build_coverage_support_depth_model_input,
    preflight_coverage_support_depth_capacity,
)


def _originality_item() -> dict[str, str]:
    return {
        "type": "motgu_owned_material",
        "source_ref": "motgu:studio-note-1",
        "material": "Founder-approved studio note.",
        "writer_use": "Use only for MOTGU first-party context.",
        "guardrails": "Do not convert this into an external market fact.",
        "approval_ref": "founder:studio-note-1",
    }


def test_model_input_binds_exact_coverage_and_snapshot_refs() -> None:
    payload = build_coverage_support_depth_model_input(
        coverage_requirements=[
            "Explain authenticity evidence.",
            "Explain MOTGU's own viewing guidance.",
        ],
        evidence_items=[
            {
                "evidence_id": "ev-1",
                "relation": "supports",
                "claim": "A factual support claim.",
            },
            {
                "evidence_id": "ev-2",
                "relation": "context_only",
                "claim": "Context that must not become factual support.",
            },
        ],
        originality_items=[_originality_item()],
        evidence_set_ref={
            "id": "es-1",
            "version": 4,
            "content_hash": "a" * 64,
        },
        originality_pack_ref={
            "id": "op-1",
            "snapshot_hash": "b" * 64,
        },
    )

    assert payload["coverage_requirements"] == [
        {
            "id": "coverage-1",
            "requirement": "Explain authenticity evidence.",
        },
        {
            "id": "coverage-2",
            "requirement": "Explain MOTGU's own viewing guidance.",
        },
    ]
    assert payload["evidence_set"] == {
        "id": "es-1",
        "version": 4,
        "content_hash": "a" * 64,
    }
    originality = payload["originality_pack"]
    assert isinstance(originality, dict)
    assert originality["id"] == "op-1"
    assert originality["snapshot_hash"] == "b" * 64
    assert originality["items"] == [_originality_item()]


def test_model_input_drops_reference_only_or_incomplete_originality() -> None:
    payload = build_coverage_support_depth_model_input(
        coverage_requirements=["Explain the decision."],
        evidence_items=[],
        originality_items=[
            _originality_item(),
            {
                "type": "reference_only",
                "source_ref": "motgu:reference-1",
            },
            {
                "type": "motgu_owned_material",
                "source_ref": "motgu:incomplete",
                "material": "Missing required fields.",
            },
        ],
        evidence_set_ref={
            "id": "es-1",
            "version": 1,
            "content_hash": "a" * 64,
        },
        originality_pack_ref={
            "id": "op-1",
            "snapshot_hash": "b" * 64,
        },
    )

    originality = payload["originality_pack"]
    assert isinstance(originality, dict)
    assert originality["items"] == [_originality_item()]


def test_model_input_rejects_oversized_exact_snapshot_before_evaluator_call() -> None:
    item = _originality_item()
    item["material"] = "x" * (COVERAGE_SUPPORT_MODEL_INPUT_MAX_BYTES + 1)

    with pytest.raises(
        CoverageSupportDepthRuntimeError,
        match="coverage_support_model_input_too_large",
    ):
        build_coverage_support_depth_model_input(
            coverage_requirements=["Explain the decision."],
            evidence_items=[],
            originality_items=[item],
            evidence_set_ref={
                "id": "es-1",
                "version": 1,
                "content_hash": "a" * 64,
            },
            originality_pack_ref={
                "id": "op-1",
                "snapshot_hash": "b" * 64,
            },
        )


def test_preresearch_capacity_reserves_worst_case_automatic_evidence() -> None:
    item = _originality_item()
    item["material"] = "😀" * 4_000
    item["writer_use"] = "x" * 4_000
    item["guardrails"] = "x" * 4_000
    coverage = [
        f"{index:02d}-" + ("x" * 497)
        for index in range(12)
    ]

    base = build_coverage_support_depth_model_input(
        coverage_requirements=coverage,
        evidence_items=[],
        originality_items=[item],
        evidence_set_ref={
            "id": "pre-research",
            "version": 1,
            "content_hash": "0" * 64,
        },
        originality_pack_ref={
            "id": "op-1",
            "snapshot_hash": "b" * 64,
        },
    )
    assert base["evidence"] == []

    with pytest.raises(
        CoverageSupportDepthRuntimeError,
        match="coverage_support_model_input_too_large",
    ):
        preflight_coverage_support_depth_capacity(
            coverage_requirements=coverage,
            originality_items=[item],
            originality_pack_ref={
                "id": "op-1",
                "snapshot_hash": "b" * 64,
            },
            max_evidence_items=8,
        )


def test_model_policy_forbids_fake_numeric_or_lexical_truth() -> None:
    payload = build_coverage_support_depth_model_input(
        coverage_requirements=[],
        evidence_items=[],
        originality_items=[],
        evidence_set_ref={
            "id": "es-1",
            "version": 1,
            "content_hash": "a" * 64,
        },
        originality_pack_ref={
            "id": "op-1",
            "snapshot_hash": "b" * 64,
        },
    )

    policy = payload["assessment_policy"]
    assert isinstance(policy, dict)
    assert policy["lexical_overlap_is_not_semantic_proof"] is True
    assert policy["numeric_quality_score_forbidden"] is True
    assert policy["context_only_is_not_factual_support"] is True
    assert policy["contradicting_evidence_requires_resolution"] is True
    assert policy["coverage_requirement_is_editorial_spec_not_evidence"] is True
    assert (
        policy["structural_navigation_directives_do_not_require_external_evidence"]
        is True
    )
    assert policy["factual_assertions_still_require_factual_support"] is True
    assert (
        policy[
            "mixed_requirement_may_combine_factual_evidence_with_"
            "first_party_editorial_support"
        ]
        is True
    )
    assert "authoritative editorial specification" in str(policy["editorial_spec_rule"])
    assert "Factual clauses still require factual support" in str(
        policy["mixed_support_rule"]
    )
