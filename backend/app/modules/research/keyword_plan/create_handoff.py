"""QM-02D1: transaction-bound CREATE production handoff."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal import operator_runtime
from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.journal.operator_control import (
    CreatedJournalCase,
    OperatorControlError,
    OperatorState,
    create_or_reuse_journal_case,
)
from app.modules.content_engine.journal.operator_locking import (
    lock_operator_idempotency,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    LocaleVariant,
    NeedHypothesis,
)
from app.modules.research.keyword_plan.production_admission import (
    ProductionAdmissionError,
    build_production_admission,
)
from app.modules.research.keyword_plan.production_decision_router import (
    ProductionDecisionRouterError,
    build_production_decision_route,
)

CREATE_HANDOFF_POLICY_VERSION = "qm-create-handoff-v1.1"
_MATERIALIZABLE_NEED_STATUSES = frozenset({"PROPOSED", "TESTING", "SUPPORTED"})


class CreateProductionHandoffError(ValueError):
    """Fail-closed CREATE handoff error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CreateProductionHandoffResult(BaseModel):
    policy_version: str
    command_id: UUID
    project_id: UUID
    opportunity_id: UUID
    content_case_id: UUID
    source_locale_variant_id: UUID
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
        raise CreateProductionHandoffError(code)
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
            "policy_version": CREATE_HANDOFF_POLICY_VERSION,
            "project_id": str(project_id),
            "opportunity_id": str(opportunity_id),
            "route_snapshot_hash": route_snapshot_hash,
            "admission_snapshot_hash": admission_snapshot_hash,
        }
    )


async def _replay_result(
    session: AsyncSession,
    *,
    command: OperatorCommand,
    project_id: UUID,
    opportunity_id: UUID,
    route_snapshot_hash: str,
    admission_snapshot_hash: str,
) -> CreateProductionHandoffResult:
    content_case = await session.get(ContentCase, command.content_case_id)
    if (
        content_case is None
        or content_case.project_id != project_id
        or content_case.content_opportunity_id != opportunity_id
        or content_case.content_type != "journal"
    ):
        raise CreateProductionHandoffError(
            "create_handoff_receipt_case_mismatch"
        )
    opportunity = await session.get(ContentOpportunity, opportunity_id)
    if opportunity is None or opportunity.project_id != project_id:
        raise CreateProductionHandoffError(
            "create_handoff_receipt_opportunity_missing"
        )
    if command.result_ref_id is None:
        raise CreateProductionHandoffError(
            "create_handoff_receipt_variant_missing"
        )
    variant = await session.get(LocaleVariant, command.result_ref_id)
    if variant is None or variant.content_case_id != content_case.id:
        raise CreateProductionHandoffError(
            "create_handoff_receipt_variant_mismatch"
        )
    state = await operator_runtime.get_operator_state(
        session,
        content_case_id=content_case.id,
    )
    return CreateProductionHandoffResult(
        policy_version=CREATE_HANDOFF_POLICY_VERSION,
        command_id=command.id,
        project_id=project_id,
        opportunity_id=opportunity_id,
        content_case_id=content_case.id,
        source_locale_variant_id=variant.id,
        route_snapshot_hash=route_snapshot_hash,
        admission_snapshot_hash=admission_snapshot_hash,
        replayed=True,
        state=state,
    )


