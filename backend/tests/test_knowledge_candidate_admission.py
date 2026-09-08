from __future__ import annotations

import copy
import inspect
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    NeedHypothesis,
    Project,
)
from app.modules.harness.models import Approval, Artifact, ContentRun
from app.modules.knowledge.admission import (
    KnowledgeCandidateAdmissionError,
    admit_knowledge_candidate,
)
from app.modules.knowledge.candidates import extract_knowledge_candidates
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    EvidenceSet,
    KnowledgeCandidate,
    OriginalityPack,
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
class AdmissionFixture:
    candidate: KnowledgeCandidate
    evidence_set: EvidenceSet
    originality_pack: OriginalityPack


async def _admission_fixture(session: AsyncSession) -> AdmissionFixture:
    project = (
        await session.execute(select(Project).where(Project.slug == "motgu"))
    ).scalar_one()
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
        next_discovery_step="candidate admission",
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
    session.add(content_case)
    await session.flush()

    source = Source(
        project_id=project.id,
        source_type="web",
        title="Admission fixture source",
        canonical_url=f"https://example.test/admission/{uuid4()}",
        locale="en",
        commercial_bias="low",
        authority_hint="high",
        provenance_json={"method": "fixture"},
        captured_at=datetime.now(UTC),
        fingerprint=str(uuid4()),
    )
    session.add(source)
    await session.flush()
    document_text = "A persisted source document excerpt for admission."
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
        project_id=project.id,
        statement="A buyer can evaluate an artwork price using documented context.",
        claim_type="fact",
        importance="high",
        status="unverified",
        entity_refs_json=["entity:artwork", "entity:buyer"],
    )
    session.add_all([document, claim])
    await session.flush()
    evidence = Evidence(
        claim_id=claim.id,
        source_document_id=document.id,
        locator="fixture:1",
        excerpt=document_text,
        relation="supports",
        quality_metadata_json={"fixture": True},
        provenance_json={
            "method": "fixture",
            "source_id": str(source.id),
            "source_document_id": str(document.id),
        },
    )
    session.add(evidence)
    await session.flush()
    evidence_set = EvidenceSet(
        project_id=project.id,
        content_case_id=content_case.id,
        version=8,
        evidence_ids_json=[str(evidence.id)],
        content_hash=content_hash("admission-evidence-set"),
        status="locked",
        locked_at=datetime.now(UTC),
        locked_by="fixture reviewer",
    )
    originality_pack = OriginalityPack(
        content_case_id=content_case.id,
        item_refs_json=[{"type": "motgu_owned_material", "material": "fixture"}],
        summary="Fixture originality pack",
        status="draft",
    )
    session.add_all([evidence_set, originality_pack])
    await session.flush()
    candidate = (
        await extract_knowledge_candidates(
            session,
            evidence_set_id=evidence_set.id,
        )
    )[0]
    return AdmissionFixture(
        candidate=candidate,
        evidence_set=evidence_set,
        originality_pack=originality_pack,
    )


def _valid_args(candidate: KnowledgeCandidate, *, decision: str = "approve") -> dict[str, object]:
    return {
        "candidate_id": candidate.id,
        "decision": decision,
        "reviewer": "MG CONTENT ENGINE",
        "review_reason": "Reviewed against the locked EvidenceSet snapshot.",
        "expected_candidate_content_hash": candidate.provenance_json[
            "candidate_content_hash"
        ],
    }


async def _admit(
    session: AsyncSession,
    candidate: KnowledgeCandidate,
    **overrides: object,
) -> KnowledgeCandidate:
    arguments = _valid_args(candidate)
    arguments.update(overrides)
    return await admit_knowledge_candidate(
        session,
        candidate_id=cast(UUID, arguments["candidate_id"]),
        decision=cast(str, arguments["decision"]),
        reviewer=cast(str, arguments["reviewer"]),
        review_reason=cast(str, arguments["review_reason"]),
        expected_candidate_content_hash=cast(
            str, arguments["expected_candidate_content_hash"]
        ),
    )


