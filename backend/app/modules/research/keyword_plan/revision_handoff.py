"""QM-02D2: transaction-bound UPDATE / REFRESH production handoff."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal import operator_runtime
from app.modules.content_engine.journal.editorial_role import (
    EditorialRoleError,
    require_editorial_role,
)
from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.journal.operator_control import OperatorState
from app.modules.content_engine.journal.operator_locking import (
    lock_operator_idempotency,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
    NeedHypothesis,
)
from app.modules.research.evidence.persistence import (
    ensure_selected_content_case,
)
from app.modules.research.keyword_plan.opportunity_selection_v2 import (
    OpportunitySelectionError,
    validate_persisted_opportunity_selection,
)
from app.modules.research.keyword_plan.production_admission import (
    ProductionAdmissionError,
    build_production_admission,
)
from app.modules.research.keyword_plan.production_decision_router import (
    ProductionDecisionRoute,
    ProductionDecisionRouterError,
    build_production_decision_route,
)

REVISION_HANDOFF_POLICY_VERSION = "qm-revision-handoff-v1"
_MATERIALIZABLE_NEED_STATUSES = frozenset(
    {"PROPOSED", "TESTING", "SUPPORTED"}
)
RevisionDecision = Literal["UPDATE", "REFRESH"]

_ROUTE_BY_DECISION = {
    "UPDATE": "REVISE_EXISTING_CONTENT",
    "REFRESH": "REFRESH_EXISTING_CONTENT",
}
_ACTION_BY_DECISION = {
    "UPDATE": "materialize_question_map_update",
    "REFRESH": "materialize_question_map_refresh",
}
_DECISION_BY_ACTION = {
    value: cast(RevisionDecision, key)
    for key, value in _ACTION_BY_DECISION.items()
}


class RevisionProductionHandoffError(ValueError):
    """Fail-closed UPDATE / REFRESH handoff error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RevisionProductionHandoffResult(BaseModel):
    policy_version: str
    command_id: UUID
    project_id: UUID
    opportunity_id: UUID
    decision: RevisionDecision
    revision_content_case_id: UUID
    source_locale_variant_id: UUID
    target_content_item_id: UUID
    target_content_version_id: UUID
    target_content_version_no: int
    target_content_version_status: str
    route_snapshot_hash: str
    admission_snapshot_hash: str
    replayed: bool
    state: OperatorState


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _normalize_hash(value: str, *, code: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(
        char not in "0123456789abcdef" for char in normalized
    ):
        raise RevisionProductionHandoffError(code)
    return normalized


def _request_hash(
    *,
    project_id: UUID,
    opportunity_id: UUID,
    route_snapshot_hash: str,
    admission_snapshot_hash: str,
) -> str:
    return _stable_hash(
        {
            "policy_version": REVISION_HANDOFF_POLICY_VERSION,
            "project_id": str(project_id),
            "opportunity_id": str(opportunity_id),
            "route_snapshot_hash": route_snapshot_hash,
            "admission_snapshot_hash": admission_snapshot_hash,
        }
    )


def _revision_decision(opportunity: ContentOpportunity) -> RevisionDecision:
    if opportunity.decision not in _ROUTE_BY_DECISION:
        raise RevisionProductionHandoffError(
            "revision_handoff_requires_update_or_refresh"
        )
    return cast(RevisionDecision, opportunity.decision)


def _require_revision_route(
    route: ProductionDecisionRoute,
    *,
    decision: RevisionDecision,
) -> None:
    if route.route != _ROUTE_BY_DECISION[decision]:
        raise RevisionProductionHandoffError(
            "revision_handoff_route_mismatch"
        )
    if (
        len(route.target_content_item_ids) != 1
        or len(route.target_snapshots) != 1
    ):
        raise RevisionProductionHandoffError(
            "revision_handoff_target_count_invalid"
        )
    target = route.target_snapshots[0]
    if (
        target.content_item_id != route.target_content_item_ids[0]
        or target.current_content_version_id is None
        or target.current_content_version_no is None
        or target.current_content_version_status is None
    ):
        raise RevisionProductionHandoffError(
            "revision_handoff_target_snapshot_invalid"
        )


async def _latest_target_version_for_update(
    session: AsyncSession,
    *,
    content_item_id: UUID,
) -> ContentVersion:
    version = await session.scalar(
        select(ContentVersion)
        .where(ContentVersion.content_item_id == content_item_id)
        .order_by(
            ContentVersion.version_no.desc(),
            ContentVersion.created_at.desc(),
            ContentVersion.id.desc(),
        )
        .limit(1)
        .with_for_update()
    )
    if version is None:
        raise RevisionProductionHandoffError(
            "revision_handoff_target_version_missing"
        )
    return version


async def _replay_result(
    session: AsyncSession,
    *,
    command: OperatorCommand,
    project_id: UUID,
    opportunity_id: UUID,
    route_snapshot_hash: str,
    admission_snapshot_hash: str,
) -> RevisionProductionHandoffResult:
    decision = _DECISION_BY_ACTION.get(command.resolved_action_key or "")
    if decision is None:
        raise RevisionProductionHandoffError(
            "revision_handoff_receipt_action_mismatch"
        )
    if command.result_ref_id is None:
        raise RevisionProductionHandoffError(
            "revision_handoff_receipt_version_missing"
        )

    revision_case = await session.get(ContentCase, command.content_case_id)
    if (
        revision_case is None
        or revision_case.project_id != project_id
        or revision_case.content_opportunity_id != opportunity_id
        or revision_case.content_type != "journal"
    ):
        raise RevisionProductionHandoffError(
            "revision_handoff_receipt_case_mismatch"
        )
    opportunity = await session.get(ContentOpportunity, opportunity_id)
    if opportunity is None or opportunity.project_id != project_id:
        raise RevisionProductionHandoffError(
            "revision_handoff_receipt_opportunity_missing"
        )

    target_version = await session.get(
        ContentVersion,
        command.result_ref_id,
    )
    if target_version is None:
        raise RevisionProductionHandoffError(
            "revision_handoff_receipt_version_missing"
        )
    target_item = await session.get(
        ContentItem,
        target_version.content_item_id,
    )
    if target_item is None or target_item.project_id != project_id:
        raise RevisionProductionHandoffError(
            "revision_handoff_receipt_target_missing"
        )

    variant = await session.scalar(
        select(LocaleVariant)
        .where(
            LocaleVariant.content_case_id == revision_case.id,
            LocaleVariant.locale == opportunity.locale,
        )
        .order_by(LocaleVariant.id)
        .limit(1)
    )
    if variant is None:
        raise RevisionProductionHandoffError(
            "revision_handoff_receipt_variant_missing"
        )

    state = await operator_runtime.get_operator_state(
        session,
        content_case_id=revision_case.id,
    )
    return RevisionProductionHandoffResult(
        policy_version=REVISION_HANDOFF_POLICY_VERSION,
        command_id=command.id,
        project_id=project_id,
        opportunity_id=opportunity_id,
        decision=decision,
        revision_content_case_id=revision_case.id,
        source_locale_variant_id=variant.id,
        target_content_item_id=target_item.id,
        target_content_version_id=target_version.id,
        target_content_version_no=target_version.version_no,
        target_content_version_status=target_version.status,
        route_snapshot_hash=route_snapshot_hash,
        admission_snapshot_hash=admission_snapshot_hash,
        replayed=True,
        state=state,
    )


async def materialize_revision_handoff(
    session: AsyncSession,
    *,
    project_id: UUID,
    opportunity_id: UUID,
    expected_route_snapshot_hash: str,
    expected_admission_snapshot_hash: str,
    idempotency_key: str,
    actor_id: str = "founder",
) -> RevisionProductionHandoffResult:
    """Materialize one exact revision intent without creating a competing item."""

    route_hash = _normalize_hash(
        expected_route_snapshot_hash,
        code="revision_handoff_route_hash_invalid",
    )
    admission_hash = _normalize_hash(
        expected_admission_snapshot_hash,
        code="revision_handoff_admission_hash_invalid",
    )
    key = idempotency_key.strip()
    if not key or len(key) > 200:
        raise RevisionProductionHandoffError(
            "revision_handoff_idempotency_key_invalid"
        )

    request_hash = _request_hash(
        project_id=project_id,
        opportunity_id=opportunity_id,
        route_snapshot_hash=route_hash,
        admission_snapshot_hash=admission_hash,
    )

    await lock_operator_idempotency(session, key=key)
    existing_command = await session.scalar(
        select(OperatorCommand).where(
            OperatorCommand.idempotency_key == key
        )
    )
    if existing_command is not None:
        if (
            existing_command.intent != "create"
            or existing_command.request_hash != request_hash
            or existing_command.resolved_action_key
            not in _DECISION_BY_ACTION
        ):
            raise RevisionProductionHandoffError(
                "revision_handoff_idempotency_conflict"
            )
        return await _replay_result(
            session,
            command=existing_command,
            project_id=project_id,
            opportunity_id=opportunity_id,
            route_snapshot_hash=route_hash,
            admission_snapshot_hash=admission_hash,
        )

    locked_opportunity = await session.scalar(
        select(ContentOpportunity)
        .where(
            ContentOpportunity.id == opportunity_id,
            ContentOpportunity.project_id == project_id,
        )
        .with_for_update()
    )
    if locked_opportunity is None:
        raise RevisionProductionHandoffError(
            "revision_handoff_opportunity_not_found"
        )
    decision = _revision_decision(locked_opportunity)

    locked_need = await session.scalar(
        select(NeedHypothesis)
        .where(
            NeedHypothesis.id == locked_opportunity.need_hypothesis_id,
            NeedHypothesis.project_id == project_id,
        )
        .with_for_update()
    )
    if locked_need is None:
        raise RevisionProductionHandoffError(
            "revision_handoff_need_not_found"
        )
    if locked_need.status == "REJECTED":
        raise RevisionProductionHandoffError(
            "revision_handoff_need_rejected"
        )
    if locked_need.status == "INSUFFICIENT_EVIDENCE":
        raise RevisionProductionHandoffError(
            "revision_handoff_need_insufficient_evidence"
        )
    if locked_need.status not in _MATERIALIZABLE_NEED_STATUSES:
        raise RevisionProductionHandoffError(
            "revision_handoff_need_status_unsupported"
        )

    try:
        preliminary_route = await build_production_decision_route(
            session,
            project_id=project_id,
            opportunity_id=opportunity_id,
        )
    except ProductionDecisionRouterError as exc:
        raise RevisionProductionHandoffError(exc.code) from exc
    _require_revision_route(
        preliminary_route,
        decision=decision,
    )

    target_id = preliminary_route.target_content_item_ids[0]
    target_item = await session.scalar(
        select(ContentItem)
        .where(
            ContentItem.id == target_id,
            ContentItem.project_id == project_id,
        )
        .with_for_update()
    )
    if target_item is None:
        raise RevisionProductionHandoffError(
            "revision_handoff_target_not_found"
        )
    target_case = await session.scalar(
        select(ContentCase)
        .where(ContentCase.id == target_item.content_case_id)
        .with_for_update()
    )
    if target_case is None:
        raise RevisionProductionHandoffError(
            "revision_handoff_target_case_missing"
        )
    target_variant = await session.scalar(
        select(LocaleVariant)
        .where(LocaleVariant.id == target_item.locale_variant_id)
        .with_for_update()
    )
    if target_variant is None:
        raise RevisionProductionHandoffError(
            "revision_handoff_target_variant_missing"
        )
    locked_target_version = await _latest_target_version_for_update(
        session,
        content_item_id=target_item.id,
    )

    try:
        route = await build_production_decision_route(
            session,
            project_id=project_id,
            opportunity_id=opportunity_id,
        )
    except ProductionDecisionRouterError as exc:
        raise RevisionProductionHandoffError(exc.code) from exc
    _require_revision_route(route, decision=decision)
    target_snapshot = route.target_snapshots[0]
    if (
        target_snapshot.current_content_version_id
        != locked_target_version.id
        or target_snapshot.content_case_id != target_case.id
        or target_snapshot.locale_variant_id != target_variant.id
    ):
        raise RevisionProductionHandoffError(
            "revision_handoff_target_snapshot_stale"
        )
    if route.snapshot_hash != route_hash:
        raise RevisionProductionHandoffError(
            "revision_handoff_route_stale"
        )

    try:
        await validate_persisted_opportunity_selection(
            session,
            project_id=project_id,
            opportunity=locked_opportunity,
        )
    except OpportunitySelectionError as exc:
        raise RevisionProductionHandoffError(
            f"revision_handoff_{exc.code}"
        ) from exc

    try:
        admission = await build_production_admission(
            session,
            project_id=project_id,
            opportunity_id=opportunity_id,
            expected_route_snapshot_hash=route_hash,
        )
    except ProductionAdmissionError as exc:
        raise RevisionProductionHandoffError(exc.code) from exc
    if admission.snapshot_hash != admission_hash:
        raise RevisionProductionHandoffError(
            "revision_handoff_admission_stale"
        )
    if admission.status != "ADMITTED":
        raise RevisionProductionHandoffError(
            "revision_handoff_not_admitted"
        )
    if admission.route != _ROUTE_BY_DECISION[decision]:
        raise RevisionProductionHandoffError(
            "revision_handoff_admission_route_mismatch"
        )

    try:
        revision_case, opportunity, _ = await ensure_selected_content_case(
            session,
            project_id=project_id,
            content_opportunity_id=opportunity_id,
            need_hypothesis_id=locked_opportunity.need_hypothesis_id,
            required_need_status=locked_need.status,
            need_status_error_code="revision_handoff_need_status_changed",
        )
    except ValueError as exc:
        raise RevisionProductionHandoffError(str(exc)) from exc

    try:
        role = require_editorial_role(opportunity.suggested_role)
    except EditorialRoleError as exc:
        raise RevisionProductionHandoffError(
            "revision_handoff_opportunity_role_invalid"
        ) from exc

    existing_variants = list(
        (
            await session.scalars(
                select(LocaleVariant)
                .where(LocaleVariant.content_case_id == revision_case.id)
                .order_by(LocaleVariant.id)
            )
        ).all()
    )
    if existing_variants:
        raise RevisionProductionHandoffError(
            "revision_handoff_unexpected_case_reuse"
        )

    source_variant = LocaleVariant(
        content_case_id=revision_case.id,
        locale=opportunity.locale,
        content_role=role,
        primary_question=opportunity.question,
        primary_intent=opportunity.intent,
        secondary_intent=None,
        primary_query=None,
        keyword_notes_json=[],
        emotion_arc_json=[],
        must_include_json=[],
        must_not_claim_json=[],
        status="draft",
    )
    session.add(source_variant)
    await session.flush()

    state = await operator_runtime.get_operator_state(
        session,
        content_case_id=revision_case.id,
    )
    command = OperatorCommand(
        content_case_id=revision_case.id,
        run_id=None,
        step_run_id=None,
        job_id=None,
        result_ref_id=locked_target_version.id,
        intent="create",
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=state.state_version,
        resolved_action_key=_ACTION_BY_DECISION[decision],
        status="completed",
        error_code=None,
        actor_id=actor_id,
        state_before=state.state_version,
        state_after=state.state_version,
    )
    session.add(command)
    await session.flush()

    return RevisionProductionHandoffResult(
        policy_version=REVISION_HANDOFF_POLICY_VERSION,
        command_id=command.id,
        project_id=project_id,
        opportunity_id=opportunity_id,
        decision=decision,
        revision_content_case_id=revision_case.id,
        source_locale_variant_id=source_variant.id,
        target_content_item_id=target_item.id,
        target_content_version_id=locked_target_version.id,
        target_content_version_no=locked_target_version.version_no,
        target_content_version_status=locked_target_version.status,
        route_snapshot_hash=route_hash,
        admission_snapshot_hash=admission_hash,
        replayed=False,
        state=state,
    )


__all__ = [
    "REVISION_HANDOFF_POLICY_VERSION",
    "RevisionDecision",
    "RevisionProductionHandoffError",
    "RevisionProductionHandoffResult",
    "materialize_revision_handoff",
]
