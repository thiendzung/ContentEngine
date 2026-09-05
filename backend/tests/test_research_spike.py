import httpx
import pytest

from app.modules.research.budget import ResearchBudget
from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    PageDocument,
    PageLink,
    PageReadResponse,
    ProviderCallArtifact,
    ProviderResponse,
    ResearchSignalKind,
    SearchRequest,
    SearchSignal,
    SourceCandidate,
)
from app.modules.research.providers.base import ResearchProviderError
from app.modules.research.providers.exa import ExaProvider
from app.modules.research.providers.jina import JinaReader
from app.modules.research.providers.serper import SerperProvider
from app.modules.research.providers.tavily import TavilyProvider
from app.modules.research.spike import ResearchSpikeService, SufficiencyPolicy


@pytest.mark.asyncio
async def test_serper_normalizes_google_discovery_signals() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search":
            return httpx.Response(
                200,
                json={
                    "peopleAlsoAsk": [{"question": "How do I choose my first painting?"}],
                    "relatedSearches": [{"query": "buy first original painting"}],
                    "organic": [
                        {
                            "title": "Museum collecting guide",
                            "link": "https://examplemuseum.org/guide",
                            "snippet": "A collecting guide.",
                            "position": 1,
                        }
                    ],
                },
            )
        if request.url.path == "/autocomplete":
            return httpx.Response(200, json={"suggestions": [{"value": "how to choose art"}]})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SerperProvider("secret", client)
        response = await provider.search(SearchRequest("first time art buyer"))

    kinds = {signal.kind for signal in response.signals}
    assert ResearchSignalKind.PEOPLE_ALSO_ASK in kinds
    assert ResearchSignalKind.RELATED_SEARCH in kinds
    assert ResearchSignalKind.AUTOCOMPLETE in kinds
    assert ResearchSignalKind.ORGANIC in kinds
    assert response.sources[0].source_type == "institutional"
    assert len(response.calls) == 2


@pytest.mark.asyncio
async def test_serper_keeps_search_results_when_autocomplete_fails() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search":
            return httpx.Response(
                200,
                json={
                    "peopleAlsoAsk": [{"question": "What should I look for in a painting?"}],
                    "organic": [
                        {
                            "title": "Museum guide",
                            "link": "https://museum.example/guide",
                            "position": 1,
                        }
                    ],
                },
            )
        if request.url.path == "/autocomplete":
            return httpx.Response(503, text="temporary failure")
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SerperProvider("secret", client)
        response = await provider.search(SearchRequest("first time art buyer"))

    assert response.sources[0].url == "https://museum.example/guide"
    assert response.calls[1].status == "error"


@pytest.mark.asyncio
async def test_source_discovery_adapters_normalize_results() -> None:
    async def tavily_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer tvly-key"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "University guide",
                        "url": "https://university.edu/art-guide",
                        "content": "Useful context",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(tavily_handler)) as client:
        tavily = TavilyProvider("tvly-key", client)
        response = await tavily.search(SearchRequest("choosing art"))
        assert response.sources[0].provider == "tavily"
        assert response.sources[0].commercial_bias.value == "low"

    async def exa_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "exa-key"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Museum essay",
                        "url": "https://museum.example/essay",
                        "text": "Useful context",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(exa_handler)) as client:
        exa = ExaProvider("exa-key", client)
        response = await exa.search(SearchRequest("choosing art"))
        assert response.sources[0].provider == "exa"
        assert response.calls[0].purpose == "semantic_or_second_hop_discovery"


@pytest.mark.asyncio
async def test_jina_reader_reads_selected_public_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer jina-key"
        assert request.headers["Accept"] == "application/json"
        assert request.headers["X-With-Links-Summary"] == "true"
        assert request.headers["X-Base"] == "final"
        assert request.headers["X-Token-Budget"] == "1234"
        return httpx.Response(200, json={"code": 200, "data": {
            "url": "https://example.org/final/article",
            "title": "Guide",
            "publishedTime": "2026-09-05T00:00:00Z",
            "content": "# Guide\nSee the report.",
            "links": {"report": "https://museum.example/report", "local": "../other"},
        }})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        reader = JinaReader(client, "jina-key", token_budget=1234)
        response = await reader.read("https://example.org/article", query="art buyer")

    assert response.document.requested_url == "https://example.org/article"
    assert response.document.final_url == "https://example.org/final/article"
    assert response.document.title == "Guide"
    assert response.document.provider_timestamp == "2026-09-05T00:00:00Z"
    assert response.document.captured_at
    assert response.document.links[1].url == "https://example.org/other"
    assert response.call.provider == "jina"


class FailingProvider:
    name = "serper"

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return 2

    async def search(self, request: SearchRequest) -> ProviderResponse:
        del request
        raise ResearchProviderError("serper", "search", "temporary_failure")


