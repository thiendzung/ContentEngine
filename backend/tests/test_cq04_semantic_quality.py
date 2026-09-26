from __future__ import annotations

import pytest

from app.modules.content_engine.journal.semantic_quality import (
    SemanticQualityError,
    angle_subject_refs,
    outline_subject_refs,
    validate_semantic_quality_assessment,
)


def _finding(
    code: str,
    subject_ref: str,
) -> dict[str, object]:
    return {
        "code": code,
        "subject_ref": subject_ref,
        "reason": "The semantic contract is not satisfied.",
        "remediation": "Revise the exact subject before approval.",
    }


def test_angle_pass_requires_zero_findings_and_exact_role() -> None:
    refs = angle_subject_refs(
        angle_id="angle-1",
        coverage_requirement_ids=["coverage-1", "coverage-2"],
    )
    result = validate_semantic_quality_assessment(
        {
            "schema_version": 1,
            "stage": "angle",
            "role": "pillar",
            "verdict": "pass",
            "findings": [],
        },
        expected_stage="angle",
        expected_role="pillar",
        allowed_subject_refs=refs,
    )
    assert result.verdict == "pass"
    assert result.findings == ()


def test_angle_revise_accepts_stable_exact_subject_finding() -> None:
    refs = angle_subject_refs(
        angle_id="angle-1",
        coverage_requirement_ids=["coverage-1"],
    )
    result = validate_semantic_quality_assessment(
        {
            "schema_version": 1,
            "stage": "angle",
            "role": "cluster",
            "verdict": "revise",
            "findings": [
                _finding(
                    "angle_question_promise_mismatch",
                    "angle:core_promise",
                )
            ],
        },
        expected_stage="angle",
        expected_role="cluster",
        allowed_subject_refs=refs,
    )
    assert result.findings[0].subject_ref == "angle:core_promise"


def test_angle_rejects_unknown_subject_and_numeric_score_escape_hatch() -> None:
    refs = angle_subject_refs(
        angle_id="angle-1",
        coverage_requirement_ids=["coverage-1"],
    )
    with pytest.raises(
        SemanticQualityError,
        match="semantic_quality_subject_ref_unknown",
    ):
        validate_semantic_quality_assessment(
            {
                "schema_version": 1,
                "stage": "angle",
                "role": "pillar",
                "verdict": "revise",
                "findings": [
                    _finding("angle_role_drift", "angle:invented")
                ],
            },
            expected_stage="angle",
            expected_role="pillar",
            allowed_subject_refs=refs,
        )

    with pytest.raises(
        SemanticQualityError,
        match="semantic_quality_payload_keys_invalid",
    ):
        validate_semantic_quality_assessment(
            {
                "schema_version": 1,
                "stage": "angle",
                "role": "pillar",
                "verdict": "pass",
                "findings": [],
                "score": 0.95,
            },
            expected_stage="angle",
            expected_role="pillar",
            allowed_subject_refs=refs,
        )


def test_outline_rejects_unknown_or_duplicate_findings() -> None:
    refs = outline_subject_refs(
        section_ids=["section-1", "section-2"],
        coverage_requirement_ids=["coverage-1"],
    )
    with pytest.raises(
        SemanticQualityError,
        match="semantic_quality_finding_duplicate",
    ):
        validate_semantic_quality_assessment(
            {
                "schema_version": 1,
                "stage": "outline",
                "role": "pillar",
                "verdict": "revise",
                "findings": [
                    _finding(
                        "outline_section_redundancy",
                        "section:section-2",
                    ),
                    _finding(
                        "outline_section_redundancy",
                        "section:section-2",
                    ),
                ],
            },
            expected_stage="outline",
            expected_role="pillar",
            allowed_subject_refs=refs,
        )


