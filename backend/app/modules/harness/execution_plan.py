"""Immutable task contracts and least-privilege capability policy for AU-01.

ExecutionPlan is a versioned Artifact bound to the ContentRun's immutable
SettingsSnapshot. This module authorizes plans only; AU-02 will add claim/heartbeat
and auto-next execution semantics.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.models import Artifact, ContentRun, StepRun
from app.modules.system.settings_service import settings_hash

EXECUTION_PLAN_SCHEMA_VERSION = 1
EXECUTION_PLAN_ARTIFACT_PREFIX = "execution_plan_"

CAPABILITIES: frozenset[str] = frozenset(
    {
        "READ",
        "WRITE_ARTIFACT",
        "RUN_MODEL",
        "RUN_TOOL",
        "RESEARCH_EXTERNAL",
        "WRITE_DATABASE",
        "PUBLISH",
        "CHANGE_SETTINGS",
        "CHANGE_PROMPT",
        "CHANGE_WORKFLOW",
    }
)
HUMAN_GATED_CAPABILITIES: frozenset[str] = frozenset(
    {
        "PUBLISH",
        "CHANGE_SETTINGS",
        "CHANGE_PROMPT",
        "CHANGE_WORKFLOW",
    }
)
_BUDGET_FIELDS = frozenset(
    {
        "max_model_calls",
        "max_tool_calls",
        "max_context_estimate",
        "max_output_tokens",
        "max_estimated_cost",
        "max_wall_clock_seconds",
        "max_research_sources",
        "max_revise_loops",
    }
)
_INTEGER_BUDGET_FIELDS = frozenset(
    {
        "max_model_calls",
        "max_tool_calls",
        "max_context_estimate",
        "max_output_tokens",
        "max_research_sources",
        "max_revise_loops",
    }
)
_DECIMAL_BUDGET_FIELDS = frozenset({"max_estimated_cost"})
_FLOAT_BUDGET_FIELDS = frozenset({"max_wall_clock_seconds"})
_PLAN_INPUT_FIELDS = frozenset(
    {
        "schema_version",
        "task_key",
        "worker_key",
        "goal",
        "input_refs",
        "expected_output_types",
        "required_capabilities",
        "allowed_actions",
        "forbidden_actions",
        "allowed_tools",
        "budget",
        "timeout_seconds",
        "max_attempts",
        "stop_conditions",
        "required_checks",
        "reviewer",
        "next_on_pass",
        "next_on_fail",
        "human_gate_required",
    }
)
_PLAN_PERSISTED_FIELDS = _PLAN_INPUT_FIELDS | frozenset(
    {"settings_snapshot_id", "settings_snapshot_hash"}
)
_POLICY_ROOT_FIELDS = frozenset({"schema_version", "enabled", "workers"})
_WORKER_POLICY_FIELDS = frozenset(
    {
        "capabilities",
        "allowed_actions",
        "forbidden_actions",
        "allowed_tools",
        "budget_ceiling",
        "max_timeout_seconds",
        "max_attempts",
    }
)
_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")


class ExecutionPlanError(ValueError):
    """Fail-closed AU-01 error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class WorkerCapabilityPolicy:
    worker_key: str
    capabilities: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    budget_ceiling: dict[str, int | float | str]
    max_timeout_seconds: float
    max_attempts: int


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    task_key: str
    worker_key: str
    goal: str
    input_refs: tuple[str, ...]
    expected_output_types: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    budget: dict[str, int | float | str]
    timeout_seconds: float
    max_attempts: int
    stop_conditions: tuple[str, ...]
    required_checks: tuple[str, ...]
    reviewer: str
    next_on_pass: str
    next_on_fail: str
    human_gate_required: bool
    settings_snapshot_id: UUID
    settings_snapshot_hash: str


@dataclass(frozen=True, slots=True)
class AuthorizedExecutionPlan:
    artifact_id: UUID
    run_id: UUID
    step_run_id: UUID | None
    artifact_version: int
    plan: ExecutionPlan
    policy: WorkerCapabilityPolicy


