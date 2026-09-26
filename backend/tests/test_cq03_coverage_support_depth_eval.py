from __future__ import annotations

from app.modules.content_engine.journal.coverage_support_depth_eval import (
    build_coverage_support_depth_model_input,
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