@pytest.mark.asyncio
async def test_candidate_approve_transitions_to_approved() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)

        result = await _admit(session, fixture.candidate)

        assert result.status == "APPROVED"
        assert result.reviewer == "MG CONTENT ENGINE"
        assert result.review_reason == "Reviewed against the locked EvidenceSet snapshot."


@pytest.mark.asyncio
async def test_candidate_reject_transitions_to_rejected() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)

        result = await _admit(session, fixture.candidate, decision="reject")

        assert result.status == "REJECTED"
        assert result.reviewer == "MG CONTENT ENGINE"
        assert result.review_reason is not None


@pytest.mark.asyncio
async def test_reviewer_is_required() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)

        with pytest.raises(KnowledgeCandidateAdmissionError, match="reviewer_required"):
            await _admit(session, fixture.candidate, reviewer=" ")


@pytest.mark.asyncio
async def test_review_reason_is_required() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)

        with pytest.raises(KnowledgeCandidateAdmissionError, match="review_reason_required"):
            await _admit(session, fixture.candidate, review_reason=" ")


@pytest.mark.asyncio
async def test_expected_hash_is_required() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)

        with pytest.raises(
            KnowledgeCandidateAdmissionError,
            match="expected_content_hash_required",
        ):
            await _admit(session, fixture.candidate, expected_candidate_content_hash=" ")


@pytest.mark.asyncio
async def test_wrong_expected_hash_is_rejected() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)

        with pytest.raises(KnowledgeCandidateAdmissionError, match="content_hash_mismatch"):
            await _admit(session, fixture.candidate, expected_candidate_content_hash="0" * 64)


@pytest.mark.asyncio
async def test_changed_statement_after_review_is_rejected_by_rebuilt_hash() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)
        fixture.candidate.statement = "Tampered statement after human review."

        with pytest.raises(KnowledgeCandidateAdmissionError, match="content_hash_mismatch"):
            await _admit(session, fixture.candidate)


@pytest.mark.asyncio
async def test_changed_source_refs_after_review_are_rejected() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)
        fixture.candidate.source_refs_json = [f"source:{uuid4()}"]

        with pytest.raises(KnowledgeCandidateAdmissionError):
            await _admit(session, fixture.candidate)


@pytest.mark.asyncio
async def test_changed_provenance_after_review_is_rejected_by_rebuilt_hash() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)
        provenance = copy.deepcopy(fixture.candidate.provenance_json)
        evidence_refs = cast(list[dict[str, object]], provenance["evidence_refs"])
        evidence_refs[0]["locator"] = "tampered:locator"
        fixture.candidate.provenance_json = provenance

        with pytest.raises(KnowledgeCandidateAdmissionError, match="content_hash_mismatch"):
            await _admit(session, fixture.candidate)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["RAW", "STALE"])
async def test_raw_and_stale_candidates_are_rejected(status: str) -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)
        fixture.candidate.status = status

        with pytest.raises(KnowledgeCandidateAdmissionError, match="status_not_admissible"):
            await _admit(session, fixture.candidate)


@pytest.mark.asyncio
async def test_approved_candidate_cannot_become_rejected() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)
        await _admit(session, fixture.candidate)

        with pytest.raises(
            KnowledgeCandidateAdmissionError,
            match="terminal_transition_rejected",
        ):
            await _admit(session, fixture.candidate, decision="reject")


@pytest.mark.asyncio
async def test_rejected_candidate_cannot_become_approved() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)
        await _admit(session, fixture.candidate, decision="reject")

        with pytest.raises(
            KnowledgeCandidateAdmissionError,
            match="terminal_transition_rejected",
        ):
            await _admit(session, fixture.candidate)