async def persist_execution_plan_artifact(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    plan: object,
    version: int = 1,
) -> Artifact:
    """Validate, authorize and persist one exact immutable ExecutionPlan artifact."""

    if version < 1:
        raise ExecutionPlanError("execution_plan_version_invalid")
    run, step, snapshot = await _execution_context(
        session,
        run_id=run_id,
        step_run_id=step_run_id,
    )
    parsed = _parse_plan_input(
        plan,
        settings_snapshot_id=snapshot.id,
        settings_snapshot_hash=snapshot.content_hash,
    )
    policy = _resolve_worker_policy(snapshot, worker_key=parsed.worker_key)
    _authorize_plan(parsed, policy)

    payload = _plan_payload(parsed)
    artifact_type = _artifact_type(
        run_id=run.id,
        step_run_id=step.id if step is not None else None,
        task_key=parsed.task_key,
    )
    payload_hash = _stable_hash(payload)

    existing = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == run.id,
            Artifact.artifact_type == artifact_type,
            Artifact.version == version,
        )
    )
    if existing is not None:
        if (
            existing.step_run_id != step_run_id
            or existing.content_json != payload
            or existing.content_hash != payload_hash
        ):
            raise ExecutionPlanError("execution_plan_replay_conflict")
        return existing

    artifact = Artifact(
        run_id=run.id,
        step_run_id=step_run_id,
        artifact_type=artifact_type,
        locale=None,
        version=version,
        content_json=payload,
        content_hash=payload_hash,
    )
    session.add(artifact)
    await session.flush()
    return artifact


async def authorize_execution_plan(
    session: AsyncSession,
    *,
    artifact_id: UUID,
    worker_key: str,
) -> AuthorizedExecutionPlan:
    """Re-authorize an existing plan against exact current durable bindings."""

    artifact = await session.get(Artifact, artifact_id)
    if artifact is None:
        raise ExecutionPlanError("execution_plan_artifact_not_found")
    if not artifact.artifact_type.startswith(EXECUTION_PLAN_ARTIFACT_PREFIX):
        raise ExecutionPlanError("execution_plan_artifact_type_invalid")
    if artifact.content_json is None:
        raise ExecutionPlanError("execution_plan_artifact_content_missing")
    if artifact.content_hash != _stable_hash(artifact.content_json):
        raise ExecutionPlanError("execution_plan_artifact_hash_mismatch")

    plan = _parse_persisted_plan(artifact.content_json)
    expected_type = _artifact_type(
        run_id=artifact.run_id,
        step_run_id=artifact.step_run_id,
        task_key=plan.task_key,
    )
    if artifact.artifact_type != expected_type:
        raise ExecutionPlanError("execution_plan_artifact_binding_mismatch")

    run, _, snapshot = await _execution_context(
        session,
        run_id=artifact.run_id,
        step_run_id=artifact.step_run_id,
    )
    if plan.settings_snapshot_id != run.settings_snapshot_id:
        raise ExecutionPlanError("execution_plan_settings_snapshot_mismatch")
    if plan.settings_snapshot_id != snapshot.id:
        raise ExecutionPlanError("execution_plan_settings_snapshot_mismatch")
    if plan.settings_snapshot_hash != snapshot.content_hash:
        raise ExecutionPlanError("execution_plan_settings_snapshot_stale")
    _validate_settings_snapshot_hash(snapshot)

    requested_worker = _required_key(worker_key, "execution_plan_worker_key_invalid")
    if requested_worker != plan.worker_key:
        raise ExecutionPlanError("execution_plan_worker_mismatch")

    policy = _resolve_worker_policy(snapshot, worker_key=plan.worker_key)
    _authorize_plan(plan, policy)
    return AuthorizedExecutionPlan(
        artifact_id=artifact.id,
        run_id=artifact.run_id,
        step_run_id=artifact.step_run_id,
        artifact_version=artifact.version,
        plan=plan,
        policy=policy,
    )


