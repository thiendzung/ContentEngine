"""Operator-facing editorial decisions bound to existing Journal approval contracts."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.angle import AngleApprovalError, approve_angle_candidate
from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.journal.operator_control import (
    OperatorControlError,
    get_operator_state,
)
from app.modules.content_engine.journal.outline_approval import (
    OutlineApprovalError,
    approve_outline_artifact,
)
from app.modules.content_engine.journal.review_actions import (
    ReviewActionError,
    submit_review_decision,
)
from app.modules.content_engine.models import ContentCase

DecisionScope = Literal["angle", "outline", "final"]
DecisionAction = Literal["approved", "changes_requested", "rejected"]

_SCOPE_GATE = {
    "angle": "angle",
    "outline": "outline",
    "final": "final_review",
}


class OperatorDecisionResult(BaseModel):
    command_id: UUID
    content_case_id: UUID
    scope: DecisionScope
    decision: DecisionAction
    approval_id: UUID | None = None
    state_before: str
    state_after: str | None
    replayed: bool = False


def _stable_hash(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _ledger_intent(decision: DecisionAction) -> str:
    if decision == "approved":
        return "approve"
    if decision == "changes_requested":
        return "request_changes"
    return "reject"


async def submit_operator_decision(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    scope: DecisionScope,
    decision: DecisionAction,
    expected_state_version: str,
    idempotency_key: str,
    artifact_id: UUID | None = None,
    artifact_version: int | None = None,
    artifact_hash: str | None = None,
    selected_angle_id: str | None = None,
    selected_candidate_hash: str | None = None,
    locale_variant_id: UUID | None = None,
    comment: str | None = None,
    actor_id: str = "founder",
) -> OperatorDecisionResult:
    key = idempotency_key.strip()
    if not key or len(key) > 200:
        raise OperatorControlError("operator_idempotency_key_invalid")
    if len(expected_state_version) != 64:
        raise OperatorControlError("operator_state_version_invalid")

    request_payload = {
        "content_case_id": str(content_case_id),
        "scope": scope,
        "decision": decision,
        "expected_state_version": expected_state_version,
        "artifact_id": str(artifact_id) if artifact_id else None,
        "artifact_version": artifact_version,
        "artifact_hash": artifact_hash,
        "selected_angle_id": selected_angle_id,
        "selected_candidate_hash": selected_candidate_hash,
        "locale_variant_id": str(locale_variant_id) if locale_variant_id else None,
        "comment": comment.strip() if isinstance(comment, str) else None,
    }
    request_hash = _stable_hash(request_payload)
    existing = await session.scalar(
        select(OperatorCommand).where(OperatorCommand.idempotency_key == key)
    )
    if existing is not None:
        if existing.request_hash != request_hash or existing.content_case_id != content_case_id:
            raise OperatorControlError("operator_idempotency_conflict")
        return OperatorDecisionResult(
            command_id=existing.id,
            content_case_id=content_case_id,
            scope=scope,
            decision=decision,
            state_before=existing.state_before,
            state_after=existing.state_after,
            replayed=True,
        )

    locked_case = await session.scalar(
        select(ContentCase)
        .where(ContentCase.id == content_case_id, ContentCase.content_type == "journal")
        .with_for_update()
    )
    if locked_case is None:
        raise OperatorControlError("operator_case_not_found")

    before = await get_operator_state(session, content_case_id=content_case_id)
    if before.state_version != expected_state_version:
        raise OperatorControlError("operator_state_stale")
    if before.status != "AWAITING_APPROVAL" or before.human_gate != _SCOPE_GATE[scope]:
        raise OperatorControlError("operator_decision_not_awaiting_scope")

    approval_id: UUID | None = None
    run_id: UUID | None = before.current_run_id
    resolved_action = f"{scope}_decision"
    try:
        if scope == "angle":
            if decision != "approved":
                raise OperatorControlError("operator_angle_nonapprove_not_supported")
            if (
                artifact_id is None
                or artifact_version is None
                or artifact_hash is None
                or selected_angle_id is None
                or selected_candidate_hash is None
            ):
                raise OperatorControlError("operator_angle_binding_required")
            angle_approval = await approve_angle_candidate(
                session,
                angle_artifact_id=artifact_id,
                expected_artifact_version=artifact_version,
                expected_artifact_hash=artifact_hash,
                selected_angle_id=selected_angle_id,
                expected_candidate_hash=selected_candidate_hash,
                approved_by=actor_id,
                approval_reason=(comment or "Founder approved from operator control").strip(),
            )
            approval_id = angle_approval.id
            run_id = angle_approval.run_id
        elif scope == "outline":
            if decision != "approved":
                raise OperatorControlError("operator_outline_nonapprove_not_supported")
            if artifact_id is None or artifact_version is None or artifact_hash is None:
                raise OperatorControlError("operator_outline_binding_required")
            outline_approval = await approve_outline_artifact(
                session,
                outline_artifact_id=artifact_id,
                expected_artifact_version=artifact_version,
                expected_artifact_hash=artifact_hash,
                approved_by=actor_id,
                approval_reason=(comment or "Founder approved from operator control").strip(),
            )
            approval_id = outline_approval.id
            run_id = outline_approval.run_id
        else:
            if locale_variant_id is None:
                raise OperatorControlError("operator_final_locale_required")
            result = await submit_review_decision(
                session,
                content_case_id=content_case_id,
                locale_variant_id=locale_variant_id,
                decision=decision,
                actor_id=actor_id,
                comment=comment,
            )
            approval_id = result.approval_id
            run_id = result.writer_run_id
    except (AngleApprovalError, OutlineApprovalError, ReviewActionError) as exc:
        code = getattr(exc, "code", "operator_decision_domain_rejected")
        raise OperatorControlError(str(code)) from exc

    command = OperatorCommand(
        content_case_id=content_case_id,
        run_id=run_id,
        step_run_id=before.current_step_run_id,
        job_id=None,
        intent=_ledger_intent(decision),
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=expected_state_version,
        resolved_action_key=resolved_action,
        status="completed",
        error_code=None,
        actor_id=actor_id,
        state_before=expected_state_version,
        state_after=None,
    )
    session.add(command)
    await session.flush()
    after = await get_operator_state(session, content_case_id=content_case_id)
    command.state_after = after.state_version
    await session.flush()
    return OperatorDecisionResult(
        command_id=command.id,
        content_case_id=content_case_id,
        scope=scope,
        decision=decision,
        approval_id=approval_id,
        state_before=expected_state_version,
        state_after=command.state_after,
        replayed=False,
    )


__all__ = [
    "DecisionAction",
    "DecisionScope",
    "OperatorDecisionResult",
    "submit_operator_decision",
]
