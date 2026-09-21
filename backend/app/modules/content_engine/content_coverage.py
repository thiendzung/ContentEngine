"""Deterministic Content Coverage read model for CC-01."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    ContentCase,
    ContentCaseSupportingNeed,
    ContentItem,
    ContentItemJourneyStage,
    ContentOpportunity,
    ContentVersion,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    Project,
)
from app.modules.customer_intelligence.living_map import resolve_journey_config
from app.modules.harness.models import Approval, ContentRun, QualityEvaluation

CoverageStatus = Literal[
    "MISSING",
    "PLANNED",
    "IN_PROGRESS",
    "PUBLISHED",
    "NEEDS_UPDATE",
    "WEAK",
    "INSUFFICIENT_DATA",
]
_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class ContentCoverageError(ValueError):
    """Fail-closed CC-01 error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class _VersionState:
    latest: ContentVersion | None
    latest_published: ContentVersion | None


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _required_text(value: str, code: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ContentCoverageError(code)
    return normalized


async def ensure_content_case_supporting_need(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    need_hypothesis_id: UUID,
    linked_by: str,
    reason: str,
) -> ContentCaseSupportingNeed:
    actor = _required_text(
        linked_by,
        "content_coverage_supporting_need_actor_required",
    )
    rationale = _required_text(
        reason,
        "content_coverage_supporting_need_reason_required",
    )
    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None:
        raise ContentCoverageError("content_coverage_case_not_found")
    need = await session.get(NeedHypothesis, need_hypothesis_id)
    if need is None:
        raise ContentCoverageError("content_coverage_need_not_found")
    if content_case.project_id != need.project_id:
        raise ContentCoverageError(
            "content_coverage_supporting_need_project_mismatch"
        )
    if content_case.need_hypothesis_id == need.id:
        raise ContentCoverageError(
            "content_coverage_supporting_need_is_primary"
        )
    if (
        content_case.audience_hypothesis_id is not None
        and need.audience_hypothesis_id is not None
        and content_case.audience_hypothesis_id
        != need.audience_hypothesis_id
    ):
        raise ContentCoverageError(
            "content_coverage_supporting_need_audience_mismatch"
        )

    existing = await session.get(
        ContentCaseSupportingNeed,
        (content_case_id, need_hypothesis_id),
    )
    if existing is not None:
        if existing.linked_by != actor or existing.reason != rationale:
            raise ContentCoverageError(
                "content_coverage_supporting_need_replay_conflict"
            )
        return existing

    link = ContentCaseSupportingNeed(
        content_case_id=content_case_id,
        need_hypothesis_id=need_hypothesis_id,
        linked_by=actor,
        reason=rationale,
    )
    session.add(link)
    await session.flush()
    return link


async def ensure_content_item_journey_stage(
    session: AsyncSession,
    *,
    content_item_id: UUID,
    stage_key: str,
    linked_by: str,
    reason: str,
) -> ContentItemJourneyStage:
    stage = stage_key.strip()
    actor = _required_text(
        linked_by,
        "content_coverage_journey_actor_required",
    )
    rationale = _required_text(
        reason,
        "content_coverage_journey_reason_required",
    )
    if not _KEY_RE.fullmatch(stage):
        raise ContentCoverageError("content_coverage_journey_stage_invalid")

    item = await session.get(ContentItem, content_item_id)
    if item is None:
        raise ContentCoverageError("content_coverage_item_not_found")
    journey = await resolve_journey_config(
        session,
        project_id=item.project_id,
    )
    configured = {str(row["key"]) for row in journey.stages}
    if stage not in configured:
        raise ContentCoverageError(
            "content_coverage_journey_stage_not_configured"
        )

    existing = await session.get(
        ContentItemJourneyStage,
        (content_item_id, stage),
    )
    if existing is not None:
        if existing.linked_by != actor or existing.reason != rationale:
            raise ContentCoverageError(
                "content_coverage_journey_stage_replay_conflict"
            )
        return existing

    link = ContentItemJourneyStage(
        content_item_id=content_item_id,
        stage_key=stage,
        linked_by=actor,
        reason=rationale,
    )
    session.add(link)
    await session.flush()
    return link


def _latest_version(rows: list[ContentVersion]) -> ContentVersion | None:
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: (row.version_no, row.created_at, str(row.id)),
    )