async def _execution_context(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
) -> tuple[ContentRun, StepRun | None, SettingsSnapshot]:
    run = await session.get(ContentRun, run_id)
    if run is None:
        raise ExecutionPlanError("execution_plan_run_not_found")

    step: StepRun | None = None
    if step_run_id is not None:
        step = await session.get(StepRun, step_run_id)
        if step is None or step.run_id != run.id:
            raise ExecutionPlanError("execution_plan_step_mismatch")

    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None or snapshot.project_id != run.project_id:
        raise ExecutionPlanError("execution_plan_settings_snapshot_missing")
    _validate_settings_snapshot_hash(snapshot)
    return run, step, snapshot


def _validate_settings_snapshot_hash(snapshot: SettingsSnapshot) -> None:
    if snapshot.content_hash != settings_hash(snapshot.resolved_settings_json):
        raise ExecutionPlanError("execution_plan_settings_snapshot_hash_mismatch")


def _resolve_worker_policy(
    snapshot: SettingsSnapshot,
    *,
    worker_key: str,
) -> WorkerCapabilityPolicy:
    root = _as_dict(
        snapshot.resolved_settings_json.get("autopilot"),
        "execution_plan_policy_root_invalid",
    )
    raw_policy = _as_exact_dict(
        root.get("capability_policy"),
        _POLICY_ROOT_FIELDS,
        "execution_plan_capability_policy_invalid",
    )
    if raw_policy.get("schema_version") != 1:
        raise ExecutionPlanError("execution_plan_capability_policy_version_invalid")
    if raw_policy.get("enabled") is not True:
        raise ExecutionPlanError("execution_plan_capability_policy_disabled")
    workers = _as_dict(
        raw_policy.get("workers"),
        "execution_plan_capability_workers_invalid",
    )
    normalized_worker = _required_key(
        worker_key,
        "execution_plan_worker_key_invalid",
    )
    raw_worker = _as_exact_dict(
        workers.get(normalized_worker),
        _WORKER_POLICY_FIELDS,
        "execution_plan_worker_policy_invalid",
    )

    capabilities = _capability_list(
        raw_worker.get("capabilities"),
        "execution_plan_policy_capabilities_invalid",
    )
    allowed_actions = _key_list(
        raw_worker.get("allowed_actions"),
        "execution_plan_policy_allowed_actions_invalid",
    )
    forbidden_actions = _key_list(
        raw_worker.get("forbidden_actions"),
        "execution_plan_policy_forbidden_actions_invalid",
    )
    allowed_tools = _key_list(
        raw_worker.get("allowed_tools"),
        "execution_plan_policy_allowed_tools_invalid",
    )
    if set(allowed_actions) & set(forbidden_actions):
        raise ExecutionPlanError("execution_plan_policy_action_conflict")

    budget_ceiling = _budget(
        raw_worker.get("budget_ceiling"),
        "execution_plan_policy_budget_invalid",
    )
    max_timeout_seconds = _positive_float(
        raw_worker.get("max_timeout_seconds"),
        "execution_plan_policy_timeout_invalid",
    )
    max_attempts = _positive_int(
        raw_worker.get("max_attempts"),
        "execution_plan_policy_attempts_invalid",
    )
    return WorkerCapabilityPolicy(
        worker_key=normalized_worker,
        capabilities=capabilities,
        allowed_actions=allowed_actions,
        forbidden_actions=forbidden_actions,
        allowed_tools=allowed_tools,
        budget_ceiling=budget_ceiling,
        max_timeout_seconds=max_timeout_seconds,
        max_attempts=max_attempts,
    )


