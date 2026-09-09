from __future__ import annotations

import copy
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from evidence_set_helpers import create_locked_evidence_set
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    NeedHypothesis,
    Project,
)
from app.modules.harness.models import ContentRun
from app.modules.knowledge.admission import (
    KnowledgeCandidateAdmissionError,
    admit_knowledge_candidate,
    verify_candidate_snapshot_lineage,
)
from app.modules.knowledge.candidates import extract_knowledge_candidates
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    EvidenceSet,
    KnowledgeCandidate,
    KnowledgeChunk,
    Source,
    SourceDocument,
)
from app.modules.knowledge.persistence import content_hash


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


@dataclass
class ProvenanceFixture:
    project: Project
    content_case: ContentCase
    claim: Claim
    evidence: Evidence
    evidence_set: EvidenceSet
    source: Source
    document: SourceDocument
    alternate_source: Source


async def _provenance_fixture(
    session: AsyncSession,
    *,
    via_chunk: bool = False,
) -> ProvenanceFixture:
    project = Project(
        slug=f"provenance-test-{uuid4().hex}",
        name="Knowledge provenance test project",
        status="active",
        default_locale="en",
    )
    session.add(project)
    await session.flush()

    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement="A buyer wants to evaluate an original artwork price.",
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
        need="evaluate artwork price",
        question="How can a buyer evaluate an artwork price?",
        intent="learn",
        promise="provide grounded context",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="buyer price evaluation",
        next_discovery_step="provenance review",
        decision="CREATE",
        priority="NOW",
        reasons_json=[],
        suggested_content_type="journal",
        selected_by="founder",
        selected_at=datetime.now(UTC),
        selection_reason="synthetic provenance fixture",
    )
    session.add(opportunity)
    await session.flush()

    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="evaluate an artwork price",
        content_hypothesis="grounded price evaluation",
        originality_statement="use reviewed sources carefully",
        reader_before="uncertain about an artwork price",
        reader_after="able to evaluate the price with context",
        status="draft",
    )
    source = Source(
        project_id=project.id,
        source_type="web",
        title="Persisted provenance source",
        publisher="Synthetic Authority",
        canonical_url=f"https://example.test/provenance/{uuid4()}",
        locator="section:valuation",
        locale="en",
        commercial_bias="low",
        authority_hint="high",
        provenance_json={"method": "synthetic_fixture"},
        captured_at=datetime.now(UTC),
        fingerprint=str(uuid4()),
    )
    alternate_source = Source(
        project_id=project.id,
        source_type="web",
        title="Alternate provenance source",
        canonical_url=f"https://example.test/alternate/{uuid4()}",
        locator="section:alternate",
        locale="en",
        commercial_bias="low",
        authority_hint="high",
        provenance_json={"method": "synthetic_fixture"},
        captured_at=datetime.now(UTC),
        fingerprint=str(uuid4()),
    )
    session.add_all([content_case, source, alternate_source])
    await session.flush()

    excerpt = "The persisted source explains how market context informs a price assessment."
    document_text = f"Opening context.\n\n{excerpt}\n\nClosing context."
    document = SourceDocument(
        source_id=source.id,
        document_version=1,
        canonical_url=source.canonical_url,
        fetched_at=datetime.now(UTC),
        content_hash=content_hash(document_text),
        content_markdown=document_text,
        metadata_json={"fixture": "persisted_source_document"},
        reader="synthetic_fixture",
        provider="fixture",
    )
    claim = Claim(
        project_id=project.id,
        statement="Market context is part of assessing whether an artwork price is reasonable.",
        claim_type="fact",
        importance="high",
        status="unverified",
        entity_refs_json=["entity:artwork", "entity:buyer"],
    )
    session.add_all([document, claim])
    await session.flush()

    chunk_id: UUID | None = None
    if via_chunk:
        chunk = KnowledgeChunk(
            source_document_id=document.id,
            ordinal=0,
            text=excerpt,
            token_estimate=14,
            fingerprint=content_hash(excerpt),
            status="active",
            metadata_json={"fixture": "knowledge_chunk"},
        )
        session.add(chunk)
        await session.flush()
        chunk_id = chunk.id

    evidence = Evidence(
        claim_id=claim.id,
        source_document_id=None if via_chunk else document.id,
        chunk_id=chunk_id,
        locator="section:valuation",
        excerpt=excerpt,
        relation="supports",
        authority_level="primary",
        quality_metadata_json={"fixture": True},
        provenance_json={
            "method": "synthetic_fixture",
            "source_id": str(source.id),
            "source_document_id": str(document.id),
            "locator": "section:valuation",
        },
    )
    session.add(evidence)
    await session.flush()

    evidence_set = await create_locked_evidence_set(
        session,
        project_id=project.id,
        content_case_id=content_case.id,
        version=1,
        evidence_ids=[str(evidence.id)],
        locked_by="synthetic reviewer",
    )
    return ProvenanceFixture(
        project=project,
        content_case=content_case,
        claim=claim,
        evidence=evidence,
        evidence_set=evidence_set,
        source=source,
        document=document,
        alternate_source=alternate_source,
    )


