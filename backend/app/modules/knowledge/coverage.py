from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.coverage_models import KnowledgeCoveragePlan
from app.modules.knowledge.harvest import verify_knowledge_harvest_snapshot
from app.modules.knowledge.harvest_models import KnowledgeHarvest

PLANNER_METHOD = "leaf_topic_freshness_coverage_v1"
_REUSABLE_STATES = {"FRESH", "DUE"}
_RESEARCH_STATES = {"STALE", "UNKNOWN"}
_TARGET_NODE_TYPES = {"topic", "subtopic"}
_FRESHNESS_BUCKETS = {
    "FRESH": "fresh_candidate_ids",
    "DUE": "due_candidate_ids",
    "STALE": "stale_candidate_ids",
    "UNKNOWN": "unknown_candidate_ids",
    "UNCLASSIFIED": "unclassified_candidate_ids",
}


class KnowledgeCoveragePlanError(ValueError):
    """Raised when deterministic coverage planning cannot proceed safely."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _required_text(value: str, code: str, *, max_length: int | None = None) -> str:
    normalized = value.strip()
    if not normalized or (max_length is not None and len(normalized) > max_length):
        raise KnowledgeCoveragePlanError(code)
    return normalized


def _mapping(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise KnowledgeCoveragePlanError(code)
    return value


def _list(value: object, code: str) -> list[object]:
    if not isinstance(value, list):
        raise KnowledgeCoveragePlanError(code)
    return value


def _string(value: object, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise KnowledgeCoveragePlanError(code)
    return value


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _plan_payload(
    *,
    harvest: KnowledgeHarvest,
    lanes: list[dict[str, object]],
    summary: dict[str, object],
) -> dict[str, object]:
    return {
        "planner_method": PLANNER_METHOD,
        "project_id": str(harvest.project_id),
        "knowledge_harvest_id": str(harvest.id),
        "content_case_id": (
            str(harvest.content_case_id) if harvest.content_case_id is not None else None
        ),
        "locale": harvest.locale,
        "harvest_snapshot_hash": harvest.snapshot_hash,
        "lanes": lanes,
        "summary": summary,
    }


def _sorted_ids(values: set[str]) -> list[str]:
    return sorted(values)


def _candidate_buckets() -> dict[str, set[str]]:
    return {bucket: set() for bucket in _FRESHNESS_BUCKETS.values()}


def _classify_reason_codes(
    *,
    coverage_role: str,
    buckets: dict[str, list[str]],
    direct_candidate_count: int,
) -> list[str]:
    reasons: set[str] = set()
    if buckets["fresh_candidate_ids"]:
        reasons.add("fresh_candidate_reusable")
    if buckets["due_candidate_ids"]:
        reasons.add("due_candidate_reusable")
        reasons.add("due_candidate_refresh_recommended")
    if buckets["unclassified_candidate_ids"]:
        reasons.add("unclassified_candidate_requires_policy")

    if coverage_role == "target":
        if direct_candidate_count == 0:
            reasons.add("target_missing_candidate_requires_research")
        if buckets["stale_candidate_ids"]:
            reasons.add("target_stale_candidate_requires_research")
        if buckets["unknown_candidate_ids"]:
            reasons.add("target_unknown_candidate_requires_research")
    else:
        if direct_candidate_count == 0:
            reasons.add("context_missing_candidate_not_required")
        if buckets["stale_candidate_ids"]:
            reasons.add("context_stale_candidate_not_reused")
        if buckets["unknown_candidate_ids"]:
            reasons.add("context_unknown_candidate_not_reused")
    return sorted(reasons)


def derive_knowledge_coverage(
    harvest: KnowledgeHarvest,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Derive K4 only from one verified immutable K3 harvest snapshot."""

    payload = verify_knowledge_harvest_snapshot(harvest)
    scope_graph = _mapping(
        payload.get("scope_graph"),
        "knowledge_coverage_harvest_scope_graph_invalid",
    )
    topics_raw = _list(
        scope_graph.get("topics"),
        "knowledge_coverage_harvest_topics_invalid",
    )
    edges_raw = _list(
        scope_graph.get("contains_edges"),
        "knowledge_coverage_harvest_edges_invalid",
    )
    items_raw = _list(payload.get("items"), "knowledge_coverage_harvest_items_invalid")

    topics: dict[str, dict[str, object]] = {}
    for raw_topic in topics_raw:
        topic = _mapping(raw_topic, "knowledge_coverage_harvest_topic_invalid")
        topic_id = _string(topic.get("topic_id"), "knowledge_coverage_topic_id_invalid")
        if topic_id in topics:
            raise KnowledgeCoveragePlanError("knowledge_coverage_topic_duplicate")
        topics[topic_id] = topic

    children: dict[str, set[str]] = {topic_id: set() for topic_id in topics}
    for raw_edge in edges_raw:
        edge = _mapping(raw_edge, "knowledge_coverage_harvest_edge_invalid")
        parent_id = _string(
            edge.get("parent_topic_id"),
            "knowledge_coverage_edge_parent_invalid",
        )
        child_id = _string(
            edge.get("child_topic_id"),
            "knowledge_coverage_edge_child_invalid",
        )
        if parent_id not in topics or child_id not in topics:
            raise KnowledgeCoveragePlanError("knowledge_coverage_edge_outside_scope")
        children[parent_id].add(child_id)

    candidate_buckets_by_topic: dict[str, dict[str, set[str]]] = {
        topic_id: _candidate_buckets() for topic_id in topics
    }
    for raw_item in items_raw:
        item = _mapping(raw_item, "knowledge_coverage_harvest_item_invalid")
        candidate_id = _string(
            item.get("candidate_id"),
            "knowledge_coverage_candidate_id_invalid",
        )
        freshness = _mapping(
            item.get("freshness"),
            "knowledge_coverage_candidate_freshness_invalid",
        )
        state = _string(
            freshness.get("state"),
            "knowledge_coverage_candidate_freshness_invalid",
        )
        bucket = _FRESHNESS_BUCKETS.get(state)
        if bucket is None:
            raise KnowledgeCoveragePlanError("knowledge_coverage_freshness_state_invalid")
        scoped_links = _list(
            item.get("scoped_topic_links"),
            "knowledge_coverage_scoped_links_invalid",
        )
        for raw_link in scoped_links:
            link = _mapping(raw_link, "knowledge_coverage_scoped_link_invalid")
            topic_id = _string(
                link.get("topic_id"),
                "knowledge_coverage_scoped_link_topic_invalid",
            )
            if topic_id not in candidate_buckets_by_topic:
                raise KnowledgeCoveragePlanError(
                    "knowledge_coverage_scoped_link_outside_harvest"
                )
            candidate_buckets_by_topic[topic_id][bucket].add(candidate_id)

    lanes: list[dict[str, object]] = []
    for topic_id in sorted(topics):
        topic = topics[topic_id]
        child_topic_ids = _sorted_ids(children[topic_id])
        node_type = _string(
            topic.get("node_type"),
            "knowledge_coverage_topic_type_invalid",
        )
        coverage_role = (
            "target"
            if node_type in _TARGET_NODE_TYPES and not child_topic_ids
            else "context"
        )
        raw_buckets = candidate_buckets_by_topic[topic_id]
        buckets = {
            key: _sorted_ids(values)
            for key, values in raw_buckets.items()
        }
        all_candidate_ids = set().union(*raw_buckets.values())
        reuse_candidate_ids = sorted(
            raw_buckets["fresh_candidate_ids"] | raw_buckets["due_candidate_ids"]
        )
        research_candidate_ids = (
            sorted(
                raw_buckets["stale_candidate_ids"]
                | raw_buckets["unknown_candidate_ids"]
            )
            if coverage_role == "target"
            else []
        )
        reuse_ready = bool(reuse_candidate_ids)
        research_required = coverage_role == "target" and (
            not all_candidate_ids or bool(research_candidate_ids)
        )
        refresh_recommended = bool(raw_buckets["due_candidate_ids"])
        policy_required = bool(raw_buckets["unclassified_candidate_ids"])
        reason_codes = _classify_reason_codes(
            coverage_role=coverage_role,
            buckets=buckets,
            direct_candidate_count=len(all_candidate_ids),
        )
        lanes.append(
            {
                "topic_id": topic_id,
                "canonical_key": topic.get("canonical_key"),
                "name": topic.get("name"),
                "node_type": node_type,
                "description": topic.get("description"),
                "coverage_role": coverage_role,
                "child_topic_ids": child_topic_ids,
                **buckets,
                "reuse_candidate_ids": reuse_candidate_ids,
                "research_candidate_ids": research_candidate_ids,
                "reuse_ready": reuse_ready,
                "research_required": research_required,
                "refresh_recommended": refresh_recommended,
                "policy_required": policy_required,
                "reason_codes": reason_codes,
            }
        )

    scoped_topic_ids = [lane["topic_id"] for lane in lanes]
    target_topic_ids = [
        lane["topic_id"] for lane in lanes if lane["coverage_role"] == "target"
    ]
    context_topic_ids = [
        lane["topic_id"] for lane in lanes if lane["coverage_role"] == "context"
    ]
    reuse_ready_topic_ids = [
        lane["topic_id"] for lane in lanes if lane["reuse_ready"] is True
    ]
    research_required_topic_ids = [
        lane["topic_id"] for lane in lanes if lane["research_required"] is True
    ]
    refresh_recommended_topic_ids = [
        lane["topic_id"] for lane in lanes if lane["refresh_recommended"] is True
    ]
    policy_required_topic_ids = [
        lane["topic_id"] for lane in lanes if lane["policy_required"] is True
    ]
    summary: dict[str, object] = {
        "scoped_topic_ids": scoped_topic_ids,
        "scoped_topic_count": len(scoped_topic_ids),
        "target_topic_ids": target_topic_ids,
        "target_topic_count": len(target_topic_ids),
        "context_topic_ids": context_topic_ids,
        "context_topic_count": len(context_topic_ids),
        "reuse_ready_topic_ids": reuse_ready_topic_ids,
        "reuse_ready_topic_count": len(reuse_ready_topic_ids),
        "research_required_topic_ids": research_required_topic_ids,
        "research_required_topic_count": len(research_required_topic_ids),
        "refresh_recommended_topic_ids": refresh_recommended_topic_ids,
        "refresh_recommended_topic_count": len(refresh_recommended_topic_ids),
        "policy_required_topic_ids": policy_required_topic_ids,
        "policy_required_topic_count": len(policy_required_topic_ids),
    }
    return lanes, summary


