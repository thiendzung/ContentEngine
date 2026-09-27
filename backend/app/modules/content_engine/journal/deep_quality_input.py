"""CQ-06 exact Deep Quality input lineage loader.

This loader composes existing validated CQ-03/04/05 and F4 quality contracts.
It never resolves "latest" artifacts and never infers provenance from prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.angle import (
    AngleGenerationError,
    load_approved_angle_semantic_quality,
)
from app.modules.content_engine.journal.angle_semantic_quality import (
    AngleSemanticQualityResult,
)
from app.modules.content_engine.journal.coverage_support_depth_eval import (
    CoverageSupportDepthResult,
    CoverageSupportDepthRuntimeError,
    load_validated_coverage_support_depth_artifact,
)
from app.modules.content_engine.journal.human_voice_trace import (
    HumanVoiceTraceError,
    HumanVoiceTraceResult,
    require_human_voice_trace_for_rewritten_artifact,
)
from app.modules.content_engine.journal.outline import (
    OutlineGenerationError,
    load_persisted_outline_semantic_quality,
)
from app.modules.content_engine.journal.outline_semantic_quality import (
    OutlineSemanticQualityResult,
)
from app.modules.content_engine.journal.quality_readiness import (
    QualityReadinessError,
    QualityReadinessInput,
    QualityReadinessResult,
    load_persisted_quality_readiness_result,
    load_quality_readiness_input,
)
from app.modules.content_engine.journal.source_copy import (
    SourceCopyError,
    SourceCopyInput,
    SourceCopyResult,
    load_persisted_source_copy_result,
    load_source_copy_input,
)
from app.modules.content_engine.journal.writer import JournalDraft, WriterInput
from app.modules.harness.models import Artifact, QualityEvaluation


class DeepQualityInputError(ValueError):
    """Stable fail-closed CQ-06 lineage error."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class DeepQualityInput:
    writer_input: WriterInput
    source_artifact: Artifact
    source_draft: JournalDraft
    coverage_support_depth: CoverageSupportDepthResult | None
    angle_semantic: AngleSemanticQualityResult
    outline_semantic: OutlineSemanticQualityResult
    human_voice_trace: HumanVoiceTraceResult
    source_copy_input: SourceCopyInput
    source_copy: SourceCopyResult
    reader_value_input: QualityReadinessInput
    reader_value: QualityReadinessResult
    search_ai_input: QualityReadinessInput
    search_ai: QualityReadinessResult


def _assert_snapshot(
    artifact: Artifact,
    *,
    expected_version: int,
    expected_hash: str,
    code: str,
) -> None:
    if (
        artifact.version != expected_version
        or artifact.content_hash != expected_hash
    ):
        raise DeepQualityInputError(code)


def _support_depth_ref(
    angle_semantic: AngleSemanticQualityResult,
) -> dict[str, object] | None:
    payload = angle_semantic.artifact.content_json
    if not isinstance(payload, dict):
        raise DeepQualityInputError("deep_quality_angle_semantic_payload_invalid")
    raw = payload.get("coverage_support_depth")
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {"id", "version", "content_hash"}:
        raise DeepQualityInputError("deep_quality_support_depth_ref_invalid")
    raw_id = raw.get("id")
    version = raw.get("version")
    content_hash = raw.get("content_hash")
    if (
        not isinstance(raw_id, str)
        or not isinstance(version, int)
        or isinstance(version, bool)
        or version <= 0
        or not isinstance(content_hash, str)
    ):
        raise DeepQualityInputError("deep_quality_support_depth_ref_invalid")
    try:
        artifact_id = UUID(raw_id)
    except ValueError as exc:
        raise DeepQualityInputError("deep_quality_support_depth_ref_invalid") from exc
    return {
        "id": artifact_id,
        "version": version,
        "content_hash": content_hash,
    }


