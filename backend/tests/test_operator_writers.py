from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_outline import isolated_session
from test_ce05_writer import (
    FakeWriterRunner,
    _draft_payload,
    _ensure_variant,
    _outline_result,
    _writer_fixture,
)

from app.modules.content_engine.journal import operator_writer_worker
from app.modules.content_engine.journal.models import (
    JournalRequiredLocale,
    OperatorCommand,
    OutlineApproval,
)
from app.modules.content_engine.journal.operator_control import OperatorControlError
from app.modules.content_engine.journal.operator_runtime import (
    get_operator_state,
    resolve_next_operator_action,
    submit_operator_command,
)
from app.modules.content_engine.journal.operator_vertical_slice import normalize_journal_locale
from app.modules.content_engine.journal.operator_writers import get_writer_lane_progress
from app.modules.content_engine.journal.writer import (
    _canonical_hash,
    _writer_handoff_payload,
    load_writer_input,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import Artifact, ContentRun, Job, StepRun
from app.modules.system.settings_service import settings_hash


async def _f3_case(session: AsyncSession):  # type: ignore[no-untyped-def]
    fixture, outline_result = await _outline_result(session)
    route_settings = {
        "models": {"angle": {"route": "agent_angle"}},
        "model_routes": {
            "agent_angle": {"provider": "codex_cli", "model": "test-model"}
        },
    }
    route_snapshot = SettingsSnapshot(
        project_id=fixture.run.project_id,
        resolved_settings_json=route_settings,
        source_version_refs_json=["f3-writers-test"],
        content_hash=settings_hash(route_settings),
    )
    session.add(route_snapshot)
    await session.flush()
    fixture.run.settings_snapshot_id = route_snapshot.id
    fixture.run.current_step = "outline"
    fixture.run.status = "waiting_approval"
    await _ensure_variant(session, run=fixture.run, locale="vi-VN")
    session.add_all(
        [
            JournalRequiredLocale(
                content_case_id=fixture.run.content_case_id,
                locale="en",
                role="source",
                declared_by="founder",
            ),
            JournalRequiredLocale(
                content_case_id=fixture.run.content_case_id,
                locale="vi-VN",
                role="translation",
                declared_by="founder",
            ),
            OutlineApproval(
                run_id=fixture.run.id,
                outline_artifact_id=outline_result.artifact.id,
                outline_artifact_version=outline_result.artifact.version,
                outline_artifact_hash=outline_result.artifact.content_hash,
                approved_by="founder",
                approval_reason="Approved exact F3 fixture Outline.",
                approved_at=datetime.now(UTC),
            ),
        ]
    )
    await session.flush()
    return fixture, outline_result


def test_f3_locale_aliases_are_canonical_and_unsupported_locales_fail_closed() -> None:
    assert normalize_journal_locale("vi") == "vi-VN"
    assert normalize_journal_locale(" VI-vn ") == "vi-VN"
    assert normalize_journal_locale("en") == "en"
    with pytest.raises(OperatorControlError, match="operator_locale_unsupported"):
        normalize_journal_locale("fr")


@pytest.mark.asyncio
async def test_f3_continue_creates_two_exact_independent_lanes_and_replays() -> None:
    async with isolated_session() as session:
        fixture, outline_result = await _f3_case(session)
        case_id = fixture.run.content_case_id
        initial = await resolve_next_operator_action(session, content_case_id=case_id)
        assert initial.action_key == "outline_to_writers"
        assert initial.intent == "continue"
        assert initial.executable is True

        first = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="continue",
            expected_state_version=initial.state_version,
            idempotency_key="f3-writers-continue",
        )
        dispatched_state = await get_operator_state(session, content_case_id=case_id)
        assert dispatched_state.state_version != initial.state_version
        assert dispatched_state.status == "QUEUED"
        replay = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="continue",
            expected_state_version=initial.state_version,
            idempotency_key="f3-writers-continue",
        )
        assert first.status == "queued"
        assert first.job_id is None
        assert replay.replayed is True
        assert replay.command_id == first.command_id

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
        assert len(runs) == 2
        steps = list(
            (
                await session.scalars(
                    select(StepRun).where(StepRun.run_id.in_([run.id for run in runs]))
                )
            ).all()
        )
        jobs = list(
            (
                await session.scalars(
                    select(Job).where(Job.run_id.in_([run.id for run in runs]))
                )
            ).all()
        )
        assert {step.step_key for step in steps} == {"writer_vi", "writer_en"}
        assert len(steps) == len(jobs) == 2
        assert {job.attempt for job in jobs} == {1}
        assert len({job.dedupe_key for job in jobs}) == 2
        for run in runs:
            handoff = await session.scalar(
                select(Artifact).where(
                    Artifact.run_id == run.id,
                    Artifact.artifact_type == "writer_handoff",
                )
            )
            assert handoff is not None
            payload = cast(dict[str, object], handoff.content_json)
            assert payload["source_run_id"] == str(fixture.run.id)
            assert cast(dict[str, object], payload["source_outline"])["id"] == str(
                outline_result.artifact.id
            )
            assert cast(dict[str, object], payload["outline_approval"])["id"] == str(
                next(
                    approval.id
                    for approval in (
                        await session.scalars(
                            select(OutlineApproval).where(
                                OutlineApproval.run_id == fixture.run.id
                            )
                        )
                    ).all()
                )
            )

        progress = await get_writer_lane_progress(
            session,
            content_case_id=case_id,
            source_run_id=fixture.run.id,
        )
        assert progress is not None
        for lane in progress.lanes:
            assert lane.run is not None
            writer_input = await load_writer_input(
                session,
                writer_run_id=lane.run.id,
                outline_artifact_id=progress.outline_artifact.id,
                expected_outline_version=progress.outline_artifact.version,
                expected_outline_hash=progress.outline_artifact.content_hash,
                outline_approval_id=progress.outline_approval.id,
                locale=lane.required_locale,
            )
            assert cast(dict[str, object], writer_input.model_input["outline_approval_ref"])[
                "id"
            ] == str(progress.outline_approval.id)
            assert "other_locale_draft" not in writer_input.model_input
            assert "translation_source" not in writer_input.model_input

        assert progress is not None
        assert progress.outline_artifact.id == outline_result.artifact.id
        assert {lane.required_locale for lane in progress.lanes} == {"vi-VN", "en"}
        assert all(lane.status == "queued" for lane in progress.lanes)


