from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from test_au01_execution_plan import (
    _approved_policy_snapshot,
    _plan,
    _policy,
)
from test_ce05_review_console import _approved_fixture, isolated_session

from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_bridge import (
    AgentBridgeError,
    claim_agent_task,
    complete_agent_task,
    complete_subagent_telemetry,
    enqueue_execution_plan_job,
    fail_agent_task,
    heartbeat_agent_task,
    materialize_auto_next,
    record_agent_review,
    request_execution_plan_approval,
    start_subagent_telemetry,
)
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.execution_plan import (
    ExecutionPlanError,
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
from app.modules.harness.persistence import create_checkpoint, resolve_approval
from app.modules.system.settings_service import create_settings_snapshot


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


async def _pending_fixture(
    session,
    *,
    settings: dict[str, object] | None = None,
) -> tuple[ContentRun, StepRun]:
    base = await _approved_fixture(session)
    source = base.writer_runs["en"]
    snapshot = await _approved_policy_snapshot(
        session,
        project_id=source.project_id,
        settings=settings or _policy(),
    )
    run = ContentRun(
        project_id=source.project_id,
        content_case_id=source.content_case_id,
        locale_variant_id=source.locale_variant_id,
        content_item_id=source.content_item_id,
        run_mode="update",
        status="running",
        current_step="customer_map_refresh",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    step = StepRun(
        run_id=run.id,
        step_key="customer_map_refresh",
        attempt=1,
        status="pending",
        input_artifact_refs_json=[],
        output_artifact_refs_json=[],
    )
    session.add(step)
    await session.flush()
    return run, step


async def _persist_default_plan(
    session,
    *,
    run: ContentRun,
    step: StepRun,
    plan: dict[str, object] | None = None,
    version: int = 1,
) -> Artifact:
    return await persist_execution_plan_artifact(
        session,
        run_id=run.id,
        step_run_id=step.id,
        plan=plan or _plan(),
        version=version,
    )


def _sensitive_settings_and_plan() -> tuple[
    dict[str, object],
    dict[str, object],
]:
    settings = _policy(
        capabilities=[
            "READ",
            "WRITE_ARTIFACT",
            "RUN_TOOL",
            "WRITE_DATABASE",
            "PUBLISH",
        ],
        allowed_actions=[
            "read.customer",
            "database.write.customer_map",
            "artifact.write.customer_map",
            "publish.execute",
        ],
        forbidden_actions=[
            "settings.change",
            "workflow.change",
        ],
    )
    plan = _plan(
        required_capabilities=[
            "READ",
            "WRITE_ARTIFACT",
            "RUN_TOOL",
            "WRITE_DATABASE",
            "PUBLISH",
        ],
        allowed_actions=[
            "read.customer",
            "database.write.customer_map",
            "artifact.write.customer_map",
            "publish.execute",
        ],
        forbidden_actions=[
            "settings.change",
            "workflow.change",
        ],
        human_gate_required=True,
    )
    return settings, plan


async def _approve_plan(
    session,
    *,
    run: ContentRun,
    step: StepRun,
    plan_artifact: Artifact,
    worker_key: str = "customer-map-worker",
    actor_id: str = "founder",
) -> Approval:
    await request_execution_plan_approval(
        session,
        execution_plan_artifact_id=plan_artifact.id,
        worker_key=worker_key,
    )
    approval = await resolve_approval(
        session,
        run_id=run.id,
        step_key=step.step_key,
        artifact_id=plan_artifact.id,
        decision="approved",
        actor_id=actor_id,
        comment="Approve exact AU-02 execution plan.",
    )
    return approval


async def _output_artifact(
    session,
    *,
    run: ContentRun,
    step: StepRun,
    artifact_type: str = "customer_map_snapshot",
    payload: dict[str, object] | None = None,
    content_hash: str | None = None,
) -> Artifact:
    content = payload or {"schema_version": 1, "value": "fixture"}
    artifact = Artifact(
        run_id=run.id,
        step_run_id=step.id,
        artifact_type=artifact_type,
        version=1,
        content_json=content,
        content_hash=content_hash or _hash(content),
    )
    session.add(artifact)
    await session.flush()
    return artifact


def _passing_checks() -> dict[str, bool]:
    return {
        "schema_valid": True,
        "project_scope_valid": True,
        "output_traceable": True,
    }


@pytest.mark.asyncio
async def test_safe_plan_enqueues_claims_and_exact_claim_replays() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )

        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        lease = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="local-agent-1",
            lease_seconds=30,
        )
        assert lease is not None
        assert lease.job_id == job.id
        assert lease.execution_plan_artifact_id == plan_artifact.id
        assert lease.execution_plan_artifact_version == plan_artifact.version
        assert lease.execution_plan_artifact_hash == plan_artifact.content_hash
        assert lease.approval_id is None
        assert lease.execution_plan["task_key"] == "customer_map_refresh"
        assert lease.execution_plan["worker_key"] == "customer-map-worker"
        assert lease.execution_plan["settings_snapshot_id"] == str(
            run.settings_snapshot_id
        )
        assert lease.settings_snapshot_id == run.settings_snapshot_id
        assert lease.settings_snapshot_hash == lease.execution_plan[
            "settings_snapshot_hash"
        ]
        assert lease.replayed is False

        replay = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="local-agent-1",
            lease_seconds=30,
        )
        assert replay is not None
        assert replay.job_id == lease.job_id
        assert replay.root_execution_id == lease.root_execution_id
        assert replay.replayed is True

        await session.refresh(step)
        await session.refresh(job)
        assert step.status == "running"
        assert job.status == "leased"
        assert str(plan_artifact.id) in step.input_artifact_refs_json

        root = await session.get(
            DelegationExecution,
            lease.root_execution_id,
        )
        assert root is not None
        assert root.status == "running"
        assert root.coordinator_key == "local_bridge"
        assert root.worker_key == "customer-map-worker"


