from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.knowledge.freshness import ensure_freshness_policy
from app.modules.knowledge.freshness_models import (
    FreshnessAssignment,
    FreshnessVerification,
    SourceDocumentObservation,
)
from app.modules.knowledge.ingest import ingest_source_document, register_source
from app.modules.knowledge.models import Claim


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


async def motgu_project(session: AsyncSession) -> Project:
    return (await session.execute(select(Project).where(Project.slug == "motgu"))).scalar_one()


async def add_other_project(session: AsyncSession) -> Project:
    project = Project(
        slug=f"k2-other-{uuid4().hex}",
        name="K2 Other Project",
        status="active",
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


@pytest.mark.asyncio
async def test_database_rejects_cross_project_assignment_and_multiple_targets() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        other = await add_other_project(session)
        policy = await ensure_freshness_policy(
            session,
            project_id=project.id,
            policy_key=f"db-guard-{uuid4().hex}",
            version=1,
            freshness_class="medium",
            max_age_days=60,
            refresh_lead_days=10,
            created_by="founder",
            rationale="K2 DB guard",
        )
        foreign_claim = Claim(
            project_id=other.id,
            subject_entity_id=None,
            statement=f"Foreign K2 claim {uuid4()}",
            claim_type="fact",
            importance="normal",
            status="unverified",
            confidence=None,
            entity_refs_json=[],
        )
        local_claim = Claim(
            project_id=project.id,
            subject_entity_id=None,
            statement=f"Local K2 claim {uuid4()}",
            claim_type="fact",
            importance="normal",
            status="unverified",
            confidence=None,
            entity_refs_json=[],
        )
        session.add_all([foreign_claim, local_claim])
        await session.flush()

        with pytest.raises(DBAPIError, match="freshness_assignment_target_project_mismatch"):
            async with session.begin_nested():
                session.add(
                    FreshnessAssignment(
                        project_id=project.id,
                        policy_id=policy.id,
                        topic_id=None,
                        claim_id=foreign_claim.id,
                        knowledge_candidate_id=None,
                        status="active",
                        assigned_by="test",
                        reason="cross-project must fail",
                        supersedes_id=None,
                        retired_at=None,
                        retired_by=None,
                        retirement_reason=None,
                    )
                )
                await session.flush()

        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    FreshnessAssignment(
                        project_id=project.id,
                        policy_id=policy.id,
                        topic_id=None,
                        claim_id=local_claim.id,
                        knowledge_candidate_id=uuid4(),
                        status="active",
                        assigned_by="test",
                        reason="multiple targets must fail",
                        supersedes_id=None,
                        retired_at=None,
                        retired_by=None,
                        retirement_reason=None,
                    )
                )
                await session.flush()


@pytest.mark.asyncio
async def test_database_rejects_policy_payload_mutation_and_observation_hash_mismatch() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        policy = await ensure_freshness_policy(
            session,
            project_id=project.id,
            policy_key=f"immutable-{uuid4().hex}",
            version=1,
            freshness_class="medium",
            max_age_days=60,
            refresh_lead_days=10,
            created_by="founder",
            rationale="Immutable policy test",
        )
        policy.max_age_days = 30
        with pytest.raises(DBAPIError, match="freshness_policy_is_immutable"):
            async with session.begin_nested():
                await session.flush()
        await session.refresh(policy)

        source_url = f"https://example.test/k2-db/{uuid4()}"
        source = (
            await register_source(
                session,
                project_id=project.id,
                source_type="web",
                canonical_url=source_url,
                provenance_json={"source_ref": source_url},
                captured_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        ).source
        document = (
            await ingest_source_document(
                session,
                source_id=source.id,
                content_markdown="K2 database guard source.",
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
                provider="manual",
                reader="test",
            )
        ).document
        with pytest.raises(DBAPIError, match="source_document_observation_hash_mismatch"):
            async with session.begin_nested():
                session.add(
                    SourceDocumentObservation(
                        source_document_id=document.id,
                        observed_at=datetime(2026, 1, 2, tzinfo=UTC),
                        content_hash="0" * 64,
                        provider="manual",
                        reader="test",
                        observation_method="document_ingest",
                    )
                )
                await session.flush()


@pytest.mark.asyncio
async def test_database_rejects_freshness_verification_update() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        claim = Claim(
            project_id=project.id,
            subject_entity_id=None,
            statement=f"Verification guard claim {uuid4()}",
            claim_type="fact",
            importance="normal",
            status="unverified",
            confidence=None,
            entity_refs_json=[],
        )
        session.add(claim)
        await session.flush()
        verification = FreshnessVerification(
            project_id=project.id,
            claim_id=claim.id,
            knowledge_candidate_id=None,
            basis_hash="a" * 64,
            verified_at=datetime(2026, 1, 1, tzinfo=UTC),
            evidence_ids_json=[],
            source_documents_json=[],
            observation_ids_json=[],
            verification_method="lineage_snapshot",
            recorded_by="test",
        )
        session.add(verification)
        await session.flush()
        verification.recorded_by = "changed"
        with pytest.raises(DBAPIError, match="freshness_verification_is_immutable"):
            async with session.begin_nested():
                await session.flush()
