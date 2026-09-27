"""CQ-06 Deep Quality final-gate contract.

This module is intentionally pure. It does not call a model, persist artifacts,
rewrite copy, or reinterpret upstream truth. It defines the exact 12-dimension
contract and deterministic verdict aggregation used by later CQ-06 slices.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

DeepQualityResult = Literal["pass", "warn", "fail"]
DeepQualityAuthority = Literal["deterministic", "upstream_gate", "semantic_model"]

DEEP_QUALITY_SCHEMA_VERSION = 1
DEEP_QUALITY_DIMENSIONS: tuple[str, ...] = (
    "promise_coverage_preservation",
    "pillar_cluster_semantic_behavior",
    "evidence_support_contradiction",
    "originality_provenance",
    "assertion_factual_integrity",
    "source_copy_attribution_safety",
    "title_angle_outline_draft_coherence",
    "reader_usefulness_decision_support",
    "human_voice_motgu_voice",
    "repetition_filler_ai_residue_system_language",
    "search_ai_readability_without_truth_tradeoff",
    "locale_specific_quality",
)

SEMANTIC_MODEL_DIMENSIONS = frozenset(
    {
        "title_angle_outline_draft_coherence",
        "human_voice_motgu_voice",
        "repetition_filler_ai_residue_system_language",
        "locale_specific_quality",
    }
)

DEEP_QUALITY_AUTHORITY_BY_DIMENSION: dict[str, DeepQualityAuthority] = {
    "promise_coverage_preservation": "upstream_gate",
    "pillar_cluster_semantic_behavior": "upstream_gate",
    "evidence_support_contradiction": "upstream_gate",
    "originality_provenance": "deterministic",
    "assertion_factual_integrity": "upstream_gate",
    "source_copy_attribution_safety": "upstream_gate",
    "title_angle_outline_draft_coherence": "semantic_model",
    "reader_usefulness_decision_support": "upstream_gate",
    "human_voice_motgu_voice": "semantic_model",
    "repetition_filler_ai_residue_system_language": "semantic_model",
    "search_ai_readability_without_truth_tradeoff": "upstream_gate",
    "locale_specific_quality": "semantic_model",
}

_ALLOWED_RESULTS = frozenset({"pass", "warn", "fail"})
_ALLOWED_AUTHORITIES = frozenset({"deterministic", "upstream_gate", "semantic_model"})


class DeepQualityError(ValueError):
    """Stable fail-closed CQ-06 contract error."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class DeepQualityDimension:
    key: str
    result: DeepQualityResult
    authority: DeepQualityAuthority
    finding: str
    remediation: str
    provenance_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "result": self.result,
            "authority": self.authority,
            "finding": self.finding,
            "remediation": self.remediation,
            "provenance_refs": list(self.provenance_refs),
        }


@dataclass(frozen=True, slots=True)
class DeepQualityAssessment:
    locale: str
    verdict: DeepQualityResult
    dimensions: tuple[DeepQualityDimension, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": DEEP_QUALITY_SCHEMA_VERSION,
            "locale": self.locale,
            "verdict": self.verdict,
            "dimensions": [item.to_dict() for item in self.dimensions],
        }


def _nonempty_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeepQualityError(code)
    return value.strip()


def _result(value: object, code: str) -> DeepQualityResult:
    if not isinstance(value, str) or value not in _ALLOWED_RESULTS:
        raise DeepQualityError(code)
    return cast(DeepQualityResult, value)


def _authority(value: object, code: str) -> DeepQualityAuthority:
    if not isinstance(value, str) or value not in _ALLOWED_AUTHORITIES:
        raise DeepQualityError(code)
    return cast(DeepQualityAuthority, value)


def aggregate_deep_quality_verdict(
    dimensions: tuple[DeepQualityDimension, ...],
) -> DeepQualityResult:
    if any(item.result == "fail" for item in dimensions):
        return "fail"
    if any(item.result == "warn" for item in dimensions):
        return "warn"
    return "pass"