class _FakeWriterPort:
    def __init__(self, output: dict[str, object]) -> None:
        self.output = output

    def resolved_model_identity(self) -> tuple[str, str]:
        return "codex_cli", "test-model"

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        del input_bundle, attempt
        return self.output


@pytest.mark.asyncio
async def test_f3_writer_failure_preserves_sibling_and_retries_only_failed_lane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _outline_result_value = await _f3_case(session)
        case_id = fixture.run.content_case_id
        initial = await resolve_next_operator_action(session, content_case_id=case_id)
        parent = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="continue",
            expected_state_version=initial.state_version,
            idempotency_key="f3-writers-failure-continue",
        )
        progress = await get_writer_lane_progress(
            session,
            content_case_id=case_id,
            source_run_id=fixture.run.id,
        )
        assert progress is not None
        for lane in progress.lanes:
            assert lane.run is not None
            lane.run.status = "running"
        await session.flush()

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
        outputs = {
            locale: _draft_payload(writer_input, locale)
            for locale, writer_input in inputs.items()
        }

        async def fake_port(  # type: ignore[no-untyped-def]
            _session, *, run_id, settings_snapshot, context_manifest_id, runner_registry, locale
        ):
            del _session, run_id, settings_snapshot, context_manifest_id, runner_registry
            return _FakeWriterPort(cast(dict[str, object], outputs[locale]))

        monkeypatch.setattr(operator_writer_worker, "create_cli_writer_model_port", fake_port)
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", FakeWriterRunner({}))

        claimed = {}
        for worker_id in ("worker-vi", "worker-en"):
            job = await operator_writer_worker.claim_or_reclaim_writer_job(
                session,
                worker_id=worker_id,
            )
            assert job is not None
            claimed_step = await session.get(StepRun, job.step_run_id)
            assert claimed_step is not None
            claimed[claimed_step.step_key] = (worker_id, job.id)
        await session.flush()

        en_worker_id, en_job_id = claimed["writer_en"]
        await operator_writer_worker.fail_writer_job(
            session,
            job_id=en_job_id,
            worker_id=en_worker_id,
            failure_class="fixture_en_failed",
            message="forced independent lane failure",
        )
        parent_row = await session.get(OperatorCommand, parent.command_id)
        assert parent_row is not None
        assert parent_row.status == "queued"
        while_state = await get_operator_state(session, content_case_id=case_id)
        assert while_state.status == "RUNNING"

        vi_worker_id, vi_job_id = claimed["writer_vi"]
        await operator_writer_worker.execute_writer_job(
            session,
            job_id=vi_job_id,
            worker_id=vi_worker_id,
            runner_registry=registry,
        )
        await session.refresh(parent_row)
        assert parent_row.status == "failed"
        assert parent_row.error_code == "operator_writer_lane_failed"
        blocked = await get_operator_state(session, content_case_id=case_id)
        assert blocked.status == "BLOCKED"
        assert blocked.primary_intent == "retry"
        retry_action = await resolve_next_operator_action(session, content_case_id=case_id)
        assert retry_action.action_key == "outline_to_writers"
        assert retry_action.intent == "retry"
        assert retry_action.executable is True

        retry = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="retry",
            expected_state_version=blocked.state_version,
            idempotency_key="f3-writers-en-retry",
        )
        assert retry.job_id is None
        progress = await get_writer_lane_progress(
            session,
            content_case_id=case_id,
            source_run_id=fixture.run.id,
        )
        assert progress is not None
        assert progress.lanes[0].status in {"completed", "queued"}
        retry_lane = next(lane for lane in progress.lanes if lane.required_locale == "en")
        assert retry_lane.latest_job is not None
        assert retry_lane.latest_job.attempt == 2
        assert retry_lane.draft is None
        retry_lane.run.status = "running"  # type: ignore[union-attr]
        await session.flush()
        retry_job = await operator_writer_worker.claim_or_reclaim_writer_job(
            session,
            worker_id="worker-en-retry",
        )
        assert retry_job is not None
        await operator_writer_worker.execute_writer_job(
            session,
            job_id=retry_job.id,
            worker_id="worker-en-retry",
            runner_registry=registry,
        )

        final_action = await resolve_next_operator_action(session, content_case_id=case_id)
        assert final_action.action_key == "writers_to_quality"
        assert final_action.intent == "continue"
        assert final_action.executable is False
        final_progress = await get_writer_lane_progress(
            session,
            content_case_id=case_id,
            source_run_id=fixture.run.id,
        )
        assert final_progress is not None and final_progress.all_complete
        assert all(lane.draft is not None for lane in final_progress.lanes)
        assert {lane.status for lane in final_progress.lanes} == {"completed"}
        for lane in final_progress.lanes:
            assert lane.draft is not None
            draft_payload = cast(dict[str, object], lane.draft.content_json)
            draft_handoff = cast(dict[str, object], draft_payload["writer_handoff"])
            assert cast(dict[str, object], draft_handoff["outline_approval"])["id"] == str(
                final_progress.outline_approval.id
            )


