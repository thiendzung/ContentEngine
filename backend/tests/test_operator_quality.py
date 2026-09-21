from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

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
from app.modules.content_engine.journal.operator_control import OperatorControlError
from app.modules.content_engine.journal.operator_decisions import submit_operator_decision
from app.modules.content_engine.journal.operator_quality import (
    QUALITY_AUDIT_TASK_KEYS,
    QUALITY_REVIEW_TASK_KEYS,
    get_quality_progress,
)
from app.modules.content_engine.journal.operator_runtime import (
    get_operator_state,
    resolve_next_operator_action,
    submit_operator_command,
)
from app.modules.content_engine.journal.operator_view import get_operator_case_view
from app.modules.content_engine.journal.quality_readiness import READINESS_CRITERIA
from app.modules.content_engine.models import ContentItem, ContentVersion
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import Approval, Artifact, ContentRun, Job, StepRun, utc_now


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


def _passing_readiness_output(stage: str, locale: str) -> dict[str, object]:
    return {
        "locale": locale,
        "result": "pass",
        "summary": f"{stage} passes in the bounded fixture.",
        "criteria": [
            {
                "key": key,
                "result": "pass",
                "finding": f"{key} passes.",
                "repair_suggestion": "",
            }
            for key in READINESS_CRITERIA[stage]
        ],
    }


async def _install_passing_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_readiness_port(
        _session: AsyncSession,
        *,
        stage: str,
        locale: str,
        **kwargs: object,
    ) -> _CapturePort:
        del _session, kwargs
        return _CapturePort(_passing_readiness_output(stage, locale))

    monkeypatch.setattr(
        operator_quality_worker,
        "create_cli_quality_readiness_model_port",
        _fake_readiness_port,
    )


async def _complete_readiness_lane(
    session: AsyncSession,
    *,
    case_id: UUID,
    locale: str,
    monkeypatch: pytest.MonkeyPatch,
    runner_registry: AgentRunnerRegistry,
    worker_prefix: str,
) -> None:
    await _install_passing_readiness(monkeypatch)
    for stage_name in ("reader_value", "search_ai"):
        progress = await get_quality_progress(
            session,
            content_case_id=case_id,
            source_run_id=None,
        )
        assert progress is not None
        lane = next(candidate for candidate in progress.lanes if candidate.locale == locale)
        stage = getattr(lane, stage_name)
        assert stage.job is not None
        job = await session.get(Job, stage.job.id)
        assert job is not None
        assert job.status == "queued"
        step = await session.get(StepRun, job.step_run_id)
        assert step is not None
        expected_prefix = (
            "reader_value_" if stage_name == "reader_value" else "search_ai_readiness_"
        )
        assert step.step_key.startswith(expected_prefix)
        run = await session.get(ContentRun, job.run_id)
        assert run is not None
        now = utc_now()
        step.status = "running"
        step.started_at = now
        if run.status == "pending":
            run.status = "running"
        worker_id = f"{worker_prefix}-{stage_name}"
        job.status = "leased"
        job.lease_owner = worker_id
        job.lease_expires_at = now + timedelta(seconds=900)
        job.updated_at = now
        await session.flush()
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=job.id,
            worker_id=worker_id,
            runner_registry=runner_registry,
        )


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


