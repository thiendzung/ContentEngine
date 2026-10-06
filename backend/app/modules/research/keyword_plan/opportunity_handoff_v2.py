"""QM-02A explicit selection handoff from the read-only Opportunity Planner v2."""

from __future__ import annotations

import hashlib
import json
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    ContentOpportunitySignal,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    NeedHypothesisSignal,
    Signal,
    utc_now,
)
from app.modules.research.keyword_plan.opportunity_handoff_models import (
    OpportunityPlannerHandoff,
)
from app.modules.research.keyword_plan.opportunity_planner_v2 import (
    OpportunityPlannerError,
    build_opportunity_plan_v2,
)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
HANDOFF_SCHEMA_VERSION = 1


class OpportunityHandoffError(ValueError):
    """Fail-closed QM-02A mutation error with a stable code."""

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
        raise OpportunityHandoffError(code)
    return value


def _required_str(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OpportunityHandoffError(code)
    return value.strip()


def _required_string_list(value: object, code: str) -> list[str]:
    if not isinstance(value, list):
        raise OpportunityHandoffError(code)
    output: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise OpportunityHandoffError(code)
        output.append(item.strip())
    return output


def _validate_hash(value: str, code: str) -> str:
    normalized = value.strip().casefold()
    if not _HASH_RE.fullmatch(normalized):
        raise OpportunityHandoffError(code)
    return normalized


def _normalize_locale(value: str) -> str:
    locale = value.strip().casefold()
    if not locale:
        raise OpportunityHandoffError("opportunity_handoff_locale_invalid")
    return locale


def _request_hash(
    *,
    project_id: UUID,
    need_id: UUID,
    locale: str,
    cluster_key: str,
    expected_planner_snapshot_hash: str,
    selected_by: str,
    reason: str,
) -> str:
    return _stable_hash(
        {
            "project_id": str(project_id),
            "need_id": str(need_id),
            "locale": locale,
            "cluster_key": cluster_key,
            "expected_planner_snapshot_hash": expected_planner_snapshot_hash,
            "selected_by": selected_by,
            "reason": reason,
        }
    )


def _receipt(
    handoff: OpportunityPlannerHandoff,
    *,
    replayed: bool,
) -> dict[str, object]:
    return {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "handoff_id": str(handoff.id),
        "resolution": handoff.resolution,
        "replayed": replayed,
        "project_id": str(handoff.project_id),
        "need_hypothesis_id": str(handoff.need_hypothesis_id),
        "need_version": handoff.need_version,
        "locale": handoff.locale,
        "cluster_key": handoff.cluster_key,
        "planner_policy_version": handoff.planner_policy_version,
        "planner_snapshot_hash": handoff.planner_snapshot_hash,
        "question_coverage_snapshot_hash": (
            handoff.question_coverage_snapshot_hash
        ),
        "recommendation_hash": handoff.recommendation_hash,
        "content_opportunity_id": str(handoff.content_opportunity_id),
        "human_selection_id": (
            str(handoff.human_selection_id)
            if handoff.human_selection_id is not None
            else None
        ),
        "selected_by": handoff.selected_by,
        "selection_reason": handoff.selection_reason,
        "semantics": {
            "content_case_created": False,
            "content_run_created": False,
            "content_experiment_created": False,
            "drafting_authorized": False,
        },
    }


def _planner_recommendation(
    planner: dict[str, object],
    *,
    cluster_key: str,
) -> dict[str, object]:
    rows = planner.get("recommendations")
    if not isinstance(rows, list):
        raise OpportunityHandoffError(
            "opportunity_handoff_planner_projection_invalid"
        )
    matches = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("cluster_key") == cluster_key
    ]
    if len(matches) != 1:
        raise OpportunityHandoffError(
            "opportunity_handoff_cluster_not_found"
        )
    return matches[0]


