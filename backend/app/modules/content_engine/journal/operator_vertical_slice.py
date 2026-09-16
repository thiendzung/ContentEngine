"""PR4.5 operator adapter for the bounded Start-to-Angle vertical slice.

OPS-02 remains authoritative for already-proven stages. This module intercepts only the
new ``start_to_angle`` stage and canonical required-locale completion semantics.
"""

from __future__ import annotations

import hashlib
import json
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import (
    JournalRequiredLocale,
    OperatorCommand,
)
from app.modules.content_engine.journal.operator_control import (
    OperatorCommandResult,
    OperatorControlError,
    OperatorIntent,
    OperatorState,
    get_operator_state,
    submit_operator_command,
)
from app.modules.content_engine.journal.operator_locking import (
    lock_operator_idempotency,
)
from app.modules.content_engine.journal.operator_preflight import (
    build_journal_operator_preflight,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentVersion,
    LocaleVariant,
)
from app.modules.harness.models import ContentRun, Job, StepRun
from app.modules.harness.persistence import enqueue_job
from app.modules.knowledge.brief_binding import (
    KnowledgeBriefBindingError,
    bind_knowledge_brief_to_run,
)

START_TO_ANGLE_STAGE = "start_to_angle"


def _stable_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def ensure_required_locales(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    source_locale: str,
    required_locales: list[str],
    declared_by: str,
) -> list[JournalRequiredLocale]:
    """Persist immutable case requirements separately from materialized LocaleVariants."""

    source = source_locale.strip().lower()
    actor = declared_by.strip()
    normalized = [value.strip().lower() for value in required_locales]
    if not source or not actor:
        raise OperatorControlError("operator_required_locales_invalid")
    if not normalized or any(not value or len(value) > 32 for value in normalized):
        raise OperatorControlError("operator_required_locales_invalid")
    if len(set(normalized)) != len(normalized):
        raise OperatorControlError("operator_required_locales_duplicate")
    if source not in normalized:
        raise OperatorControlError("operator_source_locale_not_required")

    existing = list(
        (
            await session.scalars(
                select(JournalRequiredLocale)
                .where(JournalRequiredLocale.content_case_id == content_case_id)
                .order_by(JournalRequiredLocale.locale, JournalRequiredLocale.id)
            )
        ).all()
    )
    expected = {
        locale: ("source" if locale == source else "translation")
        for locale in normalized
    }
    if existing:
        actual = {row.locale: row.role for row in existing}
        if actual != expected:
            raise OperatorControlError("operator_required_locales_conflict")
        return existing

    rows = [
        JournalRequiredLocale(
            content_case_id=content_case_id,
            locale=locale,
            role=role,
            declared_by=actor,
        )
        for locale, role in expected.items()
    ]
    session.add_all(rows)
    await session.flush()
    return rows