@pytest.mark.asyncio
async def test_exact_repeated_decision_is_idempotent() -> None:
    async with isolated_session() as session:
        initial_count = await session.scalar(
            select(func.count()).select_from(KnowledgeCandidate)
        )
        fixture = await _admission_fixture(session)
        first = await _admit(session, fixture.candidate)
        updated_at = first.updated_at
        second = await _admit(session, fixture.candidate)

        assert second.id == first.id
        assert second.status == "APPROVED"
        assert second.updated_at == updated_at
        assert (
            await session.scalar(select(func.count()).select_from(KnowledgeCandidate))
            == initial_count + 1
        )


@pytest.mark.asyncio
async def test_admission_preserves_candidate_source_and_provenance_fields() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)
        before = {
            "statement": fixture.candidate.statement,
            "summary": fixture.candidate.summary,
            "source_refs": copy.deepcopy(fixture.candidate.source_refs_json),
            "entity_refs": copy.deepcopy(fixture.candidate.entity_refs_json),
            "provenance": copy.deepcopy(fixture.candidate.provenance_json),
        }

        await _admit(session, fixture.candidate)

        assert fixture.candidate.statement == before["statement"]
        assert fixture.candidate.summary == before["summary"]
        assert fixture.candidate.source_refs_json == before["source_refs"]
        assert fixture.candidate.entity_refs_json == before["entity_refs"]
        assert fixture.candidate.provenance_json == before["provenance"]


@pytest.mark.asyncio
async def test_admission_creates_no_content_run_artifact_or_generic_approval() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)
        before = {
            "content_runs": await session.scalar(select(func.count()).select_from(ContentRun)),
            "artifacts": await session.scalar(select(func.count()).select_from(Artifact)),
            "approvals": await session.scalar(select(func.count()).select_from(Approval)),
        }

        await _admit(session, fixture.candidate)

        assert before == {
            "content_runs": await session.scalar(select(func.count()).select_from(ContentRun)),
            "artifacts": await session.scalar(select(func.count()).select_from(Artifact)),
            "approvals": await session.scalar(select(func.count()).select_from(Approval)),
        }


@pytest.mark.asyncio
async def test_evidence_set_and_originality_pack_are_unaffected() -> None:
    async with isolated_session() as session:
        fixture = await _admission_fixture(session)
        evidence_set_before = {
            "version": fixture.evidence_set.version,
            "evidence_ids": copy.deepcopy(fixture.evidence_set.evidence_ids_json),
            "content_hash": fixture.evidence_set.content_hash,
            "status": fixture.evidence_set.status,
            "locked_at": fixture.evidence_set.locked_at,
            "locked_by": fixture.evidence_set.locked_by,
        }
        originality_before = {
            "item_refs": copy.deepcopy(fixture.originality_pack.item_refs_json),
            "summary": fixture.originality_pack.summary,
            "status": fixture.originality_pack.status,
        }

        await _admit(session, fixture.candidate)

        assert evidence_set_before == {
            "version": fixture.evidence_set.version,
            "evidence_ids": fixture.evidence_set.evidence_ids_json,
            "content_hash": fixture.evidence_set.content_hash,
            "status": fixture.evidence_set.status,
            "locked_at": fixture.evidence_set.locked_at,
            "locked_by": fixture.evidence_set.locked_by,
        }
        assert originality_before == {
            "item_refs": fixture.originality_pack.item_refs_json,
            "summary": fixture.originality_pack.summary,
            "status": fixture.originality_pack.status,
        }


def test_admission_input_is_candidate_only_and_provider_free() -> None:
    parameters = tuple(inspect.signature(admit_knowledge_candidate).parameters)
    assert parameters == (
        "session",
        "candidate_id",
        "decision",
        "reviewer",
        "review_reason",
        "expected_candidate_content_hash",
    )
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/review_knowledge_candidate.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--candidate-id" in completed.stdout
    assert "--decision" in completed.stdout
    assert "--expected-content-hash" in completed.stdout
    assert "--raw" not in completed.stdout
    assert "--evidence-set-id" not in completed.stdout
