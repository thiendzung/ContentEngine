"""CQ-06 authoritative Deep Quality dimension derivation.

Only existing deterministic/upstream gates are projected here. Semantic-model
dimensions are deliberately absent and are filled by the bounded CQ06-D evaluator.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from app.modules.content_engine.journal.deep_quality import (
    DEEP_QUALITY_AUTHORITY_BY_DIMENSION,
    DeepQualityDimension,
    DeepQualityResult,
)
from app.modules.content_engine.journal.deep_quality_input import DeepQualityInput
from app.modules.content_engine.journal.semantic_quality import SemanticFinding
from app.modules.harness.models import Artifact, QualityEvaluation

AUTHORITATIVE_DEEP_QUALITY_DIMENSIONS = (
    "promise_coverage_preservation",
    "pillar_cluster_semantic_behavior",
    "evidence_support_contradiction",
    "originality_provenance",
    "assertion_factual_integrity",
    "source_copy_attribution_safety",
    "reader_usefulness_decision_support",
    "search_ai_readability_without_truth_tradeoff",
)


class DeepQualityAuthorityError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def _artifact_ref(artifact: Artifact) -> str:
    return (
        f"artifact:{artifact.id}:v{artifact.version}:"
        f"{artifact.content_hash}"
    )


def _evaluation_ref(evaluation: QualityEvaluation) -> str:
    return (
        f"evaluation:{evaluation.id}:"
        f"{evaluation.evaluator_key}:"
        f"{evaluation.evaluator_version}:"
        f"{evaluation.result}"
    )


def _result(value: str) -> DeepQualityResult:
    if value not in {"pass", "warn", "fail"}:
        raise DeepQualityAuthorityError(
            "deep_quality_authoritative_result_invalid",
            value,
        )
    return cast(DeepQualityResult, value)


def _dimension(
    key: str,
    *,
    result: DeepQualityResult,
    finding: str,
    remediation: str = "",
    provenance_refs: Iterable[str],
) -> DeepQualityDimension:
    authority = DEEP_QUALITY_AUTHORITY_BY_DIMENSION.get(key)
    if authority not in {"deterministic", "upstream_gate"}:
        raise DeepQualityAuthorityError(
            "deep_quality_authoritative_dimension_invalid",
            key,
        )
    return DeepQualityDimension(
        key=key,
        result=result,
        authority=authority,
        finding=finding,
        remediation=remediation,
        provenance_refs=tuple(provenance_refs),
    )


def _semantic_failure(
    findings: tuple[SemanticFinding, ...],
    *,
    codes: set[str],
) -> tuple[str, str] | None:
    relevant = [item for item in findings if item.code in codes]
    if not relevant:
        return None
    return (
        " ".join(item.reason for item in relevant),
        " ".join(item.remediation for item in relevant),
    )


def _readiness_detail(
    input_value: DeepQualityInput,
    *,
    stage: str,
) -> tuple[DeepQualityResult, str, str, tuple[str, ...]]:
    result = (
        input_value.reader_value
        if stage == "reader_value"
        else input_value.search_ai
    )
    normalized = _result(result.result)
    non_pass = [item for item in result.criteria if item.result != "pass"]
    if non_pass:
        finding = " ".join(item.finding for item in non_pass)
        remediation = " ".join(
            item.repair_suggestion
            for item in non_pass
            if item.repair_suggestion
        )
    else:
        finding = f"{stage} upstream gate passed on the exact revised draft."
        remediation = ""
    return (
        normalized,
        finding,
        remediation,
        (
            _artifact_ref(result.artifact),
            _evaluation_ref(result.evaluation),
        ),
    )


def derive_authoritative_deep_quality_dimensions(
    source: DeepQualityInput,
) -> dict[str, DeepQualityDimension]:
    selected = source.writer_input.outline_input.approved_angle.candidate
    selected_semantic = source.angle_semantic.by_angle_id.get(selected.angle_id)
    if selected_semantic is None:
        raise DeepQualityAuthorityError("deep_quality_selected_angle_semantic_missing")
    outline_semantic = source.outline_semantic.assessment

    coverage_failure = _semantic_failure(
        (*selected_semantic.findings, *outline_semantic.findings),
        codes={"angle_coverage_intent_drift", "outline_coverage_drift"},
    )
    support = source.coverage_support_depth
    if selected.coverage and support is None:
        raise DeepQualityAuthorityError("deep_quality_support_depth_required")
    support_unresolved = (
        support is not None
        and (
            not support.ready_for_angle
            or bool(support.unresolved_requirement_ids)
        )
    )
    coverage_provenance = [
        _artifact_ref(source.angle_semantic.artifact),
        _artifact_ref(source.outline_semantic.artifact),
    ]
    if support is not None:
        coverage_provenance.append(_artifact_ref(support.artifact))
    if coverage_failure is not None or support_unresolved:
        coverage_dimension = _dimension(
            "promise_coverage_preservation",
            result="fail",
            finding=(
                coverage_failure[0]
                if coverage_failure is not None
                else "At least one committed coverage requirement remains unresolved."
            ),
            remediation=(
                coverage_failure[1]
                if coverage_failure is not None
                else "Resolve the committed coverage requirement before final review."
            ),
            provenance_refs=coverage_provenance,
        )
    else:
        coverage_dimension = _dimension(
            "promise_coverage_preservation",
            result="pass",
            finding=(
                "Committed promise coverage remains preserved through the exact "
                "Angle and Outline lineage."
                if selected.coverage
                else "This exact approved Angle has no explicit coverage commitments."
            ),
            provenance_refs=coverage_provenance,
        )

    role_failure = _semantic_failure(
        (*selected_semantic.findings, *outline_semantic.findings),
        codes={
            "angle_role_drift",
            "angle_scope_drift",
            "outline_role_drift",
            "outline_broad_summary_filler",
            "outline_relationship_invention",
        },
    )
    role_dimension = _dimension(
        "pillar_cluster_semantic_behavior",
        result="fail" if role_failure is not None else "pass",
        finding=(
            role_failure[0]
            if role_failure is not None
            else (
                "Pillar/Cluster role and bounded scope remain consistent across "
                "the exact approved Angle and Outline."
            )
        ),
        remediation=role_failure[1] if role_failure is not None else "",
        provenance_refs=(
            _artifact_ref(source.angle_semantic.artifact),
            _artifact_ref(source.outline_semantic.artifact),
        ),
    )

    audit_evaluation = source.source_copy_input.assertion_audit_evaluation
    audit_result = _result(audit_evaluation.result)
    evidence_dimension = _dimension(
        "evidence_support_contradiction",
        result=audit_result,
        finding=(
            "Assertion Audit preserved evidence support and contradiction boundaries."
            if audit_result == "pass"
            else "Assertion Audit retained evidence-support or contradiction warnings."
        ),
        remediation=(
            ""
            if audit_result == "pass"
            else "Resolve the reported evidence-support or contradiction warnings."
        ),
        provenance_refs=(
            _artifact_ref(source.source_copy_input.assertion_audit_artifact),
            _evaluation_ref(audit_evaluation),
            *(
                (_artifact_ref(support.artifact),)
                if support is not None
                else ()
            ),
        ),
    )

    raw_pack = source.writer_input.model_input.get("originality_pack")
    if not isinstance(raw_pack, dict):
        raise DeepQualityAuthorityError("deep_quality_originality_pack_missing")
    raw_items = raw_pack.get("items")
    if not isinstance(raw_items, list):
        raise DeepQualityAuthorityError("deep_quality_originality_pack_invalid")
    allowed_originality: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        source_ref = item.get("source_ref")
        if isinstance(source_ref, str) and source_ref.strip():
            allowed_originality.add(source_ref.strip())
    used_originality = {
        *source.source_draft.lead_originality_refs,
        *(
            ref
            for section in source.source_draft.sections
            for ref in section.originality_refs
        ),
    }
    outside = sorted(used_originality - allowed_originality)
    bundle = source.writer_input.outline_input.bundle
    if outside:
        originality_dimension = _dimension(
            "originality_provenance",
            result="fail",
            finding=(
                "Draft originality references escape the exact approved pack: "
                + ", ".join(outside)
            ),
            remediation="Remove or replace originality references outside the approved pack.",
            provenance_refs=(
                f"originality_pack:{bundle.originality_pack_id}:{bundle.originality_pack_hash}",
                _artifact_ref(source.human_voice_trace.artifact),
            ),
        )
    else:
        originality_dimension = _dimension(
            "originality_provenance",
            result="pass",
            finding=(
                "All originality references remain within the exact approved "
                "OriginalityPack and the exact Human Voice rewrite trace."
            ),
            provenance_refs=(
                f"originality_pack:{bundle.originality_pack_id}:{bundle.originality_pack_hash}",
                _artifact_ref(source.human_voice_trace.artifact),
            ),
        )

    assertion_dimension = _dimension(
        "assertion_factual_integrity",
        result=audit_result,
        finding=(
            "Assertion Audit passed on the exact revised draft."
            if audit_result == "pass"
            else "Assertion Audit returned warnings on the exact revised draft."
        ),
        remediation=(
            ""
            if audit_result == "pass"
            else "Resolve Assertion Audit warnings before Founder final review."
        ),
        provenance_refs=(
            _artifact_ref(source.source_copy_input.assertion_audit_artifact),
            _evaluation_ref(audit_evaluation),
        ),
    )

    copy_result = _result(source.source_copy.check.result)
    source_copy_dimension = _dimension(
        "source_copy_attribution_safety",
        result=copy_result,
        finding=(
            "Deterministic Source-copy check passed on the exact revised draft."
            if copy_result == "pass"
            else (
                "Deterministic Source-copy check reported "
                f"{source.source_copy.check.warn_count} warning(s)."
            )
        ),
        remediation=(
            ""
            if copy_result == "pass"
            else "Review and repair the reported source-copy overlap before final approval."
        ),
        provenance_refs=(
            _artifact_ref(source.source_copy.artifact),
            _evaluation_ref(source.source_copy.evaluation),
        ),
    )

    reader_result, reader_finding, reader_remediation, reader_refs = (
        _readiness_detail(source, stage="reader_value")
    )
    reader_dimension = _dimension(
        "reader_usefulness_decision_support",
        result=reader_result,
        finding=reader_finding,
        remediation=reader_remediation,
        provenance_refs=reader_refs,
    )

    search_result, search_finding, search_remediation, search_refs = (
        _readiness_detail(source, stage="search_ai")
    )
    search_dimension = _dimension(
        "search_ai_readability_without_truth_tradeoff",
        result=search_result,
        finding=search_finding,
        remediation=search_remediation,
        provenance_refs=(*search_refs, *reader_refs),
    )

    result = {
        item.key: item
        for item in (
            coverage_dimension,
            role_dimension,
            evidence_dimension,
            originality_dimension,
            assertion_dimension,
            source_copy_dimension,
            reader_dimension,
            search_dimension,
        )
    }
    if tuple(result) != AUTHORITATIVE_DEEP_QUALITY_DIMENSIONS:
        raise DeepQualityAuthorityError("deep_quality_authoritative_dimensions_mismatch")
    return result


__all__ = [
    "AUTHORITATIVE_DEEP_QUALITY_DIMENSIONS",
    "DeepQualityAuthorityError",
    "derive_authoritative_deep_quality_dimensions",
]
