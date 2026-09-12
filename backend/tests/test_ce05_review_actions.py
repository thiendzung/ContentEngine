from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import func, select
from test_ce05_review_console import (
    _approved_fixture,
    _base_case,
    _draft,
    _hash,
    _persist_lineage,
    _persist_quality,
    isolated_session,
)

from app.modules.content_engine.journal.review_action_view import get_action_aware_review_case
from app.modules.content_engine.journal.review_actions import (
    ReviewActionError,
    submit_review_decision,
)
from app.modules.content_engine.models import (
    ContentItem,
    ContentVersion,
    LocaleVariant,
    SettingsSnapshot,
)
from app.modules.harness.models import Approval, Artifact, ContentRun
from app.modules.harness.persistence import pause_for_approval


@dataclass
class PendingReviewFixture:
    content_case_id: UUID
    variant: LocaleVariant
    writer_run: ContentRun
    final_artifact: Artifact
    current_audit: Artifact


async def _pending_fixture(session) -> PendingReviewFixture:
    project, content_case, _opportunity = await _base_case(session)
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={"models": {}},
        source_version_refs_json=["fixture"],
        content_hash="a" * 64,
    )
    session.add(snapshot)
    await session.flush()

    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="cluster",
        primary_question="What can an artwork price tell me?",
        primary_intent="evaluate",
    )
    session.add(variant)
    await session.flush()
    await _persist_lineage(
        session,
        project=project,
        content_case=content_case,
        snapshot=snapshot,
        variant=variant,
    )

    item = ContentItem(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_type="journal",
        canonical_key=f"journal:{content_case.id}:en",
    )
    session.add(item)
    await session.flush()

    writer_run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_item_id=item.id,
        run_mode="create",
        status="running",
        current_step="final_review",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(writer_run)
    await session.flush()

    draft_payload = _draft("en")
    draft_hash = _hash(draft_payload)
    source_draft = Artifact(
        run_id=writer_run.id,
        artifact_type="journal_draft",
        locale="en",
        version=4,
        content_json=draft_payload,
        content_hash=draft_hash,
    )
    final_artifact = Artifact(
        run_id=writer_run.id,
        artifact_type="final_content",
        locale="en",
        version=1,
        content_json=draft_payload,
        content_hash=draft_hash,
    )
    session.add_all([source_draft, final_artifact])
    await session.flush()

    current_audit, _source_copy = await _persist_quality(
        session,
        project=project,
        content_case=content_case,
        snapshot=snapshot,
        variant=variant,
        item=item,
        writer_run=writer_run,
        source_draft=source_draft,
    )
    await session.flush()
    await pause_for_approval(
        session,
        run_id=writer_run.id,
        step_key="final_review",
        artifact_id=final_artifact.id,
    )
    await session.flush()

    detail = await get_action_aware_review_case(
        session,
        content_case_id=content_case.id,
    )
    panel = detail.locales[0]
    assert panel.next_action == "AWAITING_FOUNDER_APPROVAL"
    assert panel.content_item_id == item.id
    assert panel.final_content is not None
    assert panel.final_content.id == final_artifact.id
    return PendingReviewFixture(
        content_case_id=content_case.id,
        variant=variant,
        writer_run=writer_run,
        final_artifact=final_artifact,
        current_audit=current_audit,
    )


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
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
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
            content_case_id=fixture.content_case_id,
        )
        panel = detail.locales[0]
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
                content_case_id=fixture.content_case_id,
                locale_variant_id=fixture.variant.id,
                decision="changes_requested",
                actor_id="founder",
                comment="",
            )
        assert await _counts(session) == before

        result = await submit_review_decision(
            session,
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
            decision="changes_requested",
            actor_id="founder",
            comment="Rút gọn đoạn mở đầu.",
        )
        after = await _counts(session)
        assert after == (before[0] + 1, before[1])
        assert result.writer_run_status == "running"
        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case_id,
        )
        panel = detail.locales[0]
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
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
            decision="rejected",
            actor_id="founder",
            comment="Không phù hợp định hướng.",
        )
        after = await _counts(session)
        assert after == (before[0] + 1, before[1])
        assert result.writer_run_status == "cancelled"
        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case_id,
        )
        panel = detail.locales[0]
        assert panel.consistency_state == "CONSISTENT"
        assert panel.next_action == "REJECTED"


@pytest.mark.asyncio
async def test_review_action_exact_replay_creates_no_duplicate() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        first = await submit_review_decision(
            session,
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
            decision="approved",
            actor_id="founder",
            comment="Duyệt.",
        )
        counts = await _counts(session)
        replay = await submit_review_decision(
            session,
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
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
        payload = dict(fixture.current_audit.content_json or {})
        summary = dict(payload["summary"])
        summary["result"] = "fail"
        summary["critical_unsupported_count"] = 1
        payload["summary"] = summary
        fixture.current_audit.content_json = payload
        await session.flush()
        before = await _counts(session)
        with pytest.raises(ReviewActionError, match="review_action_quality_blocked"):
            await submit_review_decision(
                session,
                content_case_id=fixture.content_case_id,
                locale_variant_id=fixture.variant.id,
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
