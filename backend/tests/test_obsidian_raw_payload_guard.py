from __future__ import annotations

import copy
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
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
from app.modules.harness.models import Approval, Artifact, ContentRun
from app.modules.knowledge.admission import admit_knowledge_candidate
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
from app.modules.knowledge.obsidian import KnowledgeMirrorError, export_approved_knowledge
from app.modules.knowledge.persistence import content_hash

RAW_KEYS = {
    "body",
    "html",
    "payload",
    "raw",
    "raw_payload",
    "raw_response",
    "response",
    "result",
}
RAW_SENTINELS = {
    "RAW_SERP_SENTINEL_01",
    "RAW_HTML_SENTINEL_02",
    "RAW_PAGE_BODY_SENTINEL_03",
    "RAW_PAYLOAD_SENTINEL_04",
    "RAW_RESPONSE_SENTINEL_05",
    "RAW_RESULT_SENTINEL_06",
    "RAW_NESTED_SENTINEL_07",
}
SAFE_METADATA = {
    "provider": "serper",
    "query": "synthetic raw mirror guard query",
    "source_url": "https://synthetic.example/raw-mirror-guard",
    "source_ref": "synthetic:raw-mirror-guard",
}


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
class RawGuardFixture:
    candidate: KnowledgeCandidate
    evidence_set: EvidenceSet
    originality_pack: OriginalityPack
    content_case: ContentCase
    source_document: SourceDocument


def raw_evidence_provenance() -> dict[str, object]:
    return {
        **SAFE_METADATA,
        "body": "RAW_SERP_SENTINEL_01",
        "html": "RAW_HTML_SENTINEL_02",
        "payload": "RAW_PAYLOAD_SENTINEL_04",
        "raw": "RAW_RESPONSE_SENTINEL_05",
        "raw_payload": {"secret": "RAW_NESTED_SENTINEL_07"},
        "raw_response": "RAW_RESPONSE_SENTINEL_05",
        "response": {"value": "RAW_RESULT_SENTINEL_06"},
        "result": "RAW_RESULT_SENTINEL_06",
        "metadata": {
            "safe_locator": "synthetic:metadata",
            "raw_payload": {"secret": "RAW_SERP_SENTINEL_01"},
        },
        "provider_response": {
            "nested": {"html": "RAW_HTML_SENTINEL_02"},
        },
    }


