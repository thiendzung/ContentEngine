"""AU-02 Local Agent Bridge over the existing durable Harness.

The bridge does not introduce a second workflow engine. It binds an AU-01
ExecutionPlan to the existing Job/StepRun lease lifecycle, enforces durable
Approval for human-gated capabilities at execution time, records safe
DelegationExecution telemetry, and materializes auto-next only after an
independent review result.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.harness.delegation import (
    DelegationStateError,
    complete_delegation_execution,
    ensure_delegation_execution,
    fail_delegation_execution,
    start_delegation_execution,
)
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.execution_plan import (
    EXECUTION_PLAN_ARTIFACT_PREFIX,
    AuthorizedExecutionPlan,
    ExecutionPlan,
    ExecutionPlanError,
    authorize_execution_plan,
    persist_execution_plan_artifact,
)
from app.modules.harness.models import (
    Approval,
    Artifact,
    ContentRun,
    Job,
    ModelCall,
    StepRun,
    ToolCall,
    utc_now,
)
from app.modules.harness.persistence import (
    LeaseOwnershipError,
    create_checkpoint,
    enqueue_job,
    get_latest_checkpoint,
    heartbeat_job,
    load_budget_usage,
    pause_for_approval,
)
from app.modules.harness.policy import (
    BudgetExceededError,
    BudgetLimits,
    UnknownFailureClassError,
    enforce_budget,
    is_retryable_failure,
)

AGENT_BRIDGE_SCHEMA_VERSION = 1
_ROOT_COORDINATOR_KEY = "local_bridge"
_SAFE_TELEMETRY_FIELDS = frozenset(
    {
        "runner_version",
        "repository_revision",
        "repository_tree_hash",
    }
)
_NEXT_STEP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


class AgentBridgeError(ValueError):
    """Fail-closed AU-02 error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AgentTaskLease:
    job_id: UUID
    run_id: UUID
    step_run_id: UUID
    execution_plan_artifact_id: UUID
    worker_key: str
    worker_instance_id: str
    task_key: str
    job_attempt: int
    step_attempt: int
    lease_expires_at: datetime
    plan_deadline: datetime
    root_execution_id: UUID
    approval_id: UUID | None
    execution_plan: dict[str, object]
    settings_snapshot_id: UUID
    settings_snapshot_hash: str
    replayed: bool


@dataclass(frozen=True, slots=True)
class AgentTaskCompletion:
    job_id: UUID
    completion_receipt_id: UUID
    review_request_id: UUID
    replayed: bool


@dataclass(frozen=True, slots=True)
class AgentTaskFailure:
    job_id: UUID
    failure_receipt_id: UUID
    retry_step_run_id: UUID | None
    retry_execution_plan_artifact_id: UUID | None
    retry_job_id: UUID | None
    retry_requires_approval: bool
    replayed: bool


@dataclass(frozen=True, slots=True)
class AgentReviewResult:
    review_result_id: UUID
    decision: str
    replayed: bool


@dataclass(frozen=True, slots=True)
class AutoNextResult:
    review_result_id: UUID
    route: str
    next_step_run_id: UUID
    route_receipt_id: UUID
    replayed: bool


def _required_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentBridgeError(code)
    return value.strip()


def _execution_plan_payload(plan: ExecutionPlan) -> dict[str, object]:
    return {
        "schema_version": 1,
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


def _optional_int_budget(
    plan: ExecutionPlan,
    key: str,
) -> int | None:
    value = plan.budget.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise AgentBridgeError("agent_bridge_plan_budget_invalid")
    return value


def _optional_float_budget(
    plan: ExecutionPlan,
    key: str,
) -> float | None:
    value = plan.budget.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AgentBridgeError("agent_bridge_plan_budget_invalid")
    return float(value)


def _optional_decimal_budget(
    plan: ExecutionPlan,
    key: str,
) -> Decimal | None:
    value = plan.budget.get(key)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise AgentBridgeError(
            "agent_bridge_plan_budget_invalid"
        ) from exc


def _plan_budget_limits(plan: ExecutionPlan) -> BudgetLimits:
    return BudgetLimits(
        max_model_calls=_optional_int_budget(plan, "max_model_calls"),
        max_tool_calls=_optional_int_budget(plan, "max_tool_calls"),
        max_context_estimate=_optional_int_budget(
            plan,
            "max_context_estimate",
        ),
        max_output_tokens=_optional_int_budget(
            plan,
            "max_output_tokens",
        ),
        max_estimated_cost=_optional_decimal_budget(
            plan,
            "max_estimated_cost",
        ),
        max_wall_clock_seconds=_optional_float_budget(
            plan,
            "max_wall_clock_seconds",
        ),
        max_research_sources=_optional_int_budget(
            plan,
            "max_research_sources",
        ),
        max_revise_loops=_optional_int_budget(
            plan,
            "max_revise_loops",
        ),
    )


def _ensure_bridge_budget_supported(plan: ExecutionPlan) -> None:
    unsupported = {
        "max_context_estimate",
        "max_research_sources",
        "max_revise_loops",
    }
    if unsupported & set(plan.budget):
        raise AgentBridgeError(
            "agent_bridge_budget_field_not_durable"
        )


async def _enforce_plan_budget(
    session: AsyncSession,
    *,
    authorized: AuthorizedExecutionPlan,
) -> None:
    _ensure_bridge_budget_supported(authorized.plan)
    usage = await load_budget_usage(
        session,
        run_id=authorized.run_id,
        step_run_id=authorized.step_run_id,
    )
    try:
        enforce_budget(_plan_budget_limits(authorized.plan), usage)
    except BudgetExceededError as exc:
        raise AgentBridgeError("agent_bridge_budget_exceeded") from exc


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _artifact_type(prefix: str, identity: object) -> str:
    digest = hashlib.sha256(str(identity).encode("utf-8")).hexdigest()[:16]
    value = f"{prefix}{digest}"
    if len(value) > 64:  # defensive: DB artifact_type is varchar(64)
        raise AgentBridgeError("agent_bridge_artifact_type_invalid")
    return value


def _worker_bucket(worker_key: str) -> str:
    digest = hashlib.sha256(worker_key.encode("utf-8")).hexdigest()
    return f"agent_bridge:{digest}:"


def _job_dedupe_key(
    *,
    plan_artifact_id: UUID,
    worker_key: str,
    step_attempt: int,
) -> str:
    return (
        f"{_worker_bucket(worker_key)}"
        f"{plan_artifact_id.hex[:20]}:{step_attempt}"
    )


def _root_execution_dedupe(job: Job) -> str:
    return f"agent_bridge_root:{job.id}:{job.attempt}"


async def _latest_plan_artifact(
    session: AsyncSession,
    *,
    artifact: Artifact,
) -> Artifact:
    latest = await session.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == artifact.run_id,
            Artifact.artifact_type == artifact.artifact_type,
        )
        .order_by(Artifact.version.desc(), Artifact.id.desc())
        .limit(1)
    )
    if latest is None or latest.id != artifact.id:
        raise AgentBridgeError("agent_bridge_execution_plan_stale")
    return latest


async def _authorize_latest_plan(
    session: AsyncSession,
    *,
    artifact_id: UUID,
    worker_key: str,
) -> tuple[AuthorizedExecutionPlan, Artifact, StepRun]:
    try:
        authorized = await authorize_execution_plan(
            session,
            artifact_id=artifact_id,
            worker_key=worker_key,
        )
    except ExecutionPlanError as exc:
        raise AgentBridgeError(exc.code) from exc
    if authorized.step_run_id is None:
        raise AgentBridgeError("agent_bridge_step_plan_required")
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None:
        raise AgentBridgeError("agent_bridge_execution_plan_not_found")
    await _latest_plan_artifact(session, artifact=artifact)
    step = await session.get(StepRun, authorized.step_run_id)
    if step is None or step.run_id != authorized.run_id:
        raise AgentBridgeError("agent_bridge_step_binding_invalid")
    if step.attempt > authorized.plan.max_attempts:
        raise AgentBridgeError("agent_bridge_step_attempt_exceeds_plan")
    _ensure_bridge_budget_supported(authorized.plan)
    return authorized, artifact, step