async def materialize_create_handoff(
    session: AsyncSession,
    *,
    project_id: UUID,
    opportunity_id: UUID,
    expected_route_snapshot_hash: str,
    expected_admission_snapshot_hash: str,
    idempotency_key: str,
    actor_id: str = "founder",
) -> CreateProductionHandoffResult:
    route_hash = _normalize_hash(
        expected_route_snapshot_hash,
        code="create_handoff_route_hash_invalid",
    )
    admission_hash = _normalize_hash(
        expected_admission_snapshot_hash,
        code="create_handoff_admission_hash_invalid",
    )
    key = idempotency_key.strip()
    if not key or len(key) > 200:
        raise CreateProductionHandoffError(
            "create_handoff_idempotency_key_invalid"
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
            or existing_command.resolved_action_key
            != "materialize_question_map_create"
            or existing_command.request_hash != request_hash
        ):
            raise CreateProductionHandoffError(
                "create_handoff_idempotency_conflict"
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
        raise CreateProductionHandoffError(
            "create_handoff_opportunity_not_found"
        )

    locked_need = await session.scalar(
        select(NeedHypothesis)
        .where(
            NeedHypothesis.id == locked_opportunity.need_hypothesis_id,
            NeedHypothesis.project_id == project_id,
        )
        .with_for_update()
    )
    if locked_need is None:
        raise CreateProductionHandoffError(
            "create_handoff_need_not_found"
        )
    if locked_need.status == "REJECTED":
        raise CreateProductionHandoffError(
            "create_handoff_need_rejected"
        )
    if locked_need.status == "INSUFFICIENT_EVIDENCE":
        raise CreateProductionHandoffError(
            "create_handoff_need_insufficient_evidence"
        )
    if locked_need.status not in _MATERIALIZABLE_NEED_STATUSES:
        raise CreateProductionHandoffError(
            "create_handoff_need_status_unsupported"
        )

    try:
        route = await build_production_decision_route(
            session,
            project_id=project_id,
            opportunity_id=opportunity_id,
        )
    except ProductionDecisionRouterError as exc:
        raise CreateProductionHandoffError(exc.code) from exc

    if route.snapshot_hash != route_hash:
        raise CreateProductionHandoffError(
            "create_handoff_route_stale"
        )
    if route.route != "CREATE_NEW_CONTENT":
        raise CreateProductionHandoffError(
            "create_handoff_requires_create_route"
        )

    try:
        admission = await build_production_admission(
            session,
            project_id=project_id,
            opportunity_id=opportunity_id,
            expected_route_snapshot_hash=route_hash,
        )
    except ProductionAdmissionError as exc:
        raise CreateProductionHandoffError(exc.code) from exc

    if admission.snapshot_hash != admission_hash:
        raise CreateProductionHandoffError(
            "create_handoff_admission_stale"
        )
    if admission.status != "ADMITTED":
        raise CreateProductionHandoffError(
            "create_handoff_not_admitted"
        )
    if admission.route != "CREATE_NEW_CONTENT":
        raise CreateProductionHandoffError(
            "create_handoff_admission_route_mismatch"
        )

    try:
        created: CreatedJournalCase = await create_or_reuse_journal_case(
            session,
            content_opportunity_id=opportunity_id,
            expected_opportunity_version=route.opportunity_version,
            required_need_status=locked_need.status,
            need_status_error_code="create_handoff_need_status_changed",
        )
    except OperatorControlError as exc:
        raise CreateProductionHandoffError(exc.code) from exc

    if created.reused:
        raise CreateProductionHandoffError(
            "create_handoff_unexpected_reuse"
        )

    command = OperatorCommand(
        content_case_id=created.content_case_id,
        run_id=None,
        step_run_id=None,
        job_id=None,
        result_ref_id=created.source_locale_variant_id,
        intent="create",
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=created.state.state_version,
        resolved_action_key="materialize_question_map_create",
        status="completed",
        error_code=None,
        actor_id=actor_id,
        state_before=created.state.state_version,
        state_after=created.state.state_version,
    )
    session.add(command)
    await session.flush()

    return CreateProductionHandoffResult(
        policy_version=CREATE_HANDOFF_POLICY_VERSION,
        command_id=command.id,
        project_id=project_id,
        opportunity_id=opportunity_id,
        content_case_id=created.content_case_id,
        source_locale_variant_id=created.source_locale_variant_id,
        route_snapshot_hash=route_hash,
        admission_snapshot_hash=admission_hash,
        replayed=False,
        state=created.state,
    )


__all__ = [
    "CREATE_HANDOFF_POLICY_VERSION",
    "CreateProductionHandoffError",
    "CreateProductionHandoffResult",
    "materialize_create_handoff",
]
