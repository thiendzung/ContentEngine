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
from app.modules.research.evidence.contracts import (
    AUTOMATIC_CLAIM_MAX_CHARS,
    DEFAULT_EVIDENCE_MAX_CLAIMS,
    is_usable_originality_item,
)

COVERAGE_SUPPORT_DEPTH_ARTIFACT_TYPE = "coverage_support_depth"
COVERAGE_SUPPORT_DEPTH_FAILURE_ARTIFACT_TYPE = "coverage_support_failure_diagnostic"
COVERAGE_SUPPORT_FAILURE_DIAGNOSTIC_SCHEMA_VERSION = 2
COVERAGE_SUPPORT_DIAGNOSTIC_MAX_RATIONALE_CHARS = 2_000
COVERAGE_SUPPORT_DIAGNOSTIC_MAX_GAPS = 20
COVERAGE_SUPPORT_DIAGNOSTIC_MAX_GAP_CHARS = 1_000
COVERAGE_SUPPORT_MODEL_INPUT_MAX_BYTES = 64_000
COVERAGE_SUPPORT_RESEARCH_MAX_EVIDENCE_ITEMS = DEFAULT_EVIDENCE_MAX_CLAIMS
COVERAGE_SUPPORT_AUTOMATIC_EVIDENCE_TEXT_MAX_CHARS = AUTOMATIC_CLAIM_MAX_CHARS
COVERAGE_SUPPORT_DEPTH_GENERATOR_VERSION = "cq03.coverage_support_depth.v1"