def _latest_published(rows: list[ContentVersion]) -> ContentVersion | None:
    published = [row for row in rows if row.status == "published"]
    if not published:
        return None
    return max(
        published,
        key=lambda row: (row.version_no, row.created_at, str(row.id)),
    )


def _version_payload(version: ContentVersion | None) -> dict[str, object] | None:
    if version is None:
        return None
    return {
        "id": str(version.id),
        "version_no": version.version_no,
        "status": version.status,
        "created_at": version.created_at.isoformat(),
    }


def _negative_final_decision(
    *,
    approvals: list[Approval],
    version_state: _VersionState,
) -> Approval | None:
    negatives = [
        row
        for row in approvals
        if row.decision in {"changes_requested", "rejected"}
    ]
    if not negatives:
        return None
    latest_negative = max(
        negatives,
        key=lambda row: (row.created_at, str(row.id)),
    )
    active_versions = [
        row
        for row in (version_state.latest, version_state.latest_published)
        if row is not None and row.status in {"approved", "published"}
    ]
    latest_active = (
        max(
            active_versions,
            key=lambda row: (row.created_at, row.version_no, str(row.id)),
        )
        if active_versions
        else None
    )
    if latest_active is not None and latest_active.created_at >= latest_negative.created_at:
        return None
    return latest_negative


def _version_no(value: object) -> int:
    if value is None:
        return 0
    if not isinstance(value, dict):
        raise ContentCoverageError("content_coverage_version_projection_invalid")
    version_no = value.get("version_no")
    if isinstance(version_no, bool) or not isinstance(version_no, int):
        raise ContentCoverageError("content_coverage_version_projection_invalid")
    return version_no


def _selected_opportunity_payload(
    opportunity: ContentOpportunity,
    selections: list[HumanSelection],
) -> dict[str, object]:
    return {
        "id": str(opportunity.id),
        "locale": opportunity.locale,
        "decision": opportunity.decision,
        "priority": opportunity.priority,
        "question": opportunity.question,
        "intent": opportunity.intent,
        "existing_content_refs": [
            str(ref) for ref in opportunity.existing_content_refs_json
        ],
        "selection_refs": [
            {
                "id": str(row.id),
                "selected_by": row.selected_by,
                "reason": row.reason,
                "selected_at": row.selected_at.isoformat(),
            }
            for row in sorted(
                selections,
                key=lambda row: (row.selected_at, str(row.id)),
            )
        ],
    }


def _parse_target_refs(
    opportunities: list[ContentOpportunity],
) -> tuple[set[UUID], list[str]]:
    targets: set[UUID] = set()
    invalid: list[str] = []
    for opportunity in opportunities:
        if opportunity.decision not in {"UPDATE", "REFRESH"}:
            continue
        for raw_ref in opportunity.existing_content_refs_json:
            if not isinstance(raw_ref, str):
                invalid.append(str(raw_ref))
                continue
            try:
                targets.add(UUID(raw_ref.strip()))
            except ValueError:
                invalid.append(raw_ref)
    return targets, invalid


