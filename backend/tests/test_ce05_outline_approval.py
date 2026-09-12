from __future__ import annotations

import pytest

from test_ce05_outline import (
    FakeOutlineModel,
    _approved_fixture,
    _generate,
    _outline_payload,
    isolated_session,
)

from app.modules.content_engine.journal.outline_approval import (
    OutlineApprovalError,
    approve_outline_artifact,
    handoff_approved_outline,
)


@pytest.mark.asyncio
async def test_outline_approval_is_exact_idempotent_and_handoff_verified() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        result = await _generate(
            session,
            fixture,
            FakeOutlineModel([_outline_payload(fixture.bundle)]),
        )
        fixture.run.status = "waiting_approval"
        await session.flush()

        kwargs = {
            "session": session,
            "outline_artifact_id": result.artifact.id,
            "expected_artifact_version": result.artifact.version,
            "expected_artifact_hash": result.artifact.content_hash,
            "approved_by": "founder",
            "approval_reason": "Founder approved the exact persisted Outline after review.",
        }
        first = await approve_outline_artifact(**kwargs)
        second = await approve_outline_artifact(**kwargs)
        assert second.id == first.id

        handoff = await handoff_approved_outline(
            session,
            outline_artifact_id=result.artifact.id,
            expected_artifact_version=result.artifact.version,
            expected_artifact_hash=result.artifact.content_hash,
            expected_approval_id=first.id,
        )
        assert handoff.artifact.id == result.artifact.id
        assert handoff.approval.id == first.id
        assert handoff.approval.run_id == fixture.run.id


@pytest.mark.asyncio
async def test_outline_approval_rejects_conflicting_human_decision() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        result = await _generate(
            session,
            fixture,
            FakeOutlineModel([_outline_payload(fixture.bundle)]),
        )
        fixture.run.status = "waiting_approval"
        await session.flush()

        await approve_outline_artifact(
            session,
            outline_artifact_id=result.artifact.id,
            expected_artifact_version=result.artifact.version,
            expected_artifact_hash=result.artifact.content_hash,
            approved_by="founder",
            approval_reason="Founder approved the exact persisted Outline after review.",
        )
        with pytest.raises(OutlineApprovalError, match="outline_approval_conflict"):
            await approve_outline_artifact(
                session,
                outline_artifact_id=result.artifact.id,
                expected_artifact_version=result.artifact.version,
                expected_artifact_hash=result.artifact.content_hash,
                approved_by="founder",
                approval_reason="Different decision text must not replace the immutable approval.",
            )


@pytest.mark.asyncio
async def test_outline_handoff_fails_without_or_with_stale_approval() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        result = await _generate(
            session,
            fixture,
            FakeOutlineModel([_outline_payload(fixture.bundle)]),
        )
        fixture.run.status = "waiting_approval"
        await session.flush()

        with pytest.raises(OutlineApprovalError, match="outline_approval_required"):
            await handoff_approved_outline(
                session,
                outline_artifact_id=result.artifact.id,
                expected_artifact_version=result.artifact.version,
                expected_artifact_hash=result.artifact.content_hash,
                expected_approval_id=fixture.approval.id,
            )

        approval = await approve_outline_artifact(
            session,
            outline_artifact_id=result.artifact.id,
            expected_artifact_version=result.artifact.version,
            expected_artifact_hash=result.artifact.content_hash,
            approved_by="founder",
            approval_reason="Founder approved the exact persisted Outline after review.",
        )
        with pytest.raises(OutlineApprovalError, match="outline_approval_snapshot_stale"):
            await handoff_approved_outline(
                session,
                outline_artifact_id=result.artifact.id,
                expected_artifact_version=result.artifact.version,
                expected_artifact_hash="0" * 64,
                expected_approval_id=approval.id,
            )
