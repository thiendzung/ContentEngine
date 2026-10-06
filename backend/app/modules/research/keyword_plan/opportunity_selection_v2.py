"""QM-02A: persist one exact planner recommendation after explicit human selection."""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    ContentItem,
    ContentOpportunity,
    ContentOpportunitySignal,
    HumanSelection,
    NeedHypothesis,
    NeedHypothesisSignal,
    Signal,
    utc_now,
)
from app.modules.research.keyword_plan.opportunity_planner_v2 import (
    OPPORTUNITY_PLANNER_POLICY_VERSION,
    OpportunityPlannerError,
    build_opportunity_plan_v2,
)

OPPORTUNITY_SELECTION_SCHEMA_VERSION = 1
_MATERIAL_GAP = (
    "Approved MOTGU-owned material is required before drafting; "
    "planner relevance signals are not originality proof."
)
_NOT_NEW_YET = (
    "Not established at selection; Signal-only planning data does not prove "
    "a distinct MOTGU Right-to-Win."
)
_NEXT_STEP = (
    "Prepare locked EvidenceSet and approved OriginalityPack before Lens/Angle work."
)


class OpportunitySelectionError(ValueError):
    """Fail-closed QM-02A error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OpportunitySelectionRequest(BaseModel):
    project_slug: str = Field(default="motgu", min_length=1, max_length=100)
    need_id: UUID
    locale: str = Field(min_length=1, max_length=32)
    cluster_key: str = Field(min_length=1, max_length=128)
    expected_planner_snapshot_hash: str = Field(min_length=64, max_length=64)
    selected_by: str = Field(default="founder", min_length=1, max_length=200)
    selection_reason: str = Field(min_length=1, max_length=2_000)
    promise: str = Field(min_length=1, max_length=2_000)
    coverage_requirements: list[str] = Field(min_length=1, max_length=12)


class OpportunitySelectionResult(BaseModel):
    schema_version: int
    content_opportunity_id: UUID
    human_selection_id: UUID
    planner_snapshot_hash: str
    cluster_key: str
    decision: str
    priority: str
    replayed: bool


def _text(value: object, code: str, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise OpportunitySelectionError(code)
    normalized = value.strip()
    if not normalized:
        raise OpportunitySelectionError(code)
    if len(normalized) > max_length:
        raise OpportunitySelectionError(f"{code}_too_long")
    return normalized


def _coverage_requirements(values: list[str]) -> list[str]:
    if not values or len(values) > 12:
        raise OpportunitySelectionError(
            "opportunity_selection_coverage_requirements_invalid"
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _text(
            value,
            "opportunity_selection_coverage_requirement_required",
            max_length=500,
        )
        key = item.casefold()
        if key in seen:
            raise OpportunitySelectionError(
                "opportunity_selection_coverage_requirement_duplicate"
            )
        seen.add(key)
        normalized.append(item)
    return normalized


def _required_dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise OpportunitySelectionError(code)
    return value


def _required_list(value: object, code: str) -> list[object]:
    if not isinstance(value, list):
        raise OpportunitySelectionError(code)
    return value


def _string_list(value: object, code: str) -> list[str]:
    rows = _required_list(value, code)
    result: list[str] = []
    for raw in rows:
        if not isinstance(raw, str) or not raw.strip():
            raise OpportunitySelectionError(code)
        result.append(raw.strip())
    if len(result) != len(set(result)):
        raise OpportunitySelectionError(code)
    return result


def _hash64(value: object, code: str) -> str:
    text = _text(value, code, max_length=64)
    if len(text) != 64:
        raise OpportunitySelectionError(code)
    try:
        int(text, 16)
    except ValueError as exc:
        raise OpportunitySelectionError(code) from exc
    return text.lower()


def _opportunity_payload_hash(row: ContentOpportunity) -> str:
    payload = {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "need_hypothesis_id": str(row.need_hypothesis_id),
        "locale": row.locale,
        "reader": row.reader,
        "situation": row.situation,
        "need": row.need,
        "question": row.question,
        "intent": row.intent,
        "promise": row.promise,
        "coverage_requirements": list(row.coverage_requirements_json),
        "motgu_material_refs": list(row.motgu_material_refs_json),
        "material_gaps": list(row.material_gaps_json),
        "existing_content_refs": list(row.existing_content_refs_json),
        "what_is_actually_new": row.what_is_actually_new,
        "next_discovery_step": row.next_discovery_step,
        "decision": row.decision,
        "priority": row.priority,
        "suggested_content_type": row.suggested_content_type,
        "suggested_role": row.suggested_role,
        "version": row.version,
        "selected_by": row.selected_by,
        "selection_reason": row.selection_reason,
    }
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _stable_id(kind: str, *, planner_hash: str, cluster_key: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"https://contentengine.motgu/qm02a/{kind}/{planner_hash}/{cluster_key}",
    )


def _recommendation(
    planner: dict[str, object],
    *,
    cluster_key: str,
) -> dict[str, object]:
    rows = _required_list(
        planner.get("recommendations"),
        "opportunity_selection_planner_projection_invalid",
    )
    matches: list[dict[str, object]] = []
    for raw in rows:
        row = _required_dict(
            raw,
            "opportunity_selection_planner_projection_invalid",
        )
        if row.get("cluster_key") == cluster_key:
            matches.append(row)
    if not matches:
        raise OpportunitySelectionError(
            "opportunity_selection_cluster_not_found"
        )
    if len(matches) != 1:
        raise OpportunitySelectionError(
            "opportunity_selection_cluster_ambiguous"
        )
    return matches[0]


def _signal_refs(recommendation: dict[str, object]) -> list[UUID]:
    dimensions = _required_dict(
        recommendation.get("dimensions"),
        "opportunity_selection_planner_projection_invalid",
    )
    search = _required_dict(
        dimensions.get("search_evidence"),
        "opportunity_selection_planner_projection_invalid",
    )
    refs = _string_list(
        search.get("signal_refs"),
        "opportunity_selection_signal_refs_invalid",
    )
    try:
        return sorted((UUID(value) for value in refs), key=str)
    except ValueError as exc:
        raise OpportunitySelectionError(
            "opportunity_selection_signal_refs_invalid"
        ) from exc


def _content_refs(recommendation: dict[str, object]) -> list[UUID]:
    refs = _string_list(
        recommendation.get("existing_content_refs"),
        "opportunity_selection_content_refs_invalid",
    )
    try:
        return sorted((UUID(value) for value in refs), key=str)
    except ValueError as exc:
        raise OpportunitySelectionError(
            "opportunity_selection_content_refs_invalid"
        ) from exc


async def _validate_signal_refs(
    session: AsyncSession,
    *,
    project_id: UUID,
    need_id: UUID,
    locale: str,
    signal_ids: list[UUID],
) -> None:
    if not signal_ids:
        return
    rows = (
        await session.execute(
            select(Signal)
            .join(
                NeedHypothesisSignal,
                NeedHypothesisSignal.signal_id == Signal.id,
            )
            .where(
                Signal.id.in_(signal_ids),
                Signal.project_id == project_id,
                Signal.source_kind == "SEARCH",
                NeedHypothesisSignal.need_hypothesis_id == need_id,
                NeedHypothesisSignal.relation == "supports",
            )
        )
    ).scalars().all()
    found = {row.id for row in rows}
    if found != set(signal_ids):
        raise OpportunitySelectionError(
            "opportunity_selection_signal_lineage_invalid"
        )
    if any(row.locale.strip().casefold() != locale for row in rows):
        raise OpportunitySelectionError(
            "opportunity_selection_signal_locale_mismatch"
        )


async def _validate_content_refs(
    session: AsyncSession,
    *,
    project_id: UUID,
    content_ids: list[UUID],
) -> None:
    if not content_ids:
        return
    found = set(
        (
            await session.scalars(
                select(ContentItem.id).where(
                    ContentItem.id.in_(content_ids),
                    ContentItem.project_id == project_id,
                )
            )
        ).all()
    )
    if found != set(content_ids):
        raise OpportunitySelectionError(
            "opportunity_selection_content_target_invalid"
        )


def _lineage_reasons(
    recommendation: dict[str, object],
    *,
    planner_hash: str,
    cluster_key: str,
    question_coverage_hash: str,
) -> list[str]:
    reasons = _string_list(
        recommendation.get("reason_codes"),
        "opportunity_selection_reason_codes_invalid",
    )
    return sorted(
        set(
            reasons
            + [
                "qm02a_exact_planner_selection",
                f"planner_snapshot:{planner_hash}",
                f"planner_policy:{OPPORTUNITY_PLANNER_POLICY_VERSION}",
                f"planner_cluster:{cluster_key}",
                f"question_coverage_snapshot:{question_coverage_hash}",
            ]
        )
    )


def _assert_existing_replay(
    row: ContentOpportunity,
    *,
    need_id: UUID,
    project_id: UUID,
    locale: str,
    planner_hash: str,
    cluster_key: str,
    promise: str,
    coverage: list[str],
    reason: str,
    selected_by: str,
) -> None:
    expected = {
        "project_id": project_id,
        "need_hypothesis_id": need_id,
        "locale": locale,
        "promise": promise,
        "coverage_requirements_json": coverage,
        "selected_by": selected_by,
        "selection_reason": reason,
    }
    for field, expected_value in expected.items():
        if getattr(row, field) != expected_value:
            raise OpportunitySelectionError(
                "opportunity_selection_replay_conflict"
            )
    if row.selected_at is None:
        raise OpportunitySelectionError(
            "opportunity_selection_replay_conflict"
        )

    reasons = row.reasons_json
    if not isinstance(reasons, list) or any(
        not isinstance(item, str) for item in reasons
    ):
        raise OpportunitySelectionError(
            "opportunity_selection_replay_conflict"
        )
    reason_set = set(reasons)
    required_lineage = {
        "qm02a_exact_planner_selection",
        "selection_contract:qm02a-v1",
        f"planner_snapshot:{planner_hash}",
        f"planner_cluster:{cluster_key}",
    }
    if not required_lineage.issubset(reason_set):
        raise OpportunitySelectionError(
            "opportunity_selection_replay_conflict"
        )
    if not any(item.startswith("planner_policy:") for item in reason_set):
        raise OpportunitySelectionError(
            "opportunity_selection_replay_conflict"
        )
    if not any(
        item.startswith("question_coverage_snapshot:")
        for item in reason_set
    ):
        raise OpportunitySelectionError(
            "opportunity_selection_replay_conflict"
        )

    payload_markers = [
        item.removeprefix("selection_payload:")
        for item in reasons
        if item.startswith("selection_payload:")
    ]
    if payload_markers != [_opportunity_payload_hash(row)]:
        raise OpportunitySelectionError(
            "opportunity_selection_replay_conflict"
        )


async def _validate_existing_signal_lineage(
    session: AsyncSession,
    *,
    opportunity_id: UUID,
    project_id: UUID,
    need_id: UUID,
    locale: str,
) -> None:
    rows = (
        await session.execute(
            select(Signal)
            .join(
                ContentOpportunitySignal,
                ContentOpportunitySignal.signal_id == Signal.id,
            )
            .join(
                NeedHypothesisSignal,
                NeedHypothesisSignal.signal_id == Signal.id,
            )
            .where(
                ContentOpportunitySignal.content_opportunity_id
                == opportunity_id,
                NeedHypothesisSignal.need_hypothesis_id == need_id,
                NeedHypothesisSignal.relation == "supports",
            )
        )
    ).scalars().all()
    linked_ids = set(
        (
            await session.scalars(
                select(ContentOpportunitySignal.signal_id).where(
                    ContentOpportunitySignal.content_opportunity_id
                    == opportunity_id
                )
            )
        ).all()
    )
    valid_ids = {
        row.id
        for row in rows
        if row.project_id == project_id
        and row.source_kind == "SEARCH"
        and row.locale.strip().casefold() == locale
    }
    if linked_ids != valid_ids:
        raise OpportunitySelectionError(
            "opportunity_selection_signal_lineage_conflict"
        )


async def persist_selected_opportunity(
    session: AsyncSession,
    *,
    project_id: UUID,
    request: OpportunitySelectionRequest,
) -> OpportunitySelectionResult:
    """Persist exactly one current planner recommendation after explicit selection."""

    locale = _text(
        request.locale,
        "opportunity_selection_locale_invalid",
        max_length=32,
    ).casefold()
    cluster_key = _text(
        request.cluster_key,
        "opportunity_selection_cluster_key_invalid",
        max_length=128,
    )
    planner_hash = _hash64(
        request.expected_planner_snapshot_hash,
        "opportunity_selection_snapshot_hash_invalid",
    )
    selected_by = _text(
        request.selected_by,
        "opportunity_selection_actor_required",
        max_length=200,
    )
    reason = _text(
        request.selection_reason,
        "opportunity_selection_reason_required",
        max_length=2_000,
    )
    promise = _text(
        request.promise,
        "opportunity_selection_promise_required",
        max_length=2_000,
    )
    coverage = _coverage_requirements(request.coverage_requirements)

    need = await session.scalar(
        select(NeedHypothesis)
        .where(
            NeedHypothesis.id == request.need_id,
            NeedHypothesis.project_id == project_id,
        )
        .with_for_update()
    )
    if need is None:
        raise OpportunitySelectionError(
            "opportunity_selection_need_not_found"
        )

    opportunity_id = _stable_id(
        "content-opportunity",
        planner_hash=planner_hash,
        cluster_key=cluster_key,
    )
    selection_id = _stable_id(
        "human-selection",
        planner_hash=planner_hash,
        cluster_key=cluster_key,
    )

    existing = await session.get(ContentOpportunity, opportunity_id)
    if existing is not None:
        _assert_existing_replay(
            existing,
            need_id=need.id,
            project_id=project_id,
            locale=locale,
            planner_hash=planner_hash,
            cluster_key=cluster_key,
            promise=promise,
            coverage=coverage,
            reason=reason,
            selected_by=selected_by,
        )
        selections = list(
            (
                await session.scalars(
                    select(HumanSelection)
                    .where(
                        HumanSelection.content_opportunity_id == opportunity_id
                    )
                    .order_by(HumanSelection.id)
                )
            ).all()
        )
        if len(selections) != 1:
            raise OpportunitySelectionError(
                "opportunity_selection_durable_selection_inconsistent"
            )
        selection = selections[0]
        if (
            selection.id != selection_id
            or selection.selected_by != selected_by
            or selection.reason != reason
            or selection.selected_at != existing.selected_at
        ):
            raise OpportunitySelectionError(
                "opportunity_selection_replay_conflict"
            )
        await _validate_existing_signal_lineage(
            session,
            opportunity_id=opportunity_id,
            project_id=project_id,
            need_id=need.id,
            locale=locale,
        )
        return OpportunitySelectionResult(
            schema_version=OPPORTUNITY_SELECTION_SCHEMA_VERSION,
            content_opportunity_id=existing.id,
            human_selection_id=selection.id,
            planner_snapshot_hash=planner_hash,
            cluster_key=cluster_key,
            decision=existing.decision,
            priority=existing.priority,
            replayed=True,
        )

    try:
        planner = await build_opportunity_plan_v2(
            session,
            project_id=project_id,
            need_id=need.id,
            locale=locale,
        )
    except OpportunityPlannerError as exc:
        raise OpportunitySelectionError(exc.code) from exc

    current_hash = planner.get("snapshot_hash")
    if current_hash != planner_hash:
        raise OpportunitySelectionError(
            "opportunity_selection_stale_planner_snapshot"
        )
    if planner.get("policy_version") != OPPORTUNITY_PLANNER_POLICY_VERSION:
        raise OpportunitySelectionError(
            "opportunity_selection_planner_policy_mismatch"
        )

    recommendation = _recommendation(planner, cluster_key=cluster_key)
    if recommendation.get("selection_readiness") != "READY_FOR_HUMAN_SELECTION":
        raise OpportunitySelectionError(
            "opportunity_selection_not_ready"
        )

    decision = _text(
        recommendation.get("decision"),
        "opportunity_selection_decision_invalid",
        max_length=32,
    )
    priority = _text(
        recommendation.get("priority"),
        "opportunity_selection_priority_invalid",
        max_length=16,
    )
    if decision == "DO_NOT_WRITE":
        raise OpportunitySelectionError(
            "opportunity_selection_not_ready"
        )

    content_refs = _content_refs(recommendation)
    decisions_requiring_target = {"UPDATE", "REFRESH", "MERGE", "LINK_ONLY"}
    if decision in decisions_requiring_target and not content_refs:
        raise OpportunitySelectionError(
            "opportunity_selection_content_target_required"
        )
    if decision == "CREATE" and content_refs:
        raise OpportunitySelectionError(
            "opportunity_selection_create_target_conflict"
        )

    signal_refs = _signal_refs(recommendation)
    await _validate_signal_refs(
        session,
        project_id=project_id,
        need_id=need.id,
        locale=locale,
        signal_ids=signal_refs,
    )
    await _validate_content_refs(
        session,
        project_id=project_id,
        content_ids=content_refs,
    )

    question = _text(
        recommendation.get("primary_question"),
        "opportunity_selection_question_invalid",
        max_length=4_000,
    )
    intent = _text(
        recommendation.get("intent"),
        "opportunity_selection_intent_invalid",
        max_length=64,
    )
    question_coverage_hash = _hash64(
        planner.get("question_coverage_snapshot_hash"),
        "opportunity_selection_coverage_hash_invalid",
    )
    lineage_reasons = _lineage_reasons(
        recommendation,
        planner_hash=planner_hash,
        cluster_key=cluster_key,
        question_coverage_hash=question_coverage_hash,
    )

    selected_at = utc_now()
    opportunity = ContentOpportunity(
        id=opportunity_id,
        project_id=project_id,
        need_hypothesis_id=need.id,
        locale=locale,
        reader=need.audience_scope,
        situation=need.situation,
        need=need.statement,
        question=question,
        intent=intent,
        promise=promise,
        coverage_requirements_json=coverage,
        motgu_material_refs_json=[],
        material_gaps_json=[_MATERIAL_GAP],
        existing_content_refs_json=[str(value) for value in content_refs],
        what_is_actually_new=_NOT_NEW_YET,
        next_discovery_step=_NEXT_STEP,
        decision=decision,
        priority=priority,
        reasons_json=lineage_reasons,
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
        selected_by=selected_by,
        selected_at=selected_at,
        selection_reason=reason,
    )
    opportunity.reasons_json = sorted(
        set(
            opportunity.reasons_json
            + [
                "selection_contract:qm02a-v1",
                f"selection_payload:{_opportunity_payload_hash(opportunity)}",
            ]
        )
    )
    session.add(opportunity)
    await session.flush()

    for signal_id in signal_refs:
        session.add(
            ContentOpportunitySignal(
                content_opportunity_id=opportunity.id,
                signal_id=signal_id,
            )
        )

    selection = HumanSelection(
        id=selection_id,
        content_opportunity_id=opportunity.id,
        selected_by=selected_by,
        reason=reason,
        selected_at=selected_at,
    )
    session.add(selection)
    await session.flush()

    return OpportunitySelectionResult(
        schema_version=OPPORTUNITY_SELECTION_SCHEMA_VERSION,
        content_opportunity_id=opportunity.id,
        human_selection_id=selection.id,
        planner_snapshot_hash=planner_hash,
        cluster_key=cluster_key,
        decision=decision,
        priority=priority,
        replayed=False,
    )


__all__ = [
    "OPPORTUNITY_SELECTION_SCHEMA_VERSION",
    "OpportunitySelectionError",
    "OpportunitySelectionRequest",
    "OpportunitySelectionResult",
    "persist_selected_opportunity",
]