@pytest.mark.asyncio
async def test_f3_exhausted_lane_blocks_retry_and_settles_fanout_closed() -> None:
    async with isolated_session() as session:
        fixture, _outline_result_value = await _f3_case(session)
        case_id = fixture.run.content_case_id
        initial = await resolve_next_operator_action(session, content_case_id=case_id)
        parent = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="continue",
            expected_state_version=initial.state_version,
            idempotency_key="f3-writers-exhausted-continue",
        )
        progress = await get_writer_lane_progress(
            session,
            content_case_id=case_id,
            source_run_id=fixture.run.id,
        )
        assert progress is not None
        for lane in progress.lanes:
            assert lane.run is not None
            lane.run.status = "running"
        target = next(lane for lane in progress.lanes if lane.required_locale == "en")
        sibling = next(lane for lane in progress.lanes if lane.required_locale == "vi-VN")
        assert target.latest_job is not None
        assert sibling.latest_job is not None
        target.latest_job.attempt = 2
        sibling.latest_job.status = "cancelled"
        await session.flush()

        claimed = await operator_writer_worker.claim_or_reclaim_writer_job(
            session,
            worker_id="worker-exhausted",
        )
        assert claimed is not None and claimed.id == target.latest_job.id
        await operator_writer_worker.fail_writer_job(
            session,
            job_id=claimed.id,
            worker_id="worker-exhausted",
            failure_class="fixture_en_failed_again",
            message="bounded attempt exhausted",
        )

        blocked = await get_operator_state(session, content_case_id=case_id)
        assert blocked.status == "BLOCKED"
        assert blocked.primary_intent is None
        assert blocked.allowed_intents == []
        assert blocked.blocker_code == "operator_writer_retry_exhausted"
        action = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action.action_key == "outline_to_writers"
        assert action.intent is None
        assert action.executable is False
        assert action.blocker_code == "operator_writer_retry_exhausted"
        with pytest.raises(OperatorControlError, match="operator_writer_retry_exhausted"):
            await submit_operator_command(
                session,
                content_case_id=case_id,
                intent="retry",
                expected_state_version=blocked.state_version,
                idempotency_key="f3-writers-exhausted-retry",
            )
        parent_row = await session.get(OperatorCommand, parent.command_id)
        assert parent_row is not None
        assert parent_row.status == "failed"
        assert parent_row.error_code == "operator_writer_retry_exhausted"


