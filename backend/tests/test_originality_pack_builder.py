from __future__ import annotations

import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

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
from app.modules.knowledge.models import Claim, Evidence, OriginalityPack, Source, SourceDocument
from app.modules.knowledge.persistence import content_hash
from app.modules.research.evidence.contracts import (
    ORIGINALITY_MATERIAL_TYPE,
    count_usable_originality_items,
    is_usable_originality_item,
)
from app.modules.research.evidence.persistence import (
    build_originality_pack,
    normalize_originality_items,
)


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


def d4_originality_items() -> list[dict[str, object]]:
    return [
        {
            "type": ORIGINALITY_MATERIAL_TYPE,
            "source_ref": "docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-01",
            "material": (
                "The content can anchor abstract price discussion in a real physical Artwork "
                "with live price, dimensions, material, sale status and specific work identity; "
                "current commerce facts must be read from canonical data rather than "
                "remembered/editorial copies."
            ),
            "writer_use": "Here is what to look at on the actual work in front of you.",
            "guardrails": "Do not expose internal implementation details unnecessarily.",
            "approval_ref": "docs/13-CE01-CONTENT-INPUT-PRICE.md#D4-GATE-D-PASS",
        },
        {
            "type": ORIGINALITY_MATERIAL_TYPE,
            "source_ref": "docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-02",
            "material": (
                "Packaging/shipping/insurance can be operationally separate from artwork "
                "price; oversize may require a quote."
            ),
            "writer_use": "Practical first-buyer checklist before deciding.",
            "guardrails": "Do not collapse operational costs into artwork price.",
            "approval_ref": "docs/13-CE01-CONTENT-INPUT-PRICE.md#D4-GATE-D-PASS",
        },
        {
            "type": ORIGINALITY_MATERIAL_TYPE,
            "source_ref": "docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-03",
            "material": (
                "Sale status and physical location are separate facts; availability should "
                "come from canonical state; editorial copy must not turn a status into "
                "manipulative urgency."
            ),
            "writer_use": "Explain availability plainly; do not create pressure.",
            "guardrails": "Do not turn status or location into fake scarcity.",
            "approval_ref": "docs/13-CE01-CONTENT-INPUT-PRICE.md#D4-GATE-D-PASS",
        },
        {
            "type": ORIGINALITY_MATERIAL_TYPE,
            "source_ref": "docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-04",
            "material": (
                "Calm, personal, low-pressure guidance: Take your time, Ask anything, "
                "Nothing formal; artwork remains the centre of gravity rather than "
                "investment status or luxury signaling."
            ),
            "writer_use": (
                "The reader should leave with better questions and more confidence, "
                "not a feeling of having been sold to."
            ),
            "guardrails": "Do not turn guidance into investment or luxury signaling.",
            "approval_ref": "docs/13-CE01-CONTENT-INPUT-PRICE.md#D4-GATE-D-PASS",
        },
    ]


async def content_case_for_test(session: AsyncSession) -> ContentCase:
    project = (await session.execute(select(Project).where(Project.slug == "motgu"))).scalar_one()
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement="How do I know if an original artwork is fairly priced?",
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
        need="evaluate an artwork price",
        question=need.statement,
        intent="learn",
        promise="provide grounded context",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="buyer price evaluation",
        next_discovery_step="originality review",
        decision="CREATE",
        priority="NOW",
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
        desired_action="evaluate an artwork price",
        content_hypothesis="grounded price evaluation",
        originality_statement="MOTGU-owned material remains separate from external Evidence.",
        reader_before="uncertain about an artwork price",
        reader_after="able to evaluate the price with context",
        status="draft",
    )
    session.add(content_case)
    await session.flush()
    return content_case


@pytest.mark.asyncio
async def test_d4_structured_items_are_persisted_verbatim_and_usable() -> None:
    items = d4_originality_items()
    assert count_usable_originality_items(items) == 4
    assert all(is_usable_originality_item(item) for item in items)

    async with isolated_session() as session:
        content_case = await content_case_for_test(session)
        pack = await build_originality_pack(
            session,
            content_case_id=content_case.id,
            motgu_material_refs=items,
        )

        assert pack.item_refs_json == items
        assert count_usable_originality_items(pack.item_refs_json) == 4
        assert "MOTGU-owned material is available" in pack.summary


