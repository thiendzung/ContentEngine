"""Read-only, sanitized per-case history for the Founder operator UI."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import (
    AngleApproval,
    OperatorCommand,
    OutlineApproval,
)
from app.modules.content_engine.journal.operator_control import OperatorControlError
from app.modules.content_engine.models import ContentCase, LocaleVariant
from app.modules.harness.models import (
    Approval,
    Artifact,
    ContentRun,
    ModelCall,
    QualityEvaluation,
    StepRun,
    ToolCall,
)

_HISTORY_LIMIT = 500
HistoryKind = Literal[
    "run",
    "step",
    "command",
    "approval",
    "quality",
    "model",
    "tool",
    "artifact",
]


class OperatorHistoryEvent(BaseModel):
    id: str
    at: datetime
    kind: HistoryKind
    stage: str
    status: str
    locale: str | None = None
    attempt: int | None = None
    run_id: UUID | None = None
    step_run_id: UUID | None = None
    artifact_id: UUID | None = None
    artifact_type: str | None = None
    artifact_version: int | None = None
    artifact_hash: str | None = None
    error_code: str | None = None
    decision: str | None = None
    result: str | None = None
    evaluator_key: str | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: str | None = None
    latency_ms: int | None = None
    retry_count: int | None = None
    resolved_action_key: str | None = None


class OperatorHistorySummary(BaseModel):
    event_count: int = 0
    run_count: int = 0
    step_count: int = 0
    approval_count: int = 0
    quality_count: int = 0
    failed_count: int = 0
    warning_count: int = 0


class OperatorCaseHistory(BaseModel):
    schema_version: int = 1
    content_case_id: UUID
    generated_at: datetime
    truncated: bool = False
    summary: OperatorHistorySummary
    events: list[OperatorHistoryEvent] = Field(default_factory=list)


def _duration_ms(
    started_at: datetime | None,
    completed_at: datetime | None,
) -> int | None:
    if started_at is None or completed_at is None:
        return None
    milliseconds = int((completed_at - started_at).total_seconds() * 1000)
    return max(milliseconds, 0)


def _safe_step_error_code(step: StepRun) -> str | None:
    payload = step.error_json
    if not isinstance(payload, dict):
        return None
    value = payload.get("class")
    return value.strip()[:100] if isinstance(value, str) and value.strip() else None


def _event_sort_key(event: OperatorHistoryEvent) -> tuple[datetime, str, str]:
    at = event.at
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return at, event.kind, event.id


def _history_event(**payload: object) -> OperatorHistoryEvent:
    """Validate the ORM-to-API boundary without leaking SQLAlchemy descriptor types."""

    return OperatorHistoryEvent.model_validate(payload)


async def get_operator_case_history(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> OperatorCaseHistory:
    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None:
        raise OperatorControlError("operator_case_not_found")

    variants = list(
        (
            await session.scalars(
                select(LocaleVariant)
                .where(LocaleVariant.content_case_id == content_case_id)
                .order_by(LocaleVariant.created_at, LocaleVariant.id)
            )
        ).all()
    )
    locale_by_variant = {row.id: row.locale for row in variants}

    runs = list(
        (
            await session.scalars(
                select(ContentRun)
                .where(ContentRun.content_case_id == content_case_id)
                .order_by(ContentRun.started_at, ContentRun.id)
            )
        ).all()
    )
    run_ids = [row.id for row in runs]
    run_by_id = {row.id: row for row in runs}

    def run_locale(run: ContentRun | None) -> str | None:
        if run is None or run.locale_variant_id is None:
            return None
        return locale_by_variant.get(run.locale_variant_id)

    commands = list(
        (
            await session.scalars(
                select(OperatorCommand)
                .where(OperatorCommand.content_case_id == content_case_id)
                .order_by(OperatorCommand.created_at, OperatorCommand.id)
            )
        ).all()
    )

    steps: list[StepRun] = []
    approvals: list[Approval] = []
    angle_approvals: list[AngleApproval] = []
    outline_approvals: list[OutlineApproval] = []
    quality_rows: list[QualityEvaluation] = []
    model_calls: list[ModelCall] = []
    tool_calls: list[ToolCall] = []
    artifacts: list[Artifact] = []

    if run_ids:
        steps = list(
            (
                await session.scalars(
                    select(StepRun)
                    .where(StepRun.run_id.in_(run_ids))
                    .order_by(StepRun.created_at, StepRun.id)
                )
            ).all()
        )
        approvals = list(
            (
                await session.scalars(
                    select(Approval)
                    .where(Approval.run_id.in_(run_ids))
                    .order_by(Approval.created_at, Approval.id)
                )
            ).all()
        )
        angle_approvals = list(
            (
                await session.scalars(
                    select(AngleApproval)
                    .where(AngleApproval.run_id.in_(run_ids))
                    .order_by(AngleApproval.approved_at, AngleApproval.id)
                )
            ).all()
        )
        outline_approvals = list(
            (
                await session.scalars(
                    select(OutlineApproval)
                    .where(OutlineApproval.run_id.in_(run_ids))
                    .order_by(OutlineApproval.approved_at, OutlineApproval.id)
                )
            ).all()
        )
        quality_rows = list(
            (
                await session.scalars(
                    select(QualityEvaluation)
                    .where(QualityEvaluation.run_id.in_(run_ids))
                    .order_by(QualityEvaluation.created_at, QualityEvaluation.id)
                )
            ).all()
        )
        model_calls = list(
            (
                await session.scalars(
                    select(ModelCall)
                    .where(ModelCall.run_id.in_(run_ids))
                    .order_by(ModelCall.created_at, ModelCall.id)
                )
            ).all()
        )
        tool_calls = list(
            (
                await session.scalars(
                    select(ToolCall)
                    .where(ToolCall.run_id.in_(run_ids))
                    .order_by(ToolCall.created_at, ToolCall.id)
                )
            ).all()
        )
        artifacts = list(
            (
                await session.scalars(
                    select(Artifact)
                    .where(Artifact.run_id.in_(run_ids))
                    .order_by(Artifact.created_at, Artifact.id)
                )
            ).all()
        )

    events: list[OperatorHistoryEvent] = []

    for content_run in runs:
        events.append(
            _history_event(
                id=f"run:{content_run.id}",
                at=content_run.started_at,
                kind="run",
                stage=content_run.current_step or content_run.run_mode,
                status=content_run.status,
                locale=run_locale(content_run),
                run_id=content_run.id,
                error_code=content_run.failure_code,
                latency_ms=_duration_ms(
                    content_run.started_at,
                    content_run.completed_at,
                ),
            )
        )

    for step_run in steps:
        related_run = run_by_id.get(step_run.run_id)
        events.append(
            _history_event(
                id=f"step:{step_run.id}",
                at=step_run.started_at or step_run.created_at,
                kind="step",
                stage=step_run.step_key,
                status=step_run.status,
                locale=run_locale(related_run),
                attempt=step_run.attempt,
                run_id=step_run.run_id,
                step_run_id=step_run.id,
                error_code=_safe_step_error_code(step_run),
                latency_ms=_duration_ms(
                    step_run.started_at,
                    step_run.completed_at,
                ),
            )
        )

    for command in commands:
        events.append(
            _history_event(
                id=f"command:{command.id}",
                at=command.created_at,
                kind="command",
                stage=command.intent,
                status=command.status,
                run_id=command.run_id,
                step_run_id=command.step_run_id,
                error_code=command.error_code,
                resolved_action_key=command.resolved_action_key,
            )
        )

    for angle_approval in angle_approvals:
        events.append(
            _history_event(
                id=f"angle-approval:{angle_approval.id}",
                at=angle_approval.approved_at,
                kind="approval",
                stage="angle",
                status="approved",
                run_id=angle_approval.run_id,
                artifact_id=angle_approval.angle_artifact_id,
                artifact_version=angle_approval.angle_artifact_version,
                artifact_hash=angle_approval.angle_artifact_hash,
                decision="approved",
            )
        )

    for outline_approval in outline_approvals:
        events.append(
            _history_event(
                id=f"outline-approval:{outline_approval.id}",
                at=outline_approval.approved_at,
                kind="approval",
                stage="outline",
                status="approved",
                run_id=outline_approval.run_id,
                artifact_id=outline_approval.outline_artifact_id,
                artifact_version=outline_approval.outline_artifact_version,
                artifact_hash=outline_approval.outline_artifact_hash,
                decision="approved",
            )
        )

    for final_approval in approvals:
        approval_run = run_by_id.get(final_approval.run_id)
        events.append(
            _history_event(
                id=f"approval:{final_approval.id}",
                at=final_approval.created_at,
                kind="approval",
                stage=final_approval.step_key,
                status=final_approval.decision,
                locale=run_locale(approval_run),
                run_id=final_approval.run_id,
                artifact_id=final_approval.artifact_id,
                decision=final_approval.decision,
            )
        )

    for quality_eval in quality_rows:
        quality_run = run_by_id.get(quality_eval.run_id)
        events.append(
            _history_event(
                id=f"quality:{quality_eval.id}",
                at=quality_eval.created_at,
                kind="quality",
                stage=quality_eval.evaluator_key,
                status=quality_eval.result,
                locale=run_locale(quality_run),
                run_id=quality_eval.run_id,
                artifact_id=quality_eval.artifact_id,
                result=quality_eval.result,
                evaluator_key=quality_eval.evaluator_key,
            )
        )

    for model_call in model_calls:
        model_run = run_by_id.get(model_call.run_id)
        events.append(
            _history_event(
                id=f"model:{model_call.id}",
                at=model_call.started_at or model_call.created_at,
                kind="model",
                stage=model_call.purpose,
                status=model_call.status,
                locale=run_locale(model_run),
                run_id=model_call.run_id,
                step_run_id=model_call.step_run_id,
                artifact_id=model_call.result_artifact_id,
                error_code=model_call.error_class,
                provider=model_call.provider,
                model=model_call.model,
                input_tokens=model_call.input_tokens,
                output_tokens=model_call.output_tokens,
                cost=str(model_call.cost) if model_call.cost is not None else None,
                latency_ms=model_call.latency_ms,
            )
        )

    for tool_call in tool_calls:
        tool_run = run_by_id.get(tool_call.run_id)
        events.append(
            _history_event(
                id=f"tool:{tool_call.id}",
                at=tool_call.started_at or tool_call.created_at,
                kind="tool",
                stage=tool_call.tool_key,
                status=tool_call.status,
                locale=run_locale(tool_run),
                run_id=tool_call.run_id,
                step_run_id=tool_call.step_run_id,
                error_code=tool_call.error_class,
                latency_ms=tool_call.latency_ms,
                retry_count=tool_call.retry_count,
            )
        )

    for artifact in artifacts:
        artifact_run = run_by_id.get(artifact.run_id)
        events.append(
            _history_event(
                id=f"artifact:{artifact.id}",
                at=artifact.created_at,
                kind="artifact",
                stage=artifact.artifact_type,
                status="created",
                locale=artifact.locale or run_locale(artifact_run),
                run_id=artifact.run_id,
                step_run_id=artifact.step_run_id,
                artifact_id=artifact.id,
                artifact_type=artifact.artifact_type,
                artifact_version=artifact.version,
                artifact_hash=artifact.content_hash,
            )
        )

    events.sort(key=_event_sort_key)
    truncated = len(events) > _HISTORY_LIMIT
    if truncated:
        events = events[-_HISTORY_LIMIT:]

    summary = OperatorHistorySummary(
        event_count=len(events),
        run_count=sum(event.kind == "run" for event in events),
        step_count=sum(event.kind == "step" for event in events),
        approval_count=sum(event.kind == "approval" for event in events),
        quality_count=sum(event.kind == "quality" for event in events),
        failed_count=sum(
            event.status in {"failed", "rejected", "cancelled", "fail"}
            for event in events
        ),
        warning_count=sum(event.status == "warn" for event in events),
    )
    return OperatorCaseHistory(
        content_case_id=content_case_id,
        generated_at=datetime.now(UTC),
        truncated=truncated,
        summary=summary,
        events=events,
    )


__all__ = [
    "OperatorCaseHistory",
    "OperatorHistoryEvent",
    "OperatorHistorySummary",
    "get_operator_case_history",
]