@pytest.mark.asyncio
async def test_f3_retry_exhaustion_preserves_completed_lane_and_settles_retry_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _outline_result_value = await _f3_case(session)
        case_id = fixture.run.content_case_id
        initial = await resolve_next_operator_action(session, content_case_id=case_id)
        parent = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="continue",
            expected_state_version=initial.state_version,
            idempotency_key="f3-writers-retry-exhaustion-parent",
        )
        progress = await get_writer_lane_progress(
            session,
            content_case_id=case_id,
            source_run_id=fixture.run.id,
        )
        assert progress is not None
        for lane in progress.lanes:
            assert lane.run is not None
            lane.run.status = "running"
        inputs = {
            lane.required_locale: await load_writer_input(
                session,
                writer_run_id=lane.run.id,
                outline_artifact_id=progress.outline_artifact.id,
                expected_outline_version=progress.outline_artifact.version,
                expected_outline_hash=progress.outline_artifact.content_hash,
                outline_approval_id=progress.outline_approval.id,
                locale=lane.required_locale,
            )
            for lane in progress.lanes
            if lane.run is not None
        }
        outputs = {
            locale: _draft_payload(writer_input, locale)
            for locale, writer_input in inputs.items()
        }

        async def fake_port(  # type: ignore[no-untyped-def]
            _session, *, run_id, settings_snapshot, context_manifest_id, runner_registry, locale
        ):
            del _session, run_id, settings_snapshot, context_manifest_id, runner_registry
            return _FakeWriterPort(cast(dict[str, object], outputs[locale]))

        monkeypatch.setattr(operator_writer_worker, "create_cli_writer_model_port", fake_port)
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", FakeWriterRunner({}))
        claimed: dict[str, tuple[str, object]] = {}
        for worker_id in ("worker-retry-vi", "worker-retry-en"):
            job = await operator_writer_worker.claim_or_reclaim_writer_job(
                session,
                worker_id=worker_id,
            )
            assert job is not None
            step = await session.get(StepRun, job.step_run_id)
            assert step is not None
            claimed[step.step_key] = (worker_id, job.id)

        en_worker_id, en_job_id = claimed["writer_en"]
        await operator_writer_worker.fail_writer_job(
            session,
            job_id=en_job_id,
            worker_id=en_worker_id,
            failure_class="fixture_en_first_failure",
            message="first bounded failure",
        )
        vi_worker_id, vi_job_id = claimed["writer_vi"]
        await operator_writer_worker.execute_writer_job(
            session,
            job_id=vi_job_id,
            worker_id=vi_worker_id,
            runner_registry=registry,
        )
        blocked = await get_operator_state(session, content_case_id=case_id)
        retry = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="retry",
            expected_state_version=blocked.state_version,
            idempotency_key="f3-writers-retry-exhaustion-retry",
        )
        retry_progress = await get_writer_lane_progress(
            session,
            content_case_id=case_id,
            source_run_id=fixture.run.id,
        )
        assert retry_progress is not None
        retry_lane = next(
            lane for lane in retry_progress.lanes if lane.required_locale == "en"
        )
        assert retry_lane.run is not None and retry_lane.latest_job is not None
        retry_lane.run.status = "running"
        await session.flush()
        retry_job = await operator_writer_worker.claim_or_reclaim_writer_job(
            session,
            worker_id="worker-retry-en-second",
        )
        assert retry_job is not None and retry_job.attempt == 2
        await operator_writer_worker.fail_writer_job(
            session,
            job_id=retry_job.id,
            worker_id="worker-retry-en-second",
            failure_class="fixture_en_second_failure",
            message="second bounded failure",
        )
        final_progress = await get_writer_lane_progress(
            session,
            content_case_id=case_id,
            source_run_id=fixture.run.id,
        )
        assert final_progress is not None
        vi_lane = next(lane for lane in final_progress.lanes if lane.required_locale == "vi-VN")
        en_lane = next(lane for lane in final_progress.lanes if lane.required_locale == "en")
        assert vi_lane.status == "completed"
        assert vi_lane.draft is not None
        assert en_lane.status == "failed"
        assert en_lane.latest_job is not None and en_lane.latest_job.attempt == 2
        exhausted = await get_operator_state(session, content_case_id=case_id)
        assert exhausted.blocker_code == "operator_writer_retry_exhausted"
        assert exhausted.primary_intent is None
        parent_row = await session.get(OperatorCommand, parent.command_id)
        retry_row = await session.get(OperatorCommand, retry.command_id)
        assert parent_row is not None
        assert parent_row.status == "failed"
        assert retry_row is not None
        assert retry_row.status == "failed"
        assert retry_row.error_code == "operator_writer_retry_exhausted"
        vi_jobs = list(
            (
                await session.scalars(
                    select(Job).where(Job.run_id == vi_lane.run.id)
                )
            ).all()
        )
        assert len(vi_jobs) == 1