def _authorize_plan(
    plan: ExecutionPlan,
    policy: WorkerCapabilityPolicy,
) -> None:
    if plan.worker_key != policy.worker_key:
        raise ExecutionPlanError("execution_plan_worker_mismatch")
    if not set(plan.required_capabilities).issubset(policy.capabilities):
        raise ExecutionPlanError("execution_plan_capability_not_allowed")
    if not set(plan.allowed_actions).issubset(policy.allowed_actions):
        raise ExecutionPlanError("execution_plan_action_not_allowed")
    if set(plan.allowed_actions) & set(policy.forbidden_actions):
        raise ExecutionPlanError("execution_plan_action_forbidden")
    if not set(policy.forbidden_actions).issubset(plan.forbidden_actions):
        raise ExecutionPlanError("execution_plan_policy_forbidden_action_missing")
    if not set(plan.allowed_tools).issubset(policy.allowed_tools):
        raise ExecutionPlanError("execution_plan_tool_not_allowed")
    if plan.timeout_seconds > policy.max_timeout_seconds:
        raise ExecutionPlanError("execution_plan_timeout_exceeds_policy")
    if plan.max_attempts > policy.max_attempts:
        raise ExecutionPlanError("execution_plan_attempts_exceed_policy")
    _enforce_budget_ceiling(plan.budget, policy.budget_ceiling)

    if (
        set(plan.required_capabilities) & HUMAN_GATED_CAPABILITIES
        and not plan.human_gate_required
    ):
        raise ExecutionPlanError("execution_plan_human_gate_required")


def _enforce_budget_ceiling(
    plan_budget: dict[str, int | float | str],
    ceiling: dict[str, int | float | str],
) -> None:
    for key, plan_value in plan_budget.items():
        if key not in ceiling:
            raise ExecutionPlanError("execution_plan_budget_ceiling_missing")
        if _budget_number(key, plan_value) > _budget_number(key, ceiling[key]):
            raise ExecutionPlanError("execution_plan_budget_exceeds_policy")


def _parse_plan_input(
    value: object,
    *,
    settings_snapshot_id: UUID,
    settings_snapshot_hash: str,
) -> ExecutionPlan:
    raw = _as_exact_dict(
        value,
        _PLAN_INPUT_FIELDS,
        "execution_plan_contract_invalid",
    )
    return _parse_plan_fields(
        raw,
        settings_snapshot_id=settings_snapshot_id,
        settings_snapshot_hash=settings_snapshot_hash,
    )


def _parse_persisted_plan(value: object) -> ExecutionPlan:
    raw = _as_exact_dict(
        value,
        _PLAN_PERSISTED_FIELDS,
        "execution_plan_contract_invalid",
    )
    snapshot_id = raw.get("settings_snapshot_id")
    snapshot_hash = raw.get("settings_snapshot_hash")
    try:
        parsed_snapshot_id = UUID(str(snapshot_id))
    except (TypeError, ValueError) as exc:
        raise ExecutionPlanError("execution_plan_settings_snapshot_id_invalid") from exc
    if not isinstance(snapshot_hash, str) or not re.fullmatch(
        r"[0-9a-f]{64}", snapshot_hash
    ):
        raise ExecutionPlanError("execution_plan_settings_snapshot_hash_invalid")
    return _parse_plan_fields(
        raw,
        settings_snapshot_id=parsed_snapshot_id,
        settings_snapshot_hash=snapshot_hash,
    )


