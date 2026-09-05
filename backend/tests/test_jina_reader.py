import httpx
import pytest

from app.modules.research.budget import ResearchBudget
from app.modules.research.contracts import (
    ProviderResponse,
    SearchRequest,
    SourceCandidate,
)
from app.modules.research.providers.base import ResearchProviderError
from app.modules.research.providers.jina import JinaReader
from app.modules.research.spike import ResearchSpikeService
from app.modules.research.utils import extract_second_hop_candidates


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {}, {"data": {}}, {"data": {"content": " "}},
    {"data": {"content": "ok", "url": "http://127.0.0.1/internal"}},
    {"data": {"content": "ok", "title": []}},
    {"data": {"content": "ok", "links": []}},
    {"data": {"content": "challenge", "httpStatus": 403}},
    {"data": {"content": "ok", "httpStatus": "200"}},
    {"code": 402, "data": {"content": "error body"}},
])
async def test_rejects_invalid_reader_payload(payload: object) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    )) as client:
        with pytest.raises(ResearchProviderError, match="invalid_reader_response"):
            await JinaReader(client).read("https://example.org", query="seed")


@pytest.mark.asyncio
async def test_rejects_plaintext_challenge() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text="<html>Access denied</html>")
    )) as client:
        with pytest.raises(ResearchProviderError, match="invalid_reader_response"):
            await JinaReader(client).read("https://example.org", query="seed")


@pytest.mark.asyncio
async def test_bounds_content_links_and_preserves_unknown_metadata() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": {
            "content": "abcdefghijk",
            "links": {
                "unsafe": "javascript:alert(1)",
                "private": "http://127.0.0.1",
                "a": "https://museum.example/a",
                "duplicate": "https://museum.example/a",
                "b": "https://museum.example/b",
            },
        }})
    )) as client:
        page = await JinaReader(client, max_content_chars=5, max_links=1,
                                raw_excerpt_chars=32).read("https://example.org", query="seed")
    assert page.document.content == "abcde"
    assert page.document.content_truncated and page.document.links_truncated
    assert page.document.final_url is None
    assert page.document.provider_timestamp is None
    assert page.document.title is None
    assert page.document.url == page.document.requested_url == "https://example.org"
    assert len(page.document.links) == 1
    assert len(page.call.raw_excerpt) <= 32


class OneSource:
    name = "serper"

    def estimated_calls(self, request: SearchRequest) -> int:
        return 1

    async def search(self, request: SearchRequest) -> ProviderResponse:
        return ProviderResponse((), (SourceCandidate(
            provider=self.name, query=request.query,
            url="https://example.org/article", title="Article",
        ),), ())


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["budget", "timeout", "malformed"])
async def test_read_failure_is_recorded_without_retry_or_document(failure: str) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("secret-should-not-leak", request=request)
        if failure == "budget":
            return httpx.Response(402, text="secret-should-not-leak")
        return httpx.Response(200, text="invalid JSON")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ResearchSpikeService(
            serper=OneSource(), reader=JinaReader(client, "secret-should-not-leak"),
            budget=ResearchBudget(max_provider_calls=2, max_pages_read=1, max_selected_urls=1),
        ).run("founder hypothesis")
    assert len(requests) == 1
    assert result.documents == []
    assert result.calls[-1].status == "error"
    assert "secret-should-not-leak" not in result.calls[-1].reason
    assert result.budget_usage is not None
    assert result.budget_usage.provider_calls_used == 2


def test_zero_second_hop_limit_and_duplicate_links() -> None:
    args = {"parent_url": "https://example.org", "query": "seed"}
    assert extract_second_hop_candidates("https://museum.example", limit=0, **args) == []
    candidates = extract_second_hop_candidates(
        "https://museum.example", linked_urls=["https://museum.example"], limit=2, **args
    )
    assert len(candidates) == 1