async def _approved_candidate(
    session: AsyncSession,
    fixture: ProvenanceFixture,
) -> KnowledgeCandidate:
    candidate = (
        await extract_knowledge_candidates(
            session,
            evidence_set_id=fixture.evidence_set.id,
        )
    )[0]
    return await admit_knowledge_candidate(
        session,
        candidate_id=candidate.id,
        decision="approve",
        reviewer="MG CONTENT ENGINE",
        review_reason="Synthetic end-to-end provenance review.",
        expected_candidate_content_hash=cast(
            str, candidate.provenance_json["candidate_content_hash"]
        ),
    )


def _provenance(candidate: KnowledgeCandidate) -> dict[str, Any]:
    return cast(dict[str, Any], candidate.provenance_json)


@pytest.mark.asyncio
async def test_approved_candidate_traces_to_exact_source() -> None:
    async with isolated_session() as session:
        fixture = await _provenance_fixture(session)
        candidate = await _approved_candidate(session, fixture)

        snapshot, candidate_hash = await verify_candidate_snapshot_lineage(
            session,
            candidate=candidate,
        )
        provenance = _provenance(candidate)
        evidence_set_data = cast(dict[str, Any], provenance["evidence_set"])
        evidence_set = await session.get(EvidenceSet, UUID(evidence_set_data["id"]))
        claim = await session.get(Claim, UUID(provenance["claim_id"]))
        assert evidence_set is fixture.evidence_set
        assert evidence_set is not None
        assert evidence_set.status == "locked"
        assert evidence_set.version == evidence_set_data["version"]
        assert evidence_set.content_hash == evidence_set_data["content_hash"]
        assert claim is fixture.claim
        assert claim is not None
        assert claim.project_id == candidate.project_id == evidence_set.project_id
        assert snapshot["statement"] == claim.statement == candidate.statement
        assert candidate_hash == provenance["candidate_content_hash"]

        evidence_ids = [UUID(value) for value in provenance["evidence_ids"]]
        evidence_set_ids = {UUID(value) for value in evidence_set.evidence_ids_json}
        assert set(evidence_ids) == evidence_set_ids
        evidence_refs = {
            UUID(cast(dict[str, Any], value)["evidence_id"]): cast(dict[str, Any], value)
            for value in provenance["evidence_refs"]
        }
        resolved_document_ids: set[UUID] = set()
        resolved_source_ids: set[UUID] = set()
        for evidence_id in evidence_ids:
            evidence = await session.get(Evidence, evidence_id)
            assert evidence is not None
            assert evidence.claim_id == claim.id
            evidence_ref = evidence_refs[evidence_id]
            assert evidence.relation == evidence_ref["relation"]
            assert evidence.locator == evidence_ref["locator"]
            document = await session.get(SourceDocument, evidence.source_document_id)
            assert document is not None
            source = await session.get(Source, document.source_id)
            assert source is not None
            assert source.project_id == candidate.project_id == evidence_set.project_id
            assert document.source_id == source.id
            assert source.canonical_url
            assert source.locator
            assert document.canonical_url == source.canonical_url
            assert evidence.excerpt in document.content_markdown
            resolved_document_ids.add(document.id)
            resolved_source_ids.add(source.id)
            assert evidence_ref["source_document_ids"] == [str(document.id)]
            assert evidence_ref["source_ids"] == [str(source.id)]

        assert provenance["source_document_ids"] == [
            str(value) for value in sorted(resolved_document_ids, key=str)
        ]
        assert provenance["source_ids"] == [
            str(value) for value in sorted(resolved_source_ids, key=str)
        ]
        assert candidate.source_refs_json == [
            f"source:{value}" for value in sorted(resolved_source_ids, key=str)
        ]


