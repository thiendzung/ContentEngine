from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.research.contracts import PageDocument, ProductionResearchRequest, ProductionResearchResult
from app.modules.research.evidence.contracts import ClaimCandidate, EvidenceRelation
from app.modules.research.evidence.persistence import persist_claim_evidence, persist_read_documents


@asynccontextmanager
async def isolated_session():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_evidence_service_preserves_all_relation_types() -> None:
    async with isolated_session() as session:
        project = (
            await session.execute(select(Project).where(Project.slug == "motgu"))
        ).scalar_one()
        source_url = "https://example.test/relation-source"
        excerpt = "Artwork pricing context can differ between works and artists."
        production = ProductionResearchResult(
            request=ProductionResearchRequest(
                project_id=project.id,
                query="artwork pricing context",
                max_pages_to_read=1,
            ),
            documents=[
                PageDocument(
                    provider="jina",
                    url=source_url,
                    content=excerpt,
                )
            ],
            stop_reason="test",
            sufficient=True,
        )
        page_refs = await persist_read_documents(session, production=production)

        persisted = []
        for relation in EvidenceRelation:
            persisted.append(
                await persist_claim_evidence(
                    session,
                    project_id=project.id,
                    page_refs=page_refs,
                    candidate=ClaimCandidate(
                        statement=f"relation test: {relation.value}",
                        source_url=source_url,
                        locator=f"relation:{relation.value}",
                        excerpt=excerpt,
                        relation=relation,
                    ),
                )
            )

        assert {link.relation for link in persisted} == set(EvidenceRelation)