def _parse_plan_fields(
    raw: dict[str, object],
    *,
    settings_snapshot_id: UUID,
    settings_snapshot_hash: str,
) -> ExecutionPlan:
    if raw.get("schema_version") != EXECUTION_PLAN_SCHEMA_VERSION:
        raise ExecutionPlanError("execution_plan_schema_version_invalid")
    task_key = _required_key(raw.get("task_key"), "execution_plan_task_key_invalid")
    worker_key = _required_key(raw.get("worker_key"), "execution_plan_worker_key_invalid")
    goal = _required_text(raw.get("goal"), "execution_plan_goal_required")
    input_refs = _text_list(raw.get("input_refs"), "execution_plan_input_refs_invalid")
    expected_output_types = _key_list(
        raw.get("expected_output_types"),
        "execution_plan_expected_outputs_invalid",
    )
    if not expected_output_types:
        raise ExecutionPlanError("execution_plan_expected_outputs_required")
    required_capabilities = _capability_list(
        raw.get("required_capabilities"),
        "execution_plan_required_capabilities_invalid",
    )
    allowed_actions = _key_list(
        raw.get("allowed_actions"),
        "execution_plan_allowed_actions_invalid",
    )
    forbidden_actions = _key_list(
        raw.get("forbidden_actions"),
        "execution_plan_forbidden_actions_invalid",
    )
    if set(allowed_actions) & set(forbidden_actions):
        raise ExecutionPlanError("execution_plan_action_conflict")
    allowed_tools = _key_list(
        raw.get("allowed_tools"),
        "execution_plan_allowed_tools_invalid",
    )
    budget = _budget(raw.get("budget"), "execution_plan_budget_invalid")
    timeout_seconds = _positive_float(
        raw.get("timeout_seconds"),
        "execution_plan_timeout_invalid",
    )
    max_attempts = _positive_int(
        raw.get("max_attempts"),
        "execution_plan_attempts_invalid",
    )
    stop_conditions = _text_list(
        raw.get("stop_conditions"),
        "execution_plan_stop_conditions_invalid",
    )
    required_checks = _text_list(
        raw.get("required_checks"),
        "execution_plan_required_checks_invalid",
    )
    if not stop_conditions:
        raise ExecutionPlanError("execution_plan_stop_conditions_required")
    if not required_checks:
        raise ExecutionPlanError("execution_plan_required_checks_required")
    reviewer = _required_key(raw.get("reviewer"), "execution_plan_reviewer_invalid")
    next_on_pass = _required_key(
        raw.get("next_on_pass"),
        "execution_plan_next_on_pass_invalid",
    )
    next_on_fail = _required_key(
        raw.get("next_on_fail"),
        "execution_plan_next_on_fail_invalid",
    )
    human_gate_required = raw.get("human_gate_required")
    if not isinstance(human_gate_required, bool):
        raise ExecutionPlanError("execution_plan_human_gate_invalid")

    return ExecutionPlan(
        task_key=task_key,
        worker_key=worker_key,
        goal=goal,
        input_refs=input_refs,
        expected_output_types=expected_output_types,
        required_capabilities=required_capabilities,
        allowed_actions=allowed_actions,
        forbidden_actions=forbidden_actions,
        allowed_tools=allowed_tools,
        budget=budget,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        stop_conditions=stop_conditions,
        required_checks=required_checks,
        reviewer=reviewer,
        next_on_pass=next_on_pass,
        next_on_fail=next_on_fail,
        human_gate_required=human_gate_required,
        settings_snapshot_id=settings_snapshot_id,
        settings_snapshot_hash=settings_snapshot_hash,
    )


def _plan_payload(plan: ExecutionPlan) -> dict[str, object]:
    return {
        "schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
        "task_key": plan.task_key,
        "worker_key": plan.worker_key,
        "goal": plan.goal,
        "input_refs": list(plan.input_refs),
        "expected_output_types": list(plan.expected_output_types),
        "required_capabilities": list(plan.required_capabilities),
        "allowed_actions": list(plan.allowed_actions),
        "forbidden_actions": list(plan.forbidden_actions),
        "allowed_tools": list(plan.allowed_tools),
        "budget": dict(plan.budget),
        "timeout_seconds": plan.timeout_seconds,
        "max_attempts": plan.max_attempts,
        "stop_conditions": list(plan.stop_conditions),
        "required_checks": list(plan.required_checks),
        "reviewer": plan.reviewer,
        "next_on_pass": plan.next_on_pass,
        "next_on_fail": plan.next_on_fail,
        "human_gate_required": plan.human_gate_required,
        "settings_snapshot_id": str(plan.settings_snapshot_id),
        "settings_snapshot_hash": plan.settings_snapshot_hash,
    }


def _artifact_type(
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    task_key: str,
) -> str:
    binding = f"{run_id}:{step_run_id or 'none'}:{task_key}".encode()
    suffix = hashlib.sha256(binding).hexdigest()[:24]
    return f"{EXECUTION_PLAN_ARTIFACT_PREFIX}{suffix}"


