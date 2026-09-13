from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_ce05_review_console import _approved_fixture, isolated_session

from app.modules.content_engine.journal.production_board import list_production_board_cases
from app.modules.harness.delegation import (
    DelegationConflictError,
    DelegationStateError,
    complete_delegation_execution,
    ensure_delegation_execution,
    fail_delegation_execution,
    start_delegation_execution,
)
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.models import ContentRun, StepRun


async def _active_run(session, fixture, locale: str = "en") -> tuple[ContentRun, StepRun]:
    source = fixture.writer_runs[locale]
    run = ContentRun(
        project_id=source.project_id,
        content_case_id=source.content_case_id,
        locale_variant_id=source.locale_variant_id,
        content_item_id=source.content_item_id,
        run_mode="update",
        status="running",
        current_step=f"journal_writer_{'vi' if locale == 'vi-VN' else 'en'}",
        settings_snapshot_id=source.settings_snapshot_id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    step = StepRun(
        run_id=run.id,
        step_key=run.current_step or "writer",
        attempt=1,
        status="running",
        input_artifact_refs_json=[],
        output_artifact_refs_json=[],
        started_at=datetime.now(UTC),
    )
    session.add(step)
    await session.flush()
    return run, step


@pytest.mark.asyncio
async def test_delegation_lifecycle_is_idempotent_and_hierarchical() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        run, step = await _active_run(session, fixture)
        parent = await ensure_delegation_execution(
            session,
            run_id=run.id,
            step_run_id=step.id,
            parent_execution_id=None,
            worker_kind="subagent",
            worker_key="writer_en",
            task_key="journal_writer_en",
            dedupe_key=f"test:{run.id}:writer-en:1",
        )
        reused = await ensure_delegation_execution(
            session,
            run_id=run.id,
            step_run_id=step.id,
            parent_execution_id=None,
            worker_kind="subagent",
            worker_key="writer_en",
            task_key="journal_writer_en",
            dedupe_key=f"test:{run.id}:writer-en:1",
        )
        assert reused.id == parent.id
        assert (
            int(
                await session.scalar(
                    select(func.count()).select_from(DelegationExecution)
                )
                or 0
            )
            == 1
        )

        await start_delegation_execution(session, execution_id=parent.id)
        child = await ensure_delegation_execution(
            session,
            run_id=run.id,
            step_run_id=step.id,
            parent_execution_id=parent.id,
            worker_kind="application",
            worker_key="antigravity",
            task_key="layout_assist",
            dedupe_key=f"test:{run.id}:antigravity:1",
        )
        assert child.parent_execution_id == parent.id
        await start_delegation_execution(session, execution_id=child.id)
        completed = await complete_delegation_execution(
            session,
            execution_id=child.id,
            external_execution_id="antigravity-proof-001",
        )
        assert completed.status == "completed"
        assert completed.external_execution_id == "antigravity-proof-001"
        assert completed.started_at is not None
        assert completed.completed_at is not None

        repeated = await complete_delegation_execution(
            session,
            execution_id=child.id,
            external_execution_id="antigravity-proof-001",
        )
        assert repeated.id == child.id


@pytest.mark.asyncio
async def test_delegation_dedupe_conflict_fails_closed() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        run, step = await _active_run(session, fixture)
        dedupe = f"test:{run.id}:same-key"
        await ensure_delegation_execution(
            session,
            run_id=run.id,
            step_run_id=step.id,
            parent_execution_id=None,
            worker_kind="subagent",
            worker_key="writer_en",
            task_key="journal_writer_en",
            dedupe_key=dedupe,
        )
        with pytest.raises(DelegationConflictError, match="another delegation"):
            await ensure_delegation_execution(
                session,
                run_id=run.id,
                step_run_id=step.id,
                parent_execution_id=None,
                worker_kind="subagent",
                worker_key="reviewer_en",
                task_key="review_revise_en",
                dedupe_key=dedupe,
            )


@pytest.mark.asyncio
async def test_delegation_parent_cannot_cross_content_runs() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        en_run, en_step = await _active_run(session, fixture, "en")
        vi_run, vi_step = await _active_run(session, fixture, "vi-VN")
        parent = await ensure_delegation_execution(
            session,
            run_id=en_run.id,
            step_run_id=en_step.id,
            parent_execution_id=None,
            worker_kind="subagent",
            worker_key="writer_en",
            task_key="journal_writer_en",
            dedupe_key=f"test:{en_run.id}:parent",
        )
        with pytest.raises(DelegationStateError, match="another ContentRun"):
            await ensure_delegation_execution(
                session,
                run_id=vi_run.id,
                step_run_id=vi_step.id,
                parent_execution_id=parent.id,
                worker_kind="application",
                worker_key="antigravity",
                task_key="layout_assist",
                dedupe_key=f"test:{vi_run.id}:child",
            )


@pytest.mark.asyncio
async def test_failed_delegation_preserves_safe_error_class() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        run, step = await _active_run(session, fixture)
        execution = await ensure_delegation_execution(
            session,
            run_id=run.id,
            step_run_id=step.id,
            parent_execution_id=None,
            worker_kind="subagent",
            worker_key="reviewer_en",
            task_key="review_revise_en",
            dedupe_key=f"test:{run.id}:failure",
        )
        await start_delegation_execution(session, execution_id=execution.id)
        failed = await fail_delegation_execution(
            session,
            execution_id=execution.id,
            error_class="WorkerUnavailable",
        )
        assert failed.status == "failed"
        assert failed.error_class == "WorkerUnavailable"
        assert failed.completed_at is not None


@pytest.mark.asyncio
async def test_production_board_prefers_running_delegation_worker_without_inference() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        run, step = await _active_run(session, fixture)
        execution = await ensure_delegation_execution(
            session,
            run_id=run.id,
            step_run_id=step.id,
            parent_execution_id=None,
            worker_kind="application",
            worker_key="antigravity",
            task_key="journal_writer_en",
            dedupe_key=f"test:{run.id}:board",
            external_execution_id=f"ag-{uuid4().hex}",
        )
        await start_delegation_execution(session, execution_id=execution.id)
        before = int(
            await session.scalar(select(func.count()).select_from(DelegationExecution)) or 0
        )

        rows = await list_production_board_cases(session)

        after = int(
            await session.scalar(select(func.count()).select_from(DelegationExecution)) or 0
        )
        assert after == before
        row = next(item for item in rows if item.id == fixture.content_case.id)
        assert row.status_group == "RUNNING"
        assert row.stage_key == "journal_writer_en"
        assert row.current_worker is not None
        assert row.current_worker.kind == "delegation"
        assert row.current_worker.execution_id == execution.id
        assert row.current_worker.worker_kind == "application"
        assert row.current_worker.worker_key == "antigravity"
        assert any(event.execution_id == execution.id for event in row.execution_chain)