@pytest.mark.asyncio
async def test_wrong_worker_cannot_claim_another_worker_plan() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )

        lease = await claim_agent_task(
            session,
            worker_key="different-worker",
            worker_instance_id="other-instance",
            lease_seconds=30,
        )
        assert lease is None


@pytest.mark.asyncio
async def test_human_gated_plan_requires_canonical_approval_before_queue() -> None:
    async with isolated_session() as session:
        settings, plan = _sensitive_settings_and_plan()
        run, step = await _pending_fixture(
            session,
            settings=settings,
        )
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
            plan=plan,
        )

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_human_approval_required",
        ):
            await enqueue_execution_plan_job(
                session,
                execution_plan_artifact_id=plan_artifact.id,
                worker_key="customer-map-worker",
            )

        approval = await _approve_plan(
            session,
            run=run,
            step=step,
            plan_artifact=plan_artifact,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        lease = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="approved-agent",
            lease_seconds=30,
        )
        assert lease is not None
        assert lease.job_id == job.id
        assert lease.approval_id == approval.id


@pytest.mark.asyncio
async def test_direct_approval_without_checkpoint_does_not_authorize() -> None:
    async with isolated_session() as session:
        settings, plan = _sensitive_settings_and_plan()
        run, step = await _pending_fixture(
            session,
            settings=settings,
        )
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
            plan=plan,
        )
        session.add(
            Approval(
                run_id=run.id,
                step_key=step.step_key,
                artifact_id=plan_artifact.id,
                decision="approved",
                actor_id="founder",
                comment="Direct insert must not be enough.",
            )
        )
        await session.flush()

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_human_approval_not_checkpointed",
        ):
            await enqueue_execution_plan_job(
                session,
                execution_plan_artifact_id=plan_artifact.id,
                worker_key="customer-map-worker",
            )


@pytest.mark.asyncio
async def test_approval_row_plus_generic_checkpoint_is_not_real_approval() -> None:
    async with isolated_session() as session:
        settings, plan = _sensitive_settings_and_plan()
        run, step = await _pending_fixture(
            session,
            settings=settings,
        )
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
            plan=plan,
        )
        approval = Approval(
            run_id=run.id,
            step_key=step.step_key,
            artifact_id=plan_artifact.id,
            decision="approved",
            actor_id="founder",
            comment="Synthetic approval row without approval-request provenance.",
        )
        session.add(approval)
        await session.flush()
        await create_checkpoint(session, run_id=run.id)

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_human_approval_request_missing",
        ):
            await enqueue_execution_plan_job(
                session,
                execution_plan_artifact_id=plan_artifact.id,
                worker_key="customer-map-worker",
            )


