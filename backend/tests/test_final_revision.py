from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_outline import isolated_session
from test_operator_quality import (
    _CapturePort,
    _complete_f3_writers,
    _complete_healthy_lane_from_audit,
)

from app.modules.content_engine.journal import operator_quality_worker
from app.modules.content_engine.journal.final_revision import (
    load_final_revision_requests,
)
from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.journal.operator_control import OperatorControlError
from app.modules.content_engine.journal.operator_decisions import submit_operator_decision
from app.modules.content_engine.journal.operator_quality import (
    get_quality_progress,
    settle_quality_command,
)
from app.modules.content_engine.journal.operator_runtime import (
    get_operator_state,
    resolve_next_operator_action,
    submit_operator_command,
)
from app.modules.content_engine.journal.operator_writers import get_writer_lane_progress
from app.modules.content_engine.models import ContentVersion
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import Approval, Artifact, Job, StepRun, ToolCall, utc_now


async def _revision_fixture(
    session: AsyncSession,
    *,
    locales: tuple[str, ...],
    comment: str = "Apply the exact bounded Founder feedback.",
) -> tuple[object, dict[str, object], object, dict[str, object]]:
    fixture, outputs, outline = await _complete_f3_writers(session)
    progress = await get_writer_lane_progress(
        session,
        content_case_id=fixture.run.content_case_id,
        source_run_id=fixture.run.id,
    )
    assert progress is not None
    selected: dict[str, object] = {}
    for lane in progress.lanes:
        if lane.required_locale not in locales:
            continue
        assert lane.run is not None and lane.draft is not None
        final = Artifact(
            run_id=lane.run.id,
            artifact_type="final_content",
            locale=lane.required_locale,
            version=1,
            content_json=lane.draft.content_json,
            content_hash=lane.draft.content_hash,
        )
        session.add(final)
        lane.run.current_step = "final_review"
        lane.run.status = "running"
        await session.flush()
        approval = Approval(
            run_id=lane.run.id,
            step_key="final_review",
            artifact_id=final.id,
            decision="changes_requested",
            actor_id="founder",
            comment=comment,
        )
        session.add(approval)
        selected[lane.required_locale] = {
            "lane": lane,
            "final": final,
            "approval": approval,
        }
    await session.flush()
    return fixture, outputs, outline, selected


@pytest.mark.asyncio
async def test_changes_requested_exposes_bounded_final_revision_and_dispatches_only_requested_lane(
) -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline = await _complete_f3_writers(session)
        # _complete_f3_writers returns the F3 fixture; select one completed lane.
        from app.modules.content_engine.journal.operator_writers import get_writer_lane_progress

        progress = await get_writer_lane_progress(
            session,
            content_case_id=fixture.run.content_case_id,
            source_run_id=fixture.run.id,
        )
        assert progress is not None
        requested = next(
            candidate
            for candidate in progress.lanes
            if candidate.required_locale == "en"
        )
        assert requested.run is not None and requested.draft is not None

        final = Artifact(
            run_id=requested.run.id,
            artifact_type="final_content",
            locale="en",
            version=1,
            content_json=requested.draft.content_json,
            content_hash=requested.draft.content_hash,
        )
        session.add(final)
        requested.run.current_step = "final_review"
        requested.run.status = "running"
        await session.flush()
        session.add(
            Approval(
                run_id=requested.run.id,
                step_key="final_review",
                artifact_id=final.id,
                decision="changes_requested",
                actor_id="founder",
                comment="Paraphrase the repeated caveat and keep the same factual scope.",
            )
        )
        await session.flush()

        requests = await load_final_revision_requests(
            session, content_case_id=fixture.run.content_case_id
        )
        assert len(requests) == 1
        assert requests[0].locale == "en"
        assert requests[0].source_draft.id == requested.draft.id

        state = await get_operator_state(session, content_case_id=fixture.run.content_case_id)
        assert state.status == "READY"
        assert state.primary_intent == "continue"
        assert state.allowed_intents == ["continue"]

        action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        assert action.action_key == "final_revision"
        assert action.intent == "continue"
        assert action.executable is True

        command = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="continue",
            expected_state_version=action.state_version,
            idempotency_key="final-revision-fixture-1",
        )
        assert command.status == "queued"
        assert command.job_id is not None
        jobs = list((await session.scalars(select(Job))).all())
        final_steps = list(
            (
                await session.scalars(
                    select(StepRun).where(StepRun.step_key == "final_revision_en")
                )
            ).all()
        )
        assert len(final_steps) == 1
        assert len([job for job in jobs if job.step_run_id == final_steps[0].id]) == 1
        replay = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="continue",
            expected_state_version=action.state_version,
            idempotency_key="final-revision-fixture-1",
        )
        assert replay.replayed is True
        assert await session.scalar(
            select(func.count(OperatorCommand.id)).where(
                OperatorCommand.resolved_action_key == "final_revision"
            )
        ) == 1


