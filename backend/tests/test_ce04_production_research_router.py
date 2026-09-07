from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.research.production as production_module
from app.modules.harness.policy import BudgetLimits
from app.modules.knowledge.retrieval import RetrievalHit
from app.modules.research.contracts import (
    CommercialBias,
    PageDocument,
    PageReadResponse,
    ProductionResearchRequest,
    ProviderCallArtifact,
    ProviderDecisionStatus,
    ProviderResponse,
    ResearchDepth,
    ResearchSignalKind,
    SearchRequest,
    SearchSignal,
    SourceCandidate,
)
from app.modules.research.production import ProductionSufficiencyPolicy, ResearchRouter
from app.modules.research.providers.base import ResearchProviderError


class FakeProvider:
    def __init__(
        self,
        name: str,
        response: ProviderResponse | None = None,
        error: ResearchProviderError | None = None,
    ) -> None:
        self.name = name
        self.response = response or ProviderResponse((), (), ())
        self.error = error
        self.call_count = 0

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return 1

    async def search(self, request: SearchRequest) -> ProviderResponse:
        del request
        self.call_count += 1
        if self.error is not None:
            raise self.error
        return self.response


class FakeReader:
    name = "jina"

    def __init__(
        self,
        error: ResearchProviderError | None = None,
        *,
        failures_before_success: int = 0,
    ) -> None:
        self.error = error
        self.failures_before_success = failures_before_success
        self.urls: list[str] = []

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise ResearchProviderError(
                self.name,
                "read",
                "upstream_http_403",
                failure_class="tool_invalid_response",
            )
        return PageReadResponse(
            document=PageDocument(
                provider=self.name,
                url=url,
                requested_url=url,
                content=f"clean page for {query}",
            ),
            call=ProviderCallArtifact(
                provider=self.name,
                operation="read",
                query=query,
                purpose="selected_url_read",
                status="ok",
                result_count=1,
                raw_excerpt="{}",
            ),
        )


def _signal(text: str, index: int) -> SearchSignal:
    return SearchSignal(
        provider="serper",
        query="seed",
        kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
        text=f"{text}-{index}",
    )


def _source(
    provider: str,
    index: int,
    *,
    bias: CommercialBias = CommercialBias.UNKNOWN,
    url: str | None = None,
) -> SourceCandidate:
    return SourceCandidate(
        provider=provider,
        query="seed",
        url=url or f"https://example.test/{provider}/{index}",
        title=f"source-{provider}-{index}",
        commercial_bias=bias,
    )


def _response(
    provider: str,
    *,
    question_count: int,
    source_count: int,
    low_bias_count: int = 0,
) -> ProviderResponse:
    signals = tuple(_signal(provider, index) for index in range(question_count))
    sources = tuple(
        _source(
            provider,
            index,
            bias=CommercialBias.LOW if index < low_bias_count else CommercialBias.UNKNOWN,
        )
        for index in range(source_count)
    )
    return ProviderResponse(signals, sources, ())


def _hit(*, exact_phrase: bool = False) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid4(),
        source_document_id=uuid4(),
        source_id=uuid4(),
        document_version=1,
        text="first time art buyer price guidance",
        source_type="motgu",
        authority_hint="canonical",
        commercial_bias="low",
        matched_terms=("art", "price"),
        matched_entity_ids=(),
        exact_phrase=exact_phrase,
        ranking_reasons=("ranking_policy:ce04-v1",),
    )


async def _empty_retrieval(*args: object, **kwargs: object) -> tuple[RetrievalHit, ...]:
    del args, kwargs
    return ()


def _session() -> AsyncSession:
    return cast(AsyncSession, object())


@pytest.mark.asyncio
async def test_internal_knowledge_sufficient_skips_all_external_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def retrieve(*args: object, **kwargs: object) -> tuple[RetrievalHit, ...]:
        del args, kwargs
        return (_hit(exact_phrase=True),)

    monkeypatch.setattr(production_module, "retrieve_chunks", retrieve)
    serper = FakeProvider("serper", _response("serper", question_count=3, source_count=3))
    router = ResearchRouter(
        serper=serper,
        sufficiency=ProductionSufficiencyPolicy(min_internal_hits=1),
    )

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(project_id=uuid4(), query="art price"),
    )

    assert result.sufficient is True
    assert result.stop_reason == "internal_knowledge_sufficient"
    assert serper.call_count == 0
    assert any(
        decision.provider == "serper" and decision.status is ProviderDecisionStatus.SKIPPED
        for decision in result.decisions
    )


