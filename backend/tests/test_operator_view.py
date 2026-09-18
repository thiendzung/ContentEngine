from __future__ import annotations

import pytest
from sqlalchemy import select
from test_ce05_review_revise import isolated_session
from test_operator_quality import _complete_f3_writers
from test_operator_start_to_angle import (
    ControlledCodexRunner,
    ControlledEvidenceWorkflow,
    _activate_seeded_angle_runtime,
    _intake_kwargs,
    _ready_preflight,
)

import app.modules.content_engine.journal.operator_vertical_slice as vertical_slice
from app.modules.content_engine.journal.models import AngleApproval
from app.modules.content_engine.journal.operator_decisions import submit_operator_decision
from app.modules.content_engine.journal.operator_manual_intake import (
    create_founder_journal_intake,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    get_operator_state_v45,
    submit_operator_command_v45,
)
from app.modules.content_engine.journal.operator_view import get_operator_case_view
from app.modules.content_engine.journal.operator_worker import (
    claim_next_operator_job,
    execute_start_to_angle_job,
)
from app.modules.content_engine.journal.production_board import list_production_board_cases
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import Artifact, ContentRun, StepRun
from app.modules.harness.persistence import (
    create_checkpoint,
    transition_run,
    transition_step_run,
)


@pytest.mark.asyncio
async def test_operator_view_projects_ready_intake_without_inventing_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vertical_slice,
        "build_journal_operator_preflight",
        _ready_preflight,
    )
    async with isolated_session() as session:
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="ui01-ready-view"),
        )
        view = await get_operator_case_view(
            session,
            content_case_id=created.content_case_id,
        )
        assert view.state.status == "READY"
        assert view.state.primary_intent == "start"
        assert view.pending_gate is None
        assert view.intake.source_locale == "en"
        assert view.intake.research_country == "vn"
        assert [(item.locale, item.role) for item in view.intake.required_locales] == [
            ("en", "source"),
            ("vi-VN", "translation"),
        ]
        board = await list_production_board_cases(session)
        board_row = next(item for item in board if item.id == created.content_case_id)
        assert board_row.operator_managed is True


@pytest.mark.asyncio
async def test_operator_view_projects_writer_lanes_before_quality_dispatch() -> None:
    async with isolated_session() as session:
        fixture, _outputs, _outline = await _complete_f3_writers(session)
        view = await get_operator_case_view(
            session,
            content_case_id=fixture.run.content_case_id,
        )

        assert view.state.status == "READY"
        assert view.state.primary_intent == "continue"
        assert {lane.required_locale for lane in view.writer_lanes} == {"en", "vi-VN"}
        assert all(lane.status == "completed" for lane in view.writer_lanes)
        assert all(lane.run_id is not None for lane in view.writer_lanes)
        assert all(lane.draft_artifact_id is not None for lane in view.writer_lanes)
        assert all(lane.draft_hash is not None for lane in view.writer_lanes)
        assert view.quality_lanes == []


@pytest.mark.asyncio
async def test_operator_view_returns_revalidated_exact_angle_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vertical_slice,
        "build_journal_operator_preflight",
        _ready_preflight,
    )
    async with isolated_session() as session:
        await _activate_seeded_angle_runtime(session)
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="ui01-angle-view"),
        )
        state = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="ui01-angle-view-start",
        )
        assert queued.job_id is not None
        leased = await claim_next_operator_job(
            session,
            worker_id="worker-ui01-view",
        )
        assert leased is not None
        runner = ControlledCodexRunner()
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", runner)
        result = await execute_start_to_angle_job(
            session,
            job_id=leased.id,
            worker_id="worker-ui01-view",
            evidence_workflow=ControlledEvidenceWorkflow(),  # type: ignore[arg-type]
            runner_registry=registry,
        )
        exact_artifact = await session.get(Artifact, result.angle_artifact_id)
        assert exact_artifact is not None and exact_artifact.content_json is not None
        stray = Artifact(
            run_id=exact_artifact.run_id,
            step_run_id=exact_artifact.step_run_id,
            artifact_type="angle_candidates",
            locale=exact_artifact.locale,
            version=exact_artifact.version + 100,
            content_json=exact_artifact.content_json,
            content_hash=exact_artifact.content_hash,
        )
        session.add(stray)
        await session.flush()

        view = await get_operator_case_view(
            session,
            content_case_id=created.content_case_id,
        )
        assert view.state.status == "AWAITING_APPROVAL"
        assert view.state.human_gate == "angle"
        assert view.pending_gate is not None
        assert view.pending_gate.type == "angle"
        assert view.pending_gate.artifact.id == result.angle_artifact_id
        assert view.pending_gate.artifact.id != stray.id
        assert view.pending_gate.artifact.content_hash == result.angle_artifact_hash
        assert len(view.pending_gate.candidates) == 3
        for item in view.pending_gate.candidates:
            assert len(item.candidate_hash) == 64
            assert item.locale == "en"
        assert runner.received_context is not None
        # Candidate hashes are backend-owned exact bindings, not frontend-derived values.
        assert len({item.candidate_hash for item in view.pending_gate.candidates}) == 3