async def _load_support_depth(
    session: AsyncSession,
    *,
    writer_input: WriterInput,
    angle_semantic: AngleSemanticQualityResult,
) -> CoverageSupportDepthResult | None:
    selected = writer_input.outline_input.approved_angle.candidate
    ref = _support_depth_ref(angle_semantic)
    if ref is None:
        if selected.coverage:
            raise DeepQualityInputError("deep_quality_support_depth_required")
        return None

    artifact = await session.get(Artifact, cast(UUID, ref["id"]))
    if (
        artifact is None
        or artifact.version != ref["version"]
        or artifact.content_hash != ref["content_hash"]
        or artifact.step_run_id is None
    ):
        raise DeepQualityInputError("deep_quality_support_depth_snapshot_mismatch")

    opportunity = writer_input.outline_input.bundle.opportunity
    raw_opportunity_id = opportunity.get("id")
    if not isinstance(raw_opportunity_id, str):
        raise DeepQualityInputError("deep_quality_opportunity_ref_invalid")
    try:
        opportunity_id = UUID(raw_opportunity_id)
    except ValueError as exc:
        raise DeepQualityInputError("deep_quality_opportunity_ref_invalid") from exc

    try:
        result = await load_validated_coverage_support_depth_artifact(
            session,
            artifact_id=artifact.id,
            run_id=writer_input.outline_input.approved_angle.artifact.run_id,
            step_run_id=artifact.step_run_id,
            content_case_id=writer_input.writer_run.content_case_id,
            opportunity_id=opportunity_id,
            evidence_set_id=writer_input.outline_input.bundle.evidence_set_id,
            originality_pack_id=writer_input.outline_input.bundle.originality_pack_id,
        )
    except CoverageSupportDepthRuntimeError as exc:
        raise DeepQualityInputError(
            "deep_quality_support_depth_invalid",
            exc.code,
        ) from exc
    if not result.ready_for_angle or result.unresolved_requirement_ids:
        raise DeepQualityInputError("deep_quality_support_depth_unresolved")
    return result


