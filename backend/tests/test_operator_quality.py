from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_assertion_audit import _passing_output
from test_ce05_outline import isolated_session
from test_ce05_writer import _draft_payload
from test_operator_writers import (
    _f3_case,
)

from app.modules.content_engine.journal import operator_quality_worker
from app.modules.content_engine.journal.assertion_audit import load_assertion_audit_input
from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.journal.operator_quality import (
    QUALITY_REVIEW_TASK_KEYS,
    get_quality_progress,
)
from app.modules.content_engine.journal.operator_runtime import (
    get_operator_state,
    resolve_next_operator_action,
    submit_operator_command,
)
from app.modules.content_engine.journal.operator_view import get_operator_case_view
from app.modules.content_engine.models import ContentItem, ContentVersion
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import Approval, Artifact, ContentRun, Job, StepRun


class _CapturePort:
    def __init__(self, output: object) -> None:
        self.output = output
        self.inputs: list[dict[str, object]] = []

    def resolved_model_identity(self) -> tuple[str, str]:
        return "codex_cli", "test-model"

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        del attempt
        self.inputs.append(copy.deepcopy(input_bundle))
        return copy.deepcopy(self.output)


async def _complete_f3_writers(
    session: AsyncSession,
) -> tuple[object, dict[str, dict[str, object]], object]:
    fixture, outline_result = await _f3_case(session)
    case_id = fixture.run.content_case_id
    from app.modules.content_engine.journal.models import JournalIntakeSpec

    existing_spec = await session.scalar(
        select(JournalIntakeSpec).where(JournalIntakeSpec.content_case_id == case_id)
    )
    if existing_spec is None:
        session.add(
            JournalIntakeSpec(
                content_case_id=case_id,
                source_locale="en",
                research_country="US",
                intake_hash="a" * 64,
                submitted_by="founder",
            )
        )
        await session.flush()
    f3_action = await resolve_next_operator_action(session, content_case_id=case_id)
    assert f3_action.action_key == "outline_to_writers"
    await submit_operator_command(
        session,
        content_case_id=case_id,
        intent="continue",
        expected_state_version=f3_action.state_version,
        idempotency_key="f3-quality-fixture-writers",
    )
    from test_operator_writers import _FakeWriterPort

    from app.modules.content_engine.journal.operator_writers import get_writer_lane_progress
    from app.modules.content_engine.journal.writer import WriterGenerator, load_writer_input
    from app.modules.harness.runtime import ContextInputs, build_context_manifest

    progress = await get_writer_lane_progress(
        session,
        content_case_id=case_id,
        source_run_id=fixture.run.id,
    )
    assert progress is not None
    inputs = {}
    for lane in progress.lanes:
        assert lane.run is not None
        inputs[lane.required_locale] = await load_writer_input(
            session,
            writer_run_id=lane.run.id,
            outline_artifact_id=progress.outline_artifact.id,
            expected_outline_version=progress.outline_artifact.version,
            expected_outline_hash=progress.outline_artifact.content_hash,
            outline_approval_id=progress.outline_approval.id,
            locale=lane.required_locale,
        )
    outputs: dict[str, dict[str, object]] = {
        locale: _draft_payload(writer_input, locale)
        for locale, writer_input in inputs.items()
    }
    for lane in progress.lanes:
        assert lane.run is not None
        assert lane.step is not None
        assert lane.latest_job is not None
        lane_input = inputs[lane.required_locale]
        manifest = await build_context_manifest(
            session,
            run_id=lane.run.id,
            step_run_id=lane.step.id,
            inputs=ContextInputs(
                prompt_version="p:v1",
                recipe_version="r:v1",
                evidence_set_id=lane_input.outline_input.bundle.evidence_set_id,
                originality_pack_id=lane_input.outline_input.bundle.originality_pack_id,
            ),
        )
        lane.latest_job.status = "leased"
        lane.step.status = "running"
        lane.run.status = "running"
        await session.flush()
        await WriterGenerator(max_attempts=1).generate_draft(
            session,
            writer_run_id=lane.run.id,
            outline_artifact_id=progress.outline_artifact.id,
            expected_outline_version=progress.outline_artifact.version,
            expected_outline_hash=progress.outline_artifact.content_hash,
            outline_approval_id=progress.outline_approval.id,
            locale=lane.required_locale,
            model=_FakeWriterPort(outputs[lane.required_locale]),
            provider="codex_cli",
            model_name="test-model",
            context_manifest_id=manifest.id,
            prompt_version="p:v1",
            recipe_version="r:v1",
        )
        lane.latest_job.status = "completed"
        lane.latest_job.lease_owner = None
        lane.latest_job.lease_expires_at = None
        lane.step.status = "completed"
        lane.step.completed_at = datetime.now(UTC)
        lane.run.status = "waiting_approval"
    await session.flush()
    return fixture, outputs, outline_result


