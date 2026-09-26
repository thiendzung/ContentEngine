"""CQ-04 immutable Outline semantic-quality artifact."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.semantic_quality import (
    SemanticQualityAssessment,
    SemanticQualityError,
    SemanticRole,
    outline_subject_refs,
    validate_semantic_quality_assessment,
)
from app.modules.harness.models import Artifact, StepRun

OUTLINE_SEMANTIC_QUALITY_ARTIFACT_TYPE = "outline_semantic_quality"
OUTLINE_SEMANTIC_QUALITY_GENERATOR_VERSION = "cq04.outline_semantic_quality.v1"


class OutlineSemanticQualityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutlineSemanticQualityResult:
    artifact: Artifact
    assessment: SemanticQualityAssessment


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decode_payload(raw: object) -> dict[str, object]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OutlineSemanticQualityError(
                "outline_semantic_output_json_invalid"
            ) from exc
    if not isinstance(raw, dict):
        raise OutlineSemanticQualityError("outline_semantic_output_invalid")
    return raw


def validate_outline_semantic_output(
    raw: object,
    *,
    role: SemanticRole,
    section_ids: tuple[str, ...],
    coverage_requirement_ids: tuple[str, ...],
) -> SemanticQualityAssessment:
    payload = _decode_payload(raw)
    try:
        return validate_semantic_quality_assessment(
            payload.get("semantic_quality"),
            expected_stage="outline",
            expected_role=role,
            allowed_subject_refs=outline_subject_refs(
                section_ids=section_ids,
                coverage_requirement_ids=coverage_requirement_ids,
            ),
        )
    except SemanticQualityError as exc:
        raise OutlineSemanticQualityError(exc.code) from exc


async def _append_step_output_ref(
    session: AsyncSession,
    *,
    artifact: Artifact,
) -> None:
    if artifact.step_run_id is None:
        return
    step = await session.get(StepRun, artifact.step_run_id)
    if step is None or step.run_id != artifact.run_id:
        raise OutlineSemanticQualityError("outline_semantic_step_binding_invalid")
    ref = str(artifact.id)
    if ref not in step.output_artifact_refs_json:
        step.output_artifact_refs_json = [*step.output_artifact_refs_json, ref]
        await session.flush()


async def persist_outline_semantic_quality(
    session: AsyncSession,
    *,
    outline_artifact: Artifact,
    role: SemanticRole,
    assessment: SemanticQualityAssessment,
) -> Artifact:
    if outline_artifact.artifact_type != "journal_outline":
        raise OutlineSemanticQualityError("outline_semantic_outline_artifact_invalid")
    if assessment.stage != "outline" or assessment.role != role:
        raise OutlineSemanticQualityError("outline_semantic_assessment_binding_invalid")

    payload: dict[str, object] = {
        "schema_version": 1,
        "artifact_type": OUTLINE_SEMANTIC_QUALITY_ARTIFACT_TYPE,
        "generator_version": OUTLINE_SEMANTIC_QUALITY_GENERATOR_VERSION,
        "outline_artifact": {
            "id": str(outline_artifact.id),
            "version": outline_artifact.version,
            "content_hash": outline_artifact.content_hash,
        },
        "role": role,
        "assessment": assessment.to_dict(),
    }
    content_hash = _hash(payload)
    existing = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == outline_artifact.run_id,
            Artifact.artifact_type == OUTLINE_SEMANTIC_QUALITY_ARTIFACT_TYPE,
            Artifact.content_hash == content_hash,
        )
    )
    if existing is not None:
        if existing.content_json != payload:
            raise OutlineSemanticQualityError("outline_semantic_hash_collision")
        await _append_step_output_ref(session, artifact=existing)
        return existing

    latest_version = await session.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.run_id == outline_artifact.run_id,
            Artifact.artifact_type == OUTLINE_SEMANTIC_QUALITY_ARTIFACT_TYPE,
        )
    )
    artifact = Artifact(
        run_id=outline_artifact.run_id,
        step_run_id=outline_artifact.step_run_id,
        artifact_type=OUTLINE_SEMANTIC_QUALITY_ARTIFACT_TYPE,
        locale=outline_artifact.locale,
        version=(latest_version or 0) + 1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    await _append_step_output_ref(session, artifact=artifact)
    return artifact


def _artifact_binds_outline(
    artifact: Artifact,
    *,
    outline_artifact_id: object,
) -> bool:
    payload = artifact.content_json
    if not isinstance(payload, dict):
        return False
    outline_ref = payload.get("outline_artifact")
    if not isinstance(outline_ref, dict):
        return False
    return outline_ref.get("id") == str(outline_artifact_id)


def _validate_artifact(
    artifact: Artifact,
    *,
    outline_artifact: Artifact,
    role: SemanticRole,
    section_ids: tuple[str, ...],
    coverage_requirement_ids: tuple[str, ...],
) -> SemanticQualityAssessment:
    payload = artifact.content_json
    if (
        artifact.run_id != outline_artifact.run_id
        or artifact.artifact_type != OUTLINE_SEMANTIC_QUALITY_ARTIFACT_TYPE
        or not isinstance(payload, dict)
        or _hash(payload) != artifact.content_hash
        or payload.get("schema_version") != 1
        or payload.get("artifact_type") != OUTLINE_SEMANTIC_QUALITY_ARTIFACT_TYPE
        or payload.get("generator_version") != OUTLINE_SEMANTIC_QUALITY_GENERATOR_VERSION
        or payload.get("role") != role
    ):
        raise OutlineSemanticQualityError("outline_semantic_artifact_invalid")

    outline_ref = payload.get("outline_artifact")
    if (
        not isinstance(outline_ref, dict)
        or outline_ref.get("id") != str(outline_artifact.id)
        or outline_ref.get("version") != outline_artifact.version
        or outline_ref.get("content_hash") != outline_artifact.content_hash
    ):
        raise OutlineSemanticQualityError("outline_semantic_outline_binding_stale")

    try:
        return validate_semantic_quality_assessment(
            payload.get("assessment"),
            expected_stage="outline",
            expected_role=role,
            allowed_subject_refs=outline_subject_refs(
                section_ids=section_ids,
                coverage_requirement_ids=coverage_requirement_ids,
            ),
        )
    except SemanticQualityError as exc:
        raise OutlineSemanticQualityError(exc.code) from exc


async def load_outline_semantic_quality(
    session: AsyncSession,
    *,
    outline_artifact: Artifact,
    role: SemanticRole,
    section_ids: tuple[str, ...],
    coverage_requirement_ids: tuple[str, ...],
) -> OutlineSemanticQualityResult:
    rows = list(
        (
            await session.scalars(
                select(Artifact)
                .where(
                    Artifact.run_id == outline_artifact.run_id,
                    Artifact.artifact_type == OUTLINE_SEMANTIC_QUALITY_ARTIFACT_TYPE,
                )
                .order_by(Artifact.version, Artifact.id)
            )
        ).all()
    )
    matches = [
        artifact
        for artifact in rows
        if _artifact_binds_outline(
            artifact,
            outline_artifact_id=outline_artifact.id,
        )
    ]
    if len(matches) != 1:
        raise OutlineSemanticQualityError(
            "outline_semantic_artifact_required"
            if not matches
            else "outline_semantic_artifact_conflict"
        )
    artifact = matches[0]
    assessment = _validate_artifact(
        artifact,
        outline_artifact=outline_artifact,
        role=role,
        section_ids=section_ids,
        coverage_requirement_ids=coverage_requirement_ids,
    )
    return OutlineSemanticQualityResult(
        artifact=artifact,
        assessment=assessment,
    )


__all__ = [
    "OUTLINE_SEMANTIC_QUALITY_ARTIFACT_TYPE",
    "OUTLINE_SEMANTIC_QUALITY_GENERATOR_VERSION",
    "OutlineSemanticQualityError",
    "OutlineSemanticQualityResult",
    "load_outline_semantic_quality",
    "persist_outline_semantic_quality",
    "validate_outline_semantic_output",
]
