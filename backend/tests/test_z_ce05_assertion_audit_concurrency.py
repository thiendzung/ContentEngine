from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_assertion_audit import _source
from test_ce05_assertion_audit_recovery import _mark_source_waiting

from app.core.database import engine
from app.modules.content_engine.journal.assertion_audit import load_assertion_audit_input
from app.modules.content_engine.journal.assertion_audit_execution import (
    prepare_assertion_audit_run,
)
from app.modules.harness.models import ContentRun


async def _prepare(session: AsyncSession, *, source_input):
    return await prepare_assertion_audit_run(
        session,
        source_input=source_input,
        task_key=f"assertion_audit_{source_input.writer_input.locale}",
        prompt_version="assertion-test:v1",
        recipe_version="assertion-test-recipe:v1",
    )


@pytest.mark.asyncio
async def test_postgresql_concurrent_prepare_reuses_one_locked_pending_run() -> None:
    assert engine.dialect.name == "postgresql"
    source_ids: dict[str, object] = {}
    try:
        async with engine.connect() as setup_connection:
            setup_session = AsyncSession(bind=setup_connection, expire_on_commit=False)
            try:
                _fixture, source_artifact, source_input = await _source(setup_session)
                await _mark_source_waiting(setup_session, source_input=source_input)
                source_ids = {
                    "writer_run_id": source_input.writer_input.writer_run.id,
                    "source_artifact_id": source_artifact.id,
                    "source_artifact_version": source_artifact.version,
                    "source_artifact_hash": source_artifact.content_hash,
                    "outline_artifact_id": source_input.writer_input.outline_artifact.id,
                    "outline_artifact_version": source_input.writer_input.outline_artifact.version,
                    "outline_artifact_hash": (
                        source_input.writer_input.outline_artifact.content_hash
                    ),
                }
                await setup_session.commit()
            finally:
                await setup_session.close()

        async with engine.connect() as connection_a, engine.connect() as connection_b:
            transaction_a = await connection_a.begin()
            transaction_b = await connection_b.begin()
            session_a = AsyncSession(bind=connection_a, expire_on_commit=False)
            session_b = AsyncSession(bind=connection_b, expire_on_commit=False)
            try:
                input_a = await load_assertion_audit_input(
                    session_a,
                    writer_run_id=source_ids["writer_run_id"],
                    revised_draft_artifact_id=source_ids["source_artifact_id"],
                    expected_revised_draft_version=source_ids["source_artifact_version"],
                    expected_revised_draft_hash=source_ids["source_artifact_hash"],
                    outline_artifact_id=source_ids["outline_artifact_id"],
                    expected_outline_version=source_ids["outline_artifact_version"],
                    expected_outline_hash=source_ids["outline_artifact_hash"],
                    locale="en",
                )
                input_b = await load_assertion_audit_input(
                    session_b,
                    writer_run_id=source_ids["writer_run_id"],
                    revised_draft_artifact_id=source_ids["source_artifact_id"],
                    expected_revised_draft_version=source_ids["source_artifact_version"],
                    expected_revised_draft_hash=source_ids["source_artifact_hash"],
                    outline_artifact_id=source_ids["outline_artifact_id"],
                    expected_outline_version=source_ids["outline_artifact_version"],
                    expected_outline_hash=source_ids["outline_artifact_hash"],
                    locale="en",
                )
                first = await _prepare(session_a, source_input=input_a)
                second_task = asyncio.create_task(_prepare(session_b, source_input=input_b))
                await asyncio.sleep(0.1)
                assert not second_task.done()
                await transaction_a.commit()
                second = await asyncio.wait_for(second_task, timeout=2)
                await transaction_b.commit()
                assert second.audit_run.id == first.audit_run.id
                assert second.handoff.id == first.handoff.id
                assert second.audit_run_reused is True
                assert len(
                    (
                        await session_b.scalars(
                            select(ContentRun).where(
                                ContentRun.content_case_id
                                == input_b.writer_input.writer_run.content_case_id,
                                ContentRun.run_mode == "eval",
                            )
                        )
                    ).all()
                ) == 1
            finally:
                await session_a.close()
                await session_b.close()
                if transaction_a.is_active:
                    await transaction_a.rollback()
                if transaction_b.is_active:
                    await transaction_b.rollback()
    finally:
        async with engine.begin() as cleanup_connection:
            await cleanup_connection.execute(text("TRUNCATE TABLE projects CASCADE"))
