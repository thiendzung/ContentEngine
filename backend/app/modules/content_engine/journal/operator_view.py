"""Authoritative read projection for the Journal operator console.

The projection is intentionally read-only. It exposes persisted business state and exact
immutable bindings needed by the UI, while leaving all workflow decisions to the operator
control plane.
"""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal import operator_runtime
from app.modules.content_engine.journal.angle import (
    _artifact_candidates,
    angle_candidate_hash,
    load_journal_input_bundle,
)
from app.modules.content_engine.journal.models import JournalIntakeSpec, JournalRequiredLocale
from app.modules.content_engine.journal.operator_control import OperatorControlError, OperatorState
from app.modules.content_engine.journal.operator_quality import get_quality_progress
from app.modules.content_engine.journal.operator_writers import get_writer_lane_progress
from app.modules.content_engine.models import ContentCase, ContentOpportunity
from app.modules.harness.models import Artifact, ContentRun
from app.modules.harness.persistence import get_latest_checkpoint

LocaleRole = Literal["source", "translation"]


def _int_field(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


class OperatorRequiredLocaleView(BaseModel):
    locale: str
    role: LocaleRole


class OperatorIntakeView(BaseModel):
    source_locale: str
    research_country: str
    required_locales: list[OperatorRequiredLocaleView] = Field(default_factory=list)


class OperatorAngleArtifactView(BaseModel):
    id: UUID
    version: int
    content_hash: str


class OperatorOutlineArtifactView(BaseModel):
    id: UUID
    version: int
    content_hash: str


class OperatorCoverageRequirementView(BaseModel):
    id: str
    requirement: str


class OperatorAngleCoverageView(BaseModel):
    requirement_id: str
    requirement: str
    status: Literal["covered", "reduced"]
    rationale: str


class OperatorAngleCandidateView(BaseModel):
    angle_id: str
    candidate_hash: str
    working_title: str
    reader_problem: str
    central_question: str
    core_promise: str
    point_of_view: str
    why_now: str
    evidence_refs: list[str]
    originality_refs: list[str]
    excluded_claims: list[str]
    risks: list[str]
    confidence: float
    locale: str
    coverage: list[OperatorAngleCoverageView] = Field(default_factory=list)


class OperatorAngleGateView(BaseModel):
    type: Literal["angle"] = "angle"
    artifact: OperatorAngleArtifactView
    candidates: list[OperatorAngleCandidateView]


class OperatorOutlineGateView(BaseModel):
    type: Literal["outline"] = "outline"
    artifact: OperatorOutlineArtifactView
    outline: dict[str, object]


class OperatorWriterLaneView(BaseModel):
    required_locale: str
    status: Literal["pending", "queued", "running", "completed", "failed"]
    run_id: UUID | None = None
    step_run_id: UUID | None = None
    job_id: UUID | None = None
    attempt: int | None = None
    draft_artifact_id: UUID | None = None
    draft_version: int | None = None
    draft_hash: str | None = None


class OperatorQualityRefView(BaseModel):
    id: UUID | None = None
    version: int | None = None
    content_hash: str | None = None


class OperatorQualityLaneView(BaseModel):
    locale: str
    locale_variant_id: UUID
    writer_run_id: UUID | None = None
    current_quality_stage: str
    status: str
    source_writer_draft: OperatorQualityRefView | None = None
    revised_draft: OperatorQualityRefView | None = None
    review_step_run_id: UUID | None = None
    review_job_id: UUID | None = None
    review_attempt: int | None = None
    review_status: str | None = None
    assertion_audit_run_id: UUID | None = None
    assertion_audit_step_run_id: UUID | None = None
    assertion_audit_job_id: UUID | None = None
    assertion_audit_artifact: OperatorQualityRefView | None = None
    assertion_audit_quality_evaluation_id: UUID | None = None
    assertion_audit_result: str | None = None
    critical_unsupported_count: int = 0
    critical_contradicted_count: int = 0
    unsupported_count: int = 0
    contradicted_count: int = 0
    source_copy_run_id: UUID | None = None
    source_copy_step_run_id: UUID | None = None
    source_copy_job_id: UUID | None = None
    source_copy_artifact: OperatorQualityRefView | None = None
    source_copy_quality_evaluation_id: UUID | None = None
    source_copy_result: str | None = None
    finding_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    max_overlap_tokens: int = 0
    source_copy_findings: list[object] = Field(default_factory=list)
    reader_value_artifact: OperatorQualityRefView | None = None
    reader_value_quality_evaluation_id: UUID | None = None
    reader_value_result: str | None = None
    reader_value_findings: list[object] = Field(default_factory=list)
    search_ai_artifact: OperatorQualityRefView | None = None
    search_ai_quality_evaluation_id: UUID | None = None
    search_ai_result: str | None = None
    search_ai_findings: list[object] = Field(default_factory=list)
    content_item_id: UUID | None = None
    final_content: OperatorQualityRefView | None = None
    final_review_step_run_id: UUID | None = None
    pending_approval_ready: bool = False


class OperatorCaseView(BaseModel):
    content_case_id: UUID
    question: str
    reader: str
    situation: str
    need: str
    intent: str
    promise: str
    content_role: str | None
    coverage_requirements: list[OperatorCoverageRequirementView] = Field(default_factory=list)
    state: OperatorState
    intake: OperatorIntakeView
    pending_gate: OperatorAngleGateView | OperatorOutlineGateView | None = None
    writer_lanes: list[OperatorWriterLaneView] = Field(default_factory=list)
    quality_lanes: list[OperatorQualityLaneView] = Field(default_factory=list)


def _bundle_ref(artifact: Artifact) -> tuple[UUID, int, str]:
    payload = artifact.content_json
    if not isinstance(payload, dict):
        raise OperatorControlError("operator_angle_projection_invalid")
    raw_ref = payload.get("journal_input_bundle")
    if not isinstance(raw_ref, dict):
        raise OperatorControlError("operator_angle_projection_invalid")
    raw_id = raw_ref.get("id")
    version = raw_ref.get("version")
    content_hash = raw_ref.get("content_hash")
    if not isinstance(raw_id, str):
        raise OperatorControlError("operator_angle_projection_invalid")
    try:
        bundle_id = UUID(raw_id)
    except ValueError as exc:
        raise OperatorControlError("operator_angle_projection_invalid") from exc
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise OperatorControlError("operator_angle_projection_invalid")
    if not isinstance(content_hash, str) or len(content_hash) != 64:
        raise OperatorControlError("operator_angle_projection_invalid")
    return bundle_id, version, content_hash


def _locale_role(value: str) -> LocaleRole:
    if value not in {"source", "translation"}:
        raise OperatorControlError("operator_required_locales_invalid")
    return cast(LocaleRole, value)


async def _pending_artifact(
    session: AsyncSession,
    *,
    state: OperatorState,
    step_key: str,
    artifact_type: str,
    error_prefix: str,
) -> Artifact:
    if state.current_run_id is None or state.current_step_run_id is None:
        raise OperatorControlError(f"{error_prefix}_missing")
    checkpoint = await get_latest_checkpoint(session, run_id=state.current_run_id)
    if checkpoint is None or not isinstance(checkpoint.content_json, dict):
        raise OperatorControlError(f"{error_prefix}_missing")
    pending = checkpoint.content_json.get("pending_approval")
    if not isinstance(pending, dict) or pending.get("step_key") != step_key:
        raise OperatorControlError(f"{error_prefix}_stale")
    raw_artifact_id = pending.get("artifact_id")
    if not isinstance(raw_artifact_id, str):
        raise OperatorControlError(f"{error_prefix}_invalid")
    try:
        artifact_id = UUID(raw_artifact_id)
    except ValueError as exc:
        raise OperatorControlError(f"{error_prefix}_invalid") from exc
    artifact = await session.get(Artifact, artifact_id)
    if (
        artifact is None
        or artifact.run_id != state.current_run_id
        or artifact.step_run_id != state.current_step_run_id
        or artifact.artifact_type != artifact_type
    ):
        raise OperatorControlError(f"{error_prefix}_stale")
    return artifact


def _coverage_requirements_from_snapshot(
    opportunity: dict[str, object],
) -> list[OperatorCoverageRequirementView]:
    raw = opportunity.get("coverage_requirements", [])
    if not isinstance(raw, list):
        raise OperatorControlError("operator_coverage_requirements_invalid")
    result: list[OperatorCoverageRequirementView] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise OperatorControlError("operator_coverage_requirements_invalid")
        requirement_id = item.get("id")
        requirement = item.get("requirement")
        if (
            not isinstance(requirement_id, str)
            or not requirement_id.strip()
            or not isinstance(requirement, str)
            or not requirement.strip()
            or requirement_id in seen
        ):
            raise OperatorControlError("operator_coverage_requirements_invalid")
        seen.add(requirement_id)
        result.append(
            OperatorCoverageRequirementView(
                id=requirement_id,
                requirement=requirement,
            )
        )
    return result


async def _angle_gate(
    session: AsyncSession,
    *,
    state: OperatorState,
) -> OperatorAngleGateView:
    artifact = await _pending_artifact(
        session,
        state=state,
        step_key="angle",
        artifact_type="angle_candidates",
        error_prefix="operator_angle_projection",
    )
    bundle_id, bundle_version, bundle_hash = _bundle_ref(artifact)
    try:
        bundle = await load_journal_input_bundle(
            session,
            journal_input_bundle_id=bundle_id,
            expected_content_hash=bundle_hash,
        )
        if bundle.artifact.version != bundle_version:
            raise OperatorControlError("operator_angle_projection_stale")
        candidates = _artifact_candidates(artifact, bundle=bundle)
    except OperatorControlError:
        raise
    except ValueError as exc:
        raise OperatorControlError("operator_angle_projection_stale") from exc
    if not candidates:
        raise OperatorControlError("operator_angle_projection_missing")
    coverage_requirements = _coverage_requirements_from_snapshot(bundle.opportunity)
    coverage_by_id = {item.id: item.requirement for item in coverage_requirements}
    return OperatorAngleGateView(
        artifact=OperatorAngleArtifactView(
            id=artifact.id,
            version=artifact.version,
            content_hash=artifact.content_hash,
        ),
        candidates=[
            OperatorAngleCandidateView(
                angle_id=candidate.angle_id,
                candidate_hash=angle_candidate_hash(candidate),
                working_title=candidate.working_title,
                reader_problem=candidate.reader_problem,
                central_question=candidate.central_question,
                core_promise=candidate.core_promise,
                point_of_view=candidate.point_of_view,
                why_now=candidate.why_now,
                evidence_refs=list(candidate.evidence_refs),
                originality_refs=list(candidate.originality_refs),
                excluded_claims=list(candidate.excluded_claims),
                risks=list(candidate.risks),
                confidence=candidate.confidence,
                locale=candidate.locale,
                coverage=[
                    OperatorAngleCoverageView(
                        requirement_id=item.requirement_id,
                        requirement=coverage_by_id[item.requirement_id],
                        status=cast(Literal["covered", "reduced"], item.status),
                        rationale=item.rationale,
                    )
                    for item in candidate.coverage
                ],
            )
            for candidate in candidates
        ],
    )


async def _outline_gate(
    session: AsyncSession,
    *,
    state: OperatorState,
) -> OperatorOutlineGateView:
    artifact = await _pending_artifact(
        session,
        state=state,
        step_key="outline",
        artifact_type="journal_outline",
        error_prefix="operator_outline_projection",
    )
    payload = artifact.content_json
    if not isinstance(payload, dict) or payload.get("artifact_type") != "journal_outline":
        raise OperatorControlError("operator_outline_projection_invalid")
    outline = payload.get("outline")
    if not isinstance(outline, dict):
        raise OperatorControlError("operator_outline_projection_invalid")
    return OperatorOutlineGateView(
        artifact=OperatorOutlineArtifactView(
            id=artifact.id,
            version=artifact.version,
            content_hash=artifact.content_hash,
        ),
        outline=outline,
    )


async def get_operator_case_view(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> OperatorCaseView:
    """Return the browser projection for one Journal case from persisted canonical state."""

    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None or content_case.content_type != "journal":
        raise OperatorControlError("operator_case_not_found")
    opportunity = await session.get(ContentOpportunity, content_case.content_opportunity_id)
    spec = await session.scalar(
        select(JournalIntakeSpec).where(JournalIntakeSpec.content_case_id == content_case.id)
    )
    if opportunity is None or spec is None:
        raise OperatorControlError("operator_manual_intake_receipt_missing")
    requirements = list(
        (
            await session.scalars(
                select(JournalRequiredLocale)
                .where(JournalRequiredLocale.content_case_id == content_case.id)
                .order_by(JournalRequiredLocale.role, JournalRequiredLocale.locale)
            )
        ).all()
    )
    if not requirements:
        raise OperatorControlError("operator_required_locales_missing")
    state = await operator_runtime.get_operator_state(session, content_case_id=content_case.id)
    pending_gate: OperatorAngleGateView | OperatorOutlineGateView | None = None
    if state.status == "AWAITING_APPROVAL":
        if state.human_gate == "angle":
            pending_gate = await _angle_gate(session, state=state)
        elif state.human_gate == "outline":
            pending_gate = await _outline_gate(session, state=state)
    source_runs = list(
        (
            await session.scalars(
                select(ContentRun)
                .where(
                    ContentRun.content_case_id == content_case.id,
                    ContentRun.current_step == "outline",
                    ContentRun.run_mode != "eval",
                )
                .order_by(ContentRun.created_at, ContentRun.id)
            )
        ).all()
    )
    if len(source_runs) > 1:
        raise OperatorControlError("operator_writer_source_run_conflict")
    source_run_id = source_runs[0].id if source_runs else None
    writer_progress = await get_writer_lane_progress(
        session,
        content_case_id=content_case.id,
        source_run_id=source_run_id,
    )
    quality_progress = await get_quality_progress(
        session,
        content_case_id=content_case.id,
        source_run_id=source_run_id,
    )
    if writer_progress is None and quality_progress is not None:
        writer_progress = quality_progress.writer_progress
    writer_lanes = []
    if writer_progress is not None:
        writer_lanes = [
            OperatorWriterLaneView(
                required_locale=lane.required_locale,
                status=lane.status,  # type: ignore[arg-type]
                run_id=lane.run.id if lane.run else None,
                step_run_id=lane.step.id if lane.step else None,
                job_id=lane.latest_job.id if lane.latest_job else None,
                attempt=lane.latest_job.attempt if lane.latest_job else None,
                draft_artifact_id=lane.draft.id if lane.draft else None,
                draft_version=lane.draft.version if lane.draft else None,
                draft_hash=lane.draft.content_hash if lane.draft else None,
            )
            for lane in writer_progress.lanes
        ]
    quality_lanes: list[OperatorQualityLaneView] = []
    if quality_progress is not None:
        for lane in quality_progress.lanes:
            audit_findings = (
                lane.audit.evaluation.findings_json if lane.audit.evaluation is not None else {}
            )
            source_findings = (
                lane.source_copy.evaluation.findings_json
                if lane.source_copy.evaluation is not None
                else {}
            )
            reader_findings = (
                lane.reader_value.evaluation.findings_json
                if lane.reader_value.evaluation is not None
                else {}
            )
            search_findings = (
                lane.search_ai.evaluation.findings_json
                if lane.search_ai.evaluation is not None
                else {}
            )
            source_ref = (
                OperatorQualityRefView(
                    id=lane.source_draft.id,
                    version=lane.source_draft.version,
                    content_hash=lane.source_draft.content_hash,
                )
                if lane.source_draft is not None
                else None
            )
            revised_ref = (
                OperatorQualityRefView(
                    id=lane.revised_draft.id,
                    version=lane.revised_draft.version,
                    content_hash=lane.revised_draft.content_hash,
                )
                if lane.revised_draft is not None
                else None
            )
            quality_lanes.append(
                OperatorQualityLaneView(
                    locale=lane.locale,
                    locale_variant_id=lane.variant.id,
                    writer_run_id=lane.writer.run.id if lane.writer.run else None,
                    current_quality_stage=lane.status,
                    status=lane.status,
                    source_writer_draft=source_ref,
                    revised_draft=revised_ref,
                    review_step_run_id=lane.review.step.id if lane.review.step else None,
                    review_job_id=lane.review.job.id if lane.review.job else None,
                    review_attempt=lane.review.job.attempt if lane.review.job else None,
                    review_status=lane.review.job.status if lane.review.job else None,
                    assertion_audit_run_id=lane.audit.run.id if lane.audit.run else None,
                    assertion_audit_step_run_id=lane.audit.step.id if lane.audit.step else None,
                    assertion_audit_job_id=lane.audit.job.id if lane.audit.job else None,
                    assertion_audit_artifact=(
                        OperatorQualityRefView(
                            id=lane.audit.artifact.id,
                            version=lane.audit.artifact.version,
                            content_hash=lane.audit.artifact.content_hash,
                        )
                        if lane.audit.artifact is not None
                        else None
                    ),
                    assertion_audit_quality_evaluation_id=(
                        lane.audit.evaluation.id if lane.audit.evaluation else None
                    ),
                    assertion_audit_result=(
                        lane.audit.evaluation.result if lane.audit.evaluation else None
                    ),
                    critical_unsupported_count=_int_field(
                        audit_findings.get("critical_unsupported_count", 0)
                    ),
                    critical_contradicted_count=_int_field(
                        audit_findings.get("critical_contradicted_count", 0)
                    ),
                    unsupported_count=_int_field(audit_findings.get("unsupported_count", 0)),
                    contradicted_count=_int_field(audit_findings.get("contradicted_count", 0)),
                    source_copy_run_id=lane.source_copy.run.id if lane.source_copy.run else None,
                    source_copy_step_run_id=lane.source_copy.step.id
                    if lane.source_copy.step
                    else None,
                    source_copy_job_id=lane.source_copy.job.id if lane.source_copy.job else None,
                    source_copy_artifact=(
                        OperatorQualityRefView(
                            id=lane.source_copy.artifact.id,
                            version=lane.source_copy.artifact.version,
                            content_hash=lane.source_copy.artifact.content_hash,
                        )
                        if lane.source_copy.artifact is not None
                        else None
                    ),
                    source_copy_quality_evaluation_id=(
                        lane.source_copy.evaluation.id if lane.source_copy.evaluation else None
                    ),
                    source_copy_result=(
                        lane.source_copy.evaluation.result if lane.source_copy.evaluation else None
                    ),
                    finding_count=_int_field(source_findings.get("finding_count", 0)),
                    warn_count=_int_field(source_findings.get("warn_count", 0)),
                    fail_count=_int_field(source_findings.get("fail_count", 0)),
                    max_overlap_tokens=_int_field(source_findings.get("max_overlap_tokens", 0)),
                    source_copy_findings=(
                        cast(list[object], source_findings.get("findings", []))
                        if isinstance(source_findings.get("findings", []), list)
                        else []
                    ),
                    reader_value_artifact=(
                        OperatorQualityRefView(
                            id=lane.reader_value.artifact.id,
                            version=lane.reader_value.artifact.version,
                            content_hash=lane.reader_value.artifact.content_hash,
                        )
                        if lane.reader_value.artifact is not None
                        else None
                    ),
                    reader_value_quality_evaluation_id=(
                        lane.reader_value.evaluation.id if lane.reader_value.evaluation else None
                    ),
                    reader_value_result=(
                        lane.reader_value.evaluation.result
                        if lane.reader_value.evaluation
                        else None
                    ),
                    reader_value_findings=(
                        cast(list[object], reader_findings.get("criteria", []))
                        if isinstance(reader_findings.get("criteria", []), list)
                        else []
                    ),
                    search_ai_artifact=(
                        OperatorQualityRefView(
                            id=lane.search_ai.artifact.id,
                            version=lane.search_ai.artifact.version,
                            content_hash=lane.search_ai.artifact.content_hash,
                        )
                        if lane.search_ai.artifact is not None
                        else None
                    ),
                    search_ai_quality_evaluation_id=(
                        lane.search_ai.evaluation.id if lane.search_ai.evaluation else None
                    ),
                    search_ai_result=(
                        lane.search_ai.evaluation.result if lane.search_ai.evaluation else None
                    ),
                    search_ai_findings=(
                        cast(list[object], search_findings.get("criteria", []))
                        if isinstance(search_findings.get("criteria", []), list)
                        else []
                    ),
                    content_item_id=lane.final_item.id if lane.final_item else None,
                    final_content=(
                        OperatorQualityRefView(
                            id=lane.final_content.id,
                            version=lane.final_content.version,
                            content_hash=lane.final_content.content_hash,
                        )
                        if lane.final_content is not None
                        else None
                    ),
                    final_review_step_run_id=lane.final_review.id if lane.final_review else None,
                    pending_approval_ready=lane.status == "final_gate_ready",
                )
            )
    return OperatorCaseView(
        content_case_id=content_case.id,
        question=opportunity.question,
        reader=opportunity.reader,
        situation=opportunity.situation,
        need=opportunity.need,
        intent=opportunity.intent,
        promise=opportunity.promise,
        content_role=opportunity.suggested_role,
        coverage_requirements=[
            OperatorCoverageRequirementView(
                id=f"coverage-{index + 1}",
                requirement=requirement,
            )
            for index, requirement in enumerate(opportunity.coverage_requirements_json)
        ],
        state=state,
        intake=OperatorIntakeView(
            source_locale=spec.source_locale,
            research_country=spec.research_country,
            required_locales=[
                OperatorRequiredLocaleView(locale=row.locale, role=_locale_role(row.role))
                for row in requirements
            ],
        ),
        pending_gate=pending_gate,
        writer_lanes=writer_lanes,
        quality_lanes=quality_lanes,
    )


__all__ = [
    "OperatorAngleCandidateView",
    "OperatorAngleCoverageView",
    "OperatorAngleGateView",
    "OperatorCoverageRequirementView",
    "OperatorCaseView",
    "OperatorIntakeView",
    "OperatorOutlineArtifactView",
    "OperatorOutlineGateView",
    "OperatorRequiredLocaleView",
    "OperatorWriterLaneView",
    "OperatorQualityLaneView",
    "OperatorQualityRefView",
    "get_operator_case_view",
]