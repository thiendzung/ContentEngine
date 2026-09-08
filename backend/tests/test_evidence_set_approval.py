from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.harness.models import Approval, Artifact, ContentRun
from app.modules.knowledge.evidence_set_approval import (
    EvidenceSetApprovalError,
    approve_evidence_set,
)
from app.modules.knowledge.models import EvidenceSet, EvidenceSetApproval
from app.modules.knowledge.persistence import evidence_set_hash


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


async def _draft_evidence_set(
    session: AsyncSession, *, evidence_ids: list[str] | None = None
) -> EvidenceSet:
    project = Project(
        id=uuid4(),
        slug=f"evidence-set-approval-{uuid4()}",
        name="EvidenceSet approval test",
        status="active",
        default_locale="en",
    )
    ids = evidence_ids if evidence_ids is not None else [str(uuid4())]
    evidence_set = EvidenceSet(
        project_id=project.id,
        version=1,
        evidence_ids_json=ids,
        content_hash=evidence_set_hash(ids),
        status="draft",
    )
    session.add_all([project, evidence_set])
    await session.flush()
    return evidence_set


async def _count(session: AsyncSession, model: type[object]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def _approve(session: AsyncSession, evidence_set: EvidenceSet) -> EvidenceSetApproval:
    return await approve_evidence_set(
        session,
        evidence_set_id=evidence_set.id,
        expected_version=evidence_set.version,
        expected_content_hash=evidence_set.content_hash,
        approved_by="MG CONTENT ENGINE",
        approval_reason="Exact draft snapshot has been reviewed.",
    )


@pytest.mark.asyncio
async def test_approval_creates_exact_draft_binding_without_harness_side_effects() -> None:
    async with isolated_session() as session:
        evidence_set = await _draft_evidence_set(session)
        before = {
            "approvals": await _count(session, Approval),
            "runs": await _count(session, ContentRun),
            "artifacts": await _count(session, Artifact),
        }

        approval = await _approve(session, evidence_set)

        assert approval.evidence_set_id == evidence_set.id
        assert approval.evidence_set_version == evidence_set.version
        assert approval.evidence_set_content_hash == evidence_set.content_hash
        assert approval.approved_by == "MG CONTENT ENGINE"
        assert approval.approval_reason == "Exact draft snapshot has been reviewed."
        assert approval.approved_at.tzinfo is not None
        assert evidence_set.status == "draft"
        assert evidence_set.locked_at is None
        assert evidence_set.locked_by is None
        assert before == {
            "approvals": await _count(session, Approval),
            "runs": await _count(session, ContentRun),
            "artifacts": await _count(session, Artifact),
        }


@pytest.mark.asyncio
async def test_wrong_version_or_hash_creates_no_approval() -> None:
    async with isolated_session() as session:
        evidence_set = await _draft_evidence_set(session)
        before = await _count(session, EvidenceSetApproval)

        with pytest.raises(
            EvidenceSetApprovalError,
            match="evidence_set_approval_version_mismatch",
        ):
            await approve_evidence_set(
                session,
                evidence_set_id=evidence_set.id,
                expected_version=2,
                expected_content_hash=evidence_set.content_hash,
                approved_by="reviewer",
                approval_reason="reason",
            )
        with pytest.raises(EvidenceSetApprovalError, match="evidence_set_approval_hash_mismatch"):
            await approve_evidence_set(
                session,
                evidence_set_id=evidence_set.id,
                expected_version=1,
                expected_content_hash="0" * 64,
                approved_by="reviewer",
                approval_reason="reason",
            )

        assert await _count(session, EvidenceSetApproval) == before


@pytest.mark.asyncio
async def test_corrupt_stored_hash_or_empty_evidence_set_is_rejected() -> None:
    async with isolated_session() as session:
        evidence_set = await _draft_evidence_set(session)
        evidence_set.content_hash = "f" * 64
        await session.flush()
        with pytest.raises(EvidenceSetApprovalError, match="evidence_set_content_hash_invalid"):
            await _approve(session, evidence_set)

        empty_set = await _draft_evidence_set(session, evidence_ids=[])
        with pytest.raises(
            EvidenceSetApprovalError,
            match="evidence_set_approval_requires_evidence",
        ):
            await _approve(session, empty_set)
        assert await _count(session, EvidenceSetApproval) == 0


@pytest.mark.asyncio
async def test_exact_repeat_is_idempotent_but_conflicts_cannot_overwrite() -> None:
    async with isolated_session() as session:
        evidence_set = await _draft_evidence_set(session)
        first = await _approve(session, evidence_set)
        repeated = await _approve(session, evidence_set)

        assert repeated.id == first.id
        assert await _count(session, EvidenceSetApproval) == 1
        with pytest.raises(EvidenceSetApprovalError, match="evidence_set_approval_conflict"):
            await approve_evidence_set(
                session,
                evidence_set_id=evidence_set.id,
                expected_version=evidence_set.version,
                expected_content_hash=evidence_set.content_hash,
                approved_by="different reviewer",
                approval_reason="Exact draft snapshot has been reviewed.",
            )
        assert await _count(session, EvidenceSetApproval) == 1


@pytest.mark.asyncio
async def test_actor_and_reason_are_required() -> None:
    async with isolated_session() as session:
        evidence_set = await _draft_evidence_set(session)
        with pytest.raises(EvidenceSetApprovalError, match="evidence_set_approver_required"):
            await approve_evidence_set(
                session,
                evidence_set_id=evidence_set.id,
                expected_version=1,
                expected_content_hash=evidence_set.content_hash,
                approved_by=" ",
                approval_reason="reason",
            )
        with pytest.raises(EvidenceSetApprovalError, match="evidence_set_approval_reason_required"):
            await approve_evidence_set(
                session,
                evidence_set_id=evidence_set.id,
                expected_version=1,
                expected_content_hash=evidence_set.content_hash,
                approved_by="reviewer",
                approval_reason=" ",
            )
        assert await _count(session, EvidenceSetApproval) == 0


@pytest.mark.asyncio
async def test_locked_evidence_set_cannot_receive_retrofit_approval() -> None:
    async with isolated_session() as session:
        evidence_set = await _draft_evidence_set(session)
        evidence_set.status = "locked"
        evidence_set.locked_at = datetime.now(UTC)
        evidence_set.locked_by = "MG CONTENT ENGINE"
        await session.flush()

        with pytest.raises(
            EvidenceSetApprovalError,
            match="evidence_set_approval_requires_draft_evidence_set",
        ):
            await _approve(session, evidence_set)
        assert await _count(session, EvidenceSetApproval) == 0


@pytest.mark.asyncio
async def test_database_trigger_makes_approval_row_immutable() -> None:
    async with isolated_session() as session:
        evidence_set = await _draft_evidence_set(session)
        approval = await _approve(session, evidence_set)

        with pytest.raises(DBAPIError, match="evidence_set_approval_is_immutable"):
            async with session.begin_nested():
                await session.execute(
                    update(EvidenceSetApproval)
                    .where(EvidenceSetApproval.id == approval.id)
                    .values(approved_by="altered")
                )
        with pytest.raises(DBAPIError, match="evidence_set_approval_is_immutable"):
            async with session.begin_nested():
                await session.execute(
                    delete(EvidenceSetApproval).where(EvidenceSetApproval.id == approval.id)
                )

        assert await _count(session, EvidenceSetApproval) == 1
