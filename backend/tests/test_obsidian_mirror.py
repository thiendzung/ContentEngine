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
from uuid import uuid4

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
class MirrorFixture:
    candidate: KnowledgeCandidate
    evidence_set: EvidenceSet
    originality_pack: OriginalityPack
    claim: Claim


async def mirror_fixture(session: AsyncSession) -> MirrorFixture:
    project = (await session.execute(select(Project).where(Project.slug == "motgu"))).scalar_one()
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
        next_discovery_step="candidate mirror",
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
        originality_statement="reviewed sources remain traceable",
        reader_before="uncertain about an artwork price",
        reader_after="able to evaluate the price with context",
        status="draft",
    )
    session.add(content_case)
    await session.flush()

    source = Source(
        project_id=project.id,
        source_type="web",
        title="Mirror fixture source",
        canonical_url=f"https://example.test/mirror/{uuid4()}",
        locale="en",
        commercial_bias="low",
        authority_hint="high",
        provenance_json={"method": "fixture"},
        captured_at=datetime.now(UTC),
        fingerprint=str(uuid4()),
    )
    session.add(source)
    await session.flush()
    document_text = "A persisted source document excerpt for the mirror fixture."
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
        content_hash=content_hash("mirror-evidence-set"),
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
        await extract_knowledge_candidates(session, evidence_set_id=evidence_set.id)
    )[0]
    await admit_knowledge_candidate(
        session,
        candidate_id=candidate.id,
        decision="approve",
        reviewer="MG CONTENT ENGINE",
        review_reason="Approved mirror fixture after locked-source review.",
        expected_candidate_content_hash=cast(
            str, candidate.provenance_json["candidate_content_hash"]
        ),
    )
    return MirrorFixture(candidate, evidence_set, originality_pack, claim)


@pytest.mark.asyncio
async def test_approved_candidate_renders_exact_statement_and_provenance(tmp_path: Path) -> None:
    async with isolated_session() as session:
        fixture = await mirror_fixture(session)
        result = await export_approved_knowledge(
            session,
            candidate_id=fixture.candidate.id,
            vault_path=tmp_path,
        )

        assert result.path == tmp_path / "10_Knowledge" / f"{fixture.candidate.id}.md"
        assert result.path.read_text(encoding="utf-8").startswith("---\n")
        content = result.path.read_text(encoding="utf-8")
        assert fixture.candidate.statement in content
        assert "reviewer: \"MG CONTENT ENGINE\"" in content
        assert cast(str, fixture.candidate.review_reason) in content
        assert str(fixture.evidence_set.id) in content
        provenance = fixture.candidate.provenance_json
        assert str(provenance["claim_id"]) in content
        assert str(cast(list[str], provenance["evidence_ids"])[0]) in content
        assert str(cast(list[str], provenance["source_document_ids"])[0]) in content
        assert str(cast(list[str], provenance["source_ids"])[0]) in content
        assert "raw_payload" not in content


@pytest.mark.asyncio
async def test_same_approved_snapshot_is_byte_identical_and_idempotent(tmp_path: Path) -> None:
    async with isolated_session() as session:
        fixture = await mirror_fixture(session)
        first = await export_approved_knowledge(
            session, candidate_id=fixture.candidate.id, vault_path=tmp_path
        )
        first_bytes = first.path.read_bytes()
        second = await export_approved_knowledge(
            session, candidate_id=fixture.candidate.id, vault_path=tmp_path
        )

        assert second.path == first.path
        assert second.path.read_bytes() == first_bytes
        assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == [
            "10_Knowledge",
            f"10_Knowledge/{fixture.candidate.id}.md",
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["CANDIDATE", "RAW", "REJECTED", "STALE"])
async def test_non_approved_candidate_is_rejected(status: str, tmp_path: Path) -> None:
    async with isolated_session() as session:
        fixture = await mirror_fixture(session)
        fixture.candidate.status = status

        with pytest.raises(KnowledgeMirrorError, match="status_not_exportable"):
            await export_approved_knowledge(
                session, candidate_id=fixture.candidate.id, vault_path=tmp_path
            )
        assert not (tmp_path / "10_Knowledge").exists()