async def _complete_healthy_lane_from_audit(
    session: AsyncSession,
    *,
    case_id: UUID,
    outline_result: object,
    step_run_id: UUID,
    monkeypatch: pytest.MonkeyPatch,
    worker_prefix: str,
    runner_registry: AgentRunnerRegistry,
) -> None:
    progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
    assert progress is not None
    healthy_lane = next(
        lane
        for lane in progress.lanes
        if (lane.review.step is not None and lane.review.step.id == step_run_id)
        or (lane.audit.step is not None and lane.audit.step.id == step_run_id)
    )
    assert healthy_lane.revised_draft is not None

    if healthy_lane.audit.job is not None and healthy_lane.audit.job.status == "queued":
        async def _fake_audit_port(_s: AsyncSession, *, locale: str, **kw: object) -> _CapturePort:
            del _s, kw
            prog = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
            assert prog is not None
            lane = next(cand for cand in prog.lanes if cand.locale == locale)
            assert lane.revised_draft is not None
            lane_audit_input = await load_assertion_audit_input(
                session,
                writer_run_id=lane.writer.run.id,  # type: ignore[union-attr]
                revised_draft_artifact_id=lane.revised_draft.id,
                expected_revised_draft_version=lane.revised_draft.version,
                expected_revised_draft_hash=lane.revised_draft.content_hash,
                outline_artifact_id=outline_result.artifact.id,  # type: ignore[union-attr]
                expected_outline_version=outline_result.artifact.version,  # type: ignore[union-attr]
                expected_outline_hash=outline_result.artifact.content_hash,  # type: ignore[union-attr]
                locale=lane.locale,
            )
            return _CapturePort(_passing_output(lane_audit_input))

        monkeypatch.setattr(
            operator_quality_worker,
            "create_cli_assertion_audit_model_port",
            _fake_audit_port,
        )
        audit_job = await session.get(Job, healthy_lane.audit.job.id)
        assert audit_job is not None
        step = await session.get(StepRun, audit_job.step_run_id)
        assert step is not None
        step.status = "running"
        now = utc_now()
        step.started_at = now
        run = await session.get(ContentRun, audit_job.run_id)
        assert run is not None
        if run.status == "pending":
            run.status = "running"
        audit_job.status = "leased"
        audit_job.lease_owner = f"{worker_prefix}-audit"
        audit_job.lease_expires_at = now + timedelta(seconds=900)
        audit_job.updated_at = now
        await session.flush()
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=audit_job.id,
            worker_id=f"{worker_prefix}-audit",
            runner_registry=runner_registry,
        )

    progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
    assert progress is not None
    refreshed_lane = next(lane for lane in progress.lanes if lane.locale == healthy_lane.locale)
    if (
        refreshed_lane.source_copy.job is not None
        and refreshed_lane.source_copy.job.status == "queued"
    ):
        source_job = await session.get(Job, refreshed_lane.source_copy.job.id)
        assert source_job is not None
        step = await session.get(StepRun, source_job.step_run_id)
        assert step is not None
        step.status = "running"
        now = utc_now()
        step.started_at = now
        run = await session.get(ContentRun, source_job.run_id)
        assert run is not None
        if run.status == "pending":
            run.status = "running"
        source_job.status = "leased"
        source_job.lease_owner = f"{worker_prefix}-source"
        source_job.lease_expires_at = now + timedelta(seconds=900)
        source_job.updated_at = now
        await session.flush()
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=source_job.id,
            worker_id=f"{worker_prefix}-source",
            runner_registry=runner_registry,
        )

    await _complete_readiness_lane(
        session,
        case_id=case_id,
        locale=healthy_lane.locale,
        monkeypatch=monkeypatch,
        runner_registry=runner_registry,
        worker_prefix=f"{worker_prefix}-readiness",
    )


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

        await _complete_readiness_lane(
            session,
            case_id=case_id,
            locale="vi-VN",
            monkeypatch=monkeypatch,
            runner_registry=registry,
            worker_prefix="f4-readiness-vi",
        )
        await _complete_readiness_lane(
            session,
            case_id=case_id,
            locale="en",
            monkeypatch=monkeypatch,
            runner_registry=registry,
            worker_prefix="f4-readiness-en",
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

        vi_lane = next(lane for lane in progress.lanes if lane.locale == "vi-VN")
        en_lane = next(lane for lane in progress.lanes if lane.locale == "en")
        assert vi_lane.writer.run is not None
        assert en_lane.writer.run is not None

        vi_result = await submit_operator_decision(
            session,
            content_case_id=case_id,
            scope="final",
            decision="approved",
            expected_state_version=state.state_version,
            idempotency_key="f6-partial-final-approve-vi",
            locale_variant_id=vi_lane.variant.id,
        )
        assert vi_result.approval_id is not None

        partial_progress = await get_quality_progress(
            session,
            content_case_id=case_id,
            source_run_id=None,
        )
        assert partial_progress is not None
        partial_by_locale = {lane.locale: lane for lane in partial_progress.lanes}
        assert partial_by_locale["vi-VN"].status == "qualified"
        assert partial_by_locale["en"].status == "final_gate_ready"

        partial_state = await get_operator_state(session, content_case_id=case_id)
        assert partial_state.status == "AWAITING_APPROVAL"
        assert partial_state.human_gate == "final_review"
        assert partial_state.current_run_id == en_lane.writer.run.id
        assert partial_state.blocker_code is None

        partial_action = await resolve_next_operator_action(
            session,
            content_case_id=case_id,
        )
        assert partial_action.action_key == "await_final_review_approval"
        assert partial_action.executable is False

        partial_view = await get_operator_case_view(session, content_case_id=case_id)
        pending_by_locale = {
            lane.locale: lane.pending_approval_ready for lane in partial_view.quality_lanes
        }
        assert pending_by_locale == {"en": True, "vi-VN": False}
        assert await session.scalar(select(func.count(Approval.id))) == 1
        assert await session.scalar(select(func.count(ContentVersion.id))) == 1

        en_result = await submit_operator_decision(
            session,
            content_case_id=case_id,
            scope="final",
            decision="approved",
            expected_state_version=partial_state.state_version,
            idempotency_key="f6-partial-final-approve-en",
            locale_variant_id=en_lane.variant.id,
        )
        assert en_result.approval_id is not None

        complete_state = await get_operator_state(session, content_case_id=case_id)
        assert complete_state.status == "COMPLETE"
        assert complete_state.human_gate is None
        assert complete_state.blocker_code is None
        assert await session.scalar(select(func.count(Approval.id))) == 2
        assert await session.scalar(select(func.count(ContentVersion.id))) == 2


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
        # Healthy lane enqueued Audit and continued; parent command remains queued
        assert parent_row.status == "queued"

        await _complete_healthy_lane_from_audit(
            session,
            case_id=case_id,
            outline_result=outline_result,
            step_run_id=running_job.step_run_id,
            monkeypatch=monkeypatch,
            worker_prefix="worker-running",
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
        # Sibling lane enqueued Audit; parent command remains queued
        assert parent_row.status == "queued"

        await _complete_healthy_lane_from_audit(
            session,
            case_id=case_id,
            outline_result=outline_result,
            step_run_id=sibling_job.step_run_id,
            monkeypatch=monkeypatch,
            worker_prefix="worker-sibling",
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
        # Sibling lane enqueued Audit; parent command remains queued
        assert parent_row.status == "queued"

        await _complete_healthy_lane_from_audit(
            session,
            case_id=case_id,
            outline_result=outline_result,
            step_run_id=job2.step_run_id,
            monkeypatch=monkeypatch,
            worker_prefix="worker-2",
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


@pytest.mark.asyncio
async def test_f4_review_vi_pass_en_fail_retry_converges(
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

        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        vi_lane = next(lane for lane in progress.lanes if lane.locale == "vi-VN")
        en_lane = next(lane for lane in progress.lanes if lane.locale == "en")
        assert vi_lane.review.job is not None
        assert en_lane.review.job is not None

        # 1. Claim both review jobs
        job1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-vi"
        )
        job2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-en"
        )
        assert job1 is not None and job2 is not None
        vi_job = job1 if job1.id == vi_lane.review.job.id else job2
        en_job = job2 if job1.id == vi_lane.review.job.id else job1

        registry = AgentRunnerRegistry()

        # 2. VI Review succeeds
        assert vi_job.lease_owner is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=vi_job.id,
            worker_id=cast(str, vi_job.lease_owner),
            runner_registry=registry,
        )

        # Verify VI Audit is enqueued
        progress_after_vi = await get_quality_progress(
            session, content_case_id=case_id, source_run_id=None
        )
        assert progress_after_vi is not None
        vi_lane_after = next(lane for lane in progress_after_vi.lanes if lane.locale == "vi-VN")
        assert vi_lane_after.audit.step is not None
        assert vi_lane_after.audit.job is not None
        assert vi_lane_after.audit.job.status == "queued"

        # 3. EN Review fails technically (attempt 1)
        assert en_job.lease_owner is not None
        await operator_quality_worker.fail_quality_job(
            session,
            job_id=en_job.id,
            worker_id=cast(str, en_job.lease_owner),
            failure_class="network_timeout",
            message="EN Review timeout",
        )

        # 4. Healthy VI lane continues through Audit and Source-copy
        await _complete_healthy_lane_from_audit(
            session,
            case_id=case_id,
            outline_result=outline_result,
            step_run_id=vi_job.step_run_id,
            monkeypatch=monkeypatch,
            worker_prefix="worker-vi",
            runner_registry=registry,
        )

        # After VI finishes, no active jobs remain, command settled failed
        parent_row = await session.get(OperatorCommand, parent_cmd.command_id)
        assert parent_row is not None
        assert parent_row.status == "failed"
        assert parent_row.error_code == "operator_quality_job_failed"

        state_after_fail = await get_operator_state(session, content_case_id=case_id)
        assert state_after_fail.status == "BLOCKED"
        assert state_after_fail.primary_intent == "retry"
        assert state_after_fail.allowed_intents == ["retry"]

        # Verify VI Review did NOT rerun (only 1 StepRun for VI review)
        vi_review_steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == vi_lane.writer.run.id,
                        StepRun.step_key == QUALITY_REVIEW_TASK_KEYS["vi-VN"],
                    )
                )
            ).all()
        )
        assert len(vi_review_steps) == 1

        # 5. Retry EN
        retry_action = await resolve_next_operator_action(session, content_case_id=case_id)
        assert retry_action.action_key == "writers_to_quality"
        assert retry_action.intent == "retry"
        assert retry_action.executable is True

        retry_cmd = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="retry",
            expected_state_version=retry_action.state_version,
            idempotency_key="f4-retry-en-review-case1",
        )
        assert retry_cmd.status == "queued"

        # Verify EN Review attempt 2 was enqueued
        en_review_steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == en_lane.writer.run.id,
                        StepRun.step_key == QUALITY_REVIEW_TASK_KEYS["en"],
                    )
                )
            ).all()
        )
        assert len(en_review_steps) == 2
        assert en_review_steps[-1].attempt == 2

        # VI review steps still 1
        vi_review_steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == vi_lane.writer.run.id,
                        StepRun.step_key == QUALITY_REVIEW_TASK_KEYS["vi-VN"],
                    )
                )
            ).all()
        )
        assert len(vi_review_steps) == 1

        # 6. Execute EN Review attempt 2 -> PASS
        en_retry_job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-en-retry"
        )
        assert en_retry_job is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=en_retry_job.id,
            worker_id="worker-en-retry",
            runner_registry=registry,
        )

        # 7. Complete EN through Audit and Source-copy
        await _complete_healthy_lane_from_audit(
            session,
            case_id=case_id,
            outline_result=outline_result,
            step_run_id=en_retry_job.step_run_id,
            monkeypatch=monkeypatch,
            worker_prefix="worker-en-audit-source",
            runner_registry=registry,
        )

        # 8. Verify both converge to final_gate_ready without hanging
        final_progress = await get_quality_progress(
            session, content_case_id=case_id, source_run_id=None
        )
        assert final_progress is not None
        assert final_progress.final_gate_ready is True
        assert {lane.status for lane in final_progress.lanes} == {"final_gate_ready"}

        retry_row = await session.get(OperatorCommand, retry_cmd.command_id)
        assert retry_row is not None
        assert retry_row.status == "completed"

        final_state = await get_operator_state(session, content_case_id=case_id)
        assert final_state.status == "AWAITING_APPROVAL"
        assert final_state.human_gate == "final_review"