class CoverageSupportDepthRuntimeError(ValueError):
    def __init__(
        self,
        code: str,
        detail: str | None = None,
        *,
        safe_metadata: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.detail = detail
        self.safe_metadata = safe_metadata
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


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_bounded_model_input(value: dict[str, object]) -> None:
    if len(_canonical_json(value).encode("utf-8")) > COVERAGE_SUPPORT_MODEL_INPUT_MAX_BYTES:
        raise CoverageSupportDepthRuntimeError(
            "coverage_support_model_input_too_large"
        )


def _require_dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CoverageSupportDepthRuntimeError(code)
    return cast(dict[str, object], value)


def _model_input_diagnostic_snapshot(
    source_input: CoverageSupportDepthInput,
) -> dict[str, object]:
    """Persist the exact sanitized evaluator input so its hash remains verifiable."""

    snapshot = copy.deepcopy(source_input.model_input)
    if _canonical_hash(snapshot) != source_input.input_snapshot_hash:
        raise CoverageSupportDepthRuntimeError(
            "coverage_support_diagnostic_input_hash_mismatch"
        )
    return snapshot


def _coverage_research_diagnostic_snapshot(
    source_input: CoverageSupportDepthInput,
    research_snapshot: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(research_snapshot, dict):
        return None
    research = research_snapshot.get("research")
    relation_counts = research_snapshot.get("relation_counts")
    research_gaps = research_snapshot.get("research_gaps")
    gaps = list(research_gaps) if isinstance(research_gaps, list) else []
    originality_pack = source_input.model_input.get("originality_pack")
    items = originality_pack.get("items") if isinstance(originality_pack, dict) else None
    omitted: list[str] = []
    if isinstance(items, list) and items:
        filtered: list[object] = []
        for gap in gaps:
            if isinstance(gap, str) and gap.startswith("Originality gap remains:"):
                omitted.append("stale_opportunity_originality_gap")
                continue
            filtered.append(gap)
        gaps = filtered
    return {
        "research": copy.deepcopy(research) if isinstance(research, dict) else {},
        "relation_counts": (
            copy.deepcopy(relation_counts)
            if isinstance(relation_counts, dict)
            else {}
        ),
        "research_gaps": copy.deepcopy(gaps),
        "omitted_stale_gaps": omitted,
    }


def _coverage_evaluator_identity_snapshot(
    evaluator_identity: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(evaluator_identity, dict):
        return None

    def text_value(key: str, limit: int) -> str | None:
        value = evaluator_identity.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise CoverageSupportDepthRuntimeError(
                "coverage_support_evaluator_identity_invalid"
            )
        return value.strip()[:limit]

    attempt = evaluator_identity.get("accepted_attempt")
    if (
        isinstance(attempt, bool)
        or not isinstance(attempt, int)
        or attempt < 1
        or attempt > 2
    ):
        raise CoverageSupportDepthRuntimeError(
            "coverage_support_evaluator_identity_invalid"
        )
    return {
        "prompt_version": text_value("prompt_version", 200),
        "recipe_version": text_value("recipe_version", 200),
        "provider": text_value("provider", 100),
        "model": text_value("model", 200),
        "runner_version": text_value("runner_version", 200),
        "runner_executable": text_value("runner_executable", 1000),
        "raw_output_hash": text_value("raw_output_hash", 128),
        "accepted_attempt": attempt,
        "context_manifest_id": text_value("context_manifest_id", 100),
    }


def _assessment_diagnostic_snapshot(
    assessment: CoverageSupportDepthAssessment,
) -> dict[str, object]:
    """Bound model-authored prose while retaining exact output hashes and refs."""

    items: list[dict[str, object]] = []
    for item in assessment.items:
        exact_gaps = list(item.gaps)
        items.append(
            {
                "requirement_id": item.requirement_id,
                "status": item.status,
                "evidence_refs": list(item.evidence_refs),
                "caveat_evidence_refs": list(item.caveat_evidence_refs),
                "originality_refs": list(item.originality_refs),
                "rationale": item.rationale[
                    :COVERAGE_SUPPORT_DIAGNOSTIC_MAX_RATIONALE_CHARS
                ],
                "rationale_hash": hashlib.sha256(
                    item.rationale.encode("utf-8")
                ).hexdigest(),
                "gaps": [
                    gap[:COVERAGE_SUPPORT_DIAGNOSTIC_MAX_GAP_CHARS]
                    for gap in exact_gaps[:COVERAGE_SUPPORT_DIAGNOSTIC_MAX_GAPS]
                ],
                "gaps_hash": _canonical_hash(exact_gaps),
                "gaps_total": len(exact_gaps),
            }
        )
    exact = assessment.to_dict()
    return {
        "schema_version": assessment.schema_version,
        "content_hash": _canonical_hash(exact),
        "items": items,
    }


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
    model_input = {
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
            "coverage_requirement_is_editorial_spec_not_evidence": True,
            "structural_navigation_directives_do_not_require_external_evidence": True,
            "factual_assertions_still_require_factual_support": True,
            (
                "mixed_requirement_may_combine_factual_evidence_with_"
                "first_party_editorial_support"
            ): True,
            "editorial_spec_rule": (
                "Coverage requirement text is an authoritative editorial specification, "
                "not evidence. Structural or internal-navigation directives do not need "
                "external evidence merely to be obeyed."
            ),
            "mixed_support_rule": (
                "Factual clauses still require factual support. First-party editorial "
                "stance may use approved OriginalityPack support; do not mark a requirement "
                "unresolved solely because internal navigation labels appear only in the "
                "frozen requirement."
            ),
        },
    }
    _require_bounded_model_input(model_input)
    return model_input


def _reserved_research_evidence_items(
    *,
    max_evidence_items: int,
) -> list[dict[str, object]]:
    """Upper-bound the automatic research evidence shape before external calls."""

    if (
        max_evidence_items < 0
        or max_evidence_items > COVERAGE_SUPPORT_RESEARCH_MAX_EVIDENCE_ITEMS
    ):
        raise CoverageSupportDepthRuntimeError(
            "coverage_support_evidence_reservation_invalid"
        )

    widest_text = "😀" * COVERAGE_SUPPORT_AUTOMATIC_EVIDENCE_TEXT_MAX_CHARS
    uuid_text = "f" * 36
    return [
        {
            "evidence_id": uuid_text,
            "claim_id": uuid_text,
            "claim": widest_text,
            "claim_type": "x" * 32,
            "importance": "x" * 16,
            "relation": "x" * 16,
            "locator": "x" * 128,
            "excerpt": widest_text,
            "authority_level": "x" * 32,
            "quality_metadata": {
                "source_type": "x" * 32,
                "commercial_bias": "x" * 32,
                "authority_hint": "x" * 32,
                "search_rank_used_as_authority": False,
            },
            "provenance": {
                "source_document_id": uuid_text,
                "chunk_id": uuid_text,
                "media_observation_id": uuid_text,
                "verified_at": "x" * 64,
            },
        }
        for _ in range(max_evidence_items)
    ]


def preflight_coverage_support_depth_capacity(
    *,
    coverage_requirements: list[str],
    originality_items: list[object],
    originality_pack_ref: dict[str, object],
    max_evidence_items: int = COVERAGE_SUPPORT_RESEARCH_MAX_EVIDENCE_ITEMS,
) -> None:
    """Reserve worst-case automatic Evidence payload before external research."""

    build_coverage_support_depth_model_input(
        coverage_requirements=coverage_requirements,
        evidence_items=_reserved_research_evidence_items(
            max_evidence_items=max_evidence_items
        ),
        originality_items=originality_items,
        evidence_set_ref={
            "id": "pre-research",
            "version": 1,
            "content_hash": "0" * 64,
        },
        originality_pack_ref=originality_pack_ref,
    )


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


async def _append_step_output_ref(
    session: AsyncSession,
    *,
    step: StepRun,
    artifact: Artifact,
) -> None:
    artifact_ref = str(artifact.id)
    if artifact_ref in step.output_artifact_refs_json:
        return
    step.output_artifact_refs_json = [
        *step.output_artifact_refs_json,
        artifact_ref,
    ]
    await session.flush()


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
        await _append_step_output_ref(session, step=step, artifact=artifact)
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
        await _append_step_output_ref(session, step=step, artifact=duplicate)
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
    await _append_step_output_ref(session, step=step, artifact=artifact)
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


async def load_validated_coverage_support_depth_artifact(
    session: AsyncSession,
    *,
    artifact_id: UUID,
    run_id: UUID,
    step_run_id: UUID,
    content_case_id: UUID,
    opportunity_id: UUID,
    evidence_set_id: UUID,
    originality_pack_id: UUID,
) -> CoverageSupportDepthResult:
    artifact = await session.get(Artifact, artifact_id)
    if (
        artifact is None
        or artifact.run_id != run_id
        or artifact.step_run_id != step_run_id
        or artifact.artifact_type != COVERAGE_SUPPORT_DEPTH_ARTIFACT_TYPE
        or not isinstance(artifact.content_json, dict)
        or artifact.content_hash != _canonical_hash(artifact.content_json)
    ):
        raise CoverageSupportDepthRuntimeError(
            "coverage_support_artifact_binding_invalid"
        )
    source_input = await load_coverage_support_depth_input(
        session,
        content_case_id=content_case_id,
        opportunity_id=opportunity_id,
        evidence_set_id=evidence_set_id,
        originality_pack_id=originality_pack_id,
    )
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


def coverage_support_failure_diagnostic_payload(
    source_input: CoverageSupportDepthInput,
    result: CoverageSupportDepthResult,
    *,
    research_snapshot: dict[str, object] | None = None,
    evaluator_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    assessment = _assessment_diagnostic_snapshot(result.assessment)
    assessment_items = assessment.get("items")
    if not isinstance(assessment_items, list):
        raise CoverageSupportDepthRuntimeError(
            "coverage_support_failure_diagnostic_assessment_invalid"
        )
    unresolved = [
        copy.deepcopy(item)
        for item in assessment_items
        if isinstance(item, dict) and item.get("status") == "unresolved"
    ]
    if not unresolved or result.ready_for_angle:
        raise CoverageSupportDepthRuntimeError(
            "coverage_support_failure_diagnostic_requires_unresolved"
        )

    safe_research = _coverage_research_diagnostic_snapshot(
        source_input,
        research_snapshot,
    )
    safe_evaluator_identity = _coverage_evaluator_identity_snapshot(
        evaluator_identity
    )

    model_input_snapshot = _model_input_diagnostic_snapshot(source_input)
    return {
        "schema_version": COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION,
        "diagnostic_schema_version": COVERAGE_SUPPORT_FAILURE_DIAGNOSTIC_SCHEMA_VERSION,
        "artifact_type": COVERAGE_SUPPORT_DEPTH_FAILURE_ARTIFACT_TYPE,
        "input_snapshot_hash": source_input.input_snapshot_hash,
        "model_input_snapshot": model_input_snapshot,
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
        "assessment": assessment,
        "research_snapshot": safe_research,
        "evaluator_identity": safe_evaluator_identity,
        "ready_for_angle": False,
        "unresolved": unresolved,
    }


async def persist_coverage_support_failure_diagnostic(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
    payload: dict[str, object],
) -> Artifact:
    run = await session.get(ContentRun, run_id)
    step = await session.get(StepRun, step_run_id)
    if (
        run is None
        or step is None
        or step.run_id != run.id
        or payload.get("artifact_type") != COVERAGE_SUPPORT_DEPTH_FAILURE_ARTIFACT_TYPE
        or payload.get("ready_for_angle") is not False
    ):
        raise CoverageSupportDepthRuntimeError(
            "coverage_support_failure_diagnostic_invalid"
        )
    unresolved = payload.get("unresolved")
    if not isinstance(unresolved, list) or not unresolved:
        raise CoverageSupportDepthRuntimeError(
            "coverage_support_failure_diagnostic_invalid"
        )
    content_hash = _canonical_hash(payload)
    existing = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == run.id,
            Artifact.step_run_id == step.id,
            Artifact.artifact_type == COVERAGE_SUPPORT_DEPTH_FAILURE_ARTIFACT_TYPE,
            Artifact.content_hash == content_hash,
        )
    )
    if existing is not None:
        await _append_step_output_ref(session, step=step, artifact=existing)
        return existing
    latest_version = await session.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.run_id == run.id,
            Artifact.artifact_type == COVERAGE_SUPPORT_DEPTH_FAILURE_ARTIFACT_TYPE,
        )
    )
    artifact = Artifact(
        run_id=run.id,
        step_run_id=step.id,
        artifact_type=COVERAGE_SUPPORT_DEPTH_FAILURE_ARTIFACT_TYPE,
        locale=None,
        version=(latest_version or 0) + 1,
        content_json=copy.deepcopy(payload),
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    await _append_step_output_ref(session, step=step, artifact=artifact)
    return artifact


__all__ = [
    "COVERAGE_SUPPORT_DEPTH_ARTIFACT_TYPE",
    "COVERAGE_SUPPORT_DEPTH_FAILURE_ARTIFACT_TYPE",
    "COVERAGE_SUPPORT_DEPTH_GENERATOR_VERSION",
    "CoverageSupportDepthInput",
    "CoverageSupportDepthModelPort",
    "CoverageSupportDepthResult",
    "CoverageSupportDepthRuntimeError",
    "build_coverage_support_depth_model_input",
    "coverage_support_failure_diagnostic_payload",
    "evaluate_coverage_support_depth",
    "load_coverage_support_depth_input",
    "load_validated_coverage_support_depth_artifact",
    "persist_coverage_support_failure_diagnostic",
]
