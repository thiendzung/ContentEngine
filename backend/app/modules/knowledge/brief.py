from __future__ import annotations

import copy
import hashlib
import json
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.brief_models import KnowledgeBrief
from app.modules.knowledge.coverage import (
    KnowledgeCoveragePlanError,
    rebuild_knowledge_coverage_plan_snapshot,
    verify_knowledge_coverage_plan,
)
from app.modules.knowledge.coverage_models import KnowledgeCoveragePlan
from app.modules.knowledge.harvest import (
    KnowledgeHarvestError,
    verify_knowledge_harvest_snapshot,
)
from app.modules.knowledge.harvest_models import KnowledgeHarvest

BRIEF_METHOD = "coverage_bound_knowledge_brief_v1"
_REUSABLE_STATES = {"FRESH", "DUE"}
_RESEARCH_STATES = {"STALE", "UNKNOWN"}


class KnowledgeBriefError(ValueError):
    """Raised when a deterministic K5 KnowledgeBrief cannot be trusted."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _required_text(value: str, code: str, *, max_length: int | None = None) -> str:
    normalized = value.strip()
    if not normalized or (max_length is not None and len(normalized) > max_length):
        raise KnowledgeBriefError(code)
    return normalized


def _mapping(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise KnowledgeBriefError(code)
    return value


def _list(value: object, code: str) -> list[object]:
    if not isinstance(value, list):
        raise KnowledgeBriefError(code)
    return value


def _string(value: object, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise KnowledgeBriefError(code)
    return value


def _string_list(value: object, code: str) -> list[str]:
    raw = _list(value, code)
    output: list[str] = []
    for item in raw:
        output.append(_string(item, code))
    if output != sorted(output) or len(output) != len(set(output)):
        raise KnowledgeBriefError(code)
    return output


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _candidate_state(item: dict[str, object]) -> str:
    freshness = _mapping(
        item.get("freshness"),
        "knowledge_brief_candidate_freshness_invalid",
    )
    return _string(
        freshness.get("state"),
        "knowledge_brief_candidate_freshness_invalid",
    )


def _topic_action_payload(
    lane: dict[str, object],
    *,
    candidate_key: str,
) -> dict[str, object]:
    return {
        "topic_id": _string(lane.get("topic_id"), "knowledge_brief_topic_id_invalid"),
        "canonical_key": lane.get("canonical_key"),
        "name": lane.get("name"),
        "node_type": lane.get("node_type"),
        "description": lane.get("description"),
        "reason_codes": copy.deepcopy(
            _string_list(
                lane.get("reason_codes"),
                "knowledge_brief_reason_codes_invalid",
            )
        ),
        "candidate_ids": copy.deepcopy(
            _string_list(
                lane.get(candidate_key),
                "knowledge_brief_action_candidate_ids_invalid",
            )
        ),
    }


def _assert_candidate_states(
    *,
    candidate_ids: list[str],
    item_by_id: dict[str, dict[str, object]],
    allowed_states: set[str],
    missing_code: str,
    state_code: str,
) -> None:
    for candidate_id in candidate_ids:
        item = item_by_id.get(candidate_id)
        if item is None:
            raise KnowledgeBriefError(missing_code)
        if _candidate_state(item) not in allowed_states:
            raise KnowledgeBriefError(state_code)


def derive_knowledge_brief(
    plan: KnowledgeCoveragePlan,
    *,
    harvest: KnowledgeHarvest,
) -> dict[str, object]:
    """Derive one self-contained K5 brief only from verified frozen K3/K4 snapshots."""

    try:
        harvest_payload = verify_knowledge_harvest_snapshot(harvest)
        plan_payload, recomputed_plan_hash = rebuild_knowledge_coverage_plan_snapshot(
            plan,
            harvest=harvest,
        )
    except (KnowledgeHarvestError, KnowledgeCoveragePlanError) as exc:
        raise KnowledgeBriefError(str(exc)) from exc
    if recomputed_plan_hash != plan.snapshot_hash:
        raise KnowledgeBriefError("knowledge_brief_coverage_plan_hash_mismatch")

    raw_items = _list(
        harvest_payload.get("items"),
        "knowledge_brief_harvest_items_invalid",
    )
    item_by_id: dict[str, dict[str, object]] = {}
    for raw_item in raw_items:
        item = _mapping(raw_item, "knowledge_brief_harvest_item_invalid")
        candidate_id = _string(
            item.get("candidate_id"),
            "knowledge_brief_candidate_id_invalid",
        )
        if candidate_id in item_by_id:
            raise KnowledgeBriefError("knowledge_brief_candidate_duplicate")
        item_by_id[candidate_id] = item

    raw_lanes = _list(plan_payload.get("lanes"), "knowledge_brief_plan_lanes_invalid")
    lanes = [
        _mapping(raw_lane, "knowledge_brief_plan_lane_invalid")
        for raw_lane in raw_lanes
    ]
    if [lane.get("topic_id") for lane in lanes] != sorted(
        _string(lane.get("topic_id"), "knowledge_brief_topic_id_invalid")
        for lane in lanes
    ):
        raise KnowledgeBriefError("knowledge_brief_plan_lanes_not_canonical")

    reusable_candidate_ids: set[str] = set()
    research_candidate_ids: set[str] = set()
    refresh_candidate_ids: set[str] = set()
    policy_candidate_ids: set[str] = set()
    research_targets: list[dict[str, object]] = []
    refresh_recommendations: list[dict[str, object]] = []
    policy_required_targets: list[dict[str, object]] = []

    for lane in lanes:
        reuse_ids = _string_list(
            lane.get("reuse_candidate_ids"),
            "knowledge_brief_reuse_candidate_ids_invalid",
        )
        _assert_candidate_states(
            candidate_ids=reuse_ids,
            item_by_id=item_by_id,
            allowed_states=_REUSABLE_STATES,
            missing_code="knowledge_brief_reuse_candidate_missing_from_harvest",
            state_code="knowledge_brief_reuse_candidate_state_invalid",
        )
        reusable_candidate_ids.update(reuse_ids)

        if lane.get("research_required") is True:
            if lane.get("coverage_role") != "target":
                raise KnowledgeBriefError("knowledge_brief_context_research_target_invalid")
            action = _topic_action_payload(
                lane,
                candidate_key="research_candidate_ids",
            )
            action_candidate_ids = _string_list(
                action["candidate_ids"],
                "knowledge_brief_research_candidate_ids_invalid",
            )
            _assert_candidate_states(
                candidate_ids=action_candidate_ids,
                item_by_id=item_by_id,
                allowed_states=_RESEARCH_STATES,
                missing_code="knowledge_brief_research_candidate_missing_from_harvest",
                state_code="knowledge_brief_research_candidate_state_invalid",
            )
            research_candidate_ids.update(action_candidate_ids)
            research_targets.append(action)

        if lane.get("refresh_recommended") is True:
            action = _topic_action_payload(lane, candidate_key="due_candidate_ids")
            action_candidate_ids = _string_list(
                action["candidate_ids"],
                "knowledge_brief_refresh_candidate_ids_invalid",
            )
            if not action_candidate_ids:
                raise KnowledgeBriefError("knowledge_brief_refresh_candidate_required")
            _assert_candidate_states(
                candidate_ids=action_candidate_ids,
                item_by_id=item_by_id,
                allowed_states={"DUE"},
                missing_code="knowledge_brief_refresh_candidate_missing_from_harvest",
                state_code="knowledge_brief_refresh_candidate_state_invalid",
            )
            refresh_candidate_ids.update(action_candidate_ids)
            refresh_recommendations.append(action)

        if lane.get("policy_required") is True:
            action = _topic_action_payload(
                lane,
                candidate_key="unclassified_candidate_ids",
            )
            action_candidate_ids = _string_list(
                action["candidate_ids"],
                "knowledge_brief_policy_candidate_ids_invalid",
            )
            if not action_candidate_ids:
                raise KnowledgeBriefError("knowledge_brief_policy_candidate_required")
            _assert_candidate_states(
                candidate_ids=action_candidate_ids,
                item_by_id=item_by_id,
                allowed_states={"UNCLASSIFIED"},
                missing_code="knowledge_brief_policy_candidate_missing_from_harvest",
                state_code="knowledge_brief_policy_candidate_state_invalid",
            )
            policy_candidate_ids.update(action_candidate_ids)
            policy_required_targets.append(action)

    reusable_ids = sorted(reusable_candidate_ids)
    reusable_knowledge = [copy.deepcopy(item_by_id[candidate_id]) for candidate_id in reusable_ids]
    if any(
        _candidate_state(item) not in _REUSABLE_STATES
        for item in reusable_knowledge
    ):
        raise KnowledgeBriefError("knowledge_brief_nonreusable_candidate_leaked")

    research_targets.sort(key=lambda value: str(value["topic_id"]))
    refresh_recommendations.sort(key=lambda value: str(value["topic_id"]))
    policy_required_targets.sort(key=lambda value: str(value["topic_id"]))

    research_topic_ids = [str(value["topic_id"]) for value in research_targets]
    refresh_topic_ids = [str(value["topic_id"]) for value in refresh_recommendations]
    policy_topic_ids = [str(value["topic_id"]) for value in policy_required_targets]

    summary: dict[str, object] = {
        "reusable_candidate_ids": reusable_ids,
        "reusable_candidate_count": len(reusable_ids),
        "research_target_topic_ids": research_topic_ids,
        "research_target_topic_count": len(research_topic_ids),
        "research_candidate_ids": sorted(research_candidate_ids),
        "research_candidate_count": len(research_candidate_ids),
        "refresh_topic_ids": refresh_topic_ids,
        "refresh_topic_count": len(refresh_topic_ids),
        "refresh_candidate_ids": sorted(refresh_candidate_ids),
        "refresh_candidate_count": len(refresh_candidate_ids),
        "policy_required_topic_ids": policy_topic_ids,
        "policy_required_topic_count": len(policy_topic_ids),
        "policy_candidate_ids": sorted(policy_candidate_ids),
        "policy_candidate_count": len(policy_candidate_ids),
    }

    requested_topic_ids = copy.deepcopy(
        _string_list(
            harvest_payload.get("requested_topic_ids"),
            "knowledge_brief_requested_topics_invalid",
        )
    )
    expanded_topic_ids = copy.deepcopy(
        _string_list(
            harvest_payload.get("expanded_topic_ids"),
            "knowledge_brief_expanded_topics_invalid",
        )
    )
    as_of = _string(harvest_payload.get("as_of"), "knowledge_brief_as_of_invalid")

    return {
        "brief_method": BRIEF_METHOD,
        "project_id": str(plan.project_id),
        "knowledge_coverage_plan_id": str(plan.id),
        "coverage_plan_snapshot_hash": plan.snapshot_hash,
        "knowledge_harvest_id": str(harvest.id),
        "harvest_snapshot_hash": harvest.snapshot_hash,
        "content_case_id": (
            str(plan.content_case_id) if plan.content_case_id is not None else None
        ),
        "locale": plan.locale,
        "as_of": as_of,
        "requested_topic_ids": requested_topic_ids,
        "expanded_topic_ids": expanded_topic_ids,
        "topic_contexts": copy.deepcopy(lanes),
        "reusable_knowledge": reusable_knowledge,
        "research_targets": research_targets,
        "refresh_recommendations": refresh_recommendations,
        "policy_required_targets": policy_required_targets,
        "summary": summary,
    }


def rebuild_knowledge_brief_snapshot(
    brief: KnowledgeBrief,
    *,
    plan: KnowledgeCoveragePlan,
    harvest: KnowledgeHarvest,
) -> tuple[dict[str, object], str]:
    """Recompute and validate one persisted K5 snapshot from immutable parents."""

    if brief.brief_method != BRIEF_METHOD:
        raise KnowledgeBriefError("knowledge_brief_method_invalid")
    if brief.project_id != plan.project_id or brief.project_id != harvest.project_id:
        raise KnowledgeBriefError("knowledge_brief_project_mismatch")
    if brief.knowledge_coverage_plan_id != plan.id:
        raise KnowledgeBriefError("knowledge_brief_coverage_plan_mismatch")
    if brief.knowledge_harvest_id != harvest.id:
        raise KnowledgeBriefError("knowledge_brief_harvest_mismatch")
    if plan.knowledge_harvest_id != harvest.id:
        raise KnowledgeBriefError("knowledge_brief_plan_harvest_mismatch")
    if brief.content_case_id != plan.content_case_id or brief.content_case_id != harvest.content_case_id:
        raise KnowledgeBriefError("knowledge_brief_case_mismatch")
    if brief.locale != plan.locale or brief.locale != harvest.locale:
        raise KnowledgeBriefError("knowledge_brief_locale_mismatch")
    if brief.coverage_plan_snapshot_hash != plan.snapshot_hash:
        raise KnowledgeBriefError("knowledge_brief_plan_hash_mismatch")
    if brief.harvest_snapshot_hash != harvest.snapshot_hash:
        raise KnowledgeBriefError("knowledge_brief_harvest_hash_mismatch")

    payload = derive_knowledge_brief(plan, harvest=harvest)
    if brief.brief_json != payload:
        raise KnowledgeBriefError("knowledge_brief_payload_mismatch")
    return payload, _canonical_hash(payload)


async def verify_knowledge_brief(
    session: AsyncSession,
    *,
    brief: KnowledgeBrief,
) -> dict[str, object]:
    """Fail closed before any downstream consumer uses a persisted K5 brief."""

    plan = await session.get(KnowledgeCoveragePlan, brief.knowledge_coverage_plan_id)
    if plan is None:
        raise KnowledgeBriefError("knowledge_brief_coverage_plan_not_found")
    harvest = await session.get(KnowledgeHarvest, brief.knowledge_harvest_id)
    if harvest is None:
        raise KnowledgeBriefError("knowledge_brief_harvest_not_found")
    try:
        await verify_knowledge_coverage_plan(session, plan=plan)
        verify_knowledge_harvest_snapshot(harvest)
    except (KnowledgeCoveragePlanError, KnowledgeHarvestError) as exc:
        raise KnowledgeBriefError(str(exc)) from exc
    payload, recomputed_hash = rebuild_knowledge_brief_snapshot(
        brief,
        plan=plan,
        harvest=harvest,
    )
    if recomputed_hash != brief.snapshot_hash:
        raise KnowledgeBriefError("knowledge_brief_snapshot_hash_mismatch")
    return payload


def _advisory_lock_key(plan_id: UUID) -> int:
    digest = hashlib.sha256(f"{plan_id}:{BRIEF_METHOD}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


async def materialize_knowledge_brief(
    session: AsyncSession,
    *,
    knowledge_coverage_plan_id: UUID,
    created_by: str,
) -> KnowledgeBrief:
    """Create or exactly replay one deterministic K5 brief."""

    actor = _required_text(
        created_by,
        "knowledge_brief_created_by_required",
        max_length=200,
    )
    plan = await session.get(KnowledgeCoveragePlan, knowledge_coverage_plan_id)
    if plan is None:
        raise KnowledgeBriefError("knowledge_brief_coverage_plan_not_found")
    try:
        await verify_knowledge_coverage_plan(session, plan=plan)
    except KnowledgeCoveragePlanError as exc:
        raise KnowledgeBriefError(str(exc)) from exc

    harvest = await session.get(KnowledgeHarvest, plan.knowledge_harvest_id)
    if harvest is None:
        raise KnowledgeBriefError("knowledge_brief_harvest_not_found")
    try:
        verify_knowledge_harvest_snapshot(harvest)
    except KnowledgeHarvestError as exc:
        raise KnowledgeBriefError(str(exc)) from exc

    payload = derive_knowledge_brief(plan, harvest=harvest)
    snapshot_hash = _canonical_hash(payload)

    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _advisory_lock_key(plan.id)},
    )
    existing = await session.scalar(
        select(KnowledgeBrief).where(
            KnowledgeBrief.knowledge_coverage_plan_id == plan.id,
            KnowledgeBrief.brief_method == BRIEF_METHOD,
        )
    )
    if existing is not None:
        await verify_knowledge_brief(session, brief=existing)
        return existing

    brief = KnowledgeBrief(
        project_id=plan.project_id,
        knowledge_coverage_plan_id=plan.id,
        knowledge_harvest_id=harvest.id,
        content_case_id=plan.content_case_id,
        locale=plan.locale,
        coverage_plan_snapshot_hash=plan.snapshot_hash,
        harvest_snapshot_hash=harvest.snapshot_hash,
        brief_method=BRIEF_METHOD,
        brief_json=payload,
        snapshot_hash=snapshot_hash,
        created_by=actor,
    )
    session.add(brief)
    await session.flush()
    return brief


__all__ = [
    "BRIEF_METHOD",
    "KnowledgeBriefError",
    "derive_knowledge_brief",
    "materialize_knowledge_brief",
    "rebuild_knowledge_brief_snapshot",
    "verify_knowledge_brief",
]