def assert_no_raw_keys_or_sentinels(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            assert str(key).casefold() not in RAW_KEYS
            assert str(key) not in RAW_SENTINELS
            assert_no_raw_keys_or_sentinels(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_no_raw_keys_or_sentinels(nested)
    elif isinstance(value, str):
        assert not any(sentinel in value for sentinel in RAW_SENTINELS)


async def raw_guard_fixture(session: AsyncSession) -> RawGuardFixture:
    project = (await session.execute(select(Project).where(Project.slug == "motgu"))).scalar_one()
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement="A buyer wants a safe way to evaluate an artwork price.",
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
        need="evaluate artwork price safely",
        question="How can a buyer evaluate an artwork price safely?",
        intent="learn",
        promise="provide grounded context",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="raw mirror boundary",
        next_discovery_step="review raw-data guard",
        decision="CREATE",
        priority="NOW",
        reasons_json=[],
        suggested_content_type="journal",
        selected_by="founder",
        selected_at=datetime.now(UTC),
        selection_reason="raw mirror guard test",
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="evaluate an artwork price",
        content_hypothesis="raw data must not become mirror content",
        originality_statement="MOTGU-owned material remains separate",
        reader_before="uncertain about an artwork price",
        reader_after="able to ask grounded price questions",
        status="draft",
    )
    session.add(content_case)
    await session.flush()

    source = Source(
        project_id=project.id,
        source_type="web",
        title="Synthetic raw guard source",
        canonical_url=SAFE_METADATA["source_url"],
        locale="en",
        commercial_bias="low",
        authority_hint="high",
        provenance_json=raw_evidence_provenance(),
        captured_at=datetime.now(UTC),
        fingerprint=f"raw-guard-source-{uuid4()}",
    )
    session.add(source)
    await session.flush()
    full_page = (
        "Synthetic full page retained for audit. "
        "RAW_PAGE_BODY_SENTINEL_03. More page material must not enter the mirror."
    )
    source_document = SourceDocument(
        source_id=source.id,
        document_version=1,
        canonical_url=source.canonical_url,
        fetched_at=datetime.now(UTC),
        content_hash=content_hash(full_page),
        content_markdown=full_page,
        metadata_json={"page_audit": "RAW_PAGE_BODY_SENTINEL_03"},
        reader="synthetic-reader",
        provider="serper",
    )
    claim = Claim(
        project_id=project.id,
        statement="A buyer can evaluate an artwork price using documented context.",
        claim_type="fact",
        importance="high",
        status="unverified",
        entity_refs_json=["entity:artwork", "entity:buyer"],
    )
    session.add_all([source_document, claim])
    await session.flush()
    evidence = Evidence(
        claim_id=claim.id,
        source_document_id=source_document.id,
        locator="synthetic:raw-guard:claim",
        excerpt="A buyer can evaluate an artwork price using documented context.",
        relation="supports",
        quality_metadata_json={"synthetic": True},
        provenance_json=raw_evidence_provenance(),
    )
    session.add(evidence)
    await session.flush()
    evidence_set = await create_locked_evidence_set(
        session,
        project_id=project.id,
        content_case_id=content_case.id,
        version=8,
        evidence_ids=[str(evidence.id)],
        locked_by="synthetic raw guard reviewer",
    )
    originality_pack = OriginalityPack(
        content_case_id=content_case.id,
        item_refs_json=[{"type": "motgu_owned_material", "material": "synthetic"}],
        summary="Synthetic originality pack",
        status="draft",
    )
    session.add(originality_pack)
    await session.flush()
    candidate = (
        await extract_knowledge_candidates(session, evidence_set_id=evidence_set.id)
    )[0]
    return RawGuardFixture(candidate, evidence_set, originality_pack, content_case, source_document)


async def approve_candidate(session: AsyncSession, candidate: KnowledgeCandidate) -> None:
    await admit_knowledge_candidate(
        session,
        candidate_id=candidate.id,
        decision="approve",
        reviewer="MG CONTENT ENGINE",
        review_reason="Approved after raw payload boundary review.",
        expected_candidate_content_hash=cast(
            str, candidate.provenance_json["candidate_content_hash"]
        ),
    )


@pytest.mark.asyncio
async def test_extraction_recursively_sanitizes_raw_provenance_and_keeps_safe_metadata() -> None:
    async with isolated_session() as session:
        fixture = await raw_guard_fixture(session)
        evidence_refs = cast(
            list[dict[str, object]], fixture.candidate.provenance_json["evidence_refs"]
        )
        provenance = cast(dict[str, object], evidence_refs[0]["provenance"])

        assert provenance["provider"] == "serper"
        assert provenance["query"] == SAFE_METADATA["query"]
        assert provenance["source_url"] == SAFE_METADATA["source_url"]
        assert provenance["source_ref"] == SAFE_METADATA["source_ref"]
        assert_no_raw_keys_or_sentinels(provenance)
        assert fixture.source_document.content_markdown is not None
        assert "RAW_PAGE_BODY_SENTINEL_03" in fixture.source_document.content_markdown
        assert "RAW_PAGE_BODY_SENTINEL_03" not in fixture.candidate.statement


@pytest.mark.asyncio
async def test_approved_sanitized_candidate_mirrors_without_raw_page_or_provider_data(
    tmp_path: Path,
) -> None:
    async with isolated_session() as session:
        fixture = await raw_guard_fixture(session)
        await approve_candidate(session, fixture.candidate)
        result = await export_approved_knowledge(
            session,
            candidate_id=fixture.candidate.id,
            vault_path=tmp_path,
        )
        content = result.path.read_text(encoding="utf-8")

        assert fixture.candidate.statement in content
        assert "MG CONTENT ENGINE" in content
        assert "Approved after raw payload boundary review." in content
        assert str(fixture.evidence_set.id) in content
        assert str(fixture.candidate.id) in content
        assert not any(sentinel in content for sentinel in RAW_SENTINELS)
        assert not any(
            re.search(rf"(?im)^\s*{re.escape(key)}\s*:", content) for key in RAW_KEYS
        )


@pytest.mark.asyncio
async def test_tampered_approved_candidate_is_rejected_before_file_write(tmp_path: Path) -> None:
    async with isolated_session() as session:
        fixture = await raw_guard_fixture(session)
        await approve_candidate(session, fixture.candidate)
        provenance = copy.deepcopy(fixture.candidate.provenance_json)
        evidence_refs = cast(list[dict[str, object]], provenance["evidence_refs"])
        evidence_refs[0]["provenance"] = {
            "safe": {"metadata": {"raw_response": "RAW_TAMPER_SENTINEL"}},
        }
        fixture.candidate.provenance_json = provenance

        with pytest.raises(KnowledgeMirrorError, match="candidate_raw_provenance_rejected"):
            await export_approved_knowledge(
                session,
                candidate_id=fixture.candidate.id,
                vault_path=tmp_path,
            )
        assert not (tmp_path / "10_Knowledge").exists()


@pytest.mark.asyncio
async def test_mirror_export_is_read_only_for_knowledge_and_run_ledgers(tmp_path: Path) -> None:
    async with isolated_session() as session:
        fixture = await raw_guard_fixture(session)
        await approve_candidate(session, fixture.candidate)
        before = {
            "candidate_count": await session.scalar(
                select(func.count()).select_from(KnowledgeCandidate)
            ),
            "candidate_status": fixture.candidate.status,
            "evidence_set": (
                fixture.evidence_set.status,
                fixture.evidence_set.version,
                fixture.evidence_set.content_hash,
                copy.deepcopy(fixture.evidence_set.evidence_ids_json),
            ),
            "originality_pack": (
                fixture.originality_pack.status,
                copy.deepcopy(fixture.originality_pack.item_refs_json),
            ),
            "o4_content_runs": await session.scalar(
                select(func.count()).select_from(ContentRun).where(
                    ContentRun.content_case_id
                    == "9ec6133b-5f14-46d0-9866-e3b049e537b5"
                )
            ),
            "artifacts": await session.scalar(select(func.count()).select_from(Artifact)),
            "approvals": await session.scalar(select(func.count()).select_from(Approval)),
        }

        await export_approved_knowledge(
            session,
            candidate_id=fixture.candidate.id,
            vault_path=tmp_path,
        )

        assert before == {
            "candidate_count": await session.scalar(
                select(func.count()).select_from(KnowledgeCandidate)
            ),
            "candidate_status": fixture.candidate.status,
            "evidence_set": (
                fixture.evidence_set.status,
                fixture.evidence_set.version,
                fixture.evidence_set.content_hash,
                fixture.evidence_set.evidence_ids_json,
            ),
            "originality_pack": (
                fixture.originality_pack.status,
                fixture.originality_pack.item_refs_json,
            ),
            "o4_content_runs": await session.scalar(
                select(func.count()).select_from(ContentRun).where(
                    ContentRun.content_case_id
                    == "9ec6133b-5f14-46d0-9866-e3b049e537b5"
                )
            ),
            "artifacts": await session.scalar(select(func.count()).select_from(Artifact)),
            "approvals": await session.scalar(select(func.count()).select_from(Approval)),
        }
