from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import Project, Signal
from app.modules.harness.models import Artifact
from app.modules.learning.models import (
    LearningApplication,
    LearningCandidate,
    LearningCandidateAssessment,
    LearningCandidateObservation,
    LearningCandidateReview,
    LearningCandidateSignal,
    LearningResolution,
    LearningResolutionApplication,
    LearningValidation,
)
from app.modules.measurement.models import ContentPerformanceObservation


class LearningReadError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class LearningEvidenceItem(BaseModel):
    kind: Literal["signal", "measurement_observation", "assessment_artifact"]
    id: UUID
    relation: str | None = None
    statement: str | None = None
    status: str | None = None
    source_kind: str | None = None
    occurred_at: datetime | None = None
    content_hash: str | None = None


class LearningReviewView(BaseModel):
    id: UUID
    decision: str
    reviewed_by: str
    reason: str
    candidate_snapshot_hash: str
    reviewed_at: datetime


class LearningApplicationView(BaseModel):
    id: UUID
    review_id: UUID
    target_type: str
    target_id: UUID | None
    resulting_target_id: UUID | None
    applied_action: str
    applied_signal_refs: list[object] = Field(default_factory=list)
    before_state_hash: str | None
    after_state_hash: str | None
    customer_map_snapshot_artifact_id: UUID | None
    change_report: dict[str, object] | None
    applied_by: str
    applied_at: datetime


class LearningResolutionView(BaseModel):
    id: UUID
    decision: str
    target_status: str | None
    reviewed_by: str
    reason: str
    validation_snapshot_hash: str
    reviewed_at: datetime
    application_receipt_id: UUID | None = None
    applied_action: str | None = None
    resulting_status: str | None = None
    applied_by: str | None = None
    applied_at: datetime | None = None


class LearningValidationView(BaseModel):
    id: UUID
    version: int
    validation_status: str
    validation_fingerprint: str
    target_type: str
    resulting_target_id: UUID | None
    baseline_signal_refs: list[object] = Field(default_factory=list)
    validation_signal_refs: list[object] = Field(default_factory=list)
    independent_evidence_groups: list[str] = Field(default_factory=list)
    metric_comparisons: list[object] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    evaluated_at: datetime
    resolution: LearningResolutionView | None = None


class LearningCandidateView(BaseModel):
    id: UUID
    candidate_key: str
    version: int
    target_type: str
    target_id: UUID | None
    statement: str
    relation: str
    proposal: dict[str, object]
    scope: dict[str, object]
    evidence_status: str
    alternative_explanations: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    expected_benefit: str | None
    regression_risk: str | None
    source_assessment_artifact_id: UUID
    supersedes_id: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime
    evidence: list[LearningEvidenceItem] = Field(default_factory=list)
    review: LearningReviewView | None = None
    application: LearningApplicationView | None = None
    validations: list[LearningValidationView] = Field(default_factory=list)


class LearningOverview(BaseModel):
    project_id: UUID
    project_slug: str
    counts: dict[str, int]
    semantics: dict[str, bool]
    candidates: list[LearningCandidateView] = Field(default_factory=list)


async def _project(
    session: AsyncSession,
    *,
    project_slug: str,
) -> Project:
    project = await session.scalar(
        select(Project).where(Project.slug == project_slug.strip())
    )
    if project is None:
        raise LearningReadError("learning_project_not_found")
    return project