@pytest.mark.asyncio
async def test_worker_cannot_be_its_own_human_approver() -> None:
    async with isolated_session() as session:
        settings, plan = _sensitive_settings_and_plan()
        run, step = await _pending_fixture(
            session,
            settings=settings,
        )
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
            plan=plan,
        )
        await _approve_plan(
            session,
            run=run,
            step=step,
            plan_artifact=plan_artifact,
            actor_id="customer-map-worker",
        )

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_human_approval_actor_invalid",
        ):
            await enqueue_execution_plan_job(
                session,
                execution_plan_artifact_id=plan_artifact.id,
                worker_key="customer-map-worker",
            )


@pytest.mark.asyncio
async def test_stale_execution_plan_version_cannot_queue() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        first = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        second = await _persist_default_plan(
            session,
            run=run,
            step=step,
            plan=_plan(goal="Revised bounded goal."),
            version=2,
        )

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_execution_plan_stale",
        ):
            await enqueue_execution_plan_job(
                session,
                execution_plan_artifact_id=first.id,
                worker_key="customer-map-worker",
            )

        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=second.id,
            worker_key="customer-map-worker",
        )
        assert job.step_run_id == step.id


@pytest.mark.asyncio
async def test_heartbeat_requires_owner_and_never_crosses_plan_deadline() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        lease = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="heartbeat-agent",
            lease_seconds=20,
        )
        assert lease is not None

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_lease_invalid",
        ):
            await heartbeat_agent_task(
                session,
                job_id=lease.job_id,
                worker_key="customer-map-worker",
                worker_instance_id="wrong-agent",
                extend_seconds=60,
            )

        extended = await heartbeat_agent_task(
            session,
            job_id=lease.job_id,
            worker_key="customer-map-worker",
            worker_instance_id="heartbeat-agent",
            extend_seconds=600,
        )
        assert extended.lease_expires_at <= extended.plan_deadline

        step.started_at = utc_now() - timedelta(seconds=121)
        await session.flush()
        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_budget_exceeded",
        ):
            await heartbeat_agent_task(
                session,
                job_id=lease.job_id,
                worker_key="customer-map-worker",
                worker_instance_id="heartbeat-agent",
                extend_seconds=10,
            )


@pytest.mark.asyncio
async def test_expired_lease_can_reclaim_once_with_new_root_attempt() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        first = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="agent-a",
            lease_seconds=10,
        )
        assert first is not None
        job = await session.get(Job, first.job_id)
        assert job is not None
        job.lease_expires_at = utc_now() - timedelta(seconds=1)
        await session.flush()

        second = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="agent-b",
            lease_seconds=10,
        )
        assert second is not None
        assert second.job_id == first.job_id
        assert second.job_attempt == 2
        assert second.root_execution_id != first.root_execution_id

        old_root = await session.get(
            DelegationExecution,
            first.root_execution_id,
        )
        assert old_root is not None
        assert old_root.status == "failed"
        assert old_root.error_class == "lease_lost"

        job.lease_expires_at = utc_now() - timedelta(seconds=1)
        await session.flush()
        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_reclaim_attempts_exhausted",
        ):
            await claim_agent_task(
                session,
                worker_key="customer-map-worker",
                worker_instance_id="agent-c",
                lease_seconds=10,
            )


@pytest.mark.asyncio
async def test_completion_requires_expected_bound_hash_valid_outputs() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        lease = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="complete-agent",
            lease_seconds=30,
        )
        assert lease is not None

        wrong_type = await _output_artifact(
            session,
            run=run,
            step=step,
            artifact_type="unexpected_output",
        )
        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_output_type_not_expected",
        ):
            await complete_agent_task(
                session,
                job_id=lease.job_id,
                worker_key="customer-map-worker",
                worker_instance_id="complete-agent",
                output_refs=[wrong_type.id],
            )

        bad_hash = await _output_artifact(
            session,
            run=run,
            step=step,
            payload={"schema_version": 1, "value": "bad-hash"},
            content_hash="0" * 64,
        )
        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_output_artifact_hash_mismatch",
        ):
            await complete_agent_task(
                session,
                job_id=lease.job_id,
                worker_key="customer-map-worker",
                worker_instance_id="complete-agent",
                output_refs=[bad_hash.id],
            )