def validate_deep_quality_dimensions(
    dimensions: tuple[DeepQualityDimension, ...],
) -> tuple[DeepQualityDimension, ...]:
    keys = tuple(item.key for item in dimensions)
    if keys != DEEP_QUALITY_DIMENSIONS or len(set(keys)) != len(keys):
        raise DeepQualityError("deep_quality_dimensions_mismatch")

    for item in dimensions:
        expected_authority = DEEP_QUALITY_AUTHORITY_BY_DIMENSION[item.key]
        if item.authority != expected_authority:
            raise DeepQualityError(
                "deep_quality_dimension_authority_mismatch",
                item.key,
            )
        if not item.finding.strip():
            raise DeepQualityError("deep_quality_dimension_finding_required", item.key)
        if item.result in {"warn", "fail"} and not item.remediation.strip():
            raise DeepQualityError("deep_quality_dimension_remediation_required", item.key)
        if item.result == "pass" and item.remediation.strip():
            raise DeepQualityError("deep_quality_pass_remediation_forbidden", item.key)
        if not item.provenance_refs:
            raise DeepQualityError("deep_quality_dimension_provenance_required", item.key)
        if any(not ref.strip() for ref in item.provenance_refs):
            raise DeepQualityError("deep_quality_dimension_provenance_invalid", item.key)
        if len(set(item.provenance_refs)) != len(item.provenance_refs):
            raise DeepQualityError("deep_quality_dimension_provenance_duplicate", item.key)
    return dimensions


def build_deep_quality_assessment(
    *,
    locale: str,
    dimensions: tuple[DeepQualityDimension, ...],
) -> DeepQualityAssessment:
    normalized_locale = _nonempty_text(locale, "deep_quality_locale_invalid")
    validated = validate_deep_quality_dimensions(dimensions)
    return DeepQualityAssessment(
        locale=normalized_locale,
        verdict=aggregate_deep_quality_verdict(validated),
        dimensions=validated,
    )


def validate_deep_quality_output(
    raw: object,
    *,
    locale: str,
) -> DeepQualityAssessment:
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version",
        "locale",
        "verdict",
        "dimensions",
    }:
        raise DeepQualityError("deep_quality_output_schema_invalid")
    if raw.get("schema_version") != DEEP_QUALITY_SCHEMA_VERSION:
        raise DeepQualityError("deep_quality_output_schema_version_invalid")
    if raw.get("locale") != locale:
        raise DeepQualityError("deep_quality_output_locale_mismatch")

    raw_dimensions = raw.get("dimensions")
    if not isinstance(raw_dimensions, list):
        raise DeepQualityError("deep_quality_output_dimensions_invalid")

    parsed: list[DeepQualityDimension] = []
    for raw_item in raw_dimensions:
        if not isinstance(raw_item, dict) or set(raw_item) != {
            "key",
            "result",
            "authority",
            "finding",
            "remediation",
            "provenance_refs",
        }:
            raise DeepQualityError("deep_quality_output_dimension_schema_invalid")
        key = _nonempty_text(raw_item.get("key"), "deep_quality_output_dimension_key_invalid")
        if key not in DEEP_QUALITY_AUTHORITY_BY_DIMENSION:
            raise DeepQualityError("deep_quality_output_dimension_key_unknown", key)
        raw_refs = raw_item.get("provenance_refs")
        if not isinstance(raw_refs, list) or any(not isinstance(ref, str) for ref in raw_refs):
            raise DeepQualityError("deep_quality_output_dimension_provenance_invalid", key)
        raw_remediation = raw_item.get("remediation")
        if not isinstance(raw_remediation, str):
            raise DeepQualityError("deep_quality_output_dimension_remediation_invalid", key)
        parsed.append(
            DeepQualityDimension(
                key=key,
                result=_result(
                    raw_item.get("result"),
                    "deep_quality_output_dimension_result_invalid",
                ),
                authority=_authority(
                    raw_item.get("authority"),
                    "deep_quality_output_dimension_authority_invalid",
                ),
                finding=_nonempty_text(
                    raw_item.get("finding"),
                    "deep_quality_output_dimension_finding_invalid",
                ),
                remediation=raw_remediation.strip(),
                provenance_refs=tuple(ref.strip() for ref in cast(list[str], raw_refs)),
            )
        )

    assessment = build_deep_quality_assessment(
        locale=locale,
        dimensions=tuple(parsed),
    )
    declared = _result(raw.get("verdict"), "deep_quality_output_verdict_invalid")
    if declared != assessment.verdict:
        raise DeepQualityError("deep_quality_output_verdict_mismatch")
    return assessment


__all__ = [
    "DEEP_QUALITY_AUTHORITY_BY_DIMENSION",
    "DEEP_QUALITY_DIMENSIONS",
    "DEEP_QUALITY_SCHEMA_VERSION",
    "SEMANTIC_MODEL_DIMENSIONS",
    "DeepQualityAssessment",
    "DeepQualityAuthority",
    "DeepQualityDimension",
    "DeepQualityError",
    "DeepQualityResult",
    "aggregate_deep_quality_verdict",
    "build_deep_quality_assessment",
    "validate_deep_quality_dimensions",
    "validate_deep_quality_output",
]