async def _dispatch_quality(
    session: AsyncSession,
    *,
    fixture: object,
) -> tuple[object, object]:
    case_id = fixture.run.content_case_id
    action = await resolve_next_operator_action(session, content_case_id=case_id)
    assert action.action_key == "writers_to_quality"
    assert action.intent == "continue"
    assert action.executable is True
    command = await submit_operator_command(
        session,
        content_case_id=case_id,
        intent="continue",
        expected_state_version=action.state_version,
        idempotency_key="f4-quality-dispatch",
    )
    replay = await submit_operator_command(
        session,
        content_case_id=case_id,
        intent="continue",
        expected_state_version=action.state_version,
        idempotency_key="f4-quality-dispatch",
    )
    assert replay.replayed is True
    assert replay.command_id == command.command_id
    runs = list(
        (
            await session.scalars(
                select(ContentRun).where(
                    ContentRun.content_case_id == case_id,
                    ContentRun.run_mode == "localize",
                )
            )
        ).all()
    )
    review_steps = list(
        (
            await session.scalars(
                select(StepRun).where(
                    StepRun.run_id.in_([run.id for run in runs]),
                    StepRun.step_key.in_(QUALITY_REVIEW_TASK_KEYS.values()),
                )
            )
        ).all()
    )
    review_jobs = list(
        (
            await session.scalars(
                select(Job).where(Job.step_run_id.in_([step.id for step in review_steps]))
            )
        ).all()
    )
    assert {step.step_key for step in review_steps} == set(QUALITY_REVIEW_TASK_KEYS.values())
    assert len(review_steps) == len(review_jobs) == 2
    return command, action


