from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from test_ce05_review_revise import isolated_session
from test_review_revise_orchestration import _request, _source_draft_with_settings

import app.modules.content_engine.journal.operator_control as operator_module
from app.modules.content_engine.journal.models import AngleApproval
from app.modules.content_engine.journal.operator_control import (
    OperatorControlError,
    get_operator_state,
    submit_operator_command,
)
from app.modules.content_engine.journal.operator_creation import create_journal_case_with_receipt
from app.modules.content_engine.journal.review_revise_orchestration import (
    prepare_review_revise_en_orchestration,
)
from app.modules.content_engine.journal.router import OperatorCommandRequest
from app.modules.content_engine.models import ContentCase, ContentOpportunity
from app.modules.harness.models import Job


async def _ready_preflight() -> dict[str, object]:
    return {"status": "READY", "checks": []}


async def _blocked_preflight() -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "checks": [{"key": "database", "status": "BLOCKED"}],
    }


@pytest.mark.asyncio
async def test_operator_create_receipt_is_exactly_replay_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _ = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
        )
        source_case = await session.get(
            ContentCase,
            fixture.writer_input.writer_run.content_case_id,
        )
        assert source_case is not None
        opportunity = await session.get(ContentOpportunity, source_case.content_opportunity_id)
        assert opportunity is not None

        first = await create_journal_case_with_receipt(
            session,
            content_opportunity_id=opportunity.id,
            expected_opportunity_version=opportunity.version,
            idempotency_key="operator-create-replay",
        )
        replay = await create_journal_case_with_receipt(
            session,
            content_opportunity_id=opportunity.id,
            expected_opportunity_version=opportunity.version,
            idempotency_key="operator-create-replay",
        )

        assert first.content_case_id == source_case.id
        assert first.replayed is False
        assert replay.command_id == first.command_id
        assert replay.content_case_id == first.content_case_id
        assert replay.replayed is True


@pytest.mark.asyncio
async def test_operator_command_request_forbids_internal_stage_selection() -> None:
    with pytest.raises(ValidationError):
        OperatorCommandRequest.model_validate(
            {
                "intent": "continue",
                "expected_state_version": "a" * 64,
                "idempotency_key": "no-stage-selection",
                "stage_key": "review_revise_en",
            }
        )


@pytest.mark.asyncio
async def test_operator_queue_replay_stale_and_retry_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(operator_module, "build_operational_preflight", _ready_preflight)
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
        state = await get_operator_state(
            session,
            content_case_id=prepared.run.content_case_id,
        )
        assert state.status == "READY"
        assert state.primary_intent == "continue"
        assert state.allowed_intents == ["continue"]

        first = await submit_operator_command(
            session,
            content_case_id=prepared.run.content_case_id,
            intent="continue",
            expected_state_version=state.state_version,
            idempotency_key="operator-queue-once",
        )
        replay = await submit_operator_command(
            session,
            content_case_id=prepared.run.content_case_id,
            intent="continue",
            expected_state_version=state.state_version,
            idempotency_key="operator-queue-once",
        )
        assert first.job_id is not None
        assert replay.command_id == first.command_id
        assert replay.job_id == first.job_id
        assert replay.replayed is True
        assert await session.scalar(select(func.count(Job.id))) == 1

        with pytest.raises(OperatorControlError) as stale:
            await submit_operator_command(
                session,
                content_case_id=prepared.run.content_case_id,
                intent="continue",
                expected_state_version=state.state_version,
                idempotency_key="operator-stale",
            )
        assert stale.value.code == "operator_state_stale"

        first_job = await session.get(Job, first.job_id)
        assert first_job is not None
        first_job.status = "failed"
        await session.flush()
        retry_state = await get_operator_state(
            session,
            content_case_id=prepared.run.content_case_id,
        )
        assert retry_state.primary_intent == "retry"
        assert retry_state.allowed_intents == ["retry"]

        retry = await submit_operator_command(
            session,
            content_case_id=prepared.run.content_case_id,
            intent="retry",
            expected_state_version=retry_state.state_version,
            idempotency_key="operator-retry-once",
        )
        assert retry.job_id is not None
        assert retry.job_id != first.job_id
        second_job = await session.get(Job, retry.job_id)
        assert second_job is not None
        assert second_job.attempt == 2
        assert await session.scalar(select(func.count(Job.id))) == 2


@pytest.mark.asyncio
async def test_operator_preflight_blocks_queue_before_job_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(operator_module, "build_operational_preflight", _blocked_preflight)
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
        state = await get_operator_state(
            session,
            content_case_id=prepared.run.content_case_id,
        )

        with pytest.raises(OperatorControlError) as blocked:
            await submit_operator_command(
                session,
                content_case_id=prepared.run.content_case_id,
                intent="continue",
                expected_state_version=state.state_version,
                idempotency_key="operator-preflight-blocked",
            )
        assert blocked.value.code == "operator_preflight_blocked"
        assert await session.scalar(select(func.count(Job.id))) == 0


@pytest.mark.asyncio
async def test_operator_human_gate_exposes_no_continue_bypass(
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

        state = await get_operator_state(
            session,
            content_case_id=prepared.run.content_case_id,
        )
        assert state.status == "AWAITING_APPROVAL"
        assert state.human_gate == "angle"
        assert state.primary_intent is None
        assert state.allowed_intents == []


@pytest.mark.asyncio
async def test_operator_persisted_gate_decision_is_not_offered_twice(
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
        session.add(
            AngleApproval(
                run_id=prepared.run.id,
                angle_artifact_id=source.artifact.id,
                angle_artifact_version=source.artifact.version,
                angle_artifact_hash=source.artifact.content_hash,
                selected_angle_id="angle-operator-test",
                selected_candidate_hash="a" * 64,
                approved_by="founder",
                approval_reason="operator gate projection test",
                approved_at=datetime.now(UTC),
            )
        )
        await session.flush()

        state = await get_operator_state(
            session,
            content_case_id=prepared.run.content_case_id,
        )
        assert state.status == "BLOCKED"
        assert state.human_gate is None
        assert state.allowed_intents == []
        assert state.blocker_code == "operator_gate_already_decided"