@pytest.mark.asyncio
async def test_final_revision_approval_requires_comment_and_active_version_blocks() -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline = await _complete_f3_writers(session)
        from app.modules.content_engine.journal.operator_writers import get_writer_lane_progress

        progress = await get_writer_lane_progress(
            session,
            content_case_id=fixture.run.content_case_id,
            source_run_id=fixture.run.id,
        )
        assert progress is not None
        requested = next(
            candidate
            for candidate in progress.lanes
            if candidate.required_locale == "en"
        )
        assert requested.run is not None and requested.draft is not None
        final = Artifact(
            run_id=requested.run.id,
            artifact_type="final_content",
            locale="en",
            version=1,
            content_json=requested.draft.content_json,
            content_hash=requested.draft.content_hash,
        )
        session.add(final)
        requested.run.status = "running"
        requested.run.current_step = "final_review"
        await session.flush()
        session.add(
            Approval(
                run_id=requested.run.id,
                step_key="final_review",
                artifact_id=final.id,
                decision="changes_requested",
                actor_id="founder",
                comment=None,
            )
        )
        await session.flush()
        with pytest.raises(ValueError, match="final_revision_comment_required"):
            await load_final_revision_requests(
                session, content_case_id=fixture.run.content_case_id
            )


@pytest.mark.asyncio
async def test_final_revision_worker_binds_feedback_and_queues_fresh_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, outputs, _outline = await _complete_f3_writers(session)
        from app.modules.content_engine.journal.operator_writers import get_writer_lane_progress

        progress = await get_writer_lane_progress(
            session,
            content_case_id=fixture.run.content_case_id,
            source_run_id=fixture.run.id,
        )
        assert progress is not None
        requested = next(
            candidate
            for candidate in progress.lanes
            if candidate.required_locale == "en"
        )
        assert requested.run is not None and requested.draft is not None
        final = Artifact(
            run_id=requested.run.id,
            artifact_type="final_content",
            locale="en",
            version=1,
            content_json=requested.draft.content_json,
            content_hash=requested.draft.content_hash,
        )
        session.add(final)
        requested.run.current_step = "final_review"
        requested.run.status = "running"
        await session.flush()
        session.add(
            Approval(
                run_id=requested.run.id,
                step_key="final_review",
                artifact_id=final.id,
                decision="changes_requested",
                actor_id="founder",
                comment="Rewrite the caveat naturally without changing factual scope.",
            )
        )
        await session.flush()
        action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        command = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="continue",
            expected_state_version=action.state_version,
            idempotency_key="final-revision-worker-fixture",
        )
        assert command.job_id is not None

        output = outputs["en"]
        assert isinstance(output, dict)
        output["closing_markdown"] = "Choose the next question you can verify."
        port = _CapturePort(output)

        async def fake_port(*_args: object, **_kwargs: object) -> _CapturePort:
            return port

        monkeypatch.setattr(
            operator_quality_worker,
            "create_cli_review_revise_model_port",
            fake_port,
        )
        job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="final-revision-test"
        )
        assert job is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=job.id,
            worker_id="final-revision-test",
            runner_registry=AgentRunnerRegistry(),
        )
        assert port.inputs
        request = port.inputs[0].get("final_revision_request")
        assert isinstance(request, dict)
        assert request["approval_id"]
        assert request["comment"] == "Rewrite the caveat naturally without changing factual scope."
        assert "other_locale_draft" not in port.inputs[0]
        audit_jobs = list(
            (
                await session.scalars(
                    select(Job).where(Job.status == "queued")
                )
            ).all()
        )
        assert audit_jobs
        revision_step = await session.scalar(
            select(StepRun).where(StepRun.step_key == "final_revision_en")
        )
        assert revision_step is not None
        assert revision_step.output_artifact_refs_json
        audit_step = await session.get(StepRun, audit_jobs[0].step_run_id)
        assert audit_step is not None
        assert revision_step.output_artifact_refs_json[-1] in audit_step.input_artifact_refs_json