@pytest.mark.asyncio
async def test_knowledge_chunk_evidence_traces_to_source() -> None:
    async with isolated_session() as session:
        fixture = await _provenance_fixture(session, via_chunk=True)
        candidate = await _approved_candidate(session, fixture)

        provenance = _provenance(candidate)
        evidence = await session.get(Evidence, fixture.evidence.id)
        assert evidence is not None
        assert evidence.source_document_id is None
        assert evidence.chunk_id is not None
        chunk = await session.get(KnowledgeChunk, evidence.chunk_id)
        assert chunk is not None
        document = await session.get(SourceDocument, chunk.source_document_id)
        assert document is not None
        source = await session.get(Source, document.source_id)
        assert source is not None
        assert provenance["source_document_ids"] == [str(document.id)]
        assert provenance["source_ids"] == [str(source.id)]
        assert evidence.excerpt in document.content_markdown
        assert source.canonical_url


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["version", "content_hash"])
async def test_tampered_evidence_set_lineage_fails(field: str) -> None:
    async with isolated_session() as session:
        fixture = await _provenance_fixture(session)
        candidate = await _approved_candidate(session, fixture)
        candidate_provenance = copy.deepcopy(_provenance(candidate))
        evidence_set_data = candidate_provenance["evidence_set"]
        if field == "version":
            evidence_set_data[field] = 2
        else:
            evidence_set_data[field] = "0" * 64
        candidate.provenance_json = candidate_provenance

        with pytest.raises(KnowledgeCandidateAdmissionError):
            await verify_candidate_snapshot_lineage(session, candidate=candidate)


@pytest.mark.asyncio
async def test_tampered_evidence_id_fails() -> None:
    async with isolated_session() as session:
        fixture = await _provenance_fixture(session)
        candidate = await _approved_candidate(session, fixture)
        candidate_provenance = copy.deepcopy(_provenance(candidate))
        candidate_provenance["evidence_ids"] = [str(uuid4())]
        candidate.provenance_json = candidate_provenance

        with pytest.raises(KnowledgeCandidateAdmissionError):
            await verify_candidate_snapshot_lineage(session, candidate=candidate)


@pytest.mark.asyncio
async def test_tampered_source_document_id_fails() -> None:
    async with isolated_session() as session:
        fixture = await _provenance_fixture(session)
        candidate = await _approved_candidate(session, fixture)
        candidate_provenance = copy.deepcopy(_provenance(candidate))
        evidence_ref = candidate_provenance["evidence_refs"][0]
        evidence_ref["source_document_ids"] = [str(uuid4())]
        candidate.provenance_json = candidate_provenance

        with pytest.raises(KnowledgeCandidateAdmissionError):
            await verify_candidate_snapshot_lineage(session, candidate=candidate)