def _as_dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ExecutionPlanError(code)
    return {str(key): item for key, item in value.items()}


def _as_exact_dict(
    value: object,
    fields: frozenset[str] | set[str],
    code: str,
) -> dict[str, object]:
    raw = _as_dict(value, code)
    if set(raw) != set(fields):
        raise ExecutionPlanError(code)
    return raw


def _required_text(value: object, code: str) -> str:
    if not isinstance(value, str):
        raise ExecutionPlanError(code)
    normalized = value.strip()
    if not normalized:
        raise ExecutionPlanError(code)
    return normalized


def _required_key(value: object, code: str) -> str:
    normalized = _required_text(value, code)
    if not _KEY_RE.fullmatch(normalized):
        raise ExecutionPlanError(code)
    return normalized


def _unique_list(
    value: object,
    *,
    parser: Callable[[object, str], str],
    code: str,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ExecutionPlanError(code)
    output: list[str] = []
    seen: set[str] = set()
    for raw_item in value:
        item = parser(raw_item, code)
        if item in seen:
            raise ExecutionPlanError(code)
        seen.add(item)
        output.append(item)
    return tuple(output)


def _text_list(value: object, code: str) -> tuple[str, ...]:
    return _unique_list(value, parser=_required_text, code=code)


def _key_list(value: object, code: str) -> tuple[str, ...]:
    return _unique_list(value, parser=_required_key, code=code)


def _capability(value: object, code: str) -> str:
    capability = _required_text(value, code)
    if capability not in CAPABILITIES:
        raise ExecutionPlanError(code)
    return capability


def _capability_list(value: object, code: str) -> tuple[str, ...]:
    return _unique_list(value, parser=_capability, code=code)


def _budget(value: object, code: str) -> dict[str, int | float | str]:
    raw = _as_dict(value, code)
    if not raw or not set(raw).issubset(_BUDGET_FIELDS):
        raise ExecutionPlanError(code)
    normalized: dict[str, int | float | str] = {}
    for key in sorted(raw):
        item = raw[key]
        if key in _INTEGER_BUDGET_FIELDS:
            normalized[key] = _nonnegative_int(item, code)
        elif key in _FLOAT_BUDGET_FIELDS:
            normalized[key] = _nonnegative_float(item, code)
        elif key in _DECIMAL_BUDGET_FIELDS:
            normalized[key] = _nonnegative_decimal_text(item, code)
        else:
            raise ExecutionPlanError(code)
    return normalized


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ExecutionPlanError(code)
    return value


def _positive_float(value: object, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExecutionPlanError(code)
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        raise ExecutionPlanError(code)
    return normalized


def _nonnegative_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ExecutionPlanError(code)
    return value


def _nonnegative_float(value: object, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExecutionPlanError(code)
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0:
        raise ExecutionPlanError(code)
    return normalized


def _nonnegative_decimal_text(value: object, code: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ExecutionPlanError(code)
    try:
        normalized = Decimal(str(value))
    except InvalidOperation as exc:
        raise ExecutionPlanError(code) from exc
    if not normalized.is_finite() or normalized < 0:
        raise ExecutionPlanError(code)
    return format(normalized.normalize(), "f")


def _budget_number(key: str, value: int | float | str) -> Decimal:
    if key in _INTEGER_BUDGET_FIELDS or key in _FLOAT_BUDGET_FIELDS:
        return Decimal(str(value))
    if key in _DECIMAL_BUDGET_FIELDS:
        return Decimal(str(value))
    raise ExecutionPlanError("execution_plan_budget_invalid")


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "AuthorizedExecutionPlan",
    "CAPABILITIES",
    "EXECUTION_PLAN_SCHEMA_VERSION",
    "ExecutionPlan",
    "ExecutionPlanError",
    "HUMAN_GATED_CAPABILITIES",
    "WorkerCapabilityPolicy",
    "authorize_execution_plan",
    "persist_execution_plan_artifact",
]