@pytest.mark.asyncio
async def test_final_revision_dispatches_both_requested_locales_with_exact_inputs() -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline, selected = await _revision_fixture(
            session, locales=("vi-VN", "en")
        )
        action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        assert action.action_key == "final_revision"
        assert action.intent == "continue"
        command = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="continue",
            expected_state_version=action.state_version,
            idempotency_key="final-revision-both-locales",
        )
        assert command.status == "queued"
        steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.step_key.in_({"final_revision_vi", "final_revision_en"})
                    )
                )
            ).all()
        )
        jobs = list((await session.scalars(select(Job))).all())
        assert {step.step_key for step in steps} == {
            "final_revision_vi",
            "final_revision_en",
        }
        assert len(steps) == 2
        assert len([job for job in jobs if job.step_run_id in {step.id for step in steps}]) == 2
        for locale, values in selected.items():
            final = values["final"]
            approval = values["approval"]
            matching = next(
                step
                for step in steps
                if step.step_key.endswith("vi" if locale == "vi-VN" else "en")
            )
            assert matching.input_artifact_refs_json[0] == str(approval.id)
            assert matching.input_artifact_refs_json[1] == str(final.id)


@pytest.mark.asyncio
async def test_approved_sibling_locale_is_not_revised() -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline, selected = await _revision_fixture(
            session, locales=("en",)
        )
        progress = await get_writer_lane_progress(
            session,
            content_case_id=fixture.run.content_case_id,
            source_run_id=fixture.run.id,
        )
        assert progress is not None
        vi_lane = next(lane for lane in progress.lanes if lane.required_locale == "vi-VN")
        assert vi_lane.run is not None and vi_lane.draft is not None
        vi_final = Artifact(
            run_id=vi_lane.run.id,
            artifact_type="final_content",
            locale="vi-VN",
            version=1,
            content_json=vi_lane.draft.content_json,
            content_hash=vi_lane.draft.content_hash,
        )
        session.add(vi_final)
        await session.flush()
        session.add(
            Approval(
                run_id=vi_lane.run.id,
                step_key="final_review",
                artifact_id=vi_final.id,
                decision="approved",
                actor_id="founder",
                comment="Approved sibling remains untouched.",
            )
        )
        await session.flush()
        action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        assert action.action_key == "final_revision"
        await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="continue",
            expected_state_version=action.state_version,
            idempotency_key="final-revision-one-locale-only",
        )
        assert selected["en"]["approval"].decision == "changes_requested"
        assert not (
            await session.scalars(
                select(StepRun).where(StepRun.step_key == "final_revision_vi")
            )
        ).all()


@pytest.mark.asyncio
async def test_no_final_revision_request_does_not_dispatch() -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline = await _complete_f3_writers(session)
        no_request_action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        assert no_request_action.action_key != "final_revision"


@pytest.mark.asyncio
async def test_final_revision_stale_state_fails_before_dispatch() -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline, _selected = await _revision_fixture(
            session, locales=("en",)
        )
        action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        assert action.action_key == "final_revision"
        before = await session.scalar(
            select(func.count(OperatorCommand.id)).where(
                OperatorCommand.resolved_action_key == "final_revision"
            )
        )
        with pytest.raises(OperatorControlError, match="operator_state_stale"):
            await submit_operator_command(
                session,
                content_case_id=fixture.run.content_case_id,
                intent="continue",
                expected_state_version="0" * 64,
                idempotency_key="final-revision-stale-state",
            )
        after = await session.scalar(
            select(func.count(OperatorCommand.id)).where(
                OperatorCommand.resolved_action_key == "final_revision"
            )
        )
        assert after == before == 0


