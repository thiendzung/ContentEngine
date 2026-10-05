"""Read-only join between Question Map clusters and Content Coverage."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.content_coverage import (
    ContentCoverageError,
    build_content_coverage,
)
from app.modules.research.keyword_plan.classification_v2 import (
    CLASSIFIER_VERSION,
    classify_question_v2,
)
from app.modules.research.keyword_plan.clustering_v2 import CLUSTERING_VERSION
from app.modules.research.keyword_plan.question_map import (
    QUESTION_MAP_SCHEMA_VERSION,
    build_question_map,
)

QUESTION_COVERAGE_SCHEMA_VERSION = 1
EXPECTED_CONTENT_COVERAGE_SCHEMA_VERSION = 1

QuestionCoverageStatus = Literal[
    "ANSWERED",
    "PARTIAL",
    "MISSING",
    "STALE",
    "COLLISION",
    "INSUFFICIENT_DATA",
]


class QuestionCoverageError(ValueError):
    """Fail-closed QM-01C error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _normalized(value: object) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _required_dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise QuestionCoverageError(code)
    return value


def _required_list(value: object, code: str) -> list[object]:
    if not isinstance(value, list):
        raise QuestionCoverageError(code)
    return value


def _version_no(value: object) -> int:
    if value is None:
        return 0
    row = _required_dict(
        value,
        "question_coverage_version_projection_invalid",
    )
    version_no = row.get("version_no")
    if isinstance(version_no, bool) or not isinstance(version_no, int):
        raise QuestionCoverageError(
            "question_coverage_version_projection_invalid"
        )
    return version_no


def _classify_candidate(
    *,
    question: object,
    stored_intent: object,
    locale: str,
    cluster_intent: str,
    cluster_answer_job: str,
) -> tuple[str, str | None]:
    if _normalized(stored_intent) != cluster_intent:
        return "irrelevant", None
    if not isinstance(question, str) or not question.strip():
        return "unresolved", "candidate_question_missing"

    classification = classify_question_v2(question, locale=locale)
    if (
        classification.classification_status != "classified"
        or str(classification.query_quality) != "usable"
        or classification.semantic_fallback_required
    ):
        return "unresolved", "candidate_semantics_unresolved"

    if str(classification.intent) != cluster_intent:
        return "unresolved", "stored_intent_classifier_mismatch"
    if classification.answer_job != cluster_answer_job:
        return "other_job", None
    return "match", None


def _item_is_stale(
    item: dict[str, object],
    *,
    update_target_ids: set[str],
) -> tuple[bool, list[str]]:
    item_id = str(item.get("id", ""))
    reasons: list[str] = []
    latest = item.get("latest_version")
    published = item.get("latest_published_version")
    if published is None:
        return False, reasons
    if _version_no(latest) > _version_no(published):
        reasons.append("newer_unpublished_revision_exists")
    if item_id in update_target_ids:
        reasons.append("selected_update_or_refresh_targets_content")
    return bool(reasons), reasons


def _selected_update_targets(
    selected_opportunities: list[dict[str, object]],
) -> set[str]:
    targets: set[str] = set()
    for opportunity in selected_opportunities:
        if opportunity.get("decision") not in {"UPDATE", "REFRESH"}:
            continue
        refs = opportunity.get("existing_content_refs")
        if not isinstance(refs, list):
            continue
        targets.update(
            ref.strip()
            for ref in refs
            if isinstance(ref, str) and ref.strip()
        )
    return targets


def _project_item(
    item: dict[str, object],
    *,
    stale: bool,
    stale_reasons: list[str],
) -> dict[str, object]:
    return {
        "id": str(item.get("id", "")),
        "canonical_key": item.get("canonical_key"),
        "content_case_id": item.get("content_case_id"),
        "need_role": item.get("need_role"),
        "locale": item.get("locale"),
        "content_role": item.get("content_role"),
        "primary_question": item.get("primary_question"),
        "primary_intent": item.get("primary_intent"),
        "latest_version": item.get("latest_version"),
        "latest_published_version": item.get("latest_published_version"),
        "publication": item.get("publication"),
        "stale": stale,
        "stale_reason_codes": stale_reasons,
    }


def _project_opportunity(
    opportunity: dict[str, object],
) -> dict[str, object]:
    return {
        "id": str(opportunity.get("id", "")),
        "locale": opportunity.get("locale"),
        "decision": opportunity.get("decision"),
        "priority": opportunity.get("priority"),
        "question": opportunity.get("question"),
        "intent": opportunity.get("intent"),
        "existing_content_refs": opportunity.get("existing_content_refs"),
    }