@pytest.mark.asyncio
async def test_completion_review_and_auto_next_are_idempotent() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        lease = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="finish-agent",
            lease_seconds=30,
        )
        assert lease is not None
        output = await _output_artifact(
            session,
            run=run,
            step=step,
        )
        jobs_before = await session.scalar(
            select(func.count()).select_from(Job)
        )

        completed = await complete_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="finish-agent",
            output_refs=[output.id],
            telemetry={"runner_version": "local-test-v1"},
        )
        replay = await complete_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="finish-agent",
            output_refs=[output.id],
            telemetry={"runner_version": "local-test-v1"},
        )
        assert replay.completion_receipt_id == completed.completion_receipt_id
        assert replay.review_request_id == completed.review_request_id
        assert replay.replayed is True

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_reviewer_mismatch",
        ):
            await record_agent_review(
                session,
                review_request_id=completed.review_request_id,
                reviewer_key="customer-map-worker",
                decision="pass",
                checks=_passing_checks(),
            )

        review = await record_agent_review(
            session,
            review_request_id=completed.review_request_id,
            reviewer_key="customer-map-reviewer",
            decision="pass",
            checks=_passing_checks(),
            comment="Independent checks passed.",
        )
        route = await materialize_auto_next(
            session,
            review_result_id=review.review_result_id,
        )
        route_replay = await materialize_auto_next(
            session,
            review_result_id=review.review_result_id,
        )
        assert route.route == "coverage_refresh"
        assert route.replayed is False
        assert route_replay.route_receipt_id == route.route_receipt_id
        assert route_replay.next_step_run_id == route.next_step_run_id
        assert route_replay.replayed is True

        next_step = await session.get(StepRun, route.next_step_run_id)
        assert next_step is not None
        assert next_step.status == "pending"
        assert next_step.input_artifact_refs_json == [str(output.id)]
        await session.refresh(run)
        assert run.current_step == "coverage_refresh"

        jobs_after = await session.scalar(
            select(func.count()).select_from(Job)
        )
        assert jobs_after == jobs_before

        review_request = await session.get(
            Artifact,
            completed.review_request_id,
        )
        assert review_request is not None
        assert review_request.content_json is not None
        assert review_request.content_json["reviewer"] == "customer-map-reviewer"
        assert review_request.content_json["required_checks"] == [
            "schema_valid",
            "project_scope_valid",
            "output_traceable",
        ]


@pytest.mark.asyncio
async def test_review_checks_must_be_exact_and_fail_route_is_explicit() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="review-agent-worker",
            lease_seconds=30,
        )
        output = await _output_artifact(
            session,
            run=run,
            step=step,
        )
        completed = await complete_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="review-agent-worker",
            output_refs=[output.id],
        )

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_review_checks_mismatch",
        ):
            await record_agent_review(
                session,
                review_request_id=completed.review_request_id,
                reviewer_key="customer-map-reviewer",
                decision="pass",
                checks={"schema_valid": True},
            )

        failed_checks = _passing_checks()
        failed_checks["project_scope_valid"] = False
        review = await record_agent_review(
            session,
            review_request_id=completed.review_request_id,
            reviewer_key="customer-map-reviewer",
            decision="fail",
            checks=failed_checks,
        )
        route = await materialize_auto_next(
            session,
            review_result_id=review.review_result_id,
        )
        assert route.route == "blocked"


@pytest.mark.asyncio
async def test_auto_next_rejects_route_that_cannot_fit_step_key() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
            plan=_plan(next_on_pass="x" * 65),
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="route-agent",
            lease_seconds=30,
        )
        output = await _output_artifact(
            session,
            run=run,
            step=step,
        )
        completed = await complete_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="route-agent",
            output_refs=[output.id],
        )
        review = await record_agent_review(
            session,
            review_request_id=completed.review_request_id,
            reviewer_key="customer-map-reviewer",
            decision="pass",
            checks=_passing_checks(),
        )
        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_next_route_invalid",
        ):
            await materialize_auto_next(
                session,
                review_result_id=review.review_result_id,
            )


