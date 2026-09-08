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
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    NeedHypothesis,
    Project,
)
from app.modules.knowledge.models import Claim, Evidence, Source, SourceDocument
from scripts.curate_evidence_set import curate_evidence_set


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
async def test_curated_evidence_set_is_idempotent_and_versions_changed_ids() -> None:
    async with isolated_session() as session:
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
            next_discovery_step="evidence review",
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
        content_case = ContentCase(
            project_id=project.id,
            content_type="journal",
            need_hypothesis_id=need.id,
            content_opportunity_id=opportunity.id,
            desired_action="evaluate an artwork price",
            content_hypothesis="grounded price evaluation",
            originality_statement="reviewed evidence remains separate from MOTGU material",
            reader_before="uncertain about an artwork price",
            reader_after="able to evaluate the price with context",
            status="draft",
        )
        session.add(content_case)
        await session.flush()

        source = Source(
            project_id=project.id,
            source_type="editorial_or_unknown",
            title="Curation test source",
            canonical_url=f"https://example.test/curation/{uuid4()}",
            locale="en",
            commercial_bias="unknown",
            authority_hint=None,
            provenance_json={"test": True},
            captured_at=datetime.now(UTC),
            fingerprint=str(uuid4()),
        )
        session.add(source)
        await session.flush()
        document = SourceDocument(
            source_id=source.id,
            document_version=1,
            canonical_url=source.canonical_url,
            fetched_at=datetime.now(UTC),
            content_hash=str(uuid4()).replace("-", ""),
            content_markdown="A reviewed curation excerpt.",
            metadata_json={},
            reader="test",
            provider="test",
        )
        claim_one = Claim(
            project_id=project.id,
            statement="A reviewed curation claim one.",
            claim_type="fact",
            importance="normal",
            status="unverified",
            entity_refs_json=[],
        )
        claim_two = Claim(
            project_id=project.id,
            statement="A reviewed curation claim two.",
            claim_type="fact",
            importance="normal",
            status="unverified",
            entity_refs_json=[],
        )
        session.add_all([document, claim_one, claim_two])
        await session.flush()
        evidence_one = Evidence(
            claim_id=claim_one.id,
            source_document_id=document.id,
            locator="test:1",
            excerpt="A reviewed curation excerpt.",
            relation="supports",
            quality_metadata_json={},
            provenance_json={},
        )
        evidence_two = Evidence(
            claim_id=claim_two.id,
            source_document_id=document.id,
            locator="test:1",
            excerpt="A reviewed curation excerpt.",
            relation="context_only",
            quality_metadata_json={},
            provenance_json={},
        )
        session.add_all([evidence_one, evidence_two])
        await session.flush()

        first = await curate_evidence_set(
            session,
            content_case_id=content_case.id,
            evidence_ids=[evidence_one.id],
        )
        same = await curate_evidence_set(
            session,
            content_case_id=content_case.id,
            evidence_ids=[evidence_one.id],
        )
        changed = await curate_evidence_set(
            session,
            content_case_id=content_case.id,
            evidence_ids=[evidence_one.id, evidence_two.id],
        )

        assert first["evidence_set_id"] == same["evidence_set_id"]
        assert first["version"] == same["version"] == 1
        assert first["status"] == same["status"] == "draft"
        assert first["provider_calls"] == same["provider_calls"] == 0
        assert changed["evidence_set_id"] != first["evidence_set_id"]
        assert changed["version"] == 2
        assert changed["status"] == "draft"
        assert changed["evidence_ids"] == sorted(
            [str(evidence_one.id), str(evidence_two.id)]
        )
        assert changed["relation_counts"] == {
            "context_only": 1,
            "supports": 1,
            "contradicts": 0,
            "qualifies": 0,
        }
        assert changed["source_document_count"] == 1


def test_curate_evidence_set_runner_help_works_without_pythonpath() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/curate_evidence_set.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "provider calls" in completed.stdout