def _cluster_coverage(
    *,
    cluster: dict[str, object],
    content_items: list[dict[str, object]],
    selected_opportunities: list[dict[str, object]],
    locale: str,
) -> dict[str, object]:
    cluster_intent = _normalized(cluster.get("intent"))
    answer_job = _normalized(cluster.get("answer_job"))
    if not cluster_intent or not answer_job:
        raise QuestionCoverageError(
            "question_coverage_cluster_projection_invalid"
        )

    same_locale_items = [
        item
        for item in content_items
        if _normalized(item.get("locale")) == locale
    ]
    same_locale_opportunities = [
        row
        for row in selected_opportunities
        if _normalized(row.get("locale")) == locale
    ]
    update_target_ids = _selected_update_targets(
        same_locale_opportunities
    )

    matched_items: list[dict[str, object]] = []
    unresolved_candidates: list[dict[str, object]] = []
    for item in same_locale_items:
        relation, reason = _classify_candidate(
            question=item.get("primary_question"),
            stored_intent=item.get("primary_intent"),
            locale=locale,
            cluster_intent=cluster_intent,
            cluster_answer_job=answer_job,
        )
        if relation == "match":
            stale, stale_reasons = _item_is_stale(
                item,
                update_target_ids=update_target_ids,
            )
            matched_items.append(
                _project_item(
                    item,
                    stale=stale,
                    stale_reasons=stale_reasons,
                )
            )
        elif relation == "unresolved":
            unresolved_candidates.append(
                {
                    "kind": "content_item",
                    "id": str(item.get("id", "")),
                    "reason": reason,
                }
            )

    matched_opportunities: list[dict[str, object]] = []
    do_not_write_refs: list[str] = []
    for opportunity in same_locale_opportunities:
        relation, reason = _classify_candidate(
            question=opportunity.get("question"),
            stored_intent=opportunity.get("intent"),
            locale=locale,
            cluster_intent=cluster_intent,
            cluster_answer_job=answer_job,
        )
        if relation == "match":
            if opportunity.get("decision") == "DO_NOT_WRITE":
                do_not_write_refs.append(str(opportunity.get("id", "")))
            else:
                matched_opportunities.append(
                    _project_opportunity(opportunity)
                )
        elif relation == "unresolved":
            unresolved_candidates.append(
                {
                    "kind": "selected_opportunity",
                    "id": str(opportunity.get("id", "")),
                    "reason": reason,
                }
            )

    primary_items = [
        item for item in matched_items if item.get("need_role") == "primary"
    ]
    supporting_items = [
        item for item in matched_items if item.get("need_role") == "supporting"
    ]
    primary_published = [
        item
        for item in primary_items
        if item.get("latest_published_version") is not None
    ]
    supporting_published = [
        item
        for item in supporting_items
        if item.get("latest_published_version") is not None
    ]
    stale_primary = [item for item in primary_published if item["stale"]]
    create_plans = [
        row
        for row in matched_opportunities
        if row.get("decision") == "CREATE"
    ]

    reason_codes: list[str]
    status: QuestionCoverageStatus
    if len(primary_items) > 1 or (
        not primary_items and len(create_plans) > 1
    ):
        status = "COLLISION"
        reason_codes = ["multiple_primary_answers_or_create_plans"]
    elif stale_primary:
        status = "STALE"
        reason_codes = ["matching_primary_published_content_needs_update"]
    elif primary_published:
        status = "ANSWERED"
        reason_codes = ["matching_primary_published_content_exists"]
    elif primary_items or supporting_items or matched_opportunities:
        status = "PARTIAL"
        reason_codes = ["matching_work_or_plan_without_primary_published_answer"]
        if supporting_published and not primary_items:
            reason_codes.append("supporting_need_published_content_only")
    elif unresolved_candidates:
        status = "INSUFFICIENT_DATA"
        reason_codes = ["same_intent_candidate_semantics_unresolved"]
    else:
        status = "MISSING"
        reason_codes = ["no_matching_content_or_selected_write_plan"]

    if do_not_write_refs:
        reason_codes.append("selected_do_not_write_does_not_count_as_coverage")

    return {
        "status": status,
        "reason_codes": reason_codes,
        "matched_content_items": sorted(
            matched_items,
            key=lambda row: (
                str(row.get("need_role", "")),
                str(row.get("canonical_key", "")),
                str(row.get("id", "")),
            ),
        ),
        "matched_selected_opportunities": sorted(
            matched_opportunities,
            key=lambda row: str(row.get("id", "")),
        ),
        "unresolved_candidates": sorted(
            unresolved_candidates,
            key=lambda row: (
                str(row.get("kind", "")),
                str(row.get("id", "")),
            ),
        ),
        "do_not_write_opportunity_refs": sorted(do_not_write_refs),
    }


