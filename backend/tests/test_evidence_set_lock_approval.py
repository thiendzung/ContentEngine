from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.harness.models import Approval, Artifact, ContentRun
from app.modules.knowledge.evidence_set_approval import approve_evidence_set
from app.modules.knowledge.models import EvidenceSet, EvidenceSetApproval, OriginalityPack
from app.modules.knowledge.persistence import evidence_set_hash
from app.modules.research.contracts import ProductionResearchRequest
from app.modules.research.evidence.contracts import EvidenceResearchRequest
from app.modules.research.evidence.persistence import lock_evidence_set
from app.modules.research.evidence.service import EvidenceResearchWorkflow

HISTORICAL_V8_ID = UUID("c5d46edb-3557-4efb-a479-8dd5702ae6c9")


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
        slug=f"evidence-set-lock-{uuid4()}",
        name="EvidenceSet lock test",
        status="active",
        default_locale="en",
    )
    ids = evidence_ids if evidence_ids is not None else [str(uuid4())]
    evidence_set = EvidenceSet(
        id=uuid4(),
        project_id=project.id,
        version=1,
        evidence_ids_json=ids,
        content_hash=evidence_set_hash(ids),
        status="draft",
    )
    session.add_all([project, evidence_set])
    await session.flush()
    return evidence_set


async def _approval(
    session: AsyncSession, evidence_set: EvidenceSet
) -> EvidenceSetApproval:
    return await approve_evidence_set(
        session,
        evidence_set_id=evidence_set.id,
        expected_version=evidence_set.version,
        expected_content_hash=evidence_set.content_hash,
        approved_by="MG CONTENT ENGINE",
        approval_reason="Exact snapshot reviewed for lock.",
    )


async def _count(session: AsyncSession, model: type[object]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


@pytest.mark.asyncio
async def test_draft_without_approval_is_rejected_and_exact_approval_locks() -> None:
    async with isolated_session() as session:
        evidence_set = await _draft_evidence_set(session)
        with pytest.raises(ValueError, match="evidence_set_approval_required"):
            await lock_evidence_set(
                session,
                evidence_set_id=evidence_set.id,
                locked_by="reviewer",
            )
        assert evidence_set.status == "draft"

        approval = await _approval(session, evidence_set)
        before = {
            "id": approval.id,
            "version": approval.evidence_set_version,
            "hash": approval.evidence_set_content_hash,
            "approved_by": approval.approved_by,
            "reason": approval.approval_reason,
            "approved_at": approval.approved_at,
        }
        locked = await lock_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            locked_by="reviewer",
            approval_id=approval.id,
        )

        assert locked.status == "locked"
        assert locked.evidence_ids_json == evidence_set.evidence_ids_json
        assert locked.version == evidence_set.version
        assert locked.content_hash == evidence_set.content_hash
        assert locked.locked_by == "reviewer"
        assert locked.locked_at is not None
        refreshed = await session.get(EvidenceSetApproval, approval.id)
        assert refreshed is not None
        assert {
            "id": refreshed.id,
            "version": refreshed.evidence_set_version,
            "hash": refreshed.evidence_set_content_hash,
            "approved_by": refreshed.approved_by,
            "reason": refreshed.approval_reason,
            "approved_at": refreshed.approved_at,
        } == before