def _duplicate_groups(
    items: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for item in items:
        if item.get("need_role") != "primary":
            continue
        locale = item.get("locale")
        intent = item.get("primary_intent")
        question = item.get("primary_question")
        item_id = item.get("id")
        if not all(
            isinstance(value, str)
            for value in (locale, intent, question, item_id)
        ):
            raise ContentCoverageError("content_coverage_item_projection_invalid")
        key = (
            str(locale),
            _normalized_text(str(intent)),
            _normalized_text(str(question)),
        )
        grouped[key].append(str(item_id))

    return [
        {
            "locale": key[0],
            "primary_intent": key[1],
            "normalized_primary_question": key[2],
            "content_item_ids": sorted(item_ids),
            "reason": "same_primary_need_locale_intent_question",
        }
        for key, item_ids in sorted(grouped.items())
        if len(item_ids) > 1
    ]


def _coverage_status(
    *,
    has_case: bool,
    items: list[dict[str, object]],
    selected_opportunities: list[ContentOpportunity],
    update_target_ids: set[UUID],
    invalid_target_refs: list[str],
    unresolved_quality_failure: bool,
) -> tuple[CoverageStatus, list[str]]:
    reasons: list[str] = []

    weak_ids = [
        item["id"]
        for item in items
        if item.get("unresolved_negative_final_decision") is not None
    ]
    published_ids = {
        UUID(str(item["id"]))
        for item in items
        if item.get("latest_published_version") is not None
    }
    update_in_progress = any(
        _version_no(item.get("latest_version"))
        > _version_no(item.get("latest_published_version"))
        for item in items
        if item.get("latest_published_version") is not None
    )
    unpublished_items = [
        item for item in items if item.get("latest_published_version") is None
    ]

    if published_ids:
        if published_ids & update_target_ids or update_in_progress:
            update_reasons = [
                "selected_update_or_refresh_targets_published_content"
                if published_ids & update_target_ids
                else "newer_unpublished_revision_exists"
            ]
            if invalid_target_refs:
                update_reasons.append("selected_update_target_ref_invalid")
            if weak_ids or unresolved_quality_failure:
                update_reasons.append("weak_or_failed_revision_exists")
            return "NEEDS_UPDATE", update_reasons
        published_reasons = ["published_content_exists"]
        if invalid_target_refs:
            published_reasons.append("selected_update_target_ref_invalid")
        if weak_ids or unresolved_quality_failure:
            published_reasons.append(
                "additional_weak_content_does_not_erase_published_coverage"
            )
        return "PUBLISHED", published_reasons

    if invalid_target_refs:
        return "INSUFFICIENT_DATA", ["selected_update_target_ref_invalid"]

    if weak_ids or unresolved_quality_failure:
        return "WEAK", [
            "unresolved_quality_failure_or_final_review_revision"
        ]

    if unpublished_items or (has_case and not items):
        reasons.append("content_work_exists_without_current_published_completion")
        return "IN_PROGRESS", reasons

    selected_write = [
        row
        for row in selected_opportunities
        if row.decision != "DO_NOT_WRITE"
    ]
    if selected_write:
        return "PLANNED", ["selected_content_opportunity_exists"]

    return "MISSING", ["no_content_or_selected_write_plan"]


async def build_content_coverage(
    session: AsyncSession,
    *,
    project_id: UUID,
    locale: str | None = None,
    audience_id: UUID | None = None,
    need_id: UUID | None = None,
) -> dict[str, object]:
    project = await session.get(Project, project_id)
    if project is None:
        raise ContentCoverageError("content_coverage_project_not_found")

    journey = await resolve_journey_config(session, project_id=project.id)
    stage_keys = {str(row["key"]) for row in journey.stages}
    locale_filter = locale.strip() if locale is not None else None
    if locale_filter == "":
        raise ContentCoverageError("content_coverage_locale_invalid")

    need_query = select(NeedHypothesis).where(
        NeedHypothesis.project_id == project.id
    )
    if audience_id is not None:
        need_query = need_query.where(
            NeedHypothesis.audience_hypothesis_id == audience_id
        )
    if need_id is not None:
        need_query = need_query.where(NeedHypothesis.id == need_id)
    needs = list(
        (
            await session.scalars(
                need_query.order_by(NeedHypothesis.id)
            )
        ).all()
    )
    if need_id is not None and not needs:
        raise ContentCoverageError("content_coverage_need_not_found")
    all_cases = list(
        (
            await session.scalars(
                select(ContentCase)
                .where(ContentCase.project_id == project.id)
                .order_by(ContentCase.created_at, ContentCase.id)
            )
        ).all()
    )
    case_ids = {row.id for row in all_cases}

    supporting_links = []
    if case_ids:
        supporting_links = list(
            (
                await session.scalars(
                    select(ContentCaseSupportingNeed)
                    .where(
                        ContentCaseSupportingNeed.content_case_id.in_(case_ids)
                    )
                    .order_by(
                        ContentCaseSupportingNeed.content_case_id,
                        ContentCaseSupportingNeed.need_hypothesis_id,
                    )
                )
            ).all()
        )

    cases_by_need: dict[UUID, list[tuple[ContentCase, str]]] = defaultdict(list)
    case_lookup = {row.id: row for row in all_cases}
    all_project_needs = {
        row.id: row
        for row in (
            await session.scalars(
                select(NeedHypothesis).where(
                    NeedHypothesis.project_id == project.id
                )
            )
        ).all()
    }
    for content_case in all_cases:
        primary_need = all_project_needs.get(content_case.need_hypothesis_id)
        if primary_need is None:
            raise ContentCoverageError(
                "content_coverage_primary_need_project_mismatch"
            )
        if (
            content_case.audience_hypothesis_id is not None
            and primary_need.audience_hypothesis_id is not None
            and content_case.audience_hypothesis_id
            != primary_need.audience_hypothesis_id
        ):
            raise ContentCoverageError(
                "content_coverage_primary_need_audience_mismatch"
            )
        cases_by_need[primary_need.id].append((content_case, "primary"))

    for supporting_link in supporting_links:
        supporting_case = case_lookup.get(supporting_link.content_case_id)
        support_need = all_project_needs.get(
            supporting_link.need_hypothesis_id
        )
        if supporting_case is None or support_need is None:
            raise ContentCoverageError(
                "content_coverage_supporting_need_project_mismatch"
            )
        if support_need.id == supporting_case.need_hypothesis_id:
            raise ContentCoverageError(
                "content_coverage_supporting_need_is_primary"
            )
        if (
            supporting_case.audience_hypothesis_id is not None
            and support_need.audience_hypothesis_id is not None
            and supporting_case.audience_hypothesis_id
            != support_need.audience_hypothesis_id
        ):
            raise ContentCoverageError(
                "content_coverage_supporting_need_audience_mismatch"
            )
        cases_by_need[support_need.id].append(
            (supporting_case, "supporting")
        )

    variants = []
    if case_ids:
        variant_query = select(LocaleVariant).where(
            LocaleVariant.content_case_id.in_(case_ids)
        )
        if locale_filter is not None:
            variant_query = variant_query.where(
                LocaleVariant.locale == locale_filter
            )
        variants = list(
            (
                await session.scalars(
                    variant_query.order_by(
                        LocaleVariant.content_case_id,
                        LocaleVariant.locale,
                        LocaleVariant.id,
                    )
                )
            ).all()
        )
    variant_by_id = {row.id: row for row in variants}
    variant_ids = set(variant_by_id)
    relevant_case_ids_for_locale = {
        row.content_case_id for row in variants
    }

    items = []
    if variant_ids:
        items = list(
            (
                await session.scalars(
                    select(ContentItem)
                    .where(
                        ContentItem.project_id == project.id,
                        ContentItem.locale_variant_id.in_(variant_ids),
                    )
                    .order_by(ContentItem.canonical_key, ContentItem.id)
                )
            ).all()
        )
    item_ids = {row.id for row in items}
    item_by_case: dict[UUID, list[ContentItem]] = defaultdict(list)
    for item in items:
        variant = variant_by_id.get(item.locale_variant_id)
        if variant is None or variant.content_case_id != item.content_case_id:
            raise ContentCoverageError(
                "content_coverage_item_variant_case_mismatch"
            )
        item_by_case[item.content_case_id].append(item)

    versions_by_item: dict[UUID, list[ContentVersion]] = defaultdict(list)
    if item_ids:
        version_rows = list(
            (
                await session.scalars(
                    select(ContentVersion)
                    .where(ContentVersion.content_item_id.in_(item_ids))
                    .order_by(
                        ContentVersion.content_item_id,
                        ContentVersion.version_no,
                    )
                )
            ).all()
        )
        for version in version_rows:
            versions_by_item[version.content_item_id].append(version)

    journey_by_item: dict[UUID, list[ContentItemJourneyStage]] = defaultdict(list)
    if item_ids:
        journey_rows = list(
            (
                await session.scalars(
                    select(ContentItemJourneyStage)
                    .where(ContentItemJourneyStage.content_item_id.in_(item_ids))
                    .order_by(
                        ContentItemJourneyStage.content_item_id,
                        ContentItemJourneyStage.stage_key,
                    )
                )
            ).all()
        )
        for journey_link in journey_rows:
            if journey_link.stage_key not in stage_keys:
                raise ContentCoverageError(
                    "content_coverage_journey_stage_stale"
                )
            journey_by_item[journey_link.content_item_id].append(
                journey_link
            )

    latest_quality_by_case_evaluator: dict[
        tuple[UUID, str], QualityEvaluation
    ] = {}
    if case_ids:
        quality_rows = (
            await session.execute(
                select(QualityEvaluation, ContentRun.content_case_id)
                .join(ContentRun, ContentRun.id == QualityEvaluation.run_id)
                .where(ContentRun.content_case_id.in_(case_ids))
            )
        ).all()
        for evaluation, content_case_id in quality_rows:
            key = (content_case_id, evaluation.evaluator_key)
            previous = latest_quality_by_case_evaluator.get(key)
            if previous is None or (
                evaluation.created_at,
                str(evaluation.id),
            ) > (
                previous.created_at,
                str(previous.id),
            ):
                latest_quality_by_case_evaluator[key] = evaluation
    failed_quality_case_ids = {
        content_case_id
        for (content_case_id, _evaluator), evaluation
        in latest_quality_by_case_evaluator.items()
        if evaluation.result == "fail"
    }

    approvals_by_item: dict[UUID, list[Approval]] = defaultdict(list)
    if item_ids:
        approval_rows = (
            await session.execute(
                select(Approval, ContentRun.content_item_id)
                .join(ContentRun, ContentRun.id == Approval.run_id)
                .where(
                    ContentRun.content_item_id.in_(item_ids),
                    Approval.step_key == "final_review",
                )
            )
        ).all()
        for approval, content_item_id in approval_rows:
            if content_item_id is None:
                continue
            approvals_by_item[content_item_id].append(approval)

    opportunity_query = select(ContentOpportunity).where(
        ContentOpportunity.project_id == project.id
    )
    if locale_filter is not None:
        opportunity_query = opportunity_query.where(
            ContentOpportunity.locale == locale_filter
        )
    opportunities = list(
        (
            await session.scalars(
                opportunity_query.order_by(
                    ContentOpportunity.need_hypothesis_id,
                    ContentOpportunity.version,
                    ContentOpportunity.id,
                )
            )
        ).all()
    )
    opportunity_ids = {row.id for row in opportunities}
    selections_by_opportunity: dict[UUID, list[HumanSelection]] = defaultdict(list)
    if opportunity_ids:
        selection_rows = list(
            (
                await session.scalars(
                    select(HumanSelection)
                    .where(
                        HumanSelection.content_opportunity_id.in_(
                            opportunity_ids
                        )
                    )
                    .order_by(
                        HumanSelection.content_opportunity_id,
                        HumanSelection.selected_at,
                        HumanSelection.id,
                    )
                )
            ).all()
        )
        for selection in selection_rows:
            selections_by_opportunity[
                selection.content_opportunity_id
            ].append(selection)

    selected_by_need: dict[UUID, list[ContentOpportunity]] = defaultdict(list)
    for opportunity in opportunities:
        if selections_by_opportunity.get(opportunity.id):
            selected_by_need[opportunity.need_hypothesis_id].append(
                opportunity
            )

    lanes: list[dict[str, object]] = []
    for need in needs:
        case_roles = cases_by_need.get(need.id, [])
        item_payloads: list[dict[str, object]] = []
        seen_item_roles: set[tuple[UUID, str]] = set()

        for content_case, need_role in case_roles:
            for item in item_by_case.get(content_case.id, []):
                identity = (item.id, need_role)
                if identity in seen_item_roles:
                    continue
                seen_item_roles.add(identity)
                variant = variant_by_id.get(item.locale_variant_id)
                if variant is None:
                    raise ContentCoverageError(
                        "content_coverage_variant_not_found"
                    )
                versions = versions_by_item.get(item.id, [])
                version_state = _VersionState(
                    latest=_latest_version(versions),
                    latest_published=_latest_published(versions),
                )
                negative = _negative_final_decision(
                    approvals=approvals_by_item.get(item.id, []),
                    version_state=version_state,
                )
                item_payloads.append(
                    {
                        "id": str(item.id),
                        "canonical_key": item.canonical_key,
                        "content_case_id": str(content_case.id),
                        "need_role": need_role,
                        "locale": variant.locale,
                        "content_role": variant.content_role,
                        "primary_question": variant.primary_question,
                        "primary_intent": variant.primary_intent,
                        "item_status": item.status,
                        "latest_version": _version_payload(
                            version_state.latest
                        ),
                        "latest_published_version": _version_payload(
                            version_state.latest_published
                        ),
                        "journey_stages": [
                            {
                                "stage_key": link.stage_key,
                                "linked_by": link.linked_by,
                                "reason": link.reason,
                            }
                            for link in journey_by_item.get(item.id, [])
                        ],
                        "unresolved_negative_final_decision": (
                            {
                                "id": str(negative.id),
                                "decision": negative.decision,
                                "actor_id": negative.actor_id,
                                "comment": negative.comment,
                                "created_at": negative.created_at.isoformat(),
                            }
                            if negative is not None
                            else None
                        ),
                    }
                )

        selected = selected_by_need.get(need.id, [])
        update_targets, invalid_target_refs = _parse_target_refs(selected)
        relevant_item_ids = {
            UUID(str(item["id"])) for item in item_payloads
        }
        unresolved_target_ids = update_targets - relevant_item_ids
        if unresolved_target_ids:
            invalid_target_refs.extend(
                str(item_id) for item_id in sorted(
                    unresolved_target_ids,
                    key=str,
                )
            )

        relevant_case_ids = {
            content_case.id for content_case, _ in case_roles
        }
        has_relevant_case = bool(case_roles) and (
            locale_filter is None
            or bool(relevant_case_ids & relevant_case_ids_for_locale)
        )
        status, reasons = _coverage_status(
            has_case=has_relevant_case,
            items=item_payloads,
            selected_opportunities=selected,
            update_target_ids=update_targets,
            invalid_target_refs=invalid_target_refs,
            unresolved_quality_failure=bool(
                relevant_case_ids & failed_quality_case_ids
            ),
        )
        duplicates = _duplicate_groups(item_payloads)
        if duplicates:
            reasons = [*reasons, "duplicate_candidate_detected"]

        lane: dict[str, object] = {
            "need": {
                "id": str(need.id),
                "type": need.type,
                "statement": need.statement,
                "status": need.status,
                "audience_hypothesis_id": (
                    str(need.audience_hypothesis_id)
                    if need.audience_hypothesis_id is not None
                    else None
                ),
            },
            "coverage_status": status,
            "reason_codes": reasons,
            "content_items": sorted(
                item_payloads,
                key=lambda item: (
                    str(item["locale"]),
                    str(item["canonical_key"]),
                    str(item["need_role"]),
                ),
            ),
            "selected_opportunities": [
                _selected_opportunity_payload(
                    opportunity,
                    selections_by_opportunity[opportunity.id],
                )
                for opportunity in selected
            ],
            "duplicate_candidates": duplicates,
            "invalid_update_target_refs": sorted(
                set(invalid_target_refs)
            ),
        }
        lanes.append(lane)

    counts = {
        status: sum(
            1 for lane in lanes if lane["coverage_status"] == status
        )
        for status in (
            "MISSING",
            "PLANNED",
            "IN_PROGRESS",
            "PUBLISHED",
            "NEEDS_UPDATE",
            "WEAK",
            "INSUFFICIENT_DATA",
        )
    }
    return {
        "schema_version": 1,
        "project": {
            "id": str(project.id),
            "slug": project.slug,
            "name": project.name,
        },
        "filters": {
            "locale": locale_filter,
            "audience_id": str(audience_id) if audience_id else None,
            "need_id": str(need_id) if need_id else None,
        },
        "journey": {
            "stages": [dict(stage) for stage in journey.stages],
            "source_refs": list(journey.source_refs),
        },
        "counts": counts,
        "needs": lanes,
        "semantics": {
            "published_does_not_mean_customer_problem_solved": True,
            "working_status_requires_measurement": True,
            "same_need_does_not_imply_duplicate_content": True,
        },
    }


__all__ = [
    "ContentCoverageError",
    "CoverageStatus",
    "build_content_coverage",
    "ensure_content_case_supporting_need",
    "ensure_content_item_journey_stage",
]