@pytest.mark.asyncio
async def test_serper_sufficient_stops_before_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = FakeProvider(
        "serper",
        _response("serper", question_count=3, source_count=3, low_bias_count=1),
    )
    tavily = FakeProvider("tavily")
    exa = FakeProvider("exa")
    router = ResearchRouter(serper=serper, tavily=tavily, exa=exa)

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art price",
            max_pages_to_read=0,
        ),
    )

    assert result.sufficient is True
    assert result.stop_reason == "serper_sufficient"
    assert serper.call_count == 1
    assert tavily.call_count == 0
    assert exa.call_count == 0


@pytest.mark.asyncio
async def test_standard_route_uses_one_tavily_fallback_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = FakeProvider(
        "serper",
        _response("serper", question_count=3, source_count=1),
    )
    tavily = FakeProvider(
        "tavily",
        _response("tavily", question_count=0, source_count=2, low_bias_count=1),
    )
    exa = FakeProvider("exa")
    router = ResearchRouter(serper=serper, tavily=tavily, exa=exa)

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art price",
            max_pages_to_read=0,
        ),
    )

    assert result.sufficient is True
    assert result.stop_reason == "tavily_sufficient"
    assert serper.call_count == 1
    assert tavily.call_count == 1
    assert exa.call_count == 0
    assert any(
        decision.provider == "exa" and "bounded_single_fallback" in decision.reason
        for decision in result.decisions
    )


@pytest.mark.asyncio
async def test_deep_route_uses_exa_instead_of_tavily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = FakeProvider(
        "serper",
        _response("serper", question_count=3, source_count=1),
    )
    tavily = FakeProvider("tavily")
    exa = FakeProvider(
        "exa",
        _response("exa", question_count=0, source_count=2, low_bias_count=1),
    )
    router = ResearchRouter(serper=serper, tavily=tavily, exa=exa)

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="original source for art pricing",
            depth=ResearchDepth.DEEP,
            max_pages_to_read=0,
        ),
    )

    assert result.stop_reason == "exa_sufficient"
    assert exa.call_count == 1
    assert tavily.call_count == 0


@pytest.mark.asyncio
async def test_budget_blocks_fallback_without_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = FakeProvider(
        "serper",
        _response("serper", question_count=1, source_count=1),
    )
    tavily = FakeProvider("tavily", _response("tavily", question_count=3, source_count=3))
    router = ResearchRouter(
        serper=serper,
        tavily=tavily,
        budget_limits=BudgetLimits(max_tool_calls=1),
    )

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art price",
            max_pages_to_read=0,
        ),
    )

    assert serper.call_count == 1
    assert tavily.call_count == 0
    assert result.stop_reason == "budget_exceeded_before_tavily"
    assert any(
        decision.failure_class == "budget_exceeded" for decision in result.decisions
    )


@pytest.mark.asyncio
async def test_jina_reads_only_until_page_success_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = FakeProvider(
        "serper",
        _response("serper", question_count=3, source_count=3, low_bias_count=1),
    )
    reader = FakeReader()
    router = ResearchRouter(
        serper=serper,
        reader=reader,
        budget_limits=BudgetLimits(max_tool_calls=4, max_research_sources=3),
    )

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art price",
            max_pages_to_read=1,
        ),
    )

    assert len(result.selected_sources) == 3
    assert reader.urls == [result.selected_sources[0].url]
    assert len(result.documents) == 1