def test_reference_only_and_empty_material_are_not_usable() -> None:
    empty_item = {
        "type": ORIGINALITY_MATERIAL_TYPE,
        "source_ref": "motgu:empty-material",
        "material": "   ",
        "writer_use": "Use only if reviewed.",
        "guardrails": "Do not invent detail.",
        "approval_ref": "approval:test",
    }
    normalized = normalize_originality_items(["motgu:legacy-ref", empty_item])

    assert normalized[0] == {
        "type": "reference_only",
        "source_ref": "motgu:legacy-ref",
    }
    assert normalized[1] == empty_item
    assert count_usable_originality_items(normalized) == 0


def test_external_evidence_is_excluded_from_originality_items() -> None:
    valid = d4_originality_items()[0]
    normalized = normalize_originality_items(
        [
            valid,
            {"type": "evidence", "id": "irs-evidence-id", "source_ref": "irs:claim"},
            {"kind": "evidence", "id": "mci-evidence-id", "source_ref": "mci:claim"},
            "https://www.irs.gov/charities-non-profits/appraisals",
            {"type": "motgu_owned_material", "source_ref": "https://mci.si.edu/artifact-appraisals"},
        ]
    )

    assert normalized == [valid]
    assert count_usable_originality_items(normalized) == 1


@pytest.mark.asyncio
async def test_same_exact_input_reuses_one_originality_pack_and_dedupes_stably() -> None:
    items = d4_originality_items()
    input_with_duplicate = [items[0], items[0], items[1]]

    async with isolated_session() as session:
        content_case = await content_case_for_test(session)
        first = await build_originality_pack(
            session,
            content_case_id=content_case.id,
            motgu_material_refs=input_with_duplicate,
        )
        second = await build_originality_pack(
            session,
            content_case_id=content_case.id,
            motgu_material_refs=input_with_duplicate,
        )

        assert first.id == second.id
        assert first.item_refs_json == [items[0], items[1]]
        pack_count = await session.scalar(
            select(func.count()).select_from(OriginalityPack).where(
                OriginalityPack.content_case_id == content_case.id
            )
        )
        assert pack_count == 1


@pytest.mark.asyncio
async def test_existing_external_evidence_id_is_excluded_from_originality_pack() -> None:
    async with isolated_session() as session:
        content_case = await content_case_for_test(session)
        source = Source(
            project_id=content_case.project_id,
            source_type="institutional",
            title="IRS evidence",
            canonical_url="https://www.irs.gov/charities-non-profits/appraisals",
            locale="en",
            provenance_json={"test": True},
            captured_at=datetime.now(UTC),
            fingerprint="originality-irs-evidence",
        )
        session.add(source)
        await session.flush()
        document = SourceDocument(
            source_id=source.id,
            document_version=1,
            canonical_url=source.canonical_url,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash("IRS evidence"),
            content_markdown="IRS evidence",
            metadata_json={},
        )
        claim = Claim(
            project_id=content_case.project_id,
            statement="External evidence claim",
            claim_type="fact",
            importance="normal",
            status="unverified",
            entity_refs_json=[],
        )
        session.add_all([document, claim])
        await session.flush()
        evidence = Evidence(
            claim_id=claim.id,
            source_document_id=document.id,
            locator="p.1",
            excerpt="IRS evidence",
            relation="supports",
            quality_metadata_json={},
            provenance_json={},
        )
        session.add(evidence)
        await session.flush()

        pack = await build_originality_pack(
            session,
            content_case_id=content_case.id,
            motgu_material_refs=[d4_originality_items()[0], str(evidence.id)],
        )

        assert pack.item_refs_json == [d4_originality_items()[0]]
        assert count_usable_originality_items(pack.item_refs_json) == 1


@pytest.mark.asyncio
async def test_reference_only_input_keeps_originality_gap_visible() -> None:
    async with isolated_session() as session:
        content_case = await content_case_for_test(session)
        pack = await build_originality_pack(
            session,
            content_case_id=content_case.id,
            motgu_material_refs=["motgu:legacy-ref"],
        )

        assert count_usable_originality_items(pack.item_refs_json) == 0
        assert "Originality gap" in pack.summary
        assert "reference-only" in pack.summary


def test_curate_originality_pack_runner_help_works_without_pythonpath() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/curate_originality_pack.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "provider calls" in completed.stdout
