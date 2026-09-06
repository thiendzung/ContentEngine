from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    LocaleVariant,
    NeedHypothesis,
    Project,
    SettingsSnapshot,
)
from app.modules.harness.models import Artifact, ContentRun, ModelCall, StepRun
from app.modules.harness.persistence import (
    claim_next_job,
    complete_job,
    create_checkpoint,
    enqueue_job,
    fail_job_and_maybe_retry,
    get_latest_checkpoint,
    load_budget_usage,
    pause_for_approval,
    resolve_approval,
    transition_run,
)
from app.modules.harness.policy import (
    BudgetExceededError,
    BudgetLimits,
    RetryPolicy,
    enforce_budget,
    is_retryable_failure,
)
from app.modules.knowledge.persistence import content_hash


async def _create_run(session: AsyncSession) -> ContentRun:
    project = (
        await session.execute(select(Project).where(Project.slug == "motgu"))
    ).scalar_one()
    suffix = uuid4().hex[:8]
    hypothesis = NeedHypothesis(
        project_id=project.id,
        type="problem",
        statement=f"CE03 PR-B gate {suffix}",
        audience_scope="synthetic reader",
        situation="synthetic gate",
        origin="FOUNDER",
    )
    session.add(hypothesis)
    await session.flush()
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale="en",
        reader="synthetic reader",
        situation="synthetic gate",
        need="Durable orchestration",
        question="Can the harness resume safely?",
        intent="learn",
        promise="Preserve durable state",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Synthetic harness gate",
        next_discovery_step="None",
        decision="CREATE",
        priority="NOW",
        reasons_json=["gate"],
        suggested_content_type="journal",
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=hypothesis.id,
        content_opportunity_id=opportunity.id,
        desired_action="Continue",
        content_hypothesis="Durable state preserves progress",
        originality_statement="Synthetic only",
        reader_before="Waiting",
        reader_after="Resumed",
    )
    session.add(content_case)
    await session.flush()
    locale_variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="primary",
        primary_question="Can the harness resume safely?",
        primary_intent="learn",
    )
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={"gate": True},
        source_version_refs_json=["gate"],
        content_hash=content_hash(f"ce03-pr-b-gate:{suffix}"),
    )
    session.add_all([locale_variant, snapshot])
    await session.flush()
    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=locale_variant.id,
        run_mode="create",
        status="pending",
        current_step="outline",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    return run


@pytest.mark.asyncio
async def test_ce03_pr_b_synthetic_gate() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run = await _create_run(session)
            await transition_run(session, run_id=run.id, status="running")

            outline_step = StepRun(
                run_id=run.id,
                step_key="outline",
                attempt=1,
                status="completed",
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            session.add(outline_step)
            await session.flush()
            outline = Artifact(
                run_id=run.id,
                step_run_id=outline_step.id,
                artifact_type="outline",
                locale="en",
                version=1,
                content_json={"title": "Synthetic outline"},
                content_hash=content_hash(f"outline:{run.id}:1"),
            )
            session.add(outline)
            await session.flush()

            approval_checkpoint = await pause_for_approval(
                session,
                run_id=run.id,
                step_key="outline",
                artifact_id=outline.id,
            )
            await session.refresh(run)
            assert run.status == "waiting_approval"
            assert approval_checkpoint.content_json is not None
            assert approval_checkpoint.content_json["pending_approval"] is not None

            await resolve_approval(
                session,
                run_id=run.id,
                step_key="outline",
                artifact_id=outline.id,
                decision="approved",
                actor_id="founder",
            )
            await session.refresh(run)
            assert run.status == "running"

            draft_attempt_1 = StepRun(
                run_id=run.id,
                step_key="draft",
                attempt=1,
                status="pending",
            )
            session.add(draft_attempt_1)
            await session.flush()
            first_job = await enqueue_job(
                session,
                run_id=run.id,
                step_run_id=draft_attempt_1.id,
                dedupe_key=f"gate:draft:{run.id}:1",
            )
            claimed = await claim_next_job(
                session,
                worker_id="worker-a",
                lease_duration=timedelta(minutes=5),
            )
            assert claimed is not None
            assert claimed.id == first_job.id

            retry_result = await fail_job_and_maybe_retry(
                session,
                job_id=first_job.id,
                worker_id="worker-a",
                failure_class="provider_transient",
                message="temporary outage",
                retry_policy=RetryPolicy(max_step_attempts=2),
            )
            assert retry_result.retried is True
            assert retry_result.retry_step_run_id is not None
            assert retry_result.retry_job_id is not None

            retry_job = await claim_next_job(
                session,
                worker_id="worker-b",
                lease_duration=timedelta(minutes=5),
            )
            assert retry_job is not None
            assert retry_job.id == retry_result.retry_job_id
            await complete_job(session, job_id=retry_job.id, worker_id="worker-b")

            final_checkpoint = await create_checkpoint(session, run_id=run.id)
            latest = await get_latest_checkpoint(session, run_id=run.id)
            assert latest is not None
            assert latest.id == final_checkpoint.id
            assert final_checkpoint.content_json is not None
            retry_counters = final_checkpoint.content_json["retry_counters"]
            assert retry_counters["draft"] == 2

            session.add(
                ModelCall(
                    run_id=run.id,
                    task_key="draft",
                    provider="test",
                    model="test",
                    purpose="synthetic gate",
                    prompt_version="v1",
                    output_tokens=150,
                    cost=Decimal("0.10"),
                    status="completed",
                )
            )
            await session.flush()
            usage = await load_budget_usage(session, run_id=run.id)
            with pytest.raises(BudgetExceededError, match="max_output_tokens exceeded"):
                enforce_budget(BudgetLimits(max_output_tokens=100), usage)
            assert is_retryable_failure("budget_exceeded") is False
        finally:
            await session.close()
            await transaction.rollback()
