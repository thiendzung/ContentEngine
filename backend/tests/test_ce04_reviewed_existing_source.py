from __future__ import annotations

import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import ContentCase, Project
from app.modules.knowledge.models import Claim, Evidence, KnowledgeChunk, Source, SourceDocument
from app.modules.knowledge.persistence import content_hash
from app.modules.research.evidence.contracts import EvidenceRelation
from app.modules.research.evidence.reviewed_source import (
    persist_reviewed_existing_source_evidence,
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
async def test_reviewed_existing_source_evidence_is_exact_and_idempotent() -> None:
    async with isolated_session() as session:
        project = (
            await session.execute(select(Project).where(Project.slug == "motgu"))
        ).scalar_one()
        content_case = ContentCase(
            project_id=project.id,
            content_type="journal",
            desired_action="evaluate an artwork price",
            content_hypothesis="use reviewed evidence",
            originality_statement="external evidence stays separate",
            reader_before="uncertain",
            reader_after="informed",
            status="draft",
        )
        source = Source(
            project_id=project.id,
            source_type="institutional",
            title="Reviewed source",
            canonical_url=f"https://example.edu/reviewed/{uuid4()}",
            locale="en",
            commercial_bias="low",
            authority_hint="institutional_candidate",
            provenance_json={"test": True},
            captured_at=datetime.now(UTC),
            fingerprint=str(uuid4()),
        )
        session.add_all([content_case, source])
        await session.flush()

        excerpt = (
            "Prices asked and amounts offered are determined by personal interests of both "
            "the seller and the purchaser and by the trends in the market."
        )
        document = SourceDocument(
            source_id=source.id,
            document_version=1,
            canonical_url=source.canonical_url,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash(f"prefix {excerpt} suffix"),
            content_markdown=f"Intro text.\n\n{excerpt}\n\nOther material.",
            metadata_json={},
            reader="test",
            provider="test",
        )
        session.add(document)
        await session.flush()
        chunk = KnowledgeChunk(
            source_document_id=document.id,
            ordinal=0,
            text=excerpt,
            token_estimate=30,
            fingerprint=content_hash(excerpt),
            status="active",
            metadata_json={},
        )
        session.add(chunk)
        await session.flush()

        first = await persist_reviewed_existing_source_evidence(
            session,
            content_case_id=content_case.id,
            source_document_id=document.id,
            statement=excerpt,
            excerpt=excerpt,
            relation=EvidenceRelation.SUPPORTS,
            reviewed_by="MG CONTENT ENGINE",
        )
        same = await persist_reviewed_existing_source_evidence(
            session,
            content_case_id=content_case.id,
            source_document_id=document.id,
            statement=excerpt,
            excerpt=excerpt,
            relation=EvidenceRelation.SUPPORTS,
            reviewed_by="MG CONTENT ENGINE",
        )

        assert same == first
        evidence = await session.get(Evidence, first.evidence_id)
        claim = await session.get(Claim, first.claim_id)
        assert evidence is not None
        assert claim is not None
        assert evidence.chunk_id == chunk.id
        assert evidence.relation == "supports"
        assert evidence.excerpt == excerpt
        assert evidence.quality_metadata_json["human_reviewed"] is True
        assert evidence.quality_metadata_json["reviewed_by"] == "MG CONTENT ENGINE"
        assert evidence.provenance_json["method"] == "human_review_existing_source"
        assert evidence.provenance_json["content_case_id"] == str(content_case.id)
        assert claim.statement == excerpt
        assert claim.status == "unverified"

        with pytest.raises(ValueError, match="evidence_excerpt_not_found_in_source_document"):
            await persist_reviewed_existing_source_evidence(
                session,
                content_case_id=content_case.id,
                source_document_id=document.id,
                statement="Unsupported statement",
                excerpt="This excerpt is not in the document.",
                relation=EvidenceRelation.SUPPORTS,
                reviewed_by="MG CONTENT ENGINE",
            )


def test_reviewed_existing_evidence_runner_help_works_without_pythonpath() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/persist_reviewed_existing_evidence.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "zero provider calls" in completed.stdout
