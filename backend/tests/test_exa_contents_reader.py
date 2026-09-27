import httpx
import pytest

from app.modules.research.providers.base import ResearchProviderError
from app.modules.research.providers.exa_contents import ExaContentsReader


@pytest.mark.asyncio
async def test_exa_contents_reader_returns_bounded_page_document() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.exa.ai/contents"
        assert request.headers["x-api-key"] == "secret"
        return httpx.Response(
            200,
            request=request,
            json={
                "results": [
                    {
                        "url": "https://museum.gov/guide",
                        "title": "Official artwork guide",
                        "text": (
                            "Buyers should inspect the exact artwork, artist information, "
                            "and available documentation before deciding."
                        ),
                    }
                ],
                "statuses": [
                    {
                        "id": "https://museum.gov/guide",
                        "status": "success",
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ExaContentsReader(
            "secret",
            client,
            max_content_chars=500,
        ).read(
            "https://museum.gov/guide",
            query="how to buy original artwork",
        )

    assert result.document.provider == "exa_contents"
    assert result.document.requested_url == "https://museum.gov/guide"
    assert result.document.url == "https://museum.gov/guide"
    assert result.document.title == "Official artwork guide"
    assert "inspect the exact artwork" in result.document.content
    assert result.call.provider == "exa_contents"
    assert result.call.purpose == "selected_url_exa_contents_fallback"
    assert result.call.raw_excerpt == ""


@pytest.mark.asyncio
async def test_exa_contents_reader_fails_closed_when_text_missing() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            json={
                "results": [
                    {
                        "url": "https://museum.gov/guide",
                        "title": "Official artwork guide",
                        "text": "",
                    }
                ]
            },
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await ExaContentsReader("secret", client).read(
                "https://museum.gov/guide",
                query="how to buy original artwork",
            )

    assert str(exc_info.value) == "contents_text_missing"
    assert exc_info.value.failure_class == "tool_invalid_response"


@pytest.mark.asyncio
async def test_exa_contents_reader_rejects_private_resolved_url() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            json={
                "results": [
                    {
                        "url": "http://127.0.0.1/private",
                        "title": "Unsafe redirect",
                        "text": "content",
                    }
                ]
            },
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await ExaContentsReader("secret", client).read(
                "https://museum.gov/guide",
                query="how to buy original artwork",
            )

    assert str(exc_info.value) == "contents_url_invalid"
    assert exc_info.value.failure_class == "tool_invalid_response"


@pytest.mark.asyncio
async def test_exa_contents_reader_preserves_provider_auth_failure() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            401,
            request=request,
            json={"error": "unauthorized"},
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await ExaContentsReader("secret", client).read(
                "https://museum.gov/guide",
                query="how to buy original artwork",
            )

    assert str(exc_info.value) == "http_401"
    assert exc_info.value.failure_class == "provider_auth"