def rebuild_knowledge_coverage_plan_snapshot(
    plan: KnowledgeCoveragePlan,
    *,
    harvest: KnowledgeHarvest,
) -> tuple[dict[str, object], str]:
    """Recompute a persisted K4 plan exclusively from its immutable K3 harvest."""

    if plan.planner_method != PLANNER_METHOD:
        raise KnowledgeCoveragePlanError("knowledge_coverage_plan_method_invalid")
    if plan.project_id != harvest.project_id:
        raise KnowledgeCoveragePlanError("knowledge_coverage_plan_project_mismatch")
    if plan.knowledge_harvest_id != harvest.id:
        raise KnowledgeCoveragePlanError("knowledge_coverage_plan_harvest_mismatch")
    if plan.content_case_id != harvest.content_case_id:
        raise KnowledgeCoveragePlanError("knowledge_coverage_plan_case_mismatch")
    if plan.locale != harvest.locale:
        raise KnowledgeCoveragePlanError("knowledge_coverage_plan_locale_mismatch")
    if plan.harvest_snapshot_hash != harvest.snapshot_hash:
        raise KnowledgeCoveragePlanError("knowledge_coverage_plan_harvest_hash_mismatch")

    lanes, summary = derive_knowledge_coverage(harvest)
    if plan.lanes_json != lanes:
        raise KnowledgeCoveragePlanError("knowledge_coverage_plan_lanes_mismatch")
    if plan.summary_json != summary:
        raise KnowledgeCoveragePlanError("knowledge_coverage_plan_summary_mismatch")
    payload = _plan_payload(harvest=harvest, lanes=lanes, summary=summary)
    return payload, _canonical_hash(payload)