async def _bind_plan_to_step(
    session: AsyncSession,
    *,
    step: StepRun,
    plan_artifact: Artifact,
) -> None:
    plan_ref = str(plan_artifact.id)
    if plan_ref in step.input_artifact_refs_json:
        return

    for raw_ref in step.input_artifact_refs_json:
        if not isinstance(raw_ref, str):
            continue
        try:
            ref_id = UUID(raw_ref)
        except ValueError:
            continue
        candidate = await session.get(Artifact, ref_id)
        if (
            candidate is not None
            and candidate.artifact_type.startswith(
                EXECUTION_PLAN_ARTIFACT_PREFIX
            )
            and candidate.id != plan_artifact.id
        ):
            raise AgentBridgeError(
                "agent_bridge_step_execution_plan_conflict"
            )

    step.input_artifact_refs_json = [
        *step.input_artifact_refs_json,
        plan_ref,
    ]
    await session.flush()


async def _bound_plan_artifact(
    session: AsyncSession,
    *,
    step: StepRun,
) -> Artifact:
    matches: list[Artifact] = []
    for raw_ref in step.input_artifact_refs_json:
        if not isinstance(raw_ref, str):
            continue
        try:
            ref_id = UUID(raw_ref)
        except ValueError:
            continue
        artifact = await session.get(Artifact, ref_id)
        if (
            artifact is not None
            and artifact.artifact_type.startswith(
                EXECUTION_PLAN_ARTIFACT_PREFIX
            )
        ):
            matches.append(artifact)
    if len(matches) != 1:
        raise AgentBridgeError(
            "agent_bridge_execution_plan_binding_invalid"
        )
    artifact = matches[0]
    if artifact.run_id != step.run_id or artifact.step_run_id != step.id:
        raise AgentBridgeError(
            "agent_bridge_execution_plan_binding_invalid"
        )
    return artifact


async def _real_approval(
    session: AsyncSession,
    *,
    authorized: AuthorizedExecutionPlan,
    plan_artifact: Artifact,
    step: StepRun,
) -> Approval | None:
    if not authorized.plan.human_gate_required:
        return None

    approval = await session.scalar(
        select(Approval)
        .where(
            Approval.run_id == authorized.run_id,
            Approval.step_key == step.step_key,
            Approval.artifact_id == plan_artifact.id,
        )
        .order_by(Approval.created_at.desc(), Approval.id.desc())
        .limit(1)
    )
    if approval is None or approval.decision != "approved":
        raise AgentBridgeError("agent_bridge_human_approval_required")
    if (
        not approval.actor_id.strip()
        or approval.actor_id == authorized.plan.worker_key
    ):
        raise AgentBridgeError(
            "agent_bridge_human_approval_actor_invalid"
        )

    checkpoint = await get_latest_checkpoint(
        session,
        run_id=authorized.run_id,
    )
    payload = (
        checkpoint.content_json
        if checkpoint is not None
        and isinstance(checkpoint.content_json, dict)
        else {}
    )
    approval_ids = payload.get("approval_ids")
    if (
        not isinstance(approval_ids, list)
        or str(approval.id) not in approval_ids
    ):
        raise AgentBridgeError(
            "agent_bridge_human_approval_not_checkpointed"
        )
    return approval


async def request_execution_plan_approval(
    session: AsyncSession,
    *,
    execution_plan_artifact_id: UUID,
    worker_key: str,
) -> Artifact:
    authorized, artifact, step = await _authorize_latest_plan(
        session,
        artifact_id=execution_plan_artifact_id,
        worker_key=worker_key,
    )
    if not authorized.plan.human_gate_required:
        raise AgentBridgeError("agent_bridge_human_gate_not_required")
    await _bind_plan_to_step(
        session,
        step=step,
        plan_artifact=artifact,
    )

    run = await session.get(ContentRun, authorized.run_id)
    if run is None:
        raise AgentBridgeError("agent_bridge_run_not_found")
    checkpoint = await get_latest_checkpoint(
        session,
        run_id=run.id,
    )
    pending = (
        checkpoint.content_json.get("pending_approval")
        if checkpoint is not None
        and isinstance(checkpoint.content_json, dict)
        else None
    )
    expected = {
        "step_key": step.step_key,
        "artifact_id": str(artifact.id),
    }
    if run.status == "waiting_approval" and pending == expected:
        assert checkpoint is not None
        return checkpoint  # exact request replay
    if run.status != "running":
        raise AgentBridgeError(
            "agent_bridge_run_not_ready_for_approval"
        )
    try:
        return await pause_for_approval(
            session,
            run_id=run.id,
            step_key=step.step_key,
            artifact_id=artifact.id,
        )
    except (ValueError, RuntimeError) as exc:
        raise AgentBridgeError(
            "agent_bridge_approval_request_failed"
        ) from exc


async def enqueue_execution_plan_job(
    session: AsyncSession,
    *,
    execution_plan_artifact_id: UUID,
    worker_key: str,
) -> Job:
    authorized, artifact, step = await _authorize_latest_plan(
        session,
        artifact_id=execution_plan_artifact_id,
        worker_key=worker_key,
    )
    if step.status != "pending":
        raise AgentBridgeError("agent_bridge_step_not_queueable")
    await _real_approval(
        session,
        authorized=authorized,
        plan_artifact=artifact,
        step=step,
    )
    await _bind_plan_to_step(
        session,
        step=step,
        plan_artifact=artifact,
    )
    return await enqueue_job(
        session,
        run_id=authorized.run_id,
        step_run_id=step.id,
        dedupe_key=_job_dedupe_key(
            plan_artifact_id=artifact.id,
            worker_key=authorized.plan.worker_key,
            step_attempt=step.attempt,
        ),
    )


def _plan_deadline(
    *,
    step: StepRun,
    plan: ExecutionPlan,
) -> datetime:
    if step.started_at is None:
        raise AgentBridgeError("agent_bridge_step_not_started")
    effective_timeout = plan.timeout_seconds
    budget_wall = _optional_float_budget(
        plan,
        "max_wall_clock_seconds",
    )
    if budget_wall is not None:
        effective_timeout = min(effective_timeout, budget_wall)
    return step.started_at + timedelta(seconds=effective_timeout)


def _lease_seconds(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
    ):
        raise AgentBridgeError("agent_bridge_lease_duration_invalid")
    return float(value)


async def _root_execution(
    session: AsyncSession,
    *,
    job: Job,
    authorized: AuthorizedExecutionPlan,
) -> DelegationExecution:
    try:
        execution = await ensure_delegation_execution(
            session,
            run_id=job.run_id,
            step_run_id=job.step_run_id,
            parent_execution_id=None,
            coordinator_key=_ROOT_COORDINATOR_KEY,
            coordinator_model_call_id=None,
            decision_artifact_id=None,
            worker_kind="application",
            worker_key=authorized.plan.worker_key,
            task_key=authorized.plan.task_key,
            dedupe_key=_root_execution_dedupe(job),
            attempt=job.attempt,
        )
        return await start_delegation_execution(
            session,
            execution_id=execution.id,
        )
    except DelegationStateError as exc:
        raise AgentBridgeError(
            "agent_bridge_root_execution_invalid"
        ) from exc


async def _root_execution_for_job(
    session: AsyncSession,
    *,
    job: Job,
) -> DelegationExecution:
    execution = await session.scalar(
        select(DelegationExecution).where(
            DelegationExecution.dedupe_key
            == _root_execution_dedupe(job)
        )
    )
    if (
        execution is None
        or execution.run_id != job.run_id
        or execution.step_run_id != job.step_run_id
    ):
        raise AgentBridgeError(
            "agent_bridge_root_execution_missing"
        )
    return execution


