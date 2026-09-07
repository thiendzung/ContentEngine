from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

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
from app.modules.knowledge.models import Evidence, EvidenceSet, OriginalityPack
from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    PageDocument,
    ProductionResearchRequest,
    ProductionResearchResult,
    ResearchSignalKind,
    SearchSignal,
    SourceCandidate,
)
from app.modules.research.evidence import (
    ClaimCandidate,
    EvidenceRelation,
    EvidenceResearchRequest,
    EvidenceResearchWorkflow,
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


class FakeEvidenceRouter:
    def __init__(
        self,
        *,
        with_documents: bool = True,
        source_type: str = "editorial",
        commercial_bias: CommercialBias = CommercialBias.LOW,
        intended_use: IntendedUse = IntendedUse.EVIDENCE_CANDIDATE,
    ) -> None:
        self.with_documents = with_documents
        self.source_type = source_type
        self.commercial_bias = commercial_bias
        self.intended_use = intended_use
        self.call_count = 0

    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> ProductionResearchResult:
        del session, run_id, step_run_id
        self.call_count += 1
        source_url = "https://example.test/art-pricing"
        source = SourceCandidate(
            provider="serper",
            query=request.query,
            url=source_url,
            title="Art pricing guide",
            source_type=self.source_type,
            commercial_bias=self.commercial_bias,
            intended_use=self.intended_use,
        )
        result = ProductionResearchResult(
            request=request,
            signals=[
                SearchSignal(
                    provider="serper",
                    query=request.query,
                    kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                    text="How is original artwork priced?",
                    url=source_url,
                    snippet="Search snippet must not become evidence.",
                )
            ],
            source_candidates=[source],
            selected_sources=[source],
            stop_reason="serper_sufficient",
            sufficient=True,
        )
        if self.with_documents:
            result.documents.append(
                PageDocument(
                    provider="jina",
                    url=source_url,
                    requested_url=source_url,
                    final_url=source_url,
                    title="Art pricing guide",
                    content=(
                        "The asking price of an original artwork can reflect materials, size, "
                        "and context around the artist and work.\n\n"
                        "There is no single formula that proves an artwork is fairly priced. "
                        "Different works can require different context."
                    ),
                )
            )
        return result


async def selected_o4_like_plan(
    session: AsyncSession,
    *,
    motgu_material_refs: list[str] | None = None,
) -> tuple[Project, NeedHypothesis, ContentOpportunity]:
    project = (
        await session.execute(select(Project).where(Project.slug == "motgu"))
    ).scalar_one()
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement=(
            "A first-time art buyer wants to understand whether an original artwork price "
            "makes sense before deciding to buy."
        ),
        audience_scope="international first-time art buyer",
        situation="considering an original artwork but uncertain how to evaluate the price",
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
        reader="international first-time art buyer",
        situation="considering an original artwork but uncertain how to evaluate the price",
        need="understand whether an original artwork price makes sense",
        question="How do I know if an original artwork is fairly priced?",
        intent="learn",
        promise="help the reader evaluate price with grounded context",
        motgu_material_refs_json=list(motgu_material_refs or []),
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="price evaluation for a first-time buyer",
        next_discovery_step="evidence research",
        decision="CREATE",
        priority="NOW",
        reasons_json=["founder selected"],
        suggested_content_type="journal",
        suggested_role="cluster",
        selected_by="founder",
        selected_at=datetime.now(UTC),
        selection_reason="selected for evidence research",
    )
    session.add(opportunity)
    await session.flush()
    return project, need, opportunity


def evidence_request(
    *,
    project_id: UUID,
    need_id: UUID,
    opportunity_id: UUID,
    explicit_candidates: tuple[ClaimCandidate, ...] = (),
    lock: bool = False,
) -> EvidenceResearchRequest:
    return EvidenceResearchRequest(
        research=ProductionResearchRequest(
            project_id=project_id,
            query="how to evaluate original artwork price",
            locale="en",
            country="us",
            max_pages_to_read=2,
        ),
        content_opportunity_id=opportunity_id,
        need_hypothesis_id=need_id,
        max_claims=8,
        explicit_candidates=explicit_candidates,
        lock_evidence_set=lock,
        locked_by="test-reviewer" if lock else None,
    )