@pytest.mark.asyncio
async def test_spike_keeps_failure_artifact_when_serper_fails() -> None:
    service = ResearchSpikeService(
        serper=FailingProvider(),
        budget=ResearchBudget(max_provider_calls=2, max_selected_urls=0, max_pages_read=0),
    )

    result = await service.run("seed")

    assert result.calls[0].status == "error"
    assert "temporary_failure" in result.calls[0].reason


class FakeSearchProvider:
    def __init__(self, name: str, response: ProviderResponse, calls: int = 1) -> None:
        self.name = name
        self.response = response
        self.calls = calls
        self.invocations = 0

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return self.calls

    async def search(self, request: SearchRequest) -> ProviderResponse:
        del request
        self.invocations += 1
        return self.response


class FakeReader:
    name = "jina"

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        del query
        return PageReadResponse(
            document=PageDocument(
                provider="jina",
                url=url,
                content="See original report (link provided in JSON summary only).",
                links=(PageLink("https://museum.example/original-report", "Original"),),
            ),
            call=ProviderCallArtifact(
                provider="jina",
                operation="read",
                query="seed",
                purpose="selected_url_read",
                status="ok",
                result_count=1,
                raw_excerpt="excerpt",
            ),
        )


def _response(
    provider: str,
    question_count: int,
    source_count: int,
    *,
    low_bias: bool = True,
) -> ProviderResponse:
    signals = tuple(
        SearchSignal(
            provider=provider,
            query="seed",
            kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
            text=f"question-{index}",
        )
        for index in range(question_count)
    )
    sources = tuple(
        SourceCandidate(
            provider=provider,
            query="seed",
            url=f"https://{provider}-source{index}.example/article",
            title=f"source-{index}",
            source_type="institutional" if low_bias else "commercial",
            commercial_bias=CommercialBias.LOW if low_bias else CommercialBias.HIGH,
            intended_use=(
                IntendedUse.EVIDENCE_CANDIDATE if low_bias else IntendedUse.CONTEXT_ONLY
            ),
        )
        for index in range(source_count)
    )
    call = ProviderCallArtifact(
        provider=provider,
        operation="search",
        query="seed",
        purpose="discovery",
        status="ok",
        result_count=source_count,
        raw_excerpt="{}",
    )
    return ProviderResponse(signals, sources, (call,))


@pytest.mark.asyncio
async def test_spike_stops_when_serper_is_sufficient() -> None:
    serper = FakeSearchProvider("serper", _response("serper", 4, 5), calls=2)
    tavily = FakeSearchProvider("tavily", _response("tavily", 0, 5))
    service = ResearchSpikeService(
        serper=serper,
        tavily=tavily,
        reader=FakeReader(),
        budget=ResearchBudget(max_provider_calls=6, max_selected_urls=1, max_pages_read=1),
    )

    result = await service.run("seed")

    assert serper.invocations == 1
    assert tavily.invocations == 0
    assert result.seed_origin == "founder_proposed"
    assert result.hypothesis_status == "PROPOSED"
    assert len(result.documents) == 1
    assert result.second_hop_candidates[0].relation.value == "second_hop"
    assert result.budget_usage is not None
    assert result.budget_usage.provider_calls_used == 3


@pytest.mark.asyncio
async def test_spike_does_not_stop_on_sales_heavy_serper_sources() -> None:
    serper = FakeSearchProvider(
        "serper",
        _response("serper", 4, 5, low_bias=False),
        calls=2,
    )
    tavily = FakeSearchProvider("tavily", _response("tavily", 0, 1, low_bias=True))
    exa = FakeSearchProvider("exa", _response("exa", 0, 2, low_bias=True))
    service = ResearchSpikeService(
        serper=serper,
        tavily=tavily,
        exa=exa,
        budget=ResearchBudget(max_provider_calls=6, max_selected_urls=2, max_pages_read=0),
        sufficiency=SufficiencyPolicy(
            min_question_signals=4,
            min_source_candidates=5,
            min_low_bias_or_evidence_candidates=1,
        ),
    )

    result = await service.run("seed")

    assert serper.invocations == 1
    assert tavily.invocations == 1
    assert exa.invocations == 0
    assert any(call.reason == "serper_insufficient_or_sales_heavy" for call in result.calls)


@pytest.mark.asyncio
async def test_spike_uses_tavily_then_exa_only_when_needed() -> None:
    serper = FakeSearchProvider("serper", _response("serper", 1, 1), calls=2)
    tavily = FakeSearchProvider("tavily", _response("tavily", 1, 1))
    exa = FakeSearchProvider("exa", _response("exa", 2, 3))
    service = ResearchSpikeService(
        serper=serper,
        tavily=tavily,
        exa=exa,
        budget=ResearchBudget(max_provider_calls=6, max_selected_urls=2, max_pages_read=0),
        sufficiency=SufficiencyPolicy(min_question_signals=4, min_source_candidates=5),
    )

    result = await service.run("seed")

    assert serper.invocations == 1
    assert tavily.invocations == 1
    assert exa.invocations == 1
    assert len(result.source_candidates) == 5
