"""Deterministic read-only Opportunity Planner v2 for Question Map clusters."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.research.keyword_plan.question_coverage import (
    QUESTION_COVERAGE_SCHEMA_VERSION,
    QuestionCoverageError,
    build_question_coverage,
)

OPPORTUNITY_PLANNER_SCHEMA_VERSION = 1
OPPORTUNITY_PLANNER_POLICY_VERSION = "qm-opportunity-planner-v2.1"

PlannerDecision = Literal[
    "CREATE",
    "UPDATE",
    "REFRESH",
    "MERGE",
    "LINK_ONLY",
    "DO_NOT_WRITE",
]
PlannerPriority = Literal["NOW", "NEXT", "LATER", "NO"]
SelectionReadiness = Literal[
    "READY_FOR_HUMAN_SELECTION",
    "RESEARCH_REQUIRED",
    "REUSE_EXISTING_PLAN",
    "BLOCKED",
]


class OpportunityPlannerError(ValueError):
    """Fail-closed planner error with a stable code."""

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
        raise OpportunityPlannerError(code)
    return value


def _required_list(value: object, code: str) -> list[object]:
    if not isinstance(value, list):
        raise OpportunityPlannerError(code)
    return value


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(
        {
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        }
    )


def _need_evidence_readiness(need: NeedHypothesis) -> dict[str, object]:
    status = need.status
    if status == "SUPPORTED":
        readiness = "OPPORTUNITY_READY"
        reason = "canonical_need_supported"
    elif status == "REJECTED":
        readiness = "BLOCKED"
        reason = "canonical_need_rejected"
    else:
        readiness = "RESEARCH_REQUIRED"
        reason = f"canonical_need_status:{status}"

    return {
        "status": readiness,
        "canonical_need_status": status,
        "known_gaps": sorted(set(need.missing_evidence_json)),
        "reviewed_by": need.reviewed_by,
        "reviewed_at": (
            need.reviewed_at.isoformat()
            if need.reviewed_at is not None
            else None
        ),
        "reason_codes": [reason],
        "does_not_replace_locked_evidence_set": True,
        "does_not_authorize_drafting": True,
    }


def _audience_dimension(need: NeedHypothesis) -> dict[str, object]:
    if need.audience_hypothesis_id is not None:
        return {
            "status": "CANONICAL_AUDIENCE_BOUND",
            "audience_hypothesis_id": str(need.audience_hypothesis_id),
            "audience_scope": need.audience_scope,
        }
    return {
        "status": "SCOPE_ONLY",
        "audience_hypothesis_id": None,
        "audience_scope": need.audience_scope,
    }


def _problem_dimension(need: NeedHypothesis) -> dict[str, object]:
    return {
        "status": need.status,
        "need_type": need.type,
        "need_version": need.version,
        "statement": need.statement,
        "canonical_state_only": True,
    }


def _search_dimension(cluster: dict[str, object]) -> dict[str, object]:
    signal_refs = _strings(cluster.get("signal_refs"))
    question_count = cluster.get("question_count")
    if isinstance(question_count, bool) or not isinstance(question_count, int):
        raise OpportunityPlannerError(
            "opportunity_planner_cluster_projection_invalid"
        )
    if len(signal_refs) >= 2:
        status = "REPEATED"
    elif signal_refs:
        status = "SINGLE"
    else:
        status = "NONE"
    return {
        "status": status,
        "signal_count": len(signal_refs),
        "question_count": question_count,
        "signal_refs": signal_refs,
    }


def _business_path(answer_job: str) -> dict[str, object]:
    paths = {
        "verify_authenticity": "Relevant Artwork / Artist",
        "plan_budget": "Relevant Artwork / Artist",
        "understand_value": "Relevant Artwork / Artist",
        "choose_with_confidence": "Relevant Artwork / Artist",
        "choose_size": "Relevant Artwork",
        "fit_space": "Relevant Artwork",
        "find_place_to_view": "Visit / Artist / Artwork",
        "plan_transport": "Practical guidance / Artwork",
        "plan_shipping": "Practical guidance / Artwork",
        "carry_home": "Practical guidance / Artwork",
        "understand_customs": "Practical guidance / Artwork",
        "care_for_art": "Related Journal / Artwork",
        "understand_context": "Related Journal / Artist / Visit",
        "negotiate_purchase": "Practical guidance / Artwork",
    }
    return {
        "status": "DERIVED_UNBOUND",
        "suggested_path": paths.get(
            answer_job,
            "Related Journal / Artist / Artwork",
        ),
        "canonical_entity_refs": [],
        "rule_based_only": True,
    }


def _right_to_win(
    supporting_motgu_signals: list[Signal],
    *,
    locale: str,
) -> dict[str, object]:
    normalized_locale = locale.strip().casefold()
    relevant = [
        signal
        for signal in supporting_motgu_signals
        if signal.locale.strip().casefold() == normalized_locale
    ]
    refs = sorted(str(signal.id) for signal in relevant)
    scopes: dict[str, int] = defaultdict(int)
    independence: set[str] = set()
    for signal in relevant:
        scopes[signal.scope] += 1
        independence.add(signal.independence_group or signal.fingerprint)

    status = "UNPROVEN_FIRST_PARTY_SIGNAL" if refs else "GAP"
    return {
        "status": status,
        "right_to_win_proven": False,
        "planning_signal_available": bool(refs),
        "signal_refs": refs,
        "signal_count": len(refs),
        "independent_signal_count": len(independence),
        "scopes": dict(sorted(scopes.items())),
        "locale": normalized_locale,
        "basis": "linked_supporting_MOTGU_signals_only",
        "limitations": [
            "First-party signals support planning relevance only.",
            "They do not prove a MOTGU Right-to-Win.",
            "They are not a locked EvidenceSet.",
            "They are not an approved OriginalityPack.",
        ],
    }


def _coverage_payload(cluster: dict[str, object]) -> dict[str, object]:
    coverage = _required_dict(
        cluster.get("coverage"),
        "opportunity_planner_coverage_projection_invalid",
    )
    status = coverage.get("status")
    allowed = {
        "ANSWERED",
        "PARTIAL",
        "MISSING",
        "STALE",
        "COLLISION",
        "INSUFFICIENT_DATA",
    }
    if not isinstance(status, str) or status not in allowed:
        raise OpportunityPlannerError(
            "opportunity_planner_coverage_status_invalid"
        )
    return coverage


def _content_refs(
    coverage: dict[str, object],
    *,
    primary_only: bool,
) -> list[str]:
    rows = _required_list(
        coverage.get("matched_content_items"),
        "opportunity_planner_coverage_projection_invalid",
    )
    refs: list[str] = []
    for raw in rows:
        row = _required_dict(
            raw,
            "opportunity_planner_coverage_projection_invalid",
        )
        if primary_only and row.get("need_role") != "primary":
            continue
        item_id = row.get("id")
        if isinstance(item_id, str) and item_id.strip():
            refs.append(item_id.strip())
    return sorted(set(refs))


def _plan_refs(coverage: dict[str, object]) -> list[str]:
    rows = _required_list(
        coverage.get("matched_selected_opportunities"),
        "opportunity_planner_coverage_projection_invalid",
    )
    refs: list[str] = []
    for raw in rows:
        row = _required_dict(
            raw,
            "opportunity_planner_coverage_projection_invalid",
        )
        opportunity_id = row.get("id")
        if isinstance(opportunity_id, str) and opportunity_id.strip():
            refs.append(opportunity_id.strip())
    return sorted(set(refs))


def _do_not_write_refs(coverage: dict[str, object]) -> list[str]:
    return _strings(coverage.get("do_not_write_opportunity_refs"))


def _decision_for_cluster(
    *,
    coverage: dict[str, object],
    need: NeedHypothesis,
    has_right_to_win: bool,
) -> tuple[
    PlannerDecision,
    list[str],
    list[str],
    list[str],
]:
    status = str(coverage["status"])
    content_refs = _content_refs(coverage, primary_only=True)
    plan_refs = _plan_refs(coverage)
    do_not_write_refs = _do_not_write_refs(coverage)

    if do_not_write_refs:
        return (
            "DO_NOT_WRITE",
            [],
            sorted(set(plan_refs + do_not_write_refs)),
            ["selected_do_not_write_plan_exists"],
        )

    if need.status == "REJECTED":
        return (
            "DO_NOT_WRITE",
            [],
            plan_refs,
            ["canonical_need_rejected"],
        )

    if status == "MISSING":
        return "CREATE", [], plan_refs, ["coverage_missing"]

    if status == "STALE":
        if not content_refs:
            raise OpportunityPlannerError(
                "opportunity_planner_stale_target_missing"
            )
        return (
            "REFRESH",
            content_refs,
            plan_refs,
            ["matching_content_stale"],
        )

    if status == "ANSWERED":
        if not content_refs:
            raise OpportunityPlannerError(
                "opportunity_planner_answered_target_missing"
            )
        if has_right_to_win:
            return (
                "UPDATE",
                content_refs,
                plan_refs,
                ["answered_but_first_party_value_available"],
            )
        return (
            "LINK_ONLY",
            content_refs,
            plan_refs,
            ["answered_without_new_first_party_value"],
        )

    if status == "PARTIAL":
        if content_refs:
            return (
                "UPDATE",
                content_refs,
                plan_refs,
                ["matching_content_incomplete"],
            )
        return (
            "CREATE",
            [],
            plan_refs,
            ["matching_create_plan_or_work_exists"],
        )

    if status == "COLLISION":
        if len(content_refs) >= 2:
            return (
                "MERGE",
                content_refs,
                plan_refs,
                ["multiple_matching_content_items"],
            )
        return (
            "CREATE",
            [],
            plan_refs,
            ["duplicate_plan_collision_requires_reconciliation"],
        )

    if status == "INSUFFICIENT_DATA":
        return (
            "DO_NOT_WRITE",
            [],
            plan_refs,
            ["coverage_semantics_insufficient"],
        )

    raise OpportunityPlannerError(
        "opportunity_planner_coverage_status_invalid"
    )


def _selection_readiness(
    *,
    coverage_status: str,
    need_status: str,
    decision: PlannerDecision,
    decision_reasons: list[str],
) -> tuple[SelectionReadiness, list[str]]:
    if need_status == "REJECTED":
        return "BLOCKED", ["canonical_need_rejected"]
    if coverage_status == "INSUFFICIENT_DATA":
        return "RESEARCH_REQUIRED", ["coverage_semantics_insufficient"]
    if "duplicate_plan_collision_requires_reconciliation" in decision_reasons:
        return "BLOCKED", ["duplicate_selected_plans_require_reconciliation"]
    if "matching_create_plan_or_work_exists" in decision_reasons:
        return "REUSE_EXISTING_PLAN", ["reuse_existing_selected_plan"]
    if decision == "DO_NOT_WRITE":
        return "BLOCKED", ["decision_is_do_not_write"]
    if need_status != "SUPPORTED":
        return (
            "RESEARCH_REQUIRED",
            [f"canonical_need_status:{need_status}"],
        )
    return "READY_FOR_HUMAN_SELECTION", []


def _priority(
    *,
    decision: PlannerDecision,
    coverage_status: str,
    need_status: str,
    search_signal_count: int,
    has_right_to_win: bool,
    selection_readiness: SelectionReadiness,
) -> tuple[PlannerPriority, list[str]]:
    reasons: list[str] = []
    if decision == "DO_NOT_WRITE":
        return "NO", ["decision_is_do_not_write"]
    if selection_readiness == "BLOCKED":
        return "NO", ["selection_readiness_blocked"]
    if need_status != "SUPPORTED":
        reasons.append("need_requires_more_research")
        return "LATER", reasons
    if decision in {"REFRESH", "UPDATE", "MERGE", "LINK_ONLY"}:
        reasons.append(f"existing_content_action:{decision}")
        return "NEXT", reasons
    if coverage_status == "PARTIAL":
        reasons.append("existing_plan_or_work_should_be_reused")
        return "NEXT", reasons
    if search_signal_count >= 2:
        reasons.append("repeated_search_signal")
    elif search_signal_count == 1:
        reasons.append("single_search_signal")
    else:
        reasons.append("no_search_signal")
    reasons.append(
        "first_party_right_to_win_signal_available"
        if has_right_to_win
        else "right_to_win_gap"
    )
    if search_signal_count >= 2 and has_right_to_win:
        return "NOW", reasons
    if search_signal_count >= 2 or has_right_to_win:
        return "NEXT", reasons
    return "LATER", reasons


def _recommendation(
    *,
    cluster: dict[str, object],
    need: NeedHypothesis,
    right_to_win: dict[str, object],
    evidence_readiness: dict[str, object],
) -> dict[str, object]:
    coverage = _coverage_payload(cluster)
    coverage_status = str(coverage["status"])
    has_right_to_win = right_to_win.get("right_to_win_proven") is True
    decision, target_refs, plan_refs, decision_reasons = _decision_for_cluster(
        coverage=coverage,
        need=need,
        has_right_to_win=has_right_to_win,
    )
    readiness, readiness_reasons = _selection_readiness(
        coverage_status=coverage_status,
        need_status=need.status,
        decision=decision,
        decision_reasons=decision_reasons,
    )
    search_dimension = _search_dimension(cluster)
    signal_count = search_dimension.get("signal_count")
    if isinstance(signal_count, bool) or not isinstance(signal_count, int):
        raise OpportunityPlannerError(
            "opportunity_planner_search_projection_invalid"
        )
    priority, priority_reasons = _priority(
        decision=decision,
        coverage_status=coverage_status,
        need_status=need.status,
        search_signal_count=signal_count,
        has_right_to_win=has_right_to_win,
        selection_readiness=readiness,
    )
    answer_job = cluster.get("answer_job")
    if not isinstance(answer_job, str) or not answer_job:
        raise OpportunityPlannerError(
            "opportunity_planner_cluster_projection_invalid"
        )

    return {
        "cluster_key": cluster.get("cluster_key"),
        "intent": cluster.get("intent"),
        "answer_job": answer_job,
        "primary_question": cluster.get("primary_question"),
        "decision": decision,
        "priority": priority,
        "selection_readiness": readiness,
        "existing_content_refs": target_refs,
        "existing_plan_refs": plan_refs,
        "reason_codes": sorted(
            set(
                decision_reasons
                + readiness_reasons
                + priority_reasons
            )
        ),
        "dimensions": {
            "audience_fit": _audience_dimension(need),
            "problem_strength": _problem_dimension(need),
            "search_evidence": search_dimension,
            "content_gap": {
                "status": coverage_status,
                "reason_codes": _strings(coverage.get("reason_codes")),
            },
            "motgu_right_to_win": right_to_win,
            "business_connection": _business_path(answer_job),
            "evidence_readiness": evidence_readiness,
        },
        "coverage_refs": {
            "target_primary_content_items": target_refs,
            "all_matched_content_items": _content_refs(
                coverage,
                primary_only=False,
            ),
            "matched_selected_opportunities": plan_refs,
            "do_not_write_opportunities": _do_not_write_refs(coverage),
            "unresolved_candidates": coverage.get(
                "unresolved_candidates",
                [],
            ),
        },
    }


def plan_opportunity_projection(
    *,
    question_coverage: dict[str, object],
    need: NeedHypothesis,
    supporting_motgu_signals: list[Signal],
    support_refs: list[str],
    contradiction_refs: list[str],
) -> dict[str, object]:
    if (
        question_coverage.get("schema_version")
        != QUESTION_COVERAGE_SCHEMA_VERSION
    ):
        raise OpportunityPlannerError(
            "opportunity_planner_question_coverage_schema_unsupported"
        )

    coverage_project = _required_dict(
        question_coverage.get("project"),
        "opportunity_planner_project_projection_invalid",
    )
    if str(coverage_project.get("id", "")) != str(need.project_id):
        raise OpportunityPlannerError(
            "opportunity_planner_project_mismatch"
        )

    coverage_need = _required_dict(
        question_coverage.get("need"),
        "opportunity_planner_need_projection_invalid",
    )
    if str(coverage_need.get("id", "")) != str(need.id):
        raise OpportunityPlannerError("opportunity_planner_need_mismatch")

    coverage_hash = question_coverage.get("snapshot_hash")
    if not isinstance(coverage_hash, str) or len(coverage_hash) != 64:
        raise OpportunityPlannerError(
            "opportunity_planner_question_coverage_hash_invalid"
        )

    locale = str(question_coverage.get("locale", "")).strip().casefold()
    if not locale:
        raise OpportunityPlannerError(
            "opportunity_planner_locale_invalid"
        )

    right_to_win = _right_to_win(
        supporting_motgu_signals,
        locale=locale,
    )
    evidence_readiness = _need_evidence_readiness(need)
    raw_clusters = _required_list(
        question_coverage.get("clusters"),
        "opportunity_planner_cluster_projection_invalid",
    )
    clusters = [
        _required_dict(
            raw,
            "opportunity_planner_cluster_projection_invalid",
        )
        for raw in raw_clusters
    ]
    recommendations = [
        _recommendation(
            cluster=cluster,
            need=need,
            right_to_win=right_to_win,
            evidence_readiness=evidence_readiness,
        )
        for cluster in clusters
    ]

    priority_order = {"NOW": 0, "NEXT": 1, "LATER": 2, "NO": 3}
    decision_order = {
        "REFRESH": 0,
        "UPDATE": 1,
        "MERGE": 2,
        "CREATE": 3,
        "LINK_ONLY": 4,
        "DO_NOT_WRITE": 5,
    }
    recommendations.sort(
        key=lambda row: (
            priority_order[str(row["priority"])],
            decision_order[str(row["decision"])],
            str(row.get("cluster_key", "")),
        )
    )

    counts = {
        decision: sum(
            1 for row in recommendations if row["decision"] == decision
        )
        for decision in (
            "CREATE",
            "UPDATE",
            "REFRESH",
            "MERGE",
            "LINK_ONLY",
            "DO_NOT_WRITE",
        )
    }

    snapshot: dict[str, object] = {
        "schema_version": OPPORTUNITY_PLANNER_SCHEMA_VERSION,
        "policy_version": OPPORTUNITY_PLANNER_POLICY_VERSION,
        "project": coverage_project,
        "need": {
            "id": str(need.id),
            "version": need.version,
            "status": need.status,
            "type": need.type,
            "statement": need.statement,
            "audience_hypothesis_id": (
                str(need.audience_hypothesis_id)
                if need.audience_hypothesis_id is not None
                else None
            ),
        },
        "locale": locale,
        "question_coverage_snapshot_hash": coverage_hash,
        "need_signal_state": {
            "support_signal_refs": sorted(set(support_refs)),
            "contradiction_signal_refs": sorted(
                set(contradiction_refs)
            ),
        },
        "right_to_win": right_to_win,
        "evidence_readiness": evidence_readiness,
        "counts": counts,
        "recommendations": recommendations,
        "semantics": {
            "read_only": True,
            "no_synthetic_score": True,
            "human_selection_required": True,
            "does_not_create_content_opportunity": True,
            "does_not_authorize_drafting": True,
            "locked_evidence_set_still_required_downstream": True,
            "approved_originality_pack_still_required_downstream": True,
        },
    }
    return {
        **snapshot,
        "snapshot_hash": _stable_hash(snapshot),
    }


async def build_opportunity_plan_v2(
    session: AsyncSession,
    *,
    project_id: UUID,
    need_id: UUID,
    locale: str,
) -> dict[str, object]:
    project = await session.get(Project, project_id)
    if project is None:
        raise OpportunityPlannerError(
            "opportunity_planner_project_not_found"
        )
    need = await session.get(NeedHypothesis, need_id)
    if need is None or need.project_id != project.id:
        raise OpportunityPlannerError(
            "opportunity_planner_need_not_found"
        )

    try:
        question_coverage = await build_question_coverage(
            session,
            project_id=project.id,
            need_id=need.id,
            locale=locale,
        )
    except QuestionCoverageError as exc:
        raise OpportunityPlannerError(exc.code) from exc

    rows = (
        await session.execute(
            select(NeedHypothesisSignal, Signal)
            .join(Signal, Signal.id == NeedHypothesisSignal.signal_id)
            .where(
                NeedHypothesisSignal.need_hypothesis_id == need.id,
                Signal.project_id == project.id,
            )
            .order_by(
                NeedHypothesisSignal.relation,
                Signal.id,
            )
        )
    ).all()

    supporting_motgu_signals: list[Signal] = []
    support_refs: list[str] = []
    contradiction_refs: list[str] = []
    for link, signal in rows:
        if link.relation == "supports":
            support_refs.append(str(signal.id))
            if signal.source_kind == "MOTGU":
                supporting_motgu_signals.append(signal)
        elif link.relation == "contradicts":
            contradiction_refs.append(str(signal.id))

    return plan_opportunity_projection(
        question_coverage=question_coverage,
        need=need,
        supporting_motgu_signals=supporting_motgu_signals,
        support_refs=support_refs,
        contradiction_refs=contradiction_refs,
    )


__all__ = [
    "OPPORTUNITY_PLANNER_POLICY_VERSION",
    "OPPORTUNITY_PLANNER_SCHEMA_VERSION",
    "OpportunityPlannerError",
    "PlannerDecision",
    "PlannerPriority",
    "SelectionReadiness",
    "build_opportunity_plan_v2",
    "plan_opportunity_projection",
]
