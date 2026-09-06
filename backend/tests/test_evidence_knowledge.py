from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    NeedHypothesis,
    Project,
)
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    EvidenceSet,
    KnowledgeCandidate,
    KnowledgeChunk,
    OriginalityPack,
    Source,
    SourceDocument,
)
from app.modules.knowledge.persistence import (
    content_hash,
    stable_chunk_fingerprint,
    stable_chunk_id,
    stable_document_id,
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


def source_row(project: Project, fingerprint: str = "source-fingerprint") -> Source:
    return Source(
        project_id=project.id,
        source_type="manual_document",
        title="Approved source",
        canonical_url="https://example.test/source",
        locator="page-1",
        locale="en",
        provenance_json={"source_ref": "manual:source-1", "method": "test"},
        captured_at=datetime.now(UTC),
        fingerprint=fingerprint,
    )


async def motgu_project(session: AsyncSession) -> Project:
    return (await session.execute(select(Project).where(Project.slug == "motgu"))).scalar_one()


@pytest.mark.asyncio
async def test_source_and_document_duplicates_are_rejected() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        source = source_row(project)
        session.add(source)
        await session.flush()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(source_row(project))
                await session.flush()

        document = SourceDocument(
            source_id=source.id,
            document_version=1,
            canonical_url=source.canonical_url,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash("same content"),
            content_markdown="same content",
            metadata_json={},
            reader="test",
            provider="manual",
        )
        session.add(document)
        await session.flush()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    SourceDocument(
                        source_id=source.id,
                        document_version=2,
                        fetched_at=datetime.now(UTC),
                        content_hash=document.content_hash,
                        content_markdown=document.content_markdown,
                        metadata_json={},
                    )
                )
                await session.flush()


def test_document_and_chunk_hashes_are_stable() -> None:
    assert content_hash("document") == content_hash("document")
    source_id = uuid4()
    document_hash = content_hash("document")
    assert stable_document_id(
        source_id=source_id, document_content_hash=document_hash
    ) == stable_document_id(source_id=source_id, document_content_hash=document_hash)
    document_id = uuid4()
    assert stable_chunk_id(
        source_document_id=document_id, text="chunk", ordinal=0
    ) == stable_chunk_id(source_document_id=document_id, text="chunk", ordinal=0)
    assert stable_chunk_fingerprint(text="chunk", ordinal=0) == stable_chunk_fingerprint(
        text="chunk", ordinal=0
    )
    assert stable_chunk_fingerprint(text="chunk", ordinal=0) != stable_chunk_fingerprint(
        text="chunk", ordinal=1
    )


@pytest.mark.asyncio
async def test_evidence_supports_and_contradicts_keep_provenance() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        source = source_row(project, fingerprint=f"evidence-{uuid4().hex}")
        session.add(source)
        await session.flush()
        document = SourceDocument(
            source_id=source.id,
            document_version=1,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash("evidence document"),
            content_markdown="evidence document",
            metadata_json={},
        )
        session.add(document)
        await session.flush()
        claim = Claim(
            project_id=project.id,
            statement="A test claim",
            claim_type="fact",
            importance="high",
            status="unverified",
            entity_refs_json=[],
        )
        session.add(claim)
        await session.flush()
        for relation in ("supports", "contradicts"):
            session.add(
                Evidence(
                    claim_id=claim.id,
                    source_document_id=document.id,
                    locator="p.1",
                    excerpt=f"{relation} excerpt",
                    relation=relation,
                    quality_metadata_json={"quality": "test"},
                    provenance_json={"source_document_id": str(document.id), "method": "reader"},
                )
            )
        await session.flush()
        relations = set((await session.execute(select(Evidence.relation))).scalars())
        assert relations >= {"supports", "contradicts"}
        assert (await session.execute(select(Evidence.provenance_json))).first() is not None


@pytest.mark.asyncio
async def test_search_signal_is_not_an_evidence_source_and_candidate_stays_unapproved() -> None:
    assert "signal_id" not in Evidence.__table__.columns
    async with isolated_session() as session:
        project = await motgu_project(session)
        candidate = KnowledgeCandidate(
            project_id=project.id,
            statement="Candidate statement",
            summary="Candidate summary",
            source_refs_json=["source:1"],
            provenance_json={"method": "test"},
            entity_refs_json=[],
            status="CANDIDATE",
        )
        session.add(candidate)
        await session.flush()
        assert candidate.status == "CANDIDATE"