@pytest.mark.asyncio
async def test_retryable_failure_creates_new_step_plan_and_bridge_job() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="retry-agent-a",
            lease_seconds=30,
        )
        failure = await fail_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="retry-agent-a",
            failure_class="tool_transient",
            message="Temporary tool outage.",
        )
        assert failure.retry_step_run_id is not None
        assert failure.retry_execution_plan_artifact_id is not None
        assert failure.retry_job_id is not None
        assert failure.retry_requires_approval is False

        retry_step = await session.get(
            StepRun,
            failure.retry_step_run_id,
        )
        retry_plan = await session.get(
            Artifact,
            failure.retry_execution_plan_artifact_id,
        )
        assert retry_step is not None
        assert retry_plan is not None
        assert retry_step.attempt == 2
        assert retry_plan.step_run_id == retry_step.id
        assert str(retry_plan.id) in retry_step.input_artifact_refs_json

        claimed = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="retry-agent-b",
            lease_seconds=30,
        )
        assert claimed is not None
        assert claimed.job_id == failure.retry_job_id
        assert claimed.step_attempt == 2

        replay = await fail_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="retry-agent-a",
            failure_class="tool_transient",
            message="Temporary tool outage.",
        )
        assert replay.failure_receipt_id == failure.failure_receipt_id
        assert replay.replayed is True


@pytest.mark.asyncio
async def test_sensitive_retry_requires_fresh_approval_for_retry_plan() -> None:
    async with isolated_session() as session:
        settings, plan = _sensitive_settings_and_plan()
        run, step = await _pending_fixture(
            session,
            settings=settings,
        )
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
            plan=plan,
        )
        await _approve_plan(
            session,
            run=run,
            step=step,
            plan_artifact=plan_artifact,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="sensitive-agent",
            lease_seconds=30,
        )
        failure = await fail_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="sensitive-agent",
            failure_class="tool_transient",
            message="Retry requires new approval.",
        )
        assert failure.retry_requires_approval is True
        assert failure.retry_job_id is None
        assert failure.retry_step_run_id is not None
        assert failure.retry_execution_plan_artifact_id is not None
        await session.refresh(run)
        assert run.status == "waiting_approval"

        retry_step = await session.get(
            StepRun,
            failure.retry_step_run_id,
        )
        assert retry_step is not None
        await resolve_approval(
            session,
            run_id=run.id,
            step_key=retry_step.step_key,
            artifact_id=failure.retry_execution_plan_artifact_id,
            decision="approved",
            actor_id="founder",
            comment="Fresh approval for retry attempt.",
        )
        retry_job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=failure.retry_execution_plan_artifact_id,
            worker_key="customer-map-worker",
        )
        assert retry_job.step_run_id == retry_step.id


@pytest.mark.asyncio
async def test_nonretryable_failure_terminates_run() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="terminal-agent",
            lease_seconds=30,
        )
        failure = await fail_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="terminal-agent",
            failure_class="schema_validation",
            message="Output cannot satisfy schema.",
        )
        assert failure.retry_step_run_id is None
        assert failure.retry_job_id is None
        await session.refresh(run)
        assert run.status == "failed"
        assert run.failure_code == "schema_validation"


@pytest.mark.asyncio
async def test_subagent_telemetry_reuses_existing_delegation_model() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="parent-agent",
            lease_seconds=30,
        )
        child = await start_subagent_telemetry(
            session,
            job_id=job.id,
            worker_instance_id="parent-agent",
            child_worker_key="research-subagent",
            child_task_key="bounded-research",
            dedupe_key="child-1",
        )
        child_replay = await start_subagent_telemetry(
            session,
            job_id=job.id,
            worker_instance_id="parent-agent",
            child_worker_key="research-subagent",
            child_task_key="bounded-research",
            dedupe_key="child-1",
        )
        assert child_replay.id == child.id
        completed_child = await complete_subagent_telemetry(
            session,
            job_id=job.id,
            worker_instance_id="parent-agent",
            execution_id=child.id,
        )
        assert completed_child.status == "completed"

        output = await _output_artifact(
            session,
            run=run,
            step=step,
        )
        completion = await complete_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="parent-agent",
            output_refs=[output.id],
        )
        receipt = await session.get(
            Artifact,
            completion.completion_receipt_id,
        )
        assert receipt is not None
        assert receipt.content_json is not None
        counts = receipt.content_json["runtime_counts"]
        assert isinstance(counts, dict)
        assert counts["subagent_count"] == 1