@pytest.mark.asyncio
async def test_new_evidence_set_must_start_as_clean_draft() -> None:
    async with isolated_session() as session:
        draft = await _draft_evidence_set(session)
        base_values = {
            "id": uuid4(),
            "project_id": draft.project_id,
            "version": 2,
            "evidence_ids_json": [str(uuid4())],
            "content_hash": evidence_set_hash([str(uuid4())]),
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        raw_variants = (
            {**base_values, "status": "locked", "locked_at": datetime.now(UTC)},
            {**base_values, "id": uuid4(), "status": "draft", "locked_at": datetime.now(UTC)},
            {**base_values, "id": uuid4(), "status": "draft", "locked_by": "reviewer"},
        )
        for values in raw_variants:
            with pytest.raises(DBAPIError, match="evidence_set_must_start_draft"):
                async with session.begin_nested():
                    await session.execute(insert(EvidenceSet).values(**values))

        orm_locked = EvidenceSet(
            id=uuid4(),
            project_id=draft.project_id,
            version=3,
            evidence_ids_json=[str(uuid4())],
            content_hash=draft.content_hash,
            status="locked",
            locked_at=datetime.now(UTC),
            locked_by="reviewer",
        )
        with pytest.raises(DBAPIError, match="evidence_set_must_start_draft"):
            async with session.begin_nested():
                session.add(orm_locked)
                await session.flush()

        normal = await _draft_evidence_set(session)
        assert normal.status == "draft"
        assert normal.locked_at is None
        assert normal.locked_by is None


@pytest.mark.asyncio
async def test_approval_id_validation_rejects_missing_wrong_set_version_hash_and_id() -> None:
    async with isolated_session() as session:
        first = await _draft_evidence_set(session)
        second = await _draft_evidence_set(session)
        first_approval = await _approval(session, first)

        with pytest.raises(ValueError, match="evidence_set_approval_not_found"):
            await lock_evidence_set(
                session,
                evidence_set_id=first.id,
                locked_by="reviewer",
                approval_id=uuid4(),
            )
        with pytest.raises(ValueError, match="evidence_set_approval_set_mismatch"):
            await lock_evidence_set(
                session,
                evidence_set_id=second.id,
                locked_by="reviewer",
                approval_id=first_approval.id,
            )

        wrong_version = EvidenceSetApproval(
            id=uuid4(),
            evidence_set_id=second.id,
            evidence_set_version=2,
            evidence_set_content_hash=second.content_hash,
            approved_by="reviewer",
            approval_reason="wrong version fixture",
            approved_at=datetime.now(UTC),
        )
        wrong_hash = EvidenceSetApproval(
            id=uuid4(),
            evidence_set_id=second.id,
            evidence_set_version=second.version,
            evidence_set_content_hash="0" * 64,
            approved_by="reviewer",
            approval_reason="wrong hash fixture",
            approved_at=datetime.now(UTC),
        )
        session.add_all([wrong_version, wrong_hash])
        await session.flush()
        with pytest.raises(ValueError, match="evidence_set_approval_version_mismatch"):
            await lock_evidence_set(
                session,
                evidence_set_id=second.id,
                locked_by="reviewer",
                approval_id=wrong_version.id,
            )
        with pytest.raises(ValueError, match="evidence_set_approval_hash_mismatch"):
            await lock_evidence_set(
                session,
                evidence_set_id=second.id,
                locked_by="reviewer",
                approval_id=wrong_hash.id,
            )
        assert second.status == "draft"


@pytest.mark.asyncio
async def test_corrupt_set_hash_and_changed_ids_cannot_be_locked_with_old_approval() -> None:
    async with isolated_session() as session:
        corrupt = await _draft_evidence_set(session)
        await session.execute(
            update(EvidenceSet)
            .where(EvidenceSet.id == corrupt.id)
            .values(content_hash="f" * 64)
        )
        with pytest.raises(ValueError, match="evidence_set_content_hash_invalid"):
            await lock_evidence_set(
                session,
                evidence_set_id=corrupt.id,
                locked_by="reviewer",
                approval_id=uuid4(),
            )

        evidence_set = await _draft_evidence_set(session)
        approval = await _approval(session, evidence_set)
        with pytest.raises(DBAPIError, match="approved_evidence_set_snapshot_is_immutable"):
            async with session.begin_nested():
                await session.execute(
                    update(EvidenceSet)
                    .where(EvidenceSet.id == evidence_set.id)
                    .values(evidence_ids_json=[str(uuid4())])
                )
        assert approval.evidence_set_content_hash == evidence_set.content_hash


@pytest.mark.asyncio
async def test_approved_snapshot_fields_are_database_immutable() -> None:
    async with isolated_session() as session:
        evidence_set = await _draft_evidence_set(session)
        await _approval(session, evidence_set)
        other_project = Project(
            id=uuid4(),
            slug=f"evidence-set-lock-other-{uuid4()}",
            name="Other project",
            status="active",
            default_locale="en",
        )
        session.add(other_project)
        await session.flush()

        mutations = (
            {"version": 2},
            {"evidence_ids_json": [str(uuid4())]},
            {"content_hash": "f" * 64},
            {"project_id": other_project.id},
            {"content_case_id": uuid4()},
        )
        for values in mutations:
            with pytest.raises(
                DBAPIError, match="approved_evidence_set_snapshot_is_immutable"
            ):
                async with session.begin_nested():
                    await session.execute(
                        update(EvidenceSet)
                        .where(EvidenceSet.id == evidence_set.id)
                        .values(**values)
                    )
        assert evidence_set.status == "draft"


@pytest.mark.asyncio
async def test_raw_sql_lock_requires_approval_but_exact_approval_succeeds() -> None:
    async with isolated_session() as session:
        evidence_set = await _draft_evidence_set(session)
        lock_values = {
            "status": "locked",
            "locked_at": datetime.now(UTC),
            "locked_by": "raw-reviewer",
        }
        with pytest.raises(DBAPIError, match="evidence_set_lock_requires_exact_approval"):
            async with session.begin_nested():
                await session.execute(
                    update(EvidenceSet)
                    .where(EvidenceSet.id == evidence_set.id)
                    .values(**lock_values)
                )
        assert evidence_set.status == "draft"

        await _approval(session, evidence_set)
        async with session.begin_nested():
            await session.execute(
                update(EvidenceSet)
                .where(EvidenceSet.id == evidence_set.id)
                .values(**lock_values)
            )
        assert evidence_set.status == "locked"


@pytest.mark.asyncio
async def test_lock_validation_has_no_harness_side_effects() -> None:
    async with isolated_session() as session:
        evidence_set = await _draft_evidence_set(session)
        before = {
            "harness_approvals": await _count(session, Approval),
            "runs": await _count(session, ContentRun),
            "artifacts": await _count(session, Artifact),
            "packs": await _count(session, OriginalityPack),
        }
        await _approval(session, evidence_set)
        await lock_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            locked_by="reviewer",
            approval_id=(
                await session.scalar(
                    select(EvidenceSetApproval.id).where(
                        EvidenceSetApproval.evidence_set_id == evidence_set.id
                    )
                )
            ),
        )
        assert before == {
            "harness_approvals": await _count(session, Approval),
            "runs": await _count(session, ContentRun),
            "artifacts": await _count(session, Artifact),
            "packs": await _count(session, OriginalityPack),
        }


def test_locking_research_request_requires_approval_id() -> None:
    workflow = EvidenceResearchWorkflow(router=object())  # type: ignore[arg-type]
    request = EvidenceResearchRequest(
        research=ProductionResearchRequest(project_id=uuid4(), query="test"),
        content_opportunity_id=uuid4(),
        need_hypothesis_id=uuid4(),
        lock_evidence_set=True,
        locked_by="reviewer",
    )
    with pytest.raises(
        ValueError,
        match="evidence_set_approval_required_when_locking_evidence_set",
    ):
        workflow._validate_request(request, run_id=None, step_run_id=None)


@pytest.mark.asyncio
async def test_historical_o4_v8_is_not_retrofit_with_approval() -> None:
    async with isolated_session() as session:
        evidence_set = await session.get(EvidenceSet, HISTORICAL_V8_ID)
        if evidence_set is None:
            pytest.skip("isolated database has no real O4 EvidenceSet v8")
        assert evidence_set.status == "locked"
        approval_count = await session.scalar(
            select(func.count()).select_from(EvidenceSetApproval).where(
                EvidenceSetApproval.evidence_set_id == HISTORICAL_V8_ID
            )
        )
        assert approval_count == 0
