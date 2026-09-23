from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.content_coverage import (
    ContentCoverageError,
    build_content_coverage,
)
from app.modules.content_engine.models import (
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    HumanSelection,
    NeedHypothesis,
    NeedHypothesisReview,
    Project,
    Signal,
)
from app.modules.customer_intelligence.models import (
    CustomerInsight,
    CustomerInsightReview,
)
from app.modules.harness.models import ContentRun
from app.modules.learning.models import (
    LearningApplication,
    LearningCandidate,
    LearningCandidateReview,
    LearningResolution,
    LearningResolutionApplication,
    LearningValidation,
)
from app.modules.measurement.models import (
    ContentPerformanceObservation,
    PerformanceSnapshot,
)
from app.modules.publishing.models import PublishedContent, PublishEvent


DigestDomain = Literal[
    "customer",
    "content",
    "production",
    "publication",
    "measurement",
    "learning",
]


class DailyDigestError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DigestEvent(BaseModel):
    domain: DigestDomain
    kind: str
    occurred_at: datetime
    entity_type: str
    entity_id: UUID
    summary: str
    status: str | None = None
    refs: list[str] = Field(default_factory=list)


class DailyDigest(BaseModel):
    schema_version: Literal[1] = 1
    project_id: UUID
    project_slug: str
    local_date: date
    timezone: str
    window_start: datetime
    window_end: datetime
    event_counts: dict[str, int]
    events: list[DigestEvent] = Field(default_factory=list)
    current_coverage_counts: dict[str, int]
    semantics: dict[str, bool]


def _window(
    *,
    local_date: date,
    timezone_name: str,
) -> tuple[ZoneInfo, datetime, datetime]:
    try:
        zone = ZoneInfo(timezone_name.strip())
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise DailyDigestError("daily_digest_timezone_invalid") from exc
    local_start = datetime.combine(local_date, time.min, tzinfo=zone)
    local_end = local_start + timedelta(days=1)
    return zone, local_start.astimezone(UTC), local_end.astimezone(UTC)


