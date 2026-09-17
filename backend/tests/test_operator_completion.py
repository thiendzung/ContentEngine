from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from test_ce05_review_console import _approved_fixture, isolated_session

from app.modules.content_engine.journal.models import JournalRequiredLocale
from app.modules.content_engine.journal.operator_runtime import get_operator_state
from app.modules.content_engine.journal.review_action_view import get_action_aware_review_case
from app.modules.content_engine.models import ContentVersion, LocaleVariant
from app.modules.harness.models import ContentRun


async def _canonical_completed_fixture(session):
    fixture = await _approved_fixture(session)
    source_runs = list(
        (
            await session.scalars(
                select(ContentRun).where(
                    ContentRun.content_case_id == fixture.content_case.id,
                    ContentRun.current_step == "outline",
                )
            )
        ).all()
    )
    assert len(source_runs) == 1
    source_runs[0].status = "completed"
    source_runs[0].completed_at = datetime.now(UTC)
    session.add_all(
        [
            JournalRequiredLocale(
                content_case_id=fixture.content_case.id,
                locale="en",
                role="source",
                declared_by="founder",
            ),
            JournalRequiredLocale(
                content_case_id=fixture.content_case.id,
                locale="vi-VN",
                role="translation",
                declared_by="founder",
            ),
        ]
    )
    await session.flush()
    return fixture


@pytest.mark.asyncio
async def test_exact_required_locale_final_chains_complete_case() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status == "COMPLETE"
        assert state.phase == "Hoàn tất"
        assert state.human_gate is None
        assert state.blocker_code is None

        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert detail.next_action == "APPROVED_NOT_PUBLISHED"
        assert detail.publication_state == "NOT_PUBLISHED"


@pytest.mark.asyncio
async def test_approved_version_without_exact_final_approval_fails_closed() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        await session.delete(fixture.final_approvals["en"])
        await session.flush()

        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status == "BLOCKED"
        assert state.blocker_code == "operator_completion_binding_invalid"


@pytest.mark.asyncio
async def test_content_version_bound_to_wrong_final_artifact_and_run_fails_closed() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        en_version = fixture.versions["en"]
        en_version.final_artifact_id = fixture.final_artifacts["vi-VN"].id
        en_version.created_by_run_id = fixture.writer_runs["vi-VN"].id
        await session.flush()

        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status == "BLOCKED"
        assert state.blocker_code == "operator_completion_binding_invalid"


@pytest.mark.asyncio
async def test_extra_non_required_locale_does_not_block_complete() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        session.add(
            LocaleVariant(
                content_case_id=fixture.content_case.id,
                locale="fr",
                content_role="cluster",
                primary_question="Question non requise",
                primary_intent="evaluate",
            )
        )
        await session.flush()

        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status == "COMPLETE"
        assert state.phase == "Hoàn tất"
        assert state.blocker_code is None


@pytest.mark.asyncio
async def test_missing_required_locale_active_version_never_completes() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        fixture.versions["en"].status = "superseded"
        await session.flush()

        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status != "COMPLETE"


@pytest.mark.asyncio
async def test_multiple_active_versions_for_required_locale_fail_closed() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        first = fixture.versions["en"]
        session.add(
            ContentVersion(
                content_item_id=first.content_item_id,
                version_no=2,
                final_artifact_id=first.final_artifact_id,
                change_reason="conflict fixture",
                status="approved",
                content_json=first.content_json,
                created_by_run_id=first.created_by_run_id,
            )
        )
        await session.flush()

        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status == "BLOCKED"
        assert state.blocker_code == "operator_completion_binding_invalid"