@pytest.mark.asyncio
async def test_locked_evidence_set_is_immutable_and_new_research_uses_new_version() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        evidence_set = EvidenceSet(
            project_id=project.id,
            version=1,
            evidence_ids_json=["evidence:1"],
            content_hash=content_hash("evidence:1"),
            status="locked",
            locked_at=datetime.now(UTC),
            locked_by="reviewer",
        )
        session.add(evidence_set)
        await session.flush()
        with pytest.raises(DBAPIError, match="locked_evidence_set_is_immutable"):
            async with session.begin_nested():
                await session.execute(
                    EvidenceSet.__table__.update()
                    .where(EvidenceSet.id == evidence_set.id)
                    .values(evidence_ids_json=["evidence:2"])
                )
        with pytest.raises(DBAPIError, match="locked_evidence_set_is_immutable"):
            async with session.begin_nested():
                await session.delete(evidence_set)
                await session.flush()
        replacement = EvidenceSet(
            project_id=project.id,
            version=2,
            evidence_ids_json=["evidence:2"],
            content_hash=content_hash("evidence:2"),
            status="locked",
            locked_at=datetime.now(UTC),
            locked_by="reviewer",
        )
        session.add(replacement)
        await session.flush()
        assert replacement.version == 2


@pytest.mark.asyncio
async def test_originality_pack_can_reference_real_evidence_and_knowledge_chunk() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        source = source_row(project, fingerprint=f"originality-{uuid4().hex}")
        session.add(source)
        await session.flush()
        document = SourceDocument(
            source_id=source.id,
            document_version=1,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash("MOTGU process detail"),
            content_markdown="MOTGU process detail",
            metadata_json={},
        )
        session.add(document)
        await session.flush()
        chunk = KnowledgeChunk(
            source_document_id=document.id,
            ordinal=0,
            text="MOTGU process detail",
            fingerprint=stable_chunk_fingerprint(text="MOTGU process detail", ordinal=0),
            metadata_json={},
        )
        session.add(chunk)
        await session.flush()
        need = NeedHypothesis(
            project_id=project.id,
            type="question",
            statement="How?",
            audience_scope="reader",
            situation="research",
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
            reader="reader",
            situation="research",
            need="need",
            question="How?",
            intent="learn",
            promise="help",
            motgu_material_refs_json=[],
            material_gaps_json=[],
            existing_content_refs_json=[],
            what_is_actually_new="new",
            next_discovery_step="review",
            decision="CREATE",
            priority="NEXT",
            reasons_json=[],
            suggested_content_type="journal",
        )
        session.add(opportunity)
        await session.flush()
        content_case = ContentCase(
            project_id=project.id,
            content_type="journal",
            need_hypothesis_id=need.id,
            content_opportunity_id=opportunity.id,
            desired_action="learn",
            content_hypothesis="test",
            originality_statement="test",
            reader_before="uncertain",
            reader_after="clear",
        )
        session.add(content_case)
        claim = Claim(
            project_id=project.id,
            statement="Process detail",
            claim_type="fact",
            importance="normal",
            status="unverified",
            entity_refs_json=[],
        )
        session.add(claim)
        await session.flush()
        evidence = Evidence(
            claim_id=claim.id,
            source_document_id=document.id,
            chunk_id=chunk.id,
            locator="p.1",
            excerpt="MOTGU process detail",
            relation="supports",
            quality_metadata_json={},
            provenance_json={"source_document_id": str(document.id)},
        )
        session.add(evidence)
        await session.flush()
        pack = OriginalityPack(
            content_case_id=content_case.id,
            item_refs_json=[
                {"type": "evidence", "id": str(evidence.id)},
                {"type": "knowledge_chunk", "id": str(chunk.id)},
            ],
            summary="First-party process detail grounded in evidence.",
            status="draft",
        )
        session.add(pack)
        await session.flush()
        assert {item["type"] for item in pack.item_refs_json} == {"evidence", "knowledge_chunk"}