async def verify_knowledge_coverage_plan(
    session: AsyncSession,
    *,
    plan: KnowledgeCoveragePlan,
) -> dict[str, object]:
    """Fail closed before downstream consumers use one persisted K4 plan."""

    harvest = await session.get(KnowledgeHarvest, plan.knowledge_harvest_id)
    if harvest is None:
        raise KnowledgeCoveragePlanError("knowledge_coverage_plan_harvest_not_found")
    payload, recomputed_hash = rebuild_knowledge_coverage_plan_snapshot(
        plan,
        harvest=harvest,
    )
    if recomputed_hash != plan.snapshot_hash:
        raise KnowledgeCoveragePlanError("knowledge_coverage_plan_snapshot_hash_mismatch")
    return payload


def _advisory_lock_key(harvest_id: UUID) -> int:
    digest = hashlib.sha256(f"{harvest_id}:{PLANNER_METHOD}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


async def plan_knowledge_coverage(
    session: AsyncSession,
    *,
    knowledge_harvest_id: UUID,
    created_by: str,
) -> KnowledgeCoveragePlan:
    """Create or replay the deterministic K4 plan for one K3 harvest."""

    actor = _required_text(
        created_by,
        "knowledge_coverage_plan_created_by_required",
        max_length=200,
    )
    harvest = await session.get(KnowledgeHarvest, knowledge_harvest_id)
    if harvest is None:
        raise KnowledgeCoveragePlanError("knowledge_coverage_plan_harvest_not_found")
    lanes, summary = derive_knowledge_coverage(harvest)
    payload = _plan_payload(harvest=harvest, lanes=lanes, summary=summary)
    snapshot_hash = _canonical_hash(payload)

    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _advisory_lock_key(harvest.id)},
    )
    existing = await session.scalar(
        select(KnowledgeCoveragePlan).where(
            KnowledgeCoveragePlan.knowledge_harvest_id == harvest.id,
            KnowledgeCoveragePlan.planner_method == PLANNER_METHOD,
        )
    )
    if existing is not None:
        await verify_knowledge_coverage_plan(session, plan=existing)
        return existing

    plan = KnowledgeCoveragePlan(
        project_id=harvest.project_id,
        knowledge_harvest_id=harvest.id,
        content_case_id=harvest.content_case_id,
        locale=harvest.locale,
        harvest_snapshot_hash=harvest.snapshot_hash,
        planner_method=PLANNER_METHOD,
        lanes_json=lanes,
        summary_json=summary,
        snapshot_hash=snapshot_hash,
        created_by=actor,
    )
    session.add(plan)
    await session.flush()
    return plan


__all__ = [
    "PLANNER_METHOD",
    "KnowledgeCoveragePlanError",
    "derive_knowledge_coverage",
    "plan_knowledge_coverage",
    "rebuild_knowledge_coverage_plan_snapshot",
    "verify_knowledge_coverage_plan",
]
