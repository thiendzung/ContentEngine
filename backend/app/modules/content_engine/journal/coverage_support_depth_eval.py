"""CQ-03 runtime for exact per-coverage Evidence/Originality depth assessment."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.coverage_support_depth import (
    COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION,
    CoverageSupportDepthAssessment,
    CoverageSupportDepthError,
    validate_coverage_support_depth,
)
from app.modules.content_engine.models import ContentCase, ContentOpportunity
from app.modules.harness.models import Artifact, ContentRun, StepRun
from app.modules.knowledge.models import Claim, Evidence, EvidenceSet, OriginalityPack
from app.modules.knowledge.originality_pack import originality_pack_snapshot_hash
from app.modules.knowledge.persistence import evidence_set_hash
from app.modules.research.evidence.contracts import is_usable_originality_item

COVERAGE_SUPPORT_DEPTH_ARTIFACT_TYPE = "coverage_support_depth"
COVERAGE_SUPPORT_DEPTH_GENERATOR_VERSION = "cq03.coverage_support_depth.v1"


class CoverageSupportDepthRuntimeError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class CoverageSupportDepthModelPort(Protocol):
    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class CoverageSupportDepthInput:
    content_case: ContentCase
    opportunity: ContentOpportunity
    evidence_set: EvidenceSet
    originality_pack: OriginalityPack
    model_input: dict[str, object]
    input_snapshot_hash: str


@dataclass(frozen=True, slots=True)
class CoverageSupportDepthResult:
    artifact: Artifact
    assessment: CoverageSupportDepthAssessment
    ready_for_angle: bool
    unresolved_requirement_ids: tuple[str, ...]
    model_attempts: int
    reused: bool


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CoverageSupportDepthRuntimeError(code)
    return cast(dict[str, object], value)


def build_coverage_support_depth_model_input(
    *,
    coverage_requirements: list[str],
    evidence_items: list[dict[str, object]],
    originality_items: list[object],
    evidence_set_ref: dict[str, object],
    originality_pack_ref: dict[str, object],
) -> dict[str, object]:
    requirements = [
        {"id": f"coverage-{index + 1}", "requirement": requirement}
        for index, requirement in enumerate(coverage_requirements)
    ]
    usable_originality = [
        copy.deepcopy(item)
        for item in originality_items
        if is_usable_originality_item(item)
    ]
    return {
        "schema_version": COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION,
        "coverage_requirements": requirements,
        "evidence_set": copy.deepcopy(evidence_set_ref),
        "evidence": copy.deepcopy(evidence_items),
        "originality_pack": {
            **copy.deepcopy(originality_pack_ref),
            "items": usable_originality,
        },
        "assessment_policy": {
            "statuses": [
                "evidence_supported",
                "originality_supported",
                "mixed",
                "unresolved",
            ],
            "every_requirement_exactly_once": True,
            "cite_only_allowed_refs": True,
            "context_only_is_not_factual_support": True,
            "qualifying_evidence_is_not_clean_factual_support": True,
            "contradicting_evidence_requires_resolution": True,
            "lexical_overlap_is_not_semantic_proof": True,
            "numeric_quality_score_forbidden": True,
            "do_not_invent_artist_or_motgu_facts": True,
        },
    }


async def load_coverage_support_depth_input(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    opportunity_id: UUID,
    evidence_set_id: UUID,
    originality_pack_id: UUID,
) -> CoverageSupportDepthInput:
    case = await session.get(ContentCase, content_case_id)
    opportunity = await session.get(ContentOpportunity, opportunity_id)
    evidence_set = await session.get(EvidenceSet, evidence_set_id)
    originality_pack = await session.get(OriginalityPack, originality_pack_id)

    if case is None or case.content_type != "journal":
        raise CoverageSupportDepthRuntimeError("coverage_support_case_invalid")
    if (
        opportunity is None
        or opportunity.id != case.content_opportunity_id
        or opportunity.project_id != case.project_id
    ):
        raise CoverageSupportDepthRuntimeError("coverage_support_opportunity_invalid")
    if (
        evidence_set is None
        or evidence_set.project_id != case.project_id
        or evidence_set.content_case_id != case.id
        or evidence_set.status != "locked"
        or evidence_set.locked_at is None
        or evidence_set.content_hash != evidence_set_hash(evidence_set.evidence_ids_json)
    ):
        raise CoverageSupportDepthRuntimeError("coverage_support_evidence_set_invalid")
    if (
        originality_pack is None
        or originality_pack.content_case_id != case.id
        or originality_pack.status != "approved"
        or originality_pack.snapshot_hash is None
        or originality_pack.snapshot_hash
        != originality_pack_snapshot_hash(originality_pack)
    ):
        raise CoverageSupportDepthRuntimeError("coverage_support_originality_pack_invalid")

    raw_ids = evidence_set.evidence_ids_json
    if not isinstance(raw_ids, list):
        raise CoverageSupportDepthRuntimeError("coverage_support_evidence_ids_invalid")
    evidence_items: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for raw_id in raw_ids:
        if not isinstance(raw_id, str):
            raise CoverageSupportDepthRuntimeError("coverage_support_evidence_id_invalid")
        try:
            evidence_id = UUID(raw_id)
        except ValueError as exc:
            raise CoverageSupportDepthRuntimeError(
                "coverage_support_evidence_id_invalid"
            ) from exc
        if raw_id in seen_ids:
            raise CoverageSupportDepthRuntimeError(
                "coverage_support_evidence_id_duplicate"
            )
        seen_ids.add(raw_id)

        evidence = await session.get(Evidence, evidence_id)
        if evidence is None:
            raise CoverageSupportDepthRuntimeError("coverage_support_evidence_missing")
        claim = await session.get(Claim, evidence.claim_id)
        if claim is None or claim.project_id != case.project_id:
            raise CoverageSupportDepthRuntimeError("coverage_support_claim_invalid")
        if evidence.relation not in {
            "supports",
            "qualifies",
            "contradicts",
            "context_only",
        }:
            raise CoverageSupportDepthRuntimeError(
                "coverage_support_evidence_relation_invalid"
            )
        evidence_items.append(
            {
                "evidence_id": str(evidence.id),
                "claim_id": str(claim.id),
                "claim": claim.statement,
                "claim_type": claim.claim_type,
                "importance": claim.importance,
                "relation": evidence.relation,
                "locator": evidence.locator,
                "excerpt": evidence.excerpt,
                "authority_level": evidence.authority_level,
                "quality_metadata": copy.deepcopy(evidence.quality_metadata_json),
                "provenance": {
                    "source_document_id": (
                        str(evidence.source_document_id)
                        if evidence.source_document_id is not None
                        else None
                    ),
                    "chunk_id": (
                        str(evidence.chunk_id)
                        if evidence.chunk_id is not None
                        else None
                    ),
                    "media_observation_id": (
                        str(evidence.media_observation_id)
                        if evidence.media_observation_id is not None
                        else None
                    ),
                    "verified_at": (
                        evidence.verified_at.isoformat()
                        if evidence.verified_at is not None
                        else None
                    ),
                },
            }
        )

    model_input = build_coverage_support_depth_model_input(
        coverage_requirements=list(opportunity.coverage_requirements_json),
        evidence_items=evidence_items,
        originality_items=list(originality_pack.item_refs_json),
        evidence_set_ref={
            "id": str(evidence_set.id),
            "version": evidence_set.version,
            "content_hash": evidence_set.content_hash,
        },
        originality_pack_ref={
            "id": str(originality_pack.id),
            "snapshot_hash": originality_pack.snapshot_hash,
        },
    )
    return CoverageSupportDepthInput(
        content_case=case,
        opportunity=opportunity,
        evidence_set=evidence_set,
        originality_pack=originality_pack,
        model_input=model_input,
        input_snapshot_hash=_canonical_hash(model_input),
    )


def _artifact_payload(
    source_input: CoverageSupportDepthInput,
    assessment: CoverageSupportDepthAssessment,
) -> dict[str, object]:
    unresolved = [
        item.requirement_id
        for item in assessment.items
        if item.status == "unresolved"
    ]
    return {
        "schema_version": COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION,
        "artifact_type": COVERAGE_SUPPORT_DEPTH_ARTIFACT_TYPE,
        "generator_version": COVERAGE_SUPPORT_DEPTH_GENERATOR_VERSION,
        "input_snapshot_hash": source_input.input_snapshot_hash,
        "opportunity": {
            "id": str(source_input.opportunity.id),
            "version": source_input.opportunity.version,
        },
        "evidence_set": {
            "id": str(source_input.evidence_set.id),
            "version": source_input.evidence_set.version,
            "content_hash": source_input.evidence_set.content_hash,
        },
        "originality_pack": {
            "id": str(source_input.originality_pack.id),
            "snapshot_hash": source_input.originality_pack.snapshot_hash,
        },
        "assessment": assessment.to_dict(),
        "ready_for_angle": not unresolved,
        "unresolved_requirement_ids": unresolved,
    }


def _validate_persisted_payload(
    payload: object,
    *,
    source_input: CoverageSupportDepthInput,
) -> tuple[CoverageSupportDepthAssessment, tuple[str, ...]]:
    data = _require_dict(payload, "coverage_support_artifact_payload_invalid")
    if (
        data.get("schema_version") != COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION
        or data.get("artifact_type") != COVERAGE_SUPPORT_DEPTH_ARTIFACT_TYPE
        or data.get("generator_version") != COVERAGE_SUPPORT_DEPTH_GENERATOR_VERSION
        or data.get("input_snapshot_hash") != source_input.input_snapshot_hash
    ):
        raise CoverageSupportDepthRuntimeError("coverage_support_artifact_stale")
    assessment_raw = data.get("assessment")
    model_input = source_input.model_input
    evidence = model_input.get("evidence")
    originality_pack = model_input.get("originality_pack")
    requirements = model_input.get("coverage_requirements")
    if (
        not isinstance(evidence, list)
        or not isinstance(requirements, list)
        or not isinstance(originality_pack, dict)
        or not isinstance(originality_pack.get("items"), list)
    ):
        raise CoverageSupportDepthRuntimeError("coverage_support_model_input_invalid")
    try:
        assessment = validate_coverage_support_depth(
            assessment_raw,
            coverage_requirements=requirements,
            evidence_items=evidence,
            originality_items=cast(list[object], originality_pack["items"]),
        )
    except CoverageSupportDepthError as exc:
        raise CoverageSupportDepthRuntimeError(
            "coverage_support_artifact_assessment_invalid",
            exc.code,
        ) from exc
    unresolved = tuple(
        item.requirement_id
        for item in assessment.items
        if item.status == "unresolved"
    )
    if data.get("ready_for_angle") != (not unresolved):
        raise CoverageSupportDepthRuntimeError("coverage_support_artifact_ready_mismatch")
    raw_unresolved = data.get("unresolved_requirement_ids")
    if raw_unresolved != list(unresolved):
        raise CoverageSupportDepthRuntimeError(
            "coverage_support_artifact_unresolved_mismatch"
        )
    return assessment, unresolved


async def evaluate_coverage_support_depth(
    session: AsyncSession,
    *,
    source_input: CoverageSupportDepthInput,
    run_id: UUID,
    step_run_id: UUID,
    model: CoverageSupportDepthModelPort,
    max_attempts: int = 2,
) -> CoverageSupportDepthResult:
    if max_attempts < 1 or max_attempts > 2:
        raise CoverageSupportDepthRuntimeError("coverage_support_attempts_invalid")
    run = await session.get(ContentRun, run_id)
    step = await session.get(StepRun, step_run_id)
    if (
        run is None
        or step is None
        or step.run_id != run.id
        or run.content_case_id != source_input.content_case.id
    ):
        raise CoverageSupportDepthRuntimeError("coverage_support_execution_binding_invalid")

    existing = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == run.id,
                    Artifact.step_run_id == step.id,
                    Artifact.artifact_type == COVERAGE_SUPPORT_DEPTH_ARTIFACT_TYPE,
                )
            )
        ).all()
    )
    if len(existing) > 1:
        raise CoverageSupportDepthRuntimeError("coverage_support_artifact_conflict")
    if existing:
        artifact = existing[0]
        if (
            not isinstance(artifact.content_json, dict)
            or artifact.content_hash != _canonical_hash(artifact.content_json)
        ):
            raise CoverageSupportDepthRuntimeError("coverage_support_artifact_hash_invalid")
        assessment, unresolved = _validate_persisted_payload(
            artifact.content_json,
            source_input=source_input,
        )
        return CoverageSupportDepthResult(
            artifact=artifact,
            assessment=assessment,
            ready_for_angle=not unresolved,
            unresolved_requirement_ids=unresolved,
            model_attempts=0,
            reused=True,
        )

    requirements = source_input.model_input.get("coverage_requirements")
    if not isinstance(requirements, list):
        raise CoverageSupportDepthRuntimeError("coverage_support_model_input_invalid")

    raw: object
    attempts = 0
    if not requirements:
        raw = {
            "schema_version": COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION,
            "items": [],
        }
    else:
        last_error: CoverageSupportDepthError | None = None
        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            raw = await model.generate(
                input_bundle=copy.deepcopy(source_input.model_input),
                attempt=attempt,
            )
            evidence = source_input.model_input.get("evidence")
            originality_pack = source_input.model_input.get("originality_pack")
            if (
                not isinstance(evidence, list)
                or not isinstance(originality_pack, dict)
                or not isinstance(originality_pack.get("items"), list)
            ):
                raise CoverageSupportDepthRuntimeError(
                    "coverage_support_model_input_invalid"
                )
            try:
                assessment = validate_coverage_support_depth(
                    raw,
                    coverage_requirements=requirements,
                    evidence_items=evidence,
                    originality_items=cast(list[object], originality_pack["items"]),
                )
                break
            except CoverageSupportDepthError as exc:
                last_error = exc
        else:
            raise CoverageSupportDepthRuntimeError(
                "coverage_support_model_output_invalid",
                last_error.code if last_error is not None else None,
            )
    if not requirements:
        try:
            assessment = validate_coverage_support_depth(
                raw,
                coverage_requirements=[],
                evidence_items=[],
                originality_items=[],
            )
        except CoverageSupportDepthError as exc:
            raise CoverageSupportDepthRuntimeError(
                "coverage_support_legacy_assessment_invalid",
                exc.code,
            ) from exc

    payload = _artifact_payload(source_input, assessment)
    content_hash = _canonical_hash(payload)
    duplicate = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == run.id,
            Artifact.step_run_id == step.id,
            Artifact.artifact_type == COVERAGE_SUPPORT_DEPTH_ARTIFACT_TYPE,
            Artifact.content_hash == content_hash,
        )
    )
    if duplicate is not None:
        validated, unresolved = _validate_persisted_payload(
            duplicate.content_json,
            source_input=source_input,
        )
        return CoverageSupportDepthResult(
            artifact=duplicate,
            assessment=validated,
            ready_for_angle=not unresolved,
            unresolved_requirement_ids=unresolved,
            model_attempts=attempts,
            reused=True,
        )

    latest_version = await session.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.run_id == run.id,
            Artifact.artifact_type == COVERAGE_SUPPORT_DEPTH_ARTIFACT_TYPE,
        )
    )
    artifact = Artifact(
        run_id=run.id,
        step_run_id=step.id,
        artifact_type=COVERAGE_SUPPORT_DEPTH_ARTIFACT_TYPE,
        locale=source_input.opportunity.locale,
        version=(latest_version or 0) + 1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    unresolved = tuple(
        item.requirement_id
        for item in assessment.items
        if item.status == "unresolved"
    )
    return CoverageSupportDepthResult(
        artifact=artifact,
        assessment=assessment,
        ready_for_angle=not unresolved,
        unresolved_requirement_ids=unresolved,
        model_attempts=attempts,
        reused=False,
    )


__all__ = [
    "COVERAGE_SUPPORT_DEPTH_ARTIFACT_TYPE",
    "COVERAGE_SUPPORT_DEPTH_GENERATOR_VERSION",
    "CoverageSupportDepthInput",
    "CoverageSupportDepthModelPort",
    "CoverageSupportDepthResult",
    "CoverageSupportDepthRuntimeError",
    "build_coverage_support_depth_model_input",
    "evaluate_coverage_support_depth",
    "load_coverage_support_depth_input",
]