@pytest.mark.asyncio
async def test_f3_legacy_writer_payload_keeps_pre_f3_shape_and_hash() -> None:
    async with isolated_session() as session:
        fixture = await _writer_fixture(session, locale="en")
        handoff = fixture.writer_input.handoff_artifact
        payload = cast(dict[str, object], handoff.content_json)
        assert "outline_approval" not in payload
        assert "outline_approval_ref" not in fixture.writer_input.model_input
        expected = _writer_handoff_payload(
            source_run=fixture.outline_fixture.run,
            outline_artifact=fixture.outline_result.artifact,
            locale_variant=fixture.writer_input.locale_variant,
        )
        assert payload == expected
        assert handoff.content_hash == _canonical_hash(expected)


@pytest.mark.asyncio
async def test_f3_symmetric_vi_failure_keeps_en_lane_and_blocks_without_retry() -> None:
    async with isolated_session() as session:
        fixture, _outline_result_value = await _f3_case(session)
        case_id = fixture.run.content_case_id
        initial = await resolve_next_operator_action(session, content_case_id=case_id)
        parent = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="continue",
            expected_state_version=initial.state_version,
            idempotency_key="f3-writers-symmetric-continue",
        )
        progress = await get_writer_lane_progress(
            session,
            content_case_id=case_id,
            source_run_id=fixture.run.id,
        )
        assert progress is not None
        for lane in progress.lanes:
            assert lane.run is not None
            lane.run.status = "running"
        claimed: dict[str, tuple[str, object]] = {}
        for worker_id in ("worker-one", "worker-two"):
            job = await operator_writer_worker.claim_or_reclaim_writer_job(
                session,
                worker_id=worker_id,
            )
            assert job is not None
            step = await session.get(StepRun, job.step_run_id)
            assert step is not None
            claimed[step.step_key] = (worker_id, job.id)
        vi_worker_id, vi_job_id = claimed["writer_vi"]
        await operator_writer_worker.fail_writer_job(
            session,
            job_id=vi_job_id,
            worker_id=vi_worker_id,
            failure_class="fixture_vi_failed",
            message="forced VI failure",
        )
        assert (await get_operator_state(session, content_case_id=case_id)).status == "RUNNING"
        en_worker_id, en_job_id = claimed["writer_en"]
        await operator_writer_worker.fail_writer_job(
            session,
            job_id=en_job_id,
            worker_id=en_worker_id,
            failure_class="fixture_en_failed",
            message="forced EN failure",
        )
        blocked = await get_operator_state(session, content_case_id=case_id)
        assert blocked.status == "BLOCKED"
        assert blocked.primary_intent == "retry"
        parent_row = await session.get(OperatorCommand, parent.command_id)
        assert parent_row is not None
        assert parent_row.status == "failed"
        assert parent_row.error_code == "operator_writer_lane_failed"
        action = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action.action_key == "outline_to_writers"
        assert action.intent == "retry"
        assert action.executable is True


