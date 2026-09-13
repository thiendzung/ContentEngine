"""Safe durable lifecycle for Codex delegation telemetry."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import get_logger
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.models import Artifact, ContentRun, ModelCall, StepRun, utc_now

logger = get_logger("delegation")


class DelegationStateError(ValueError):
    """Raised when a delegation lifecycle transition is invalid."""


class DelegationConflictError(ValueError):
    """Raised when a dedupe key is reused for a different logical delegation."""


async def ensure_delegation_execution(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    parent_execution_id: UUID | None,
    worker_kind: str,
    worker_key: str,
    task_key: str,
    dedupe_key: str,
    coordinator_key: str = "codex",
    coordinator_model_call_id: UUID | None = None,
    decision_artifact_id: UUID | None = None,
    attempt: int = 1,
    external_execution_id: str | None = None,
) -> DelegationExecution:
    """Create one queued delegation or return the exact existing logical record."""

    _require_nonempty("coordinator_key", coordinator_key)
    _require_nonempty("worker_key", worker_key)
    _require_nonempty("task_key", task_key)
    _require_nonempty("dedupe_key", dedupe_key)
    if worker_kind not in {"subagent", "application", "tool"}:
        raise DelegationStateError("invalid_worker_kind")
    if attempt <= 0:
        raise DelegationStateError("attempt_must_be_positive")

    run = await session.get(ContentRun, run_id)
    if run is None:
        raise DelegationStateError("ContentRun not found")
    await _validate_step(session, run_id=run_id, step_run_id=step_run_id)
    await _validate_parent(
        session,
        run_id=run_id,
        step_run_id=step_run_id,
        parent_execution_id=parent_execution_id,
    )
    await _validate_control_provenance(
        session,
        run_id=run_id,
        step_run_id=step_run_id,
        coordinator_model_call_id=coordinator_model_call_id,
        decision_artifact_id=decision_artifact_id,
    )

    values = {
        "run_id": run_id,
        "step_run_id": step_run_id,
        "parent_execution_id": parent_execution_id,
        "coordinator_key": coordinator_key,
        "coordinator_model_call_id": coordinator_model_call_id,
        "decision_artifact_id": decision_artifact_id,
        "worker_kind": worker_kind,
        "worker_key": worker_key,
        "task_key": task_key,
        "attempt": attempt,
        "status": "queued",
        "dedupe_key": dedupe_key,
        "external_execution_id": external_execution_id,
    }
    statement = (
        insert(DelegationExecution)
        .values(**values)
        .on_conflict_do_nothing(index_elements=[DelegationExecution.dedupe_key])
        .returning(DelegationExecution.id)
    )
    execution_id = (await session.execute(statement)).scalar_one_or_none()
    if execution_id is not None:
        execution = await session.get(DelegationExecution, execution_id)
        assert execution is not None
        logger.info("delegation_queued", extra=_log_fields(execution))
        return execution

    existing = await session.scalar(
        select(DelegationExecution).where(DelegationExecution.dedupe_key == dedupe_key)
    )
    assert existing is not None
    _assert_same_identity(
        existing,
        run_id=run_id,
        step_run_id=step_run_id,
        parent_execution_id=parent_execution_id,
        coordinator_key=coordinator_key,
        coordinator_model_call_id=coordinator_model_call_id,
        decision_artifact_id=decision_artifact_id,
        worker_kind=worker_kind,
        worker_key=worker_key,
        task_key=task_key,
        attempt=attempt,
        external_execution_id=external_execution_id,
    )
    logger.debug("delegation_reused", extra=_log_fields(existing))
    return existing


async def bind_delegation_model_call(
    session: AsyncSession,
    *,
    execution_id: UUID,
    model_call_id: UUID,
) -> DelegationExecution:
    """Bind one exact worker ModelCall to a delegation without permitting rebinding."""

    execution = await _locked_execution(session, execution_id)
    call = await session.get(ModelCall, model_call_id)
    if call is None:
        raise DelegationStateError("worker ModelCall not found")
    if call.run_id != execution.run_id or call.step_run_id != execution.step_run_id:
        raise DelegationStateError("worker ModelCall does not belong to delegation")
    if execution.worker_model_call_id is not None:
        if execution.worker_model_call_id != model_call_id:
            raise DelegationConflictError("delegation worker ModelCall mismatch")
        return execution
    execution.worker_model_call_id = model_call_id
    await session.flush()
    logger.debug("delegation_model_call_bound", extra=_log_fields(execution))
    return execution


async def start_delegation_execution(
    session: AsyncSession,
    *,
    execution_id: UUID,
) -> DelegationExecution:
    execution = await _locked_execution(session, execution_id)
    if execution.status == "running":
        return execution
    if execution.status != "queued":
        raise DelegationStateError(f"invalid delegation transition: {execution.status} -> running")
    execution.status = "running"
    execution.started_at = utc_now()
    await session.flush()
    logger.info("delegation_started", extra=_log_fields(execution))
    return execution


async def complete_delegation_execution(
    session: AsyncSession,
    *,
    execution_id: UUID,
    result_artifact_id: UUID | None = None,
    external_execution_id: str | None = None,
) -> DelegationExecution:
    execution = await _locked_execution(session, execution_id)
    if execution.status == "completed":
        if execution.result_artifact_id != result_artifact_id:
            raise DelegationConflictError("completed delegation result artifact mismatch")
        if (
            external_execution_id is not None
            and execution.external_execution_id != external_execution_id
        ):
            raise DelegationConflictError("completed delegation external execution mismatch")
        return execution
    if execution.status != "running":
        raise DelegationStateError(
            f"invalid delegation transition: {execution.status} -> completed"
        )
    if result_artifact_id is not None:
        await _validate_result_artifact(
            session,
            execution=execution,
            result_artifact_id=result_artifact_id,
        )
    if external_execution_id is not None:
        execution.external_execution_id = external_execution_id
    execution.result_artifact_id = result_artifact_id
    execution.status = "completed"
    execution.completed_at = utc_now()
    await session.flush()
    logger.info("delegation_completed", extra=_log_fields(execution))
    return execution


async def fail_delegation_execution(
    session: AsyncSession,
    *,
    execution_id: UUID,
    error_class: str,
) -> DelegationExecution:
    _require_nonempty("error_class", error_class)
    execution = await _locked_execution(session, execution_id)
    if execution.status == "failed":
        if execution.error_class != error_class:
            raise DelegationConflictError("failed delegation error class mismatch")
        return execution
    if execution.status != "running":
        raise DelegationStateError(f"invalid delegation transition: {execution.status} -> failed")
    execution.status = "failed"
    execution.error_class = error_class
    execution.completed_at = utc_now()
    await session.flush()
    logger.error("delegation_failed", extra=_log_fields(execution))
    return execution


async def cancel_delegation_execution(
    session: AsyncSession,
    *,
    execution_id: UUID,
) -> DelegationExecution:
    execution = await _locked_execution(session, execution_id)
    if execution.status == "cancelled":
        return execution
    if execution.status not in {"queued", "running"}:
        raise DelegationStateError(
            f"invalid delegation transition: {execution.status} -> cancelled"
        )
    execution.status = "cancelled"
    execution.completed_at = utc_now()
    await session.flush()
    logger.info("delegation_cancelled", extra=_log_fields(execution))
    return execution


async def _locked_execution(session: AsyncSession, execution_id: UUID) -> DelegationExecution:
    execution = await session.scalar(
        select(DelegationExecution)
        .where(DelegationExecution.id == execution_id)
        .with_for_update()
    )
    if execution is None:
        raise DelegationStateError("DelegationExecution not found")
    return execution


async def _validate_step(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
) -> None:
    if step_run_id is None:
        return
    step = await session.get(StepRun, step_run_id)
    if step is None or step.run_id != run_id:
        raise DelegationStateError("StepRun does not belong to ContentRun")


async def _validate_parent(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    parent_execution_id: UUID | None,
) -> None:
    if parent_execution_id is None:
        return
    parent = await session.get(DelegationExecution, parent_execution_id)
    if parent is None:
        raise DelegationStateError("parent DelegationExecution not found")
    if parent.run_id != run_id:
        raise DelegationStateError("parent delegation belongs to another ContentRun")
    if (
        parent.step_run_id is not None
        and step_run_id is not None
        and parent.step_run_id != step_run_id
    ):
        raise DelegationStateError("parent delegation belongs to another StepRun")


async def _validate_control_provenance(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    coordinator_model_call_id: UUID | None,
    decision_artifact_id: UUID | None,
) -> None:
    if coordinator_model_call_id is None and decision_artifact_id is None:
        return
    if coordinator_model_call_id is None or decision_artifact_id is None:
        raise DelegationStateError("controlled delegation provenance is incomplete")
    call = await session.get(ModelCall, coordinator_model_call_id)
    if call is None or call.run_id != run_id or call.step_run_id != step_run_id:
        raise DelegationStateError("coordinator ModelCall does not belong to delegation")
    if call.status != "completed" or call.result_artifact_id != decision_artifact_id:
        raise DelegationStateError("coordinator ModelCall has no completed decision artifact")
    artifact = await session.get(Artifact, decision_artifact_id)
    if artifact is None or artifact.run_id != run_id or artifact.step_run_id != step_run_id:
        raise DelegationStateError("decision Artifact does not belong to delegation")


async def _validate_result_artifact(
    session: AsyncSession,
    *,
    execution: DelegationExecution,
    result_artifact_id: UUID,
) -> None:
    artifact = await session.get(Artifact, result_artifact_id)
    if artifact is None or artifact.run_id != execution.run_id:
        raise DelegationStateError("result Artifact does not belong to delegation run")
    if execution.step_run_id is not None and artifact.step_run_id != execution.step_run_id:
        raise DelegationStateError("result Artifact does not belong to delegation step")


def _assert_same_identity(
    execution: DelegationExecution,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    parent_execution_id: UUID | None,
    coordinator_key: str,
    coordinator_model_call_id: UUID | None,
    decision_artifact_id: UUID | None,
    worker_kind: str,
    worker_key: str,
    task_key: str,
    attempt: int,
    external_execution_id: str | None,
) -> None:
    identity = (
        execution.run_id,
        execution.step_run_id,
        execution.parent_execution_id,
        execution.coordinator_key,
        execution.coordinator_model_call_id,
        execution.decision_artifact_id,
        execution.worker_kind,
        execution.worker_key,
        execution.task_key,
        execution.attempt,
    )
    expected = (
        run_id,
        step_run_id,
        parent_execution_id,
        coordinator_key,
        coordinator_model_call_id,
        decision_artifact_id,
        worker_kind,
        worker_key,
        task_key,
        attempt,
    )
    if identity != expected:
        raise DelegationConflictError("dedupe key already belongs to another delegation")
    if (
        external_execution_id is not None
        and execution.external_execution_id != external_execution_id
    ):
        raise DelegationConflictError("dedupe key external execution mismatch")


def _log_fields(execution: DelegationExecution) -> dict[str, object]:
    fields: dict[str, object] = {
        "event": "delegation_execution",
        "execution_id": str(execution.id),
        "content_run_id": str(execution.run_id),
        "task_key": execution.task_key,
        "worker_key": execution.worker_key,
        "worker_kind": execution.worker_kind,
        "status": execution.status,
    }
    if execution.step_run_id is not None:
        fields["step_run_id"] = str(execution.step_run_id)
    if execution.coordinator_model_call_id is not None:
        fields["coordinator_model_call_id"] = str(execution.coordinator_model_call_id)
    if execution.worker_model_call_id is not None:
        fields["worker_model_call_id"] = str(execution.worker_model_call_id)
    if execution.error_class is not None:
        fields["error_class"] = execution.error_class
    return fields


def _require_nonempty(field: str, value: str) -> None:
    if not value.strip():
        raise DelegationStateError(f"{field}_is_required")


__all__ = [
    "DelegationConflictError",
    "DelegationStateError",
    "bind_delegation_model_call",
    "cancel_delegation_execution",
    "complete_delegation_execution",
    "ensure_delegation_execution",
    "fail_delegation_execution",
    "start_delegation_execution",
]