@pytest.mark.asyncio
async def test_final_revision_superseded_request_is_not_rebound_to_new_candidate() -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline, selected = await _revision_fixture(
            session, locales=("en",)
        )
        values = selected["en"]
        final_v1 = values["final"]
        run = values["lane"].run
        assert run is not None
        current_step = StepRun(
            run_id=run.id,
            step_key="final_review",
            attempt=2,
            status="completed",
            input_artifact_refs_json=[],
            output_artifact_refs_json=[],
        )
        session.add(current_step)
        await session.flush()
        final_v2 = Artifact(
            run_id=run.id,
            step_run_id=current_step.id,
            artifact_type="final_content",
            locale="en",
            version=2,
            content_json={"artifact_type": "final_content", "version": 2},
            content_hash="2" * 64,
        )
        session.add(final_v2)
        await session.flush()
        assert final_v1.version == 1
        assert final_v2.version == final_v1.version + 1
        assert final_v2.step_run_id == current_step.id
        assert final_v1.content_hash != final_v2.content_hash
        assert values["approval"].artifact_id == final_v1.id
        assert values["approval"].artifact_id != final_v2.id
        assert await load_final_revision_requests(
            session, content_case_id=fixture.run.content_case_id
        ) == ()


@pytest.mark.asyncio
async def test_final_revision_model_input_contains_exact_binding_and_no_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, outputs, _outline, selected = await _revision_fixture(
            session, locales=("en",), comment="Keep evidence and rewrite only the caveat."
        )
        action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="continue",
            expected_state_version=action.state_version,
            idempotency_key="final-revision-binding-proof",
        )
        port = _CapturePort(outputs["en"])

        async def fake_port(*_args: object, **_kwargs: object) -> _CapturePort:
            return port

        monkeypatch.setattr(
            operator_quality_worker,
            "create_cli_review_revise_model_port",
            fake_port,
        )
        job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="final-revision-binding-proof"
        )
        assert job is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=job.id,
            worker_id="final-revision-binding-proof",
            runner_registry=AgentRunnerRegistry(),
        )
        model_input = port.inputs[0]
        request = model_input["final_revision_request"]
        assert isinstance(request, dict)
        assert request["approval_id"] == str(selected["en"]["approval"].id)
        assert request["final_artifact"]["version"] == 1
        assert request["final_artifact"]["content_hash"] == selected["en"]["final"].content_hash
        assert request["comment"] == "Keep evidence and rewrite only the caveat."
        evidence_set = model_input["evidence_set"]
        originality_pack = model_input["originality_pack"]
        assert isinstance(evidence_set, dict)
        assert evidence_set["id"] and evidence_set["version"] and evidence_set["content_hash"]
        assert isinstance(originality_pack, dict)
        assert originality_pack["id"] and originality_pack["snapshot_hash"]
        serialized = str(model_input)
        assert "other_locale_draft" not in serialized
        assert await session.scalar(select(func.count(ToolCall.id))) == 0


@pytest.mark.asyncio
async def test_final_revision_retry_reopens_only_failed_locale_and_separates_attempt_budget(
) -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline, _selected = await _revision_fixture(
            session, locales=("vi-VN", "en")
        )
        action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        first = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="continue",
            expected_state_version=action.state_version,
            idempotency_key="final-revision-retry-initial",
        )
        assert first.status == "queued"
        en_step = await session.scalar(
            select(StepRun).where(StepRun.step_key == "final_revision_en")
        )
        vi_step = await session.scalar(
            select(StepRun).where(StepRun.step_key == "final_revision_vi")
        )
        assert en_step is not None and vi_step is not None
        en_job = await session.scalar(select(Job).where(Job.step_run_id == en_step.id))
        vi_job = await session.scalar(select(Job).where(Job.step_run_id == vi_step.id))
        assert en_job is not None and vi_job is not None
        now = utc_now()
        requests = await load_final_revision_requests(
            session, content_case_id=fixture.run.content_case_id
        )
        en_request = next(request for request in requests if request.locale == "en")
        en_request.writer_run.status = "waiting_approval"
        en_request.writer_run.completed_at = None
        en_step.status = "running"
        vi_step.status = "running"
        await session.flush()
        en_step.status = "failed"
        en_step.completed_at = now
        en_job.status = "failed"
        vi_step.status = "completed"
        vi_step.completed_at = now
        vi_job.status = "completed"
        await session.flush()
        failed_state = await get_operator_state(
            session, content_case_id=fixture.run.content_case_id
        )
        assert failed_state.blocker_code == "operator_final_revision_job_failed"
        retry = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="retry",
            expected_state_version=failed_state.state_version,
            idempotency_key="final-revision-retry-only-failed",
        )
        assert retry.status == "queued"
        retry_steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.step_key.in_(
                            {"final_revision_vi", "final_revision_en"}
                        )
                    )
                )
            ).all()
        )
        assert sorted((step.step_key, step.attempt) for step in retry_steps) == [
            ("final_revision_en", 1),
            ("final_revision_en", 2),
            ("final_revision_vi", 1),
        ]
        requests = await load_final_revision_requests(
            session, content_case_id=fixture.run.content_case_id
        )
        assert any(request.writer_run.status == "running" for request in requests)