@pytest.mark.asyncio
async def test_operator_projection_exact_binding_approves_angle_and_replays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vertical_slice,
        "build_journal_operator_preflight",
        _ready_preflight,
    )
    async with isolated_session() as session:
        await _activate_seeded_angle_runtime(session)
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="ui01-angle-approve"),
        )
        state = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="ui01-angle-approve-start",
        )
        assert queued.job_id is not None
        leased = await claim_next_operator_job(
            session,
            worker_id="worker-ui01-approve",
        )
        assert leased is not None
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", ControlledCodexRunner())
        await execute_start_to_angle_job(
            session,
            job_id=leased.id,
            worker_id="worker-ui01-approve",
            evidence_workflow=ControlledEvidenceWorkflow(),  # type: ignore[arg-type]
            runner_registry=registry,
        )
        view = await get_operator_case_view(
            session,
            content_case_id=created.content_case_id,
        )
        assert view.pending_gate is not None
        assert view.pending_gate.type == "angle"
        selected = view.pending_gate.candidates[0]
        artifact = view.pending_gate.artifact
        decision_kwargs = {
            "content_case_id": created.content_case_id,
            "scope": "angle",
            "decision": "approved",
            "expected_state_version": view.state.state_version,
            "idempotency_key": "ui01-angle-approve-decision",
            "artifact_id": artifact.id,
            "artifact_version": artifact.version,
            "artifact_hash": artifact.content_hash,
            "selected_angle_id": selected.angle_id,
            "selected_candidate_hash": selected.candidate_hash,
            "comment": "UI-01 exact projection approval",
            "actor_id": "founder",
        }
        decision = await submit_operator_decision(session, **decision_kwargs)  # type: ignore[arg-type]
        replay = await submit_operator_decision(session, **decision_kwargs)  # type: ignore[arg-type]
        assert decision.approval_id is not None
        assert replay.replayed is True and replay.command_id == decision.command_id
        approval = await session.get(AngleApproval, decision.approval_id)
        assert approval is not None
        assert approval.angle_artifact_id == artifact.id
        assert approval.angle_artifact_version == artifact.version
        assert approval.angle_artifact_hash == artifact.content_hash
        assert approval.selected_angle_id == selected.angle_id
        assert approval.selected_candidate_hash == selected.candidate_hash
        after = await get_operator_case_view(
            session,
            content_case_id=created.content_case_id,
        )
        assert after.pending_gate is None


@pytest.mark.asyncio
async def test_operator_view_exposes_exact_pending_outline_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vertical_slice,
        "build_journal_operator_preflight",
        _ready_preflight,
    )
    async with isolated_session() as session:
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="f2-outline-view"),
        )
        run = await session.get(ContentRun, created.bootstrap_run_id)
        assert run is not None
        start_step = await session.scalar(
            select(StepRun).where(
                StepRun.run_id == run.id,
                StepRun.step_key == "start_to_angle",
            )
        )
        assert start_step is not None
        await transition_run(session, run_id=run.id, status="running")
        await transition_step_run(session, step_run_id=start_step.id, status="running")
        await transition_step_run(session, step_run_id=start_step.id, status="completed")
        outline_step = StepRun(
            run_id=run.id,
            step_key="outline",
            attempt=1,
            status="pending",
            input_artifact_refs_json=[],
            output_artifact_refs_json=[],
        )
        session.add(outline_step)
        await session.flush()
        await transition_step_run(session, step_run_id=outline_step.id, status="running")
        await transition_step_run(session, step_run_id=outline_step.id, status="completed")
        payload = {
            "artifact_type": "journal_outline",
            "outline": {
                "title": "Exact projected Outline",
                "sections": [],
            },
        }
        exact = Artifact(
            run_id=run.id,
            step_run_id=outline_step.id,
            artifact_type="journal_outline",
            locale="en",
            version=1,
            content_json=payload,
            content_hash="b" * 64,
        )
        stray = Artifact(
            run_id=run.id,
            step_run_id=outline_step.id,
            artifact_type="journal_outline",
            locale="en",
            version=2,
            content_json=payload,
            content_hash="c" * 64,
        )
        session.add_all([exact, stray])
        await session.flush()
        outline_step.output_artifact_refs_json = [str(exact.id), str(stray.id)]
        run.current_step = "outline"
        await transition_run(session, run_id=run.id, status="waiting_approval")
        await create_checkpoint(
            session,
            run_id=run.id,
            pending_approval={"step_key": "outline", "artifact_id": str(exact.id)},
        )
        await session.flush()

        view = await get_operator_case_view(
            session,
            content_case_id=created.content_case_id,
        )

        assert view.state.status == "AWAITING_APPROVAL"
        assert view.state.human_gate == "outline"
        assert view.pending_gate is not None
        assert view.pending_gate.type == "outline"
        assert view.pending_gate.artifact.id == exact.id
        assert view.pending_gate.artifact.id != stray.id
        assert view.pending_gate.artifact.version == exact.version
        assert view.pending_gate.artifact.content_hash == exact.content_hash
        assert view.pending_gate.outline["title"] == "Exact projected Outline"