async def load_deep_quality_input(
    session: AsyncSession,
    *,
    writer_run_id: UUID,
    source_draft_artifact_id: UUID,
    expected_source_draft_version: int,
    expected_source_draft_hash: str,
    outline_artifact_id: UUID,
    expected_outline_version: int,
    expected_outline_hash: str,
    assertion_audit_artifact_id: UUID,
    expected_assertion_audit_version: int,
    expected_assertion_audit_hash: str,
    assertion_audit_quality_evaluation_id: UUID,
    source_copy_artifact_id: UUID,
    expected_source_copy_version: int,
    expected_source_copy_hash: str,
    source_copy_quality_evaluation_id: UUID,
    reader_value_artifact_id: UUID,
    expected_reader_value_version: int,
    expected_reader_value_hash: str,
    reader_value_quality_evaluation_id: UUID,
    search_ai_artifact_id: UUID,
    expected_search_ai_version: int,
    expected_search_ai_hash: str,
    search_ai_quality_evaluation_id: UUID,
    locale: str,
) -> DeepQualityInput:
    try:
        source_copy_input = await load_source_copy_input(
            session,
            writer_run_id=writer_run_id,
            source_draft_artifact_id=source_draft_artifact_id,
            expected_source_draft_version=expected_source_draft_version,
            expected_source_draft_hash=expected_source_draft_hash,
            assertion_audit_artifact_id=assertion_audit_artifact_id,
            expected_assertion_audit_version=expected_assertion_audit_version,
            expected_assertion_audit_hash=expected_assertion_audit_hash,
            assertion_audit_quality_evaluation_id=assertion_audit_quality_evaluation_id,
            outline_artifact_id=outline_artifact_id,
            expected_outline_version=expected_outline_version,
            expected_outline_hash=expected_outline_hash,
            locale=locale,
        )
        source_copy = await load_persisted_source_copy_result(
            session,
            source_input=source_copy_input,
            artifact_id=source_copy_artifact_id,
            evaluation_id=source_copy_quality_evaluation_id,
        )
    except SourceCopyError as exc:
        raise DeepQualityInputError("deep_quality_source_copy_invalid", exc.code) from exc

    _assert_snapshot(
        source_copy.artifact,
        expected_version=expected_source_copy_version,
        expected_hash=expected_source_copy_hash,
        code="deep_quality_source_copy_snapshot_mismatch",
    )
    writer_input = source_copy_input.writer_input
    source_artifact = source_copy_input.source_artifact
    source_draft = source_copy_input.source_draft

    try:
        angle_semantic = await load_approved_angle_semantic_quality(
            session,
            approved=writer_input.outline_input.approved_angle,
            bundle=writer_input.outline_input.bundle,
        )
    except AngleGenerationError as exc:
        raise DeepQualityInputError("deep_quality_angle_semantic_invalid", exc.code) from exc
    if angle_semantic is None:
        raise DeepQualityInputError("deep_quality_angle_semantic_required")

    try:
        _outline, outline_semantic = await load_persisted_outline_semantic_quality(
            session,
            artifact=writer_input.outline_artifact,
            outline_input=writer_input.outline_input,
        )
    except OutlineGenerationError as exc:
        raise DeepQualityInputError("deep_quality_outline_semantic_invalid", exc.code) from exc
    if outline_semantic is None:
        raise DeepQualityInputError("deep_quality_outline_semantic_required")

    try:
        human_voice_trace = await require_human_voice_trace_for_rewritten_artifact(
            session,
            writer_input=writer_input,
            rewritten_artifact=source_artifact,
            rewritten_draft=source_draft,
        )
    except HumanVoiceTraceError as exc:
        raise DeepQualityInputError("deep_quality_human_voice_trace_invalid", exc.code) from exc

    coverage_support_depth = await _load_support_depth(
        session,
        writer_input=writer_input,
        angle_semantic=angle_semantic,
    )

    try:
        reader_input = await load_quality_readiness_input(
            session,
            stage="reader_value",
            writer_run_id=writer_run_id,
            source_draft_artifact_id=source_artifact.id,
            expected_source_draft_version=source_artifact.version,
            expected_source_draft_hash=source_artifact.content_hash,
            outline_artifact_id=outline_artifact_id,
            expected_outline_version=expected_outline_version,
            expected_outline_hash=expected_outline_hash,
            source_copy_artifact_id=source_copy.artifact.id,
            source_copy_quality_evaluation_id=source_copy.evaluation.id,
            locale=locale,
        )
        reader_value = await load_persisted_quality_readiness_result(
            session,
            source_input=reader_input,
            artifact_id=reader_value_artifact_id,
            evaluation_id=reader_value_quality_evaluation_id,
        )
    except QualityReadinessError as exc:
        raise DeepQualityInputError("deep_quality_reader_value_invalid", exc.code) from exc

    _assert_snapshot(
        reader_value.artifact,
        expected_version=expected_reader_value_version,
        expected_hash=expected_reader_value_hash,
        code="deep_quality_reader_value_snapshot_mismatch",
    )

    try:
        search_input = await load_quality_readiness_input(
            session,
            stage="search_ai",
            writer_run_id=writer_run_id,
            source_draft_artifact_id=source_artifact.id,
            expected_source_draft_version=source_artifact.version,
            expected_source_draft_hash=source_artifact.content_hash,
            outline_artifact_id=outline_artifact_id,
            expected_outline_version=expected_outline_version,
            expected_outline_hash=expected_outline_hash,
            source_copy_artifact_id=source_copy.artifact.id,
            source_copy_quality_evaluation_id=source_copy.evaluation.id,
            locale=locale,
            reader_value_artifact_id=reader_value.artifact.id,
            reader_value_quality_evaluation_id=reader_value.evaluation.id,
        )
        search_ai = await load_persisted_quality_readiness_result(
            session,
            source_input=search_input,
            artifact_id=search_ai_artifact_id,
            evaluation_id=search_ai_quality_evaluation_id,
        )
    except QualityReadinessError as exc:
        raise DeepQualityInputError("deep_quality_search_ai_invalid", exc.code) from exc

    _assert_snapshot(
        search_ai.artifact,
        expected_version=expected_search_ai_version,
        expected_hash=expected_search_ai_hash,
        code="deep_quality_search_ai_snapshot_mismatch",
    )

    return DeepQualityInput(
        writer_input=writer_input,
        source_artifact=source_artifact,
        source_draft=source_draft,
        coverage_support_depth=coverage_support_depth,
        angle_semantic=angle_semantic,
        outline_semantic=outline_semantic,
        human_voice_trace=human_voice_trace,
        source_copy_input=source_copy_input,
        source_copy=source_copy,
        reader_value_input=reader_input,
        reader_value=reader_value,
        search_ai_input=search_input,
        search_ai=search_ai,
    )