@pytest.mark.asyncio
async def test_tampered_source_id_and_source_ref_fail() -> None:
    async with isolated_session() as session:
        fixture = await _provenance_fixture(session)
        candidate = await _approved_candidate(session, fixture)
        candidate_provenance = copy.deepcopy(_provenance(candidate))
        candidate_provenance["source_ids"] = [str(fixture.alternate_source.id)]
        candidate.source_refs_json = [f"source:{fixture.alternate_source.id}"]
        candidate.provenance_json = candidate_provenance

        with pytest.raises(KnowledgeCandidateAdmissionError):
            await verify_candidate_snapshot_lineage(session, candidate=candidate)


@pytest.mark.asyncio
async def test_tampered_source_refs_fail() -> None:
    async with isolated_session() as session:
        fixture = await _provenance_fixture(session)
        candidate = await _approved_candidate(session, fixture)
        candidate.source_refs_json = ["source:tampered"]

        with pytest.raises(KnowledgeCandidateAdmissionError):
            await verify_candidate_snapshot_lineage(session, candidate=candidate)


@pytest.mark.asyncio
async def test_changed_persisted_claim_statement_fails() -> None:
    async with isolated_session() as session:
        fixture = await _provenance_fixture(session)
        candidate = await _approved_candidate(session, fixture)
        fixture.claim.statement = "A changed persisted claim is not the approved snapshot."
        await session.flush()

        with pytest.raises(KnowledgeCandidateAdmissionError, match="candidate_snapshot_stale"):
            await verify_candidate_snapshot_lineage(session, candidate=candidate)


@pytest.mark.asyncio
async def test_changed_persisted_evidence_locator_and_provenance_fail() -> None:
    async with isolated_session() as session:
        fixture = await _provenance_fixture(session)
        candidate = await _approved_candidate(session, fixture)
        fixture.evidence.locator = "section:changed"
        fixture.evidence.provenance_json = {"method": "changed_fixture"}
        await session.flush()

        with pytest.raises(KnowledgeCandidateAdmissionError, match="candidate_snapshot_stale"):
            await verify_candidate_snapshot_lineage(session, candidate=candidate)


@pytest.mark.asyncio
async def test_changed_source_document_linkage_fails() -> None:
    async with isolated_session() as session:
        fixture = await _provenance_fixture(session)
        candidate = await _approved_candidate(session, fixture)
        fixture.document.source_id = fixture.alternate_source.id
        await session.flush()

        with pytest.raises(KnowledgeCandidateAdmissionError, match="candidate_snapshot_stale"):
            await verify_candidate_snapshot_lineage(session, candidate=candidate)


async def _counts(session: AsyncSession) -> dict[str, int]:
    tables = {
        "candidates": KnowledgeCandidate,
        "evidence_sets": EvidenceSet,
        "claims": Claim,
        "evidence": Evidence,
        "documents": SourceDocument,
        "sources": Source,
    }
    return {
        name: int(await session.scalar(select(func.count()).select_from(model)))
        for name, model in tables.items()
    }


@pytest.mark.asyncio
async def test_lineage_verification_is_read_only_and_provider_free() -> None:
    async with isolated_session() as session:
        fixture = await _provenance_fixture(session)
        candidate = await _approved_candidate(session, fixture)
        before_counts = await _counts(session)
        before_status = candidate.status
        before_provenance = copy.deepcopy(candidate.provenance_json)
        before_o4_runs = int(
            await session.scalar(
                select(func.count()).select_from(ContentRun).where(
                    ContentRun.content_case_id
                    == UUID("9ec6133b-5f14-46d0-9866-e3b049e537b5")
                )
            )
        )

        snapshot, _candidate_hash = await verify_candidate_snapshot_lineage(
            session,
            candidate=candidate,
        )

        assert snapshot["evidence_set"]["id"] == str(fixture.evidence_set.id)
        assert candidate.status == before_status == "APPROVED"
        assert candidate.provenance_json == before_provenance
        assert await _counts(session) == before_counts
        assert (
            await session.scalar(
                select(func.count()).select_from(ContentRun).where(
                    ContentRun.content_case_id
                    == UUID("9ec6133b-5f14-46d0-9866-e3b049e537b5")
                )
            )
            == before_o4_runs
        )
