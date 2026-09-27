"""CQ-06 bounded semantic evaluator for the four model-owned dimensions.

The evaluator receives no raw EvidenceSet/OriginalityPack and cannot rewrite content,
research, use tools, set provenance, or declare the overall Deep Quality verdict.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Protocol, cast

from app.modules.content_engine.journal.deep_quality import (
    DEEP_QUALITY_DIMENSIONS,
    SEMANTIC_MODEL_DIMENSIONS,
    DeepQualityDimension,
    DeepQualityResult,
)
from app.modules.content_engine.journal.deep_quality_input import DeepQualityInput
from app.modules.harness.models import Artifact

DEEP_QUALITY_SEMANTIC_SCHEMA_VERSION = 1
DEEP_QUALITY_SEMANTIC_GENERATOR_VERSION = "cq06.deep_quality_semantic.v1"
DEEP_QUALITY_SEMANTIC_DIMENSIONS = tuple(
    key for key in DEEP_QUALITY_DIMENSIONS if key in SEMANTIC_MODEL_DIMENSIONS
)


class DeepQualitySemanticError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class DeepQualitySemanticModelPort(Protocol):
    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class DeepQualitySemanticResult:
    dimensions: tuple[DeepQualityDimension, ...]
    model_attempts: int


def _artifact_ref(artifact: Artifact) -> str:
    return (
        f"artifact:{artifact.id}:v{artifact.version}:"
        f"{artifact.content_hash}"
    )


def _result(value: object) -> DeepQualityResult:
    if not isinstance(value, str) or value not in {"pass", "warn", "fail"}:
        raise DeepQualitySemanticError("deep_quality_semantic_result_invalid")
    return cast(DeepQualityResult, value)


def _provenance_refs(
    source: DeepQualityInput,
    *,
    key: str,
) -> tuple[str, ...]:
    draft_ref = _artifact_ref(source.source_artifact)
    if key == "title_angle_outline_draft_coherence":
        return (
            draft_ref,
            _artifact_ref(source.angle_semantic.artifact),
            _artifact_ref(source.outline_semantic.artifact),
        )
    if key == "human_voice_motgu_voice":
        return (
            draft_ref,
            _artifact_ref(source.human_voice_trace.artifact),
        )
    if key == "repetition_filler_ai_residue_system_language":
        return (draft_ref,)
    if key == "locale_specific_quality":
        return (
            draft_ref,
            (
                f"locale_variant:{source.writer_input.locale_variant.id}:"
                f"{source.writer_input.locale}"
            ),
        )
    raise DeepQualitySemanticError("deep_quality_semantic_dimension_unknown", key)


def build_deep_quality_semantic_model_input(
    source: DeepQualityInput,
) -> dict[str, object]:
    case = source.reader_value_input.content_case
    variant = source.writer_input.locale_variant
    return {
        "schema_version": DEEP_QUALITY_SEMANTIC_SCHEMA_VERSION,
        "locale": source.writer_input.locale,
        "source_draft_ref": {
            "id": str(source.source_artifact.id),
            "version": source.source_artifact.version,
            "content_hash": source.source_artifact.content_hash,
        },
        "source_draft": source.source_draft.to_dict(),
        "approved_angle": (
            source.writer_input.outline_input.approved_angle.candidate.to_dict()
        ),
        "outline": copy.deepcopy(source.writer_input.outline_payload),
        "content_case": {
            "reader_before": case.reader_before,
            "reader_after": case.reader_after,
            "content_hypothesis": case.content_hypothesis,
            "desired_action": case.desired_action,
        },
        "locale_variant": {
            "id": str(variant.id),
            "locale": variant.locale,
            "content_role": variant.content_role,
            "primary_question": variant.primary_question,
            "primary_intent": variant.primary_intent,
            "secondary_intent": variant.secondary_intent,
            "must_include": copy.deepcopy(variant.must_include_json),
            "must_not_claim": copy.deepcopy(variant.must_not_claim_json),
        },
        "human_voice_diagnostics": (
            source.human_voice_trace.style_comparison.to_dict()
        ),
        "evaluation_policy": {
            "dimensions": list(DEEP_QUALITY_SEMANTIC_DIMENSIONS),
            "result_order": ["pass", "warn", "fail"],
            "no_numeric_score": True,
            "no_overall_verdict": True,
            "no_research": True,
            "no_tools": True,
            "no_rewrite": True,
            "do_not_reclassify_factual_truth": True,
            "do_not_invent_provenance": True,
            "evaluate_only_supplied_locale": True,
        },
    }


def validate_deep_quality_semantic_output(
    raw: object,
    *,
    source: DeepQualityInput,
) -> tuple[DeepQualityDimension, ...]:
    if not isinstance(raw, dict) or set(raw) != {"locale", "dimensions"}:
        raise DeepQualitySemanticError("deep_quality_semantic_output_schema_invalid")
    if raw.get("locale") != source.writer_input.locale:
        raise DeepQualitySemanticError("deep_quality_semantic_output_locale_mismatch")
    raw_dimensions = raw.get("dimensions")
    if not isinstance(raw_dimensions, list):
        raise DeepQualitySemanticError("deep_quality_semantic_dimensions_invalid")
    if len(raw_dimensions) != len(DEEP_QUALITY_SEMANTIC_DIMENSIONS):
        raise DeepQualitySemanticError("deep_quality_semantic_dimensions_mismatch")

    dimensions: list[DeepQualityDimension] = []
    for expected_key, raw_item in zip(
        DEEP_QUALITY_SEMANTIC_DIMENSIONS,
        raw_dimensions,
        strict=True,
    ):
        if not isinstance(raw_item, dict) or set(raw_item) != {
            "key",
            "result",
            "finding",
            "remediation",
        }:
            raise DeepQualitySemanticError(
                "deep_quality_semantic_dimension_schema_invalid"
            )
        if raw_item.get("key") != expected_key:
            raise DeepQualitySemanticError(
                "deep_quality_semantic_dimension_order_mismatch"
            )
        result = _result(raw_item.get("result"))
        finding = raw_item.get("finding")
        remediation = raw_item.get("remediation")
        if not isinstance(finding, str) or not finding.strip():
            raise DeepQualitySemanticError(
                "deep_quality_semantic_finding_required"
            )
        if not isinstance(remediation, str):
            raise DeepQualitySemanticError(
                "deep_quality_semantic_remediation_invalid"
            )
        remediation = remediation.strip()
        if result == "pass" and remediation:
            raise DeepQualitySemanticError(
                "deep_quality_semantic_pass_remediation_forbidden"
            )
        if result in {"warn", "fail"} and not remediation:
            raise DeepQualitySemanticError(
                "deep_quality_semantic_remediation_required"
            )
        dimensions.append(
            DeepQualityDimension(
                key=expected_key,
                result=result,
                authority="semantic_model",
                finding=finding.strip(),
                remediation=remediation,
                provenance_refs=_provenance_refs(
                    source,
                    key=expected_key,
                ),
            )
        )
    return tuple(dimensions)


async def evaluate_deep_quality_semantics(
    source: DeepQualityInput,
    *,
    model: DeepQualitySemanticModelPort,
    max_attempts: int = 2,
) -> DeepQualitySemanticResult:
    if (
        isinstance(max_attempts, bool)
        or not isinstance(max_attempts, int)
        or max_attempts < 1
        or max_attempts > 2
    ):
        raise DeepQualitySemanticError("deep_quality_semantic_attempts_invalid")
    model_input = build_deep_quality_semantic_model_input(source)
    last_error: DeepQualitySemanticError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            raw = await model.generate(
                input_bundle=copy.deepcopy(model_input),
                attempt=attempt,
            )
            dimensions = validate_deep_quality_semantic_output(
                raw,
                source=source,
            )
        except DeepQualitySemanticError as exc:
            last_error = exc
            if attempt == max_attempts:
                raise DeepQualitySemanticError(
                    "deep_quality_semantic_model_output_invalid",
                    exc.code,
                ) from exc
            continue
        return DeepQualitySemanticResult(
            dimensions=dimensions,
            model_attempts=attempt,
        )
    raise DeepQualitySemanticError(
        "deep_quality_semantic_model_output_invalid"
    ) from last_error


__all__ = [
    "DEEP_QUALITY_SEMANTIC_DIMENSIONS",
    "DEEP_QUALITY_SEMANTIC_GENERATOR_VERSION",
    "DEEP_QUALITY_SEMANTIC_SCHEMA_VERSION",
    "DeepQualitySemanticError",
    "DeepQualitySemanticModelPort",
    "DeepQualitySemanticResult",
    "build_deep_quality_semantic_model_input",
    "evaluate_deep_quality_semantics",
    "validate_deep_quality_semantic_output",
]
