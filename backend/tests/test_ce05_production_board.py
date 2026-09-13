from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from test_ce05_review_actions import _pending_fixture
from test_ce05_review_console import _approved_fixture, isolated_session

from app.modules.content_engine.journal.production_board import (
    list_production_board_cases,
)
from app.modules.harness.models import ContentRun, ModelCall, StepRun, ToolCall


async def _telemetry_counts(session) -> tuple[int, int, int, int]:
    return (
        int(await session.scalar(select(func.count()).select_from(ContentRun)) or 0),
        int(await session.scalar(select(func.count()).select_from(StepRun)) or 0),
        int(await session.scalar(select(func.count()).select_from(ModelCall)) or 0),
        int(await session.scalar(select(func.count()).select_from(ToolCall)) or 0),
    )


@pytest.mark.asyncio
async def test_production_board_projects_approved_case_without_writes() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        writer_run = fixture.writer_runs["en"]
        step = StepRun(
            run_id=writer_run.id,
            step_key="journal_writer_en",
            attempt=1,
            status="completed",
            input_artifact_refs_json=[],
            output_artifact_refs_json=[],
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        session.add(step)
        await session.flush()
        session.add(
            ModelCall(
                run_id=writer_run.id,
                step_run_id=step.id,
                task_key="journal_writer_en",
                provider="codex_cli",
                model="gpt-5.6-luna",
                purpose="journal_writer_en",
                prompt_version="journal_writer_en:v1",
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                status="completed",
            )
        )
        await session.flush()
        before = await _telemetry_counts(session)

        rows = await list_production_board_cases(session)

        assert await _telemetry_counts(session) == before
        row = next(item for item in rows if item.id == fixture.content_case.id)
        assert row.status_group == "COMPLETED"
        assert row.stage_key == "approved"
        assert row.coordinator == "Codex"
        assert row.current_worker is None
        assert row.execution_chain[-1].kind == "model"
        assert row.execution_chain[-1].provider == "codex_cli"
        assert set(row.locales) == {"vi-VN", "en"}
        assert row.next_action == "APPROVED_NOT_PUBLISHED"


@pytest.mark.asyncio
async def test_production_board_maps_pending_founder_review_to_review_lane() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        rows = await list_production_board_cases(session)
        row = next(item for item in rows if item.id == fixture.content_case_id)

        assert row.status_group == "AWAITING_APPROVAL"
        assert row.stage_key == "final_review"
        assert row.coordinator == "Codex"
        assert row.next_action == "AWAITING_FOUNDER_APPROVAL"
