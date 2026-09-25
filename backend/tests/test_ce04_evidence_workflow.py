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
from app.modules.knowledge.evidence_set_approval import approve_evidence_set
from app.modules.knowledge.models import (
    Evidence,
    EvidenceSet,
    OriginalityPack,
    Source,
    SourceDocument,
)
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
from app.modules.research.evidence.persistence import lock_evidence_set


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


class CrossLanguageEvidenceRouter:
    def __init__(
        self,
        *,
        source_type: str = "institutional",
        commercial_bias: CommercialBias = CommercialBias.LOW,
        intended_use: IntendedUse = IntendedUse.EVIDENCE_CANDIDATE,
        candidate_url: str = "https://museum.gov.example/conservation/oil-paintings",
        final_url: str | None = None,
        title: str = "Conservation guidance for oil paintings",
        snippet: str = (
            "Museum guidance covers paintings, light exposure, humidity, handling, and storage."
        ),
        content: str = (
            "Oil paintings should be kept away from direct sunlight and strong heat sources. "
            "Stable display conditions help reduce avoidable environmental stress.\n\n"
            "The visitor cafe opened a new seasonal menu last summer."
        ),
    ) -> None:
        self.source_type = source_type
        self.commercial_bias = commercial_bias
        self.intended_use = intended_use
        self.candidate_url = candidate_url
        self.final_url = final_url or candidate_url
        self.title = title
        self.snippet = snippet
        self.content = content

    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> ProductionResearchResult:
        del session, run_id, step_run_id
        source = SourceCandidate(
            provider="exa",
            query=request.query,
            url=self.candidate_url,
            title=self.title,
            snippet=self.snippet,
            source_type=self.source_type,
            commercial_bias=self.commercial_bias,
            intended_use=self.intended_use,
        )
        return ProductionResearchResult(
            request=request,
            source_candidates=[source],
            selected_sources=[source],
            documents=[
                PageDocument(
                    provider="jina",
                    url=self.final_url,
                    requested_url=self.candidate_url,
                    final_url=self.final_url,
                    title=self.title,
                    content=self.content,
                )
            ],
            stop_reason="exa_sufficient",
            sufficient=True,
        )


async def selected_vi_conservation_plan(
    session: AsyncSession,
) -> tuple[Project, NeedHypothesis, ContentOpportunity]:
    project = (
        await session.execute(select(Project).where(Project.slug == "motgu"))
    ).scalar_one()
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement=(
            "Người sở hữu tranh sơn dầu cần biết cách chăm sóc tác phẩm trong khí hậu "
            "nóng ẩm mà không tự thực hiện phục chế rủi ro."
        ),
        audience_scope="người sở hữu tranh sơn dầu",
        situation="đang treo, cất giữ hoặc vận chuyển tranh trong khí hậu nóng ẩm",
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
        locale="vi-VN",
        reader="người sở hữu tranh sơn dầu",
        situation="đang chăm sóc tranh trong khí hậu nóng ẩm",
        need="giảm nguy cơ hư hại mà không tự phục chế",
        question=(
            "Người sở hữu nên chăm sóc tranh sơn dầu như thế nào trong khí hậu nóng ẩm?"
        ),
        intent="learn",
        promise="đưa ra checklist chăm sóc tranh có căn cứ",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="hướng dẫn chăm sóc tranh sau khi mua",
        next_discovery_step="evidence research",
        decision="CREATE",
        priority="NOW",
        reasons_json=["founder selected"],
        suggested_content_type="journal",
        suggested_role="cluster",
        selected_by="founder",
        selected_at=datetime.now(UTC),
        selection_reason="selected for cross-language evidence regression",
    )
    session.add(opportunity)
    await session.flush()
    return project, need, opportunity


def vi_evidence_request(
    *,
    project_id: UUID,
    need_id: UUID,
    opportunity_id: UUID,
) -> EvidenceResearchRequest:
    return EvidenceResearchRequest(
        research=ProductionResearchRequest(
            project_id=project_id,
            query=(
                "Người sở hữu nên chăm sóc tranh sơn dầu như thế nào trong khí hậu nóng ẩm?"
            ),
            locale="vi-VN",
            country="vn",
            max_pages_to_read=2,
            required_intended_use=IntendedUse.EVIDENCE_CANDIDATE,
        ),
        content_opportunity_id=opportunity_id,
        need_hypothesis_id=need_id,
        max_claims=8,
    )




