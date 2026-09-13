"""Read-only production board for Journal ContentCases.

The board is intentionally case-centric. Codex is the configured coordinator;
workers shown here are derived only from persisted delegation/StepRun/ModelCall/
ToolCall telemetry. Missing worker telemetry is rendered as missing rather than
guessed.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.review_action_view import (
    list_action_aware_review_cases,
)
from app.modules.content_engine.models import ContentCase
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.models import ContentRun, ModelCall, StepRun, ToolCall


class ProductionExecutionEvent(BaseModel):
    kind: str
    status: str
    role: str
    technical_name: str | None = None
    provider: str | None = None
    model: str | None = None
    execution_id: UUID | None = None
    parent_execution_id: UUID | None = None
    worker_kind: str | None = None
    worker_key: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ProductionBoardCase(BaseModel):
    id: UUID
    title: str
    status_group: str
    stage_key: str
    coordinator: str = "Codex"
    locales: list[str] = Field(default_factory=list)
    quality_state: str
    publication_state: str
    consistency_state: str
    next_action: str
    next_action_label: str
    updated_at: datetime
    current_worker: ProductionExecutionEvent | None = None
    execution_chain: list[ProductionExecutionEvent] = Field(default_factory=list)


def _event_sort_key(event: ProductionExecutionEvent) -> tuple[datetime, str]:
    stamp = event.started_at or event.completed_at
    assert stamp is not None
    return stamp, event.technical_name or event.role


def _model_event(row: ModelCall) -> ProductionExecutionEvent:
    return ProductionExecutionEvent(
        kind="model",
        status=row.status,
        role=row.purpose or row.task_key,
        technical_name=row.task_key,
        provider=row.provider,
        model=row.model,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _tool_event(row: ToolCall) -> ProductionExecutionEvent:
    return ProductionExecutionEvent(
        kind="tool",
        status=row.status,
        role=row.tool_key,
        technical_name=row.tool_key,
        worker_kind="tool",
        worker_key=row.tool_key,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _delegation_event(row: DelegationExecution) -> ProductionExecutionEvent:
    return ProductionExecutionEvent(
        kind="delegation",
        status=row.status,
        role=row.task_key,
        technical_name=row.task_key,
        execution_id=row.id,
        parent_execution_id=row.parent_execution_id,
        worker_kind=row.worker_kind,
        worker_key=row.worker_key,
        started_at=row.started_at or row.created_at,
        completed_at=row.completed_at,
    )


def _status_group(
    *,
    quality_state: str,
    consistency_state: str,
    next_action: str,
    runs: list[ContentRun],
    steps: list[StepRun],
    models: list[ModelCall],
    tools: list[ToolCall],
    delegations: list[DelegationExecution],
) -> str:
    if consistency_state == "INCONSISTENT" or quality_state == "FAIL":
        return "BLOCKED"
    if any(row.status == "failed" for row in delegations):
        return "BLOCKED"
    if next_action in {"AWAITING_FOUNDER_APPROVAL", "REVIEW_REQUIRED"}:
        return "AWAITING_APPROVAL"
    if any(row.status == "running" for row in delegations):
        return "RUNNING"
    if any(row.status == "running" for row in runs):
        return "RUNNING"
    if any(row.status == "running" for row in steps):
        return "RUNNING"
    if any(row.status == "running" for row in models):
        return "RUNNING"
    if any(row.status == "running" for row in tools):
        return "RUNNING"
    if any(row.status == "queued" for row in delegations):
        return "QUEUED"
    if next_action in {"APPROVED_NOT_PUBLISHED", "PUBLISHED", "REJECTED"}:
        return "COMPLETED"
    return "QUEUED"


def _stage_key(
    *,
    next_action: str,
    runs: list[ContentRun],
    steps: list[StepRun],
    delegations: list[DelegationExecution],
) -> str:
    active_delegations = [
        row for row in delegations if row.status in {"queued", "running", "failed"}
    ]
    if active_delegations:
        latest_delegation = max(
            active_delegations,
            key=lambda row: (row.updated_at, row.attempt, str(row.id)),
        )
        return latest_delegation.task_key

    fallback = {
        "AWAITING_FOUNDER_APPROVAL": "final_review",
        "REVIEW_REQUIRED": "final_review",
        "QUALITY_BLOCKED": "quality_gate",
        "REVISION_REQUESTED": "revision_requested",
        "REJECTED": "rejected",
        "APPROVED_NOT_PUBLISHED": "approved",
        "PUBLISHED": "published",
        "INCONSISTENT_STATE": "data_conflict",
    }
    if next_action in fallback:
        return fallback[next_action]
    active_steps = [row for row in steps if row.status in {"running", "pending"}]
    if active_steps:
        latest = max(active_steps, key=lambda row: (row.updated_at, row.attempt, str(row.id)))
        return latest.step_key
    active_runs = [row for row in runs if row.status in {"running", "waiting_approval"}]
    if active_runs:
        latest_run = max(active_runs, key=lambda row: (row.updated_at, str(row.id)))
        if latest_run.current_step:
            return latest_run.current_step
    completed_steps = [row for row in steps if row.status == "completed"]
    if completed_steps:
        latest = max(completed_steps, key=lambda row: (row.updated_at, row.attempt, str(row.id)))
        return latest.step_key
    return "intake"


def _updated_at(
    *,
    content_case: ContentCase,
    runs: list[ContentRun],
    steps: list[StepRun],
    models: list[ModelCall],
    tools: list[ToolCall],
    delegations: list[DelegationExecution],
) -> datetime:
    values = [content_case.updated_at]
    values.extend(row.updated_at for row in runs)
    values.extend(row.updated_at for row in steps)
    values.extend(row.updated_at for row in models)
    values.extend(row.updated_at for row in tools)
    values.extend(row.updated_at for row in delegations)
    return max(values)


def _execution_events(
    models: list[ModelCall],
    tools: list[ToolCall],
    delegations: list[DelegationExecution],
) -> tuple[ProductionExecutionEvent | None, list[ProductionExecutionEvent]]:
    events: list[ProductionExecutionEvent] = []
    for model_call in models:
        if model_call.started_at is not None or model_call.completed_at is not None:
            events.append(_model_event(model_call))
    for tool_call in tools:
        if tool_call.started_at is not None or tool_call.completed_at is not None:
            events.append(_tool_event(tool_call))
    for delegation in delegations:
        events.append(_delegation_event(delegation))
    events.sort(key=_event_sort_key)

    current_worker: ProductionExecutionEvent | None
    active_delegations = [
        event for event in events if event.kind == "delegation" and event.status == "running"
    ]
    if active_delegations:
        current_worker = active_delegations[-1]
    else:
        active = [event for event in events if event.status == "running"]
        current_worker = active[-1] if active else None
    return current_worker, events[-12:]


async def list_production_board_cases(
    session: AsyncSession,
) -> list[ProductionBoardCase]:
    summaries = await list_action_aware_review_cases(session)
    if not summaries:
        return []

    case_ids = [row.id for row in summaries]
    cases = list(
        (
            await session.scalars(
                select(ContentCase)
                .where(ContentCase.id.in_(case_ids))
                .order_by(ContentCase.created_at, ContentCase.id)
            )
        ).all()
    )
    case_by_id = {row.id: row for row in cases}

    runs = list(
        (
            await session.scalars(
                select(ContentRun)
                .where(ContentRun.content_case_id.in_(case_ids))
                .order_by(ContentRun.started_at, ContentRun.id)
            )
        ).all()
    )
    run_ids = [row.id for row in runs]
    steps = (
        list(
            (
                await session.scalars(
                    select(StepRun)
                    .where(StepRun.run_id.in_(run_ids))
                    .order_by(StepRun.created_at, StepRun.id)
                )
            ).all()
        )
        if run_ids
        else []
    )
    models = (
        list(
            (
                await session.scalars(
                    select(ModelCall)
                    .where(ModelCall.run_id.in_(run_ids))
                    .order_by(ModelCall.created_at, ModelCall.id)
                )
            ).all()
        )
        if run_ids
        else []
    )
    tools = (
        list(
            (
                await session.scalars(
                    select(ToolCall)
                    .where(ToolCall.run_id.in_(run_ids))
                    .order_by(ToolCall.created_at, ToolCall.id)
                )
            ).all()
        )
        if run_ids
        else []
    )
    delegations = (
        list(
            (
                await session.scalars(
                    select(DelegationExecution)
                    .where(DelegationExecution.run_id.in_(run_ids))
                    .order_by(DelegationExecution.created_at, DelegationExecution.id)
                )
            ).all()
        )
        if run_ids
        else []
    )

    run_case = {row.id: row.content_case_id for row in runs}
    output: list[ProductionBoardCase] = []
    for summary in summaries:
        content_case = case_by_id.get(summary.id)
        if content_case is None:
            continue
        case_runs = [row for row in runs if row.content_case_id == summary.id]
        case_run_ids = {row.id for row in case_runs}
        case_steps = [row for row in steps if row.run_id in case_run_ids]
        case_models = [row for row in models if run_case.get(row.run_id) == summary.id]
        case_tools = [row for row in tools if run_case.get(row.run_id) == summary.id]
        case_delegations = [row for row in delegations if run_case.get(row.run_id) == summary.id]
        current_worker, chain = _execution_events(
            case_models,
            case_tools,
            case_delegations,
        )
        output.append(
            ProductionBoardCase(
                id=summary.id,
                title=summary.opportunity_question,
                status_group=_status_group(
                    quality_state=summary.quality_state,
                    consistency_state=summary.consistency_state,
                    next_action=summary.next_action,
                    runs=case_runs,
                    steps=case_steps,
                    models=case_models,
                    tools=case_tools,
                    delegations=case_delegations,
                ),
                stage_key=_stage_key(
                    next_action=summary.next_action,
                    runs=case_runs,
                    steps=case_steps,
                    delegations=case_delegations,
                ),
                locales=[row.locale for row in summary.locales],
                quality_state=summary.quality_state,
                publication_state=summary.publication_state,
                consistency_state=summary.consistency_state,
                next_action=summary.next_action,
                next_action_label=summary.next_action_label,
                updated_at=_updated_at(
                    content_case=content_case,
                    runs=case_runs,
                    steps=case_steps,
                    models=case_models,
                    tools=case_tools,
                    delegations=case_delegations,
                ),
                current_worker=current_worker,
                execution_chain=chain,
            )
        )
    return output


__all__ = ["ProductionBoardCase", "list_production_board_cases"]