@pytest.mark.asyncio
async def test_final_revision_cancel_marks_step_and_run_coherent_for_retry() -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline, _selected = await _revision_fixture(
            session, locales=("en",)
        )
        action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        queued = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="continue",
            expected_state_version=action.state_version,
            idempotency_key="final-revision-cancel-initial",
        )
        assert queued.status == "queued"
        running = await get_operator_state(session, content_case_id=fixture.run.content_case_id)
        cancelled = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="cancel",
            expected_state_version=running.state_version,
            idempotency_key="final-revision-cancel-coherent",
        )
        assert cancelled.status == "cancelled"
        initial_row = await session.get(OperatorCommand, queued.command_id)
        assert initial_row is not None and initial_row.status == "cancelled"
        step = await session.scalar(select(StepRun).where(StepRun.step_key == "final_revision_en"))
        job = await session.scalar(select(Job).where(Job.step_run_id == step.id)) if step else None
        assert step is not None and step.status == "failed"
        assert job is not None and job.status == "cancelled"
        requests = await load_final_revision_requests(
            session, content_case_id=fixture.run.content_case_id
        )
        assert requests[0].writer_run.status == "waiting_approval"
        retry_state = await get_operator_state(
            session, content_case_id=fixture.run.content_case_id
        )
        assert retry_state.blocker_code == "operator_final_revision_job_failed"


@pytest.mark.asyncio
async def test_final_revision_worker_failure_returns_run_to_waiting_approval_before_retry() -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline, _selected = await _revision_fixture(
            session, locales=("en",)
        )
        action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        queued = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="continue",
            expected_state_version=action.state_version,
            idempotency_key="final-revision-production-failure",
        )
        job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="final-revision-production-failure-worker"
        )
        assert job is not None and job.id == queued.job_id
        await operator_quality_worker.fail_quality_job(
            session,
            job_id=job.id,
            worker_id="final-revision-production-failure-worker",
            failure_class="fixture_failure",
            message="bounded fixture failure",
        )
        requests = await load_final_revision_requests(
            session, content_case_id=fixture.run.content_case_id
        )
        assert requests[0].writer_run.status == "waiting_approval"
        failed_state = await get_operator_state(
            session, content_case_id=fixture.run.content_case_id
        )
        retry = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="retry",
            expected_state_version=failed_state.state_version,
            idempotency_key="final-revision-production-failure-retry",
        )
        assert retry.status == "queued"
        requests = await load_final_revision_requests(
            session, content_case_id=fixture.run.content_case_id
        )
        assert requests[0].writer_run.status == "running"