async def _persist_receipt(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
    artifact_type: str,
    payload: dict[str, object],
) -> tuple[Artifact, bool]:
    content_hash = _stable_hash(payload)
    existing = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == artifact_type,
            Artifact.version == 1,
        )
    )
    if existing is not None:
        if (
            existing.step_run_id != step_run_id
            or existing.content_json != payload
            or existing.content_hash != content_hash
        ):
            raise AgentBridgeError("agent_bridge_receipt_replay_conflict")
        return existing, True

    artifact = Artifact(
        run_id=run_id,
        step_run_id=step_run_id,
        artifact_type=artifact_type,
        locale=None,
        version=1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    return artifact, False


async def _claim_receipt(
    session: AsyncSession,
    *,
    job: Job,
    authorized: AuthorizedExecutionPlan,
    plan_artifact: Artifact,
    worker_instance_id: str,
    root_execution: DelegationExecution,
    approval: Approval | None,
) -> Artifact:
    payload: dict[str, object] = {
        "schema_version": AGENT_BRIDGE_SCHEMA_VERSION,
        "job_id": str(job.id),
        "job_attempt": job.attempt,
        "run_id": str(job.run_id),
        "step_run_id": str(job.step_run_id),
        "execution_plan": {
            "id": str(plan_artifact.id),
            "version": plan_artifact.version,
            "content_hash": plan_artifact.content_hash,
        },
        "worker_key": authorized.plan.worker_key,
        "worker_instance_id": worker_instance_id,
        "task_key": authorized.plan.task_key,
        "root_execution_id": str(root_execution.id),
        "approval_id": (
            str(approval.id) if approval is not None else None
        ),
    }
    artifact, _replayed = await _persist_receipt(
        session,
        run_id=job.run_id,
        step_run_id=job.step_run_id,
        artifact_type=_artifact_type(
            "agent_bridge_claim_",
            f"{job.id}:{job.attempt}",
        ),
        payload=payload,
    )
    return artifact


async def _load_job_plan(
    session: AsyncSession,
    *,
    job: Job,
    worker_key: str,
) -> tuple[AuthorizedExecutionPlan, Artifact, StepRun, Approval | None]:
    step = await session.get(StepRun, job.step_run_id)
    if step is None or step.run_id != job.run_id:
        raise AgentBridgeError("agent_bridge_job_step_invalid")
    plan_artifact = await _bound_plan_artifact(
        session,
        step=step,
    )
    authorized, latest_artifact, authorized_step = (
        await _authorize_latest_plan(
            session,
            artifact_id=plan_artifact.id,
            worker_key=worker_key,
        )
    )
    if latest_artifact.id != plan_artifact.id or authorized_step.id != step.id:
        raise AgentBridgeError(
            "agent_bridge_execution_plan_binding_invalid"
        )
    if job.attempt > authorized.plan.max_attempts:
        raise AgentBridgeError("agent_bridge_job_attempt_exceeds_plan")
    approval = await _real_approval(
        session,
        authorized=authorized,
        plan_artifact=plan_artifact,
        step=step,
    )
    await _enforce_plan_budget(
        session,
        authorized=authorized,
    )
    return authorized, plan_artifact, step, approval


async def _existing_worker_lease(
    session: AsyncSession,
    *,
    worker_key: str,
    worker_instance_id: str,
) -> Job | None:
    now = utc_now()
    job: Job | None = await session.scalar(
        select(Job)
        .where(
            Job.status == "leased",
            Job.lease_owner == worker_instance_id,
            Job.lease_expires_at > now,
            Job.dedupe_key.like(f"{_worker_bucket(worker_key)}%"),
        )
        .order_by(Job.created_at, Job.id)
        .limit(1)
        .with_for_update()
    )
    return job


async def _queued_worker_job(
    session: AsyncSession,
    *,
    worker_key: str,
) -> Job | None:
    now = utc_now()
    job: Job | None = await session.scalar(
        select(Job)
        .where(
            Job.status == "queued",
            Job.available_at <= now,
            Job.dedupe_key.like(f"{_worker_bucket(worker_key)}%"),
        )
        .order_by(Job.available_at, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return job


async def _expired_worker_job(
    session: AsyncSession,
    *,
    worker_key: str,
) -> Job | None:
    now = utc_now()
    job: Job | None = await session.scalar(
        select(Job)
        .where(
            Job.status == "leased",
            Job.lease_expires_at <= now,
            Job.dedupe_key.like(f"{_worker_bucket(worker_key)}%"),
        )
        .order_by(Job.lease_expires_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return job


async def _lease_payload(
    session: AsyncSession,
    *,
    job: Job,
    worker_key: str,
    worker_instance_id: str,
    replayed: bool,
) -> AgentTaskLease:
    (
        authorized,
        plan_artifact,
        step,
        approval,
    ) = await _load_job_plan(
        session,
        job=job,
        worker_key=worker_key,
    )
    now = utc_now()
    deadline = _plan_deadline(
        step=step,
        plan=authorized.plan,
    )
    if now >= deadline:
        raise AgentBridgeError("agent_bridge_plan_timeout")
    if (
        job.lease_expires_at is None
        or job.lease_expires_at <= now
        or job.lease_owner != worker_instance_id
        or job.status != "leased"
    ):
        raise AgentBridgeError("agent_bridge_lease_invalid")
    if job.lease_expires_at > deadline:
        raise AgentBridgeError("agent_bridge_lease_exceeds_plan_timeout")

    root = await _root_execution(
        session,
        job=job,
        authorized=authorized,
    )
    await _claim_receipt(
        session,
        job=job,
        authorized=authorized,
        plan_artifact=plan_artifact,
        worker_instance_id=worker_instance_id,
        root_execution=root,
        approval=approval,
    )
    return AgentTaskLease(
        job_id=job.id,
        run_id=job.run_id,
        step_run_id=job.step_run_id,
        execution_plan_artifact_id=plan_artifact.id,
        worker_key=authorized.plan.worker_key,
        worker_instance_id=worker_instance_id,
        task_key=authorized.plan.task_key,
        job_attempt=job.attempt,
        step_attempt=step.attempt,
        lease_expires_at=job.lease_expires_at,
        plan_deadline=deadline,
        root_execution_id=root.id,
        approval_id=approval.id if approval is not None else None,
        execution_plan=_execution_plan_payload(authorized.plan),
        settings_snapshot_id=authorized.plan.settings_snapshot_id,
        settings_snapshot_hash=authorized.plan.settings_snapshot_hash,
        replayed=replayed,
    )


async def claim_agent_task(
    session: AsyncSession,
    *,
    worker_key: str,
    worker_instance_id: str,
    lease_seconds: float,
) -> AgentTaskLease | None:
    normalized_worker = _required_text(
        worker_key,
        "agent_bridge_worker_key_required",
    )
    instance = _required_text(
        worker_instance_id,
        "agent_bridge_worker_instance_required",
    )
    requested_lease = _lease_seconds(lease_seconds)

    existing = await _existing_worker_lease(
        session,
        worker_key=normalized_worker,
        worker_instance_id=instance,
    )
    if existing is not None:
        return await _lease_payload(
            session,
            job=existing,
            worker_key=normalized_worker,
            worker_instance_id=instance,
            replayed=True,
        )

    job = await _queued_worker_job(
        session,
        worker_key=normalized_worker,
    )
    reclaimed = False
    if job is None:
        job = await _expired_worker_job(
            session,
            worker_key=normalized_worker,
        )
        reclaimed = job is not None
    if job is None:
        return None

    (
        authorized,
        _plan_artifact,
        step,
        _approval,
    ) = await _load_job_plan(
        session,
        job=job,
        worker_key=normalized_worker,
    )
    now = utc_now()
    if reclaimed:
        if job.attempt >= authorized.plan.max_attempts:
            raise AgentBridgeError(
                "agent_bridge_reclaim_attempts_exhausted"
            )
        old_root = await _root_execution_for_job(
            session,
            job=job,
        )
        if old_root.status != "running":
            raise AgentBridgeError(
                "agent_bridge_expired_lease_state_inconsistent"
            )
        try:
            await fail_delegation_execution(
                session,
                execution_id=old_root.id,
                error_class="lease_lost",
            )
        except DelegationStateError as exc:
            raise AgentBridgeError(
                "agent_bridge_root_execution_invalid"
            ) from exc
        job.attempt += 1
    else:
        if step.status != "pending":
            raise AgentBridgeError("agent_bridge_step_not_claimable")
        step.status = "running"
        step.started_at = now
        step.updated_at = now

    deadline = _plan_deadline(
        step=step,
        timeout_seconds=authorized.plan.timeout_seconds,
    )
    if now >= deadline:
        raise AgentBridgeError("agent_bridge_plan_timeout")
    actual_seconds = min(
        requested_lease,
        max((deadline - now).total_seconds(), 0.0),
    )
    if actual_seconds <= 0:
        raise AgentBridgeError("agent_bridge_plan_timeout")
    job.status = "leased"
    job.lease_owner = instance
    job.lease_expires_at = now + timedelta(seconds=actual_seconds)
    job.updated_at = now
    await session.flush()

    return await _lease_payload(
        session,
        job=job,
        worker_key=normalized_worker,
        worker_instance_id=instance,
        replayed=False,
    )


async def heartbeat_agent_task(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_key: str,
    worker_instance_id: str,
    extend_seconds: float,
) -> AgentTaskLease:
    normalized_worker = _required_text(
        worker_key,
        "agent_bridge_worker_key_required",
    )
    instance = _required_text(
        worker_instance_id,
        "agent_bridge_worker_instance_required",
    )
    requested = _lease_seconds(extend_seconds)
    job = await session.get(Job, job_id)
    if job is None:
        raise AgentBridgeError("agent_bridge_job_not_found")
    (
        authorized,
        _plan_artifact,
        step,
        _approval,
    ) = await _load_job_plan(
        session,
        job=job,
        worker_key=normalized_worker,
    )
    deadline = _plan_deadline(
        step=step,
        timeout_seconds=authorized.plan.timeout_seconds,
    )
    now = utc_now()
    if now >= deadline:
        raise AgentBridgeError("agent_bridge_plan_timeout")
    actual_seconds = min(
        requested,
        max((deadline - now).total_seconds(), 0.0),
    )
    try:
        updated = await heartbeat_job(
            session,
            job_id=job.id,
            worker_id=instance,
            extend_by=timedelta(seconds=actual_seconds),
        )
    except LeaseOwnershipError as exc:
        raise AgentBridgeError("agent_bridge_lease_invalid") from exc
    if (
        updated.lease_expires_at is not None
        and updated.lease_expires_at > deadline
    ):
        updated.lease_expires_at = deadline
        await session.flush()
    return await _lease_payload(
        session,
        job=updated,
        worker_key=normalized_worker,
        worker_instance_id=instance,
        replayed=True,
    )


async def _owned_active_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_instance_id: str,
) -> Job:
    now = utc_now()
    job = await session.scalar(
        select(Job).where(Job.id == job_id).with_for_update()
    )
    if (
        job is None
        or job.status != "leased"
        or job.lease_owner != worker_instance_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
    ):
        raise AgentBridgeError("agent_bridge_lease_invalid")
    return job


def _normalize_output_refs(value: object) -> list[UUID]:
    if not isinstance(value, list) or not value:
        raise AgentBridgeError("agent_bridge_output_refs_required")
    refs: list[UUID] = []
    for item in value:
        if not isinstance(item, (UUID, str)):
            raise AgentBridgeError("agent_bridge_output_ref_invalid")
        try:
            ref = item if isinstance(item, UUID) else UUID(item)
        except ValueError as exc:
            raise AgentBridgeError(
                "agent_bridge_output_ref_invalid"
            ) from exc
        if ref in refs:
            raise AgentBridgeError("agent_bridge_output_ref_duplicate")
        refs.append(ref)
    return refs


async def _validated_outputs(
    session: AsyncSession,
    *,
    job: Job,
    plan: ExecutionPlan,
    output_refs: object,
) -> tuple[list[UUID], list[Artifact]]:
    refs = _normalize_output_refs(output_refs)
    step = await session.get(StepRun, job.step_run_id)
    if step is None or step.started_at is None:
        raise AgentBridgeError("agent_bridge_step_not_started")
    artifacts: list[Artifact] = []
    for ref in refs:
        artifact = await session.get(Artifact, ref)
        if (
            artifact is None
            or artifact.run_id != job.run_id
            or artifact.step_run_id != job.step_run_id
        ):
            raise AgentBridgeError(
                "agent_bridge_output_artifact_binding_invalid"
            )
        if artifact.artifact_type not in plan.expected_output_types:
            raise AgentBridgeError(
                "agent_bridge_output_type_not_expected"
            )
        if (
            artifact.content_json is not None
            and artifact.content_hash != _stable_hash(artifact.content_json)
        ):
            raise AgentBridgeError(
                "agent_bridge_output_artifact_hash_mismatch"
            )
        if artifact.created_at < step.started_at:
            raise AgentBridgeError(
                "agent_bridge_output_artifact_predates_execution"
            )
        latest = await session.scalar(
            select(Artifact)
            .where(
                Artifact.run_id == job.run_id,
                Artifact.step_run_id == job.step_run_id,
                Artifact.artifact_type == artifact.artifact_type,
            )
            .order_by(Artifact.version.desc(), Artifact.id.desc())
            .limit(1)
        )
        if latest is None or latest.id != artifact.id:
            raise AgentBridgeError(
                "agent_bridge_output_artifact_stale"
            )
        artifacts.append(artifact)

    observed_types = {artifact.artifact_type for artifact in artifacts}
    if not set(plan.expected_output_types).issubset(observed_types):
        raise AgentBridgeError(
            "agent_bridge_expected_output_missing"
        )
    return refs, artifacts


def _normalize_safe_telemetry(
    value: object,
) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise AgentBridgeError("agent_bridge_telemetry_invalid")
    if not set(value).issubset(_SAFE_TELEMETRY_FIELDS):
        raise AgentBridgeError("agent_bridge_telemetry_field_forbidden")
    normalized: dict[str, str] = {}
    for key, item in value.items():
        if (
            not isinstance(item, str)
            or not item.strip()
            or len(item.strip()) > 255
        ):
            raise AgentBridgeError("agent_bridge_telemetry_invalid")
        normalized[str(key)] = item.strip()
    return normalized


async def _runtime_counts(
    session: AsyncSession,
    *,
    job: Job,
    root_execution: DelegationExecution,
) -> dict[str, int]:
    model_calls = await session.scalar(
        select(func.count()).select_from(ModelCall).where(
            ModelCall.run_id == job.run_id,
            ModelCall.step_run_id == job.step_run_id,
        )
    )
    tool_calls = await session.scalar(
        select(func.count()).select_from(ToolCall).where(
            ToolCall.run_id == job.run_id,
            ToolCall.step_run_id == job.step_run_id,
        )
    )
    subagents = await session.scalar(
        select(func.count()).select_from(DelegationExecution).where(
            DelegationExecution.parent_execution_id
            == root_execution.id
        )
    )
    return {
        "model_calls": int(model_calls or 0),
        "tool_calls": int(tool_calls or 0),
        "subagent_count": int(subagents or 0),
    }


async def _review_request(
    session: AsyncSession,
    *,
    job: Job,
    plan_artifact: Artifact,
    plan: ExecutionPlan,
    output_refs: list[UUID],
    completion_receipt: Artifact,
) -> Artifact:
    payload: dict[str, object] = {
        "schema_version": AGENT_BRIDGE_SCHEMA_VERSION,
        "job_id": str(job.id),
        "run_id": str(job.run_id),
        "step_run_id": str(job.step_run_id),
        "task_key": plan.task_key,
        "worker_key": plan.worker_key,
        "execution_plan": {
            "id": str(plan_artifact.id),
            "version": plan_artifact.version,
            "content_hash": plan_artifact.content_hash,
        },
        "completion_receipt": {
            "id": str(completion_receipt.id),
            "content_hash": completion_receipt.content_hash,
        },
        "reviewer": plan.reviewer,
        "required_checks": list(plan.required_checks),
        "next_on_pass": plan.next_on_pass,
        "next_on_fail": plan.next_on_fail,
        "output_refs": [str(value) for value in output_refs],
    }
    artifact, _replayed = await _persist_receipt(
        session,
        run_id=job.run_id,
        step_run_id=job.step_run_id,
        artifact_type=_artifact_type(
            "agent_review_request_",
            job.id,
        ),
        payload=payload,
    )
    return artifact


async def _completed_replay(
    session: AsyncSession,
    *,
    job: Job,
    worker_key: str,
    worker_instance_id: str,
    output_refs: object,
    telemetry: object,
) -> AgentTaskCompletion:
    completion_type = _artifact_type(
        "agent_bridge_complete_",
        f"{job.id}:{job.attempt}",
    )
    receipt = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == job.run_id,
            Artifact.artifact_type == completion_type,
            Artifact.version == 1,
        )
    )
    if receipt is None or not isinstance(receipt.content_json, dict):
        raise AgentBridgeError(
            "agent_bridge_completed_receipt_missing"
        )
    if receipt.content_hash != _stable_hash(receipt.content_json):
        raise AgentBridgeError(
            "agent_bridge_completed_receipt_invalid"
        )
    payload = receipt.content_json
    normalized_refs = [str(value) for value in _normalize_output_refs(output_refs)]
    safe_telemetry = _normalize_safe_telemetry(telemetry)
    if (
        payload.get("worker_key") != worker_key
        or payload.get("worker_instance_id") != worker_instance_id
        or payload.get("output_refs") != normalized_refs
        or payload.get("reported_telemetry") != safe_telemetry
    ):
        raise AgentBridgeError(
            "agent_bridge_completion_replay_conflict"
        )
    review = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == job.run_id,
            Artifact.artifact_type
            == _artifact_type("agent_review_request_", job.id),
            Artifact.version == 1,
        )
    )
    if review is None:
        raise AgentBridgeError(
            "agent_bridge_review_request_missing"
        )
    await _review_request_artifact(
        session,
        review_request_id=review.id,
    )
    return AgentTaskCompletion(
        job_id=job.id,
        completion_receipt_id=receipt.id,
        review_request_id=review.id,
        replayed=True,
    )


