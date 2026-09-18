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
from app.modules.content_engine.journal.operator_quality import (
    get_quality_progress,
    submit_writers_to_quality_command,
)
from app.modules.content_engine.journal.operator_vertical_slice import START_TO_ANGLE_STAGE
from app.modules.content_engine.journal.operator_vertical_slice import (
    get_operator_state_v45 as _get_operator_state_impl,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    submit_operator_command_v45 as _submit_operator_command_impl,
)
from app.modules.content_engine.journal.operator_writers import (
    WRITER_MAX_JOB_ATTEMPTS,
    WRITER_STEP_BY_LOCALE,
    get_writer_lane_progress,
    settle_writer_commands,
)
from app.modules.content_engine.journal.outline import OutlineGenerationError, load_outline_input
from app.modules.content_engine.journal.outline_agent_bridge import (
    OUTLINE_PROMPT_KEY,
    OUTLINE_RECIPE_KEY,
    OUTLINE_ROUTE_TASK_KEY,
    OUTLINE_TASK_KEY,
)
from app.modules.content_engine.journal.writer import WriterGenerationError, ensure_writer_run
from app.modules.content_engine.models import ContentCase, SettingsSnapshot
from app.modules.harness.models import Artifact, ContentRun, Job, StepRun
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
    "writers_to_quality",
    "finalize_content",
    "complete",
]

