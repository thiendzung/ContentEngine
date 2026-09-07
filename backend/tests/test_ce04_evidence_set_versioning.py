from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import ContentOpportunity, NeedHypothesis, Project
from app.modules.knowledge.models import EvidenceSet
from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    PageDocument,
    ProductionResearchRequest,
    ProductionResearchResult,
    SourceCandidate,
)
from app.modules.research.evidence.contracts import ClaimCandidate, EvidenceRelation
from app.modules.research.evidence.persistence import (
    create_or_reuse_evidence_set,
    ensure_selected_content_case,
    lock_evidence_set,
    persist_claim_evidence,
    persist_read_documents,
)


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
async def test_locked_evidence_set_versions_forward_when_research_changes() -> None:
    async with isolated_session() as session:
        project = (
            await session.execute(select(Project).where(Project.slug == "motgu"))
        ).scalar_one()
        need = NeedHypothesis(
            project_id=project.id,
            type="question",
            statement="How can a buyer evaluate an artwork price?",
            audience_scope="first-time buyer",
            situation="considering a purchase",
            origin="founder_proposed",
            status="PROPOSED",
            alternative_explanations_json=[],
            missing_evidence_json=[],
        )
        session.add(need)
        await session.flush()
        opportunity = ContentOpportunity(
            project_id=project.id,
            need_hypothesis_id=need.id,
            locale="en",
            reader="first-time buyer",
            situation="considering a purchase",
            need="evaluate price",
            question="How can a buyer evaluate an artwork price?",
            intent="learn",
            promise="provide grounded context",
            motgu_material_refs_json=[],
            material_gaps_json=[],
            existing_content_refs_json=[],
            what_is_actually_new="buyer price evaluation",
            next_discovery_step="evidence research",
            decision="CREATE",
            priority="NOW",
            reasons_json=[],
            suggested_content_type="journal",
            selected_by="founder",
            selected_at=datetime.now(UTC),
            selection_reason="selected",
        )
        session.add(opportunity)
        await session.flush()
        content_case, _, _ = await ensure_selected_content_case(
            session,
            project_id=project.id,
            content_opportunity_id=opportunity.id,
            need_hypothesis_id=need.id,
        )

        source_url = "https://example.test/evidence-set"
        source = SourceCandidate(
            provider="serper",
            query="artwork price",
            url=source_url,
            title="Evidence source",
            source_type="institutional",
            commercial_bias=CommercialBias.LOW,
            intended_use=IntendedUse.EVIDENCE_CANDIDATE,
        )
        production = ProductionResearchResult(
            request=ProductionResearchRequest(
                project_id=project.id,
                query="artwork price",
                max_pages_to_read=1,
            ),
            source_candidates=[source],
            selected_sources=[source],
            documents=[
                PageDocument(
                    provider="jina",
                    url=source_url,
                    content=(
                        "Artwork price can depend on information about the work and its context. "
                        "A buyer can ask for supporting details before deciding."
                    ),
                )
            ],
            stop_reason="serper_sufficient",
            sufficient=True,
        )
        page_refs = await persist_read_documents(session, production=production)
        first_link = await persist_claim_evidence(
            session,
            project_id=project.id,
            page_refs=page_refs,
            candidate=ClaimCandidate(
                statement="Artwork price can depend on information about the work and its context.",
                source_url=source_url,
                locator="sentence:1",
                excerpt=(
                    "Artwork price can depend on information about the work and its context."
                ),
                relation=EvidenceRelation.SUPPORTS,
            ),
        )
        v1 = await create_or_reuse_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=[first_link.evidence_id],
        )
        v1 = await lock_evidence_set(
            session,
            evidence_set_id=v1.id,
            locked_by="reviewer",
        )

        same_v1 = await create_or_reuse_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=[first_link.evidence_id],
        )
        assert same_v1.id == v1.id
        assert same_v1.status == "locked"

        second_link = await persist_claim_evidence(
            session,
            project_id=project.id,
            page_refs=page_refs,
            candidate=ClaimCandidate(
                statement="A buyer can ask for supporting details before deciding.",
                source_url=source_url,
                locator="sentence:2",
                excerpt="A buyer can ask for supporting details before deciding.",
                relation=EvidenceRelation.QUALIFIES,
            ),
        )
        v2 = await create_or_reuse_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=[first_link.evidence_id, second_link.evidence_id],
        )

        assert v1.version == 1
        assert v1.status == "locked"
        assert v2.id != v1.id
        assert v2.version == 2
        assert v2.status == "draft"
        assert v2.content_hash != v1.content_hash

        locked_v2 = await lock_evidence_set(
            session,
            evidence_set_id=v2.id,
            locked_by="reviewer",
        )
        assert locked_v2.status == "locked"
        stored_v1 = await session.get(EvidenceSet, v1.id)
        assert stored_v1 is not None
        assert stored_v1.version == 1
        assert stored_v1.locked_by == "reviewer"