async def complete_agent_task(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_key: str,
    worker_instance_id: str,
    output_refs: object,
    telemetry: object = None,
) -> AgentTaskCompletion:
    normalized_worker = _required_text(
        worker_key,
        "agent_bridge_worker_key_required",
    )
    instance = _required_text(
        worker_instance_id,
        "agent_bridge_worker_instance_required",
    )
    job = await session.scalar(
        select(Job).where(Job.id == job_id).with_for_update()
    )
    if job is None:
        raise AgentBridgeError("agent_bridge_job_not_found")
    if job.status == "completed":
        return await _completed_replay(
            session,
            job=job,
            worker_key=normalized_worker,
            worker_instance_id=instance,
            output_refs=output_refs,
            telemetry=telemetry,
        )
    if job.status != "leased":
        raise AgentBridgeError("agent_bridge_job_not_completable")
    if job.lease_owner != instance:
        raise AgentBridgeError("agent_bridge_lease_invalid")
    job = await _owned_active_job(
        session,
        job_id=job.id,
        worker_instance_id=instance,
    )
    (
        authorized,
        plan_artifact,
        step,
        _approval,
    ) = await _load_job_plan(
        session,
        job=job,
        worker_key=normalized_worker,
    )
    deadline = _plan_deadline(
        step=step,
        timeout_seconds=authorized.plan.timeout_seconds,
    )
    if utc_now() >= deadline:
        raise AgentBridgeError("agent_bridge_plan_timeout")

    refs, _artifacts = await _validated_outputs(
        session,
        job=job,
        plan=authorized.plan,
        output_refs=output_refs,
    )
    safe_telemetry = _normalize_safe_telemetry(telemetry)
    root = await _root_execution_for_job(session, job=job)
    if root.status != "running":
        raise AgentBridgeError(
            "agent_bridge_root_execution_not_running"
        )
    counts = await _runtime_counts(
        session,
        job=job,
        root_execution=root,
    )
    payload: dict[str, object] = {
        "schema_version": AGENT_BRIDGE_SCHEMA_VERSION,
        "job_id": str(job.id),
        "job_attempt": job.attempt,
        "run_id": str(job.run_id),
        "step_run_id": str(job.step_run_id),
        "execution_plan": {
            "id": str(plan_artifact.id),
            "version": plan_artifact.version,
            "content_hash": plan_artifact.content_hash,
        },
        "worker_key": authorized.plan.worker_key,
        "worker_instance_id": instance,
        "task_key": authorized.plan.task_key,
        "root_execution_id": str(root.id),
        "output_refs": [str(value) for value in refs],
        "reported_telemetry": safe_telemetry,
        "runtime_counts": counts,
    }
    completion_receipt, _ = await _persist_receipt(
        session,
        run_id=job.run_id,
        step_run_id=job.step_run_id,
        artifact_type=_artifact_type(
            "agent_bridge_complete_",
            f"{job.id}:{job.attempt}",
        ),
        payload=payload,
    )
    review_request = await _review_request(
        session,
        job=job,
        plan_artifact=plan_artifact,
        plan=authorized.plan,
        output_refs=refs,
        completion_receipt=completion_receipt,
    )

    existing_output_refs = list(step.output_artifact_refs_json)
    normalized_output_refs = [str(value) for value in refs]
    if existing_output_refs and existing_output_refs != normalized_output_refs:
        raise AgentBridgeError(
            "agent_bridge_step_output_conflict"
        )
    step.output_artifact_refs_json = normalized_output_refs

    try:
        await complete_delegation_execution(
            session,
            execution_id=root.id,
            result_artifact_id=completion_receipt.id,
        )
    except DelegationStateError as exc:
        raise AgentBridgeError(
            "agent_bridge_root_completion_invalid"
        ) from exc

    now = utc_now()
    job.status = "completed"
    job.lease_owner = None
    job.lease_expires_at = None
    job.updated_at = now
    step.status = "completed"
    step.completed_at = now
    step.updated_at = now
    await session.flush()

    return AgentTaskCompletion(
        job_id=job.id,
        completion_receipt_id=completion_receipt.id,
        review_request_id=review_request.id,
        replayed=False,
    )