@pytest.mark.asyncio
async def test_f4_audit_vi_pass_en_fail_retry_converges(
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

        registry = AgentRunnerRegistry()

        # 1. Both reviews execute and succeed
        job1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-rev-1"
        )
        job2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-rev-2"
        )
        assert job1 is not None and job2 is not None
        await operator_quality_worker.execute_quality_job(
            session, job_id=job1.id, worker_id="worker-rev-1", runner_registry=registry
        )
        await operator_quality_worker.execute_quality_job(
            session, job_id=job2.id, worker_id="worker-rev-2", runner_registry=registry
        )

        # Now both VI and EN Audit are queued
        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        vi_lane = next(lane for lane in progress.lanes if lane.locale == "vi-VN")
        en_lane = next(lane for lane in progress.lanes if lane.locale == "en")
        assert vi_lane.audit.job is not None
        assert en_lane.audit.job is not None

        # Setup audit port mock
        async def fake_audit_port(
            _session: AsyncSession, *, locale: str, **kwargs: object
        ) -> _CapturePort:
            del _session, kwargs
            prog = await get_quality_progress(
                session, content_case_id=case_id, source_run_id=None
            )
            assert prog is not None
            lane = next(candidate for candidate in prog.lanes if candidate.locale == locale)
            assert lane.revised_draft is not None
            audit_input = await load_assertion_audit_input(
                session,
                writer_run_id=lane.writer.run.id,
                revised_draft_artifact_id=lane.revised_draft.id,
                expected_revised_draft_version=lane.revised_draft.version,
                expected_revised_draft_hash=lane.revised_draft.content_hash,
                outline_artifact_id=outline_result.artifact.id,
                expected_outline_version=outline_result.artifact.version,
                expected_outline_hash=outline_result.artifact.content_hash,
                locale=lane.locale,
            )
            return _CapturePort(_passing_output(audit_input))

        monkeypatch.setattr(
            operator_quality_worker, "create_cli_assertion_audit_model_port", fake_audit_port
        )

        # Claim both audit jobs
        ajob1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-aud-1"
        )
        ajob2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-aud-2"
        )
        assert ajob1 is not None and ajob2 is not None
        vi_audit_job = ajob1 if ajob1.id == vi_lane.audit.job.id else ajob2
        en_audit_job = ajob2 if ajob1.id == vi_lane.audit.job.id else ajob1

        # 2. VI Audit PASS -> execute it
        assert vi_audit_job.lease_owner is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=vi_audit_job.id,
            worker_id=cast(str, vi_audit_job.lease_owner),
            runner_registry=registry,
        )

        # Verify VI Source-copy is enqueued
        progress_after_vi_audit = await get_quality_progress(
            session, content_case_id=case_id, source_run_id=None
        )
        assert progress_after_vi_audit is not None
        vi_lane_after = next(
            lane for lane in progress_after_vi_audit.lanes if lane.locale == "vi-VN"
        )
        assert vi_lane_after.source_copy.job is not None
        assert vi_lane_after.source_copy.job.status == "queued"

        # 3. EN Audit fails technically
        assert en_audit_job.lease_owner is not None
        await operator_quality_worker.fail_quality_job(
            session,
            job_id=en_audit_job.id,
            worker_id=cast(str, en_audit_job.lease_owner),
            failure_class="network_timeout",
            message="EN Audit timeout",
        )

        # 4. VI Source-copy executes and passes
        vi_source_job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-sc-vi"
        )
        assert vi_source_job is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=vi_source_job.id,
            worker_id="worker-sc-vi",
            runner_registry=registry,
        )
        await _complete_readiness_lane(
            session,
            case_id=case_id,
            locale="vi-VN",
            monkeypatch=monkeypatch,
            runner_registry=registry,
            worker_prefix="worker-sc-vi-readiness",
        )

        # Now VI is qualified, EN Audit failed, no active jobs remain -> command failed
        parent_row = await session.get(OperatorCommand, parent_cmd.command_id)
        assert parent_row is not None
        assert parent_row.status == "failed"
        assert parent_row.error_code == "operator_quality_job_failed"

        # Verify VI Audit was NOT rerun
        vi_audit_steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.step_key == QUALITY_AUDIT_TASK_KEYS["vi-VN"],
                    )
                )
            ).all()
        )
        assert len(vi_audit_steps) == 1

        # 5. Retry EN Audit
        retry_action = await resolve_next_operator_action(session, content_case_id=case_id)
        assert retry_action.intent == "retry"
        assert retry_action.executable is True

        retry_cmd = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="retry",
            expected_state_version=retry_action.state_version,
            idempotency_key="f4-retry-en-audit-case2",
        )
        assert retry_cmd.status == "queued"

        # 6. Execute EN Audit retry -> PASS
        en_audit_retry_job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-en-aud-retry"
        )
        assert en_audit_retry_job is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=en_audit_retry_job.id,
            worker_id="worker-en-aud-retry",
            runner_registry=registry,
        )

        # 7. Execute EN Source-copy -> PASS
        en_source_job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-en-sc"
        )
        assert en_source_job is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=en_source_job.id,
            worker_id="worker-en-sc",
            runner_registry=registry,
        )

        # 8. Verify both converge to final_gate_ready
        final_progress = await get_quality_progress(
            session, content_case_id=case_id, source_run_id=None
        )
        assert final_progress is not None
        assert final_progress.final_gate_ready is True

        retry_row = await session.get(OperatorCommand, retry_cmd.command_id)
        assert retry_row is not None
        assert retry_row.status == "completed"

        final_state = await get_operator_state(session, content_case_id=case_id)
        assert final_state.status == "AWAITING_APPROVAL"
        assert final_state.human_gate == "final_review"


