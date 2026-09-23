from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import Project, SettingsVersion
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.model_policy_models import ModelRouteDecision
from app.modules.harness.models import ContentRun, ModelCall, ToolCall


class SystemReadError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AutomationWorkerPolicy(BaseModel):
    worker_key: str
    capabilities: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)


class AutomationPolicySource(BaseModel):
    settings_version_id: UUID
    scope_type: str
    scope_key: str
    version: int
    approved_by: str | None
    approval_recorded: bool
    schema_version: int | None
    configured_enabled: bool | None
    workers: list[AutomationWorkerPolicy] = Field(default_factory=list)


class ModelUsageGroup(BaseModel):
    provider: str
    model: str
    status: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost: Decimal


class StatusCount(BaseModel):
    key: str
    status: str
    count: int


class RouteDecisionView(BaseModel):
    id: UUID
    model_call_id: UUID
    task_key: str
    policy_key: str
    policy_version: int
    capability: str
    candidate_index: int
    escalation_reason: str | None
    max_escalations: int
    max_model_calls_per_step: int
    provider: str
    model: str
    created_at: datetime


class SystemOverview(BaseModel):
    project_id: UUID
    project_slug: str
    automation_policy_sources: list[AutomationPolicySource] = Field(
        default_factory=list
    )
    model_usage: list[ModelUsageGroup] = Field(default_factory=list)
    tool_usage: list[StatusCount] = Field(default_factory=list)
    delegation_usage: list[StatusCount] = Field(default_factory=list)
    recent_route_decisions: list[RouteDecisionView] = Field(default_factory=list)
    semantics: dict[str, bool]


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(
        {
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        }
    )


def _automation_policy_source(
    row: SettingsVersion,
) -> AutomationPolicySource | None:
    settings = row.settings_json
    if not isinstance(settings, dict):
        return None
    autopilot = settings.get("autopilot")
    if not isinstance(autopilot, dict):
        return None
    raw_policy = autopilot.get("capability_policy")
    if not isinstance(raw_policy, dict):
        return None

    schema_raw = raw_policy.get("schema_version")
    schema_version = schema_raw if isinstance(schema_raw, int) else None
    enabled_raw = raw_policy.get("enabled")
    configured_enabled = enabled_raw if isinstance(enabled_raw, bool) else None

    workers: list[AutomationWorkerPolicy] = []
    raw_workers = raw_policy.get("workers")
    if isinstance(raw_workers, dict):
        for worker_key in sorted(raw_workers):
            raw_worker = raw_workers[worker_key]
            if not isinstance(worker_key, str) or not isinstance(raw_worker, dict):
                continue
            workers.append(
                AutomationWorkerPolicy(
                    worker_key=worker_key,
                    capabilities=_strings(raw_worker.get("capabilities")),
                    allowed_actions=_strings(raw_worker.get("allowed_actions")),
                    forbidden_actions=_strings(
                        raw_worker.get("forbidden_actions")
                    ),
                )
            )

    return AutomationPolicySource(
        settings_version_id=row.id,
        scope_type=row.scope_type,
        scope_key=row.scope_key,
        version=row.version,
        approved_by=row.approved_by,
        approval_recorded=bool(row.approved_by and row.approved_by.strip()),
        schema_version=schema_version,
        configured_enabled=configured_enabled,
        workers=workers,
    )