def _execution_plan_input(plan: ExecutionPlan) -> dict[str, object]:
    return {
        "schema_version": 1,
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
    }


async def _failure_replay(
    session: AsyncSession,
    *,
    job: Job,
    worker_key: str,
    worker_instance_id: str,
    failure_class: str,
    message: str,
) -> AgentTaskFailure:
    artifact = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == job.run_id,
            Artifact.artifact_type
            == _artifact_type(
                "agent_bridge_fail_",
                f"{job.id}:{job.attempt}",
            ),
            Artifact.version == 1,
        )
    )
    if artifact is None or not isinstance(artifact.content_json, dict):
        raise AgentBridgeError(
            "agent_bridge_failure_receipt_missing"
        )
    if artifact.content_hash != _stable_hash(artifact.content_json):
        raise AgentBridgeError(
            "agent_bridge_failure_receipt_invalid"
        )
    payload = artifact.content_json
    if (
        payload.get("worker_key") != worker_key
        or payload.get("worker_instance_id") != worker_instance_id
        or payload.get("failure_class") != failure_class
        or payload.get("message") != message
    ):
        raise AgentBridgeError("agent_bridge_failure_replay_conflict")
    retry_step = payload.get("retry_step_run_id")
    retry_plan = payload.get("retry_execution_plan_artifact_id")
    retry_job = payload.get("retry_job_id")
    return AgentTaskFailure(
        job_id=job.id,
        failure_receipt_id=artifact.id,
        retry_step_run_id=UUID(retry_step)
        if isinstance(retry_step, str)
        else None,
        retry_execution_plan_artifact_id=UUID(retry_plan)
        if isinstance(retry_plan, str)
        else None,
        retry_job_id=UUID(retry_job)
        if isinstance(retry_job, str)
        else None,
        retry_requires_approval=bool(
            payload.get("retry_requires_approval")
        ),
        replayed=True,
    )