_ACTION_BY_STAGE: dict[str, OperatorActionKey] = {
    START_TO_ANGLE_STAGE: "start_to_angle",
    "review_revise_en": "review_revise_en",
    OUTLINE_TASK_KEY: "angle_to_outline",
    "review_revise_vi": "writers_to_quality",
    "assertion_audit_vi": "writers_to_quality",
    "assertion_audit_en": "writers_to_quality",
    "source_copy_check_vi": "writers_to_quality",
    "source_copy_check_en": "writers_to_quality",
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
_AUTHORITATIVE_COMPLETION_BLOCKERS = {"operator_completion_binding_invalid"}


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


def _completion_projection_is_authoritative(state: OperatorState) -> bool:
    return (
        state.status == "COMPLETE"
        or state.blocker_code in _AUTHORITATIVE_COMPLETION_BLOCKERS
    )


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
    """Project the durable F2 Outline job ahead of legacy compatibility blockers."""

    if state.current_run_id is None or state.current_step_run_id is None:
        return state
    run = await session.get(ContentRun, state.current_run_id)
    step = await session.get(StepRun, state.current_step_run_id)
    if run is None or step is None or step.run_id != run.id or step.step_key != OUTLINE_TASK_KEY:
        return state
    job = await _latest_job(session, step_run_id=step.id)
    if run.status != "running" or step.status not in {"pending", "running"} or job is None:
        return state
    if job.status == "queued":
        return state.model_copy(
            update={
                "status": "QUEUED",
                "phase": "Dàn ý",
                "primary_intent": None,
                "allowed_intents": ["cancel"],
                "human_gate": None,
                "current_worker": None,
                "blocker_code": None,
                "blocker_message": None,
                "last_checkpoint": "Tác vụ Outline đã nằm trong hàng đợi bền vững.",
            }
        )
    if job.status == "leased":
        return state.model_copy(
            update={
                "status": "RUNNING",
                "phase": "Dàn ý",
                "primary_intent": None,
                "allowed_intents": [],
                "human_gate": None,
                "current_worker": job.lease_owner,
                "blocker_code": None,
                "blocker_message": None,
                "last_checkpoint": "Worker đang giữ lease của tác vụ Outline.",
            }
        )
    if job.status in {"failed", "cancelled"}:
        return state.model_copy(
            update={
                "status": "BLOCKED",
                "phase": "Dàn ý",
                "primary_intent": "retry",
                "allowed_intents": ["retry"],
                "human_gate": None,
                "current_worker": None,
                "blocker_code": "operator_job_failed",
                "blocker_message": (
                    "Tác vụ Outline thất bại; có thể thử lại nếu lineage vẫn hợp lệ."
                ),
                "last_checkpoint": "Outline chưa hoàn tất; lần chạy gần nhất đã thất bại.",
            }
        )
    return state


async def _angle_continuation_state_overlay(
    session: AsyncSession,
    *,
    state: OperatorState,
) -> OperatorState:
    """Expose the now-wired Angle continuation instead of a compatibility blocker."""

    if state.blocker_code != "operator_gate_already_decided" or state.current_run_id is None:
        return state
    run = await session.get(ContentRun, state.current_run_id)
    if run is None or run.content_case_id != state.content_case_id or run.current_step != "angle":
        return state
    await _angle_approval(session, run_id=run.id)
    return state.model_copy(
        update={
            "status": "READY",
            "phase": "Dàn ý",
            "primary_intent": "continue",
            "allowed_intents": ["continue"],
            "human_gate": None,
            "blocker_code": None,
            "blocker_message": None,
            "last_checkpoint": "Angle đã duyệt; sẵn sàng tạo Outline.",
        }
    )


async def _writer_state_overlay(
    session: AsyncSession,
    *,
    state: OperatorState,
) -> OperatorState:
    source_step_run_id = state.current_step_run_id
    progress = await get_writer_lane_progress(
        session,
        content_case_id=state.content_case_id,
        source_run_id=state.current_run_id,
    )
    if progress is None and state.current_run_id is not None:
        focused_run = await session.get(ContentRun, state.current_run_id)
        if focused_run is not None and focused_run.run_mode == "localize":
            handoffs = list(
                (
                    await session.scalars(
                        select(Artifact).where(
                            Artifact.run_id == focused_run.id,
                            Artifact.artifact_type == "writer_handoff",
                        )
                    )
                ).all()
            )
            if len(handoffs) == 1 and isinstance(handoffs[0].content_json, dict):
                raw_source_run_id = handoffs[0].content_json.get("source_run_id")
                if isinstance(raw_source_run_id, str):
                    try:
                        source_run_id = UUID(raw_source_run_id)
                    except ValueError:
                        source_run_id = None
                    if source_run_id is not None:
                        progress = await get_writer_lane_progress(
                            session,
                            content_case_id=state.content_case_id,
                            source_run_id=source_run_id,
                        )
                        if progress is not None:
                            source_step = await session.scalar(
                                select(StepRun)
                                .where(
                                    StepRun.run_id == progress.source_run.id,
                                    StepRun.step_key == progress.source_run.current_step,
                                )
                                .order_by(StepRun.attempt.desc(), StepRun.id.desc())
                                .limit(1)
                            )
                            if source_step is not None:
                                source_step_run_id = source_step.id
    if progress is None:
        return state

    version_payload = {
        "base": state.state_version,
        "writers": progress.version_payload,
    }
    state_version = hashlib.sha256(
        json.dumps(version_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    common = {
        "state_version": state_version,
        "phase": "Soạn song ngữ",
        "human_gate": None,
        "current_worker": None,
        "current_run_id": progress.source_run.id,
        "current_step_run_id": source_step_run_id,
    }
    if not progress.dispatched:
        return state.model_copy(
            update={
                **common,
                "status": "READY",
                "primary_intent": "continue",
                "allowed_intents": ["continue"],
                "blocker_code": None,
                "blocker_message": None,
                "last_checkpoint": (
                    "Outline đã duyệt; sẵn sàng tạo độc lập một lane Writer cho từng locale."
                ),
            }
        )
    if progress.all_complete:
        return state.model_copy(
            update={
                **common,
                "status": "READY",
                "phase": "Chờ kiểm tra chất lượng",
                "primary_intent": "continue",
                "allowed_intents": ["continue"],
                "blocker_code": None,
                "blocker_message": None,
                "last_checkpoint": ("Mọi lane Writer đã có journal_draft; F3 dừng trước Quality."),
            }
        )
    if progress.has_active_job:
        return state.model_copy(
            update={
                **common,
                "status": "RUNNING"
                if any(lane.status == "running" for lane in progress.lanes)
                else "QUEUED",
                "primary_intent": None,
                "allowed_intents": ["cancel"] if progress.has_queued_job else [],
                "blocker_code": None,
                "blocker_message": None,
                "last_checkpoint": (
                    "Các lane Writer đang chạy độc lập; trạng thái từng locale được giữ riêng."
                ),
            }
        )
    if progress.has_exhausted_lane:
        return state.model_copy(
            update={
                **common,
                "status": "BLOCKED",
                "primary_intent": None,
                "allowed_intents": [],
                "blocker_code": "operator_writer_retry_exhausted",
                "blocker_message": (
                    "Một hoặc nhiều lane Writer đã chạm giới hạn retry; cần xử lý thủ công."
                ),
                "last_checkpoint": ("Draft đã hoàn tất được giữ nguyên; lane Writer đã hết retry."),
            }
        )
    if progress.has_retryable_failed_lane:
        return state.model_copy(
            update={
                **common,
                "status": "BLOCKED",
                "primary_intent": "retry",
                "allowed_intents": ["retry"],
                "blocker_code": "operator_writer_lane_failed",
                "blocker_message": (
                    "Một hoặc nhiều lane Writer thất bại; chỉ lane lỗi được phép thử lại."
                ),
                "last_checkpoint": "Draft đã hoàn tất được giữ nguyên; lane lỗi chưa được retry.",
            }
        )
    if progress.has_failed_lane:
        return state.model_copy(
            update={
                **common,
                "status": "BLOCKED",
                "primary_intent": None,
                "allowed_intents": [],
                "blocker_code": "operator_writer_lane_failed",
                "blocker_message": "Lane Writer thất bại ở trạng thái không thể retry an toàn.",
                "last_checkpoint": "Lane Writer thất bại; không có retry an toàn được quảng cáo.",
            }
        )
    return state.model_copy(update=common)


async def _quality_state_overlay(
    session: AsyncSession,
    *,
    state: OperatorState,
) -> OperatorState:
    """Project the bilingual F4 quality fan-out over the legacy operator state."""

    progress = await get_quality_progress(
        session,
        content_case_id=state.content_case_id,
        source_run_id=None,
    )
    if progress is None:
        return state
    version_payload = {
        "base": state.state_version,
        "quality": progress.version_payload,
    }
    dumped = json.dumps(version_payload, sort_keys=True, separators=(",", ":"))
    state_version = hashlib.sha256(dumped.encode()).hexdigest()
    focused = next(
        (lane for lane in progress.lanes if lane.status not in {"qualified", "final_gate_ready"}),
        progress.lanes[0],
    )
    focused_run = focused.writer.run
    focused_step = focused.review.step or focused.audit.step or focused.source_copy.step
    common = {
        "state_version": state_version,
        "current_run_id": focused_run.id if focused_run is not None else state.current_run_id,
        "current_step_run_id": focused_step.id if focused_step is not None else None,
        "phase": "Kiểm tra chất lượng",
        "human_gate": None,
        "current_worker": None,
    }
    pending_final_lanes = [
        lane for lane in progress.lanes if lane.status == "final_gate_ready"
    ]
    if progress.all_qualified and pending_final_lanes:
        final_lane = pending_final_lanes[0]
        return state.model_copy(
            update={
                **common,
                "status": "AWAITING_APPROVAL",
                "phase": "Duyệt cuối",
                "human_gate": "final_review",
                "current_run_id": final_lane.writer.run.id if final_lane.writer.run else None,
                "current_step_run_id": final_lane.final_review.id
                if final_lane.final_review
                else None,
                "primary_intent": None,
                "allowed_intents": [],
                "blocker_code": None,
                "blocker_message": None,
                "last_checkpoint": (
                    "Mọi locale đã qua Quality; vẫn còn locale chờ Founder duyệt cuối."
                ),
            }
        )
    if progress.has_active_job:
        active_lane = next(
            lane
            for lane in progress.lanes
            if any(
                stage.job is not None and stage.job.status in {"queued", "leased"}
                for stage in (lane.review, lane.audit, lane.source_copy)
            )
        )
        active_stage = next(
            stage
            for stage in (active_lane.review, active_lane.audit, active_lane.source_copy)
            if stage.job is not None and stage.job.status in {"queued", "leased"}
        )
        return state.model_copy(
            update={
                **common,
                "status": "RUNNING"
                if active_stage.job and active_stage.job.status == "leased"
                else "QUEUED",
                "current_run_id": active_lane.writer.run.id if active_lane.writer.run else None,
                "current_step_run_id": active_stage.step.id if active_stage.step else None,
                "current_worker": active_stage.job.lease_owner if active_stage.job else None,
                "primary_intent": None,
                "allowed_intents": ["cancel"]
                if active_stage.job and active_stage.job.status == "queued"
                else [],
                "blocker_code": None,
                "blocker_message": None,
                "last_checkpoint": (
                    "Quality lanes đang chạy độc lập; mỗi locale giữ nguyên lineage riêng."
                ),
            }
        )
    if progress.has_content_block:
        return state.model_copy(
            update={
                **common,
                "status": "BLOCKED",
                "primary_intent": None,
                "allowed_intents": [],
                "blocker_code": "operator_quality_blocked",
                "blocker_message": (
                    "Quality phát hiện lỗi nội dung; lane locale bị chặn và không tự retry."
                ),
                "last_checkpoint": (
                    "Quality failure là content failure, không phải technical retry."
                ),
            }
        )
    if progress.has_exhausted_failure:
        return state.model_copy(
            update={
                **common,
                "status": "BLOCKED",
                "primary_intent": None,
                "allowed_intents": [],
                "blocker_code": "operator_quality_retry_exhausted",
                "blocker_message": "Quality job đã hết giới hạn retry; không quảng cáo retry tiếp.",
                "last_checkpoint": "Các artifact locale đã hoàn tất vẫn được giữ nguyên.",
            }
        )
    if progress.has_retryable_failure:
        return state.model_copy(
            update={
                **common,
                "status": "BLOCKED",
                "primary_intent": "retry",
                "allowed_intents": ["retry"],
                "blocker_code": "operator_quality_job_failed",
                "blocker_message": "Quality technical job thất bại; chỉ lane lỗi được retry.",
                "last_checkpoint": "Lane quality đã hoàn tất được giữ nguyên khi xử lý lane lỗi.",
            }
        )
    return state.model_copy(update=common)


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
    if _completion_projection_is_authoritative(state):
        return state
    state = await _outline_state_overlay(session, state=state)
    state = await _angle_continuation_state_overlay(session, state=state)
    state = await _writer_state_overlay(session, state=state)
    return await _quality_state_overlay(session, state=state)


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
    if state.status == "COMPLETE":
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key="complete",
            current_run_id=state.current_run_id,
            current_step_run_id=state.current_step_run_id,
        )
    if state.blocker_code in _AUTHORITATIVE_COMPLETION_BLOCKERS:
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            current_run_id=state.current_run_id,
            current_step_run_id=state.current_step_run_id,
            blocker_code=state.blocker_code,
        )

    run, step = await _bound_focus(session, state=state)
    writer_progress = await get_writer_lane_progress(
        session,
        content_case_id=content_case_id,
        source_run_id=state.current_run_id,
    )
    quality_progress = await get_quality_progress(
        session,
        content_case_id=content_case_id,
        source_run_id=None,
    )
    if quality_progress is not None:
        writer_progress = quality_progress.writer_progress

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

    if quality_progress is not None and quality_progress.has_retryable_failure:
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key="writers_to_quality",
            intent="retry",
            executable=True,
            current_run_id=state.current_run_id,
            current_step_run_id=state.current_step_run_id,
            blocker_code=state.blocker_code,
        )

    if quality_progress is not None and quality_progress.dispatched:
        if state.status in {"QUEUED", "RUNNING"}:
            return ResolvedOperatorAction(
                content_case_id=content_case_id,
                state_version=state.state_version,
                status=state.status,
                action_key="writers_to_quality",
                executable=False,
                current_run_id=state.current_run_id,
                current_step_run_id=state.current_step_run_id,
            )
        if not quality_progress.final_gate_ready:
            return ResolvedOperatorAction(
                content_case_id=content_case_id,
                state_version=state.state_version,
                status=state.status,
                action_key="writers_to_quality",
                executable=False,
                current_run_id=state.current_run_id,
                current_step_run_id=state.current_step_run_id,
                blocker_code=state.blocker_code,
            )

    if writer_progress is not None and writer_progress.all_complete and quality_progress is None:
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key="writers_to_quality",
            intent="continue",
            executable=True,
            current_run_id=writer_progress.source_run.id,
            current_step_run_id=state.current_step_run_id,
        )

    if writer_progress is not None and writer_progress.dispatched:
        exhausted = writer_progress.has_exhausted_lane
        retryable = (
            not exhausted
            and writer_progress.has_retryable_failed_lane
            and state.primary_intent == "retry"
        )
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key="outline_to_writers",
            intent="retry" if retryable else None,
            executable=retryable,
            current_run_id=writer_progress.source_run.id,
            current_step_run_id=state.current_step_run_id,
            blocker_code=("operator_writer_retry_exhausted" if exhausted else state.blocker_code),
        )

    if (
        state.primary_intent == "continue"
        and run is not None
        and (
            run.current_step in _F2_EXECUTABLE_CONTINUATIONS
            or (
                writer_progress is not None
                and not writer_progress.dispatched
                and run.current_step == "outline"
            )
        )
    ):
        continuation_action: OperatorActionKey = _GATE_CONTINUATIONS[run.current_step]
        return ResolvedOperatorAction(
            content_case_id=content_case_id,
            state_version=state.state_version,
            status=state.status,
            action_key=continuation_action,
            intent="continue",
            executable=True,
            current_run_id=run.id,
            current_step_run_id=state.current_step_run_id,
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
        if intent == "cancel" and (previous_job is None or previous_job.status != "queued"):
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


def _writer_job_dedupe_key(
    *,
    command_id: UUID,
    locale: str,
    outline_artifact_id: UUID,
    outline_version: int,
    outline_hash: str,
    outline_approval_id: UUID,
    attempt: int,
) -> str:
    payload = {
        "command_id": str(command_id),
        "locale": locale,
        "outline_artifact_id": str(outline_artifact_id),
        "outline_version": outline_version,
        "outline_hash": outline_hash,
        "outline_approval_id": str(outline_approval_id),
        "attempt": attempt,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"operator:writer:{digest}"


async def _submit_outline_to_writers_command(
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
        action_key="outline_to_writers",
    )
    await lock_operator_idempotency(session, key=key)
    existing = await session.scalar(
        select(OperatorCommand).where(OperatorCommand.idempotency_key == key)
    )
    if existing is not None:
        if existing.content_case_id != content_case_id or existing.request_hash != request_hash:
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
    if resolved.action_key != "outline_to_writers":
        raise OperatorControlError("operator_internal_action_not_approved")
    if intent == "continue" and not resolved.executable:
        raise OperatorControlError("operator_intent_not_allowed")
    if intent == "retry" and resolved.blocker_code == "operator_writer_retry_exhausted":
        raise OperatorControlError("operator_writer_retry_exhausted")
    if intent == "retry" and resolved.intent != "retry":
        raise OperatorControlError("operator_retry_requires_failed_writer_lane")
    progress = await get_writer_lane_progress(
        session,
        content_case_id=content_case_id,
        source_run_id=resolved.current_run_id,
    )
    if progress is None:
        raise OperatorControlError("operator_writer_lineage_missing")

    command = OperatorCommand(
        content_case_id=content_case_id,
        run_id=progress.source_run.id,
        step_run_id=resolved.current_step_run_id,
        job_id=None,
        intent=intent,
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=expected_state_version,
        resolved_action_key="outline_to_writers",
        status="accepted",
        error_code=None,
        actor_id=actor_id,
        state_before=expected_state_version,
        state_after=None,
    )
    session.add(command)
    await session.flush()

    if intent == "cancel":
        if not progress.has_queued_job:
            raise OperatorControlError("operator_cancel_requires_queued_writer_job")
        for lane in progress.lanes:
            job = lane.latest_job
            if job is not None and job.status == "queued":
                job.status = "cancelled"
        command.status = "cancelled"
    else:
        if intent == "continue":
            if progress.dispatched:
                raise OperatorControlError("operator_writer_run_conflict")
            lanes = list(progress.lanes)
        else:
            lanes = [
                lane
                for lane in progress.lanes
                if lane.status == "failed"
                and lane.latest_job is not None
                and lane.latest_job.status in {"failed", "cancelled"}
                and lane.latest_job.attempt < WRITER_MAX_JOB_ATTEMPTS
            ]
            if not lanes:
                raise OperatorControlError("operator_writer_retry_lane_missing")
        for lane in lanes:
            if lane.required_locale not in WRITER_STEP_BY_LOCALE:
                raise OperatorControlError(
                    "operator_writer_locale_unsupported", lane.required_locale
                )
            try:
                handoff = await ensure_writer_run(
                    session,
                    source_run_id=progress.source_run.id,
                    outline_artifact_id=progress.outline_artifact.id,
                    expected_outline_version=progress.outline_artifact.version,
                    expected_outline_hash=progress.outline_artifact.content_hash,
                    outline_approval_id=progress.outline_approval.id,
                    locale=lane.required_locale,
                )
            except WriterGenerationError as exc:
                raise OperatorControlError(exc.code) from exc
            step = lane.step
            if step is None:
                step = StepRun(
                    run_id=handoff.run.id,
                    step_key=WRITER_STEP_BY_LOCALE[lane.required_locale],
                    attempt=1,
                    status="pending",
                    input_artifact_refs_json=[
                        str(handoff.artifact.id),
                        str(progress.outline_artifact.id),
                        f"outline_approval:{progress.outline_approval.id}",
                    ],
                    output_artifact_refs_json=[],
                )
                session.add(step)
                await session.flush()
            elif intent == "retry":
                previous_job = lane.latest_job
                if previous_job is None or previous_job.status not in {"failed", "cancelled"}:
                    raise OperatorControlError("operator_writer_retry_lane_missing")
                if previous_job.attempt >= WRITER_MAX_JOB_ATTEMPTS:
                    raise OperatorControlError("operator_writer_retry_exhausted")
                if step.status != "running":
                    step.status = "running"
                    step.error_json = None
                if handoff.run.status != "running":
                    handoff.run.status = "running"
            previous_job = lane.latest_job
            attempt = 1 if previous_job is None else previous_job.attempt + 1
            queued = await enqueue_job(
                session,
                run_id=handoff.run.id,
                step_run_id=step.id,
                dedupe_key=_writer_job_dedupe_key(
                    command_id=command.id,
                    locale=lane.required_locale,
                    outline_artifact_id=progress.outline_artifact.id,
                    outline_version=progress.outline_artifact.version,
                    outline_hash=progress.outline_artifact.content_hash,
                    outline_approval_id=progress.outline_approval.id,
                    attempt=attempt,
                ),
            )
            queued.attempt = attempt
        command.status = "queued"

    await session.flush()
    settlement_progress = None
    if intent == "cancel":
        settlement_progress = await get_writer_lane_progress(
            session,
            content_case_id=content_case_id,
            source_run_id=progress.source_run.id,
        )
    after = await get_operator_state(
        session,
        content_case_id=content_case_id,
        preflight_checked=True,
    )
    if settlement_progress is not None:
        await settle_writer_commands(
            session,
            content_case_id=content_case_id,
            progress=settlement_progress,
            state_version=after.state_version,
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
        job_id=None,
        replayed=False,
    )


async def _existing_f2_replay(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    intent: OperatorIntent,
    expected_state_version: str,
    idempotency_key: str,
    knowledge_brief_id: UUID | None,
) -> OperatorCommandResult | None:
    """Replay an F2 command before mutable case state can redirect dispatch."""

    key = idempotency_key.strip()
    if not key or len(key) > 200:
        return None
    existing = await session.scalar(
        select(OperatorCommand).where(OperatorCommand.idempotency_key == key)
    )
    if existing is None or existing.resolved_action_key != "angle_to_outline":
        return None
    if knowledge_brief_id is not None:
        raise OperatorControlError("operator_knowledge_brief_binding_start_only")
    if len(expected_state_version) != 64:
        raise OperatorControlError("operator_state_version_invalid")
    request_hash = _command_hash(
        content_case_id=content_case_id,
        intent=intent,
        state_version=expected_state_version,
        action_key="angle_to_outline",
    )
    if existing.content_case_id != content_case_id or existing.request_hash != request_hash:
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

    replay = await _existing_f2_replay(
        session,
        content_case_id=content_case_id,
        intent=intent,
        expected_state_version=expected_state_version,
        idempotency_key=idempotency_key,
        knowledge_brief_id=knowledge_brief_id,
    )
    if replay is not None:
        return replay

    existing = await session.scalar(
        select(OperatorCommand).where(OperatorCommand.idempotency_key == idempotency_key.strip())
    )
    if existing is not None:
        if existing.resolved_action_key == "writers_to_quality":
            return await submit_writers_to_quality_command(
                session,
                content_case_id=content_case_id,
                intent=intent,
                expected_state_version=expected_state_version,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
                resolved_state=await resolve_next_operator_action(
                    session, content_case_id=content_case_id, preflight_checked=True
                ),
            )
        if existing.resolved_action_key == "outline_to_writers":
            return await _submit_outline_to_writers_command(
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
    if resolved.action_key == "outline_to_writers":
        if knowledge_brief_id is not None:
            raise OperatorControlError("operator_knowledge_brief_binding_start_only")
        return await _submit_outline_to_writers_command(
            session,
            content_case_id=content_case_id,
            intent=intent,
            expected_state_version=expected_state_version,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
        )
    if resolved.action_key == "writers_to_quality":
        if knowledge_brief_id is not None:
            raise OperatorControlError("operator_knowledge_brief_binding_start_only")
        return await submit_writers_to_quality_command(
            session,
            content_case_id=content_case_id,
            intent=intent,
            expected_state_version=expected_state_version,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            resolved_state=resolved,
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
