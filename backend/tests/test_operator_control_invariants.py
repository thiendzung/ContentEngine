from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_ce05_review_revise import isolated_session
from test_review_revise_orchestration import _request, _source_draft_with_settings

import app.modules.content_engine.journal.operator_decisions as operator_decision_module
from app.modules.content_engine.journal.operator_bootstrap import ensure_operator_bootstrap_run
from app.modules.content_engine.journal.operator_control import get_operator_state
from app.modules.content_engine.journal.operator_decisions import submit_operator_decision
from app.modules.content_engine.journal.review_revise_orchestration import (
    prepare_review_revise_en_orchestration,
)
from app.modules.harness.models import ContentRun, utc_now

_APP_ROOT = Path(__file__).parents[1] / "app"
_V45_COMPATIBILITY_FILES = {"operator_vertical_slice.py", "operator_runtime.py"}


def test_production_operator_entrypoint_imports_are_canonical() -> None:
    v45_violations: list[str] = []
    control_state_violations: list[str] = []

    for path in sorted(_APP_ROOT.rglob("*.py")):
        if path.name in _V45_COMPATIBILITY_FILES:
            continue
        source = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(source.splitlines(), start=1):
            if "get_operator_state_v45" in line or "submit_operator_command_v45" in line:
                v45_violations.append(f"{path}:{line_number}")

        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "app.modules.content_engine.journal.operator_control":
                continue
            if any(alias.name == "get_operator_state" for alias in node.names):
                control_state_violations.append(f"{path}:{node.lineno}")

    assert v45_violations == []
    assert control_state_violations == []


@pytest.mark.asyncio
async def test_bootstrap_reuses_matching_source_create_run_not_newer_eval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _ = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
        )
        source_run = fixture.writer_input.writer_run
        bootstrap, _ = await ensure_operator_bootstrap_run(
            session,
            content_case_id=source_run.content_case_id,
            locale_variant_id=source_run.locale_variant_id,
        )
        assert bootstrap.run_mode == "create"
        assert bootstrap.locale_variant_id == source_run.locale_variant_id

        newer_eval = ContentRun(
            project_id=bootstrap.project_id,
            content_case_id=bootstrap.content_case_id,
            locale_variant_id=bootstrap.locale_variant_id,
            content_item_id=None,
            run_mode="eval",
            status="pending",
            current_step="review_revise_en",
            settings_snapshot_id=bootstrap.settings_snapshot_id,
            started_at=utc_now(),
            completed_at=None,
            failure_code=None,
            failure_message=None,
        )
        session.add(newer_eval)
        await session.flush()

        replay, reused = await ensure_operator_bootstrap_run(
            session,
            content_case_id=bootstrap.content_case_id,
            locale_variant_id=bootstrap.locale_variant_id,
        )
        assert reused is True
        assert replay.id == bootstrap.id
        assert replay.id != newer_eval.id


@pytest.mark.asyncio
async def test_final_decision_replay_returns_same_approval_reference(
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
        prepared.run.current_step = "final_review"
        await session.flush()
        state = await get_operator_state(
            session,
            content_case_id=prepared.run.content_case_id,
        )
        assert state.human_gate == "final_review"
        assert prepared.run.locale_variant_id is not None

        approval_id = uuid4()
        calls = 0

        async def fake_submit_review_decision(
            session_arg: object,
            **kwargs: object,
        ) -> SimpleNamespace:
            nonlocal calls
            assert session_arg is session
            calls += 1
            return SimpleNamespace(
                approval_id=approval_id,
                writer_run_id=prepared.run.id,
            )

        monkeypatch.setattr(
            operator_decision_module,
            "submit_review_decision",
            fake_submit_review_decision,
        )
        kwargs = {
            "content_case_id": prepared.run.content_case_id,
            "scope": "final",
            "decision": "approved",
            "expected_state_version": state.state_version,
            "idempotency_key": "operator-final-exact-replay",
            "locale_variant_id": prepared.run.locale_variant_id,
        }
        first = await submit_operator_decision(session, **kwargs)
        replay = await submit_operator_decision(session, **kwargs)

        assert first.approval_id == approval_id
        assert replay.approval_id == approval_id
        assert replay.command_id == first.command_id
        assert replay.state_before == first.state_before
        assert replay.state_after == first.state_after
        assert replay.replayed is True
        assert calls == 1
