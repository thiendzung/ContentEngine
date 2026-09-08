from __future__ import annotations

import inspect
import subprocess
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

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
from app.modules.knowledge.candidates import (
    EXTRACTION_METHOD,
    deterministic_candidate_summary,
    extract_knowledge_candidates,
    stable_knowledge_candidate_id,
)
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    EvidenceSet,
    KnowledgeCandidate,
    Source,
    SourceDocument,
)
from app.modules.knowledge.persistence import content_hash


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


@dataclass
class CandidateFixture:
    project: Project
    content_case: ContentCase
    claim: Claim
    evidence_set: EvidenceSet
    evidence: list[Evidence]
    source: Source
    document: SourceDocument


async def _new_project(session: AsyncSession) -> Project:
    project = Project(
        slug=f"candidate-test-{uuid4().hex}",
        name="Candidate extraction test project",
        status="active",
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


async def _candidate_fixture(
    session: AsyncSession,
    *,
    relations: tuple[str, ...] = ("supports",),
    claim_project: Project | None = None,
    case_project: Project | None = None,
    evidence_set_status: str = "locked",
    evidence_set_version: int = 8,
    evidence_ids_override: list[str] | None = None,
) -> CandidateFixture:
    project = (
        await session.execute(select(Project).where(Project.slug == "motgu"))
    ).scalar_one()
    case_project = case_project or project
    claim_project = claim_project or project

    need = NeedHypothesis(
        project_id=case_project.id,
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
        project_id=case_project.id,
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
        next_discovery_step="evidence review",
        decision="CREATE",
        priority="NOW",
        reasons_json=[],
        suggested_content_type="journal",
        selected_by="founder",
        selected_at=datetime.now(UTC),
        selection_reason="test selection",
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=case_project.id,
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
    session.add(content_case)
    await session.flush()

    source = Source(
        project_id=project.id,
        source_type="web",
        title="Candidate extraction fixture source",
        canonical_url=f"https://example.test/candidate/{uuid4()}",
        locale="en",
        commercial_bias="low",
        authority_hint="high",
        provenance_json={"method": "fixture"},
        captured_at=datetime.now(UTC),
        fingerprint=str(uuid4()),
    )
    session.add(source)
    await session.flush()
    document_text = "A persisted source document excerpt for candidate extraction."
    document = SourceDocument(
        source_id=source.id,
        document_version=1,
        canonical_url=source.canonical_url,
        fetched_at=datetime.now(UTC),
        content_hash=content_hash(document_text),
        content_markdown=document_text,
        metadata_json={},
        reader="fixture",
        provider="fixture",
    )
    claim = Claim(
        project_id=claim_project.id,
        statement="A buyer can evaluate an artwork price using documented context.",
        claim_type="fact",
        importance="high",
        status="unverified",
        entity_refs_json=["entity:artwork", "entity:buyer"],
    )
    session.add_all([document, claim])
    await session.flush()

    evidence = [
        Evidence(
            claim_id=claim.id,
            source_document_id=document.id,
            locator=f"fixture:{index}",
            excerpt=document_text,
            relation=relation,
            quality_metadata_json={"fixture": True},
            provenance_json={
                "method": "fixture",
                "source_id": str(source.id),
                "source_document_id": str(document.id),
                "raw_payload": "must not be copied into a candidate",
            },
        )
        for index, relation in enumerate(relations, start=1)
    ]
    session.add_all(evidence)
    await session.flush()

    evidence_ids = evidence_ids_override or [str(row.id) for row in evidence]
    if evidence_set_status == "locked":
        evidence_set = await create_locked_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            version=evidence_set_version,
            evidence_ids=evidence_ids,
            locked_by="fixture reviewer",
        )
    else:
        evidence_set = EvidenceSet(
            project_id=project.id,
            content_case_id=content_case.id,
            version=evidence_set_version,
            evidence_ids_json=evidence_ids,
            content_hash=content_hash(f"fixture-evidence-set-{uuid4()}"),
            status=evidence_set_status,
        )
        session.add(evidence_set)
        await session.flush()
    return CandidateFixture(
        project=project,
        content_case=content_case,
        claim=claim,
        evidence_set=evidence_set,
        evidence=evidence,
        source=source,
        document=document,
    )


@pytest.mark.asyncio
async def test_locked_supported_claim_becomes_candidate_with_full_provenance() -> None:
    async with isolated_session() as session:
        fixture = await _candidate_fixture(
            session,
            relations=("supports", "contradicts", "qualifies", "context_only"),
        )
        original_set = (
            fixture.evidence_set.version,
            fixture.evidence_set.content_hash,
            list(fixture.evidence_set.evidence_ids_json),
            fixture.evidence_set.status,
        )

        candidates = await extract_knowledge_candidates(
            session,
            evidence_set_id=fixture.evidence_set.id,
        )

        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.project_id == fixture.project.id
        assert candidate.locale == "en"
        assert candidate.statement == fixture.claim.statement
        assert candidate.entity_refs_json == fixture.claim.entity_refs_json
        assert candidate.status == "CANDIDATE"
        assert candidate.reviewer is None
        assert candidate.review_reason is None
        assert candidate.source_refs_json == [f"source:{fixture.source.id}"]
        assert candidate.summary == deterministic_candidate_summary(
            statement=fixture.claim.statement,
            relation_counts={
                "supports": 1,
                "contradicts": 1,
                "qualifies": 1,
                "context_only": 1,
            },
        )

        provenance = candidate.provenance_json
        assert provenance["method"] == EXTRACTION_METHOD
        assert provenance["evidence_set"] == {
            "id": str(fixture.evidence_set.id),
            "version": fixture.evidence_set.version,
            "content_hash": fixture.evidence_set.content_hash,
        }
        assert provenance["claim_id"] == str(fixture.claim.id)
        assert provenance["evidence_ids"] == sorted(str(row.id) for row in fixture.evidence)
        assert provenance["source_document_ids"] == [str(fixture.document.id)]
        assert provenance["source_ids"] == [str(fixture.source.id)]
        assert provenance["relation_counts"] == {
            "supports": 1,
            "contradicts": 1,
            "qualifies": 1,
            "context_only": 1,
        }
        assert provenance["evidence_refs"][0]["provenance"]["method"] == "fixture"
        assert "raw_payload" not in str(provenance)
        assert isinstance(provenance["candidate_content_hash"], str)
        assert candidate.id == stable_knowledge_candidate_id(
            candidate_content_hash=provenance["candidate_content_hash"]
        )
        assert (
            fixture.evidence_set.version,
            fixture.evidence_set.content_hash,
            fixture.evidence_set.evidence_ids_json,
            fixture.evidence_set.status,
        ) == original_set


@pytest.mark.asyncio
async def test_supported_claim_never_auto_approves() -> None:
    async with isolated_session() as session:
        fixture = await _candidate_fixture(session)
        candidate = (
            await extract_knowledge_candidates(
                session,
                evidence_set_id=fixture.evidence_set.id,
            )
        )[0]

        assert candidate.status == "CANDIDATE"
        assert candidate.status != "APPROVED"
        assert candidate.reviewer is None
        assert candidate.review_reason is None


@pytest.mark.asyncio
@pytest.mark.parametrize("relation", ["contradicts", "qualifies", "context_only"])
async def test_non_support_only_claim_does_not_create_candidate(relation: str) -> None:
    async with isolated_session() as session:
        initial_count = await session.scalar(
            select(func.count()).select_from(KnowledgeCandidate)
        )
        fixture = await _candidate_fixture(session, relations=(relation,))

        candidates = await extract_knowledge_candidates(
            session,
            evidence_set_id=fixture.evidence_set.id,
        )

        assert candidates == []
        assert (
            await session.scalar(select(func.count()).select_from(KnowledgeCandidate))
            == initial_count
        )


@pytest.mark.asyncio
async def test_draft_evidence_set_is_rejected() -> None:
    async with isolated_session() as session:
        fixture = await _candidate_fixture(session, evidence_set_status="draft")

        with pytest.raises(ValueError, match="candidate_requires_locked_evidence_set"):
            await extract_knowledge_candidates(
                session,
                evidence_set_id=fixture.evidence_set.id,
            )


@pytest.mark.asyncio
async def test_same_exact_snapshot_reuses_candidate() -> None:
    async with isolated_session() as session:
        initial_count = await session.scalar(
            select(func.count()).select_from(KnowledgeCandidate)
        )
        fixture = await _candidate_fixture(session)

        first = (
            await extract_knowledge_candidates(
                session,
                evidence_set_id=fixture.evidence_set.id,
            )
        )[0]
        second = (
            await extract_knowledge_candidates(
                session,
                evidence_set_id=fixture.evidence_set.id,
            )
        )[0]

        assert second.id == first.id
        assert second.provenance_json == first.provenance_json
        assert (
            await session.scalar(select(func.count()).select_from(KnowledgeCandidate))
            == initial_count + 1
        )


@pytest.mark.asyncio
async def test_changed_claim_snapshot_creates_new_candidate_instead_of_stale_reuse() -> None:
    async with isolated_session() as session:
        initial_count = await session.scalar(
            select(func.count()).select_from(KnowledgeCandidate)
        )
        fixture = await _candidate_fixture(session)

        first = (
            await extract_knowledge_candidates(
                session,
                evidence_set_id=fixture.evidence_set.id,
            )
        )[0]
        fixture.claim.statement = "A changed claim snapshot requires a new candidate."
        second = (
            await extract_knowledge_candidates(
                session,
                evidence_set_id=fixture.evidence_set.id,
            )
        )[0]

        assert second.id != first.id
        assert first.statement != second.statement
        assert (
            await session.scalar(select(func.count()).select_from(KnowledgeCandidate))
            == initial_count + 2
        )


@pytest.mark.asyncio
async def test_evidence_claim_from_wrong_project_is_rejected() -> None:
    async with isolated_session() as session:
        wrong_project = await _new_project(session)
        fixture = await _candidate_fixture(session, claim_project=wrong_project)

        with pytest.raises(ValueError, match="candidate_claim_project_mismatch"):
            await extract_knowledge_candidates(
                session,
                evidence_set_id=fixture.evidence_set.id,
            )


@pytest.mark.asyncio
async def test_content_case_from_wrong_project_is_rejected() -> None:
    async with isolated_session() as session:
        wrong_project = await _new_project(session)
        fixture = await _candidate_fixture(session, case_project=wrong_project)

        with pytest.raises(ValueError, match="candidate_content_case_project_mismatch"):
            await extract_knowledge_candidates(
                session,
                evidence_set_id=fixture.evidence_set.id,
            )


@pytest.mark.asyncio
async def test_missing_evidence_row_is_rejected() -> None:
    async with isolated_session() as session:
        fixture = await _candidate_fixture(
            session,
            evidence_ids_override=[str(uuid4())],
        )

        with pytest.raises(ValueError, match="candidate_evidence_not_found"):
            await extract_knowledge_candidates(
                session,
                evidence_set_id=fixture.evidence_set.id,
            )


def test_extraction_accepts_only_an_evidence_set_id_and_no_raw_provider_input() -> None:
    parameters = tuple(inspect.signature(extract_knowledge_candidates).parameters)
    assert parameters == ("session", "evidence_set_id")

    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/extract_knowledge_candidates.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--evidence-set-id" in completed.stdout
    assert "--raw" not in completed.stdout
    assert "SearchSignal" not in completed.stdout
