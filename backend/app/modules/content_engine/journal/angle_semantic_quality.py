"""CQ-04 immutable Angle semantic-quality artifact."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.semantic_quality import (
    SemanticQualityAssessment,
    SemanticQualityError,
    SemanticRole,
    angle_subject_refs,
    validate_semantic_quality_assessment,
)
from app.modules.harness.models import Artifact, StepRun

ANGLE_SEMANTIC_QUALITY_ARTIFACT_TYPE = "angle_semantic_quality"
ANGLE_SEMANTIC_QUALITY_GENERATOR_VERSION = "cq04.angle_semantic_quality.v2"


class AngleSemanticQualityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AngleSemanticCandidateRef:
    angle_id: str
    candidate_hash: str
    coverage_requirement_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AngleSemanticAssessmentEntry:
    candidate: AngleSemanticCandidateRef
    assessment: SemanticQualityAssessment

    def to_dict(self) -> dict[str, object]:
        return {
            "angle_id": self.candidate.angle_id,
            "candidate_hash": self.candidate.candidate_hash,
            "assessment": self.assessment.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class AngleSemanticQualityResult:
    artifact: Artifact
    entries: tuple[AngleSemanticAssessmentEntry, ...]

    @property
    def by_angle_id(self) -> dict[str, SemanticQualityAssessment]:
        return {entry.candidate.angle_id: entry.assessment for entry in self.entries}


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_support_depth_ref(
    value: object | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
        "id",
        "version",
        "content_hash",
    }:
        raise AngleSemanticQualityError(
            "angle_semantic_support_depth_ref_invalid"
        )
    raw_id = value.get("id")
    version = value.get("version")
    content_hash = value.get("content_hash")
    if (
        not isinstance(raw_id, str)
        or isinstance(version, bool)
        or not isinstance(version, int)
        or version <= 0
        or not isinstance(content_hash, str)
        or len(content_hash) != 64
        or any(ch not in "0123456789abcdef" for ch in content_hash)
    ):
        raise AngleSemanticQualityError(
            "angle_semantic_support_depth_ref_invalid"
        )
    try:
        artifact_id = UUID(raw_id)
    except ValueError as exc:
        raise AngleSemanticQualityError(
            "angle_semantic_support_depth_ref_invalid"
        ) from exc
    return {
        "id": str(artifact_id),
        "version": version,
        "content_hash": content_hash,
    }


def _decoded_candidates(raw: object) -> list[object]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AngleSemanticQualityError(
                "angle_semantic_output_json_invalid"
            ) from exc
    if isinstance(raw, dict):
        raw = raw.get("candidates")
    if not isinstance(raw, list):
        raise AngleSemanticQualityError("angle_semantic_output_invalid")
    return raw


def validate_angle_semantic_output(
    raw: object,
    *,
    candidates: tuple[AngleSemanticCandidateRef, ...],
    role: SemanticRole,
) -> tuple[AngleSemanticAssessmentEntry, ...]:
    raw_candidates = _decoded_candidates(raw)
    if len(raw_candidates) != len(candidates):
        raise AngleSemanticQualityError("angle_semantic_candidate_count_mismatch")
    expected_by_id = {candidate.angle_id: candidate for candidate in candidates}
    if len(expected_by_id) != len(candidates):
        raise AngleSemanticQualityError("angle_semantic_candidate_id_duplicate")

    entries: list[AngleSemanticAssessmentEntry] = []
    seen: set[str] = set()
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, dict):
            raise AngleSemanticQualityError("angle_semantic_candidate_invalid")
        angle_id = raw_candidate.get("angle_id")
        if not isinstance(angle_id, str) or angle_id not in expected_by_id:
            raise AngleSemanticQualityError("angle_semantic_candidate_unknown")
        if angle_id in seen:
            raise AngleSemanticQualityError("angle_semantic_candidate_duplicate")
        seen.add(angle_id)
        candidate = expected_by_id[angle_id]
        try:
            assessment = validate_semantic_quality_assessment(
                raw_candidate.get("semantic_quality"),
                expected_stage="angle",
                expected_role=role,
                allowed_subject_refs=angle_subject_refs(
                    angle_id=candidate.angle_id,
                    coverage_requirement_ids=candidate.coverage_requirement_ids,
                ),
            )
        except SemanticQualityError as exc:
            raise AngleSemanticQualityError(exc.code) from exc
        entries.append(
            AngleSemanticAssessmentEntry(
                candidate=candidate,
                assessment=assessment,
            )
        )
    if seen != set(expected_by_id):
        raise AngleSemanticQualityError("angle_semantic_candidate_incomplete")
    return tuple(
        next(entry for entry in entries if entry.candidate.angle_id == candidate.angle_id)
        for candidate in candidates
    )


async def _append_step_output_ref(
    session: AsyncSession,
    *,
    artifact: Artifact,
) -> None:
    if artifact.step_run_id is None:
        return
    step = await session.get(StepRun, artifact.step_run_id)
    if step is None or step.run_id != artifact.run_id:
        raise AngleSemanticQualityError("angle_semantic_step_binding_invalid")
    ref = str(artifact.id)
    if ref not in step.output_artifact_refs_json:
        step.output_artifact_refs_json = [*step.output_artifact_refs_json, ref]
        await session.flush()


async def persist_angle_semantic_quality(
    session: AsyncSession,
    *,
    angle_artifact: Artifact,
    role: SemanticRole,
    entries: tuple[AngleSemanticAssessmentEntry, ...],
    coverage_support_depth_ref: object | None = None,
) -> Artifact:
    if angle_artifact.artifact_type != "angle_candidates":
        raise AngleSemanticQualityError("angle_semantic_angle_artifact_invalid")
    if not entries:
        raise AngleSemanticQualityError("angle_semantic_entries_required")
    normalized_support_depth = _normalize_support_depth_ref(
        coverage_support_depth_ref
    )
    payload: dict[str, object] = {
        "schema_version": 1,
        "artifact_type": ANGLE_SEMANTIC_QUALITY_ARTIFACT_TYPE,
        "generator_version": ANGLE_SEMANTIC_QUALITY_GENERATOR_VERSION,
        "angle_artifact": {
            "id": str(angle_artifact.id),
            "version": angle_artifact.version,
            "content_hash": angle_artifact.content_hash,
        },
        "role": role,
        "coverage_support_depth": normalized_support_depth,
        "entries": [entry.to_dict() for entry in entries],
    }
    content_hash = _hash(payload)
    existing = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == angle_artifact.run_id,
            Artifact.artifact_type == ANGLE_SEMANTIC_QUALITY_ARTIFACT_TYPE,
            Artifact.content_hash == content_hash,
        )
    )
    if existing is not None:
        if existing.content_json != payload:
            raise AngleSemanticQualityError("angle_semantic_hash_collision")
        await _append_step_output_ref(session, artifact=existing)
        return existing

    latest_version = await session.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.run_id == angle_artifact.run_id,
            Artifact.artifact_type == ANGLE_SEMANTIC_QUALITY_ARTIFACT_TYPE,
        )
    )
    artifact = Artifact(
        run_id=angle_artifact.run_id,
        step_run_id=angle_artifact.step_run_id,
        artifact_type=ANGLE_SEMANTIC_QUALITY_ARTIFACT_TYPE,
        locale=angle_artifact.locale,
        version=(latest_version or 0) + 1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    await _append_step_output_ref(session, artifact=artifact)
    return artifact


def _validate_artifact_payload(
    artifact: Artifact,
    *,
    angle_artifact: Artifact,
    role: SemanticRole,
    candidates: tuple[AngleSemanticCandidateRef, ...],
    coverage_support_depth_ref: object | None,
) -> tuple[AngleSemanticAssessmentEntry, ...]:
    payload = artifact.content_json
    if (
        artifact.run_id != angle_artifact.run_id
        or artifact.artifact_type != ANGLE_SEMANTIC_QUALITY_ARTIFACT_TYPE
        or not isinstance(payload, dict)
        or _hash(payload) != artifact.content_hash
        or payload.get("schema_version") != 1
        or payload.get("artifact_type") != ANGLE_SEMANTIC_QUALITY_ARTIFACT_TYPE
        or payload.get("generator_version") != ANGLE_SEMANTIC_QUALITY_GENERATOR_VERSION
        or payload.get("role") != role
    ):
        raise AngleSemanticQualityError("angle_semantic_artifact_invalid")
    angle_ref = payload.get("angle_artifact")
    if (
        not isinstance(angle_ref, dict)
        or angle_ref.get("id") != str(angle_artifact.id)
        or angle_ref.get("version") != angle_artifact.version
        or angle_ref.get("content_hash") != angle_artifact.content_hash
    ):
        raise AngleSemanticQualityError("angle_semantic_angle_binding_stale")
    expected_support_depth = _normalize_support_depth_ref(
        coverage_support_depth_ref
    )
    if payload.get("coverage_support_depth") != expected_support_depth:
        raise AngleSemanticQualityError(
            "angle_semantic_support_depth_binding_stale"
        )
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or len(raw_entries) != len(candidates):
        raise AngleSemanticQualityError("angle_semantic_entries_invalid")

    expected = {candidate.angle_id: candidate for candidate in candidates}
    entries: list[AngleSemanticAssessmentEntry] = []
    seen: set[str] = set()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict) or set(raw_entry) != {
            "angle_id",
            "candidate_hash",
            "assessment",
        }:
            raise AngleSemanticQualityError("angle_semantic_entry_invalid")
        angle_id = raw_entry.get("angle_id")
        if (
            not isinstance(angle_id, str)
            or angle_id not in expected
            or angle_id in seen
        ):
            raise AngleSemanticQualityError("angle_semantic_entry_binding_invalid")
        candidate = expected[angle_id]
        if raw_entry.get("candidate_hash") != candidate.candidate_hash:
            raise AngleSemanticQualityError("angle_semantic_candidate_hash_stale")
        try:
            assessment = validate_semantic_quality_assessment(
                raw_entry.get("assessment"),
                expected_stage="angle",
                expected_role=role,
                allowed_subject_refs=angle_subject_refs(
                    angle_id=candidate.angle_id,
                    coverage_requirement_ids=candidate.coverage_requirement_ids,
                ),
            )
        except SemanticQualityError as exc:
            raise AngleSemanticQualityError(exc.code) from exc
        seen.add(angle_id)
        entries.append(
            AngleSemanticAssessmentEntry(
                candidate=candidate,
                assessment=assessment,
            )
        )
    if seen != set(expected):
        raise AngleSemanticQualityError("angle_semantic_entries_incomplete")
    return tuple(
        next(entry for entry in entries if entry.candidate.angle_id == candidate.angle_id)
        for candidate in candidates
    )


def _artifact_binds_angle(
    artifact: Artifact,
    *,
    angle_artifact_id: object,
) -> bool:
    payload = artifact.content_json
    if not isinstance(payload, dict):
        return False
    angle_ref = payload.get("angle_artifact")
    if not isinstance(angle_ref, dict):
        return False
    return angle_ref.get("id") == str(angle_artifact_id)


async def load_angle_semantic_quality(
    session: AsyncSession,
    *,
    angle_artifact: Artifact,
    role: SemanticRole,
    candidates: tuple[AngleSemanticCandidateRef, ...],
    coverage_support_depth_ref: object | None = None,
) -> AngleSemanticQualityResult:
    rows = list(
        (
            await session.scalars(
                select(Artifact)
                .where(
                    Artifact.run_id == angle_artifact.run_id,
                    Artifact.artifact_type == ANGLE_SEMANTIC_QUALITY_ARTIFACT_TYPE,
                )
                .order_by(Artifact.version, Artifact.id)
            )
        ).all()
    )
    matches = [
        artifact
        for artifact in rows
        if _artifact_binds_angle(
            artifact,
            angle_artifact_id=angle_artifact.id,
        )
    ]
    if len(matches) != 1:
        raise AngleSemanticQualityError(
            "angle_semantic_artifact_required"
            if not matches
            else "angle_semantic_artifact_conflict"
        )
    artifact = matches[0]
    entries = _validate_artifact_payload(
        artifact,
        angle_artifact=angle_artifact,
        role=role,
        candidates=candidates,
        coverage_support_depth_ref=coverage_support_depth_ref,
    )
    return AngleSemanticQualityResult(artifact=artifact, entries=entries)


async def require_angle_semantic_pass(
    session: AsyncSession,
    *,
    angle_artifact: Artifact,
    role: SemanticRole,
    candidates: tuple[AngleSemanticCandidateRef, ...],
    selected_angle_id: str,
    coverage_support_depth_ref: object | None = None,
) -> SemanticQualityAssessment:
    result = await load_angle_semantic_quality(
        session,
        angle_artifact=angle_artifact,
        role=role,
        candidates=candidates,
        coverage_support_depth_ref=coverage_support_depth_ref,
    )
    assessment = result.by_angle_id.get(selected_angle_id)
    if assessment is None:
        raise AngleSemanticQualityError("angle_semantic_selected_candidate_missing")
    if assessment.verdict != "pass":
        raise AngleSemanticQualityError("angle_semantic_revision_required")
    return assessment


__all__ = [
    "ANGLE_SEMANTIC_QUALITY_ARTIFACT_TYPE",
    "ANGLE_SEMANTIC_QUALITY_GENERATOR_VERSION",
    "AngleSemanticAssessmentEntry",
    "AngleSemanticCandidateRef",
    "AngleSemanticQualityError",
    "AngleSemanticQualityResult",
    "load_angle_semantic_quality",
    "persist_angle_semantic_quality",
    "require_angle_semantic_pass",
    "validate_angle_semantic_output",
]
