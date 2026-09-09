from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    ContentOpportunitySignal,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
)
from app.modules.content_engine.models import Signal as DBSignal
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    EvidenceSet,
    Source,
    SourceDocument,
)
from app.modules.knowledge.persistence import content_hash
from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    PageDocument,
    ProductionResearchRequest,
    ProductionResearchResult,
    ResearchSignalKind,
    SearchSignal,
    SourceCandidate,
    utc_now_iso,
)
from app.modules.research.discovery import DiscoveryResearchWorkflow, DiscoveryWorkflowRequest
from app.modules.research.evidence import (
    ClaimCandidate,
    EvidenceRelation,
    EvidenceResearchRequest,
    EvidenceResearchWorkflow,
)
from app.modules.research.evidence.persistence import (
    persist_claim_evidence,
    persist_read_documents,
)
from app.modules.research.keyword_plan.contracts import (
    NeedType,
    SignalScope,
    SignalSourceKind,
)
from app.modules.research.keyword_plan.normalize import make_observed_signal
from app.modules.research.keyword_plan.service import OpportunityMapRequest

O4_OPPORTUNITY_ID = UUID("068991ab-de34-4787-9c38-8935c3f0e2da")
O4_CONTENT_CASE_ID = UUID("9ec6133b-5f14-46d0-9866-e3b049e537b5")
O4_NEED_ID = UUID("530bdd27-f008-4910-9b3b-df83e007cfa2")
O4_EVIDENCE_SET_ID = UUID("c5d46edb-3557-4efb-a479-8dd5702ae6c9")
O4_ORIGINALITY_PACK_ID = UUID("6bd287ec-43f9-4d69-957c-2223f258f909")


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


class StubRouter:
    def __init__(self, result: ProductionResearchResult) -> None:
        self.result = result
        self.calls = 0

    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> ProductionResearchResult:
        del session, run_id, step_run_id
        self.calls += 1
        assert request is self.result.request
        return self.result


@dataclass
class SelectedFixture:
    project: Project
    need: NeedHypothesis
    opportunity: ContentOpportunity
    content_case: ContentCase


async def _selected_fixture(session: AsyncSession) -> SelectedFixture:
    project = Project(
        slug=f"signal-boundary-{uuid4().hex}",
        name="Discovery signal boundary fixture",
        status="active",
        default_locale="en",
    )
    session.add(project)
    await session.flush()

    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement="A buyer wants source-backed context before pricing an artwork.",
        audience_scope="first-time art buyer",
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
        reader="first-time art buyer",
        situation="considering a purchase",
        need="source-backed artwork pricing context",
        question="How can a buyer assess an artwork price?",
        intent="evaluate",
        promise="provide source-backed context",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="source-backed price context",
        next_discovery_step="read selected sources",
        decision="CREATE",
        priority="NOW",
        reasons_json=[],
        suggested_content_type="journal",
        selected_by="founder",
        selected_at=datetime.now(UTC),
        selection_reason="synthetic boundary fixture",
    )
    session.add(opportunity)
    await session.flush()

    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="assess an artwork price",
        content_hypothesis="source-backed price context helps evaluation",
        originality_statement="MOTGU material remains separate",
        reader_before="uncertain about price context",
        reader_after="able to assess source-backed context",
        status="draft",
    )
    session.add(content_case)
    await session.flush()
    return SelectedFixture(
        project=project,
        need=need,
        opportunity=opportunity,
        content_case=content_case,
    )


def _production_request(project_id: UUID, query: str) -> ProductionResearchRequest:
    return ProductionResearchRequest(
        project_id=project_id,
        query=query,
        locale="en",
        country="us",
        limit=10,
        max_pages_to_read=1,
    )


def _source_candidate(url: str, query: str) -> SourceCandidate:
    return SourceCandidate(
        provider="serper",
        query=query,
        url=url,
        title="Synthetic discovery result",
        snippet="A factual-looking search snippet that is not a read page.",
        source_type="institutional",
        commercial_bias=CommercialBias.LOW,
        intended_use=IntendedUse.EVIDENCE_CANDIDATE,
    )


