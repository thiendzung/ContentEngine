from __future__ import annotations

import pytest
from sqlalchemy import delete, func, select

from app.modules.content_engine.journal.review_action_view import get_action_aware_review_case
from app.modules.content_engine.journal.review_actions import (
    ReviewActionError,
    submit_review_decision,
)
from app.modules.content_engine.models import ContentVersion
from app.modules.harness.models import Approval
from app.modules.harness.persistence import pause_for_approval
from test_ce05_review_console import ReviewFixture, _approved_fixture, isolated_session


async def _pending_fixture(session) -> ReviewFixture:
    fixture = await _approved_fixture(session)
    locale = "en"
    await session.execute(
        delete(ContentVersion).where(ContentVersion.id == fixture.versions[locale].id)
    )
    await session.execute(
        delete(Approval).where(Approval.id == fixture.final_approvals[locale].id)
    )
    run = fixture.writer_runs[locale]
    run.status = "running"
    run.completed_at = None
    await session.flush()
    await pause_for_approval(
        session,
        run_id=run.id,
        step_key="final_review",
        artifact_id=fixture.final_artifacts[locale].id,
    )
    await session.flush()
    detail = await get_action_aware_review_case(
        session,
        content_case_id=fixture.content_case.id,
    )
    panel = next(row for row in detail.locales if row.locale == locale)
    assert panel.next_action == "AWAITING_FOUNDER_APPROVAL"
    return fixture


async def _counts(session) -> tuple[int, int]:
    approvals = int(await session.scalar(select(func.count()).select_from(Approval)) or 0)
    versions = int(
        await session.scalar(select(func.count()).select_from(ContentVersion)) or 0
    )
    return approvals, versions


@pytest.mark.asyncio
async def test_review_action_approve_persists_version_and_completes_run() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        before = await _counts(session)
        result = await submit_review_decision(
            session,
            content_case_id=fixture.content_case.id,
            locale_variant_id=fixture.variants["en"].id,
            decision="approved",
            actor_id="founder",
            comment="Duyệt từ giao diện.",
        )
        after = await _counts(session)
        assert after == (before[0] + 1, before[1] + 1)
        assert result.content_version_id is not None
        assert result.writer_run_status == "completed"
        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case.id,
        )
        panel = next(row for row in detail.locales if row.locale == "en")
        assert panel.next_action == "APPROVED_NOT_PUBLISHED"
        assert panel.final_approval is not None
        assert panel.final_approval.decision == "approved"


@pytest.mark.asyncio
async def test_review_action_changes_requested_is_durable_and_requires_comment() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        before = await _counts(session)
        with pytest.raises(ReviewActionError, match="review_action_comment_required"):
            await submit_review_decision(
                session,
                content_case_id=fixture.content_case.id,
                locale_variant_id=fixture.variants["en"].id,
                decision="changes_requested",
                actor_id="founder",
                comment="",
            )
        assert await _counts(session) == before

        result = await submit_review_decision(
            session,
            content_case_id=fixture.content_case.id,
            locale_variant_id=fixture.variants["en"].id,
            decision="changes_requested",
            actor_id="founder",
            comment="Rút gọn đoạn mở đầu.",
        )
        after = await _counts(session)
        assert after == (before[0] + 1, before[1])
        assert result.writer_run_status == "running"
        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case.id,
        )
        panel = next(row for row in detail.locales if row.locale == "en")
        assert panel.consistency_state == "CONSISTENT"
        assert panel.next_action == "REVISION_REQUESTED"
        assert panel.final_approval is not None
        assert panel.final_approval.decision == "changes_requested"


@pytest.mark.asyncio
async def test_review_action_reject_cancels_without_content_version() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        before = await _counts(session)
        result = await submit_review_decision(
            session,
            content_case_id=fixture.content_case.id,
            locale_variant_id=fixture.variants["en"].id,
            decision="rejected",
            actor_id="founder",
            comment="Không phù hợp định hướng.",
        )
        after = await _counts(session)
        assert after == (before[0] + 1, before[1])
        assert result.writer_run_status == "cancelled"
        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case.id,
        )
        panel = next(row for row in detail.locales if row.locale == "en")
        assert panel.consistency_state == "CONSISTENT"
        assert panel.next_action == "REJECTED"


@pytest.mark.asyncio
async def test_review_action_exact_replay_creates_no_duplicate() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        first = await submit_review_decision(
            session,
            content_case_id=fixture.content_case.id,
            locale_variant_id=fixture.variants["en"].id,
            decision="approved",
            actor_id="founder",
            comment="Duyệt.",
        )
        counts = await _counts(session)
        replay = await submit_review_decision(
            session,
            content_case_id=fixture.content_case.id,
            locale_variant_id=fixture.variants["en"].id,
            decision="approved",
            actor_id="founder",
            comment="Duyệt.",
        )
        assert replay.replayed is True
        assert replay.approval_id == first.approval_id
        assert replay.content_version_id == first.content_version_id
        assert await _counts(session) == counts


@pytest.mark.asyncio
async def test_review_action_quality_failure_creates_no_decision() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        audit = fixture.current_audits["en"]
        payload = dict(audit.content_json)
        summary = dict(payload["summary"])
        summary["result"] = "fail"
        summary["critical_unsupported_count"] = 1
        payload["summary"] = summary
        audit.content_json = payload
        await session.flush()
        before = await _counts(session)
        with pytest.raises(ReviewActionError, match="review_action_quality_blocked"):
            await submit_review_decision(
                session,
                content_case_id=fixture.content_case.id,
                locale_variant_id=fixture.variants["en"].id,
                decision="approved",
                actor_id="founder",
                comment="Duyệt.",
            )
        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_m1_already_approved_state_exposes_no_write_action() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case.id,
        )
        for panel in detail.locales:
            assert panel.next_action == "APPROVED_NOT_PUBLISHED"
