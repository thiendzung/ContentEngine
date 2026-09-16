from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from test_ce05_review_revise import isolated_session
from test_review_revise_orchestration import _request, _source_draft_with_settings

from app.modules.content_engine.journal import operator_runtime
from app.modules.content_engine.journal.models import AngleApproval, OutlineApproval
from app.modules.content_engine.journal.operator_runtime import (
    get_operator_state,
    resolve_next_operator_action,
    submit_operator_command,
)
from app.modules.content_engine.journal.review_revise_orchestration import (
    prepare_review_revise_en_orchestration,
)
from app.modules.harness.models import Job, StepRun


@pytest.mark.asyncio
async def test_operator_runtime_resolves_existing_executable_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
        )
        prepared = await prepare_review_revise_en_orchestration(
            session,
            request=_request(fixture, source),
        )

        action = await resolve_next_operator_action(
            session,
            content_case_id=prepared.run.content_case_id,
        )

        assert action.action_key == "review_revise_en"
        assert action.intent == "continue"
        assert action.executable is True
        assert action.current_run_id == prepared.run.id
        assert action.current_step_run_id == prepared.step.id


@pytest.mark.asyncio
async def test_operator_runtime_stops_at_undecided_human_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
        )
        prepared = await prepare_review_revise_en_orchestration(
            session,
            request=_request(fixture, source),
        )
        prepared.run.status = "waiting_approval"
        prepared.run.current_step = "angle"
        await session.flush()

        action = await resolve_next_operator_action(
            session,
            content_case_id=prepared.run.content_case_id,
        )

        assert action.action_key == "await_angle_approval"
        assert action.intent is None
        assert action.executable is False
        assert action.human_gate == "angle"


async def _approved_angle_stage(session, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    fixture, source = await _source_draft_with_settings(
        session,
        monkeypatch,
        locale="en",
        unresolved=True,
    )
    prepared = await prepare_review_revise_en_orchestration(
        session,
        request=_request(fixture, source),
    )
    # This fixture was originally built for review/revise. Close that synthetic step so
    # the operator focus represents only the human Angle gate used by this test.
    prepared.step.status = "completed"
    prepared.run.status = "waiting_approval"
    prepared.run.current_step = "angle"
    approval = AngleApproval(
        run_id=prepared.run.id,
        angle_artifact_id=source.artifact.id,
        angle_artifact_version=source.artifact.version,
        angle_artifact_hash=source.artifact.content_hash,
        selected_angle_id="angle-runtime-test",
        selected_candidate_hash="a" * 64,
        approved_by="founder",
        approval_reason="canonical runtime resolver test",
        approved_at=datetime.now(UTC),
    )
    session.add(approval)
    await session.flush()
    return prepared, source, approval


@pytest.mark.asyncio
async def test_operator_runtime_makes_only_angle_continuation_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        prepared, _source, _approval = await _approved_angle_stage(session, monkeypatch)

        action = await resolve_next_operator_action(
            session,
            content_case_id=prepared.run.content_case_id,
        )

        assert action.action_key == "angle_to_outline"
        assert action.intent == "continue"
        assert action.executable is True
        assert action.blocker_code == "operator_gate_already_decided"
        assert action.current_run_id == prepared.run.id


@pytest.mark.asyncio
async def test_angle_to_outline_command_is_idempotent_retryable_and_stops_at_outline_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def skip_runtime_validation(*args: object, **kwargs: object) -> None:
        del args, kwargs

    monkeypatch.setattr(
        operator_runtime,
        "_validate_outline_runtime",
        skip_runtime_validation,
    )

    async with isolated_session() as session:
        prepared, source, _approval = await _approved_angle_stage(session, monkeypatch)
        case_id = prepared.run.content_case_id
        initial = await resolve_next_operator_action(session, content_case_id=case_id)
        assert initial.action_key == "angle_to_outline"
        assert initial.executable is True

        first = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="continue",
            expected_state_version=initial.state_version,
            idempotency_key="f2-angle-outline-continue",
        )
        assert first.status == "queued"
        assert first.job_id is not None
        assert first.replayed is False

        replay = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="continue",
            expected_state_version=initial.state_version,
            idempotency_key="f2-angle-outline-continue",
        )
        assert replay.replayed is True
        assert replay.command_id == first.command_id
        assert replay.job_id == first.job_id

        outline_steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == prepared.run.id,
                        StepRun.step_key == "outline",
                    )
                )
            ).all()
        )
        jobs = list(
            (
                await session.scalars(
                    select(Job)
                    .where(Job.run_id == prepared.run.id)
                    .order_by(Job.created_at, Job.id)
                )
            ).all()
        )
        assert len(outline_steps) == 1
        assert len(jobs) == 1
        outline_step = outline_steps[0]
        first_job = jobs[0]
        assert first_job.id == first.job_id
        assert first_job.step_run_id == outline_step.id
        assert prepared.run.status == "running"
        assert prepared.run.current_step == "outline"

        queued_state = await get_operator_state(session, content_case_id=case_id)
        assert queued_state.status == "QUEUED"

        # Simulate one bounded worker failure. F2 retries the Job, not the Outline StepRun.
        first_job.status = "failed"
        first_job.lease_owner = None
        first_job.lease_expires_at = None
        outline_step.status = "running"
        await session.flush()

        retry_state = await get_operator_state(session, content_case_id=case_id)
        assert retry_state.status == "BLOCKED"
        assert retry_state.primary_intent == "retry"
        retry_action = await resolve_next_operator_action(session, content_case_id=case_id)
        assert retry_action.action_key == "angle_to_outline"
        assert retry_action.intent == "retry"
        assert retry_action.executable is True

        retried = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="retry",
            expected_state_version=retry_state.state_version,
            idempotency_key="f2-angle-outline-retry",
        )
        assert retried.status == "queued"
        assert retried.job_id is not None
        assert retried.job_id != first.job_id

        jobs = list(
            (
                await session.scalars(
                    select(Job)
                    .where(Job.run_id == prepared.run.id)
                    .order_by(Job.created_at, Job.id)
                )
            ).all()
        )
        outline_steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == prepared.run.id,
                        StepRun.step_key == "outline",
                    )
                )
            ).all()
        )
        assert len(jobs) == 2
        assert len(outline_steps) == 1
        retry_job = next(row for row in jobs if row.id == retried.job_id)
        assert retry_job.step_run_id == outline_step.id
        assert retry_job.attempt == first_job.attempt + 1

        # Simulate the successful worker boundary. Before approval, the resolver must stop.
        retry_job.status = "completed"
        outline_step.status = "completed"
        prepared.run.status = "waiting_approval"
        prepared.run.current_step = "outline"
        await session.flush()

        outline_gate = await resolve_next_operator_action(session, content_case_id=case_id)
        assert outline_gate.action_key == "await_outline_approval"
        assert outline_gate.human_gate == "outline"
        assert outline_gate.executable is False

        session.add(
            OutlineApproval(
                run_id=prepared.run.id,
                outline_artifact_id=source.artifact.id,
                outline_artifact_version=source.artifact.version,
                outline_artifact_hash=source.artifact.content_hash,
                approved_by="founder",
                approval_reason="F2 stop-gate resolver proof",
                approved_at=datetime.now(UTC),
            )
        )
        await session.flush()

        after_approval = await resolve_next_operator_action(session, content_case_id=case_id)
        assert after_approval.action_key == "outline_to_writers"
        assert after_approval.intent == "continue"
        assert after_approval.executable is False