async def _row_counts(session: AsyncSession) -> dict[str, int]:
    models = {
        "claims": Claim,
        "evidence": Evidence,
        "evidence_sets": EvidenceSet,
        "source_documents": SourceDocument,
        "sources": Source,
    }
    return {
        name: int(await session.scalar(select(func.count()).select_from(model)))
        for name, model in models.items()
    }


@pytest.mark.asyncio
async def test_discovery_persistence_creates_planning_rows_but_no_factual_evidence() -> None:
    async with isolated_session() as session:
        project = (
            await session.execute(select(Project).where(Project.slug == "motgu"))
        ).scalar_one()
        suffix = uuid4().hex
        query = f"fair original artwork price {suffix}"
        observed_text = f"How can a buyer judge a fair original artwork price {suffix}?"
        source_url = f"https://search.example/discovery/{suffix}"
        production_request = _production_request(project.id, query)
        production = ProductionResearchResult(
            request=production_request,
            signals=[
                SearchSignal(
                    provider="serper",
                    query=query,
                    kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                    text=observed_text,
                    url=source_url,
                    snippet=observed_text,
                    position=1,
                )
            ],
            source_candidates=[_source_candidate(source_url, query)],
            selected_sources=[_source_candidate(source_url, query)],
            sufficient=True,
            stop_reason="synthetic_discovery_complete",
        )
        workflow = DiscoveryResearchWorkflow(router=StubRouter(production))
        discovery_request = DiscoveryWorkflowRequest(
            research=production_request,
            opportunity=OpportunityMapRequest(
                project_id="motgu",
                locale="en",
                audience_scope="first-time art buyer",
                situation="considering an original artwork",
                reader="first-time art buyer",
                need_statement=f"A buyer needs confidence when judging artwork price {suffix}",
                need_type=NeedType.QUESTION,
            ),
        )
        before = await _row_counts(session)

        result = await workflow.run(
            session,
            request=discovery_request,
            persist_plan=True,
        )

        after = await _row_counts(session)
        assert result.planning_refs is not None
        assert result.planning_refs.signal_ids
        assert result.planning_refs.opportunity_ids
        assert after["claims"] == before["claims"]
        assert after["evidence"] == before["evidence"]
        assert after["source_documents"] == before["source_documents"]
        signal_id = next(iter(result.planning_refs.signal_ids.values()))
        signal = await session.get(DBSignal, signal_id)
        assert signal is not None
        assert signal.source_kind == "SEARCH"
        assert signal.scope == "market_web"
        assert signal.observed_text == observed_text
        assert signal.source_url == source_url
        assert signal.provenance_json["provider"] == "serper"
        assert signal.provenance_json["source_ref"] == source_url
        support_link = await session.get(
            NeedHypothesisSignal,
            (result.planning_refs.need_hypothesis_id, signal_id, "supports"),
        )
        assert support_link is not None
        opportunity_link = await session.get(
            ContentOpportunitySignal,
            (next(iter(result.planning_refs.opportunity_ids.values())), signal_id),
        )
        assert opportunity_link is not None
        assert result.evidence_eligible is False


@pytest.mark.asyncio
async def test_signal_url_alone_cannot_create_claim_or_evidence() -> None:
    async with isolated_session() as session:
        project = (
            await session.execute(select(Project).where(Project.slug == "motgu"))
        ).scalar_one()
        suffix = uuid4().hex
        source_url = f"https://search.example/url-only/{suffix}"
        signal = DBSignal(
            project_id=project.id,
            source_kind="SEARCH",
            scope="market_web",
            observed_text="Original artwork prices depend on market context.",
            source_url=source_url,
            locale="en",
            context="synthetic search result",
            captured_at=datetime.now(UTC),
            fingerprint=content_hash(suffix),
            provenance_json={"provider": "serper", "query": "artwork price"},
        )
        session.add(signal)
        await session.flush()
        before = await _row_counts(session)

        with pytest.raises(ValueError, match="evidence_source_must_be_successfully_read"):
            await persist_claim_evidence(
                session,
                project_id=project.id,
                page_refs={},
                candidate=ClaimCandidate(
                    statement="Original artwork prices depend on market context.",
                    source_url=signal.source_url or "",
                    locator="search:1",
                    excerpt=signal.observed_text,
                ),
            )

        after = await _row_counts(session)
        assert after["claims"] == before["claims"]
        assert after["evidence"] == before["evidence"]


