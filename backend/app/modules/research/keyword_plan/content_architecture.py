"""Deterministic locale-specific Pillar/Cluster architecture over Question Map planning."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.content_coverage import (
    ContentCoverageError,
    build_content_coverage,
)
from app.modules.research.keyword_plan.opportunity_planner_v2 import (
    OPPORTUNITY_PLANNER_POLICY_VERSION,
    OpportunityPlannerError,
    build_opportunity_plan_v2,
)

CONTENT_ARCHITECTURE_SCHEMA_VERSION = 1
CONTENT_ARCHITECTURE_POLICY_VERSION = "qm-content-architecture-v1"
MIN_PILLAR_MEMBER_CLUSTERS = 3

ArchitectureRole = Literal["pillar", "cluster"]


class ContentArchitectureError(ValueError):
    """Fail-closed content-architecture projection error."""

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


def _required_dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ContentArchitectureError(code)
    return value


def _required_list(value: object, code: str) -> list[object]:
    if not isinstance(value, list):
        raise ContentArchitectureError(code)
    return value


def _required_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContentArchitectureError(code)
    return value.strip()


def _string_list(value: object, code: str) -> list[str]:
    rows = _required_list(value, code)
    values = [
        item.strip()
        for item in rows
        if isinstance(item, str) and item.strip()
    ]
    if len(values) != len(rows):
        raise ContentArchitectureError(code)
    return sorted(set(values))


def content_architecture_candidate_key(
    *,
    need_id: str,
    locale: str,
    role: ArchitectureRole,
    member_cluster_keys: list[str],
) -> str:
    members = sorted(set(member_cluster_keys))
    if not members:
        raise ContentArchitectureError(
            "content_architecture_member_clusters_required"
        )
    payload = (
        f"{need_id}\x1f{locale}\x1f{role}\x1f"
        + "\x1e".join(members)
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:24]


def _coverage_lane(
    *,
    content_coverage: dict[str, object],
    need_id: str,
) -> dict[str, object]:
    lanes = _required_list(
        content_coverage.get("needs"),
        "content_architecture_coverage_projection_invalid",
    )
    matches: list[dict[str, object]] = []
    for raw in lanes:
        lane = _required_dict(
            raw,
            "content_architecture_coverage_projection_invalid",
        )
        need = _required_dict(
            lane.get("need"),
            "content_architecture_coverage_projection_invalid",
        )
        if str(need.get("id", "")) == need_id:
            matches.append(lane)
    if len(matches) != 1:
        raise ContentArchitectureError(
            "content_architecture_need_lane_missing"
        )
    return matches[0]


def _pillar_collision_state(
    *,
    lane: dict[str, object],
    locale: str,
) -> dict[str, object]:
    item_refs: list[str] = []
    for raw in _required_list(
        lane.get("content_items"),
        "content_architecture_coverage_projection_invalid",
    ):
        item = _required_dict(
            raw,
            "content_architecture_coverage_projection_invalid",
        )
        if (
            str(item.get("locale", "")).strip().casefold() == locale
            and str(item.get("content_role", "")).strip().casefold()
            == "pillar"
        ):
            item_refs.append(_required_text(
                item.get("id"),
                "content_architecture_coverage_projection_invalid",
            ))

    plan_refs: list[str] = []
    for raw in _required_list(
        lane.get("selected_opportunities"),
        "content_architecture_coverage_projection_invalid",
    ):
        opportunity = _required_dict(
            raw,
            "content_architecture_coverage_projection_invalid",
        )
        if (
            str(opportunity.get("locale", "")).strip().casefold() == locale
            and str(opportunity.get("suggested_role", "")).strip().casefold()
            == "pillar"
            and str(opportunity.get("decision", "")).strip().upper()
            != "DO_NOT_WRITE"
        ):
            plan_refs.append(_required_text(
                opportunity.get("id"),
                "content_architecture_coverage_projection_invalid",
            ))

    return {
        "existing_pillar_content_refs": sorted(set(item_refs)),
        "selected_pillar_plan_refs": sorted(set(plan_refs)),
        "has_collision": bool(item_refs or plan_refs),
    }


def _cluster_candidate(
    *,
    recommendation: dict[str, object],
    need_id: str,
    locale: str,
) -> dict[str, Any]:
    cluster_key = _required_text(
        recommendation.get("cluster_key"),
        "content_architecture_cluster_projection_invalid",
    )
    intent = _required_text(
        recommendation.get("intent"),
        "content_architecture_cluster_projection_invalid",
    )
    audience_stage = _required_text(
        recommendation.get("audience_stage"),
        "content_architecture_cluster_projection_invalid",
    )
    answer_job = _required_text(
        recommendation.get("answer_job"),
        "content_architecture_cluster_projection_invalid",
    )
    primary_question = _required_text(
        recommendation.get("primary_question"),
        "content_architecture_cluster_projection_invalid",
    )
    decision = _required_text(
        recommendation.get("decision"),
        "content_architecture_cluster_projection_invalid",
    )
    priority = _required_text(
        recommendation.get("priority"),
        "content_architecture_cluster_projection_invalid",
    )
    readiness = _required_text(
        recommendation.get("selection_readiness"),
        "content_architecture_cluster_projection_invalid",
    )
    dimensions = _required_dict(
        recommendation.get("dimensions"),
        "content_architecture_cluster_projection_invalid",
    )
    search = _required_dict(
        dimensions.get("search_evidence"),
        "content_architecture_cluster_projection_invalid",
    )
    content_gap = _required_dict(
        dimensions.get("content_gap"),
        "content_architecture_cluster_projection_invalid",
    )
    coverage_status = _required_text(
        content_gap.get("status"),
        "content_architecture_cluster_projection_invalid",
    )
    signal_refs = _string_list(
        search.get("signal_refs"),
        "content_architecture_cluster_projection_invalid",
    )
    search_count = search.get("question_count")
    if isinstance(search_count, bool) or not isinstance(search_count, int):
        raise ContentArchitectureError(
            "content_architecture_cluster_projection_invalid"
        )

    candidate_key = content_architecture_candidate_key(
        need_id=need_id,
        locale=locale,
        role="cluster",
        member_cluster_keys=[cluster_key],
    )
    return {
        "candidate_key": candidate_key,
        "role": "cluster",
        "member_cluster_keys": [cluster_key],
        "intent": intent,
        "audience_stage": audience_stage,
        "answer_job": answer_job,
        "primary_question": primary_question,
        "question_source": "search_language",
        "question_count": search_count,
        "signal_refs": signal_refs,
        "decision": decision,
        "priority": priority,
        "selection_readiness": readiness,
        "coverage_status": coverage_status,
        "selectable": (
            readiness == "READY_FOR_HUMAN_SELECTION"
            and decision != "DO_NOT_WRITE"
        ),
        "existing_content_refs": _string_list(
            recommendation.get("existing_content_refs"),
            "content_architecture_cluster_projection_invalid",
        ),
        "existing_plan_refs": _string_list(
            recommendation.get("existing_plan_refs"),
            "content_architecture_cluster_projection_invalid",
        ),
        "reason_codes": _string_list(
            recommendation.get("reason_codes"),
            "content_architecture_cluster_projection_invalid",
        ),
    }


def _pillar_candidate(
    *,
    need: dict[str, object],
    locale: str,
    clusters: list[dict[str, Any]],
    collision: dict[str, object],
) -> dict[str, Any] | None:
    eligible = [
        row
        for row in clusters
        if row["decision"] != "DO_NOT_WRITE"
        and row["selection_readiness"] == "READY_FOR_HUMAN_SELECTION"
    ]
    answer_jobs = {
        str(row["answer_job"])
        for row in eligible
    }
    primary_questions = {
        str(row["primary_question"]).strip().casefold()
        for row in eligible
    }
    if (
        len(eligible) < MIN_PILLAR_MEMBER_CLUSTERS
        or len(answer_jobs) < MIN_PILLAR_MEMBER_CLUSTERS
        or len(primary_questions) < MIN_PILLAR_MEMBER_CLUSTERS
    ):
        return None

    need_id = _required_text(
        need.get("id"),
        "content_architecture_need_projection_invalid",
    )
    statement = _required_text(
        need.get("statement"),
        "content_architecture_need_projection_invalid",
    )
    member_keys = sorted(
        str(row["member_cluster_keys"][0]) for row in eligible
    )
    candidate_key = content_architecture_candidate_key(
        need_id=need_id,
        locale=locale,
        role="pillar",
        member_cluster_keys=member_keys,
    )
    signal_refs = sorted({
        signal_ref
        for row in eligible
        for signal_ref in row["signal_refs"]
        if isinstance(signal_ref, str)
    })
    intents = sorted({str(row["intent"]) for row in eligible})
    stages = sorted({str(row["audience_stage"]) for row in eligible})
    has_collision = bool(collision["has_collision"])

    return {
        "candidate_key": candidate_key,
        "role": "pillar",
        "member_cluster_keys": member_keys,
        "intent": intents[0] if len(intents) == 1 else "mixed",
        "audience_stage": stages[0] if len(stages) == 1 else "mixed",
        "answer_job": "synthesize_need_overview",
        "primary_question": statement,
        "question_source": "canonical_need_statement",
        "question_count": sum(
            int(row["question_count"]) for row in eligible
        ),
        "signal_refs": signal_refs,
        "decision": "DO_NOT_WRITE" if has_collision else "CREATE",
        "priority": "NO" if has_collision else "NEXT",
        "selection_readiness": (
            "BLOCKED" if has_collision else "READY_FOR_HUMAN_SELECTION"
        ),
        "coverage_status": "COLLISION" if has_collision else "MIXED",
        "selectable": not has_collision,
        "existing_content_refs": collision[
            "existing_pillar_content_refs"
        ],
        "existing_plan_refs": collision[
            "selected_pillar_plan_refs"
        ],
        "reason_codes": (
            ["existing_pillar_or_selected_plan_collision"]
            if has_collision
            else ["distinct_ready_answer_jobs_support_pillar"]
        ),
        "member_clusters": [
            {
                "candidate_key": row["candidate_key"],
                "cluster_key": row["member_cluster_keys"][0],
                "intent": row["intent"],
                "audience_stage": row["audience_stage"],
                "answer_job": row["answer_job"],
                "primary_question": row["primary_question"],
                "decision": row["decision"],
                "selection_readiness": row["selection_readiness"],
                "coverage_status": row["coverage_status"],
                "existing_content_refs": row["existing_content_refs"],
                "existing_plan_refs": row["existing_plan_refs"],
            }
            for row in eligible
        ],
    }


def build_content_architecture_projection(
    *,
    planner: dict[str, object],
    content_coverage: dict[str, object],
) -> dict[str, object]:
    planner_hash = _required_text(
        planner.get("snapshot_hash"),
        "content_architecture_planner_hash_invalid",
    )
    if len(planner_hash) != 64:
        raise ContentArchitectureError(
            "content_architecture_planner_hash_invalid"
        )
    if planner.get("policy_version") != OPPORTUNITY_PLANNER_POLICY_VERSION:
        raise ContentArchitectureError(
            "content_architecture_planner_policy_mismatch"
        )

    project = _required_dict(
        planner.get("project"),
        "content_architecture_project_projection_invalid",
    )
    need = _required_dict(
        planner.get("need"),
        "content_architecture_need_projection_invalid",
    )
    need_id = _required_text(
        need.get("id"),
        "content_architecture_need_projection_invalid",
    )
    locale = _required_text(
        planner.get("locale"),
        "content_architecture_locale_invalid",
    ).casefold()

    coverage_project = _required_dict(
        content_coverage.get("project"),
        "content_architecture_coverage_projection_invalid",
    )
    if str(project.get("id", "")) != str(coverage_project.get("id", "")):
        raise ContentArchitectureError(
            "content_architecture_project_mismatch"
        )
    filters = _required_dict(
        content_coverage.get("filters"),
        "content_architecture_coverage_projection_invalid",
    )
    filter_need = filters.get("need_id")
    if filter_need is not None and str(filter_need) != need_id:
        raise ContentArchitectureError(
            "content_architecture_need_mismatch"
        )

    lane = _coverage_lane(
        content_coverage=content_coverage,
        need_id=need_id,
    )
    lane_hash = _stable_hash(lane)
    recommendations = [
        _required_dict(
            raw,
            "content_architecture_recommendation_projection_invalid",
        )
        for raw in _required_list(
            planner.get("recommendations"),
            "content_architecture_recommendation_projection_invalid",
        )
    ]
    clusters = [
        _cluster_candidate(
            recommendation=row,
            need_id=need_id,
            locale=locale,
        )
        for row in recommendations
    ]
    clusters.sort(key=lambda row: str(row["candidate_key"]))

    collision = _pillar_collision_state(
        lane=lane,
        locale=locale,
    )
    pillar = _pillar_candidate(
        need=need,
        locale=locale,
        clusters=clusters,
        collision=collision,
    )
    candidates: list[dict[str, Any]] = []
    if pillar is not None:
        candidates.append(pillar)
    candidates.extend(clusters)

    snapshot: dict[str, object] = {
        "schema_version": CONTENT_ARCHITECTURE_SCHEMA_VERSION,
        "policy_version": CONTENT_ARCHITECTURE_POLICY_VERSION,
        "project": project,
        "need": need,
        "locale": locale,
        "planner_snapshot_hash": planner_hash,
        "content_coverage_lane_hash": lane_hash,
        "pillar_policy": {
            "minimum_distinct_member_clusters": (
                MIN_PILLAR_MEMBER_CLUSTERS
            ),
            "requires_distinct_answer_jobs": True,
            "requires_distinct_primary_questions": True,
            "do_not_write_excluded_from_breadth": True,
            "blocked_or_research_required_excluded_from_selection": True,
            "no_forced_pillar": True,
        },
        "counts": {
            "cluster_candidates": len(clusters),
            "pillar_candidates": 1 if pillar is not None else 0,
            "selectable_candidates": sum(
                1 for row in candidates if row["selectable"]
            ),
        },
        "pillar_collision_state": collision,
        "candidates": candidates,
        "semantics": {
            "derived_read_model": True,
            "locale_specific": True,
            "does_not_translate_demand": True,
            "does_not_create_content": True,
            "does_not_create_child_cases": True,
            "founder_selection_required": True,
            "no_invented_parent_child_relation": True,
        },
    }
    return {
        **snapshot,
        "snapshot_hash": _stable_hash(snapshot),
    }


async def build_content_architecture(
    session: AsyncSession,
    *,
    project_id: UUID,
    need_id: UUID,
    locale: str,
) -> dict[str, object]:
    try:
        planner = await build_opportunity_plan_v2(
            session,
            project_id=project_id,
            need_id=need_id,
            locale=locale,
        )
        content_coverage = await build_content_coverage(
            session,
            project_id=project_id,
            need_id=need_id,
            locale=locale,
        )
    except (OpportunityPlannerError, ContentCoverageError) as exc:
        raise ContentArchitectureError(exc.code) from exc
    return build_content_architecture_projection(
        planner=planner,
        content_coverage=content_coverage,
    )


__all__ = [
    "CONTENT_ARCHITECTURE_POLICY_VERSION",
    "CONTENT_ARCHITECTURE_SCHEMA_VERSION",
    "MIN_PILLAR_MEMBER_CLUSTERS",
    "ArchitectureRole",
    "ContentArchitectureError",
    "build_content_architecture",
    "build_content_architecture_projection",
    "content_architecture_candidate_key",
]