@pytest.mark.asyncio
async def test_final_revision_real_worker_quality_chain_approves_v2_to_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, outputs, outline, selected = await _revision_fixture(
            session, locales=("vi-VN", "en")
        )
        action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        command = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="continue",
            expected_state_version=action.state_version,
            idempotency_key="final-revision-real-chain",
        )
        ports = {}
        for locale, original in outputs.items():
            revised_output = copy.deepcopy(original)
            assert isinstance(revised_output, dict)
            revised_output["closing_markdown"] = (
                "Verify the next question you can answer."
                if locale == "en"
                else "Hãy kiểm tra câu hỏi tiếp theo bạn có thể trả lời."
            )
            ports[locale] = _CapturePort(revised_output)

        async def fake_review_port(
            *_args: object, locale: str, **_kwargs: object
        ) -> _CapturePort:
            return ports[locale]

        monkeypatch.setattr(
            operator_quality_worker,
            "create_cli_review_revise_model_port",
            fake_review_port,
        )
        registry = AgentRunnerRegistry()
        revision_jobs = []
        for index in range(2):
            revision_job = await operator_quality_worker.claim_or_reclaim_quality_job(
                session, worker_id=f"final-revision-real-chain-worker-{index}"
            )
            assert revision_job is not None
            revision_jobs.append(revision_job)
            await operator_quality_worker.execute_quality_job(
                session,
                job_id=revision_job.id,
                worker_id=f"final-revision-real-chain-worker-{index}",
                runner_registry=registry,
            )
        assert len(revision_jobs) == 2
        assert command.job_id in {job.id for job in revision_jobs}
        progress = await get_quality_progress(
            session, content_case_id=fixture.run.content_case_id, source_run_id=None
        )
        assert progress is not None
        for lane in progress.lanes:
            assert lane.audit.step is not None and lane.audit.job is not None
            await _complete_healthy_lane_from_audit(
                session,
                case_id=fixture.run.content_case_id,
                outline_result=outline,
                step_run_id=lane.audit.step.id,
                monkeypatch=monkeypatch,
                worker_prefix=f"final-revision-real-chain-quality-{lane.locale}",
                runner_registry=registry,
            )
        progress = await get_quality_progress(
            session, content_case_id=fixture.run.content_case_id, source_run_id=None
        )
        assert progress is not None and progress.final_gate_ready is True
        assert all(lane.final_content is not None for lane in progress.lanes)
        assert all(lane.final_content.version == 2 for lane in progress.lanes)  # type: ignore[union-attr]
        state = await get_operator_state(
            session, content_case_id=fixture.run.content_case_id
        )
        assert state.status == "AWAITING_APPROVAL"
        assert state.human_gate == "final_review"
        for lane in progress.lanes:
            old_final = selected[lane.locale]["final"]
            session.add(
                ContentVersion(
                    content_item_id=lane.final_item.id,  # type: ignore[union-attr]
                    version_no=1,
                    change_reason="Prior revised draft snapshot",
                    status="draft",
                    content_json=old_final.content_json,
                    created_by_run_id=lane.writer.run.id,  # type: ignore[union-attr]
                    final_artifact_id=old_final.id,
                )
            )
        await session.flush()
        for lane in progress.lanes:
            state = await get_operator_state(
                session, content_case_id=fixture.run.content_case_id
            )
            approval = await submit_operator_decision(
                session,
                content_case_id=fixture.run.content_case_id,
                scope="final",
                decision="approved",
                expected_state_version=state.state_version,
                idempotency_key=f"final-revision-real-chain-approve-v2-{lane.locale}",
                locale_variant_id=lane.variant.id,
                comment="Approve the exact revised v2.",
            )
            assert approval.approval_id is not None
        versions = list((await session.scalars(select(ContentVersion))).all())
        assert {version.version_no for version in versions if version.status == "approved"} == {2}
        complete = await get_operator_state(
            session, content_case_id=fixture.run.content_case_id
        )
        assert complete.status == "COMPLETE"
        parent = await session.get(OperatorCommand, command.command_id)
        assert parent is not None and parent.status == "completed"


@pytest.mark.asyncio
async def test_final_revision_parent_command_settles_at_final_gate() -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline, _selected = await _revision_fixture(
            session, locales=("en",)
        )
        action = await resolve_next_operator_action(
            session, content_case_id=fixture.run.content_case_id
        )
        command = await submit_operator_command(
            session,
            content_case_id=fixture.run.content_case_id,
            intent="continue",
            expected_state_version=action.state_version,
            idempotency_key="final-revision-settlement",
        )
        step = await session.scalar(select(StepRun).where(StepRun.step_key == "final_revision_en"))
        assert step is not None
        job = await session.scalar(select(Job).where(Job.step_run_id == step.id))
        assert job is not None
        step.status = "running"
        await session.flush()
        step.status = "completed"
        step.completed_at = utc_now()
        job.status = "completed"
        await session.flush()
        await settle_quality_command(
            session,
            progress=SimpleNamespace(
                content_case_id=fixture.run.content_case_id,
                has_active_job=False,
                final_gate_ready=True,
                has_content_block=False,
                has_exhausted_failure=False,
                has_retryable_failure=False,
            ),
            state_version="a" * 64,
        )
        row = await session.get(OperatorCommand, command.command_id)
        assert row is not None and row.status == "completed"
