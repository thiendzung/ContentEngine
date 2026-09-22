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
from app.modules.content_engine.journal.quality_readiness import (
    READER_VALUE_TASK_KEYS,
    READINESS_CRITERIA,
    READINESS_HANDOFF_TYPES,
)
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


class _ReadinessCapturePort(_CapturePort):
    def __init__(self, output: object, *, stage: str) -> None:
        super().__init__(output)
        self.stage = stage

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        assert input_bundle.get("stage") == self.stage
        assert isinstance(input_bundle.get("approved_angle"), dict)
        originality_pack = input_bundle.get("originality_pack")
        assert isinstance(originality_pack, dict)
        assert isinstance(originality_pack.get("items"), list)
        assert originality_pack["items"]
        if self.stage == "search_ai":
            assert isinstance(input_bundle.get("reader_value"), dict)
        else:
            assert "reader_value" not in input_bundle
        return await super().generate(input_bundle=input_bundle, attempt=attempt)


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
        return _ReadinessCapturePort(
            _passing_readiness_output(stage, locale),
            stage=stage,
        )

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