from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.knowledge.freshness import record_lineage_verification
from app.modules.knowledge.freshness_models import FreshnessVerification
from app.modules.knowledge.ingest import ingest_source_document, register_source
from app.modules.knowledge.models import Claim, Evidence

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


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


async def add_source_evidence(
    session: AsyncSession,
    *,
    project: Project,
    claim: Claim,
    label: str,
) -> tuple[UUID, str]:
    source_url = f"https://example.test/k2-multisource/{label}/{uuid4()}"
    source = (
        await register_source(
            session,
            project_id=project.id,
            source_type="web",
            canonical_url=source_url,
            provenance_json={"source_ref": source_url, "method": "k2-multisource-test"},
            captured_at=T0,
            locale="en",
            authority_hint="high",
            commercial_bias="low",
        )
    ).source
    text = f"Independent source {label} supports the synthetic multi-source claim."
    ingested = await ingest_source_document(
        session,
        source_id=source.id,
        content_markdown=text,
        fetched_at=T0,
        canonical_url=source_url,
        reader="k2-multisource-test",
        provider="manual",
    )
    session.add(
        Evidence(
            claim_id=claim.id,
            source_document_id=ingested.document.id,
            chunk_id=ingested.chunks[0].id,
            locator=f"source:{label}",
            excerpt=text,
            relation="supports",
            authority_level="high",
            quality_metadata_json={"source_type": "web"},
            provenance_json={
                "method": "read_excerpt_link",
                "source_id": str(source.id),
                "source_document_id": str(ingested.document.id),
                "source_document_hash": ingested.document.content_hash,
            },
            verified_at=T0,
        )
    )
    await session.flush()
    return source.id, text


@pytest.mark.asyncio
async def test_partial_reread_does_not_advance_or_conflict_multisource_frontier() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        claim = Claim(
            project_id=project.id,
            subject_entity_id=None,
            statement=f"Synthetic multi-source K2 claim {uuid4()}",
            claim_type="fact",
            importance="normal",
            status="unverified",
            confidence=None,
            entity_refs_json=[],
        )
        session.add(claim)
        await session.flush()

        source_a, text_a = await add_source_evidence(
            session,
            project=project,
            claim=claim,
            label="a",
        )
        source_b, text_b = await add_source_evidence(
            session,
            project=project,
            claim=claim,
            label="b",
        )

        first = await record_lineage_verification(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            recorded_by="policy:k2-lineage",
            as_of=T0,
        )
        assert first.verified_at == T0

        await ingest_source_document(
            session,
            source_id=source_a,
            content_markdown=text_a,
            fetched_at=T0 + timedelta(days=10),
            reader="k2-multisource-test",
            provider="manual",
        )
        partial = await record_lineage_verification(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            recorded_by="policy:k2-lineage",
            as_of=T0 + timedelta(days=10),
        )
        assert partial.id == first.id
        assert partial.verified_at == T0
        assert (
            await session.scalar(
                select(func.count())
                .select_from(FreshnessVerification)
                .where(FreshnessVerification.claim_id == claim.id)
            )
        ) == 1

        await ingest_source_document(
            session,
            source_id=source_b,
            content_markdown=text_b,
            fetched_at=T0 + timedelta(days=20),
            reader="k2-multisource-test",
            provider="manual",
        )
        advanced = await record_lineage_verification(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            recorded_by="policy:k2-lineage",
            as_of=T0 + timedelta(days=20),
        )
        assert advanced.id != first.id
        assert advanced.verified_at == T0 + timedelta(days=10)
        assert (
            await session.scalar(
                select(func.count())
                .select_from(FreshnessVerification)
                .where(FreshnessVerification.claim_id == claim.id)
            )
        ) == 2
