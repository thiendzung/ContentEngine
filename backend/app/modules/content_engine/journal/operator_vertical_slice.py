"""PR4.5 operator adapter for the bounded Start-to-Angle vertical slice.

OPS-02 remains authoritative for already-proven stages. This module intercepts only the
new ``start_to_angle`` stage and canonical required-locale completion semantics.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal, cast
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
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
)
from app.modules.harness.models import Approval, Artifact, ContentRun, Job, StepRun
from app.modules.harness.persistence import enqueue_job
from app.modules.knowledge.brief_binding import (
    KnowledgeBriefBindingError,
    bind_knowledge_brief_to_run,
)

START_TO_ANGLE_STAGE = "start_to_angle"
_JOURNAL_LOCALE_ALIASES = {
    "vi": "vi-VN",
    "vi-vn": "vi-VN",
    "en": "en",
}
CompletionBindingState = Literal["complete", "missing", "invalid"]
_COMPLETION_BINDING_BLOCKER = "operator_completion_binding_invalid"


def normalize_journal_locale(value: str) -> str:
    """Return one canonical Journal locale or fail closed."""

    normalized = value.strip().lower()
    locale = _JOURNAL_LOCALE_ALIASES.get(normalized)
    if locale is None:
        raise OperatorControlError("operator_locale_unsupported", value)
    return locale


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

    source = normalize_journal_locale(source_locale)
    actor = declared_by.strip()
    normalized = [normalize_journal_locale(value) for value in required_locales]
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
    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None:
        raise OperatorControlError("operator_case_not_found")
    opportunity = await session.get(ContentOpportunity, content_case.content_opportunity_id)
    if opportunity is None:
        raise OperatorControlError("operator_opportunity_not_found")

    if existing:
        actual = {row.locale: row.role for row in existing}
        if actual != expected:
            raise OperatorControlError("operator_required_locales_conflict")
    else:
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
        existing = rows

    variants = list(
        (
            await session.scalars(
                select(LocaleVariant).where(
                    LocaleVariant.content_case_id == content_case_id,
                    LocaleVariant.locale.in_(normalized),
                )
            )
        ).all()
    )
    by_locale: dict[str, list[LocaleVariant]] = {}
    for variant in variants:
        by_locale.setdefault(variant.locale, []).append(variant)
    for locale in normalized:
        if len(by_locale.get(locale, [])) > 1:
            raise OperatorControlError("operator_locale_variant_ambiguous", locale)
    source_variants = by_locale.get(source, [])
    if len(source_variants) != 1:
        raise OperatorControlError("operator_source_locale_variant_missing")
    source_variant = source_variants[0]
    for locale in normalized:
        if by_locale.get(locale):
            continue
        session.add(
            LocaleVariant(
                content_case_id=content_case_id,
                locale=locale,
                content_role=source_variant.content_role,
                primary_question=source_variant.primary_question,
                primary_intent=source_variant.primary_intent,
                secondary_intent=source_variant.secondary_intent,
                primary_query=source_variant.primary_query,
                keyword_notes_json=list(source_variant.keyword_notes_json),
                emotion_arc_json=list(source_variant.emotion_arc_json),
                must_include_json=list(source_variant.must_include_json),
                must_not_claim_json=list(source_variant.must_not_claim_json),
                status=source_variant.status,
            )
        )
    await session.flush()
    return existing


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


async def _required_locale_completion_binding(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    locale: str,
) -> tuple[CompletionBindingState, dict[str, object]]:
    """Resolve one required locale through the exact durable final-approval lineage."""

    payload: dict[str, object] = {"locale": locale}
    variants = list(
        (
            await session.scalars(
                select(LocaleVariant).where(
                    LocaleVariant.content_case_id == content_case_id,
                    LocaleVariant.locale == locale,
                )
            )
        ).all()
    )
    payload["variant_ids"] = [str(row.id) for row in variants]
    if not variants:
        payload["reason"] = "locale_variant_missing"
        return "missing", payload
    if len(variants) != 1:
        payload["reason"] = "locale_variant_ambiguous"
        return "invalid", payload
    variant = variants[0]

    items = list(
        (
            await session.scalars(
                select(ContentItem).where(
                    ContentItem.content_case_id == content_case_id,
                    ContentItem.locale_variant_id == variant.id,
                )
            )
        ).all()
    )
    payload["content_item_ids"] = [str(row.id) for row in items]
    if not items:
        payload["reason"] = "content_item_missing"
        return "missing", payload
    if len(items) != 1:
        payload["reason"] = "content_item_ambiguous"
        return "invalid", payload
    item = items[0]
    if item.content_type != "journal":
        payload["reason"] = "content_item_type_mismatch"
        return "invalid", payload

    versions = list(
        (
            await session.scalars(
                select(ContentVersion)
                .where(
                    ContentVersion.content_item_id == item.id,
                    ContentVersion.status.in_(("approved", "published")),
                )
                .order_by(ContentVersion.version_no, ContentVersion.id)
            )
        ).all()
    )
    payload["active_content_versions"] = [
        {
            "id": str(row.id),
            "version_no": row.version_no,
            "status": row.status,
            "final_artifact_id": str(row.final_artifact_id)
            if row.final_artifact_id is not None
            else None,
            "created_by_run_id": str(row.created_by_run_id)
            if row.created_by_run_id is not None
            else None,
            "content_hash": _stable_hash(row.content_json),
        }
        for row in versions
    ]
    if not versions:
        payload["reason"] = "active_content_version_missing"
        return "missing", payload
    if len(versions) != 1:
        payload["reason"] = "active_content_version_ambiguous"
        return "invalid", payload
    version = versions[0]
    if version.final_artifact_id is None or version.created_by_run_id is None:
        payload["reason"] = "content_version_final_binding_missing"
        return "invalid", payload

    final_artifact = await session.get(Artifact, version.final_artifact_id)
    writer_run = await session.get(ContentRun, version.created_by_run_id)
    if final_artifact is None or writer_run is None:
        payload["reason"] = "content_version_final_binding_missing"
        return "invalid", payload
    payload["final_artifact"] = {
        "id": str(final_artifact.id),
        "run_id": str(final_artifact.run_id),
        "artifact_type": final_artifact.artifact_type,
        "locale": final_artifact.locale,
        "version": final_artifact.version,
        "content_hash": final_artifact.content_hash,
    }
    payload["writer_run"] = {
        "id": str(writer_run.id),
        "content_case_id": str(writer_run.content_case_id),
        "locale_variant_id": str(writer_run.locale_variant_id),
        "content_item_id": str(writer_run.content_item_id)
        if writer_run.content_item_id is not None
        else None,
        "status": writer_run.status,
    }
    if (
        final_artifact.artifact_type != "final_content"
        or final_artifact.locale != locale
        or final_artifact.run_id != writer_run.id
        or writer_run.content_case_id != content_case_id
        or writer_run.locale_variant_id != variant.id
        or writer_run.content_item_id != item.id
        or writer_run.status != "completed"
        or version.final_artifact_id != final_artifact.id
        or version.created_by_run_id != writer_run.id
        or final_artifact.content_json is None
        or version.content_json != final_artifact.content_json
    ):
        payload["reason"] = "content_version_final_binding_mismatch"
        return "invalid", payload

    approvals = list(
        (
            await session.scalars(
                select(Approval)
                .where(
                    Approval.run_id == writer_run.id,
                    Approval.step_key == "final_review",
                    Approval.artifact_id == final_artifact.id,
                )
                .order_by(Approval.created_at, Approval.id)
            )
        ).all()
    )
    payload["final_approvals"] = [
        {
            "id": str(row.id),
            "artifact_id": str(row.artifact_id),
            "decision": row.decision,
            "actor_id": row.actor_id,
        }
        for row in approvals
    ]
    if len(approvals) != 1:
        payload["reason"] = "final_approval_missing_or_ambiguous"
        return "invalid", payload
    approval = approvals[0]
    if (
        approval.artifact_id != final_artifact.id
        or approval.decision != "approved"
        or approval.actor_id != "founder"
    ):
        payload["reason"] = "final_approval_binding_mismatch"
        return "invalid", payload

    payload["reason"] = None
    return "complete", payload


async def _completion_state(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    base: OperatorState,
) -> OperatorState:
    """Derive COMPLETE only from required locales and their exact final lineage."""

    required_rows = list(
        (
            await session.scalars(
                select(JournalRequiredLocale)
                .where(JournalRequiredLocale.content_case_id == content_case_id)
                .order_by(JournalRequiredLocale.locale, JournalRequiredLocale.id)
            )
        ).all()
    )
    if not required_rows:
        return base
    required = [row.locale for row in required_rows]

    bindings: list[dict[str, object]] = []
    states: dict[str, CompletionBindingState] = {}
    for locale in required:
        binding_state, payload = await _required_locale_completion_binding(
            session,
            content_case_id=content_case_id,
            locale=locale,
        )
        states[locale] = binding_state
        bindings.append(payload)

    completion_version = _stable_hash(
        {
            "base": base.state_version,
            "required_locales": required,
            "bindings": bindings,
        }
    )
    invalid = sorted(locale for locale, state in states.items() if state == "invalid")
    if invalid:
        return base.model_copy(
            update={
                "state_version": completion_version,
                "status": "BLOCKED",
                "primary_intent": None,
                "allowed_intents": [],
                "human_gate": None,
                "blocker_code": _COMPLETION_BINDING_BLOCKER,
                "blocker_message": (
                    "Liên kết bản duyệt cuối không nhất quán; chưa được phép đánh dấu hoàn tất."
                ),
                "last_checkpoint": (
                    "Locale có liên kết hoàn tất không hợp lệ: " + ", ".join(invalid)
                ),
            }
        )

    missing = sorted(locale for locale, state in states.items() if state == "missing")
    if missing:
        if base.blocker_code != "operator_completion_requirements_not_wired":
            return base
        return base.model_copy(
            update={
                "state_version": completion_version,
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
            "state_version": completion_version,
            "status": "COMPLETE",
            "phase": "Hoàn tất",
            "primary_intent": None,
            "allowed_intents": [],
            "human_gate": None,
            "blocker_code": None,
            "blocker_message": None,
            "last_checkpoint": (
                "Mọi locale bắt buộc đã có ContentVersion khớp exact final_content "
                "và Founder Approval."
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
