"""Fail-closed operator control plane for Journal production.

The service exposes operator intent, never arbitrary internal stage execution. Long-running
work is represented by the durable Job queue only after a real ContentRun and StepRun have
been resolved from persisted state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import (
    AngleApproval,
    OperatorCommand,
    OutlineApproval,
)
from app.modules.content_engine.journal.operator_locking import lock_operator_idempotency
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
)
from app.modules.harness.models import Approval, ContentRun, Job, QualityEvaluation, StepRun
from app.modules.harness.persistence import enqueue_job
from app.modules.research.evidence.persistence import ensure_selected_content_case
from app.modules.system.preflight import build_operational_preflight

OperatorIntent = Literal["start", "continue", "resume", "retry", "cancel"]
OperatorStatus = Literal[
    "NOT_READY",
    "READY",
    "QUEUED",
    "RUNNING",
    "AWAITING_APPROVAL",
    "BLOCKED",
    "COMPLETE",
]
HumanGate = Literal["angle", "outline", "final_review"]

_EXECUTABLE_STAGE = "review_revise_en"
_GATE_STEPS: dict[str, HumanGate] = {
    "angle": "angle",
    "outline": "outline",
    "final_review": "final_review",
}
_PHASE_LABELS = {
    "angle": "Góc tiếp cận",
    "outline": "Dàn ý",
    "writer_vi": "Soạn tiếng Việt",
    "writer_en": "Soạn tiếng Anh",
    "review_revise_vi": "Rà soát tiếng Việt",
    "review_revise_en": "Rà soát tiếng Anh",
    "assertion_audit_vi": "Kiểm tra dữ kiện tiếng Việt",
    "assertion_audit_en": "Kiểm tra dữ kiện tiếng Anh",
    "final_review": "Duyệt cuối",
}
_BLOCKER_MESSAGES = {
    "operator_pipeline_start_not_wired": (
        "Case đã được tạo nhưng chưa có bước thực thi bền vững đã được backend chuẩn bị."
    ),
    "operator_action_not_wired": "Bước hiện tại chưa có adapter vận hành được phê duyệt.",
    "operator_completion_requirements_not_wired": (
        "Đã có nội dung được duyệt nhưng điều kiện hoàn tất song ngữ chưa được backend khóa."
    ),
    "operator_gate_already_decided": (
        "Cổng duyệt đã được ghi nhận; bước tiếp theo chưa được backend chuẩn bị."
    ),
    "operator_unknown_human_gate": "Workflow đang chờ duyệt ở một cổng chưa được ánh xạ.",
    "operator_run_failed": "Lần chạy gần nhất đã thất bại và chưa có đường phục hồi an toàn.",
    "operator_step_failed": "Bước gần nhất đã thất bại và chưa thể thử lại an toàn.",
    "operator_job_failed": (
        "Tác vụ nền gần nhất thất bại; có thể thử lại nếu trạng thái còn hợp lệ."
    ),
    "operator_preflight_blocked": "Hệ thống chưa sẵn sàng để nhận tác vụ thực thi.",
    "operator_state_stale": "Trạng thái đã thay đổi. Hãy tải lại trước khi thao tác.",
    "operator_intent_not_allowed": "Thao tác này không hợp lệ ở trạng thái hiện tại.",
}


class OperatorControlError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


class OperatorQualitySummary(BaseModel):
    passed: int = 0
    warned: int = 0
    failed: int = 0


class OperatorState(BaseModel):
    content_case_id: UUID
    state_version: str
    status: OperatorStatus
    phase: str
    primary_intent: OperatorIntent | None = None
    allowed_intents: list[OperatorIntent] = Field(default_factory=list)
    human_gate: HumanGate | None = None
    current_run_id: UUID | None = None
    current_step_run_id: UUID | None = None
    current_worker: str | None = None
    last_checkpoint: str | None = None
    quality_summary: OperatorQualitySummary | None = None
    blocker_code: str | None = None
    blocker_message: str | None = None


class OperatorCommandResult(BaseModel):
    command_id: UUID
    content_case_id: UUID
    intent: OperatorIntent
    status: str
    state_before: str
    state_after: str | None
    job_id: UUID | None = None
    replayed: bool = False


class CreatedJournalCase(BaseModel):
    content_case_id: UUID
    reused: bool
    source_locale_variant_id: UUID
    state: OperatorState


def _stable_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _message(code: str | None) -> str | None:
    if code is None:
        return None
    return _BLOCKER_MESSAGES.get(code, "Workflow bị chặn bởi chính sách an toàn của backend.")


async def create_or_reuse_journal_case(
    session: AsyncSession,
    *,
    content_opportunity_id: UUID,
    expected_opportunity_version: int,
) -> CreatedJournalCase:
    opportunity = await session.get(ContentOpportunity, content_opportunity_id)
    if opportunity is None:
        raise OperatorControlError("operator_opportunity_not_found")
    if opportunity.version != expected_opportunity_version:
        raise OperatorControlError("operator_opportunity_stale")
    if opportunity.selected_by is None or opportunity.selected_at is None:
        raise OperatorControlError("operator_opportunity_not_selected")
    if opportunity.suggested_content_type != "journal":
        raise OperatorControlError("operator_opportunity_not_journal")
    if opportunity.decision != "CREATE":
        raise OperatorControlError("operator_create_requires_create_opportunity")

    existing = list(
        (
            await session.scalars(
                select(ContentCase).where(
                    ContentCase.content_opportunity_id == opportunity.id,
                    ContentCase.content_type == "journal",
                )
            )
        ).all()
    )
    if len(existing) > 1:
        raise OperatorControlError("operator_case_duplicate_binding")
    reused = bool(existing)
    try:
        content_case, opportunity, _ = await ensure_selected_content_case(
            session,
            project_id=opportunity.project_id,
            content_opportunity_id=opportunity.id,
            need_hypothesis_id=opportunity.need_hypothesis_id,
        )
    except ValueError as exc:
        raise OperatorControlError(str(exc)) from exc

    variants = list(
        (
            await session.scalars(
                select(LocaleVariant).where(LocaleVariant.content_case_id == content_case.id)
            )
        ).all()
    )
    source_variant = next((row for row in variants if row.locale == opportunity.locale), None)
    if source_variant is None:
        source_variant = LocaleVariant(
            content_case_id=content_case.id,
            locale=opportunity.locale,
            content_role=opportunity.suggested_role or "primary",
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

    state = await get_operator_state(session, content_case_id=content_case.id)
    return CreatedJournalCase(
        content_case_id=content_case.id,
        reused=reused,
        source_locale_variant_id=source_variant.id,
        state=state,
    )


async def _case_rows(
    session: AsyncSession,
    content_case_id: UUID,
) -> tuple[ContentCase, list[LocaleVariant], list[ContentRun]]:
    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None or content_case.content_type != "journal":
        raise OperatorControlError("operator_case_not_found")
    variants = list(
        (
            await session.scalars(
                select(LocaleVariant)
                .where(LocaleVariant.content_case_id == content_case.id)
                .order_by(LocaleVariant.locale, LocaleVariant.id)
            )
        ).all()
    )
    runs = list(
        (
            await session.scalars(
                select(ContentRun)
                .where(ContentRun.content_case_id == content_case.id)
                .order_by(ContentRun.updated_at, ContentRun.id)
            )
        ).all()
    )
    return content_case, variants, runs


async def _latest_step(session: AsyncSession, run: ContentRun | None) -> StepRun | None:
    if run is None:
        return None
    if run.current_step:
        exact = cast(
            StepRun | None,
            await session.scalar(
                select(StepRun)
                .where(StepRun.run_id == run.id, StepRun.step_key == run.current_step)
                .order_by(StepRun.attempt.desc())
                .limit(1)
            ),
        )
        if exact is not None:
            return exact
    return cast(
        StepRun | None,
        await session.scalar(
            select(StepRun)
            .where(StepRun.run_id == run.id)
            .order_by(StepRun.updated_at.desc(), StepRun.id.desc())
            .limit(1)
        ),
    )


async def _latest_job(session: AsyncSession, step: StepRun | None) -> Job | None:
    if step is None:
        return None
    return cast(
        Job | None,
        await session.scalar(
            select(Job)
            .where(Job.step_run_id == step.id)
            .order_by(Job.updated_at.desc(), Job.id.desc())
            .limit(1)
        ),
    )


async def _operator_focus(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    runs: list[ContentRun],
) -> tuple[ContentRun | None, StepRun | None, Job | None]:
    """Choose the currently actionable persisted run/step, not an arbitrary latest run."""
    if not runs:
        return None, None, None

    executable = (
        await session.execute(
            select(ContentRun, StepRun)
            .join(StepRun, StepRun.run_id == ContentRun.id)
            .where(
                ContentRun.content_case_id == content_case_id,
                StepRun.step_key == _EXECUTABLE_STAGE,
                StepRun.status.in_(("pending", "running", "failed")),
                ContentRun.status.in_(("pending", "running", "failed")),
            )
            .order_by(StepRun.updated_at.desc(), StepRun.attempt.desc(), StepRun.id.desc())
            .limit(1)
        )
    ).first()
    if executable is not None:
        run, step = executable
        return run, step, await _latest_job(session, step)

    waiting = [row for row in runs if row.status == "waiting_approval"]
    if waiting:
        run = max(waiting, key=lambda row: (row.updated_at, str(row.id)))
        step = await _latest_step(session, run)
        return run, step, await _latest_job(session, step)

    active = [row for row in runs if row.status in {"pending", "running", "failed"}]
    if active:
        run = max(active, key=lambda row: (row.updated_at, str(row.id)))
        step = await _latest_step(session, run)
        return run, step, await _latest_job(session, step)

    run = max(runs, key=lambda row: (row.updated_at, str(row.id)))
    step = await _latest_step(session, run)
    return run, step, await _latest_job(session, step)


async def _quality_summary(
    session: AsyncSession,
    run: ContentRun | None,
) -> OperatorQualitySummary | None:
    if run is None:
        return None
    rows = (
        await session.execute(
            select(QualityEvaluation.result, func.count(QualityEvaluation.id))
            .where(QualityEvaluation.run_id == run.id)
            .group_by(QualityEvaluation.result)
        )
    ).all()
    if not rows:
        return None
    counts = {str(result): int(count) for result, count in rows}
    return OperatorQualitySummary(
        passed=counts.get("pass", 0),
        warned=counts.get("warn", 0),
        failed=counts.get("fail", 0),
    )


async def _approved_version_count(session: AsyncSession, content_case_id: UUID) -> int:
    value = await session.scalar(
        select(func.count(ContentVersion.id))
        .join(ContentItem, ContentItem.id == ContentVersion.content_item_id)
        .where(
            ContentItem.content_case_id == content_case_id,
            ContentVersion.status.in_(("approved", "published")),
        )
    )
    return int(value or 0)


async def _approval_ids(
    session: AsyncSession,
    run_ids: list[UUID],
) -> tuple[list[AngleApproval], list[OutlineApproval], list[Approval]]:
    if not run_ids:
        return [], [], []
    angles = list(
        (
            await session.scalars(
                select(AngleApproval)
                .where(AngleApproval.run_id.in_(run_ids))
                .order_by(AngleApproval.created_at, AngleApproval.id)
            )
        ).all()
    )
    outlines = list(
        (
            await session.scalars(
                select(OutlineApproval)
                .where(OutlineApproval.run_id.in_(run_ids))
                .order_by(OutlineApproval.created_at, OutlineApproval.id)
            )
        ).all()
    )
    finals = list(
        (
            await session.scalars(
                select(Approval)
                .where(Approval.run_id.in_(run_ids), Approval.step_key == "final_review")
                .order_by(Approval.created_at, Approval.id)
            )
        ).all()
    )
    return angles, outlines, finals


async def _gate_decided(
    session: AsyncSession,
    *,
    run_id: UUID,
    gate: HumanGate,
) -> bool:
    if gate == "angle":
        row = await session.scalar(
            select(AngleApproval.id).where(AngleApproval.run_id == run_id).limit(1)
        )
        return row is not None
    if gate == "outline":
        row = await session.scalar(
            select(OutlineApproval.id).where(OutlineApproval.run_id == run_id).limit(1)
        )
        return row is not None
    row = await session.scalar(
        select(Approval.id)
        .where(Approval.run_id == run_id, Approval.step_key == "final_review")
        .limit(1)
    )
    return row is not None


async def _state_snapshot(
    session: AsyncSession,
    content_case_id: UUID,
) -> tuple[
    ContentCase,
    list[LocaleVariant],
    list[ContentRun],
    ContentRun | None,
    StepRun | None,
    Job | None,
    str,
]:
    content_case, variants, runs = await _case_rows(session, content_case_id)
    run, step, job = await _operator_focus(
        session,
        content_case_id=content_case_id,
        runs=runs,
    )
    angles, outlines, finals = await _approval_ids(session, [row.id for row in runs])

    payload = {
        "case": {
            "id": str(content_case.id),
            "status": content_case.status,
            "updated_at": _timestamp(content_case.updated_at),
        },
        "variants": [
            {
                "id": str(row.id),
                "locale": row.locale,
                "status": row.status,
                "updated_at": _timestamp(row.updated_at),
            }
            for row in variants
        ],
        "runs": [
            {
                "id": str(row.id),
                "status": row.status,
                "current_step": row.current_step,
                "failure_code": row.failure_code,
                "updated_at": _timestamp(row.updated_at),
            }
            for row in runs
        ],
        "focus": {
            "run_id": str(run.id) if run else None,
            "step_run_id": str(step.id) if step else None,
            "job_id": str(job.id) if job else None,
        },
        "step": None
        if step is None
        else {
            "id": str(step.id),
            "step_key": step.step_key,
            "attempt": step.attempt,
            "status": step.status,
            "error": step.error_json,
            "updated_at": _timestamp(step.updated_at),
        },
        "job": None
        if job is None
        else {
            "id": str(job.id),
            "status": job.status,
            "attempt": job.attempt,
            "lease_owner": job.lease_owner,
            "lease_expires_at": _timestamp(job.lease_expires_at),
            "updated_at": _timestamp(job.updated_at),
        },
        "angle_approvals": [str(row.id) for row in angles],
        "outline_approvals": [str(row.id) for row in outlines],
        "final_approvals": [
            {"id": str(row.id), "decision": row.decision} for row in finals
        ],
    }
    return content_case, variants, runs, run, step, job, _stable_hash(payload)


async def get_operator_state(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> OperatorState:
    _, variants, _, run, step, job, version = await _state_snapshot(
        session,
        content_case_id,
    )
    quality = await _quality_summary(session, run)
    approved_versions = await _approved_version_count(session, content_case_id)

    if variants and approved_versions >= len(variants):
        code = "operator_completion_requirements_not_wired"
        return OperatorState(
            content_case_id=content_case_id,
            state_version=version,
            status="BLOCKED",
            phase="Chờ điều kiện hoàn tất",
            current_run_id=run.id if run else None,
            current_step_run_id=step.id if step else None,
            quality_summary=quality,
            blocker_code=code,
            blocker_message=_message(code),
            last_checkpoint=(
                "Đã có ContentVersion được duyệt cho mọi locale hiện có, nhưng required_locales "
                "chưa được persist nên backend không được kết luận COMPLETE."
            ),
        )
    if run is None:
        code = "operator_pipeline_start_not_wired"
        return OperatorState(
            content_case_id=content_case_id,
            state_version=version,
            status="NOT_READY",
            phase="Khởi tạo",
            quality_summary=quality,
            blocker_code=code,
            blocker_message=_message(code),
        )

    gate = _GATE_STEPS.get(run.current_step or "") if run.status == "waiting_approval" else None
    if gate is not None:
        if not await _gate_decided(session, run_id=run.id, gate=gate):
            return OperatorState(
                content_case_id=content_case_id,
                state_version=version,
                status="AWAITING_APPROVAL",
                phase=_PHASE_LABELS.get(run.current_step or "", "Chờ duyệt"),
                human_gate=gate,
                current_run_id=run.id,
                current_step_run_id=step.id if step else None,
                quality_summary=quality,
                last_checkpoint="Đã dừng tại cổng duyệt bắt buộc.",
            )
        code = "operator_gate_already_decided"
        return OperatorState(
            content_case_id=content_case_id,
            state_version=version,
            status="BLOCKED",
            phase=_PHASE_LABELS.get(run.current_step or "", "Đã duyệt"),
            current_run_id=run.id,
            current_step_run_id=step.id if step else None,
            quality_summary=quality,
            blocker_code=code,
            blocker_message=_message(code),
            last_checkpoint="Approval đã persist; đang chờ bước tiếp theo được chuẩn bị.",
        )
    if run.status == "waiting_approval":
        code = "operator_unknown_human_gate"
        return OperatorState(
            content_case_id=content_case_id,
            state_version=version,
            status="BLOCKED",
            phase=_PHASE_LABELS.get(run.current_step or "", "Chờ duyệt"),
            current_run_id=run.id,
            current_step_run_id=step.id if step else None,
            quality_summary=quality,
            blocker_code=code,
            blocker_message=_message(code),
        )

    phase_key = step.step_key if step else (run.current_step or "")
    phase = _PHASE_LABELS.get(phase_key, "Đang xử lý")
    if job is not None and job.status == "queued":
        return OperatorState(
            content_case_id=content_case_id,
            state_version=version,
            status="QUEUED",
            phase=phase,
            allowed_intents=["cancel"],
            current_run_id=run.id,
            current_step_run_id=step.id if step else None,
            quality_summary=quality,
            last_checkpoint="Tác vụ đã nằm trong hàng đợi bền vững.",
        )
    if job is not None and job.status == "leased":
        return OperatorState(
            content_case_id=content_case_id,
            state_version=version,
            status="RUNNING",
            phase=phase,
            current_run_id=run.id,
            current_step_run_id=step.id if step else None,
            current_worker=job.lease_owner,
            quality_summary=quality,
            last_checkpoint="Worker đang giữ lease của tác vụ.",
        )
    if (
        step is not None
        and step.step_key == _EXECUTABLE_STAGE
        and step.status in {"pending", "running"}
        and job is not None
        and job.status in {"failed", "cancelled"}
    ):
        code = "operator_job_failed"
        return OperatorState(
            content_case_id=content_case_id,
            state_version=version,
            status="BLOCKED",
            phase=phase,
            primary_intent="retry",
            allowed_intents=["retry"],
            current_run_id=run.id,
            current_step_run_id=step.id,
            quality_summary=quality,
            blocker_code=code,
            blocker_message=_message(code),
        )
    if run.status == "failed":
        code = "operator_run_failed"
        return OperatorState(
            content_case_id=content_case_id,
            state_version=version,
            status="BLOCKED",
            phase=phase,
            current_run_id=run.id,
            current_step_run_id=step.id if step else None,
            quality_summary=quality,
            blocker_code=code,
            blocker_message=_message(code),
        )
    if step is not None and step.status == "failed":
        code = "operator_step_failed"
        return OperatorState(
            content_case_id=content_case_id,
            state_version=version,
            status="BLOCKED",
            phase=phase,
            current_run_id=run.id,
            current_step_run_id=step.id,
            quality_summary=quality,
            blocker_code=code,
            blocker_message=_message(code),
        )
    if (
        step is not None
        and step.step_key == _EXECUTABLE_STAGE
        and step.status in {"pending", "running"}
    ):
        intent: OperatorIntent = "start" if run.status == "pending" else "continue"
        return OperatorState(
            content_case_id=content_case_id,
            state_version=version,
            status="READY",
            phase=phase,
            primary_intent=intent,
            allowed_intents=[intent],
            current_run_id=run.id,
            current_step_run_id=step.id,
            quality_summary=quality,
            last_checkpoint="Bước đã được chuẩn bị và có thể đưa vào hàng đợi.",
        )

    code = "operator_action_not_wired"
    return OperatorState(
        content_case_id=content_case_id,
        state_version=version,
        status="BLOCKED",
        phase=phase,
        current_run_id=run.id,
        current_step_run_id=step.id if step else None,
        quality_summary=quality,
        blocker_code=code,
        blocker_message=_message(code),
    )


def _request_hash(
    *,
    content_case_id: UUID,
    intent: OperatorIntent,
    state_version: str,
) -> str:
    return _stable_hash(
        {
            "content_case_id": str(content_case_id),
            "intent": intent,
            "expected_state_version": state_version,
        }
    )


async def submit_operator_command(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    intent: OperatorIntent,
    expected_state_version: str,
    idempotency_key: str,
    actor_id: str = "founder",
) -> OperatorCommandResult:
    key = idempotency_key.strip()
    if not key or len(key) > 200:
        raise OperatorControlError("operator_idempotency_key_invalid")
    if len(expected_state_version) != 64:
        raise OperatorControlError("operator_state_version_invalid")
    request_hash = _request_hash(
        content_case_id=content_case_id,
        intent=intent,
        state_version=expected_state_version,
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

    state = await get_operator_state(session, content_case_id=content_case_id)
    if state.state_version != expected_state_version:
        raise OperatorControlError("operator_state_stale")
    if intent not in state.allowed_intents:
        raise OperatorControlError("operator_intent_not_allowed")

    if intent in {"start", "continue", "retry"}:
        preflight = await build_operational_preflight()
        if preflight.get("status") != "READY":
            raise OperatorControlError("operator_preflight_blocked")

    _, _, _, run, step, job, _ = await _state_snapshot(session, content_case_id)
    if run is None or step is None:
        raise OperatorControlError("operator_runnable_step_missing")
    if step.step_key != _EXECUTABLE_STAGE:
        raise OperatorControlError("operator_internal_action_not_approved")

    command = OperatorCommand(
        content_case_id=content_case_id,
        run_id=run.id,
        step_run_id=step.id,
        job_id=None,
        intent=intent,
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=expected_state_version,
        resolved_action_key=_EXECUTABLE_STAGE,
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
        if intent == "retry" and (job is None or job.status not in {"failed", "cancelled"}):
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
    after = await get_operator_state(session, content_case_id=content_case_id)
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
    "CreatedJournalCase",
    "OperatorCommandResult",
    "OperatorControlError",
    "OperatorIntent",
    "OperatorQualitySummary",
    "OperatorState",
    "create_or_reuse_journal_case",
    "get_operator_state",
    "submit_operator_command",
]