@pytest.mark.asyncio
async def test_tampered_candidate_snapshot_is_rejected(tmp_path: Path) -> None:
    async with isolated_session() as session:
        fixture = await mirror_fixture(session)
        fixture.candidate.statement = "Tampered statement after admission."

        with pytest.raises(KnowledgeMirrorError, match="content_hash_mismatch"):
            await export_approved_knowledge(
                session, candidate_id=fixture.candidate.id, vault_path=tmp_path
            )


@pytest.mark.asyncio
async def test_tampered_provenance_is_rejected(tmp_path: Path) -> None:
    async with isolated_session() as session:
        fixture = await mirror_fixture(session)
        provenance = copy.deepcopy(fixture.candidate.provenance_json)
        evidence_refs = cast(list[dict[str, object]], provenance["evidence_refs"])
        evidence_refs[0]["locator"] = "tampered:locator"
        fixture.candidate.provenance_json = provenance

        with pytest.raises(KnowledgeMirrorError, match="content_hash_mismatch"):
            await export_approved_knowledge(
                session, candidate_id=fixture.candidate.id, vault_path=tmp_path
            )


@pytest.mark.asyncio
async def test_stale_locked_evidence_lineage_is_rejected(tmp_path: Path) -> None:
    async with isolated_session() as session:
        fixture = await mirror_fixture(session)
        fixture.claim.statement = "The locked claim was changed after admission."

        with pytest.raises(KnowledgeMirrorError, match="snapshot_stale"):
            await export_approved_knowledge(
                session, candidate_id=fixture.candidate.id, vault_path=tmp_path
            )


@pytest.mark.asyncio
async def test_export_is_read_only_and_dry_run_writes_nothing(tmp_path: Path) -> None:
    async with isolated_session() as session:
        fixture = await mirror_fixture(session)
        before = {
            "candidate": (
                fixture.candidate.status,
                fixture.candidate.reviewer,
                fixture.candidate.review_reason,
                copy.deepcopy(fixture.candidate.provenance_json),
            ),
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
            "candidate_count": await session.scalar(
                select(func.count()).select_from(KnowledgeCandidate)
            ),
        }

        result = await export_approved_knowledge(
            session,
            candidate_id=fixture.candidate.id,
            vault_path=tmp_path,
            dry_run=True,
        )

        assert result.dry_run is True
        assert not (tmp_path / "10_Knowledge").exists()
        assert before == {
            "candidate": (
                fixture.candidate.status,
                fixture.candidate.reviewer,
                fixture.candidate.review_reason,
                fixture.candidate.provenance_json,
            ),
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
            "candidate_count": await session.scalar(
                select(func.count()).select_from(KnowledgeCandidate)
            ),
        }


def test_vault_path_is_explicit_and_cli_has_no_import_or_default_path() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/export_approved_knowledge.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--candidate-id" in completed.stdout
    assert "--vault-path" in completed.stdout
    assert "--dry-run" in completed.stdout
    assert "--import" not in completed.stdout
    assert "default" not in completed.stdout.lower()
    assert tuple(inspect.signature(export_approved_knowledge).parameters) == (
        "session",
        "candidate_id",
        "vault_path",
        "dry_run",
    )


@pytest.mark.asyncio
async def test_invalid_vault_directory_and_path_traversal_are_rejected(tmp_path: Path) -> None:
    async with isolated_session() as session:
        fixture = await mirror_fixture(session)
        invalid_root = tmp_path / "not-a-directory"
        invalid_root.write_text("not a vault", encoding="utf-8")
        with pytest.raises(KnowledgeMirrorError, match="existing_directory"):
            await export_approved_knowledge(
                session, candidate_id=fixture.candidate.id, vault_path=invalid_root
            )

        knowledge_file = tmp_path / "10_Knowledge"
        knowledge_file.write_text("not a directory", encoding="utf-8")
        with pytest.raises(KnowledgeMirrorError, match="knowledge_directory_invalid"):
            await export_approved_knowledge(
                session, candidate_id=fixture.candidate.id, vault_path=tmp_path
            )
