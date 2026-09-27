from __future__ import annotations

import copy

import pytest

from app.modules.content_engine.journal.deep_quality import (
    DEEP_QUALITY_AUTHORITY_BY_DIMENSION,
    DEEP_QUALITY_DIMENSIONS,
    DEEP_QUALITY_SCHEMA_VERSION,
    SEMANTIC_MODEL_DIMENSIONS,
    DeepQualityDimension,
    DeepQualityError,
    build_deep_quality_assessment,
    validate_deep_quality_output,
)


def _dimension(
    key: str,
    *,
    result: str = "pass",
) -> DeepQualityDimension:
    authority = DEEP_QUALITY_AUTHORITY_BY_DIMENSION[key]
    return DeepQualityDimension(
        key=key,
        result=result,  # type: ignore[arg-type]
        authority=authority,
        finding=f"{key}: bounded explicit finding",
        remediation="" if result == "pass" else f"Repair {key}.",
        provenance_refs=(f"artifact:{key}:exact",),
    )


def _assessment_payload(
    *,
    locale: str = "en",
    overrides: dict[str, str] | None = None,
) -> dict[str, object]:
    overrides = overrides or {}
    dimensions = tuple(
        _dimension(key, result=overrides.get(key, "pass"))
        for key in DEEP_QUALITY_DIMENSIONS
    )
    assessment = build_deep_quality_assessment(locale=locale, dimensions=dimensions)
    return assessment.to_dict()


def test_deep_quality_contract_has_exact_12_dimensions_and_bounded_semantic_scope() -> None:
    assert len(DEEP_QUALITY_DIMENSIONS) == 12
    assert len(set(DEEP_QUALITY_DIMENSIONS)) == 12
    assert SEMANTIC_MODEL_DIMENSIONS == {
        "title_angle_outline_draft_coherence",
        "human_voice_motgu_voice",
        "repetition_filler_ai_residue_system_language",
        "locale_specific_quality",
    }
    assert set(DEEP_QUALITY_AUTHORITY_BY_DIMENSION) == set(DEEP_QUALITY_DIMENSIONS)
    assert all(
        DEEP_QUALITY_AUTHORITY_BY_DIMENSION[key] == "semantic_model"
        for key in SEMANTIC_MODEL_DIMENSIONS
    )
    assert all(
        DEEP_QUALITY_AUTHORITY_BY_DIMENSION[key] != "semantic_model"
        for key in set(DEEP_QUALITY_DIMENSIONS) - SEMANTIC_MODEL_DIMENSIONS
    )


def test_good_content_fixture_passes_without_score() -> None:
    payload = _assessment_payload()
    assessment = validate_deep_quality_output(payload, locale="en")

    assert assessment.verdict == "pass"
    assert tuple(item.key for item in assessment.dimensions) == DEEP_QUALITY_DIMENSIONS
    assert payload["schema_version"] == DEEP_QUALITY_SCHEMA_VERSION
    assert "score" not in payload
    assert "quality_score" not in payload
    assert "confidence" not in payload


def test_deceptive_polished_content_cannot_hide_factual_failure() -> None:
    payload = _assessment_payload(
        overrides={"assertion_factual_integrity": "fail"}
    )
    dimensions = payload["dimensions"]
    assert isinstance(dimensions, list)

    semantic_rows = [
        row
        for row in dimensions
        if isinstance(row, dict) and row.get("key") in SEMANTIC_MODEL_DIMENSIONS
    ]
    assert semantic_rows
    assert all(row.get("result") == "pass" for row in semantic_rows)

    assessment = validate_deep_quality_output(payload, locale="en")
    assert assessment.verdict == "fail"
    assertion = next(
        item
        for item in assessment.dimensions
        if item.key == "assertion_factual_integrity"
    )
    assert assertion.authority == "upstream_gate"
    assert assertion.result == "fail"


def test_warn_is_preserved_when_no_dimension_fails() -> None:
    payload = _assessment_payload(
        overrides={"repetition_filler_ai_residue_system_language": "warn"}
    )
    assessment = validate_deep_quality_output(payload, locale="en")
    assert assessment.verdict == "warn"


def test_declared_verdict_cannot_override_dimension_aggregation() -> None:
    payload = _assessment_payload(
        overrides={"source_copy_attribution_safety": "fail"}
    )
    payload["verdict"] = "pass"

    with pytest.raises(DeepQualityError, match="deep_quality_output_verdict_mismatch"):
        validate_deep_quality_output(payload, locale="en")


def test_semantic_model_cannot_claim_authority_over_upstream_dimension() -> None:
    payload = _assessment_payload()
    dimensions = payload["dimensions"]
    assert isinstance(dimensions, list)
    row = next(
        item
        for item in dimensions
        if isinstance(item, dict)
        and item.get("key") == "evidence_support_contradiction"
    )
    assert isinstance(row, dict)
    row["authority"] = "semantic_model"

    with pytest.raises(
        DeepQualityError,
        match="deep_quality_dimension_authority_mismatch",
    ):
        validate_deep_quality_output(payload, locale="en")


def test_missing_reordered_or_duplicate_dimensions_fail_closed() -> None:
    missing = _assessment_payload()
    missing_rows = missing["dimensions"]
    assert isinstance(missing_rows, list)
    missing_rows.pop()
    with pytest.raises(DeepQualityError, match="deep_quality_dimensions_mismatch"):
        validate_deep_quality_output(missing, locale="en")

    reordered = _assessment_payload()
    reordered_rows = reordered["dimensions"]
    assert isinstance(reordered_rows, list)
    reordered_rows[0], reordered_rows[1] = reordered_rows[1], reordered_rows[0]
    with pytest.raises(DeepQualityError, match="deep_quality_dimensions_mismatch"):
        validate_deep_quality_output(reordered, locale="en")

    duplicate = _assessment_payload()
    duplicate_rows = duplicate["dimensions"]
    assert isinstance(duplicate_rows, list)
    duplicate_rows[-1] = copy.deepcopy(duplicate_rows[0])
    with pytest.raises(DeepQualityError, match="deep_quality_dimensions_mismatch"):
        validate_deep_quality_output(duplicate, locale="en")


def test_non_pass_requires_remediation_and_every_dimension_requires_provenance() -> None:
    payload = _assessment_payload(
        overrides={"locale_specific_quality": "warn"}
    )
    rows = payload["dimensions"]
    assert isinstance(rows, list)
    locale_row = next(
        item
        for item in rows
        if isinstance(item, dict) and item.get("key") == "locale_specific_quality"
    )
    assert isinstance(locale_row, dict)
    locale_row["remediation"] = ""

    with pytest.raises(
        DeepQualityError,
        match="deep_quality_dimension_remediation_required",
    ):
        validate_deep_quality_output(payload, locale="en")

    no_provenance = _assessment_payload()
    no_provenance_rows = no_provenance["dimensions"]
    assert isinstance(no_provenance_rows, list)
    first = no_provenance_rows[0]
    assert isinstance(first, dict)
    first["provenance_refs"] = []

    with pytest.raises(
        DeepQualityError,
        match="deep_quality_dimension_provenance_required",
    ):
        validate_deep_quality_output(no_provenance, locale="en")


def test_extra_score_field_is_rejected_by_exact_schema() -> None:
    payload = _assessment_payload()
    payload["score"] = 99

    with pytest.raises(DeepQualityError, match="deep_quality_output_schema_invalid"):
        validate_deep_quality_output(payload, locale="en")