def join_question_map_with_coverage(
    *,
    question_map: dict[str, object],
    content_coverage: dict[str, object],
) -> dict[str, object]:
    if question_map.get("schema_version") != QUESTION_MAP_SCHEMA_VERSION:
        raise QuestionCoverageError(
            "question_coverage_question_map_schema_unsupported"
        )
    if (
        content_coverage.get("schema_version")
        != EXPECTED_CONTENT_COVERAGE_SCHEMA_VERSION
    ):
        raise QuestionCoverageError(
            "question_coverage_content_coverage_schema_unsupported"
        )

    question_project = _required_dict(
        question_map.get("project"),
        "question_coverage_project_projection_invalid",
    )
    coverage_project = _required_dict(
        content_coverage.get("project"),
        "question_coverage_project_projection_invalid",
    )
    if str(question_project.get("id", "")) != str(
        coverage_project.get("id", "")
    ):
        raise QuestionCoverageError("question_coverage_project_mismatch")

    source_policy = _required_dict(
        question_map.get("source_policy"),
        "question_coverage_question_map_projection_invalid",
    )
    if source_policy.get("classifier_version") != CLASSIFIER_VERSION:
        raise QuestionCoverageError(
            "question_coverage_classifier_version_mismatch"
        )
    if source_policy.get("clustering_version") != CLUSTERING_VERSION:
        raise QuestionCoverageError(
            "question_coverage_clustering_version_mismatch"
        )

    locale = _normalized(question_map.get("locale"))
    need = _required_dict(
        question_map.get("need"),
        "question_coverage_need_projection_invalid",
    )
    need_id = str(need.get("id", ""))
    if not locale or not need_id:
        raise QuestionCoverageError(
            "question_coverage_question_map_projection_invalid"
        )

    lanes = _required_list(
        content_coverage.get("needs"),
        "question_coverage_content_coverage_projection_invalid",
    )
    matching_lanes: list[dict[str, object]] = []
    for raw_lane in lanes:
        lane = _required_dict(
            raw_lane,
            "question_coverage_content_coverage_projection_invalid",
        )
        lane_need = _required_dict(
            lane.get("need"),
            "question_coverage_content_coverage_projection_invalid",
        )
        if str(lane_need.get("id", "")) == need_id:
            matching_lanes.append(lane)
    if len(matching_lanes) != 1:
        raise QuestionCoverageError("question_coverage_need_lane_missing")
    lane = matching_lanes[0]

    content_items = [
        _required_dict(
            row,
            "question_coverage_item_projection_invalid",
        )
        for row in _required_list(
            lane.get("content_items"),
            "question_coverage_item_projection_invalid",
        )
    ]
    selected_opportunities = [
        _required_dict(
            row,
            "question_coverage_opportunity_projection_invalid",
        )
        for row in _required_list(
            lane.get("selected_opportunities"),
            "question_coverage_opportunity_projection_invalid",
        )
    ]
    clusters = [
        _required_dict(
            row,
            "question_coverage_cluster_projection_invalid",
        )
        for row in _required_list(
            question_map.get("clusters"),
            "question_coverage_cluster_projection_invalid",
        )
    ]

    joined_clusters: list[dict[str, object]] = []
    for cluster in clusters:
        joined_clusters.append(
            {
                **cluster,
                "coverage": _cluster_coverage(
                    cluster=cluster,
                    content_items=content_items,
                    selected_opportunities=selected_opportunities,
                    locale=locale,
                ),
            }
        )

    statuses = (
        "ANSWERED",
        "PARTIAL",
        "MISSING",
        "STALE",
        "COLLISION",
        "INSUFFICIENT_DATA",
    )
    counts: dict[str, int] = {status: 0 for status in statuses}
    for cluster in joined_clusters:
        coverage = _required_dict(
            cluster.get("coverage"),
            "question_coverage_cluster_projection_invalid",
        )
        coverage_status = coverage.get("status")
        if not isinstance(coverage_status, str) or coverage_status not in counts:
            raise QuestionCoverageError(
                "question_coverage_cluster_status_invalid"
            )
        counts[coverage_status] += 1

    snapshot: dict[str, object] = {
        "schema_version": QUESTION_COVERAGE_SCHEMA_VERSION,
        "project": question_map.get("project"),
        "need": need,
        "locale": locale,
        "question_map_snapshot_hash": question_map.get("snapshot_hash"),
        "content_coverage_schema_version": content_coverage.get(
            "schema_version"
        ),
        "classifier_version": CLASSIFIER_VERSION,
        "clustering_version": CLUSTERING_VERSION,
        "counts": counts,
        "clusters": joined_clusters,
        "semantics": {
            "read_only_join": True,
            "published_does_not_mean_customer_problem_solved": True,
            "missing_requires_no_matching_classified_candidate": True,
            "insufficient_data_is_fail_closed": True,
        },
    }
    return {
        **snapshot,
        "snapshot_hash": _stable_hash(snapshot),
    }


async def build_question_coverage(
    session: AsyncSession,
    *,
    project_id: UUID,
    need_id: UUID,
    locale: str,
) -> dict[str, object]:
    question_map = await build_question_map(
        session,
        project_id=project_id,
        need_id=need_id,
        locale=locale,
    )
    try:
        content_coverage = await build_content_coverage(
            session,
            project_id=project_id,
            need_id=need_id,
        )
    except ContentCoverageError as exc:
        raise QuestionCoverageError(exc.code) from exc
    return join_question_map_with_coverage(
        question_map=question_map,
        content_coverage=content_coverage,
    )


__all__ = [
    "QUESTION_COVERAGE_SCHEMA_VERSION",
    "QuestionCoverageError",
    "QuestionCoverageStatus",
    "build_question_coverage",
    "join_question_map_with_coverage",
]