@pytest.mark.asyncio
async def test_safe_telemetry_rejects_prompt_or_raw_payload_fields() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="telemetry-agent",
            lease_seconds=30,
        )
        output = await _output_artifact(
            session,
            run=run,
            step=step,
        )

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_telemetry_field_forbidden",
        ):
            await complete_agent_task(
                session,
                job_id=job.id,
                worker_key="customer-map-worker",
                worker_instance_id="telemetry-agent",
                output_refs=[output.id],
                telemetry={"prompt": "must-not-cross-bridge"},
            )


@pytest.mark.asyncio
async def test_bridge_control_plane_does_not_create_model_or_tool_calls() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        before = (
            await session.scalar(select(func.count()).select_from(ModelCall)),
            await session.scalar(select(func.count()).select_from(ToolCall)),
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        lease = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="control-agent",
            lease_seconds=20,
        )
        assert lease is not None
        await heartbeat_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="control-agent",
            extend_seconds=20,
        )
        after = (
            await session.scalar(select(func.count()).select_from(ModelCall)),
            await session.scalar(select(func.count()).select_from(ToolCall)),
        )
        assert after == before


@pytest.mark.asyncio
async def test_malformed_capability_settings_provenance_fails_closed() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        current = await session.get(
            SettingsSnapshot,
            run.settings_snapshot_id,
        )
        assert current is not None
        replacement = await create_settings_snapshot(
            session,
            project_id=run.project_id,
            resolved_settings=current.resolved_settings_json,
            source_version_refs=[
                *current.source_version_refs_json,
                "settings_version:fake:v1",
            ],
        )
        run.settings_snapshot_id = replacement.id
        await session.flush()

        with pytest.raises(
            ExecutionPlanError,
            match="execution_plan_policy_source_ref_invalid",
        ):
            await persist_execution_plan_artifact(
                session,
                run_id=run.id,
                step_run_id=step.id,
                plan=_plan(),
            )

@pytest.mark.asyncio
async def test_nonrunning_run_cannot_queue_plan() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        run.status = "failed"
        run.completed_at = utc_now()
        await session.flush()

        with pytest.raises(
            AgentBridgeError,
            match="execution_plan_run_not_authorizable",
        ):
            await enqueue_execution_plan_job(
                session,
                execution_plan_artifact_id=plan_artifact.id,
                worker_key="customer-map-worker",
            )
        assert str(plan_artifact.id) not in step.input_artifact_refs_json


@pytest.mark.asyncio
async def test_bridge_fails_closed_on_nondurable_budget_counter() -> None:
    async with isolated_session() as session:
        settings = _policy()
        autopilot = settings["autopilot"]
        assert isinstance(autopilot, dict)
        capability_policy = autopilot["capability_policy"]
        assert isinstance(capability_policy, dict)
        workers = capability_policy["workers"]
        assert isinstance(workers, dict)
        worker = workers["customer-map-worker"]
        assert isinstance(worker, dict)
        ceiling = worker["budget_ceiling"]
        assert isinstance(ceiling, dict)
        ceiling["max_context_estimate"] = 100

        run, step = await _pending_fixture(
            session,
            settings=settings,
        )
        plan = _plan(
            budget={
                "max_tool_calls": 6,
                "max_model_calls": 1,
                "max_context_estimate": 50,
                "max_output_tokens": 4000,
                "max_estimated_cost": "0.50",
                "max_wall_clock_seconds": 120,
            }
        )
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
            plan=plan,
        )

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_budget_field_not_durable",
        ):
            await enqueue_execution_plan_job(
                session,
                execution_plan_artifact_id=plan_artifact.id,
                worker_key="customer-map-worker",
            )


@pytest.mark.asyncio
async def test_completion_rejects_stale_output_artifact_version() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        lease = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="stale-output-agent",
            lease_seconds=30,
        )
        assert lease is not None
        first = await _output_artifact(
            session,
            run=run,
            step=step,
        )
        newer_payload = {"schema_version": 1, "value": "newer"}
        newer = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="customer_map_snapshot",
            version=2,
            content_json=newer_payload,
            content_hash=_hash(newer_payload),
        )
        session.add(newer)
        await session.flush()

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_output_artifact_stale",
        ):
            await complete_agent_task(
                session,
                job_id=job.id,
                worker_key="customer-map-worker",
                worker_instance_id="stale-output-agent",
                output_refs=[first.id],
            )


