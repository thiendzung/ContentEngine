from __future__ import annotations

from datetime import UTC, datetime

import pytest
from test_ce05_review_revise import isolated_session
from test_review_revise_orchestration import _request, _source_draft_with_settings

from app.modules.content_engine.journal.models import AngleApproval
from app.modules.content_engine.journal.operator_runtime import resolve_next_operator_action
from app.modules.content_engine.journal.review_revise_orchestration import (
    prepare_review_revise_en_orchestration,
)


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
        assert action.current_step_run_id == prepared.step_run.id


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


@pytest.mark.asyncio
async def test_operator_runtime_resolves_approved_angle_to_future_outline_action(
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
                selected_angle_id="angle-runtime-test",
                selected_candidate_hash="a" * 64,
                approved_by="founder",
                approval_reason="canonical runtime resolver test",
                approved_at=datetime.now(UTC),
            )
        )
        await session.flush()

        action = await resolve_next_operator_action(
            session,
            content_case_id=prepared.run.content_case_id,
        )

        assert action.action_key == "angle_to_outline"
        assert action.intent == "continue"
        assert action.executable is False
        assert action.blocker_code == "operator_gate_already_decided"
        assert action.current_run_id == prepared.run.id