async def selected_o4_like_plan(
    session: AsyncSession,
    *,
    motgu_material_refs: list[str] | None = None,
    coverage_requirements: list[str] | None = None,
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
        coverage_requirements_json=list(coverage_requirements or []),
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


class CapturingTopicWorkflow(EvidenceResearchWorkflow):
    def __init__(self, *, router: FakeEvidenceRouter) -> None:
        super().__init__(router=router)
        self.captured_topic_texts: tuple[str, ...] | None = None

    def _extract_claim_candidates(
        self,
        production: ProductionResearchResult,
        *,
        subject_text: str,
        topic_texts: tuple[str, ...],
        limit: int,
    ) -> list[ClaimCandidate]:
        del production, subject_text, limit
        self.captured_topic_texts = topic_texts
        return []


@pytest.mark.asyncio
async def test_evidence_workflow_includes_founder_coverage_in_extraction_topics() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_o4_like_plan(
            session,
            coverage_requirements=[
                "Explain safe display conditions.",
                "Explain safe handling and transport.",
            ],
        )
        workflow = CapturingTopicWorkflow(router=FakeEvidenceRouter())
        await workflow.run(
            session,
            request=evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
            ),
        )

        assert workflow.captured_topic_texts == (
            opportunity.question,
            opportunity.need,
            opportunity.promise,
            "Explain safe display conditions.",
            "Explain safe handling and transport.",
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
        )

        first = await workflow.run(session, request=request)
        draft = await session.get(EvidenceSet, first.evidence_set_id)
        assert draft is not None
        approval = await approve_evidence_set(
            session,
            evidence_set_id=draft.id,
            expected_version=draft.version,
            expected_content_hash=draft.content_hash,
            approved_by="test-reviewer",
            approval_reason="test reviewed evidence set",
        )
        await lock_evidence_set(
            session,
            evidence_set_id=draft.id,
            locked_by="test-reviewer",
            approval_id=approval.id,
        )
        second = await workflow.run(session, request=request)

        assert first.content_case_id == second.content_case_id
        assert first.evidence_set_id == second.evidence_set_id
        assert first.originality_pack_id == second.originality_pack_id
        assert first.evidence_ids == second.evidence_ids
        assert first.relation_counts["contradicts"] == 1
        assert first.evidence_eligible is True
        assert first.evidence_set_status == "draft"
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
        evidence_count_before = await session.scalar(select(func.count()).select_from(Evidence))

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
        assert evidence_count == evidence_count_before


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
        assert result.relation_counts["qualifies"] == 0
        assert result.relation_counts["context_only"] > 0
        assert result.evidence_eligible is False
        assert any(
            "No Evidence member can support or qualify factual claims" in gap
            for gap in result.research_gaps
        )


@pytest.mark.asyncio
async def test_qualifying_evidence_is_eligible_even_with_context_only_sources() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_o4_like_plan(session)
        workflow = EvidenceResearchWorkflow(
            router=FakeEvidenceRouter(
                source_type="community_or_review",
                commercial_bias=CommercialBias.UNKNOWN,
                intended_use=IntendedUse.DISCOVERY,
            )
        )
        explicit = (
            ClaimCandidate(
                statement="The source qualifies when a buyer should rely on professional advice.",
                source_url="https://example.test/art-pricing",
                locator="reviewed_sentence:2",
                excerpt="There is no single formula that proves an artwork is fairly priced.",
                relation=EvidenceRelation.QUALIFIES,
            ),
        )

        result = await workflow.run(
            session,
            request=evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
                explicit_candidates=explicit,
            ),
        )

        assert result.relation_counts["supports"] == 0
        assert result.relation_counts["qualifies"] == 1
        assert result.relation_counts["context_only"] > 0
        assert result.evidence_eligible is True
        assert not any(
            "No Evidence member can support or qualify factual claims" in gap
            for gap in result.research_gaps
        )


@pytest.mark.asyncio
async def test_vi_brief_can_extract_support_from_english_institutional_document() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_vi_conservation_plan(session)
        workflow = EvidenceResearchWorkflow(router=CrossLanguageEvidenceRouter())

        result = await workflow.run(
            session,
            request=vi_evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
            ),
        )

        assert result.relation_counts["supports"] > 0
        assert result.relation_counts["qualifies"] == 0
        assert result.evidence_eligible is True


@pytest.mark.asyncio
async def test_vi_brief_keeps_cross_language_community_evidence_context_only() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_vi_conservation_plan(session)
        workflow = EvidenceResearchWorkflow(
            router=CrossLanguageEvidenceRouter(
                source_type="community_or_review",
                commercial_bias=CommercialBias.UNKNOWN,
                intended_use=IntendedUse.DISCOVERY,
            )
        )

        result = await workflow.run(
            session,
            request=vi_evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
            ),
        )

        assert result.relation_counts["supports"] == 0
        assert result.relation_counts["qualifies"] == 0
        assert result.relation_counts["context_only"] > 0
        assert result.evidence_eligible is False