def test_outline_revise_requires_findings() -> None:
    refs = outline_subject_refs(
        section_ids=["section-1"],
        coverage_requirement_ids=["coverage-1"],
    )
    with pytest.raises(
        SemanticQualityError,
        match="semantic_quality_revise_without_findings",
    ):
        validate_semantic_quality_assessment(
            {
                "schema_version": 1,
                "stage": "outline",
                "role": "cluster",
                "verdict": "revise",
                "findings": [],
            },
            expected_stage="outline",
            expected_role="cluster",
            allowed_subject_refs=refs,
        )


def test_pass_cannot_hide_findings() -> None:
    refs = outline_subject_refs(
        section_ids=["section-1"],
        coverage_requirement_ids=[],
    )
    with pytest.raises(
        SemanticQualityError,
        match="semantic_quality_pass_with_findings",
    ):
        validate_semantic_quality_assessment(
            {
                "schema_version": 1,
                "stage": "outline",
                "role": "pillar",
                "verdict": "pass",
                "findings": [
                    _finding(
                        "outline_section_job_unclear",
                        "section:section-1",
                    )
                ],
            },
            expected_stage="outline",
            expected_role="pillar",
            allowed_subject_refs=refs,
        )



@pytest.mark.parametrize(
    ("role", "code", "subject_ref"),
    [
        ("pillar", "angle_role_drift", "angle:role"),
        ("pillar", "angle_coverage_intent_drift", "coverage:coverage-2"),
        ("cluster", "angle_role_drift", "angle:role"),
        ("cluster", "angle_scope_drift", "angle:scope"),
    ],
)
def test_angle_pillar_cluster_adversarial_findings_are_exact(
    role: str,
    code: str,
    subject_ref: str,
) -> None:
    refs = angle_subject_refs(
        angle_id="angle-1",
        coverage_requirement_ids=["coverage-1", "coverage-2"],
    )
    result = validate_semantic_quality_assessment(
        {
            "schema_version": 1,
            "stage": "angle",
            "role": role,
            "verdict": "revise",
            "findings": [_finding(code, subject_ref)],
        },
        expected_stage="angle",
        expected_role=role,  # type: ignore[arg-type]
        allowed_subject_refs=refs,
    )
    assert result.verdict == "revise"
    assert result.findings[0].code == code
    assert result.findings[0].subject_ref == subject_ref


@pytest.mark.parametrize(
    ("role", "code", "subject_ref"),
    [
        ("pillar", "outline_coverage_drift", "coverage:coverage-2"),
        ("pillar", "outline_broad_summary_filler", "section:section-3"),
        ("cluster", "outline_section_redundancy", "section:section-2"),
        (
            "cluster",
            "outline_section_support_purpose_unclear",
            "section:section-3",
        ),
    ],
)
def test_outline_pillar_cluster_adversarial_findings_are_exact(
    role: str,
    code: str,
    subject_ref: str,
) -> None:
    refs = outline_subject_refs(
        section_ids=["section-1", "section-2", "section-3"],
        coverage_requirement_ids=["coverage-1", "coverage-2"],
    )
    result = validate_semantic_quality_assessment(
        {
            "schema_version": 1,
            "stage": "outline",
            "role": role,
            "verdict": "revise",
            "findings": [_finding(code, subject_ref)],
        },
        expected_stage="outline",
        expected_role=role,  # type: ignore[arg-type]
        allowed_subject_refs=refs,
    )
    assert result.verdict == "revise"
    assert result.findings[0].code == code
    assert result.findings[0].subject_ref == subject_ref


def test_pillar_cluster_roles_cannot_be_flattened_or_swapped() -> None:
    refs = angle_subject_refs(
        angle_id="angle-1",
        coverage_requirement_ids=["coverage-1"],
    )
    with pytest.raises(
        SemanticQualityError,
        match="semantic_quality_role_mismatch",
    ):
        validate_semantic_quality_assessment(
            {
                "schema_version": 1,
                "stage": "angle",
                "role": "pillar",
                "verdict": "pass",
                "findings": [],
            },
            expected_stage="angle",
            expected_role="cluster",
            allowed_subject_refs=refs,
        )