@pytest.mark.asyncio
async def test_reader_failover_tries_next_selected_source_after_page_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = FakeProvider(
        "serper",
        _response("serper", question_count=3, source_count=3, low_bias_count=1),
    )
    reader = FakeReader(failures_before_success=1)
    router = ResearchRouter(
        serper=serper,
        reader=reader,
        budget_limits=BudgetLimits(max_tool_calls=4, max_research_sources=3),
    )

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art price",
            max_pages_to_read=1,
        ),
    )

    assert len(result.selected_sources) == 3
    assert reader.urls == [
        result.selected_sources[0].url,
        result.selected_sources[1].url,
    ]
    assert len(result.documents) == 1
    failed = [
        decision
        for decision in result.decisions
        if decision.provider == "jina" and decision.status is ProviderDecisionStatus.FAILED
    ]
    assert len(failed) == 1
    assert failed[0].reason == "selected_url_read:upstream_http_403"


@pytest.mark.asyncio
async def test_reader_failover_is_bounded_when_all_selected_sources_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = FakeProvider(
        "serper",
        _response("serper", question_count=3, source_count=3, low_bias_count=1),
    )
    reader = FakeReader(
        error=ResearchProviderError(
            "jina",
            "read",
            "upstream_http_403",
            failure_class="tool_invalid_response",
        )
    )
    router = ResearchRouter(
        serper=serper,
        reader=reader,
        budget_limits=BudgetLimits(max_tool_calls=4, max_research_sources=3),
    )

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art price",
            max_pages_to_read=1,
        ),
    )

    assert len(result.selected_sources) == 3
    assert reader.urls == [source.url for source in result.selected_sources]
    assert result.documents == []
    assert result.stop_reason == "jina_candidates_exhausted"


@pytest.mark.asyncio
async def test_reader_failover_stops_when_ce03_budget_is_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = FakeProvider(
        "serper",
        _response("serper", question_count=3, source_count=3, low_bias_count=1),
    )
    reader = FakeReader(failures_before_success=1)
    router = ResearchRouter(
        serper=serper,
        reader=reader,
        budget_limits=BudgetLimits(max_tool_calls=2, max_research_sources=3),
    )

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art price",
            max_pages_to_read=1,
        ),
    )

    assert reader.urls == [result.selected_sources[0].url]
    assert result.documents == []
    assert result.stop_reason == "budget_exceeded_before_jina"


@pytest.mark.asyncio
async def test_selected_shortlist_is_bounded_independently_from_page_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = FakeProvider(
        "serper",
        _response("serper", question_count=3, source_count=5, low_bias_count=1),
    )
    reader = FakeReader()
    router = ResearchRouter(
        serper=serper,
        reader=reader,
        budget_limits=BudgetLimits(max_tool_calls=4, max_research_sources=2),
    )

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art price",
            max_pages_to_read=1,
        ),
    )

    assert len(result.selected_sources) == 2
    assert len(reader.urls) == 1
    assert len(result.documents) == 1


@pytest.mark.asyncio
async def test_provider_failure_preserves_failure_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = FakeProvider(
        "serper",
        error=ResearchProviderError(
            "serper",
            "search",
            "http_429",
            failure_class="provider_rate_limit",
        ),
    )
    router = ResearchRouter(serper=serper)

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art price",
            max_pages_to_read=0,
        ),
    )

    failed = next(
        decision
        for decision in result.decisions
        if decision.provider == "serper" and decision.status is ProviderDecisionStatus.FAILED
    )
    assert failed.failure_class == "provider_rate_limit"
    assert result.stop_reason == "bounded_search_exhausted"


@pytest.mark.asyncio
async def test_duplicate_sources_are_normalized_across_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    duplicate_url = "https://example.test/shared"
    serper_response = ProviderResponse(
        tuple(_signal("serper", index) for index in range(3)),
        (_source("serper", 1, url=duplicate_url),),
        (),
    )
    tavily_response = ProviderResponse(
        (),
        (
            _source("tavily", 1, url=duplicate_url, bias=CommercialBias.LOW),
            _source("tavily", 2, bias=CommercialBias.LOW),
            _source("tavily", 3),
        ),
        (),
    )
    serper = FakeProvider("serper", serper_response)
    tavily = FakeProvider("tavily", tavily_response)
    router = ResearchRouter(serper=serper, tavily=tavily)

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art price",
            max_pages_to_read=0,
        ),
    )

    urls = [source.url for source in result.source_candidates]
    assert urls.count(duplicate_url) == 1
