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

    for run in runs:
        events.append(
            _history_event(
                id=f"run:{run.id}",
                at=run.started_at,
                kind="run",
                stage=run.current_step or run.run_mode,
                status=run.status,
                locale=run_locale(run),
                run_id=run.id,
                error_code=run.failure_code,
                latency_ms=_duration_ms(run.started_at, run.completed_at),
            )
        )

    for step in steps:
        run = run_by_id.get(step.run_id)
        events.append(
            _history_event(
                id=f"step:{step.id}",
                at=step.started_at or step.created_at,
                kind="step",
                stage=step.step_key,
                status=step.status,
                locale=run_locale(run),
                attempt=step.attempt,
                run_id=step.run_id,
                step_run_id=step.id,
                error_code=_safe_step_error_code(step),
                latency_ms=_duration_ms(step.started_at, step.completed_at),
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

    for approval in angle_approvals:
        events.append(
            _history_event(
                id=f"angle-approval:{approval.id}",
                at=approval.approved_at,
                kind="approval",
                stage="angle",
                status="approved",
                run_id=approval.run_id,
                artifact_id=approval.angle_artifact_id,
                artifact_version=approval.angle_artifact_version,
                artifact_hash=approval.angle_artifact_hash,
                decision="approved",
            )
        )

    for approval in outline_approvals:
        events.append(
            _history_event(
                id=f"outline-approval:{approval.id}",
                at=approval.approved_at,
                kind="approval",
                stage="outline",
                status="approved",
                run_id=approval.run_id,
                artifact_id=approval.outline_artifact_id,
                artifact_version=approval.outline_artifact_version,
                artifact_hash=approval.outline_artifact_hash,
                decision="approved",
            )
        )

    for approval in approvals:
        run = run_by_id.get(approval.run_id)
        events.append(
            _history_event(
                id=f"approval:{approval.id}",
                at=approval.created_at,
                kind="approval",
                stage=approval.step_key,
                status=approval.decision,
                locale=run_locale(run),
                run_id=approval.run_id,
                artifact_id=approval.artifact_id,
                decision=approval.decision,
            )
        )

    for row in quality_rows:
        run = run_by_id.get(row.run_id)
        events.append(
            _history_event(
                id=f"quality:{row.id}",
                at=row.created_at,
                kind="quality",
                stage=row.evaluator_key,
                status=row.result,
                locale=run_locale(run),
                run_id=row.run_id,
                artifact_id=row.artifact_id,
                result=row.result,
                evaluator_key=row.evaluator_key,
            )
        )

    for row in model_calls:
        run = run_by_id.get(row.run_id)
        events.append(
            _history_event(
                id=f"model:{row.id}",
                at=row.started_at or row.created_at,
                kind="model",
                stage=row.purpose,
                status=row.status,
                locale=run_locale(run),
                run_id=row.run_id,
                step_run_id=row.step_run_id,
                artifact_id=row.result_artifact_id,
                error_code=row.error_class,
                provider=row.provider,
                model=row.model,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                cost=str(row.cost) if row.cost is not None else None,
                latency_ms=row.latency_ms,
            )
        )

    for row in tool_calls:
        run = run_by_id.get(row.run_id)
        events.append(
            _history_event(
                id=f"tool:{row.id}",
                at=row.started_at or row.created_at,
                kind="tool",
                stage=row.tool_key,
                status=row.status,
                locale=run_locale(run),
                run_id=row.run_id,
                step_run_id=row.step_run_id,
                error_code=row.error_class,
                latency_ms=row.latency_ms,
                retry_count=row.retry_count,
            )
        )

    for row in artifacts:
        run = run_by_id.get(row.run_id)
        events.append(
            _history_event(
                id=f"artifact:{row.id}",
                at=row.created_at,
                kind="artifact",
                stage=row.artifact_type,
                status="created",
                locale=row.locale or run_locale(run),
                run_id=row.run_id,
                step_run_id=row.step_run_id,
                artifact_id=row.id,
                artifact_type=row.artifact_type,
                artifact_version=row.version,
                artifact_hash=row.content_hash,
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