@pytest.mark.asyncio
async def test_f4_review_bounded_two_attempts_exhausted(
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

        registry = AgentRunnerRegistry()

        job1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-b1"
        )
        job2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-b2"
        )
        assert job1 is not None and job2 is not None

        # Sibling job (job2) completes to qualified so it has no active jobs
        await operator_quality_worker.execute_quality_job(
            session, job_id=job2.id, worker_id="worker-b2", runner_registry=registry
        )
        await _complete_healthy_lane_from_audit(
            session,
            case_id=case_id,
            outline_result=outline_result,
            step_run_id=job2.step_run_id,
            monkeypatch=monkeypatch,
            worker_prefix="worker-b2",
            runner_registry=registry,
        )

        # Target job (job1) fails attempt 1
        await operator_quality_worker.fail_quality_job(
            session,
            job_id=job1.id,
            worker_id="worker-b1",
            failure_class="network_timeout",
            message="Review attempt 1 timeout",
        )

        # Command settled failed
        parent_row = await session.get(OperatorCommand, parent_cmd.command_id)
        assert parent_row is not None
        assert parent_row.status == "failed"
        assert parent_row.error_code == "operator_quality_job_failed"

        state_after_1 = await get_operator_state(session, content_case_id=case_id)
        assert state_after_1.status == "BLOCKED"
        assert state_after_1.primary_intent == "retry"
        assert state_after_1.allowed_intents == ["retry"]

        action_1 = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action_1.executable is True
        assert action_1.intent == "retry"

        # Submit retry attempt 1 (creates attempt 2)
        retry_cmd = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="retry",
            expected_state_version=action_1.state_version,
            idempotency_key="f4-retry-attempt-2-case3",
        )
        assert retry_cmd.status == "queued"

        # Target lane has StepRun with attempt=2
        target_step_1 = await session.get(StepRun, job1.step_run_id)
        assert target_step_1 is not None
        target_steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == target_step_1.run_id,
                        StepRun.step_key == target_step_1.step_key,
                    ).order_by(StepRun.attempt)
                )
            ).all()
        )
        assert len(target_steps) == 2
        assert [s.attempt for s in target_steps] == [1, 2]

        # Claim attempt 2 job
        job_attempt_2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-attempt-2"
        )
        assert job_attempt_2 is not None
        assert job_attempt_2.step_run_id == target_steps[1].id

        # Fail attempt 2
        await operator_quality_worker.fail_quality_job(
            session,
            job_id=job_attempt_2.id,
            worker_id="worker-attempt-2",
            failure_class="network_timeout",
            message="Review attempt 2 timeout",
        )

        # Settle state after attempt 2 failure: exhausted!
        retry_row = await session.get(OperatorCommand, retry_cmd.command_id)
        assert retry_row is not None
        assert retry_row.status == "failed"
        assert retry_row.error_code == "operator_quality_retry_exhausted"

        state_after_2 = await get_operator_state(session, content_case_id=case_id)
        assert state_after_2.status == "BLOCKED"
        assert state_after_2.primary_intent is None
        assert state_after_2.allowed_intents == []
        assert state_after_2.blocker_code == "operator_quality_retry_exhausted"

        action_2 = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action_2.executable is False
        assert action_2.intent is None

        # Verify exactly 2 StepRuns for review (no attempt 3)
        target_steps_after = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == target_step_1.run_id,
                        StepRun.step_key == target_step_1.step_key,
                    ).order_by(StepRun.attempt)
                )
            ).all()
        )
        assert len(target_steps_after) == 2
        assert [s.attempt for s in target_steps_after] == [1, 2]

        # Try retry again -> fail closed
        with pytest.raises(OperatorControlError) as exc_info:
            await submit_operator_command(
                session,
                content_case_id=case_id,
                intent="retry",
                expected_state_version=state_after_2.state_version,
                idempotency_key="f4-retry-attempt-3-forbidden",
            )
        assert exc_info.value.code in {
            "operator_quality_retry_requires_failed_job",
            "operator_quality_retry_exhausted",
        }

        # Assert StepRuns and Jobs did not increase
        target_steps_final = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == target_step_1.run_id,
                        StepRun.step_key == target_step_1.step_key,
                    )
                )
            ).all()
        )
        assert len(target_steps_final) == 2

        all_target_jobs = list(
            (
                await session.scalars(
                    select(Job).where(
                        Job.step_run_id.in_([s.id for s in target_steps_final])
                    )
                )
            ).all()
        )
        assert len(all_target_jobs) == 2


