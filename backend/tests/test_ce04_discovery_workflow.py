from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    PageDocument,
    ProductionResearchRequest,
    ProductionResearchResult,
    ProviderDecision,
    ProviderDecisionStatus,
    ResearchSignalKind,
    SearchSignal,
    SourceCandidate,
    SourceRelation,
)
from app.modules.research.discovery import (
    DiscoveryResearchWorkflow,
    DiscoveryWorkflowRequest,
    MarketObservation,
)
from app.modules.research.keyword_plan.contracts import (
    HypothesisStatus,
    NeedType,
    SignalSourceKind,
)
from app.modules.research.keyword_plan.service import OpportunityMapRequest

SEED = "First-time art buyer worries about choosing the wrong painting."
REDDIT = "https://www.reddit.com/r/artcollecting/comments/example"
COMMERCIAL = "https://gallery.example/shop/first-painting"
INSTITUTIONAL = "https://museum.example/collecting-guide"


class FakeRouter:
    def __init__(self, result: ProductionResearchResult) -> None:
        self.result = result
        self.calls: list[tuple[UUID | None, UUID | None]] = []

    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> ProductionResearchResult:
        del session
        assert request is self.result.request
        self.calls.append((run_id, step_run_id))
        return self.result


def _research_request() -> ProductionResearchRequest:
    return ProductionResearchRequest(
        project_id=uuid4(),
        query=SEED,
        locale="en",
        country="us",
        limit=10,
        max_pages_to_read=1,
    )


def _opportunity_request() -> OpportunityMapRequest:
    return OpportunityMapRequest(
        project_id="motgu",
        locale="en",
        audience_scope="international first-time art buyer",
        situation="interested in original art but uncertain how to choose",
        reader="international first-time art buyer",
        need_statement=SEED,
        need_type=NeedType.PAIN,
    )


def _question_signal(text: str) -> SearchSignal:
    return SearchSignal(
        provider="serper",
        query=SEED,
        kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
        text=text,
    )


def _source(
    url: str,
    *,
    source_type: str,
    bias: CommercialBias,
    title: str = "Source",
) -> SourceCandidate:
    return SourceCandidate(
        provider="serper",
        query=SEED,
        url=url,
        title=title,
        source_type=source_type,
        commercial_bias=bias,
        intended_use=IntendedUse.DISCOVERY,
        relation=SourceRelation.DIRECT,
        why_selected="Discovery source classification.",
    )


def _result(
    request: ProductionResearchRequest,
    *,
    signals: list[SearchSignal] | None = None,
    sources: list[SourceCandidate] | None = None,
    documents: list[PageDocument] | None = None,
    sufficient: bool = True,
    stop_reason: str = "serper_sufficient",
) -> ProductionResearchResult:
    return ProductionResearchResult(
        request=request,
        decisions=[
            ProviderDecision(
                provider="internal_knowledge",
                status=ProviderDecisionStatus.CALLED,
                reason="insufficient_for_request_external_search_required",
            )
        ],
        signals=signals or [],
        source_candidates=sources or [],
        selected_sources=sources or [],
        documents=documents or [],
        sufficient=sufficient,
        stop_reason=stop_reason,
    )


def _workflow(result: ProductionResearchResult) -> tuple[DiscoveryResearchWorkflow, FakeRouter]:
    router = FakeRouter(result)
    return DiscoveryResearchWorkflow(router=router), router