@pytest.mark.asyncio
async def test_f4_quality_dispatch_is_bilingual_idempotent_and_final_gate_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, writer_outputs, outline_result = await _complete_f3_writers(session)
        case_id = fixture.run.content_case_id
        _command, before_quality = await _dispatch_quality(session, fixture=fixture)

        review_ports = {
            locale: _CapturePort(payload) for locale, payload in writer_outputs.items()
        }

        async def fake_review_port(
            _session: AsyncSession,
            *,
            locale: str,
            **kwargs: object,
        ) -> _CapturePort:
            del _session, kwargs
            return review_ports[locale]

        monkeypatch.setattr(
            operator_quality_worker,
            "create_cli_review_revise_model_port",
            fake_review_port,
        )
        registry = AgentRunnerRegistry()
        for _ in range(2):
            job = await operator_quality_worker.claim_or_reclaim_quality_job(
                session, worker_id=f"f4-review-{_}"
            )
            assert job is not None
            await operator_quality_worker.execute_quality_job(
                session,
                job_id=job.id,
                worker_id=f"f4-review-{_}",
                runner_registry=registry,
            )
        assert {locale for locale, port in review_ports.items() if port.inputs} == {
            "vi-VN",
            "en",
        }
        for locale, port in review_ports.items():
            assert port.inputs[0]["locale"] == locale
            assert "other_locale_draft" not in port.inputs[0]
            assert "translation_source" not in port.inputs[0]

        quality = await get_quality_progress(
            session, content_case_id=case_id, source_run_id=None
        )
        assert quality is not None
        assert all(lane.revised_draft is not None for lane in quality.lanes)
        audit_ports: dict[str, _CapturePort] = {}
        for lane in quality.lanes:
            assert lane.revised_draft is not None
            audit_input = await load_assertion_audit_input(
                session,
                writer_run_id=lane.writer.run.id,  # type: ignore[union-attr]
                revised_draft_artifact_id=lane.revised_draft.id,
                expected_revised_draft_version=lane.revised_draft.version,
                expected_revised_draft_hash=lane.revised_draft.content_hash,
                outline_artifact_id=outline_result.artifact.id,
                expected_outline_version=outline_result.artifact.version,
                expected_outline_hash=outline_result.artifact.content_hash,
                locale=lane.locale,
            )
            audit_ports[lane.locale] = _CapturePort(_passing_output(audit_input))

        async def fake_audit_port(
            _session: AsyncSession,
            *,
            locale: str,
            **kwargs: object,
        ) -> _CapturePort:
            del _session, kwargs
            return audit_ports[locale]

        monkeypatch.setattr(
            operator_quality_worker,
            "create_cli_assertion_audit_model_port",
            fake_audit_port,
        )
        state_after_one_review = await get_operator_state(session, content_case_id=case_id)
        assert state_after_one_review.state_version != before_quality.state_version
        for _ in range(2):
            job = await operator_quality_worker.claim_or_reclaim_quality_job(
                session, worker_id=f"f4-audit-{_}"
            )
            assert job is not None
            await operator_quality_worker.execute_quality_job(
                session,
                job_id=job.id,
                worker_id=f"f4-audit-{_}",
                runner_registry=registry,
            )

        for _ in range(2):
            job = await operator_quality_worker.claim_or_reclaim_quality_job(
                session, worker_id=f"f4-source-copy-{_}"
            )
            assert job is not None
            await operator_quality_worker.execute_quality_job(
                session,
                job_id=job.id,
                worker_id=f"f4-source-copy-{_}",
                runner_registry=registry,
            )

        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        assert progress.final_gate_ready is True
        assert {lane.status for lane in progress.lanes} == {"final_gate_ready"}
        items = list(
            (
                await session.scalars(
                    select(ContentItem).where(ContentItem.content_case_id == case_id)
                )
            ).all()
        )
        assert len(items) == 2
        assert {item.canonical_key for item in items} == {
            f"journal:{case_id}:vi-VN",
            f"journal:{case_id}:en",
        }
        final_artifacts = list(
            (
                await session.scalars(
                    select(Artifact).where(
                        Artifact.artifact_type == "final_content",
                        Artifact.locale.in_(["vi-VN", "en"]),
                    )
                )
            ).all()
        )
        assert len(final_artifacts) == 2
        for lane in progress.lanes:
            assert lane.writer.run is not None
            assert lane.final_content is not None
            assert lane.final_review is not None
            assert lane.writer.run.content_item_id == lane.final_item.id  # type: ignore[union-attr]
            assert lane.final_content.content_json == copy.deepcopy(lane.revised_draft.content_json)  # type: ignore[union-attr]
            assert lane.final_content.content_hash == lane.revised_draft.content_hash  # type: ignore[union-attr]
            assert lane.final_review.attempt == 1
            assert lane.status == "final_gate_ready"

        state = await get_operator_state(session, content_case_id=case_id)
        assert state.status == "AWAITING_APPROVAL"
        assert state.human_gate == "final_review"
        action = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action.action_key == "await_final_review_approval"
        assert action.executable is False
        view = await get_operator_case_view(session, content_case_id=case_id)
        assert len(view.quality_lanes) == 2
        assert all(lane.pending_approval_ready for lane in view.quality_lanes)
        checkpoints = list(
            (
                await session.scalars(
                    select(Artifact).where(Artifact.artifact_type == "checkpoint")
                )
            ).all()
        )
        pending = [
            checkpoint
            for checkpoint in checkpoints
            if isinstance(checkpoint.content_json, dict)
            and checkpoint.content_json.get("pending_approval")
        ]
        assert len(pending) == 2
        assert await session.scalar(select(func.count(Approval.id))) == 0
        assert await session.scalar(select(func.count(ContentVersion.id))) == 0
        assert await session.scalar(
            select(func.count(OperatorCommand.id)).where(
                OperatorCommand.resolved_action_key == "writers_to_quality"
            )
        ) == 1