@pytest.mark.asyncio
async def test_f3_expired_writer_lease_reclaims_once_then_fails_closed_at_limit() -> None:
    async with isolated_session() as session:
        fixture, _outline_result_value = await _f3_case(session)
        case_id = fixture.run.content_case_id
        initial = await resolve_next_operator_action(session, content_case_id=case_id)
        await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="continue",
            expected_state_version=initial.state_version,
            idempotency_key="f3-writers-lease",
        )
        progress = await get_writer_lane_progress(
            session,
            content_case_id=case_id,
            source_run_id=fixture.run.id,
        )
        assert progress is not None
        for lane in progress.lanes:
            assert lane.run is not None
            lane.run.status = "running"
        job = await operator_writer_worker.claim_or_reclaim_writer_job(
            session,
            worker_id="worker-first",
            lease_seconds=10,
        )
        assert job is not None
        sibling = await session.scalar(
            select(Job).where(
                Job.id != job.id,
                Job.run_id.in_([lane.run.id for lane in progress.lanes if lane.run]),
            )
        )
        assert sibling is not None
        sibling.status = "cancelled"
        job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.flush()
        reclaimed = await operator_writer_worker.claim_or_reclaim_writer_job(
            session,
            worker_id="worker-reclaimed",
            lease_seconds=10,
        )
        assert reclaimed is not None and reclaimed.id == job.id and reclaimed.attempt == 2
        reclaimed.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.flush()
        assert (
            await operator_writer_worker.claim_or_reclaim_writer_job(
                session,
                worker_id="worker-after-limit",
                lease_seconds=10,
            )
            is None
        )
        exhausted = await session.get(Job, job.id)
        assert exhausted is not None
        assert exhausted.status == "failed"
        assert exhausted.attempt == 2