@pytest.mark.asyncio
async def test_vi_brief_keeps_cross_language_educational_discovery_context_only() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_vi_conservation_plan(session)
        workflow = EvidenceResearchWorkflow(
            router=CrossLanguageEvidenceRouter(
                source_type="educational",
                commercial_bias=CommercialBias.LOW,
                intended_use=IntendedUse.DISCOVERY,
                candidate_url="https://artschool.example.edu.vn/oil-painting-care",
            )
        )

        result = await workflow.run(
            session,
            request=vi_evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
            ),
        )

        assert result.relation_counts["supports"] == 0
        assert result.relation_counts["qualifies"] == 0
        assert result.relation_counts["context_only"] > 0
        assert result.evidence_eligible is False

        document = await session.get(SourceDocument, result.source_document_ids[0])
        assert document is not None
        source = await session.get(Source, document.source_id)
        assert source is not None
        assert source.source_type == "educational"
        assert source.provenance_json["intended_use"] == "discovery"
        assert source.provenance_json["evidence_candidate"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "intended_use",
    [IntendedUse.DISCOVERY, IntendedUse.CONTEXT_ONLY],
)
async def test_source_type_alone_cannot_promote_non_evidence_use_to_support(
    intended_use: IntendedUse,
) -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_vi_conservation_plan(session)
        workflow = EvidenceResearchWorkflow(
            router=CrossLanguageEvidenceRouter(
                source_type="institutional",
                commercial_bias=CommercialBias.LOW,
                intended_use=intended_use,
            )
        )

        result = await workflow.run(
            session,
            request=vi_evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
            ),
        )

        assert result.relation_counts["supports"] == 0
        assert result.relation_counts["qualifies"] == 0
        assert result.relation_counts["context_only"] > 0
        assert result.evidence_eligible is False




@pytest.mark.asyncio
async def test_source_title_anchor_does_not_admit_unrelated_institutional_sentence() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_vi_conservation_plan(session)
        workflow = EvidenceResearchWorkflow(
            router=CrossLanguageEvidenceRouter(
                content=(
                    "The visitor cafe opened a new seasonal menu last summer and extended "
                    "its evening opening hours for tourists."
                )
            )
        )

        result = await workflow.run(
            session,
            request=vi_evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
            ),
        )

        assert result.evidence_ids == []
        assert result.relation_counts["supports"] == 0
        assert result.evidence_eligible is False


@pytest.mark.asyncio
async def test_redirected_read_url_preserves_institutional_source_relation() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_vi_conservation_plan(session)
        workflow = EvidenceResearchWorkflow(
            router=CrossLanguageEvidenceRouter(
                candidate_url="https://museum.gov.example/conservation/oil-paintings",
                final_url="https://museum.gov.example/conservation/oil-paintings/index.html",
            )
        )

        result = await workflow.run(
            session,
            request=vi_evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
            ),
        )

        assert result.relation_counts["supports"] > 0
        assert result.relation_counts["context_only"] == 0
        assert result.evidence_eligible is True




@pytest.mark.asyncio
async def test_same_language_title_anchor_cannot_override_need_relevance() -> None:
    async with isolated_session() as session:
        project, need, opportunity = await selected_o4_like_plan(session)
        source_url = "https://museum.example/auction-results"
        source = SourceCandidate(
            provider="exa",
            query="art appraisal valuation factors comparable sales price",
            url=source_url,
            title="Auction result",
            snippet="Auction result from a recent sale.",
            source_type="institutional",
            commercial_bias=CommercialBias.LOW,
            intended_use=IntendedUse.EVIDENCE_CANDIDATE,
        )

        class SameLanguageIrrelevantRouter:
            async def run(
                self,
                session: AsyncSession,
                *,
                request: ProductionResearchRequest,
                run_id: UUID | None = None,
                step_run_id: UUID | None = None,
            ) -> ProductionResearchResult:
                del session, run_id, step_run_id
                return ProductionResearchResult(
                    request=request,
                    source_candidates=[source],
                    selected_sources=[source],
                    documents=[
                        PageDocument(
                            provider="jina",
                            url=source_url,
                            requested_url=source_url,
                            final_url=source_url,
                            title="Auction result",
                            content=(
                                "The price was $9,500 and the lot closed after a short auction "
                                "with several bids recorded during the sale."
                            ),
                        )
                    ],
                    stop_reason="exa_sufficient",
                    sufficient=True,
                )

        workflow = EvidenceResearchWorkflow(router=SameLanguageIrrelevantRouter())
        result = await workflow.run(
            session,
            request=evidence_request(
                project_id=project.id,
                need_id=need.id,
                opportunity_id=opportunity.id,
            ),
        )

        assert result.evidence_ids == []
        assert result.relation_counts["supports"] == 0
        assert result.evidence_eligible is False




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

        assert result.originality_item_count == 0
        assert any(
            "Reference-only items do not close this gap" in gap
            for gap in result.research_gaps
        )
        pack = await session.get(OriginalityPack, result.originality_pack_id)
        assert pack is not None
        assert pack.item_refs_json == [
            {"type": "reference_only", "source_ref": "motgu:studio-pricing-note"}
        ]
        assert "External web evidence is intentionally excluded" in pack.summary