@pytest.mark.asyncio
async def test_f4_cancel_all_queued_quality_jobs_settles_parent_without_hanging() -> None:
    async with isolated_session() as session:
        fixture, writer_outputs, outline_result = await _complete_f3_writers(session)
        case_id = fixture.run.content_case_id
        parent_cmd, before_quality = await _dispatch_quality(session, fixture=fixture)
        state_before_cancel = await get_operator_state(session, content_case_id=case_id)
        assert state_before_cancel.status in {"QUEUED", "RUNNING"}

        cancel_cmd = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="cancel",
            expected_state_version=state_before_cancel.state_version,
            idempotency_key="f4-cancel-all-queued",
        )
        assert cancel_cmd.status == "cancelled"

        jobs = list(
            (
                await session.scalars(
                    select(Job).where(
                        Job.run_id.in_(
                            select(ContentRun.id).where(
                                ContentRun.content_case_id == case_id,
                                ContentRun.run_mode == "localize",
                            )
                        )
                    )
                )
            ).all()
        )
        assert len(jobs) == 4
        review_jobs = [j for j in jobs if j.status == "cancelled"]
        assert len(review_jobs) == 2

        cancel_row = await session.get(OperatorCommand, cancel_cmd.command_id)
        parent_row = await session.get(OperatorCommand, parent_cmd.command_id)
        assert cancel_row is not None and cancel_row.status == "cancelled"
        assert cancel_row.error_code is None
        assert parent_row is not None
        assert parent_row.status == "failed"
        assert parent_row.error_code == "operator_quality_job_failed"

        state_after_cancel = await get_operator_state(session, content_case_id=case_id)
        assert state_after_cancel.status == "BLOCKED"
        assert state_after_cancel.primary_intent == "retry"
        assert state_after_cancel.allowed_intents == ["retry"]
        assert parent_row.state_after == state_after_cancel.state_version
        assert cancel_row.state_after == state_after_cancel.state_version

        action = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action.action_key == "writers_to_quality"
        assert action.intent == "retry"
        assert action.executable is True

        retry_cmd = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="retry",
            expected_state_version=action.state_version,
            idempotency_key="f4-retry-after-cancel",
        )
        assert retry_cmd.status == "queued"


@pytest.mark.asyncio
async def test_f4_cancel_queued_sibling_waits_for_running_lane_then_settles_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, writer_outputs, outline_result = await _complete_f3_writers(session)
        case_id = fixture.run.content_case_id
        parent_cmd, before_quality = await _dispatch_quality(session, fixture=fixture)

        review_ports = {
            locale: _CapturePort(payload) for locale, payload in writer_outputs.items()
        }

        async def fake_review_port(
            _session: AsyncSession, *, locale: str, **kwargs: object
        ) -> _CapturePort:
            del _session, kwargs
            return review_ports[locale]

        monkeypatch.setattr(
            operator_quality_worker, "create_cli_review_revise_model_port", fake_review_port
        )

        running_job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-running"
        )
        assert running_job is not None

        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        running_lane = next(
            lane for lane in progress.lanes
            if lane.review.job is not None and lane.review.job.id == running_job.id
        )
        queued_lane = next(lane for lane in progress.lanes if lane != running_lane)

        before_cancel = await get_operator_state(session, content_case_id=case_id)
        cancel_cmd = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="cancel",
            expected_state_version=before_cancel.state_version,
            idempotency_key="f4-cancel-mixed",
        )
        assert cancel_cmd.status == "cancelled"

        parent_row = await session.get(OperatorCommand, parent_cmd.command_id)
        assert parent_row is not None and parent_row.status == "queued"
        state_during = await get_operator_state(session, content_case_id=case_id)
        assert state_during.status == "RUNNING"

        assert queued_lane.review.job is not None
        queued_job_row = await session.get(Job, queued_lane.review.job.id)
        assert queued_job_row is not None and queued_job_row.status == "cancelled"

        registry = AgentRunnerRegistry()
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=running_job.id,
            worker_id="worker-running",
            runner_registry=registry,
        )

        parent_row = await session.get(OperatorCommand, parent_cmd.command_id)
        assert parent_row is not None
        assert parent_row.status == "failed"
        assert parent_row.error_code == "operator_quality_job_failed"
        state_after = await get_operator_state(session, content_case_id=case_id)
        assert state_after.status == "BLOCKED"
        assert state_after.primary_intent == "retry"
        assert state_after.blocker_code == "operator_quality_job_failed"
        assert parent_row.state_after == state_after.state_version


@pytest.mark.asyncio
async def test_f4_expired_attempt_two_settles_parent_after_sibling_completed() -> None:
    async with isolated_session() as session:
        fixture, writer_outputs, outline_result = await _complete_f3_writers(session)
        case_id = fixture.run.content_case_id
        parent_cmd, before_quality = await _dispatch_quality(session, fixture=fixture)

        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        target_lane = progress.lanes[0]
        sibling_lane = progress.lanes[1]
        assert target_lane.review.job is not None
        assert sibling_lane.review.job is not None

        sibling_job = sibling_lane.review.job
        sibling_job.status = "completed"
        sibling_job.lease_owner = None
        sibling_job.lease_expires_at = None
        if sibling_lane.review.step is not None:
            sibling_lane.review.step.status = "running"
            await session.flush()
            sibling_lane.review.step.status = "completed"

        target_job = target_lane.review.job
        target_job.status = "leased"
        target_job.attempt = 2
        target_job.lease_owner = "worker-expired"
        target_job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        if target_lane.review.step is not None:
            target_lane.review.step.status = "running"
        await session.flush()

        reclaim_result = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-reclaim"
        )
        assert reclaim_result is None

        target_job_row = await session.get(Job, target_job.id)
        assert target_job_row is not None
        assert target_job_row.status == "failed"
        assert target_job_row.attempt == 2

        parent_row = await session.get(OperatorCommand, parent_cmd.command_id)
        assert parent_row is not None
        assert parent_row.status == "failed"
        assert parent_row.error_code == "operator_quality_retry_exhausted"

        state = await get_operator_state(session, content_case_id=case_id)
        assert state.status == "BLOCKED"
        assert state.primary_intent is None
        assert state.allowed_intents == []
        assert state.blocker_code == "operator_quality_retry_exhausted"
        assert parent_row.state_after == state.state_version

        action = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action.executable is False
        assert action.intent is None