def _selection_state(
    recommendation: dict[str, object],
) -> tuple[str, str]:
    readiness = _required_str(
        recommendation.get("selection_readiness"),
        "opportunity_handoff_readiness_invalid",
    )
    decision = _required_str(
        recommendation.get("decision"),
        "opportunity_handoff_decision_invalid",
    )
    if decision == "DO_NOT_WRITE":
        raise OpportunityHandoffError(
            "opportunity_handoff_do_not_write_not_selectable"
        )
    if readiness in {"BLOCKED", "RESEARCH_REQUIRED"}:
        raise OpportunityHandoffError(
            f"opportunity_handoff_{readiness.casefold()}"
        )
    if readiness not in {
        "READY_FOR_HUMAN_SELECTION",
        "REUSE_EXISTING_PLAN",
    }:
        raise OpportunityHandoffError(
            "opportunity_handoff_readiness_invalid"
        )
    return readiness, decision


async def _validate_search_signal_refs(
    session: AsyncSession,
    *,
    need: NeedHypothesis,
    locale: str,
    recommendation: dict[str, object],
) -> list[UUID]:
    dimensions = _required_dict(
        recommendation.get("dimensions"),
        "opportunity_handoff_dimensions_invalid",
    )
    search_evidence = _required_dict(
        dimensions.get("search_evidence"),
        "opportunity_handoff_search_evidence_invalid",
    )
    raw_refs = _required_string_list(
        search_evidence.get("signal_refs"),
        "opportunity_handoff_search_signal_refs_invalid",
    )
    signal_ids: list[UUID] = []
    for raw in raw_refs:
        try:
            signal_id = UUID(raw)
        except ValueError as exc:
            raise OpportunityHandoffError(
                "opportunity_handoff_search_signal_ref_invalid"
            ) from exc
        signal = await session.get(Signal, signal_id)
        link = await session.get(
            NeedHypothesisSignal,
            (need.id, signal_id, "supports"),
        )
        if (
            signal is None
            or signal.project_id != need.project_id
            or signal.source_kind != "SEARCH"
            or signal.locale.strip().casefold() != locale
            or link is None
        ):
            raise OpportunityHandoffError(
                "opportunity_handoff_search_signal_binding_invalid"
            )
        signal_ids.append(signal_id)
    return sorted(set(signal_ids), key=str)


async def _validate_primary_target_refs(
    session: AsyncSession,
    *,
    need: NeedHypothesis,
    locale: str,
    refs: list[str],
) -> None:
    for raw in refs:
        try:
            item_id = UUID(raw)
        except ValueError as exc:
            raise OpportunityHandoffError(
                "opportunity_handoff_existing_target_ref_invalid"
            ) from exc
        row = (
            await session.execute(
                select(ContentItem, ContentCase, LocaleVariant)
                .join(
                    ContentCase,
                    ContentCase.id == ContentItem.content_case_id,
                )
                .join(
                    LocaleVariant,
                    LocaleVariant.id == ContentItem.locale_variant_id,
                )
                .where(ContentItem.id == item_id)
            )
        ).one_or_none()
        if row is None:
            raise OpportunityHandoffError(
                "opportunity_handoff_existing_target_missing"
            )
        item, content_case, variant = row
        if (
            item.project_id != need.project_id
            or content_case.project_id != need.project_id
            or content_case.need_hypothesis_id != need.id
            or variant.locale.strip().casefold() != locale
        ):
            raise OpportunityHandoffError(
                "opportunity_handoff_existing_target_binding_invalid"
            )


def _primary_target_refs(
    recommendation: dict[str, object],
    *,
    decision: str,
) -> list[str]:
    refs = _required_string_list(
        recommendation.get("existing_content_refs"),
        "opportunity_handoff_content_refs_invalid",
    )
    if decision in {"UPDATE", "REFRESH", "MERGE", "LINK_ONLY"} and not refs:
        raise OpportunityHandoffError(
            "opportunity_handoff_existing_target_required"
        )
    if decision == "CREATE" and refs:
        raise OpportunityHandoffError(
            "opportunity_handoff_create_target_conflict"
        )
    return sorted(set(refs))


def _planner_material_gaps(need: NeedHypothesis) -> list[str]:
    return list(
        dict.fromkeys(
            [
                *need.missing_evidence_json,
                (
                    "QM-01D does not prove MOTGU Right-to-Win or approved "
                    "MOTGU-owned editorial material."
                ),
                (
                    "Founder/editorial coverage requirements are not supplied "
                    "by the Question Map selection handoff."
                ),
            ]
        )
    )