@pytest.mark.asyncio
async def test_f4_r2_audit_exact_lineage_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement C.1: Audit exact lineage retry exhaustion after 2 attempts."""
    async with isolated_session() as session:
        fixture, writer_outputs, outline_result = await _complete_f3_writers(session)
        case_id = fixture.run.content_case_id
        parent_cmd, before_quality = await _dispatch_quality(session, fixture=fixture)
        del parent_cmd, before_quality

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

        registry = AgentRunnerRegistry()

        job1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-aud-rev1"
        )
        job2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-aud-rev2"
        )
        assert job1 is not None and job2 is not None
        await operator_quality_worker.execute_quality_job(
            session, job_id=job1.id, worker_id="worker-aud-rev1", runner_registry=registry
        )
        await operator_quality_worker.execute_quality_job(
            session, job_id=job2.id, worker_id="worker-aud-rev2", runner_registry=registry
        )

        await _complete_healthy_lane_from_audit(
            session,
            case_id=case_id,
            outline_result=outline_result,
            step_run_id=job2.step_run_id,
            monkeypatch=monkeypatch,
            worker_prefix="worker-aud-sib",
            runner_registry=registry,
        )

        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        target_step_run_id = job1.step_run_id
        target_lane = next(
            lane
            for lane in progress.lanes
            if lane.review.step is not None and lane.review.step.id == target_step_run_id
        )
        assert target_lane.audit.job is not None
        target_audit_job_id = target_lane.audit.job.id

        audit_job_1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-audit-att1"
        )
        assert audit_job_1 is not None
        assert audit_job_1.id == target_audit_job_id

        await operator_quality_worker.fail_quality_job(
            session,
            job_id=audit_job_1.id,
            worker_id="worker-audit-att1",
            failure_class="network_timeout",
            message="Audit attempt 1 worker crashed",
        )

        progress_1 = await get_quality_progress(
            session, content_case_id=case_id, source_run_id=None
        )
        assert progress_1 is not None
        target_lane_1 = next(lane for lane in progress_1.lanes if lane.locale == target_lane.locale)
        assert target_lane_1.status == "execution_failed_retryable"
        assert target_lane_1.audit.attempt == 1

        state_1 = await get_operator_state(session, content_case_id=case_id)
        assert state_1.status == "BLOCKED"
        assert state_1.primary_intent == "retry"
        assert state_1.allowed_intents == ["retry"]

        action_1 = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action_1.executable is True
        assert action_1.intent == "retry"

        retry_cmd = await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="retry",
            expected_state_version=action_1.state_version,
            idempotency_key="f4-r2-audit-retry-1",
        )
        assert retry_cmd.status == "queued"

        audit_job_2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-audit-att2"
        )
        assert audit_job_2 is not None
        assert audit_job_2.id != audit_job_1.id

        await operator_quality_worker.fail_quality_job(
            session,
            job_id=audit_job_2.id,
            worker_id="worker-audit-att2",
            failure_class="database_connection_lost",
            message="Audit attempt 2 DB lost",
        )

        progress_2 = await get_quality_progress(
            session, content_case_id=case_id, source_run_id=None
        )
        assert progress_2 is not None
        target_lane_2 = next(lane for lane in progress_2.lanes if lane.locale == target_lane.locale)
        assert target_lane_2.status == "execution_failed_exhausted"
        assert target_lane_2.audit.attempt == 2
        assert target_lane_2.audit.run is not None
        assert target_lane_2.audit.run.failure_code == "operator_quality_retry_exhausted"

        state_2 = await get_operator_state(session, content_case_id=case_id)
        assert state_2.status == "BLOCKED"
        assert state_2.primary_intent is None
        assert state_2.allowed_intents == []
        assert state_2.blocker_code == "operator_quality_retry_exhausted"

        action_2 = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action_2.executable is False
        assert action_2.intent is None

        with pytest.raises(OperatorControlError) as exc_info:
            await submit_operator_command(
                session,
                content_case_id=case_id,
                intent="retry",
                expected_state_version=state_2.state_version,
                idempotency_key="f4-r2-audit-retry-3-forbidden",
            )
        assert exc_info.value.code in {
            "operator_quality_retry_requires_failed_job",
            "operator_quality_retry_exhausted",
        }

        audit_handoff = target_lane_2.audit.handoff
        assert audit_handoff is not None
        matching_runs = list(
            (
                await session.scalars(
                    select(ContentRun.id)
                    .join(Artifact, Artifact.run_id == ContentRun.id)
                    .where(
                        Artifact.artifact_type == "assertion_audit_handoff",
                        Artifact.content_hash == audit_handoff.content_hash,
                    )
                )
            ).all()
        )
        assert len(matching_runs) == 2


@pytest.mark.asyncio
async def test_f4_r2_unrelated_historical_audit_does_not_consume_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement C.2: Historical audit for another draft does not consume budget."""
    async with isolated_session() as session:
        fixture, writer_outputs, outline_result = await _complete_f3_writers(session)
        case_id = fixture.run.content_case_id
        parent_cmd, before_quality = await _dispatch_quality(session, fixture=fixture)
        del parent_cmd, before_quality

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

        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        vi_lane = next(lane for lane in progress.lanes if lane.locale == "vi-VN")
        en_lane = next(lane for lane in progress.lanes if lane.locale == "en")
        assert vi_lane.review.job is not None
        assert en_lane.review.job is not None

        registry = AgentRunnerRegistry()

        job1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-hist-rev1"
        )
        job2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-hist-rev2"
        )
        assert job1 is not None and job2 is not None
        vi_job = job1 if job1.id == vi_lane.review.job.id else job2
        en_job = job2 if job1.id == vi_lane.review.job.id else job1

        await operator_quality_worker.execute_quality_job(
            session,
            job_id=vi_job.id,
            worker_id=cast(str, vi_job.lease_owner),
            runner_registry=registry,
        )
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=en_job.id,
            worker_id=cast(str, en_job.lease_owner),
            runner_registry=registry,
        )

        await _complete_healthy_lane_from_audit(
            session,
            case_id=case_id,
            outline_result=outline_result,
            step_run_id=en_job.step_run_id,
            monkeypatch=monkeypatch,
            worker_prefix="worker-hist-sib",
            runner_registry=registry,
        )

        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        target_lane = next(lane for lane in progress.lanes if lane.locale == "vi-VN")
        assert target_lane.writer.run is not None
        writer_run = target_lane.writer.run
        assert target_lane.audit.job is not None

        historical_run = ContentRun(
            project_id=writer_run.project_id,
            content_case_id=case_id,
            locale_variant_id=target_lane.variant.id,
            run_mode="eval",
            current_step="audit_vi_draft",
            status="failed",
            failure_code="operator_quality_retry_exhausted",
            settings_snapshot_id=writer_run.settings_snapshot_id,
            started_at=utc_now() - timedelta(hours=2),
            completed_at=utc_now() - timedelta(hours=2),
        )
        session.add(historical_run)
        await session.flush()

        historical_handoff = Artifact(
            run_id=historical_run.id,
            artifact_type="assertion_audit_handoff",
            locale="vi-VN",
            version=1,
            content_json={
                "task_key": "audit_vi_draft",
                "source_writer_run": {"id": str(writer_run.id), "run_mode": "localize"},
                "source_draft": {"id": str(uuid4()), "version": 1, "content_hash": "x" * 64},
            },
            content_hash="historical-handoff-hash-x",
        )
        session.add(historical_handoff)
        await session.flush()

        audit_job_1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-audit-y1"
        )
        assert audit_job_1 is not None
        assert audit_job_1.id == target_lane.audit.job.id

        await operator_quality_worker.fail_quality_job(
            session,
            job_id=audit_job_1.id,
            worker_id="worker-audit-y1",
            failure_class="network_timeout",
            message="Draft Y Audit attempt 1 timeout",
        )

        progress_after = await get_quality_progress(
            session, content_case_id=case_id, source_run_id=None
        )
        assert progress_after is not None
        lane_after = next(lane for lane in progress_after.lanes if lane.locale == "vi-VN")
        assert lane_after.status == "execution_failed_retryable"
        assert lane_after.audit.attempt == 1
        assert lane_after.audit.run is not None
        assert lane_after.audit.run.failure_code == "network_timeout"

        state = await get_operator_state(session, content_case_id=case_id)
        assert state.status == "BLOCKED"
        assert state.primary_intent == "retry"
        assert state.allowed_intents == ["retry"]

        action = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action.executable is True
        assert action.intent == "retry"


