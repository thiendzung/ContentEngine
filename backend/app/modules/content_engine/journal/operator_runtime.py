"""Canonical Journal operator runtime authority.

The UI submits semantic intent only. This module derives the one safe next action from
persisted state and owns durable command creation for operator continuations.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import AngleApproval, OperatorCommand
from app.modules.content_engine.journal.operator_control import (
    OperatorCommandResult,
    OperatorControlError,
    OperatorIntent,
    OperatorState,
)
from app.modules.content_engine.journal.operator_locking import lock_operator_idempotency
from app.modules.content_engine.journal.operator_vertical_slice import START_TO_ANGLE_STAGE
from app.modules.content_engine.journal.operator_vertical_slice import (
    get_operator_state_v45 as _get_operator_state_impl,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    submit_operator_command_v45 as _submit_operator_command_impl,
)
from app.modules.content_engine.journal.outline import OutlineGenerationError, load_outline_input
from app.modules.content_engine.journal.outline_agent_bridge import (
    OUTLINE_PROMPT_KEY,
    OUTLINE_RECIPE_KEY,
    OUTLINE_ROUTE_TASK_KEY,
    OUTLINE_TASK_KEY,
)
from app.modules.content_engine.models import ContentCase, SettingsSnapshot
from app.modules.harness.models import ContentRun, Job, StepRun
from app.modules.harness.persistence import enqueue_job, transition_run
from app.modules.harness.runtime import RuntimeConfigurationError, SettingsModelRouter
from app.modules.system.settings_service import (
    SettingsResolutionError,
    active_prompt_definition,
    active_recipe_definition,
)

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

_ACTION_BY_STAGE: dict[str, OperatorActionKey] = {
    START_TO_ANGLE_STAGE: "start_to_angle",
    "review_revise_en": "review_revise_en",
    OUTLINE_TASK_KEY: "angle_to_outline",
}
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
_F2_EXECUTABLE_CONTINUATIONS = {"angle"}


class ResolvedOperatorAction(BaseModel):
    """The backend-derived next action for one durable Journal case state."""

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


def _command_hash(
    *,
    content_case_id: UUID,
    intent: OperatorIntent,
    state_version: str,
    action_key: str,
) -> str:
    raw = json.dumps(
        {
            "content_case_id": str(content_case_id),
            "intent": intent,
            "expected_state_version": state_version,
            "action_key": action_key,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def _latest_job(session: AsyncSession, *, step_run_id: UUID) -> Job | None:
    return cast(
        Job | None,
        await session.scalar(
            select(Job)
            .where(Job.step_run_id == step_run_id)
            .order_by(Job.updated_at.desc(), Job.id.desc())
            .limit(1)
        ),
    )


async def _angle_approval(session: AsyncSession, *, run_id: UUID) -> AngleApproval:
    approvals = list(
        (
            await session.scalars(
                select(AngleApproval)
                .where(AngleApproval.run_id == run_id)
                .order_by(AngleApproval.created_at, AngleApproval.id)
            )
        ).all()
    )
    if len(approvals) != 1:
        raise OperatorControlError("operator_angle_approval_conflict")
    return approvals[0]


async def _validate_outline_runtime(
    session: AsyncSession,
    *,
    run: ContentRun,
    approval: AngleApproval,
) -> None:
    """Fail before enqueue when exact Outline inputs/config are not resolvable."""

    try:
        outline_input = await load_outline_input(
            session,
            angle_artifact_id=approval.angle_artifact_id,
            expected_angle_artifact_version=approval.angle_artifact_version,
            expected_angle_artifact_hash=approval.angle_artifact_hash,
            selected_angle_id=approval.selected_angle_id,
            expected_candidate_hash=approval.selected_candidate_hash,
            expected_approval_id=approval.id,
        )
    except OutlineGenerationError as exc:
        raise OperatorControlError("operator_outline_input_invalid", exc.code) from exc

    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None:
        raise OperatorControlError("operator_outline_settings_missing")
    try:
        route = SettingsModelRouter().resolve(
            task_key=OUTLINE_ROUTE_TASK_KEY,
            settings_snapshot=snapshot,
        )
    except RuntimeConfigurationError as exc:
        raise OperatorControlError("operator_outline_route_invalid") from exc
    if route.primary.provider != "codex_cli" or not route.primary.model.strip():
        raise OperatorControlError("operator_outline_route_not_allowed")

    try:
        await active_prompt_definition(session, prompt_key=OUTLINE_PROMPT_KEY)
        await active_recipe_definition(
            session,
            recipe_key=OUTLINE_RECIPE_KEY,
            content_type="journal",
            locale=outline_input.approved_angle.candidate.locale,
            task_key=OUTLINE_TASK_KEY,
        )
    except SettingsResolutionError as exc:
        raise OperatorControlError("operator_outline_registry_blocked", exc.code) from exc


async def _outline_state_overlay(
    session: AsyncSession,
    *,
    state: OperatorState,
) -> OperatorState:
    """Add bounded manual-retry semantics for the F2 Outline step."""

    if state.current_run_id is None or state.current_step_run_id is None:
        return state
    run = await session.get(ContentRun, state.current_run_id)
    step = await session.get(StepRun, state.current_step_run_id)
    if (
        run is None
        or step is None
        or step.run_id != run.id
        or step.step_key != OUTLINE_TASK_KEY
    ):
        return state
    job = await _latest_job(session, step_run_id=step.id)
    if (
        run.status == "running"
        and step.status in {"pending", "running"}
        and job is not None
        and job.status in {"failed", "cancelled"}
    ):
        return state.model_copy(
            update={
                "status": "BLOCKED",
                "phase": "Dàn ý",
                "primary_intent": "retry",
                "allowed_intents": ["retry"],
                "blocker_code": "operator_job_failed",
                "blocker_message": (
                    "Tác vụ Outline thất bại; có thể thử lại nếu lineage vẫn hợp lệ."
                ),
                "last_checkpoint": "Outline chưa hoàn tất; lần chạy gần nhất đã thất bại.",
            }
        )
    return state


async def get_operator_state(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    preflight_checked: bool = False,
) -> OperatorState:
    """Return the canonical operator projection used by API, worker and receipts."""

    state = await _get_operator_state_impl(
        session,
        content_case_id=content_case_id,
        preflight_checked=preflight_checked,
    )
    return await _outline_state_overlay(session, state=state)


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
    """Resolve one safe next action from persisted truth only."""

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
        gate_action: OperatorActionKey = _GATE_CONTINUATIONS[run.current_step]
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key=gate_action,
            intent="continue",
            executable=run.current_step in _F2_EXECUTABLE_CONTINUATIONS,
            current_run_id=run.id,
            current_step_run_id=state.current_step_run_id,
            blocker_code=state.blocker_code,
        )

    if state.primary_intent is not None:
        if state.primary_intent not in state.allowed_intents or step is None:
            raise OperatorControlError("operator_next_action_state_conflict")
        runnable_action = _ACTION_BY_STAGE.get(step.step_key)
        if runnable_action is None:
            raise OperatorControlError("operator_next_action_not_allowlisted")
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key=runnable_action,
            intent=state.primary_intent,
            executable=True,
            current_run_id=state.current_run_id,
            current_step_run_id=step.id,
            blocker_code=state.blocker_code,
        )

    if state.status in {"QUEUED", "RUNNING"}:
        if step is None:
            raise OperatorControlError("operator_next_action_state_conflict")
        active_action = _ACTION_BY_STAGE.get(step.step_key)
        if active_action is None:
            raise OperatorControlError("operator_next_action_state_conflict")
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key=active_action,
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


async def _submit_angle_to_outline_command(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    intent: OperatorIntent,
    expected_state_version: str,
    idempotency_key: str,
    actor_id: str,
) -> OperatorCommandResult:
    if intent not in {"continue", "retry", "cancel"}:
        raise OperatorControlError("operator_intent_not_allowed")
    key = idempotency_key.strip()
    if not key or len(key) > 200:
        raise OperatorControlError("operator_idempotency_key_invalid")
    if len(expected_state_version) != 64:
        raise OperatorControlError("operator_state_version_invalid")
    request_hash = _command_hash(
        content_case_id=content_case_id,
        intent=intent,
        state_version=expected_state_version,
        action_key="angle_to_outline",
    )

    await lock_operator_idempotency(session, key=key)
    existing = await session.scalar(
        select(OperatorCommand).where(OperatorCommand.idempotency_key == key)
    )
    if existing is not None:
        if existing.request_hash != request_hash or existing.content_case_id != content_case_id:
            raise OperatorControlError("operator_idempotency_conflict")
        return OperatorCommandResult(
            command_id=existing.id,
            content_case_id=existing.content_case_id,
            intent=cast(OperatorIntent, existing.intent),
            status=existing.status,
            state_before=existing.state_before,
            state_after=existing.state_after,
            job_id=existing.job_id,
            replayed=True,
        )

    locked_case = await session.scalar(
        select(ContentCase)
        .where(ContentCase.id == content_case_id, ContentCase.content_type == "journal")
        .with_for_update()
    )
    if locked_case is None:
        raise OperatorControlError("operator_case_not_found")

    resolved = await resolve_next_operator_action(
        session,
        content_case_id=content_case_id,
        preflight_checked=True,
    )
    if resolved.state_version != expected_state_version:
        raise OperatorControlError("operator_state_stale")
    if resolved.action_key != "angle_to_outline":
        raise OperatorControlError("operator_internal_action_not_approved")
    if intent == "continue" and not resolved.executable:
        raise OperatorControlError("operator_intent_not_allowed")
    if intent == "retry" and resolved.intent != "retry":
        raise OperatorControlError("operator_retry_requires_failed_job")
    if resolved.current_run_id is None:
        raise OperatorControlError("operator_runnable_step_missing")

    run = await session.get(ContentRun, resolved.current_run_id)
    if run is None or run.content_case_id != content_case_id:
        raise OperatorControlError("operator_next_action_state_conflict")
    approval = await _angle_approval(session, run_id=run.id)
    await _validate_outline_runtime(session, run=run, approval=approval)

    previous_job: Job | None = None
    if intent == "continue":
        if run.status != "waiting_approval" or run.current_step != "angle":
            raise OperatorControlError("operator_next_action_state_conflict")
        existing_steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == run.id,
                        StepRun.step_key == OUTLINE_TASK_KEY,
                    )
                )
            ).all()
        )
        if existing_steps:
            raise OperatorControlError("operator_outline_step_conflict")
        step = StepRun(
            run_id=run.id,
            step_key=OUTLINE_TASK_KEY,
            attempt=1,
            status="pending",
            input_artifact_refs_json=[
                str(approval.angle_artifact_id),
                f"angle_approval:{approval.id}",
            ],
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
        await transition_run(session, run_id=run.id, status="running")
        run.current_step = OUTLINE_TASK_KEY
        run.failure_code = None
        run.failure_message = None
        await session.flush()
    else:
        if resolved.current_step_run_id is None:
            raise OperatorControlError("operator_runnable_step_missing")
        retry_step = await session.get(StepRun, resolved.current_step_run_id)
        if (
            retry_step is None
            or retry_step.run_id != run.id
            or retry_step.step_key != OUTLINE_TASK_KEY
        ):
            raise OperatorControlError("operator_next_action_state_conflict")
        step = retry_step
        previous_job = await _latest_job(session, step_run_id=step.id)
        if intent == "retry" and (
            previous_job is None or previous_job.status not in {"failed", "cancelled"}
        ):
            raise OperatorControlError("operator_retry_requires_failed_job")
        if intent == "cancel" and (
            previous_job is None or previous_job.status != "queued"
        ):
            raise OperatorControlError("operator_cancel_requires_queued_job")

    command = OperatorCommand(
        content_case_id=content_case_id,
        run_id=run.id,
        step_run_id=step.id,
        job_id=None,
        intent=intent,
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=expected_state_version,
        resolved_action_key="angle_to_outline",
        status="accepted",
        error_code=None,
        actor_id=actor_id,
        state_before=expected_state_version,
        state_after=None,
    )
    session.add(command)
    await session.flush()

    if intent == "cancel":
        assert previous_job is not None
        previous_job.status = "cancelled"
        command.job_id = previous_job.id
        command.status = "cancelled"
    else:
        dedupe_payload = f"{command.id}:{key}".encode()
        queued = await enqueue_job(
            session,
            run_id=run.id,
            step_run_id=step.id,
            dedupe_key=f"operator:{hashlib.sha256(dedupe_payload).hexdigest()}",
        )
        if intent == "retry" and previous_job is not None:
            queued.attempt = previous_job.attempt + 1
        command.job_id = queued.id
        command.status = "queued"

    await session.flush()
    after = await get_operator_state(
        session,
        content_case_id=content_case_id,
        preflight_checked=True,
    )
    command.state_after = after.state_version
    await session.flush()
    return OperatorCommandResult(
        command_id=command.id,
        content_case_id=content_case_id,
        intent=intent,
        status=command.status,
        state_before=command.state_before,
        state_after=command.state_after,
        job_id=command.job_id,
        replayed=False,
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

    resolved = await resolve_next_operator_action(
        session,
        content_case_id=content_case_id,
        preflight_checked=True,
    )
    if resolved.action_key == "angle_to_outline":
        if knowledge_brief_id is not None:
            raise OperatorControlError("operator_knowledge_brief_binding_start_only")
        return await _submit_angle_to_outline_command(
            session,
            content_case_id=content_case_id,
            intent=intent,
            expected_state_version=expected_state_version,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
        )

    return await _submit_operator_command_impl(
        session,
        content_case_id=content_case_id,
        intent=intent,
        expected_state_version=expected_state_version,
        idempotency_key=idempotency_key,
        knowledge_brief_id=knowledge_brief_id,
        actor_id=actor_id,
    )


__all__ = [
    "OperatorActionKey",
    "ResolvedOperatorAction",
    "START_TO_ANGLE_STAGE",
    "get_operator_state",
    "resolve_next_operator_action",
    "submit_operator_command",
]