@pytest.mark.asyncio
async def test_evidence_workflow_is_idempotent_and_preserves_contradiction() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_o4_like_plan(session)
        router = FakeEvidenceRouter()
        workflow = EvidenceResearchWorkflow(router=router)
        explicit = (
            ClaimCandidate(
                statement="A single formula can always prove whether an artwork price is fair.",
                source_url="https://example.test/art-pricing",
                locator="reviewed_sentence:2",
                excerpt="There is no single formula that proves an artwork is fairly priced.",
                relation=EvidenceRelation.CONTRADICTS,
                importance="high",
            ),
        )
        request = evidence_request(
            project_id=project.id,
            need_id=need.id,
            opportunity_id=opportunity.id,
            explicit_candidates=explicit,
            lock=True,
        )

        first = await workflow.run(session, request=request)
        second = await workflow.run(session, request=request)

        assert first.content_case_id == second.content_case_id
        assert first.evidence_set_id == second.evidence_set_id
        assert first.originality_pack_id == second.originality_pack_id
        assert first.evidence_ids == second.evidence_ids
        assert first.relation_counts["contradicts"] == 1
        assert first.evidence_eligible is True
        assert first.evidence_set_status == "locked"
        assert first.evidence_set_version == 1
        assert first.originality_item_count == 0
        assert any("Originality gap" in gap for gap in first.research_gaps)
        assert not any("Contradiction coverage" in gap for gap in first.research_gaps)
        assert router.call_count == 2

        content_case_count = await session.scalar(
            select(func.count()).select_from(ContentCase).where(
                ContentCase.content_opportunity_id == opportunity.id
            )
        )
        assert content_case_count == 1
        stored_need = await session.get(NeedHypothesis, need.id)
        assert stored_need is not None
        assert stored_need.status == "PROPOSED"
        evidence_set = await session.get(EvidenceSet, first.evidence_set_id)
        assert evidence_set is not None
        assert evidence_set.locked_by == "test-reviewer"
        pack = await session.get(OriginalityPack, first.originality_pack_id)
        assert pack is not None
        assert pack.item_refs_json == []


@pytest.mark.asyncio
async def test_search_only_result_cannot_create_factual_evidence() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_o4_like_plan(session)
        workflow = EvidenceResearchWorkflow(router=FakeEvidenceRouter(with_documents=False))

        result = await workflow.run(
            session,
            request=evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
            ),
        )

        assert result.evidence_ids == []
        assert result.claim_ids == []
        assert result.evidence_set_id is None
        assert result.evidence_eligible is False
        assert any("SEARCH snippets remain ineligible" in gap for gap in result.research_gaps)
        evidence_count = await session.scalar(select(func.count()).select_from(Evidence))
        assert evidence_count == 0


@pytest.mark.asyncio
async def test_community_source_defaults_to_context_only() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_o4_like_plan(session)
        workflow = EvidenceResearchWorkflow(
            router=FakeEvidenceRouter(
                source_type="community_or_review",
                commercial_bias=CommercialBias.UNKNOWN,
                intended_use=IntendedUse.DISCOVERY,
            )
        )

        result = await workflow.run(
            session,
            request=evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
            ),
        )

        assert result.relation_counts["supports"] == 0
        assert result.relation_counts["context_only"] > 0


@pytest.mark.asyncio
async def test_explicit_evidence_excerpt_must_exist_in_read_document() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_o4_like_plan(session)
        workflow = EvidenceResearchWorkflow(router=FakeEvidenceRouter())
        invalid = (
            ClaimCandidate(
                statement="Unsupported statement",
                source_url="https://example.test/art-pricing",
                locator="reviewed_sentence:missing",
                excerpt="This exact excerpt does not exist in the source.",
                relation=EvidenceRelation.SUPPORTS,
            ),
        )

        with pytest.raises(ValueError, match="evidence_excerpt_not_found_in_source_document"):
            await workflow.run(
                session,
                request=evidence_request(
                    project_id=project.id,
                    need_id=need.id,
                    opportunity_id=opportunity.id,
                    explicit_candidates=invalid,
                ),
            )


@pytest.mark.asyncio
async def test_originality_pack_keeps_motgu_refs_separate_from_web_evidence() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_o4_like_plan(
            session,
            motgu_material_refs=["motgu:studio-pricing-note"],
        )
        workflow = EvidenceResearchWorkflow(router=FakeEvidenceRouter())

        result = await workflow.run(
            session,
            request=evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
            ),
        )

        assert result.originality_item_count == 1
        pack = await session.get(OriginalityPack, result.originality_pack_id)
        assert pack is not None
        assert pack.item_refs_json == [
            {"type": "motgu_material_ref", "ref": "motgu:studio-pricing-note"}
        ]
        assert "External web evidence is intentionally excluded" in pack.summary