async def build_system_overview(
    session: AsyncSession,
    *,
    project_slug: str,
) -> SystemOverview:
    project = await session.scalar(
        select(Project).where(Project.slug == project_slug.strip())
    )
    if project is None:
        raise SystemReadError("system_project_not_found")

    settings_rows = list(
        (
            await session.scalars(
                select(SettingsVersion)
                .where(
                    SettingsVersion.status == "active",
                    or_(
                        SettingsVersion.project_id.is_(None),
                        SettingsVersion.project_id == project.id,
                    ),
                )
                .order_by(
                    SettingsVersion.scope_type,
                    SettingsVersion.scope_key,
                    SettingsVersion.version,
                    SettingsVersion.id,
                )
            )
        ).all()
    )
    policy_sources = [
        source
        for row in settings_rows
        if (source := _automation_policy_source(row)) is not None
    ]

    model_rows = (
        await session.execute(
            select(ModelCall)
            .join(ContentRun, ContentRun.id == ModelCall.run_id)
            .where(ContentRun.project_id == project.id)
            .order_by(ModelCall.created_at, ModelCall.id)
        )
    ).scalars().all()

    model_groups: dict[tuple[str, str, str], ModelUsageGroup] = {}
    for row in model_rows:
        key = (row.provider, row.model, row.status)
        group = model_groups.get(key)
        if group is None:
            group = ModelUsageGroup(
                provider=row.provider,
                model=row.model,
                status=row.status,
                calls=0,
                input_tokens=0,
                output_tokens=0,
                cost=Decimal("0"),
            )
            model_groups[key] = group
        group.calls += 1
        group.input_tokens += row.input_tokens or 0
        group.output_tokens += row.output_tokens or 0
        group.cost += row.cost or Decimal("0")

    tool_rows = (
        await session.execute(
            select(ToolCall)
            .join(ContentRun, ContentRun.id == ToolCall.run_id)
            .where(ContentRun.project_id == project.id)
        )
    ).scalars().all()
    tool_counts: dict[tuple[str, str], int] = {}
    for row in tool_rows:
        key = (row.tool_key, row.status)
        tool_counts[key] = tool_counts.get(key, 0) + 1

    delegation_rows = (
        await session.execute(
            select(DelegationExecution)
            .join(ContentRun, ContentRun.id == DelegationExecution.run_id)
            .where(ContentRun.project_id == project.id)
        )
    ).scalars().all()
    delegation_counts: dict[tuple[str, str], int] = {}
    for row in delegation_rows:
        key = (f"{row.worker_kind}:{row.worker_key}", row.status)
        delegation_counts[key] = delegation_counts.get(key, 0) + 1

    route_rows = (
        await session.execute(
            select(ModelRouteDecision, ModelCall)
            .join(ModelCall, ModelCall.id == ModelRouteDecision.model_call_id)
            .join(ContentRun, ContentRun.id == ModelRouteDecision.run_id)
            .where(ContentRun.project_id == project.id)
            .order_by(
                ModelRouteDecision.created_at.desc(),
                ModelRouteDecision.id,
            )
            .limit(20)
        )
    ).all()

    return SystemOverview(
        project_id=project.id,
        project_slug=project.slug,
        automation_policy_sources=policy_sources,
        model_usage=sorted(
            model_groups.values(),
            key=lambda item: (item.provider, item.model, item.status),
        ),
        tool_usage=[
            StatusCount(key=key, status=status, count=count)
            for (key, status), count in sorted(tool_counts.items())
        ],
        delegation_usage=[
            StatusCount(key=key, status=status, count=count)
            for (key, status), count in sorted(delegation_counts.items())
        ],
        recent_route_decisions=[
            RouteDecisionView(
                id=decision.id,
                model_call_id=decision.model_call_id,
                task_key=decision.task_key,
                policy_key=decision.policy_key,
                policy_version=decision.policy_version,
                capability=decision.capability,
                candidate_index=decision.candidate_index,
                escalation_reason=decision.escalation_reason,
                max_escalations=decision.max_escalations,
                max_model_calls_per_step=decision.max_model_calls_per_step,
                provider=model_call.provider,
                model=model_call.model,
                created_at=decision.created_at,
            )
            for decision, model_call in route_rows
        ],
        semantics={
            "configured_policy_is_not_runtime_state": True,
            "historical_usage_is_not_provider_health": True,
            "delegation_history_is_not_worker_health": True,
            "preflight_is_separate_live_capability_evidence": True,
        },
    )


__all__ = [
    "SystemOverview",
    "SystemReadError",
    "build_system_overview",
]