async def build_learning_overview(
    session: AsyncSession,
    *,
    project_slug: str,
) -> LearningOverview:
    project = await _project(session, project_slug=project_slug)
    candidates = list(
        (
            await session.scalars(
                select(LearningCandidate)
                .where(LearningCandidate.project_id == project.id)
                .order_by(
                    LearningCandidate.created_at.desc(),
                    LearningCandidate.id,
                )
            )
        ).all()
    )
    if not candidates:
        return LearningOverview(
            project_id=project.id,
            project_slug=project.slug,
            counts={
                "candidates": 0,
                "ready_for_review": 0,
                "reviews": 0,
                "applications": 0,
                "validations": 0,
                "resolutions": 0,
            },
            semantics={
                "candidate_is_not_customer_truth": True,
                "evidence_is_not_learning_rule": True,
                "application_receipt_required_for_truth_change": True,
                "validation_does_not_auto_promote": True,
            },
            candidates=[],
        )

    candidate_ids = [row.id for row in candidates]

    reviews = list(
        (
            await session.scalars(
                select(LearningCandidateReview).where(
                    LearningCandidateReview.learning_candidate_id.in_(candidate_ids)
                )
            )
        ).all()
    )
    applications = list(
        (
            await session.scalars(
                select(LearningApplication).where(
                    LearningApplication.learning_candidate_id.in_(candidate_ids)
                )
            )
        ).all()
    )
    validations = list(
        (
            await session.scalars(
                select(LearningValidation).where(
                    LearningValidation.learning_candidate_id.in_(candidate_ids)
                )
            )
        ).all()
    )
    application_ids = [row.id for row in applications]
    resolutions = (
        list(
            (
                await session.scalars(
                    select(LearningResolution).where(
                        LearningResolution.learning_application_id.in_(application_ids)
                    )
                )
            ).all()
        )
        if application_ids
        else []
    )
    resolution_ids = [row.id for row in resolutions]
    resolution_applications = (
        list(
            (
                await session.scalars(
                    select(LearningResolutionApplication).where(
                        LearningResolutionApplication.learning_resolution_id.in_(
                            resolution_ids
                        )
                    )
                )
            ).all()
        )
        if resolution_ids
        else []
    )

    review_by_candidate = {row.learning_candidate_id: row for row in reviews}
    application_by_candidate = {
        row.learning_candidate_id: row for row in applications
    }
    validations_by_application: dict[UUID, list[LearningValidation]] = {}
    for row in validations:
        validations_by_application.setdefault(row.learning_application_id, []).append(row)
    for rows in validations_by_application.values():
        rows.sort(key=lambda row: (row.version, row.evaluated_at, str(row.id)))

    resolution_by_validation = {
        row.learning_validation_id: row for row in resolutions
    }
    resolution_application_by_resolution = {
        row.learning_resolution_id: row for row in resolution_applications
    }

    evidence_by_candidate: dict[UUID, list[LearningEvidenceItem]] = {
        candidate_id: [] for candidate_id in candidate_ids
    }

    signal_rows = (
        await session.execute(
            select(LearningCandidateSignal, Signal)
            .join(Signal, Signal.id == LearningCandidateSignal.signal_id)
            .where(LearningCandidateSignal.learning_candidate_id.in_(candidate_ids))
        )
    ).all()
    for link, signal in signal_rows:
        evidence_by_candidate[link.learning_candidate_id].append(
            LearningEvidenceItem(
                kind="signal",
                id=signal.id,
                relation=link.relation,
                statement=signal.observed_text,
                status=None,
                source_kind=signal.source_kind,
                occurred_at=signal.observed_at or signal.captured_at,
            )
        )

    observation_rows = (
        await session.execute(
            select(LearningCandidateObservation, ContentPerformanceObservation)
            .join(
                ContentPerformanceObservation,
                ContentPerformanceObservation.id
                == LearningCandidateObservation.observation_id,
            )
            .where(
                LearningCandidateObservation.learning_candidate_id.in_(candidate_ids)
            )
        )
    ).all()
    for link, observation in observation_rows:
        evidence_by_candidate[link.learning_candidate_id].append(
            LearningEvidenceItem(
                kind="measurement_observation",
                id=observation.id,
                relation=link.relation,
                statement=observation.statement,
                status=observation.data_status,
                occurred_at=observation.observed_at,
            )
        )

    assessment_rows = (
        await session.execute(
            select(LearningCandidateAssessment, Artifact)
            .join(
                Artifact,
                Artifact.id == LearningCandidateAssessment.assessment_artifact_id,
            )
            .where(
                LearningCandidateAssessment.learning_candidate_id.in_(candidate_ids)
            )
        )
    ).all()
    for link, artifact in assessment_rows:
        evidence_by_candidate[link.learning_candidate_id].append(
            LearningEvidenceItem(
                kind="assessment_artifact",
                id=artifact.id,
                status=artifact.artifact_type,
                occurred_at=artifact.created_at,
                content_hash=artifact.content_hash,
            )
        )

    for items in evidence_by_candidate.values():
        items.sort(
            key=lambda item: (
                item.occurred_at.timestamp()
                if item.occurred_at is not None
                else float("-inf"),
                str(item.id),
            ),
            reverse=True,
        )

    output: list[LearningCandidateView] = []
    for candidate in candidates:
        review = review_by_candidate.get(candidate.id)
        application = application_by_candidate.get(candidate.id)

        application_view = (
            LearningApplicationView(
                id=application.id,
                review_id=application.review_id,
                target_type=application.target_type,
                target_id=application.target_id,
                resulting_target_id=application.resulting_target_id,
                applied_action=application.applied_action,
                applied_signal_refs=list(application.applied_signal_refs_json),
                before_state_hash=application.before_state_hash,
                after_state_hash=application.after_state_hash,
                customer_map_snapshot_artifact_id=(
                    application.customer_map_snapshot_artifact_id
                ),
                change_report=application.change_report_json,
                applied_by=application.applied_by,
                applied_at=application.applied_at,
            )
            if application is not None
            else None
        )

        validation_views: list[LearningValidationView] = []
        if application is not None:
            for validation in validations_by_application.get(application.id, []):
                resolution = resolution_by_validation.get(validation.id)
                receipt = (
                    resolution_application_by_resolution.get(resolution.id)
                    if resolution is not None
                    else None
                )
                resolution_view = (
                    LearningResolutionView(
                        id=resolution.id,
                        decision=resolution.decision,
                        target_status=resolution.target_status,
                        reviewed_by=resolution.reviewed_by,
                        reason=resolution.reason,
                        validation_snapshot_hash=(
                            resolution.validation_snapshot_hash
                        ),
                        reviewed_at=resolution.reviewed_at,
                        application_receipt_id=receipt.id if receipt else None,
                        applied_action=receipt.applied_action if receipt else None,
                        resulting_status=receipt.resulting_status if receipt else None,
                        applied_by=receipt.applied_by if receipt else None,
                        applied_at=receipt.applied_at if receipt else None,
                    )
                    if resolution is not None
                    else None
                )
                validation_views.append(
                    LearningValidationView(
                        id=validation.id,
                        version=validation.version,
                        validation_status=validation.validation_status,
                        validation_fingerprint=validation.validation_fingerprint,
                        target_type=validation.target_type,
                        resulting_target_id=validation.resulting_target_id,
                        baseline_signal_refs=list(
                            validation.baseline_signal_refs_json
                        ),
                        validation_signal_refs=list(
                            validation.validation_signal_refs_json
                        ),
                        independent_evidence_groups=list(
                            validation.independent_evidence_groups_json
                        ),
                        metric_comparisons=list(
                            validation.metric_comparisons_json
                        ),
                        alternative_explanations=list(
                            validation.alternative_explanations_json
                        ),
                        missing_evidence=list(validation.missing_evidence_json),
                        evaluated_at=validation.evaluated_at,
                        resolution=resolution_view,
                    )
                )

        output.append(
            LearningCandidateView(
                id=candidate.id,
                candidate_key=candidate.candidate_key,
                version=candidate.version,
                target_type=candidate.target_type,
                target_id=candidate.target_id,
                statement=candidate.statement,
                relation=candidate.relation,
                proposal=dict(candidate.proposal_json),
                scope=dict(candidate.scope_json),
                evidence_status=candidate.evidence_status,
                alternative_explanations=list(
                    candidate.alternative_explanations_json
                ),
                missing_evidence=list(candidate.missing_evidence_json),
                expected_benefit=candidate.expected_benefit,
                regression_risk=candidate.regression_risk,
                source_assessment_artifact_id=(
                    candidate.source_assessment_artifact_id
                ),
                supersedes_id=candidate.supersedes_id,
                status=candidate.status,
                created_at=candidate.created_at,
                updated_at=candidate.updated_at,
                evidence=evidence_by_candidate.get(candidate.id, []),
                review=(
                    LearningReviewView(
                        id=review.id,
                        decision=review.decision,
                        reviewed_by=review.reviewed_by,
                        reason=review.reason,
                        candidate_snapshot_hash=review.candidate_snapshot_hash,
                        reviewed_at=review.reviewed_at,
                    )
                    if review is not None
                    else None
                ),
                application=application_view,
                validations=validation_views,
            )
        )

    return LearningOverview(
        project_id=project.id,
        project_slug=project.slug,
        counts={
            "candidates": len(candidates),
            "ready_for_review": sum(
                1
                for row in candidates
                if row.status == "OPEN"
                and row.evidence_status == "READY_FOR_REVIEW"
            ),
            "reviews": len(reviews),
            "applications": len(applications),
            "validations": len(validations),
            "resolutions": len(resolutions),
        },
        semantics={
            "candidate_is_not_customer_truth": True,
            "evidence_is_not_learning_rule": True,
            "application_receipt_required_for_truth_change": True,
            "validation_does_not_auto_promote": True,
        },
        candidates=output,
    )


__all__ = [
    "LearningOverview",
    "LearningReadError",
    "build_learning_overview",
]