@pytest.mark.asyncio
async def test_evidence_candidate_without_read_document_stays_a_gap() -> None:
    async with isolated_session() as session:
        fixture = await _selected_fixture(session)
        query = f"evidence candidate without read {uuid4().hex}"
        source_url = f"https://search.example/no-page/{uuid4()}"
        production_request = _production_request(fixture.project.id, query)
        production = ProductionResearchResult(
            request=production_request,
            signals=[
                SearchSignal(
                    provider="serper",
                    query=query,
                    kind=ResearchSignalKind.ORGANIC,
                    text="A search snippet that looks factual but was not read.",
                    url=source_url,
                    snippet="A search snippet that looks factual but was not read.",
                    position=2,
                )
            ],
            source_candidates=[_source_candidate(source_url, query)],
            selected_sources=[_source_candidate(source_url, query)],
            documents=[],
            sufficient=False,
            stop_reason="no_successful_page_read",
        )
        router = StubRouter(production)
        workflow = EvidenceResearchWorkflow(router=router)
        before = await _row_counts(session)

        result = await workflow.run(
            session,
            request=EvidenceResearchRequest(
                research=production_request,
                content_opportunity_id=fixture.opportunity.id,
                need_hypothesis_id=fixture.need.id,
            ),
        )

        after = await _row_counts(session)
        assert router.calls == 1
        assert result.claim_ids == []
        assert result.evidence_ids == []
        assert result.evidence_set_id is None
        assert result.evidence_eligible is False
        assert any("No external page was read successfully" in gap for gap in result.research_gaps)
        assert any("SEARCH snippets remain ineligible" in gap for gap in result.research_gaps)
        assert any("No source-backed Claim/Evidence link" in gap for gap in result.research_gaps)
        assert after["claims"] == before["claims"]
        assert after["evidence"] == before["evidence"]
        assert after["evidence_sets"] == before["evidence_sets"]


@pytest.mark.asyncio
async def test_successful_read_is_required_before_positive_evidence_link() -> None:
    async with isolated_session() as session:
        fixture = await _selected_fixture(session)
        suffix = uuid4().hex
        query = f"read artwork price source {suffix}"
        source_url = f"https://source.example/read/{suffix}"
        signal = make_observed_signal(
            source_kind=SignalSourceKind.SEARCH,
            scope=SignalScope.MARKET_WEB,
            observed_text=f"Search lead differs from the source page {suffix}.",
            locale="en",
            provider="serper",
            method="organic",
            context="synthetic discovery lead",
            captured_at=utc_now_iso(),
            source_url=source_url,
            locator="position:1",
        )
        page_excerpt = (
            "The read page states that market context should be considered before pricing."
        )
        production_request = _production_request(fixture.project.id, query)
        source_candidate = _source_candidate(source_url, query)
        production = ProductionResearchResult(
            request=production_request,
            signals=[
                SearchSignal(
                    provider="serper",
                    query=query,
                    kind=ResearchSignalKind.ORGANIC,
                    text=signal.observed_text,
                    url=source_url,
                    position=1,
                )
            ],
            source_candidates=[source_candidate],
            selected_sources=[source_candidate],
            documents=[
                PageDocument(
                    provider="jina",
                    url=source_url,
                    requested_url=source_url,
                    final_url=source_url,
                    title="Read source",
                    content=f"Page heading.\n\n{page_excerpt}\n\nPage closing.",
                )
            ],
            sufficient=True,
            stop_reason="read_success",
        )
        page_refs = await persist_read_documents(session, production=production)
        link = await persist_claim_evidence(
            session,
            project_id=fixture.project.id,
            page_refs=page_refs,
            candidate=ClaimCandidate(
                statement=page_excerpt,
                source_url=source_url,
                locator="document_sentence:2",
                excerpt=page_excerpt,
                relation=EvidenceRelation.SUPPORTS,
            ),
        )

        evidence = await session.get(Evidence, link.evidence_id)
        claim = await session.get(Claim, link.claim_id)
        assert evidence is not None
        assert claim is not None
        assert evidence.claim_id == claim.id
        assert evidence.source_document_id is not None
        document = await session.get(SourceDocument, evidence.source_document_id)
        assert document is not None
        source = await session.get(Source, document.source_id)
        assert source is not None
        assert evidence.excerpt == page_excerpt
        assert evidence.excerpt in document.content_markdown
        assert document.source_id == source.id
        assert evidence.provenance_json["source_id"] == str(source.id)
        assert evidence.provenance_json["source_document_id"] == str(document.id)
        assert evidence.provenance_json["source_document_hash"] == document.content_hash
        assert evidence.quality_metadata_json["search_rank_used_as_authority"] is False
        assert str(signal.id) not in json.dumps(evidence.provenance_json)
        assert "signal_id" not in Evidence.__table__.columns


