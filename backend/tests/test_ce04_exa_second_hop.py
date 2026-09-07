import httpx
import pytest

from app.modules.research.contracts import SearchRequest, SourceRelation
from app.modules.research.providers.exa import ExaProvider


@pytest.mark.asyncio
async def test_exa_preserves_second_hop_parent_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "results": [
                    {
                        "title": "Original museum source",
                        "url": "https://museum.example/source",
                        "text": "Primary source candidate",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        response = await ExaProvider("exa-key", client).search(
            SearchRequest(
                query="original source for artwork pricing",
                parent_url="https://summary.example/article",
            )
        )

    assert len(response.sources) == 1
    source = response.sources[0]
    assert source.relation is SourceRelation.SECOND_HOP
    assert source.parent_url == "https://summary.example/article"
    assert source.found_via == "exa_second_hop"
    assert response.calls[0].purpose == "second_hop_source_discovery"


@pytest.mark.asyncio
async def test_exa_without_parent_remains_direct_semantic_discovery() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            json={
                "results": [
                    {
                        "title": "Related source",
                        "url": "https://example.org/related",
                        "text": "Related content",
                    }
                ]
            },
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        response = await ExaProvider("exa-key", client).search(
            SearchRequest(query="artwork pricing")
        )

    source = response.sources[0]
    assert source.relation is SourceRelation.DIRECT
    assert source.parent_url is None
    assert source.found_via == "exa_semantic_discovery"
