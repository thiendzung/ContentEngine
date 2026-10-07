"""QM-02D3: bounded MERGE reconciliation handoff."""

from __future__ import annotations

import hashlib
import json
from typing import cast
from uuid import UUID

from pydantic import BaseModel, ValidationError
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
    TargetContentSnapshot,
    build_production_decision_route,
)

MERGE_HANDOFF_POLICY_VERSION = "qm-merge-handoff-v1"
_MERGE_ACTION_KEY = "materialize_question_map_merge"
_MATERIALIZABLE_NEED_STATUSES = frozenset(
    {"PROPOSED", "TESTING", "SUPPORTED"}
)


class MergeProductionHandoffError(ValueError):
    """Fail-closed MERGE handoff error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class MergeProductionHandoffResult(BaseModel):
    policy_version: str
    command_id: UUID
    project_id: UUID
    opportunity_id: UUID
    reconciliation_content_case_id: UUID
    source_locale_variant_id: UUID
    survivor_content_item_id: UUID
    survivor_content_version_id: UUID
    target_snapshots: list[TargetContentSnapshot]
    conflict_set_hash: str
    founder_reason: str
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
        raise MergeProductionHandoffError(code)
    return normalized


def _normalize_reason(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > 2000:
        raise MergeProductionHandoffError(
            "merge_handoff_founder_reason_invalid"
        )
    return normalized


def _request_hash(
    *,
    project_id: UUID,
    opportunity_id: UUID,
    survivor_content_item_id: UUID,
    founder_reason: str,
    route_snapshot_hash: str,
    admission_snapshot_hash: str,
) -> str:
    return _stable_hash(
        {
            "policy_version": MERGE_HANDOFF_POLICY_VERSION,
            "project_id": str(project_id),
            "opportunity_id": str(opportunity_id),
            "survivor_content_item_id": str(survivor_content_item_id),
            "founder_reason": founder_reason,
            "route_snapshot_hash": route_snapshot_hash,
            "admission_snapshot_hash": admission_snapshot_hash,
        }
    )


def _require_merge_route(
    route: ProductionDecisionRoute,
    *,
    opportunity: ContentOpportunity,
    survivor_content_item_id: UUID,
) -> None:
    if (
        opportunity.decision != "MERGE"
        or route.decision != "MERGE"
        or route.route != "RECONCILE_CONTENT"
        or not route.reconciliation_required
        or route.admission_candidate
        or route.production_forbidden
    ):
        raise MergeProductionHandoffError(
            "merge_handoff_requires_merge_reconciliation"
        )
    if (
        len(route.target_content_item_ids) < 2
        or len(route.target_snapshots)
        != len(route.target_content_item_ids)
    ):
        raise MergeProductionHandoffError(
            "merge_handoff_target_count_invalid"
        )
    if survivor_content_item_id not in route.target_content_item_ids:
        raise MergeProductionHandoffError(
            "merge_handoff_survivor_not_in_conflict_set"
        )

    normalized_intent = opportunity.intent.strip().casefold()
    target_intents = {
        row.primary_intent.strip().casefold()
        for row in route.target_snapshots
    }
    if not normalized_intent or target_intents != {normalized_intent}:
        raise MergeProductionHandoffError(
            "merge_handoff_target_intent_mismatch"
        )

    try:
        expected_role = require_editorial_role(
            opportunity.suggested_role
        )
    except EditorialRoleError as exc:
        raise MergeProductionHandoffError(
            "merge_handoff_opportunity_role_invalid"
        ) from exc
    target_roles = {
        row.content_role.strip().casefold()
        for row in route.target_snapshots
    }
    if target_roles != {expected_role}:
        raise MergeProductionHandoffError(
            "merge_handoff_target_role_mismatch"
        )

    for target in route.target_snapshots:
        if (
            target.current_content_version_id is None
            or target.current_content_version_no is None
            or target.current_content_version_status is None
        ):
            raise MergeProductionHandoffError(
                "merge_handoff_target_snapshot_invalid"
            )


async def _latest_target_version(
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
        raise MergeProductionHandoffError(
            "merge_handoff_target_version_missing"
        )
    return version


async def _lock_conflict_set(
    session: AsyncSession,
    *,
    project_id: UUID,
    target_ids: list[UUID],
) -> tuple[
    dict[UUID, ContentItem],
    dict[UUID, ContentCase],
    dict[UUID, LocaleVariant],
    dict[UUID, ContentVersion],
]:
    items = list(
        (
            await session.scalars(
                select(ContentItem)
                .where(
                    ContentItem.id.in_(target_ids),
                    ContentItem.project_id == project_id,
                )
                .order_by(ContentItem.id)
                .with_for_update()
            )
        ).all()
    )
    if len(items) != len(target_ids):
        raise MergeProductionHandoffError(
            "merge_handoff_target_not_found"
        )

    case_ids = sorted(
        {item.content_case_id for item in items},
        key=str,
    )
    cases = list(
        (
            await session.scalars(
                select(ContentCase)
                .where(ContentCase.id.in_(case_ids))
                .order_by(ContentCase.id)
                .with_for_update()
            )
        ).all()
    )
    if len(cases) != len(case_ids):
        raise MergeProductionHandoffError(
            "merge_handoff_target_case_missing"
        )

    variant_ids = sorted(
        {item.locale_variant_id for item in items},
        key=str,
    )
    variants = list(
        (
            await session.scalars(
                select(LocaleVariant)
                .where(LocaleVariant.id.in_(variant_ids))
                .order_by(LocaleVariant.id)
                .with_for_update()
            )
        ).all()
    )
    if len(variants) != len(variant_ids):
        raise MergeProductionHandoffError(
            "merge_handoff_target_variant_missing"
        )

    versions: dict[UUID, ContentVersion] = {}
    for item in items:
        versions[item.id] = await _latest_target_version(
            session,
            content_item_id=item.id,
        )

    return (
        {item.id: item for item in items},
        {row.id: row for row in cases},
        {row.id: row for row in variants},
        versions,
    )


def _conflict_set_payload(
    *,
    project_id: UUID,
    opportunity_id: UUID,
    survivor_content_item_id: UUID,
    founder_reason: str,
    route_snapshot_hash: str,
    admission_snapshot_hash: str,
    target_snapshots: list[TargetContentSnapshot],
) -> dict[str, object]:
    target_rows = [
        row.model_dump(mode="json")
        for row in sorted(
            target_snapshots,
            key=lambda value: str(value.content_item_id),
        )
    ]
    conflict_set_hash = _stable_hash(
        {
            "project_id": str(project_id),
            "opportunity_id": str(opportunity_id),
            "survivor_content_item_id": str(
                survivor_content_item_id
            ),
            "targets": target_rows,
        }
    )
    return {
        "kind": "qm_merge_reconciliation_plan",
        "schema_version": 1,
        "policy_version": MERGE_HANDOFF_POLICY_VERSION,
        "project_id": str(project_id),
        "opportunity_id": str(opportunity_id),
        "survivor_content_item_id": str(
            survivor_content_item_id
        ),
        "founder_reason": founder_reason,
        "route_snapshot_hash": route_snapshot_hash,
        "admission_snapshot_hash": admission_snapshot_hash,
        "target_snapshots": target_rows,
        "conflict_set_hash": conflict_set_hash,
    }


def _parse_conflict_set_payload(
    raw_notes: list[object],
    *,
    project_id: UUID,
    opportunity_id: UUID,
) -> tuple[
    UUID,
    str,
    str,
    str,
    str,
    list[TargetContentSnapshot],
]:
    if len(raw_notes) != 1 or not isinstance(raw_notes[0], dict):
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_plan_missing"
        )
    payload = cast(dict[str, object], raw_notes[0])
    if (
        payload.get("kind") != "qm_merge_reconciliation_plan"
        or payload.get("schema_version") != 1
        or payload.get("policy_version")
        != MERGE_HANDOFF_POLICY_VERSION
        or payload.get("project_id") != str(project_id)
        or payload.get("opportunity_id") != str(opportunity_id)
    ):
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_plan_invalid"
        )
    survivor_raw = payload.get("survivor_content_item_id")
    founder_reason = payload.get("founder_reason")
    conflict_set_hash = payload.get("conflict_set_hash")
    route_hash = payload.get("route_snapshot_hash")
    admission_hash = payload.get("admission_snapshot_hash")
    target_rows = payload.get("target_snapshots")
    if (
        not isinstance(survivor_raw, str)
        or not isinstance(founder_reason, str)
        or not isinstance(conflict_set_hash, str)
        or not isinstance(route_hash, str)
        or not isinstance(admission_hash, str)
        or not isinstance(target_rows, list)
    ):
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_plan_invalid"
        )
    try:
        survivor_id = UUID(survivor_raw)
        targets = [
            TargetContentSnapshot.model_validate(row)
            for row in target_rows
        ]
    except (ValueError, ValidationError) as exc:
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_plan_invalid"
        ) from exc
    target_ids = [row.content_item_id for row in targets]
    if (
        len(targets) < 2
        or len(target_ids) != len(set(target_ids))
        or survivor_id not in target_ids
    ):
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_plan_invalid"
        )
    expected_conflict_hash = _stable_hash(
        {
            "project_id": str(project_id),
            "opportunity_id": str(opportunity_id),
            "survivor_content_item_id": str(survivor_id),
            "targets": [
                row.model_dump(mode="json")
                for row in sorted(
                    targets,
                    key=lambda value: str(value.content_item_id),
                )
            ],
        }
    )
    if expected_conflict_hash != conflict_set_hash:
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_plan_hash_mismatch"
        )
    return (
        survivor_id,
        founder_reason,
        conflict_set_hash,
        route_hash,
        admission_hash,
        targets,
    )


async def _replay_result(
    session: AsyncSession,
    *,
    command: OperatorCommand,
    project_id: UUID,
    opportunity_id: UUID,
    route_snapshot_hash: str,
    admission_snapshot_hash: str,
) -> MergeProductionHandoffResult:
    if (
        command.resolved_action_key != _MERGE_ACTION_KEY
        or command.result_ref_id is None
    ):
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_action_mismatch"
        )

    reconciliation_case = await session.get(
        ContentCase,
        command.content_case_id,
    )
    if (
        reconciliation_case is None
        or reconciliation_case.project_id != project_id
        or reconciliation_case.content_opportunity_id
        != opportunity_id
        or reconciliation_case.content_type != "journal"
    ):
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_case_mismatch"
        )

    opportunity = await session.get(
        ContentOpportunity,
        opportunity_id,
    )
    if opportunity is None or opportunity.project_id != project_id:
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_opportunity_missing"
        )
    source_variant = await session.scalar(
        select(LocaleVariant)
        .where(
            LocaleVariant.content_case_id == reconciliation_case.id,
            LocaleVariant.locale == opportunity.locale,
        )
        .order_by(LocaleVariant.id)
        .limit(1)
    )
    if source_variant is None:
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_variant_missing"
        )
    (
        survivor_id,
        founder_reason,
        conflict_set_hash,
        stored_route_hash,
        stored_admission_hash,
        targets,
    ) = _parse_conflict_set_payload(
        source_variant.keyword_notes_json,
        project_id=project_id,
        opportunity_id=opportunity_id,
    )
    if stored_route_hash != route_snapshot_hash:
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_route_mismatch"
        )
    if stored_admission_hash != admission_snapshot_hash:
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_admission_mismatch"
        )

    survivor_target = next(
        (
            row
            for row in targets
            if row.content_item_id == survivor_id
        ),
        None,
    )
    if (
        survivor_target is None
        or survivor_target.current_content_version_id
        != command.result_ref_id
    ):
        raise MergeProductionHandoffError(
            "merge_handoff_receipt_survivor_mismatch"
        )

    state = await operator_runtime.get_operator_state(
        session,
        content_case_id=reconciliation_case.id,
    )
    return MergeProductionHandoffResult(
        policy_version=MERGE_HANDOFF_POLICY_VERSION,
        command_id=command.id,
        project_id=project_id,
        opportunity_id=opportunity_id,
        reconciliation_content_case_id=reconciliation_case.id,
        source_locale_variant_id=source_variant.id,
        survivor_content_item_id=survivor_id,
        survivor_content_version_id=command.result_ref_id,
        target_snapshots=targets,
        conflict_set_hash=conflict_set_hash,
        founder_reason=founder_reason,
        route_snapshot_hash=route_snapshot_hash,
        admission_snapshot_hash=admission_snapshot_hash,
        replayed=True,
        state=state,
    )


async def materialize_merge_handoff(
    session: AsyncSession,
    *,
    project_id: UUID,
    opportunity_id: UUID,
    survivor_content_item_id: UUID,
    founder_reason: str,
    expected_route_snapshot_hash: str,
    expected_admission_snapshot_hash: str,
    idempotency_key: str,
    actor_id: str = "founder",
) -> MergeProductionHandoffResult:
    """Freeze one explicit MERGE reconciliation plan without destructive effects."""

    route_hash = _normalize_hash(
        expected_route_snapshot_hash,
        code="merge_handoff_route_hash_invalid",
    )
    admission_hash = _normalize_hash(
        expected_admission_snapshot_hash,
        code="merge_handoff_admission_hash_invalid",
    )
    reason = _normalize_reason(founder_reason)
    key = idempotency_key.strip()
    if not key or len(key) > 200:
        raise MergeProductionHandoffError(
            "merge_handoff_idempotency_key_invalid"
        )

    request_hash = _request_hash(
        project_id=project_id,
        opportunity_id=opportunity_id,
        survivor_content_item_id=survivor_content_item_id,
        founder_reason=reason,
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
            != _MERGE_ACTION_KEY
        ):
            raise MergeProductionHandoffError(
                "merge_handoff_idempotency_conflict"
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
        raise MergeProductionHandoffError(
            "merge_handoff_opportunity_not_found"
        )

    locked_need = await session.scalar(
        select(NeedHypothesis)
        .where(
            NeedHypothesis.id
            == locked_opportunity.need_hypothesis_id,
            NeedHypothesis.project_id == project_id,
        )
        .with_for_update()
    )
    if locked_need is None:
        raise MergeProductionHandoffError(
            "merge_handoff_need_not_found"
        )
    if locked_need.status == "REJECTED":
        raise MergeProductionHandoffError(
            "merge_handoff_need_rejected"
        )
    if locked_need.status == "INSUFFICIENT_EVIDENCE":
        raise MergeProductionHandoffError(
            "merge_handoff_need_insufficient_evidence"
        )
    if locked_need.status not in _MATERIALIZABLE_NEED_STATUSES:
        raise MergeProductionHandoffError(
            "merge_handoff_need_status_unsupported"
        )

    try:
        preliminary_route = await build_production_decision_route(
            session,
            project_id=project_id,
            opportunity_id=opportunity_id,
        )
    except ProductionDecisionRouterError as exc:
        raise MergeProductionHandoffError(exc.code) from exc
    _require_merge_route(
        preliminary_route,
        opportunity=locked_opportunity,
        survivor_content_item_id=survivor_content_item_id,
    )

    items, cases, variants, versions = await _lock_conflict_set(
        session,
        project_id=project_id,
        target_ids=preliminary_route.target_content_item_ids,
    )

    try:
        route = await build_production_decision_route(
            session,
            project_id=project_id,
            opportunity_id=opportunity_id,
        )
    except ProductionDecisionRouterError as exc:
        raise MergeProductionHandoffError(exc.code) from exc
    _require_merge_route(
        route,
        opportunity=locked_opportunity,
        survivor_content_item_id=survivor_content_item_id,
    )

    for target in route.target_snapshots:
        item = items.get(target.content_item_id)
        case = cases.get(target.content_case_id)
        variant = variants.get(target.locale_variant_id)
        version = versions.get(target.content_item_id)
        if (
            item is None
            or case is None
            or variant is None
            or version is None
            or item.content_case_id != case.id
            or item.locale_variant_id != variant.id
            or target.current_content_version_id != version.id
            or target.current_content_version_no
            != version.version_no
            or target.current_content_version_status
            != version.status
        ):
            raise MergeProductionHandoffError(
                "merge_handoff_target_snapshot_stale"
            )

    if route.snapshot_hash != route_hash:
        raise MergeProductionHandoffError(
            "merge_handoff_route_stale"
        )

    try:
        await validate_persisted_opportunity_selection(
            session,
            project_id=project_id,
            opportunity=locked_opportunity,
        )
    except OpportunitySelectionError as exc:
        raise MergeProductionHandoffError(
            f"merge_handoff_{exc.code}"
        ) from exc

    try:
        admission = await build_production_admission(
            session,
            project_id=project_id,
            opportunity_id=opportunity_id,
            expected_route_snapshot_hash=route_hash,
        )
    except ProductionAdmissionError as exc:
        raise MergeProductionHandoffError(exc.code) from exc
    if admission.snapshot_hash != admission_hash:
        raise MergeProductionHandoffError(
            "merge_handoff_admission_stale"
        )
    if (
        admission.status != "RECONCILIATION_REQUIRED"
        or admission.route != "RECONCILE_CONTENT"
    ):
        raise MergeProductionHandoffError(
            "merge_handoff_not_reconcilable"
        )

    try:
        reconciliation_case, opportunity, _ = (
            await ensure_selected_content_case(
                session,
                project_id=project_id,
                content_opportunity_id=opportunity_id,
                need_hypothesis_id=locked_opportunity.need_hypothesis_id,
                required_need_status=locked_need.status,
                need_status_error_code=(
                    "merge_handoff_need_status_changed"
                ),
            )
        )
    except ValueError as exc:
        raise MergeProductionHandoffError(str(exc)) from exc

    existing_variants = list(
        (
            await session.scalars(
                select(LocaleVariant)
                .where(
                    LocaleVariant.content_case_id
                    == reconciliation_case.id
                )
                .order_by(LocaleVariant.id)
            )
        ).all()
    )
    if existing_variants:
        raise MergeProductionHandoffError(
            "merge_handoff_unexpected_case_reuse"
        )

    try:
        role = require_editorial_role(opportunity.suggested_role)
    except EditorialRoleError as exc:
        raise MergeProductionHandoffError(
            "merge_handoff_opportunity_role_invalid"
        ) from exc

    conflict_payload = _conflict_set_payload(
        project_id=project_id,
        opportunity_id=opportunity_id,
        survivor_content_item_id=survivor_content_item_id,
        founder_reason=reason,
        route_snapshot_hash=route_hash,
        admission_snapshot_hash=admission_hash,
        target_snapshots=route.target_snapshots,
    )
    source_variant = LocaleVariant(
        content_case_id=reconciliation_case.id,
        locale=opportunity.locale,
        content_role=role,
        primary_question=opportunity.question,
        primary_intent=opportunity.intent,
        secondary_intent=None,
        primary_query=None,
        keyword_notes_json=[conflict_payload],
        emotion_arc_json=[],
        must_include_json=[],
        must_not_claim_json=[],
        status="draft",
    )
    session.add(source_variant)
    await session.flush()

    survivor_snapshot = next(
        row
        for row in route.target_snapshots
        if row.content_item_id == survivor_content_item_id
    )
    survivor_version_id = survivor_snapshot.current_content_version_id
    if survivor_version_id is None:
        raise MergeProductionHandoffError(
            "merge_handoff_survivor_version_missing"
        )

    state = await operator_runtime.get_operator_state(
        session,
        content_case_id=reconciliation_case.id,
    )
    command = OperatorCommand(
        content_case_id=reconciliation_case.id,
        run_id=None,
        step_run_id=None,
        job_id=None,
        result_ref_id=survivor_version_id,
        intent="create",
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=state.state_version,
        resolved_action_key=_MERGE_ACTION_KEY,
        status="completed",
        error_code=None,
        actor_id=actor_id,
        state_before=state.state_version,
        state_after=state.state_version,
    )
    session.add(command)
    await session.flush()

    return MergeProductionHandoffResult(
        policy_version=MERGE_HANDOFF_POLICY_VERSION,
        command_id=command.id,
        project_id=project_id,
        opportunity_id=opportunity_id,
        reconciliation_content_case_id=reconciliation_case.id,
        source_locale_variant_id=source_variant.id,
        survivor_content_item_id=survivor_content_item_id,
        survivor_content_version_id=survivor_version_id,
        target_snapshots=route.target_snapshots,
        conflict_set_hash=cast(
            str,
            conflict_payload["conflict_set_hash"],
        ),
        founder_reason=reason,
        route_snapshot_hash=route_hash,
        admission_snapshot_hash=admission_hash,
        replayed=False,
        state=state,
    )


__all__ = [
    "MERGE_HANDOFF_POLICY_VERSION",
    "MergeProductionHandoffError",
    "MergeProductionHandoffResult",
    "materialize_merge_handoff",
]