async def fail_agent_task(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_key: str,
    worker_instance_id: str,
    failure_class: str,
    message: str,
) -> AgentTaskFailure:
    normalized_worker = _required_text(
        worker_key,
        "agent_bridge_worker_key_required",
    )
    instance = _required_text(
        worker_instance_id,
        "agent_bridge_worker_instance_required",
    )
    failure = _required_text(
        failure_class,
        "agent_bridge_failure_class_required",
    )
    detail = _required_text(
        message,
        "agent_bridge_failure_message_required",
    )
    try:
        retryable = is_retryable_failure(failure)
    except UnknownFailureClassError as exc:
        raise AgentBridgeError(
            "agent_bridge_failure_class_invalid"
        ) from exc

    job = await session.scalar(
        select(Job).where(Job.id == job_id).with_for_update()
    )
    if job is None:
        raise AgentBridgeError("agent_bridge_job_not_found")
    if job.status == "failed":
        return await _failure_replay(
            session,
            job=job,
            worker_key=normalized_worker,
            worker_instance_id=instance,
            failure_class=failure,
            message=detail,
        )
    job = await _owned_active_job(
        session,
        job_id=job.id,
        worker_instance_id=instance,
    )
    (
        authorized,
        plan_artifact,
        step,
        _approval,
    ) = await _load_job_plan(
        session,
        job=job,
        worker_key=normalized_worker,
    )
    root = await _root_execution_for_job(session, job=job)
    if root.status == "running":
        try:
            await fail_delegation_execution(
                session,
                execution_id=root.id,
                error_class=failure,
            )
        except DelegationStateError as exc:
            raise AgentBridgeError(
                "agent_bridge_root_failure_invalid"
            ) from exc

    now = utc_now()
    job.status = "failed"
    job.lease_owner = None
    job.lease_expires_at = None
    job.updated_at = now
    step.status = "failed"
    step.completed_at = now
    step.error_json = {"class": failure, "message": detail}
    step.updated_at = now

    retry_step: StepRun | None = None
    retry_plan_artifact: Artifact | None = None
    retry_job: Job | None = None
    retry_requires_approval = False

    if retryable and step.attempt < authorized.plan.max_attempts:
        retry_step = StepRun(
            run_id=step.run_id,
            step_key=step.step_key,
            attempt=step.attempt + 1,
            status="pending",
            input_artifact_refs_json=[
                raw_ref
                for raw_ref in step.input_artifact_refs_json
                if raw_ref != str(plan_artifact.id)
            ],
            output_artifact_refs_json=[],
        )
        session.add(retry_step)
        await session.flush()
        try:
            retry_plan_artifact = await persist_execution_plan_artifact(
                session,
                run_id=job.run_id,
                step_run_id=retry_step.id,
                plan=_execution_plan_input(authorized.plan),
            )
        except ExecutionPlanError as exc:
            raise AgentBridgeError(exc.code) from exc
        await _bind_plan_to_step(
            session,
            step=retry_step,
            plan_artifact=retry_plan_artifact,
        )
        if authorized.plan.human_gate_required:
            retry_requires_approval = True
            try:
                await pause_for_approval(
                    session,
                    run_id=job.run_id,
                    step_key=retry_step.step_key,
                    artifact_id=retry_plan_artifact.id,
                )
            except (ValueError, RuntimeError) as exc:
                raise AgentBridgeError(
                    "agent_bridge_retry_approval_request_failed"
                ) from exc
        else:
            retry_job = await enqueue_job(
                session,
                run_id=job.run_id,
                step_run_id=retry_step.id,
                dedupe_key=_job_dedupe_key(
                    plan_artifact_id=retry_plan_artifact.id,
                    worker_key=authorized.plan.worker_key,
                    step_attempt=retry_step.attempt,
                ),
            )
    else:
        run = await session.get(ContentRun, job.run_id)
        if run is None:
            raise AgentBridgeError("agent_bridge_run_not_found")
        if run.status == "running":
            run.status = "failed"
            run.completed_at = now
        run.failure_code = failure
        run.failure_message = detail

    payload: dict[str, object] = {
        "schema_version": AGENT_BRIDGE_SCHEMA_VERSION,
        "job_id": str(job.id),
        "job_attempt": job.attempt,
        "run_id": str(job.run_id),
        "step_run_id": str(job.step_run_id),
        "execution_plan": {
            "id": str(plan_artifact.id),
            "version": plan_artifact.version,
            "content_hash": plan_artifact.content_hash,
        },
        "worker_key": authorized.plan.worker_key,
        "worker_instance_id": instance,
        "root_execution_id": str(root.id),
        "failure_class": failure,
        "message": detail,
        "retry_step_run_id": (
            str(retry_step.id) if retry_step is not None else None
        ),
        "retry_execution_plan_artifact_id": (
            str(retry_plan_artifact.id)
            if retry_plan_artifact is not None
            else None
        ),
        "retry_job_id": (
            str(retry_job.id) if retry_job is not None else None
        ),
        "retry_requires_approval": retry_requires_approval,
    }
    receipt, _ = await _persist_receipt(
        session,
        run_id=job.run_id,
        step_run_id=job.step_run_id,
        artifact_type=_artifact_type(
            "agent_bridge_fail_",
            f"{job.id}:{job.attempt}",
        ),
        payload=payload,
    )
    await session.flush()
    return AgentTaskFailure(
        job_id=job.id,
        failure_receipt_id=receipt.id,
        retry_step_run_id=(
            retry_step.id if retry_step is not None else None
        ),
        retry_execution_plan_artifact_id=(
            retry_plan_artifact.id
            if retry_plan_artifact is not None
            else None
        ),
        retry_job_id=retry_job.id if retry_job is not None else None,
        retry_requires_approval=retry_requires_approval,
        replayed=False,
    )


async def start_subagent_telemetry(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_instance_id: str,
    child_worker_key: str,
    child_task_key: str,
    dedupe_key: str,
    attempt: int = 1,
) -> DelegationExecution:
    instance = _required_text(
        worker_instance_id,
        "agent_bridge_worker_instance_required",
    )
    child_worker = _required_text(
        child_worker_key,
        "agent_bridge_subagent_worker_required",
    )
    child_task = _required_text(
        child_task_key,
        "agent_bridge_subagent_task_required",
    )
    logical_key = _required_text(
        dedupe_key,
        "agent_bridge_subagent_dedupe_required",
    )
    job = await _owned_active_job(
        session,
        job_id=job_id,
        worker_instance_id=instance,
    )
    root = await _root_execution_for_job(session, job=job)
    if root.status != "running":
        raise AgentBridgeError(
            "agent_bridge_root_execution_not_running"
        )
    try:
        child = await ensure_delegation_execution(
            session,
            run_id=job.run_id,
            step_run_id=job.step_run_id,
            parent_execution_id=root.id,
            coordinator_key=_ROOT_COORDINATOR_KEY,
            coordinator_model_call_id=None,
            decision_artifact_id=None,
            worker_kind="subagent",
            worker_key=child_worker,
            task_key=child_task,
            dedupe_key=(
                "agent_bridge_child:"
                f"{root.id}:"
                f"{hashlib.sha256(logical_key.encode('utf-8')).hexdigest()[:24]}"
            ),
            attempt=attempt,
        )
        return await start_delegation_execution(
            session,
            execution_id=child.id,
        )
    except DelegationStateError as exc:
        raise AgentBridgeError(
            "agent_bridge_subagent_telemetry_invalid"
        ) from exc


async def complete_subagent_telemetry(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_instance_id: str,
    execution_id: UUID,
    result_artifact_id: UUID | None = None,
) -> DelegationExecution:
    job = await _owned_active_job(
        session,
        job_id=job_id,
        worker_instance_id=worker_instance_id,
    )
    execution = await session.get(DelegationExecution, execution_id)
    root = await _root_execution_for_job(session, job=job)
    if (
        execution is None
        or execution.parent_execution_id != root.id
        or execution.run_id != job.run_id
        or execution.step_run_id != job.step_run_id
    ):
        raise AgentBridgeError(
            "agent_bridge_subagent_binding_invalid"
        )
    try:
        return await complete_delegation_execution(
            session,
            execution_id=execution.id,
            result_artifact_id=result_artifact_id,
        )
    except DelegationStateError as exc:
        raise AgentBridgeError(
            "agent_bridge_subagent_completion_invalid"
        ) from exc


async def fail_subagent_telemetry(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_instance_id: str,
    execution_id: UUID,
    error_class: str,
) -> DelegationExecution:
    job = await _owned_active_job(
        session,
        job_id=job_id,
        worker_instance_id=worker_instance_id,
    )
    execution = await session.get(DelegationExecution, execution_id)
    root = await _root_execution_for_job(session, job=job)
    if (
        execution is None
        or execution.parent_execution_id != root.id
        or execution.run_id != job.run_id
        or execution.step_run_id != job.step_run_id
    ):
        raise AgentBridgeError(
            "agent_bridge_subagent_binding_invalid"
        )
    try:
        return await fail_delegation_execution(
            session,
            execution_id=execution.id,
            error_class=_required_text(
                error_class,
                "agent_bridge_subagent_error_required",
            ),
        )
    except DelegationStateError as exc:
        raise AgentBridgeError(
            "agent_bridge_subagent_failure_invalid"
        ) from exc


def _uuid_value(value: object, code: str) -> UUID:
    if not isinstance(value, str):
        raise AgentBridgeError(code)
    try:
        return UUID(value)
    except ValueError as exc:
        raise AgentBridgeError(code) from exc


def _object_dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AgentBridgeError(code)
    return {str(key): item for key, item in value.items()}