def _next_discovery_step(
    recommendation: dict[str, object],
    *,
    decision: str,
) -> str:
    if decision == "LINK_ONLY":
        return "Reuse/link the selected existing content; no new drafting is authorized."
    dimensions = _required_dict(
        recommendation.get("dimensions"),
        "opportunity_handoff_dimensions_invalid",
    )
    business = _required_dict(
        dimensions.get("business_connection"),
        "opportunity_handoff_business_connection_invalid",
    )
    suggested = business.get("suggested_path")
    if isinstance(suggested, str) and suggested.strip():
        return suggested.strip()
    return "Resolve evidence, originality and editorial coverage before drafting."


async def _exact_unselected_opportunity(
    session: AsyncSession,
    *,
    need: NeedHypothesis,
    locale: str,
    question: str,
    intent: str,
    decision: str,
    target_refs: list[str],
) -> ContentOpportunity | None:
    rows = tuple(
        (
            await session.execute(
                select(ContentOpportunity)
                .where(
                    ContentOpportunity.project_id == need.project_id,
                    ContentOpportunity.need_hypothesis_id == need.id,
                    ContentOpportunity.locale == locale,
                    ContentOpportunity.question == question,
                    ContentOpportunity.intent == intent,
                    ContentOpportunity.decision == decision,
                    ContentOpportunity.selected_by.is_(None),
                )
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    exact = [
        row
        for row in rows
        if sorted(set(row.existing_content_refs_json)) == target_refs
    ]
    if len(exact) > 1:
        raise OpportunityHandoffError(
            "opportunity_handoff_unselected_opportunity_ambiguous"
        )
    return exact[0] if exact else None


async def _select_new_opportunity(
    session: AsyncSession,
    *,
    need: NeedHypothesis,
    locale: str,
    recommendation: dict[str, object],
    decision: str,
    selected_by: str,
    reason: str,
) -> tuple[ContentOpportunity, HumanSelection]:
    question = _required_str(
        recommendation.get("primary_question"),
        "opportunity_handoff_question_invalid",
    )
    intent = _required_str(
        recommendation.get("intent"),
        "opportunity_handoff_intent_invalid",
    )
    priority = _required_str(
        recommendation.get("priority"),
        "opportunity_handoff_priority_invalid",
    )
    if priority not in {"NOW", "NEXT", "LATER", "NO"}:
        raise OpportunityHandoffError(
            "opportunity_handoff_priority_invalid"
        )
    answer_job = _required_str(
        recommendation.get("answer_job"),
        "opportunity_handoff_answer_job_invalid",
    )
    target_refs = _primary_target_refs(
        recommendation,
        decision=decision,
    )
    await _validate_primary_target_refs(
        session,
        need=need,
        locale=locale,
        refs=target_refs,
    )
    reason_codes = _required_string_list(
        recommendation.get("reason_codes"),
        "opportunity_handoff_reason_codes_invalid",
    )

    opportunity = await _exact_unselected_opportunity(
        session,
        need=need,
        locale=locale,
        question=question,
        intent=intent,
        decision=decision,
        target_refs=target_refs,
    )
    if opportunity is None:
        opportunity = ContentOpportunity(
            project_id=need.project_id,
            need_hypothesis_id=need.id,
            locale=locale,
            reader=need.audience_scope,
            situation=need.situation,
            need=need.statement,
            question=question,
            intent=intent,
            promise=f"Help the reader answer: {question}",
            coverage_requirements_json=[],
            motgu_material_refs_json=[],
            material_gaps_json=_planner_material_gaps(need),
            existing_content_refs_json=target_refs,
            what_is_actually_new=(
                "Not established by QM-01D; this selected handoff does not "
                "claim approved MOTGU-owned new value."
            ),
            next_discovery_step=_next_discovery_step(
                recommendation,
                decision=decision,
            ),
            decision=decision,
            priority=priority,
            reasons_json=list(
                dict.fromkeys(
                    [
                        *reason_codes,
                        f"question_map_answer_job:{answer_job}",
                        "qm02a_selected_from_planner_v2",
                    ]
                )
            ),
            suggested_content_type="journal",
            suggested_role="cluster",
            version=1,
        )
        session.add(opportunity)
        await session.flush()
    else:
        opportunity.reader = need.audience_scope
        opportunity.situation = need.situation
        opportunity.need = need.statement
        opportunity.promise = f"Help the reader answer: {question}"
        opportunity.coverage_requirements_json = []
        opportunity.motgu_material_refs_json = []
        opportunity.material_gaps_json = _planner_material_gaps(need)
        opportunity.existing_content_refs_json = target_refs
        opportunity.what_is_actually_new = (
            "Not established by QM-01D; this selected handoff does not "
            "claim approved MOTGU-owned new value."
        )
        opportunity.next_discovery_step = _next_discovery_step(
            recommendation,
            decision=decision,
        )
        opportunity.priority = priority
        opportunity.reasons_json = list(
            dict.fromkeys(
                [
                    *reason_codes,
                    f"question_map_answer_job:{answer_job}",
                    "qm02a_selected_from_planner_v2",
                ]
            )
        )
        opportunity.suggested_content_type = "journal"
        opportunity.suggested_role = "cluster"

    selected_at = utc_now()
    opportunity.selected_by = selected_by
    opportunity.selected_at = selected_at
    opportunity.selection_reason = reason
    selection = HumanSelection(
        content_opportunity_id=opportunity.id,
        selected_by=selected_by,
        reason=reason,
        selected_at=selected_at,
    )
    session.add(selection)
    await session.flush()
    return opportunity, selection


async def _reuse_existing_plan(
    session: AsyncSession,
    *,
    need: NeedHypothesis,
    locale: str,
    recommendation: dict[str, object],
) -> tuple[ContentOpportunity, HumanSelection]:
    refs = _required_string_list(
        recommendation.get("existing_plan_refs"),
        "opportunity_handoff_existing_plan_refs_invalid",
    )
    if len(refs) != 1:
        raise OpportunityHandoffError(
            "opportunity_handoff_existing_plan_not_unique"
        )
    try:
        opportunity_id = UUID(refs[0])
    except ValueError as exc:
        raise OpportunityHandoffError(
            "opportunity_handoff_existing_plan_ref_invalid"
        ) from exc

    opportunity = (
        await session.execute(
            select(ContentOpportunity)
            .where(ContentOpportunity.id == opportunity_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if (
        opportunity is None
        or opportunity.project_id != need.project_id
        or opportunity.need_hypothesis_id != need.id
        or opportunity.locale.strip().casefold() != locale
        or opportunity.selected_by is None
    ):
        raise OpportunityHandoffError(
            "opportunity_handoff_existing_plan_binding_invalid"
        )
    selections = tuple(
        (
            await session.execute(
                select(HumanSelection)
                .where(
                    HumanSelection.content_opportunity_id == opportunity.id
                )
                .order_by(
                    HumanSelection.selected_at.asc(),
                    HumanSelection.id.asc(),
                )
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    if len(selections) != 1:
        raise OpportunityHandoffError(
            "opportunity_handoff_existing_selection_not_unique"
        )
    return opportunity, selections[0]


async def _link_search_signals(
    session: AsyncSession,
    *,
    opportunity_id: UUID,
    signal_ids: list[UUID],
) -> None:
    for signal_id in signal_ids:
        existing = await session.get(
            ContentOpportunitySignal,
            (opportunity_id, signal_id),
        )
        if existing is None:
            session.add(
                ContentOpportunitySignal(
                    content_opportunity_id=opportunity_id,
                    signal_id=signal_id,
                )
            )
    await session.flush()


async def select_opportunity_plan_v2(
    session: AsyncSession,
    *,
    project_id: UUID,
    need_id: UUID,
    locale: str,
    cluster_key: str,
    expected_planner_snapshot_hash: str,
    idempotency_key: str,
    selected_by: str,
    reason: str,
) -> dict[str, object]:
    locale_normalized = _normalize_locale(locale)
    cluster = cluster_key.strip()
    key = idempotency_key.strip()
    actor = selected_by.strip()
    selection_reason = reason.strip()
    if not cluster:
        raise OpportunityHandoffError(
            "opportunity_handoff_cluster_key_invalid"
        )
    if not key or len(key) > 200:
        raise OpportunityHandoffError(
            "opportunity_handoff_idempotency_key_invalid"
        )
    if not actor or len(actor) > 200:
        raise OpportunityHandoffError(
            "opportunity_handoff_selected_by_invalid"
        )
    if not selection_reason:
        raise OpportunityHandoffError(
            "opportunity_handoff_selection_reason_required"
        )
    expected_hash = _validate_hash(
        expected_planner_snapshot_hash,
        "opportunity_handoff_planner_hash_invalid",
    )
    request_hash = _request_hash(
        project_id=project_id,
        need_id=need_id,
        locale=locale_normalized,
        cluster_key=cluster,
        expected_planner_snapshot_hash=expected_hash,
        selected_by=actor,
        reason=selection_reason,
    )

    need = (
        await session.execute(
            select(NeedHypothesis)
            .where(
                NeedHypothesis.id == need_id,
                NeedHypothesis.project_id == project_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if need is None:
        raise OpportunityHandoffError(
            "opportunity_handoff_need_not_found"
        )

    existing_by_key = (
        await session.execute(
            select(OpportunityPlannerHandoff)
            .where(OpportunityPlannerHandoff.idempotency_key == key)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing_by_key is not None:
        if existing_by_key.request_hash != request_hash:
            raise OpportunityHandoffError(
                "opportunity_handoff_idempotency_conflict"
            )
        return _receipt(existing_by_key, replayed=True)

    try:
        planner = await build_opportunity_plan_v2(
            session,
            project_id=project_id,
            need_id=need_id,
            locale=locale_normalized,
        )
    except OpportunityPlannerError as exc:
        raise OpportunityHandoffError(exc.code) from exc

    planner_hash = _validate_hash(
        _required_str(
            planner.get("snapshot_hash"),
            "opportunity_handoff_planner_projection_invalid",
        ),
        "opportunity_handoff_planner_projection_invalid",
    )
    if planner_hash != expected_hash:
        raise OpportunityHandoffError(
            "opportunity_handoff_planner_snapshot_stale"
        )

    recommendation = _planner_recommendation(
        planner,
        cluster_key=cluster,
    )
    readiness, decision = _selection_state(recommendation)
    recommendation_hash = _stable_hash(recommendation)
    policy_version = _required_str(
        planner.get("policy_version"),
        "opportunity_handoff_policy_version_invalid",
    )
    coverage_hash = _validate_hash(
        _required_str(
            planner.get("question_coverage_snapshot_hash"),
            "opportunity_handoff_coverage_hash_invalid",
        ),
        "opportunity_handoff_coverage_hash_invalid",
    )

    existing_exact = (
        await session.execute(
            select(OpportunityPlannerHandoff)
            .where(
                OpportunityPlannerHandoff.project_id == project_id,
                OpportunityPlannerHandoff.planner_snapshot_hash
                == planner_hash,
                OpportunityPlannerHandoff.cluster_key == cluster,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing_exact is not None:
        raise OpportunityHandoffError(
            "opportunity_handoff_cluster_already_selected"
        )

    signal_ids = await _validate_search_signal_refs(
        session,
        need=need,
        locale=locale_normalized,
        recommendation=recommendation,
    )

    if readiness == "REUSE_EXISTING_PLAN":
        opportunity, selection = await _reuse_existing_plan(
            session,
            need=need,
            locale=locale_normalized,
            recommendation=recommendation,
        )
        resolution = "REUSED"
    else:
        opportunity, selection = await _select_new_opportunity(
            session,
            need=need,
            locale=locale_normalized,
            recommendation=recommendation,
            decision=decision,
            selected_by=actor,
            reason=selection_reason,
        )
        await _link_search_signals(
            session,
            opportunity_id=opportunity.id,
            signal_ids=signal_ids,
        )
        resolution = "SELECTED"

    handoff = OpportunityPlannerHandoff(
        project_id=project_id,
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        human_selection_id=selection.id,
        locale=locale_normalized,
        cluster_key=cluster,
        planner_policy_version=policy_version,
        planner_snapshot_hash=planner_hash,
        question_coverage_snapshot_hash=coverage_hash,
        recommendation_hash=recommendation_hash,
        need_version=need.version,
        idempotency_key=key,
        request_hash=request_hash,
        resolution=resolution,
        selected_by=actor,
        selection_reason=selection_reason,
    )
    session.add(handoff)
    await session.flush()
    return _receipt(handoff, replayed=False)


__all__ = [
    "HANDOFF_SCHEMA_VERSION",
    "OpportunityHandoffError",
    "select_opportunity_plan_v2",
]