@pytest.mark.asyncio
async def test_f4_expired_attempt_two_waits_for_active_sibling_then_settles_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, writer_outputs, outline_result = await _complete_f3_writers(session)
        case_id = fixture.run.content_case_id
        parent_cmd, before_quality = await _dispatch_quality(session, fixture=fixture)

        review_ports = {
            locale: _CapturePort(payload) for locale, payload in writer_outputs.items()
        }

        async def fake_review_port(
            _session: AsyncSession, *, locale: str, **kwargs: object
        ) -> _CapturePort:
            del _session, kwargs
            return review_ports[locale]

        monkeypatch.setattr(
            operator_quality_worker, "create_cli_review_revise_model_port", fake_review_port
        )

        target_job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-target"
        )
        assert target_job is not None
        target_job.attempt = 2
        target_job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.flush()

        sibling_job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-sibling"
        )
        assert sibling_job is not None

        reclaimed = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-terminal"
        )
        assert reclaimed is None

        parent_row = await session.get(OperatorCommand, parent_cmd.command_id)
        assert parent_row is not None and parent_row.status == "queued"
        state_during = await get_operator_state(session, content_case_id=case_id)
        assert state_during.status == "RUNNING"

        registry = AgentRunnerRegistry()
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=sibling_job.id,
            worker_id="worker-sibling",
            runner_registry=registry,
        )

        parent_row = await session.get(OperatorCommand, parent_cmd.command_id)
        assert parent_row is not None
        assert parent_row.status == "failed"
        assert parent_row.error_code == "operator_quality_retry_exhausted"

        state_final = await get_operator_state(session, content_case_id=case_id)
        assert state_final.status == "BLOCKED"
        assert state_final.blocker_code == "operator_quality_retry_exhausted"
        assert parent_row.state_after == state_final.state_version


@pytest.mark.asyncio
async def test_f4_technical_failure_attempt_one_waits_for_active_sibling_then_settles_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, writer_outputs, outline_result = await _complete_f3_writers(session)
        case_id = fixture.run.content_case_id
        parent_cmd, before_quality = await _dispatch_quality(session, fixture=fixture)

        review_ports = {
            locale: _CapturePort(payload) for locale, payload in writer_outputs.items()
        }

        async def fake_review_port(
            _session: AsyncSession, *, locale: str, **kwargs: object
        ) -> _CapturePort:
            del _session, kwargs
            return review_ports[locale]

        monkeypatch.setattr(
            operator_quality_worker, "create_cli_review_revise_model_port", fake_review_port
        )

        job1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-1"
        )
        job2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-2"
        )
        assert job1 is not None and job2 is not None

        await operator_quality_worker.fail_quality_job(
            session,
            job_id=job1.id,
            worker_id="worker-1",
            failure_class="network_timeout",
            message="Connection timed out",
        )

        parent_row = await session.get(OperatorCommand, parent_cmd.command_id)
        assert parent_row is not None and parent_row.status == "queued"
        state_during = await get_operator_state(session, content_case_id=case_id)
        assert state_during.status == "RUNNING"

        registry = AgentRunnerRegistry()
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=job2.id,
            worker_id="worker-2",
            runner_registry=registry,
        )

        parent_row = await session.get(OperatorCommand, parent_cmd.command_id)
        assert parent_row is not None
        assert parent_row.status == "failed"
        assert parent_row.error_code == "operator_quality_job_failed"

        state_final = await get_operator_state(session, content_case_id=case_id)
        assert state_final.status == "BLOCKED"
        assert state_final.primary_intent == "retry"
        assert state_final.blocker_code == "operator_quality_job_failed"
        assert parent_row.state_after == state_final.state_version

