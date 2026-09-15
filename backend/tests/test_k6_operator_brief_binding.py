from __future__ import annotations

import pytest
from sqlalchemy import select
from test_ce05_review_revise import isolated_session
from test_k6_journal_knowledge_brief_binding import _materialize_case_brief
from test_operator_start_to_angle import (
    ControlledCodexRunner,
    ControlledEvidenceWorkflow,
    _activate_seeded_angle_runtime,
    _intake_kwargs,
    _ready_preflight,
)

import app.modules.content_engine.journal.operator_vertical_slice as vertical_slice
from app.modules.content_engine.journal.operator_control import OperatorControlError
from app.modules.content_engine.journal.operator_manual_intake import create_founder_journal_intake
from app.modules.content_engine.journal.operator_vertical_slice import (
    get_operator_state_v45,
    submit_operator_command_v45,
)
from app.modules.content_engine.journal.operator_worker import (
    claim_next_operator_job,
    execute_start_to_angle_job,
)
from app.modules.content_engine.models import ContentCase, LocaleVariant, Project
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.knowledge.brief_binding import load_run_knowledge_brief_binding
from app.modules.knowledge.brief_ref import knowledge_brief_snapshot


async def _brief_for_created_case(session, created):
    content_case = await session.get(ContentCase, created.content_case_id)
    assert content_case is not None
    project = await session.get(Project, content_case.project_id)
    assert project is not None
    variant = await session.scalar(
        select(LocaleVariant).where(LocaleVariant.content_case_id == content_case.id)
    )
    assert variant is not None
    brief, _candidate = await _materialize_case_brief(
        session,
        project=project,
        content_case=content_case,
        locale=variant.locale,
        with_candidate=False,
    )
    return content_case, variant, brief


@pytest.mark.asyncio
async def test_operator_start_binds_exact_brief_and_idempotency_includes_brief(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vertical_slice, "build_operational_preflight", _ready_preflight)
    async with isolated_session() as session:
        created = await create_founder_journal_intake(
            session, **_intake_kwargs(key="k6-start-binding")
        )
        content_case, variant, first_brief = await _brief_for_created_case(session, created)
        second_brief, _candidate = await _materialize_case_brief(
            session,
            project=await session.get(Project, content_case.project_id),  # type: ignore[arg-type]
            content_case=content_case,
            locale=variant.locale,
            with_candidate=False,
        )
        state = await get_operator_state_v45(
            session, content_case_id=created.content_case_id
        )

        first = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="k6-start-binding-command",
            knowledge_brief_id=first_brief.id,
            actor_id="founder",
        )
        assert first.job_id is not None
        binding = await load_run_knowledge_brief_binding(
            session,
            run_id=created.bootstrap_run_id,
        )
        assert binding is not None
        assert binding.brief_id == first_brief.id
        assert binding.snapshot_hash == first_brief.snapshot_hash
        assert binding.binding.bound_by == "founder"

        replay = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="k6-start-binding-command",
            knowledge_brief_id=first_brief.id,
            actor_id="founder",
        )
        assert replay.replayed is True
        assert replay.command_id == first.command_id

        with pytest.raises(OperatorControlError, match="operator_idempotency_conflict"):
            await submit_operator_command_v45(
                session,
                content_case_id=created.content_case_id,
                intent="start",
                expected_state_version=state.state_version,
                idempotency_key="k6-start-binding-command",
                knowledge_brief_id=second_brief.id,
                actor_id="founder",
            )

        with pytest.raises(
            OperatorControlError,
            match="operator_knowledge_brief_binding_start_only",
        ):
            await submit_operator_command_v45(
                session,
                content_case_id=created.content_case_id,
                intent="retry",
                expected_state_version=state.state_version,
                idempotency_key="k6-binding-switch-forbidden",
                knowledge_brief_id=second_brief.id,
                actor_id="founder",
            )


@pytest.mark.asyncio
async def test_worker_consumes_brief_bound_by_operator_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vertical_slice, "build_operational_preflight", _ready_preflight)
    async with isolated_session() as session:
        await _activate_seeded_angle_runtime(session)
        created = await create_founder_journal_intake(
            session, **_intake_kwargs(key="k6-worker-binding")
        )
        _content_case, _variant, brief = await _brief_for_created_case(session, created)
        state = await get_operator_state_v45(
            session, content_case_id=created.content_case_id
        )
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="k6-worker-binding-start",
            knowledge_brief_id=brief.id,
            actor_id="founder",
        )
        assert queued.job_id is not None
        leased = await claim_next_operator_job(
            session,
            worker_id="worker-k6-binding",
            lease_seconds=900,
        )
        assert leased is not None and leased.id == queued.job_id

        workflow = ControlledEvidenceWorkflow()
        runner = ControlledCodexRunner()
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", runner)
        await execute_start_to_angle_job(
            session,
            job_id=leased.id,
            worker_id="worker-k6-binding",
            evidence_workflow=workflow,  # type: ignore[arg-type]
            runner_registry=registry,
        )

        assert runner.received_context is not None
        model_input = runner.received_context["angle_model_input"]
        assert isinstance(model_input, dict)
        assert model_input["knowledge_brief"] == knowledge_brief_snapshot(brief)
