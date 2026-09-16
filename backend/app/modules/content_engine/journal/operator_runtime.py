"""Canonical Journal operator runtime authority.

This module is the stable entrypoint for operator state, semantic commands and safe
server-side continuation resolution. Older implementation modules remain compatibility
layers only; production callers should import from here rather than versioned adapters.
"""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.operator_control import (
    OperatorCommandResult,
    OperatorControlError,
    OperatorIntent,
    OperatorState,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    START_TO_ANGLE_STAGE,
    get_operator_state_v45 as _get_operator_state_impl,
    submit_operator_command_v45 as _submit_operator_command_impl,
)
from app.modules.harness.models import ContentRun, StepRun

OperatorActionKey = Literal[
    "start_to_angle",
    "review_revise_en",
    "await_angle_approval",
    "await_outline_approval",
    "await_final_review_approval",
    "angle_to_outline",
    "outline_to_writers",
    "finalize_content",
    "complete",
]

_EXECUTABLE_ACTIONS = {START_TO_ANGLE_STAGE, "review_revise_en"}
_GATE_WAIT_ACTIONS: dict[str, OperatorActionKey] = {
    "angle": "await_angle_approval",
    "outline": "await_outline_approval",
    "final_review": "await_final_review_approval",
}
_GATE_CONTINUATIONS: dict[str, OperatorActionKey] = {
    "angle": "angle_to_outline",
    "outline": "outline_to_writers",
    "final_review": "finalize_content",
}


class ResolvedOperatorAction(BaseModel):
    """The only backend-derived next action for the current durable case state."""

    content_case_id: UUID
    state_version: str
    status: str
    action_key: OperatorActionKey | None = None
    intent: OperatorIntent | None = None
    executable: bool = False
    current_run_id: UUID | None = None
    current_step_run_id: UUID | None = None
    human_gate: str | None = None
    blocker_code: str | None = None


async def get_operator_state(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    preflight_checked: bool = False,
) -> OperatorState:
    """Return the canonical operator projection used by API, worker and receipts."""

    return await _get_operator_state_impl(
        session,
        content_case_id=content_case_id,
        preflight_checked=preflight_checked,
    )


async def submit_operator_command(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    intent: OperatorIntent,
    expected_state_version: str,
    idempotency_key: str,
    knowledge_brief_id: UUID | None = None,
    actor_id: str = "founder",
) -> OperatorCommandResult:
    """Submit semantic operator intent without accepting an internal stage selector."""

    return await _submit_operator_command_impl(
        session,
        content_case_id=content_case_id,
        intent=intent,
        expected_state_version=expected_state_version,
        idempotency_key=idempotency_key,
        knowledge_brief_id=knowledge_brief_id,
        actor_id=actor_id,
    )


async def _bound_focus(
    session: AsyncSession,
    *,
    state: OperatorState,
) -> tuple[ContentRun | None, StepRun | None]:
    run = (
        await session.get(ContentRun, state.current_run_id)
        if state.current_run_id is not None
        else None
    )
    step = (
        await session.get(StepRun, state.current_step_run_id)
        if state.current_step_run_id is not None
        else None
    )
    if state.current_run_id is not None and (
        run is None or run.content_case_id != state.content_case_id
    ):
        raise OperatorControlError("operator_next_action_state_conflict")
    if state.current_step_run_id is not None and (
        step is None or run is None or step.run_id != run.id
    ):
        raise OperatorControlError("operator_next_action_state_conflict")
    return run, step


async def resolve_next_operator_action(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    preflight_checked: bool = False,
) -> ResolvedOperatorAction:
    """Resolve one safe next action from persisted truth only.

    F1 deliberately does not make future continuation actions executable. It establishes
    one fail-closed authority that later slices can wire without allowing the frontend to
    choose a stage, model, provider, prompt, recipe or worker.
    """

    state = await get_operator_state(
        session,
        content_case_id=content_case_id,
        preflight_checked=preflight_checked,
    )
    run, step = await _bound_focus(session, state=state)

    if state.status == "COMPLETE":
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key="complete",
            current_run_id=state.current_run_id,
            current_step_run_id=state.current_step_run_id,
        )

    if state.status == "AWAITING_APPROVAL":
        if state.human_gate is None or state.human_gate not in _GATE_WAIT_ACTIONS:
            raise OperatorControlError("operator_next_action_state_conflict")
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key=_GATE_WAIT_ACTIONS[state.human_gate],
            current_run_id=state.current_run_id,
            current_step_run_id=state.current_step_run_id,
            human_gate=state.human_gate,
        )

    if state.blocker_code == "operator_gate_already_decided":
        if run is None or run.current_step not in _GATE_CONTINUATIONS:
            raise OperatorControlError("operator_next_action_state_conflict")
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key=_GATE_CONTINUATIONS[run.current_step],
            intent="continue",
            executable=False,
            current_run_id=run.id,
            current_step_run_id=state.current_step_run_id,
            blocker_code=state.blocker_code,
        )

    if state.primary_intent is not None:
        if state.primary_intent not in state.allowed_intents or step is None:
            raise OperatorControlError("operator_next_action_state_conflict")
        if step.step_key not in _EXECUTABLE_ACTIONS:
            raise OperatorControlError("operator_next_action_not_allowlisted")
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key=cast(OperatorActionKey, step.step_key),
            intent=state.primary_intent,
            executable=True,
            current_run_id=state.current_run_id,
            current_step_run_id=step.id,
            blocker_code=state.blocker_code,
        )

    if state.status in {"QUEUED", "RUNNING"}:
        if step is None or step.step_key not in _EXECUTABLE_ACTIONS:
            raise OperatorControlError("operator_next_action_state_conflict")
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key=cast(OperatorActionKey, step.step_key),
            executable=False,
            current_run_id=state.current_run_id,
            current_step_run_id=step.id,
        )

    return ResolvedOperatorAction(
        content_case_id=content_case_id,
        state_version=state.state_version,
        status=state.status,
        current_run_id=state.current_run_id,
        current_step_run_id=state.current_step_run_id,
        blocker_code=state.blocker_code,
    )


__all__ = [
    "OperatorActionKey",
    "ResolvedOperatorAction",
    "START_TO_ANGLE_STAGE",
    "get_operator_state",
    "resolve_next_operator_action",
    "submit_operator_command",
]