async def build_daily_digest(
    session: AsyncSession,
    *,
    project_slug: str,
    local_date: date,
    timezone_name: str,
) -> DailyDigest:
    project = await session.scalar(
        select(Project).where(Project.slug == project_slug.strip())
    )
    if project is None:
        raise DailyDigestError("daily_digest_project_not_found")
    zone, window_start, window_end = _window(
        local_date=local_date,
        timezone_name=timezone_name,
    )

    events: list[DigestEvent] = []

    signal_rows = list(
        (
            await session.scalars(
                select(Signal)
                .where(
                    Signal.project_id == project.id,
                    Signal.captured_at >= window_start,
                    Signal.captured_at < window_end,
                )
                .order_by(Signal.captured_at, Signal.id)
            )
        ).all()
    )
    events.extend(
        DigestEvent(
            domain="customer",
            kind="signal_captured",
            occurred_at=row.captured_at,
            entity_type="signal",
            entity_id=row.id,
            summary=row.observed_text,
            status=row.source_kind,
            refs=[
                ref
                for ref in (
                    f"source:{row.source_url}" if row.source_url else None,
                    f"external:{row.external_id}" if row.external_id else None,
                )
                if ref is not None
            ],
        )
        for row in signal_rows
    )

    need_review_rows = (
        await session.execute(
            select(NeedHypothesisReview, NeedHypothesis)
            .join(
                NeedHypothesis,
                NeedHypothesis.id == NeedHypothesisReview.need_hypothesis_id,
            )
            .where(
                NeedHypothesis.project_id == project.id,
                NeedHypothesisReview.reviewed_at >= window_start,
                    NeedHypothesisReview.reviewed_at < window_end,
            )
            .order_by(NeedHypothesisReview.reviewed_at, NeedHypothesisReview.id)
        )
    ).all()
    events.extend(
        DigestEvent(
            domain="customer",
            kind="need_reviewed",
            occurred_at=review.reviewed_at,
            entity_type="need_hypothesis",
            entity_id=need.id,
            summary=need.statement,
            status=review.status,
            refs=[f"review:{review.id}", f"need_version:{review.version}"],
        )
        for review, need in need_review_rows
    )

    insight_review_rows = (
        await session.execute(
            select(CustomerInsightReview, CustomerInsight)
            .join(
                CustomerInsight,
                CustomerInsight.id
                == CustomerInsightReview.customer_insight_id,
            )
            .where(
                CustomerInsight.project_id == project.id,
                CustomerInsightReview.reviewed_at >= window_start,
                    CustomerInsightReview.reviewed_at < window_end,
            )
            .order_by(
                CustomerInsightReview.reviewed_at,
                CustomerInsightReview.id,
            )
        )
    ).all()
    events.extend(
        DigestEvent(
            domain="customer",
            kind="insight_reviewed",
            occurred_at=review.reviewed_at,
            entity_type="customer_insight",
            entity_id=insight.id,
            summary=insight.statement,
            status=review.status,
            refs=[f"review:{review.id}", f"insight_version:{insight.version}"],
        )
        for review, insight in insight_review_rows
    )

    opportunity_rows = list(
        (
            await session.scalars(
                select(ContentOpportunity)
                .where(
                    ContentOpportunity.project_id == project.id,
                    ContentOpportunity.created_at >= window_start,
                    ContentOpportunity.created_at < window_end,
                )
                .order_by(ContentOpportunity.created_at, ContentOpportunity.id)
            )
        ).all()
    )
    events.extend(
        DigestEvent(
            domain="content",
            kind="content_opportunity_created",
            occurred_at=row.created_at,
            entity_type="content_opportunity",
            entity_id=row.id,
            summary=row.question,
            status=f"{row.decision}:{row.priority}",
            refs=[f"need:{row.need_hypothesis_id}", f"locale:{row.locale}"],
        )
        for row in opportunity_rows
    )

    selection_rows = (
        await session.execute(
            select(HumanSelection, ContentOpportunity)
            .join(
                ContentOpportunity,
                ContentOpportunity.id == HumanSelection.content_opportunity_id,
            )
            .where(
                ContentOpportunity.project_id == project.id,
                HumanSelection.selected_at >= window_start,
                    HumanSelection.selected_at < window_end,
            )
            .order_by(HumanSelection.selected_at, HumanSelection.id)
        )
    ).all()
    events.extend(
        DigestEvent(
            domain="content",
            kind="content_opportunity_selected",
            occurred_at=selection.selected_at,
            entity_type="content_opportunity",
            entity_id=opportunity.id,
            summary=opportunity.question,
            status=opportunity.decision,
            refs=[
                f"selection:{selection.id}",
                f"selected_by:{selection.selected_by}",
            ],
        )
        for selection, opportunity in selection_rows
    )

    item_rows = list(
        (
            await session.scalars(
                select(ContentItem)
                .where(
                    ContentItem.project_id == project.id,
                    ContentItem.created_at >= window_start,
                    ContentItem.created_at < window_end,
                )
                .order_by(ContentItem.created_at, ContentItem.id)
            )
        ).all()
    )
    events.extend(
        DigestEvent(
            domain="content",
            kind="content_item_created",
            occurred_at=row.created_at,
            entity_type="content_item",
            entity_id=row.id,
            summary=row.canonical_key,
            status=row.status,
            refs=[f"case:{row.content_case_id}"],
        )
        for row in item_rows
    )

    version_rows = (
        await session.execute(
            select(ContentVersion, ContentItem)
            .join(ContentItem, ContentItem.id == ContentVersion.content_item_id)
            .where(
                ContentItem.project_id == project.id,
                ContentVersion.created_at >= window_start,
                    ContentVersion.created_at < window_end,
            )
            .order_by(ContentVersion.created_at, ContentVersion.id)
        )
    ).all()
    events.extend(
        DigestEvent(
            domain="content",
            kind="content_version_created",
            occurred_at=version.created_at,
            entity_type="content_version",
            entity_id=version.id,
            summary=version.change_reason,
            status=version.status,
            refs=[
                f"content_item:{item.id}",
                f"version:{version.version_no}",
            ],
        )
        for version, item in version_rows
    )

    run_rows = list(
        (
            await session.scalars(
                select(ContentRun)
                .where(
                    ContentRun.project_id == project.id,
                    ContentRun.updated_at >= window_start,
                    ContentRun.updated_at < window_end,
                )
                .order_by(ContentRun.updated_at, ContentRun.id)
            )
        ).all()
    )
    events.extend(
        DigestEvent(
            domain="production",
            kind="content_run_state_updated",
            occurred_at=row.updated_at,
            entity_type="content_run",
            entity_id=row.id,
            summary=(
                f"Run mode {row.run_mode}; current step "
                f"{row.current_step or 'none'}."
            ),
            status=row.status,
            refs=[
                f"content_case:{row.content_case_id}",
                *(
                    [f"failure_code:{row.failure_code}"]
                    if row.failure_code
                    else []
                ),
            ],
        )
        for row in run_rows
    )

    publish_rows = (
        await session.execute(
            select(PublishEvent, PublishedContent)
            .join(
                PublishedContent,
                PublishedContent.id == PublishEvent.published_content_id,
            )
            .where(
                PublishedContent.project_id == project.id,
                PublishEvent.created_at >= window_start,
                    PublishEvent.created_at < window_end,
            )
            .order_by(PublishEvent.created_at, PublishEvent.id)
        )
    ).all()
    events.extend(
        DigestEvent(
            domain="publication",
            kind="publish_event_recorded",
            occurred_at=event.created_at,
            entity_type="publish_event",
            entity_id=event.id,
            summary=event.canonical_url,
            status=f"{event.action}:{event.external_status}",
            refs=[
                f"published_content:{published.id}",
                f"content_version:{event.content_version_id}",
            ],
        )
        for event, published in publish_rows
    )

    snapshot_rows = (
        await session.execute(
            select(PerformanceSnapshot, PublishedContent)
            .join(
                PublishedContent,
                PublishedContent.id == PerformanceSnapshot.published_content_id,
            )
            .where(
                PublishedContent.project_id == project.id,
                PerformanceSnapshot.imported_at >= window_start,
                    PerformanceSnapshot.imported_at < window_end,
            )
            .order_by(PerformanceSnapshot.imported_at, PerformanceSnapshot.id)
        )
    ).all()
    events.extend(
        DigestEvent(
            domain="measurement",
            kind="performance_snapshot_imported",
            occurred_at=snapshot.imported_at,
            entity_type="performance_snapshot",
            entity_id=snapshot.id,
            summary=(
                f"{snapshot.provider} window "
                f"{snapshot.window_start.isoformat()} → "
                f"{snapshot.window_end.isoformat()}"
            ),
            status=snapshot.provider,
            refs=[
                f"published_content:{published.id}",
                f"content_version:{snapshot.content_version_id}",
            ],
        )
        for snapshot, published in snapshot_rows
    )

    observation_rows = (
        await session.execute(
            select(ContentPerformanceObservation, PublishedContent)
            .join(
                PublishedContent,
                PublishedContent.id
                == ContentPerformanceObservation.published_content_id,
            )
            .where(
                PublishedContent.project_id == project.id,
                ContentPerformanceObservation.observed_at >= window_start,
                    ContentPerformanceObservation.observed_at < window_end,
            )
            .order_by(
                ContentPerformanceObservation.observed_at,
                ContentPerformanceObservation.id,
            )
        )
    ).all()
    events.extend(
        DigestEvent(
            domain="measurement",
            kind="performance_observation_recorded",
            occurred_at=observation.observed_at,
            entity_type="content_performance_observation",
            entity_id=observation.id,
            summary=observation.statement,
            status=observation.data_status,
            refs=[
                f"published_content:{published.id}",
                *[f"metric:{ref}" for ref in observation.metric_refs_json],
            ],
        )
        for observation, published in observation_rows
    )

    candidate_rows = list(
        (
            await session.scalars(
                select(LearningCandidate)
                .where(
                    LearningCandidate.project_id == project.id,
                    LearningCandidate.created_at >= window_start,
                    LearningCandidate.created_at < window_end,
                )
                .order_by(LearningCandidate.created_at, LearningCandidate.id)
            )
        ).all()
    )
    events.extend(
        DigestEvent(
            domain="learning",
            kind="learning_candidate_created",
            occurred_at=row.created_at,
            entity_type="learning_candidate",
            entity_id=row.id,
            summary=row.statement,
            status=f"{row.status}:{row.evidence_status}",
            refs=[
                f"target_type:{row.target_type}",
                *(
                    [f"target:{row.target_id}"]
                    if row.target_id is not None
                    else []
                ),
            ],
        )
        for row in candidate_rows
    )

    review_rows = (
        await session.execute(
            select(LearningCandidateReview, LearningCandidate)
            .join(
                LearningCandidate,
                LearningCandidate.id
                == LearningCandidateReview.learning_candidate_id,
            )
            .where(
                LearningCandidate.project_id == project.id,
                LearningCandidateReview.reviewed_at >= window_start,
                    LearningCandidateReview.reviewed_at < window_end,
            )
            .order_by(
                LearningCandidateReview.reviewed_at,
                LearningCandidateReview.id,
            )
        )
    ).all()
    events.extend(
        DigestEvent(
            domain="learning",
            kind="learning_candidate_reviewed",
            occurred_at=review.reviewed_at,
            entity_type="learning_candidate",
            entity_id=candidate.id,
            summary=review.reason,
            status=review.decision,
            refs=[f"review:{review.id}"],
        )
        for review, candidate in review_rows
    )

    application_rows = list(
        (
            await session.scalars(
                select(LearningApplication)
                .where(
                    LearningApplication.project_id == project.id,
                    LearningApplication.applied_at >= window_start,
                    LearningApplication.applied_at < window_end,
                )
                .order_by(LearningApplication.applied_at, LearningApplication.id)
            )
        ).all()
    )
    events.extend(
        DigestEvent(
            domain="learning",
            kind="learning_application_applied",
            occurred_at=row.applied_at,
            entity_type="learning_application",
            entity_id=row.id,
            summary=row.applied_action,
            status=row.target_type,
            refs=[
                f"learning_candidate:{row.learning_candidate_id}",
                f"review:{row.review_id}",
                *(
                    [f"resulting_target:{row.resulting_target_id}"]
                    if row.resulting_target_id is not None
                    else []
                ),
            ],
        )
        for row in application_rows
    )

    validation_rows = list(
        (
            await session.scalars(
                select(LearningValidation)
                .where(
                    LearningValidation.project_id == project.id,
                    LearningValidation.evaluated_at >= window_start,
                    LearningValidation.evaluated_at < window_end,
                )
                .order_by(
                    LearningValidation.evaluated_at,
                    LearningValidation.id,
                )
            )
        ).all()
    )
    events.extend(
        DigestEvent(
            domain="learning",
            kind="learning_validation_recorded",
            occurred_at=row.evaluated_at,
            entity_type="learning_validation",
            entity_id=row.id,
            summary=(
                f"Validation v{row.version} for {row.target_type}; "
                "human resolution remains separate."
            ),
            status=row.validation_status,
            refs=[
                f"learning_application:{row.learning_application_id}",
                f"learning_candidate:{row.learning_candidate_id}",
            ],
        )
        for row in validation_rows
    )

    resolution_rows = list(
        (
            await session.scalars(
                select(LearningResolution)
                .where(
                    LearningResolution.project_id == project.id,
                    LearningResolution.reviewed_at >= window_start,
                    LearningResolution.reviewed_at < window_end,
                )
                .order_by(
                    LearningResolution.reviewed_at,
                    LearningResolution.id,
                )
            )
        ).all()
    )
    events.extend(
        DigestEvent(
            domain="learning",
            kind="learning_resolution_reviewed",
            occurred_at=row.reviewed_at,
            entity_type="learning_resolution",
            entity_id=row.id,
            summary=row.reason,
            status=row.decision,
            refs=[
                f"learning_validation:{row.learning_validation_id}",
                f"learning_application:{row.learning_application_id}",
            ],
        )
        for row in resolution_rows
    )

    resolution_application_rows = list(
        (
            await session.scalars(
                select(LearningResolutionApplication)
                .where(
                    LearningResolutionApplication.project_id == project.id,
                    LearningResolutionApplication.applied_at >= window_start,
                    LearningResolutionApplication.applied_at < window_end,
                )
                .order_by(
                    LearningResolutionApplication.applied_at,
                    LearningResolutionApplication.id,
                )
            )
        ).all()
    )
    events.extend(
        DigestEvent(
            domain="learning",
            kind="learning_resolution_applied",
            occurred_at=row.applied_at,
            entity_type="learning_resolution_application",
            entity_id=row.id,
            summary=row.applied_action,
            status=row.decision,
            refs=[
                f"learning_resolution:{row.learning_resolution_id}",
                f"learning_validation:{row.learning_validation_id}",
                *(
                    [f"resulting_target:{row.resulting_target_id}"]
                    if row.resulting_target_id is not None
                    else []
                ),
            ],
        )
        for row in resolution_application_rows
    )

    try:
        coverage = await build_content_coverage(
            session,
            project_id=project.id,
        )
    except ContentCoverageError as exc:
        raise DailyDigestError(
            f"daily_digest_{exc.code}"
        ) from exc
    raw_counts = coverage.get("counts")
    if not isinstance(raw_counts, dict):
        raise DailyDigestError("daily_digest_coverage_counts_invalid")
    coverage_counts = {
        str(key): int(value)
        for key, value in raw_counts.items()
        if isinstance(value, int)
    }

    events.sort(
        key=lambda event: (
            event.occurred_at.timestamp(),
            event.domain,
            event.kind,
            str(event.entity_id),
        ),
        reverse=True,
    )
    domains: tuple[DigestDomain, ...] = (
        "customer",
        "content",
        "production",
        "publication",
        "measurement",
        "learning",
    )

    return DailyDigest(
        project_id=project.id,
        project_slug=project.slug,
        local_date=local_date,
        timezone=zone.key,
        window_start=window_start,
        window_end=window_end,
        event_counts={
            domain: sum(1 for event in events if event.domain == domain)
            for domain in domains
        },
        events=events,
        current_coverage_counts=coverage_counts,
        semantics={
            "events_are_durable_facts": True,
            "current_coverage_is_not_historical_change": True,
            "measurement_observation_is_not_causal_proof": True,
            "digest_does_not_trigger_research": True,
            "learning_validation_does_not_auto_promote": True,
        },
    )


__all__ = [
    "DailyDigest",
    "DailyDigestError",
    "build_daily_digest",
]