@pytest.mark.asyncio
async def test_f4_r2_deterministic_terminal_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement C.3: Deterministic terminal attempt selection independently of DB row order."""
    async with isolated_session() as session:
        fixture, writer_outputs, outline_result = await _complete_f3_writers(session)
        case_id = fixture.run.content_case_id
        parent_cmd, before_quality = await _dispatch_quality(session, fixture=fixture)
        del parent_cmd, before_quality

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

        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        vi_lane = next(lane for lane in progress.lanes if lane.locale == "vi-VN")
        en_lane = next(lane for lane in progress.lanes if lane.locale == "en")
        assert vi_lane.review.job is not None
        assert en_lane.review.job is not None

        registry = AgentRunnerRegistry()

        job1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-det-rev1"
        )
        job2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-det-rev2"
        )
        assert job1 is not None and job2 is not None
        vi_job = job1 if job1.id == vi_lane.review.job.id else job2
        en_job = job2 if job1.id == vi_lane.review.job.id else job1

        await operator_quality_worker.execute_quality_job(
            session,
            job_id=vi_job.id,
            worker_id=cast(str, vi_job.lease_owner),
            runner_registry=registry,
        )
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=en_job.id,
            worker_id=cast(str, en_job.lease_owner),
            runner_registry=registry,
        )

        await _complete_healthy_lane_from_audit(
            session,
            case_id=case_id,
            outline_result=outline_result,
            step_run_id=en_job.step_run_id,
            monkeypatch=monkeypatch,
            worker_prefix="worker-det-sib",
            runner_registry=registry,
        )

        audit_job_1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-det-a1"
        )
        assert audit_job_1 is not None
        await operator_quality_worker.fail_quality_job(
            session,
            job_id=audit_job_1.id,
            worker_id="worker-det-a1",
            failure_class="network_timeout",
            message="Attempt 1 timeout",
        )

        action_1 = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action_1.executable is True
        await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="retry",
            expected_state_version=action_1.state_version,
            idempotency_key="f4-r2-det-retry-1",
        )

        audit_job_2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-det-a2"
        )
        assert audit_job_2 is not None
        await operator_quality_worker.fail_quality_job(
            session,
            job_id=audit_job_2.id,
            worker_id="worker-det-a2",
            failure_class="network_timeout",
            message="Attempt 2 timeout",
        )

        real_scalars = session.scalars

        async def inverted_scalars(
            statement: object, *args: object, **kwargs: object
        ) -> object:
            result = await real_scalars(statement, *args, **kwargs)
            stmt_str = str(statement)
            if "assertion_audit_handoff" in stmt_str:
                all_items = list(result.all())
                all_items.reverse()

                class _InvertedResult:
                    def all(self) -> list[object]:
                        return all_items

                return _InvertedResult()
            return result

        monkeypatch.setattr(session, "scalars", inverted_scalars)

        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        vi_lane = next(lane for lane in progress.lanes if lane.locale == "vi-VN")
        assert vi_lane.status == "execution_failed_exhausted"
        assert vi_lane.audit.attempt == 2
        assert vi_lane.audit.run is not None
        assert vi_lane.audit.run.id == audit_job_2.run_id
        assert vi_lane.audit.run.failure_code == "operator_quality_retry_exhausted"


@pytest.mark.asyncio
async def test_f4_r2_source_copy_exact_lineage_budget_and_historical_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement C.4: Source-copy exact lineage retry budget=2 and historical isolation."""
    async with isolated_session() as session:
        fixture, writer_outputs, outline_result = await _complete_f3_writers(session)
        case_id = fixture.run.content_case_id
        parent_cmd, before_quality = await _dispatch_quality(session, fixture=fixture)
        del parent_cmd, before_quality

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

        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        vi_lane = next(lane for lane in progress.lanes if lane.locale == "vi-VN")
        en_lane = next(lane for lane in progress.lanes if lane.locale == "en")
        assert vi_lane.review.job is not None
        assert en_lane.review.job is not None

        registry = AgentRunnerRegistry()

        job1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-sc-rev1"
        )
        job2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-sc-rev2"
        )
        assert job1 is not None and job2 is not None
        vi_job = job1 if job1.id == vi_lane.review.job.id else job2
        en_job = job2 if job1.id == vi_lane.review.job.id else job1

        await operator_quality_worker.execute_quality_job(
            session,
            job_id=vi_job.id,
            worker_id=cast(str, vi_job.lease_owner),
            runner_registry=registry,
        )
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=en_job.id,
            worker_id=cast(str, en_job.lease_owner),
            runner_registry=registry,
        )

        await _complete_healthy_lane_from_audit(
            session,
            case_id=case_id,
            outline_result=outline_result,
            step_run_id=en_job.step_run_id,
            monkeypatch=monkeypatch,
            worker_prefix="worker-sc-sib",
            runner_registry=registry,
        )

        progress = await get_quality_progress(session, content_case_id=case_id, source_run_id=None)
        assert progress is not None
        vi_lane = next(lane for lane in progress.lanes if lane.locale == "vi-VN")
        assert vi_lane.revised_draft is not None
        audit_input = await load_assertion_audit_input(
            session,
            writer_run_id=vi_lane.writer.run.id,  # type: ignore[union-attr]
            revised_draft_artifact_id=vi_lane.revised_draft.id,
            expected_revised_draft_version=vi_lane.revised_draft.version,
            expected_revised_draft_hash=vi_lane.revised_draft.content_hash,
            outline_artifact_id=outline_result.artifact.id,  # type: ignore[union-attr]
            expected_outline_version=outline_result.artifact.version,  # type: ignore[union-attr]
            expected_outline_hash=outline_result.artifact.content_hash,  # type: ignore[union-attr]
            locale="vi-VN",
        )

        async def _fake_audit_port(_s: AsyncSession, *, locale: str, **kw: object) -> _CapturePort:
            del _s, locale, kw
            return _CapturePort(_passing_output(audit_input))

        monkeypatch.setattr(
            operator_quality_worker, "create_cli_assertion_audit_model_port", _fake_audit_port
        )

        vi_audit_job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-sc-audit"
        )
        assert vi_audit_job is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=vi_audit_job.id,
            worker_id="worker-sc-audit",
            runner_registry=registry,
        )

        progress_after_audit = await get_quality_progress(
            session, content_case_id=case_id, source_run_id=None
        )
        assert progress_after_audit is not None
        vi_lane_sc = next(lane for lane in progress_after_audit.lanes if lane.locale == "vi-VN")
        assert vi_lane_sc.source_copy.job is not None
        sc_job_1_id = vi_lane_sc.source_copy.job.id

        historical_sc_run = ContentRun(
            project_id=vi_lane_sc.writer.run.project_id,  # type: ignore[union-attr]
            content_case_id=case_id,
            locale_variant_id=vi_lane_sc.variant.id,
            run_mode="eval",
            current_step="source_copy_vi_draft",
            status="failed",
            failure_code="operator_quality_retry_exhausted",
            settings_snapshot_id=vi_lane_sc.writer.run.settings_snapshot_id,  # type: ignore[union-attr]
            started_at=utc_now() - timedelta(hours=3),
            completed_at=utc_now() - timedelta(hours=3),
        )
        session.add(historical_sc_run)
        await session.flush()

        historical_sc_handoff = Artifact(
            run_id=historical_sc_run.id,
            artifact_type="source_copy_handoff",
            locale="vi-VN",
            version=1,
            content_json={
                "task_key": "source_copy_vi_draft",
                "source_writer_run_id": str(vi_lane_sc.writer.run.id),  # type: ignore[union-attr]
                "source_draft": {"id": str(uuid4()), "version": 1, "content_hash": "y" * 64},
                "assertion_audit": {
                    "artifact": {"id": str(uuid4()), "version": 1, "content_hash": "z" * 64},
                    "quality_evaluation_id": str(uuid4()),
                },
            },
            content_hash="historical-sc-handoff-hash",
        )
        session.add(historical_sc_handoff)
        await session.flush()

        sc_job_1 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-sc-att1"
        )
        assert sc_job_1 is not None
        assert sc_job_1.id == sc_job_1_id

        await operator_quality_worker.fail_quality_job(
            session,
            job_id=sc_job_1.id,
            worker_id="worker-sc-att1",
            failure_class="process_timeout",
            message="Source-copy attempt 1 timeout",
        )

        progress_sc_1 = await get_quality_progress(
            session, content_case_id=case_id, source_run_id=None
        )
        assert progress_sc_1 is not None
        vi_lane_sc_1 = next(lane for lane in progress_sc_1.lanes if lane.locale == "vi-VN")
        assert vi_lane_sc_1.status == "execution_failed_retryable"
        assert vi_lane_sc_1.source_copy.attempt == 1

        state_sc_1 = await get_operator_state(session, content_case_id=case_id)
        assert state_sc_1.status == "BLOCKED"
        assert state_sc_1.allowed_intents == ["retry"]

        action_sc_1 = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action_sc_1.executable is True

        await submit_operator_command(
            session,
            content_case_id=case_id,
            intent="retry",
            expected_state_version=action_sc_1.state_version,
            idempotency_key="f4-r2-sc-retry-1",
        )

        sc_job_2 = await operator_quality_worker.claim_or_reclaim_quality_job(
            session, worker_id="worker-sc-att2"
        )
        assert sc_job_2 is not None
        assert sc_job_2.id != sc_job_1.id

        await operator_quality_worker.fail_quality_job(
            session,
            job_id=sc_job_2.id,
            worker_id="worker-sc-att2",
            failure_class="database_error",
            message="Source-copy attempt 2 error",
        )

        progress_sc_2 = await get_quality_progress(
            session, content_case_id=case_id, source_run_id=None
        )
        assert progress_sc_2 is not None
        vi_lane_sc_2 = next(lane for lane in progress_sc_2.lanes if lane.locale == "vi-VN")
        assert vi_lane_sc_2.status == "execution_failed_exhausted"
        assert vi_lane_sc_2.source_copy.attempt == 2
        assert vi_lane_sc_2.source_copy.run is not None
        assert vi_lane_sc_2.source_copy.run.failure_code == "operator_quality_retry_exhausted"

        state_sc_2 = await get_operator_state(session, content_case_id=case_id)
        assert state_sc_2.status == "BLOCKED"
        assert state_sc_2.allowed_intents == []
        assert state_sc_2.blocker_code == "operator_quality_retry_exhausted"

        action_sc_2 = await resolve_next_operator_action(session, content_case_id=case_id)
        assert action_sc_2.executable is False

        with pytest.raises(OperatorControlError) as exc_info:
            await submit_operator_command(
                session,
                content_case_id=case_id,
                intent="retry",
                expected_state_version=state_sc_2.state_version,
                idempotency_key="f4-r2-sc-retry-3-forbidden",
            )
        assert exc_info.value.code in {
            "operator_quality_retry_requires_failed_job",
            "operator_quality_retry_exhausted",
        }