async def ensure_start_to_angle_step(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> StepRun:
    """Prepare the one real executable PR4.5 stage without creating a Job."""

    run = await session.scalar(
        select(ContentRun).where(ContentRun.id == run_id).with_for_update()
    )
    if run is None:
        raise OperatorControlError("operator_start_run_missing")
    existing = await session.scalar(
        select(StepRun)
        .where(
            StepRun.run_id == run.id,
            StepRun.step_key == START_TO_ANGLE_STAGE,
        )
        .order_by(StepRun.attempt.asc())
        .limit(1)
    )
    if existing is not None:
        return existing
    if run.status != "pending":
        raise OperatorControlError("operator_start_run_not_pending")
    step = StepRun(
        run_id=run.id,
        step_key=START_TO_ANGLE_STAGE,
        attempt=1,
        status="pending",
        input_artifact_refs_json=[],
        output_artifact_refs_json=[],
    )
    session.add(step)
    run.current_step = START_TO_ANGLE_STAGE
    await session.flush()
    return step


async def _start_focus(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> tuple[ContentRun, StepRun, Job | None] | None:
    row = (
        await session.execute(
            select(ContentRun, StepRun)
            .join(StepRun, StepRun.run_id == ContentRun.id)
            .where(
                ContentRun.content_case_id == content_case_id,
                StepRun.step_key == START_TO_ANGLE_STAGE,
            )
            .order_by(
                StepRun.attempt.desc(),
                StepRun.updated_at.desc(),
                StepRun.id.desc(),
            )
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    run, step = row
    job = cast(
        Job | None,
        await session.scalar(
            select(Job)
            .where(Job.step_run_id == step.id)
            .order_by(Job.updated_at.desc(), Job.id.desc())
            .limit(1)
        ),
    )
    return run, step, job


async def _completion_state(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    base: OperatorState,
) -> OperatorState:
    """Replace the temporary OPS-02 locale-count heuristic with persisted requirements."""

    required = {
        row.locale
        for row in (
            await session.scalars(
                select(JournalRequiredLocale).where(
                    JournalRequiredLocale.content_case_id == content_case_id
                )
            )
        ).all()
    }
    if not required:
        return base

    approved = {
        str(locale)
        for locale in (
            await session.scalars(
                select(LocaleVariant.locale)
                .join(ContentItem, ContentItem.locale_variant_id == LocaleVariant.id)
                .join(ContentVersion, ContentVersion.content_item_id == ContentItem.id)
                .where(
                    LocaleVariant.content_case_id == content_case_id,
                    ContentVersion.status.in_(("approved", "published")),
                )
            )
        ).all()
    }
    if base.blocker_code != "operator_completion_requirements_not_wired":
        return base
    missing = sorted(required - approved)
    if missing:
        return base.model_copy(
            update={
                "blocker_code": "operator_required_locales_incomplete",
                "blocker_message": (
                    "Chưa có bản nội dung được duyệt cho mọi locale bắt buộc."
                ),
                "last_checkpoint": f"Locale còn thiếu: {', '.join(missing)}",
            }
        )

    active = await session.scalar(
        select(ContentRun.id)
        .where(
            ContentRun.content_case_id == content_case_id,
            ContentRun.status.in_(("pending", "running", "waiting_approval")),
        )
        .limit(1)
    )
    if active is not None:
        return base
    return base.model_copy(
        update={
            "status": "COMPLETE",
            "phase": "Hoàn tất",
            "primary_intent": None,
            "allowed_intents": [],
            "human_gate": None,
            "blocker_code": None,
            "blocker_message": None,
            "last_checkpoint": (
                "Mọi locale bắt buộc đã có ContentVersion được duyệt."
            ),
        }
    )


async def get_operator_state_v45(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    preflight_checked: bool = False,
) -> OperatorState:
    base = await get_operator_state(session, content_case_id=content_case_id)
    focus = await _start_focus(session, content_case_id=content_case_id)
    if focus is None:
        return await _completion_state(
            session,
            content_case_id=content_case_id,
            base=base,
        )

    run, step, job = focus
    if run.status == "waiting_approval" or run.current_step != START_TO_ANGLE_STAGE:
        return await _completion_state(
            session,
            content_case_id=content_case_id,
            base=base,
        )
    if job is not None and job.status in {"queued", "leased"}:
        return base
    if job is not None and job.status in {"failed", "cancelled"} and step.status in {
        "pending",
        "running",
    }:
        return base.model_copy(
            update={
                "status": "BLOCKED",
                "phase": "Khởi động đến Angle",
                "primary_intent": "retry",
                "allowed_intents": ["retry"],
                "current_run_id": run.id,
                "current_step_run_id": step.id,
                "blocker_code": "operator_job_failed",
                "blocker_message": (
                    "Tác vụ nền thất bại; có thể thử lại nếu trạng thái còn hợp lệ."
                ),
            }
        )
    if step.status in {"pending", "running"} and job is None:
        if not preflight_checked:
            preflight = await build_journal_operator_preflight(session)
            if preflight.get("status") != "READY":
                return base.model_copy(
                    update={
                        "status": "BLOCKED",
                        "phase": "Khởi động đến Angle",
                        "primary_intent": None,
                        "allowed_intents": [],
                        "current_run_id": run.id,
                        "current_step_run_id": step.id,
                        "blocker_code": "operator_preflight_blocked",
                        "blocker_message": (
                            "Điều kiện chạy Journal chưa sẵn sàng; kiểm tra preflight."
                        ),
                        "last_checkpoint": (
                            "Start-to-Angle chưa được phép enqueue vì preflight đang BLOCKED."
                        ),
                    }
                )
        intent: OperatorIntent = "start" if run.status == "pending" else "continue"
        return base.model_copy(
            update={
                "status": "READY",
                "phase": "Khởi động đến Angle",
                "primary_intent": intent,
                "allowed_intents": [intent],
                "current_run_id": run.id,
                "current_step_run_id": step.id,
                "blocker_code": None,
                "blocker_message": None,
                "last_checkpoint": (
                    "Stage Start-to-Angle đã được chuẩn bị và chưa có Job."
                ),
            }
        )
    return await _completion_state(
        session,
        content_case_id=content_case_id,
        base=base,
    )


def _request_hash(
    *,
    content_case_id: UUID,
    intent: OperatorIntent,
    state_version: str,
    knowledge_brief_id: UUID | None = None,
) -> str:
    payload: dict[str, object] = {
        "content_case_id": str(content_case_id),
        "intent": intent,
        "expected_state_version": state_version,
    }
    if knowledge_brief_id is not None:
        payload["knowledge_brief_id"] = str(knowledge_brief_id)
    return _stable_hash(payload)


async def submit_operator_command_v45(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    intent: OperatorIntent,
    expected_state_version: str,
    idempotency_key: str,
    knowledge_brief_id: UUID | None = None,
    actor_id: str = "founder",
) -> OperatorCommandResult:
    """Dispatch OPS-02 commands unchanged unless the new bounded stage owns the case."""

    if knowledge_brief_id is not None and intent != "start":
        raise OperatorControlError("operator_knowledge_brief_binding_start_only")

    focus = await _start_focus(session, content_case_id=content_case_id)
    if focus is None:
        if knowledge_brief_id is not None:
            raise OperatorControlError("operator_knowledge_brief_binding_stage_required")
        return await submit_operator_command(
            session,
            content_case_id=content_case_id,
            intent=intent,
            expected_state_version=expected_state_version,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
        )

    run, step, job = focus
    if run.current_step != START_TO_ANGLE_STAGE and not (
        job is not None
        and job.step_run_id == step.id
        and job.status in {"queued", "leased"}
    ):
        if knowledge_brief_id is not None:
            raise OperatorControlError("operator_knowledge_brief_binding_stage_required")
        return await submit_operator_command(
            session,
            content_case_id=content_case_id,
            intent=intent,
            expected_state_version=expected_state_version,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
        )

    key = idempotency_key.strip()
    if not key or len(key) > 200:
        raise OperatorControlError("operator_idempotency_key_invalid")
    if len(expected_state_version) != 64:
        raise OperatorControlError("operator_state_version_invalid")
    request_hash = _request_hash(
        content_case_id=content_case_id,
        intent=intent,
        state_version=expected_state_version,
        knowledge_brief_id=knowledge_brief_id,
    )

    await lock_operator_idempotency(session, key=key)
    existing = await session.scalar(
        select(OperatorCommand).where(OperatorCommand.idempotency_key == key)
    )
    if existing is not None:
        if (
            existing.request_hash != request_hash
            or existing.content_case_id != content_case_id
        ):
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
        .where(
            ContentCase.id == content_case_id,
            ContentCase.content_type == "journal",
        )
        .with_for_update()
    )
    if locked_case is None:
        raise OperatorControlError("operator_case_not_found")

    state = await get_operator_state_v45(
        session,
        content_case_id=content_case_id,
        preflight_checked=True,
    )
    if state.state_version != expected_state_version:
        raise OperatorControlError("operator_state_stale")
    if intent not in state.allowed_intents:
        raise OperatorControlError("operator_intent_not_allowed")
    if intent in {"start", "continue", "retry"}:
        preflight = await build_journal_operator_preflight(session)
        if preflight.get("status") != "READY":
            raise OperatorControlError("operator_preflight_blocked")

    focus = await _start_focus(session, content_case_id=content_case_id)
    if focus is None:
        raise OperatorControlError("operator_runnable_step_missing")
    run, step, job = focus
    if step.step_key != START_TO_ANGLE_STAGE:
        raise OperatorControlError("operator_internal_action_not_approved")

    if knowledge_brief_id is not None:
        try:
            await bind_knowledge_brief_to_run(
                session,
                run_id=run.id,
                knowledge_brief_id=knowledge_brief_id,
                bound_by=actor_id,
            )
        except KnowledgeBriefBindingError as exc:
            raise OperatorControlError(exc.code) from exc

    command = OperatorCommand(
        content_case_id=content_case_id,
        run_id=run.id,
        step_run_id=step.id,
        job_id=None,
        intent=intent,
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=expected_state_version,
        resolved_action_key=START_TO_ANGLE_STAGE,
        status="accepted",
        error_code=None,
        actor_id=actor_id,
        state_before=expected_state_version,
        state_after=None,
    )
    session.add(command)
    await session.flush()

    if intent == "cancel":
        if job is None or job.status != "queued":
            raise OperatorControlError("operator_cancel_requires_queued_job")
        job.status = "cancelled"
        command.job_id = job.id
        command.status = "cancelled"
    elif intent == "resume":
        raise OperatorControlError("operator_resume_not_wired")
    else:
        if step.status not in {"pending", "running"}:
            raise OperatorControlError("operator_step_not_queueable")
        if intent == "retry" and (
            job is None or job.status not in {"failed", "cancelled"}
        ):
            raise OperatorControlError("operator_retry_requires_failed_job")
        dedupe = f"operator:{_stable_hash({'command_id': str(command.id), 'key': key})}"
        queued = await enqueue_job(
            session,
            run_id=run.id,
            step_run_id=step.id,
            dedupe_key=dedupe,
        )
        if intent == "retry" and job is not None:
            queued.attempt = job.attempt + 1
        command.job_id = queued.id
        command.status = "queued"

    await session.flush()
    after = await get_operator_state_v45(
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


__all__ = [
    "START_TO_ANGLE_STAGE",
    "ensure_required_locales",
    "ensure_start_to_angle_step",
    "get_operator_state_v45",
    "submit_operator_command_v45",
]
