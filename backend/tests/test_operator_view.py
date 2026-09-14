from __future__ import annotations

import pytest
from test_ce05_review_revise import isolated_session
from test_operator_start_to_angle import (
    ControlledCodexRunner,
    ControlledEvidenceWorkflow,
    _activate_seeded_angle_runtime,
    _intake_kwargs,
    _ready_preflight,
)

import app.modules.content_engine.journal.operator_vertical_slice as vertical_slice
from app.modules.content_engine.journal.angle import angle_candidate_hash
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
from app.modules.harness.agent_runner import AgentRunnerRegistry


@pytest.mark.asyncio
async def test_operator_view_projects_ready_intake_without_inventing_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vertical_slice, "build_operational_preflight", _ready_preflight)
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
            ("vi", "translation"),
        ]


@pytest.mark.asyncio
async def test_operator_view_returns_revalidated_exact_angle_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vertical_slice, "build_operational_preflight", _ready_preflight)
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
        view = await get_operator_case_view(
            session,
            content_case_id=created.content_case_id,
        )
        assert view.state.status == "AWAITING_APPROVAL"
        assert view.state.human_gate == "angle"
        assert view.pending_gate is not None
        assert view.pending_gate.type == "angle"
        assert view.pending_gate.artifact.id == result.angle_artifact_id
        assert view.pending_gate.artifact.content_hash == result.angle_artifact_hash
        assert len(view.pending_gate.candidates) == 3
        for item in view.pending_gate.candidates:
            assert len(item.candidate_hash) == 64
            assert item.locale == "en"
        raw_candidates = runner.received_context
        assert raw_candidates is not None
        # Candidate hashes are backend-owned exact bindings, not frontend-derived values.
        assert len({item.candidate_hash for item in view.pending_gate.candidates}) == 3