@pytest.mark.asyncio
async def test_forged_review_request_fails_semantic_revalidation() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        lease = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="review-forge-agent",
            lease_seconds=30,
        )
        assert lease is not None
        output = await _output_artifact(
            session,
            run=run,
            step=step,
        )
        completed = await complete_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="review-forge-agent",
            output_refs=[output.id],
        )
        real = await session.get(Artifact, completed.review_request_id)
        assert real is not None
        assert real.content_json is not None
        forged_payload = dict(real.content_json)
        forged_payload["reviewer"] = "forged-reviewer"
        forged = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="agent_review_request_forged",
            version=1,
            content_json=forged_payload,
            content_hash=_hash(forged_payload),
        )
        session.add(forged)
        await session.flush()

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_review_request_semantic_mismatch",
        ):
            await record_agent_review(
                session,
                review_request_id=forged.id,
                reviewer_key="forged-reviewer",
                decision="pass",
                checks=_passing_checks(),
            )

@pytest.mark.asyncio
async def test_budget_exhaustion_blocks_execution_but_can_be_recorded_as_failure() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan = _plan(
            budget={
                "max_tool_calls": 6,
                "max_model_calls": 1,
                "max_output_tokens": 4000,
                "max_estimated_cost": "0.50",
                "max_wall_clock_seconds": 5,
            },
            timeout_seconds=5,
        )
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
            plan=plan,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        lease = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="budget-agent",
            lease_seconds=30,
        )
        assert lease is not None
        step.started_at = utc_now() - timedelta(seconds=6)
        await session.flush()

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_budget_exceeded",
        ):
            await heartbeat_agent_task(
                session,
                job_id=job.id,
                worker_key="customer-map-worker",
                worker_instance_id="budget-agent",
                extend_seconds=10,
            )

        failure = await fail_agent_task(
            session,
            job_id=job.id,
            worker_key="customer-map-worker",
            worker_instance_id="budget-agent",
            failure_class="budget_exceeded",
            message="ExecutionPlan wall-clock budget exhausted.",
        )
        assert failure.retry_step_run_id is None
        await session.refresh(run)
        assert run.status == "failed"
        assert run.failure_code == "budget_exceeded"

@pytest.mark.asyncio
async def test_completion_rejects_output_created_exactly_at_step_start() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        lease = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="timestamp-boundary-agent",
            lease_seconds=30,
        )
        assert lease is not None
        await session.refresh(step)
        assert step.started_at is not None

        payload = {"schema_version": 1, "value": "equal-start"}
        output = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="customer_map_snapshot",
            version=1,
            content_json=payload,
            external_ref=None,
            content_hash=_hash(payload),
            created_at=step.started_at,
        )
        session.add(output)
        await session.flush()

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_output_artifact_predates_execution",
        ):
            await complete_agent_task(
                session,
                job_id=job.id,
                worker_key="customer-map-worker",
                worker_instance_id="timestamp-boundary-agent",
                output_refs=[output.id],
            )


@pytest.mark.asyncio
async def test_completion_rejects_external_only_output_without_verifier() -> None:
    async with isolated_session() as session:
        run, step = await _pending_fixture(session)
        plan_artifact = await _persist_default_plan(
            session,
            run=run,
            step=step,
        )
        job = await enqueue_execution_plan_job(
            session,
            execution_plan_artifact_id=plan_artifact.id,
            worker_key="customer-map-worker",
        )
        lease = await claim_agent_task(
            session,
            worker_key="customer-map-worker",
            worker_instance_id="external-output-agent",
            lease_seconds=30,
        )
        assert lease is not None

        output = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="customer_map_snapshot",
            version=1,
            content_json=None,
            external_ref="external://unverified-object",
            content_hash="f" * 64,
        )
        session.add(output)
        await session.flush()

        with pytest.raises(
            AgentBridgeError,
            match="agent_bridge_external_output_hash_unverifiable",
        ):
            await complete_agent_task(
                session,
                job_id=job.id,
                worker_key="customer-map-worker",
                worker_instance_id="external-output-agent",
                output_refs=[output.id],
            )