@pytest.mark.asyncio
async def test_signal_text_cannot_be_used_as_excerpt_when_page_differs() -> None:
    async with isolated_session() as session:
        fixture = await _selected_fixture(session)
        suffix = uuid4().hex
        source_url = f"https://source.example/different/{suffix}"
        signal_text = "The search snippet claims every original artwork price is fair."
        page_excerpt = "The read page contains a different source-backed observation."
        query = f"different source text {suffix}"
        source_candidate = _source_candidate(source_url, query)
        production = ProductionResearchResult(
            request=_production_request(fixture.project.id, query),
            source_candidates=[source_candidate],
            selected_sources=[source_candidate],
            documents=[
                PageDocument(
                    provider="jina",
                    url=source_url,
                    final_url=source_url,
                    content=f"Heading.\n\n{page_excerpt}",
                )
            ],
            sufficient=True,
            stop_reason="read_success",
        )
        page_refs = await persist_read_documents(session, production=production)
        before = await _row_counts(session)

        with pytest.raises(ValueError, match="evidence_excerpt_not_found_in_source_document"):
            await persist_claim_evidence(
                session,
                project_id=fixture.project.id,
                page_refs=page_refs,
                candidate=ClaimCandidate(
                    statement=signal_text,
                    source_url=source_url,
                    locator="search:1",
                    excerpt=signal_text,
                ),
            )

        after = await _row_counts(session)
        assert after["claims"] == before["claims"]
        assert after["evidence"] == before["evidence"]


@pytest.mark.asyncio
async def test_search_rank_is_not_factual_authority() -> None:
    async with isolated_session() as session:
        fixture = await _selected_fixture(session)
        suffix = uuid4().hex
        query = f"rank authority boundary {suffix}"
        source_url = f"https://source.example/rank/{suffix}"
        source_candidate = _source_candidate(source_url, query)
        production = ProductionResearchResult(
            request=_production_request(fixture.project.id, query),
            signals=[
                SearchSignal(
                    provider="serper",
                    query=query,
                    kind=ResearchSignalKind.ORGANIC,
                    text="Ranked search lead",
                    url=source_url,
                    position=1,
                )
            ],
            source_candidates=[source_candidate],
            selected_sources=[source_candidate],
            documents=[
                PageDocument(
                    provider="jina",
                    url=source_url,
                    final_url=source_url,
                    content="A read document with a source-backed price observation.",
                )
            ],
            sufficient=True,
            stop_reason="read_success",
        )
        page_refs = await persist_read_documents(session, production=production)
        excerpt = "A read document with a source-backed price observation."
        link = await persist_claim_evidence(
            session,
            project_id=fixture.project.id,
            page_refs=page_refs,
            candidate=ClaimCandidate(
                statement=excerpt,
                source_url=source_url,
                locator="document_sentence:1",
                excerpt=excerpt,
            ),
        )
        evidence = await session.get(Evidence, link.evidence_id)
        assert evidence is not None
        assert evidence.quality_metadata_json["search_rank_used_as_authority"] is False
        assert evidence.authority_level == "institutional_candidate"
