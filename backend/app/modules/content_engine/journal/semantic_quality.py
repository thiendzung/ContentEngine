"""CQ-04 deterministic semantic-quality assessment contract."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, cast

SemanticStage = Literal["angle", "outline"]
SemanticVerdict = Literal["pass", "revise"]
SemanticRole = Literal["pillar", "cluster"]

SEMANTIC_QUALITY_SCHEMA_VERSION = 1

ANGLE_SEMANTIC_FINDING_CODES = (
    "angle_title_problem_mismatch",
    "angle_problem_question_mismatch",
    "angle_question_promise_mismatch",
    "angle_role_drift",
    "angle_scope_drift",
    "angle_coverage_intent_drift",
)
OUTLINE_SEMANTIC_FINDING_CODES = (
    "outline_angle_drift",
    "outline_role_drift",
    "outline_coverage_drift",
    "outline_section_job_unclear",
    "outline_section_support_purpose_unclear",
    "outline_section_redundancy",
    "outline_broad_summary_filler",
    "outline_relationship_invention",
)
_ALLOWED_FINDING_CODES = {
    "angle": set(ANGLE_SEMANTIC_FINDING_CODES),
    "outline": set(OUTLINE_SEMANTIC_FINDING_CODES),
}

class SemanticQualityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SemanticFinding:
    code: str
    subject_ref: str
    reason: str
    remediation: str

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "subject_ref": self.subject_ref,
            "reason": self.reason,
            "remediation": self.remediation,
        }


@dataclass(frozen=True, slots=True)
class SemanticQualityAssessment:
    schema_version: int
    stage: SemanticStage
    role: SemanticRole
    verdict: SemanticVerdict
    findings: tuple[SemanticFinding, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "stage": self.stage,
            "role": self.role,
            "verdict": self.verdict,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SemanticQualityError(code)
    return cast(dict[str, object], value)


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticQualityError(code)
    return value.strip()


def _exact_keys(
    value: dict[str, object],
    *,
    allowed: set[str],
    code: str,
) -> None:
    if set(value) != allowed:
        raise SemanticQualityError(code)


def angle_subject_refs(
    *,
    angle_id: str,
    coverage_requirement_ids: Iterable[str],
) -> set[str]:
    angle_id = _text(angle_id, "semantic_angle_id_required")
    refs = {
        f"angle:{angle_id}",
        "angle:working_title",
        "angle:reader_problem",
        "angle:central_question",
        "angle:core_promise",
        "angle:role",
        "angle:scope",
    }
    for requirement_id in coverage_requirement_ids:
        normalized = _text(
            requirement_id,
            "semantic_coverage_requirement_id_required",
        )
        refs.add(f"coverage:{normalized}")
    return refs


def outline_subject_refs(
    *,
    section_ids: Iterable[str],
    coverage_requirement_ids: Iterable[str],
) -> set[str]:
    refs = {
        "outline:global",
        "outline:angle_alignment",
        "outline:role",
        "outline:relationship",
    }
    for section_id in section_ids:
        normalized = _text(section_id, "semantic_outline_section_id_required")
        refs.add(f"section:{normalized}")
    for requirement_id in coverage_requirement_ids:
        normalized = _text(
            requirement_id,
            "semantic_coverage_requirement_id_required",
        )
        refs.add(f"coverage:{normalized}")
    return refs


def validate_semantic_quality_assessment(
    raw: object,
    *,
    expected_stage: SemanticStage,
    expected_role: SemanticRole,
    allowed_subject_refs: set[str],
) -> SemanticQualityAssessment:
    payload = _dict(raw, "semantic_quality_payload_invalid")
    _exact_keys(
        payload,
        allowed={"schema_version", "stage", "role", "verdict", "findings"},
        code="semantic_quality_payload_keys_invalid",
    )
    if payload.get("schema_version") != SEMANTIC_QUALITY_SCHEMA_VERSION:
        raise SemanticQualityError("semantic_quality_schema_invalid")

    stage = _text(payload.get("stage"), "semantic_quality_stage_required")
    if stage != expected_stage:
        raise SemanticQualityError("semantic_quality_stage_mismatch")

    role = _text(payload.get("role"), "semantic_quality_role_required")
    if role != expected_role:
        raise SemanticQualityError("semantic_quality_role_mismatch")

    verdict = _text(payload.get("verdict"), "semantic_quality_verdict_required")
    if verdict not in {"pass", "revise"}:
        raise SemanticQualityError("semantic_quality_verdict_invalid")

    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        raise SemanticQualityError("semantic_quality_findings_invalid")

    findings: list[SemanticFinding] = []
    seen: set[tuple[str, str]] = set()
    allowed_codes = _ALLOWED_FINDING_CODES[expected_stage]
    for raw_finding in raw_findings:
        finding = _dict(raw_finding, "semantic_quality_finding_invalid")
        _exact_keys(
            finding,
            allowed={"code", "subject_ref", "reason", "remediation"},
            code="semantic_quality_finding_keys_invalid",
        )
        code = _text(finding.get("code"), "semantic_quality_finding_code_required")
        if code not in allowed_codes:
            raise SemanticQualityError("semantic_quality_finding_code_invalid")

        subject_ref = _text(
            finding.get("subject_ref"),
            "semantic_quality_subject_ref_required",
        )
        if subject_ref not in allowed_subject_refs:
            raise SemanticQualityError("semantic_quality_subject_ref_unknown")

        key = (code, subject_ref)
        if key in seen:
            raise SemanticQualityError("semantic_quality_finding_duplicate")
        seen.add(key)

        findings.append(
            SemanticFinding(
                code=code,
                subject_ref=subject_ref,
                reason=_text(
                    finding.get("reason"),
                    "semantic_quality_finding_reason_required",
                ),
                remediation=_text(
                    finding.get("remediation"),
                    "semantic_quality_finding_remediation_required",
                ),
            )
        )

    if verdict == "pass" and findings:
        raise SemanticQualityError("semantic_quality_pass_with_findings")
    if verdict == "revise" and not findings:
        raise SemanticQualityError("semantic_quality_revise_without_findings")

    return SemanticQualityAssessment(
        schema_version=SEMANTIC_QUALITY_SCHEMA_VERSION,
        stage=stage,
        role=role,
        verdict=cast(SemanticVerdict, verdict),
        findings=tuple(findings),
    )


__all__ = [
    "ANGLE_SEMANTIC_FINDING_CODES",
    "OUTLINE_SEMANTIC_FINDING_CODES",
    "SEMANTIC_QUALITY_SCHEMA_VERSION",
    "SemanticFinding",
    "SemanticQualityAssessment",
    "SemanticQualityError",
    "SemanticRole",
    "SemanticStage",
    "SemanticVerdict",
    "angle_subject_refs",
    "outline_subject_refs",
    "validate_semantic_quality_assessment",
]