def _string_list(value: object, code: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise AgentBridgeError(code)
    return [str(item) for item in value]


async def _validate_review_request_semantics(
    session: AsyncSession,
    *,
    artifact: Artifact,
    payload: dict[str, object],
) -> None:
    if artifact.step_run_id is None:
        raise AgentBridgeError("agent_bridge_review_step_missing")
    job_id = _uuid_value(
        payload.get("job_id"),
        "agent_bridge_review_request_invalid",
    )
    job = await session.get(Job, job_id)
    if (
        job is None
        or job.status != "completed"
        or job.run_id != artifact.run_id
        or job.step_run_id != artifact.step_run_id
        or artifact.artifact_type
        != _artifact_type("agent_review_request_", job.id)
    ):
        raise AgentBridgeError(
            "agent_bridge_review_request_semantic_mismatch"
        )

    step = await session.get(StepRun, job.step_run_id)
    if (
        step is None
        or step.status != "completed"
        or step.run_id != job.run_id
    ):
        raise AgentBridgeError(
            "agent_bridge_review_request_semantic_mismatch"
        )
    output_refs = _string_list(
        payload.get("output_refs"),
        "agent_bridge_review_request_invalid",
    )
    if output_refs != step.output_artifact_refs_json:
        raise AgentBridgeError(
            "agent_bridge_review_request_semantic_mismatch"
        )

    completion_ref = _object_dict(
        payload.get("completion_receipt"),
        "agent_bridge_review_request_invalid",
    )
    completion_id = _uuid_value(
        completion_ref.get("id"),
        "agent_bridge_review_request_invalid",
    )
    completion = await session.get(Artifact, completion_id)
    if (
        completion is None
        or completion.run_id != job.run_id
        or completion.step_run_id != job.step_run_id
        or completion.artifact_type
        != _artifact_type(
            "agent_bridge_complete_",
            f"{job.id}:{job.attempt}",
        )
        or not isinstance(completion.content_json, dict)
        or completion.content_hash
        != _stable_hash(completion.content_json)
        or completion_ref.get("content_hash")
        != completion.content_hash
    ):
        raise AgentBridgeError(
            "agent_bridge_review_request_semantic_mismatch"
        )
    completion_payload = completion.content_json
    if (
        completion_payload.get("job_id") != str(job.id)
        or completion_payload.get("job_attempt") != job.attempt
        or completion_payload.get("run_id") != str(job.run_id)
        or completion_payload.get("step_run_id")
        != str(job.step_run_id)
        or completion_payload.get("output_refs") != output_refs
    ):
        raise AgentBridgeError(
            "agent_bridge_review_request_semantic_mismatch"
        )

    root_id = _uuid_value(
        completion_payload.get("root_execution_id"),
        "agent_bridge_review_request_invalid",
    )
    root = await session.get(DelegationExecution, root_id)
    if (
        root is None
        or root.status != "completed"
        or root.run_id != job.run_id
        or root.step_run_id != job.step_run_id
        or root.result_artifact_id != completion.id
    ):
        raise AgentBridgeError(
            "agent_bridge_review_request_semantic_mismatch"
        )

    request_plan_ref = _object_dict(
        payload.get("execution_plan"),
        "agent_bridge_review_request_invalid",
    )
    completion_plan_ref = _object_dict(
        completion_payload.get("execution_plan"),
        "agent_bridge_review_request_invalid",
    )
    if request_plan_ref != completion_plan_ref:
        raise AgentBridgeError(
            "agent_bridge_review_request_semantic_mismatch"
        )
    plan_id = _uuid_value(
        request_plan_ref.get("id"),
        "agent_bridge_review_request_invalid",
    )
    plan_artifact = await session.get(Artifact, plan_id)
    if (
        plan_artifact is None
        or plan_artifact.run_id != job.run_id
        or plan_artifact.step_run_id != job.step_run_id
        or not plan_artifact.artifact_type.startswith(
            EXECUTION_PLAN_ARTIFACT_PREFIX
        )
        or not isinstance(plan_artifact.content_json, dict)
        or plan_artifact.content_hash
        != _stable_hash(plan_artifact.content_json)
        or request_plan_ref.get("version") != plan_artifact.version
        or request_plan_ref.get("content_hash")
        != plan_artifact.content_hash
    ):
        raise AgentBridgeError(
            "agent_bridge_review_request_semantic_mismatch"
        )
    plan_payload = plan_artifact.content_json
    expected: dict[str, object] = {
        "schema_version": AGENT_BRIDGE_SCHEMA_VERSION,
        "job_id": str(job.id),
        "run_id": str(job.run_id),
        "step_run_id": str(job.step_run_id),
        "task_key": plan_payload.get("task_key"),
        "worker_key": plan_payload.get("worker_key"),
        "execution_plan": {
            "id": str(plan_artifact.id),
            "version": plan_artifact.version,
            "content_hash": plan_artifact.content_hash,
        },
        "completion_receipt": {
            "id": str(completion.id),
            "content_hash": completion.content_hash,
        },
        "reviewer": plan_payload.get("reviewer"),
        "required_checks": plan_payload.get("required_checks"),
        "next_on_pass": plan_payload.get("next_on_pass"),
        "next_on_fail": plan_payload.get("next_on_fail"),
        "output_refs": output_refs,
    }
    if payload != expected:
        raise AgentBridgeError(
            "agent_bridge_review_request_semantic_mismatch"
        )


async def _review_request_artifact(
    session: AsyncSession,
    *,
    review_request_id: UUID,
) -> tuple[Artifact, dict[str, object]]:
    artifact = await session.get(Artifact, review_request_id)
    if (
        artifact is None
        or not isinstance(artifact.content_json, dict)
        or artifact.content_hash != _stable_hash(artifact.content_json)
    ):
        raise AgentBridgeError(
            "agent_bridge_review_request_invalid"
        )
    payload = artifact.content_json
    await _validate_review_request_semantics(
        session,
        artifact=artifact,
        payload=payload,
    )
    return artifact, payload


def _normalize_review_checks(
    value: object,
    *,
    required_checks: list[str],
    decision: str,
) -> dict[str, bool]:
    if not isinstance(value, dict):
        raise AgentBridgeError("agent_bridge_review_checks_invalid")
    if set(value) != set(required_checks):
        raise AgentBridgeError(
            "agent_bridge_review_checks_mismatch"
        )
    normalized: dict[str, bool] = {}
    for key in required_checks:
        result = value.get(key)
        if not isinstance(result, bool):
            raise AgentBridgeError(
                "agent_bridge_review_checks_invalid"
            )
        normalized[key] = result
    if decision == "pass" and not all(normalized.values()):
        raise AgentBridgeError(
            "agent_bridge_review_pass_checks_failed"
        )
    if decision == "fail" and all(normalized.values()):
        raise AgentBridgeError(
            "agent_bridge_review_fail_requires_failure"
        )
    return normalized


async def record_agent_review(
    session: AsyncSession,
    *,
    review_request_id: UUID,
    reviewer_key: str,
    decision: str,
    checks: object,
    comment: str | None = None,
) -> AgentReviewResult:
    request_artifact, request = await _review_request_artifact(
        session,
        review_request_id=review_request_id,
    )
    reviewer = _required_text(
        reviewer_key,
        "agent_bridge_reviewer_required",
    )
    expected_reviewer = request.get("reviewer")
    worker_key = request.get("worker_key")
    if (
        not isinstance(expected_reviewer, str)
        or reviewer != expected_reviewer
        or reviewer == worker_key
    ):
        raise AgentBridgeError(
            "agent_bridge_reviewer_mismatch"
        )
    normalized_decision = _required_text(
        decision,
        "agent_bridge_review_decision_required",
    ).lower()
    if normalized_decision not in {"pass", "fail"}:
        raise AgentBridgeError(
            "agent_bridge_review_decision_invalid"
        )
    raw_required = request.get("required_checks")
    if (
        not isinstance(raw_required, list)
        or not all(
            isinstance(item, str) and item
            for item in raw_required
        )
    ):
        raise AgentBridgeError(
            "agent_bridge_review_request_invalid"
        )
    required_checks = [str(item) for item in raw_required]
    normalized_checks = _normalize_review_checks(
        checks,
        required_checks=required_checks,
        decision=normalized_decision,
    )
    normalized_comment: str | None = None
    if comment is not None:
        normalized_comment = _required_text(
            comment,
            "agent_bridge_review_comment_invalid",
        )

    payload: dict[str, object] = {
        "schema_version": AGENT_BRIDGE_SCHEMA_VERSION,
        "review_request": {
            "id": str(request_artifact.id),
            "content_hash": request_artifact.content_hash,
        },
        "run_id": request.get("run_id"),
        "step_run_id": request.get("step_run_id"),
        "reviewer": reviewer,
        "decision": normalized_decision,
        "checks": normalized_checks,
        "comment": normalized_comment,
    }
    result, replayed = await _persist_receipt(
        session,
        run_id=request_artifact.run_id,
        step_run_id=request_artifact.step_run_id
        if request_artifact.step_run_id is not None
        else _raise_missing_review_step(),
        artifact_type=_artifact_type(
            "agent_review_result_",
            request_artifact.id,
        ),
        payload=payload,
    )
    return AgentReviewResult(
        review_result_id=result.id,
        decision=normalized_decision,
        replayed=replayed,
    )


def _raise_missing_review_step() -> UUID:
    raise AgentBridgeError("agent_bridge_review_step_missing")


def _expected_review_result_payload(
    *,
    result_payload: dict[str, object],
    request_artifact: Artifact,
    request_payload: dict[str, object],
) -> dict[str, object]:
    reviewer = _required_text(
        result_payload.get("reviewer"),
        "agent_bridge_review_result_invalid",
    )
    expected_reviewer = request_payload.get("reviewer")
    worker_key = request_payload.get("worker_key")
    if (
        not isinstance(expected_reviewer, str)
        or reviewer != expected_reviewer
        or reviewer == worker_key
    ):
        raise AgentBridgeError(
            "agent_bridge_review_result_semantic_mismatch"
        )
    decision = _required_text(
        result_payload.get("decision"),
        "agent_bridge_review_result_invalid",
    ).lower()
    if decision not in {"pass", "fail"}:
        raise AgentBridgeError(
            "agent_bridge_review_result_invalid"
        )
    required_checks = _string_list(
        request_payload.get("required_checks"),
        "agent_bridge_review_request_invalid",
    )
    checks = _normalize_review_checks(
        result_payload.get("checks"),
        required_checks=required_checks,
        decision=decision,
    )
    comment = result_payload.get("comment")
    if comment is not None:
        comment = _required_text(
            comment,
            "agent_bridge_review_comment_invalid",
        )
    return {
        "schema_version": AGENT_BRIDGE_SCHEMA_VERSION,
        "review_request": {
            "id": str(request_artifact.id),
            "content_hash": request_artifact.content_hash,
        },
        "run_id": request_payload.get("run_id"),
        "step_run_id": request_payload.get("step_run_id"),
        "reviewer": reviewer,
        "decision": decision,
        "checks": checks,
        "comment": comment,
    }


async def _review_result_artifact(
    session: AsyncSession,
    *,
    review_result_id: UUID,
) -> tuple[Artifact, dict[str, object], Artifact, dict[str, object]]:
    result = await session.get(Artifact, review_result_id)
    if (
        result is None
        or not result.artifact_type.startswith(
            "agent_review_result_"
        )
        or not isinstance(result.content_json, dict)
        or result.content_hash != _stable_hash(result.content_json)
    ):
        raise AgentBridgeError(
            "agent_bridge_review_result_invalid"
        )
    result_payload = result.content_json
    request_ref = result_payload.get("review_request")
    if not isinstance(request_ref, dict):
        raise AgentBridgeError(
            "agent_bridge_review_result_invalid"
        )
    raw_request_id = request_ref.get("id")
    if not isinstance(raw_request_id, str):
        raise AgentBridgeError(
            "agent_bridge_review_result_invalid"
        )
    try:
        request_id = UUID(raw_request_id)
    except ValueError as exc:
        raise AgentBridgeError(
            "agent_bridge_review_result_invalid"
        ) from exc
    request_artifact, request_payload = (
        await _review_request_artifact(
            session,
            review_request_id=request_id,
        )
    )
    if (
        request_ref.get("content_hash")
        != request_artifact.content_hash
        or result.run_id != request_artifact.run_id
        or result.step_run_id != request_artifact.step_run_id
        or result.artifact_type
        != _artifact_type(
            "agent_review_result_",
            request_artifact.id,
        )
    ):
        raise AgentBridgeError(
            "agent_bridge_review_result_binding_invalid"
        )
    expected = _expected_review_result_payload(
        result_payload=result_payload,
        request_artifact=request_artifact,
        request_payload=request_payload,
    )
    if result_payload != expected:
        raise AgentBridgeError(
            "agent_bridge_review_result_semantic_mismatch"
        )
    return (
        result,
        result_payload,
        request_artifact,
        request_payload,
    )


async def materialize_auto_next(
    session: AsyncSession,
    *,
    review_result_id: UUID,
) -> AutoNextResult:
    (
        result_artifact,
        review,
        request_artifact,
        request,
    ) = await _review_result_artifact(
        session,
        review_result_id=review_result_id,
    )
    decision = review.get("decision")
    if decision == "pass":
        route = request.get("next_on_pass")
    elif decision == "fail":
        route = request.get("next_on_fail")
    else:
        raise AgentBridgeError(
            "agent_bridge_review_result_invalid"
        )
    route_key = _required_text(
        route,
        "agent_bridge_next_route_invalid",
    )
    if not _NEXT_STEP_RE.fullmatch(route_key):
        raise AgentBridgeError(
            "agent_bridge_next_route_invalid"
        )

    raw_step_id = request.get("step_run_id")
    if not isinstance(raw_step_id, str):
        raise AgentBridgeError(
            "agent_bridge_review_request_invalid"
        )
    try:
        completed_step_id = UUID(raw_step_id)
    except ValueError as exc:
        raise AgentBridgeError(
            "agent_bridge_review_request_invalid"
        ) from exc
    completed_step = await session.get(
        StepRun,
        completed_step_id,
    )
    if (
        completed_step is None
        or completed_step.status != "completed"
        or completed_step.run_id != request_artifact.run_id
    ):
        raise AgentBridgeError(
            "agent_bridge_reviewed_step_not_completed"
        )
    if route_key == completed_step.step_key:
        raise AgentBridgeError(
            "agent_bridge_next_route_same_step"
        )

    run = await session.scalar(
        select(ContentRun)
        .where(ContentRun.id == request_artifact.run_id)
        .with_for_update()
    )
    if run is None or run.status != "running":
        raise AgentBridgeError(
            "agent_bridge_run_not_auto_next_ready"
        )

    route_type = _artifact_type(
        "agent_route_decision_",
        result_artifact.id,
    )
    existing_receipt = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == run.id,
            Artifact.artifact_type == route_type,
            Artifact.version == 1,
        )
    )
    if existing_receipt is not None:
        if (
            not isinstance(existing_receipt.content_json, dict)
            or existing_receipt.content_hash
            != _stable_hash(existing_receipt.content_json)
        ):
            raise AgentBridgeError(
                "agent_bridge_route_receipt_invalid"
            )
        raw_next = existing_receipt.content_json.get(
            "next_step_run_id"
        )
        if (
            not isinstance(raw_next, str)
            or existing_receipt.content_json.get("route")
            != route_key
            or run.current_step != route_key
        ):
            raise AgentBridgeError(
                "agent_bridge_route_replay_conflict"
            )
        try:
            next_step_id = UUID(raw_next)
        except ValueError as exc:
            raise AgentBridgeError(
                "agent_bridge_route_receipt_invalid"
            ) from exc
        return AutoNextResult(
            review_result_id=result_artifact.id,
            route=route_key,
            next_step_run_id=next_step_id,
            route_receipt_id=existing_receipt.id,
            replayed=True,
        )

    if run.current_step != completed_step.step_key:
        raise AgentBridgeError(
            "agent_bridge_current_step_changed"
        )

    raw_outputs = request.get("output_refs")
    if (
        not isinstance(raw_outputs, list)
        or not all(isinstance(item, str) for item in raw_outputs)
    ):
        raise AgentBridgeError(
            "agent_bridge_review_request_invalid"
        )
    next_step = await session.scalar(
        select(StepRun).where(
            StepRun.run_id == run.id,
            StepRun.step_key == route_key,
            StepRun.attempt == 1,
        )
    )
    if next_step is None:
        next_step = StepRun(
            run_id=run.id,
            step_key=route_key,
            attempt=1,
            status="pending",
            input_artifact_refs_json=list(raw_outputs),
            output_artifact_refs_json=[],
        )
        session.add(next_step)
        await session.flush()
    elif (
        next_step.status != "pending"
        or next_step.input_artifact_refs_json != list(raw_outputs)
    ):
        raise AgentBridgeError(
            "agent_bridge_next_step_conflict"
        )

    run.current_step = route_key
    payload: dict[str, object] = {
        "schema_version": AGENT_BRIDGE_SCHEMA_VERSION,
        "review_result": {
            "id": str(result_artifact.id),
            "content_hash": result_artifact.content_hash,
        },
        "review_request_id": str(request_artifact.id),
        "completed_step_run_id": str(completed_step.id),
        "route": route_key,
        "next_step_run_id": str(next_step.id),
        "input_refs": list(raw_outputs),
        "job_enqueued": False,
    }
    route_receipt, _ = await _persist_receipt(
        session,
        run_id=run.id,
        step_run_id=completed_step.id,
        artifact_type=route_type,
        payload=payload,
    )
    await create_checkpoint(session, run_id=run.id)
    await session.flush()
    return AutoNextResult(
        review_result_id=result_artifact.id,
        route=route_key,
        next_step_run_id=next_step.id,
        route_receipt_id=route_receipt.id,
        replayed=False,
    )


__all__ = [
    "AGENT_BRIDGE_SCHEMA_VERSION",
    "AgentBridgeError",
    "AgentReviewResult",
    "AgentTaskCompletion",
    "AgentTaskFailure",
    "AgentTaskLease",
    "AutoNextResult",
    "claim_agent_task",
    "complete_agent_task",
    "complete_subagent_telemetry",
    "enqueue_execution_plan_job",
    "fail_agent_task",
    "fail_subagent_telemetry",
    "heartbeat_agent_task",
    "materialize_auto_next",
    "record_agent_review",
    "request_execution_plan_approval",
    "start_subagent_telemetry",
]