@pytest.mark.asyncio
async def test_discovery_uses_router_once_and_keeps_search_signal_as_search() -> None:
    request = _research_request()
    signals = [
        SearchSignal(
            provider="serper",
            query=SEED,
            kind=ResearchSignalKind.ORGANIC,
            text="New to buying art? Community discussion",
            url=REDDIT,
            position=1,
        ),
        _question_signal("How do I know what art I like?"),
        _question_signal("How much should I spend on my first painting?"),
    ]
    result = _result(
        request,
        signals=signals,
        sources=[_source(REDDIT, source_type="community_or_review", bias=CommercialBias.UNKNOWN)],
    )
    workflow, router = _workflow(result)

    discovery = await workflow.run(
        cast(AsyncSession, object()),
        request=DiscoveryWorkflowRequest(
            research=request,
            opportunity=_opportunity_request(),
        ),
    )

    assert len(router.calls) == 1
    reddit_signal = next(item for item in discovery.opportunity_map.signals if item.source_url == REDDIT)
    assert reddit_signal.source_kind is SignalSourceKind.SEARCH
    assert not any(item.source_kind is SignalSourceKind.MARKET for item in discovery.opportunity_map.signals)
    assert discovery.evidence_eligible is False
    assert discovery.artifact_type == "discovery_research_report"


@pytest.mark.asyncio
async def test_unreadable_market_observation_becomes_gap_not_market_signal() -> None:
    request = _research_request()
    result = _result(
        request,
        signals=[_question_signal("How much should I spend on my first painting?")],
        sources=[_source(REDDIT, source_type="community_or_review", bias=CommercialBias.UNKNOWN)],
        documents=[],
        sufficient=False,
        stop_reason="bounded_search_exhausted",
    )
    workflow, _ = _workflow(result)

    discovery = await workflow.run(
        cast(AsyncSession, object()),
        request=DiscoveryWorkflowRequest(
            research=request,
            opportunity=_opportunity_request(),
            market_observations=(
                MarketObservation(
                    source_url=REDDIT,
                    observed_text="I was nervous about overspending on my first painting.",
                    locator="comment:abc",
                ),
            ),
        ),
    )

    assert not any(item.source_kind is SignalSourceKind.MARKET for item in discovery.opportunity_map.signals)
    assert any("not read successfully" in gap for gap in discovery.research_gaps)
    assert any("bounded_search_exhausted" in gap for gap in discovery.research_gaps)


@pytest.mark.asyncio
async def test_readable_market_observation_requires_locator_and_preserves_provenance() -> None:
    request = _research_request()
    document = PageDocument(
        provider="jina",
        url=REDDIT,
        requested_url=REDDIT,
        final_url=REDDIT,
        title="Community thread",
        content="Readable community content.",
    )
    result = _result(
        request,
        signals=[
            _question_signal("How do I know what art I like?"),
            _question_signal("How much should I spend on my first painting?"),
        ],
        sources=[_source(REDDIT, source_type="community_or_review", bias=CommercialBias.UNKNOWN)],
        documents=[document],
    )
    workflow, _ = _workflow(result)

    discovery = await workflow.run(
        cast(AsyncSession, object()),
        request=DiscoveryWorkflowRequest(
            research=request,
            opportunity=_opportunity_request(),
            artifact_ref="artifact:discovery-1",
            market_observations=(
                MarketObservation(
                    source_url=REDDIT,
                    observed_text="I was nervous about overspending on my first painting.",
                    locator="comment:abc",
                    external_id="reddit:abc",
                ),
            ),
        ),
    )

    market = next(
        item for item in discovery.opportunity_map.signals if item.source_kind is SignalSourceKind.MARKET
    )
    assert market.provenance.provider == "jina"
    assert market.provenance.method == "read_observation"
    assert market.provenance.locator == "comment:abc"
    assert market.provenance.artifact_ref == "artifact:discovery-1"
    assert market.source_url == REDDIT

    with pytest.raises(ValueError, match="market_observation_locator_required"):
        await workflow.run(
            cast(AsyncSession, object()),
            request=DiscoveryWorkflowRequest(
                research=request,
                opportunity=_opportunity_request(),
                market_observations=(
                    MarketObservation(
                        source_url=REDDIT,
                        observed_text="Observation",
                        locator="",
                    ),
                ),
            ),
        )