def _artifact_ref_parts(
    value: object,
    *,
    code: str,
) -> tuple[UUID, int, str]:
    if not isinstance(value, dict) or set(value) != {
        "id",
        "version",
        "content_hash",
    }:
        raise DeepQualityInputError(code)
    raw_id = value.get("id")
    version = value.get("version")
    content_hash = value.get("content_hash")
    if (
        not isinstance(raw_id, str)
        or not isinstance(version, int)
        or isinstance(version, bool)
        or version <= 0
        or not isinstance(content_hash, str)
        or not content_hash
    ):
        raise DeepQualityInputError(code)
    try:
        artifact_id = UUID(raw_id)
    except ValueError as exc:
        raise DeepQualityInputError(code) from exc
    return artifact_id, version, content_hash


async def load_deep_quality_input_from_search_result(
    session: AsyncSession,
    *,
    source_input: QualityReadinessInput,
    search_artifact: Artifact,
    search_evaluation: QualityEvaluation,
) -> DeepQualityInput:
    if (
        source_input.stage != "search_ai"
        or source_input.reader_value_artifact is None
        or source_input.reader_value_evaluation is None
        or search_artifact.locale != source_input.writer_input.locale
    ):
        raise DeepQualityInputError("deep_quality_search_handoff_invalid")

    try:
        validated_search = await load_persisted_quality_readiness_result(
            session,
            source_input=source_input,
            artifact_id=search_artifact.id,
            evaluation_id=search_evaluation.id,
        )
    except QualityReadinessError as exc:
        raise DeepQualityInputError(
            "deep_quality_search_ai_invalid",
            exc.code,
        ) from exc

    source_copy_payload = source_input.source_copy_artifact.content_json
    if not isinstance(source_copy_payload, dict):
        raise DeepQualityInputError("deep_quality_source_copy_payload_invalid")
    audit_payload = source_copy_payload.get("assertion_audit")
    if not isinstance(audit_payload, dict):
        raise DeepQualityInputError("deep_quality_audit_ref_invalid")
    audit_id, audit_version, audit_hash = _artifact_ref_parts(
        audit_payload.get("artifact"),
        code="deep_quality_audit_ref_invalid",
    )
    raw_audit_evaluation_id = audit_payload.get("quality_evaluation_id")
    if not isinstance(raw_audit_evaluation_id, str):
        raise DeepQualityInputError("deep_quality_audit_ref_invalid")
    try:
        audit_evaluation_id = UUID(raw_audit_evaluation_id)
    except ValueError as exc:
        raise DeepQualityInputError("deep_quality_audit_ref_invalid") from exc

    return await load_deep_quality_input(
        session,
        writer_run_id=source_input.writer_input.writer_run.id,
        source_draft_artifact_id=source_input.source_artifact.id,
        expected_source_draft_version=source_input.source_artifact.version,
        expected_source_draft_hash=source_input.source_artifact.content_hash,
        outline_artifact_id=source_input.writer_input.outline_artifact.id,
        expected_outline_version=source_input.writer_input.outline_artifact.version,
        expected_outline_hash=source_input.writer_input.outline_artifact.content_hash,
        assertion_audit_artifact_id=audit_id,
        expected_assertion_audit_version=audit_version,
        expected_assertion_audit_hash=audit_hash,
        assertion_audit_quality_evaluation_id=audit_evaluation_id,
        source_copy_artifact_id=source_input.source_copy_artifact.id,
        expected_source_copy_version=source_input.source_copy_artifact.version,
        expected_source_copy_hash=source_input.source_copy_artifact.content_hash,
        source_copy_quality_evaluation_id=source_input.source_copy_evaluation.id,
        reader_value_artifact_id=source_input.reader_value_artifact.id,
        expected_reader_value_version=source_input.reader_value_artifact.version,
        expected_reader_value_hash=source_input.reader_value_artifact.content_hash,
        reader_value_quality_evaluation_id=source_input.reader_value_evaluation.id,
        search_ai_artifact_id=validated_search.artifact.id,
        expected_search_ai_version=validated_search.artifact.version,
        expected_search_ai_hash=validated_search.artifact.content_hash,
        search_ai_quality_evaluation_id=validated_search.evaluation.id,
        locale=source_input.writer_input.locale,
    )


__all__ = [
    "DeepQualityInput",
    "DeepQualityInputError",
    "load_deep_quality_input",
    "load_deep_quality_input_from_search_result",
]