@pytest.mark.asyncio
async def test_duplicate_market_observations_do_not_count_as_independent_support() -> None:
    request = _research_request()
    second_url = f"{REDDIT}/duplicate"
    documents = [
        PageDocument(provider="jina", url=REDDIT, content="A"),
        PageDocument(provider="jina", url=second_url, content="B"),
    ]
    sources = [
        _source(REDDIT, source_type="community_or_review", bias=CommercialBias.UNKNOWN),
        _source(second_url, source_type="community_or_review", bias=CommercialBias.UNKNOWN),
    ]
    result = _result(
        request,
        signals=[_question_signal("How much should I spend on my first painting?")],
        sources=sources,
        documents=documents,
    )
    workflow, _ = _workflow(result)
    repeated = "I was nervous about overspending on my first painting."

    discovery = await workflow.run(
        cast(AsyncSession, object()),
        request=DiscoveryWorkflowRequest(
            research=request,
            opportunity=_opportunity_request(),
            market_observations=(
                MarketObservation(source_url=REDDIT, observed_text=repeated, locator="comment:a"),
                MarketObservation(source_url=second_url, observed_text=repeated, locator="comment:b"),
            ),
        ),
    )

    market = [
        item for item in discovery.opportunity_map.signals if item.source_kind is SignalSourceKind.MARKET
    ]
    assert len(market) == 2
    assert sum(item.duplicate_of is not None for item in market) == 1


@pytest.mark.asyncio
async def test_rank_one_commercial_source_does_not_receive_high_authority() -> None:
    request = _research_request()
    signals = [
        SearchSignal(
            provider="serper",
            query=SEED,
            kind=ResearchSignalKind.ORGANIC,
            text="Buy your first painting",
            url=COMMERCIAL,
            position=1,
        ),
        SearchSignal(
            provider="serper",
            query=SEED,
            kind=ResearchSignalKind.ORGANIC,
            text="Museum collecting guide",
            url=INSTITUTIONAL,
            position=2,
        ),
    ]
    sources = [
        _source(COMMERCIAL, source_type="commercial", bias=CommercialBias.HIGH),
        _source(INSTITUTIONAL, source_type="institutional", bias=CommercialBias.LOW),
    ]
    workflow, _ = _workflow(_result(request, signals=signals, sources=sources))

    discovery = await workflow.run(
        cast(AsyncSession, object()),
        request=DiscoveryWorkflowRequest(
            research=request,
            opportunity=_opportunity_request(),
        ),
    )

    commercial = next(item for item in discovery.source_metadata if item.url == COMMERCIAL)
    institutional = next(item for item in discovery.source_metadata if item.url == INSTITUTIONAL)
    assert commercial.rank_position == 1
    assert commercial.commercial_bias is CommercialBias.HIGH
    assert commercial.authority_hint == "commercial_context_only"
    assert institutional.rank_position == 2
    assert institutional.authority_hint == "institutional_candidate"
    assert "rank/provider score is excluded" in commercial.metadata_reason


@pytest.mark.asyncio
async def test_handoff_requires_human_selection_and_does_not_promote_hypothesis() -> None:
    request = _research_request()
    result = _result(
        request,
        signals=[
            _question_signal("How do I know what art I like?"),
            _question_signal("How much should I spend on my first painting?"),
        ],
    )
    workflow, _ = _workflow(result)
    discovery = await workflow.run(
        cast(AsyncSession, object()),
        request=DiscoveryWorkflowRequest(
            research=request,
            opportunity=_opportunity_request(),
        ),
    )

    with pytest.raises(ValueError, match="human_selection_required_before_opportunity_handoff"):
        workflow.handoff(discovery)

    selected_id = discovery.opportunity_map.opportunities[0].id
    workflow.select(
        discovery,
        opportunity_id=selected_id,
        selected_by="founder",
        reason="Best planning fit for the next content experiment.",
    )
    handoff = workflow.handoff(discovery)

    assert handoff.opportunity_id == selected_id
    assert discovery.opportunity_map.need_hypothesis.status is HypothesisStatus.PROPOSED
    assert handoff.need_hypothesis_id == discovery.opportunity_map.need_hypothesis.id
