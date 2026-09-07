import httpx
import pytest

from app.modules.research.providers.base import ResearchProviderError
from app.modules.research.providers.http import post_json
from app.modules.research.providers.jina import JinaReader


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "failure_class"),
    [
        (401, "provider_auth"),
        (403, "provider_auth"),
        (429, "provider_rate_limit"),
        (503, "provider_transient"),
        (400, "tool_invalid_response"),
    ],
)
async def test_post_json_classifies_http_failures(
    status_code: int,
    failure_class: str,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code, request=request, text="hidden-provider-body")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await post_json(
                provider="provider",
                operation="search",
                client=client,
                url="https://provider.test/search",
                headers={"Authorization": "Bearer secret-should-not-leak"},
                payload={"query": "test"},
            )

    error = exc_info.value
    assert error.failure_class == failure_class
    assert str(error) == f"http_{status_code}"
    assert "hidden-provider-body" not in str(error)
    assert "secret-should-not-leak" not in str(error)


@pytest.mark.asyncio
async def test_post_json_invalid_payload_is_tool_invalid_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, request=request, text="not-json")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await post_json(
                provider="provider",
                operation="search",
                client=client,
                url="https://provider.test/search",
                headers={},
                payload={"query": "test"},
            )

    assert exc_info.value.failure_class == "tool_invalid_response"
    assert str(exc_info.value) == "invalid_json_response"


@pytest.mark.asyncio
async def test_jina_rate_limit_uses_canonical_failure_class() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(429, request=request, text="do-not-log-this")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await JinaReader(client, api_key="secret-should-not-leak").read(
                "https://example.org/page",
                query="test",
            )

    error = exc_info.value
    assert error.failure_class == "provider_rate_limit"
    assert str(error) == "http_429"
    assert "secret-should-not-leak" not in str(error)
    assert "do-not-log-this" not in str(error)


@pytest.mark.asyncio
async def test_jina_invalid_envelope_exposes_safe_parse_reason() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            json={"code": 200, "data": {"content": ""}},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await JinaReader(client).read("https://example.org/page", query="test")

    assert exc_info.value.failure_class == "tool_invalid_response"
    assert str(exc_info.value) == "invalid_reader_response:missing_content"


@pytest.mark.asyncio
async def test_jina_structured_503_envelope_is_provider_transient() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            json={
                "code": 503,
                "status": 50002,
                "data": None,
                "message": "provider detail must not be copied",
            },
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await JinaReader(client).read("https://example.org/page", query="test")

    error = exc_info.value
    assert error.failure_class == "provider_transient"
    assert str(error) == "reader_code_503"
    assert "provider detail must not be copied" not in str(error)


@pytest.mark.asyncio
async def test_jina_upstream_403_is_page_specific_not_provider_auth() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            json={
                "code": 200,
                "data": {
                    "httpStatus": 403,
                    "content": "",
                },
            },
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await JinaReader(client).read("https://example.org/page", query="test")

    error = exc_info.value
    assert error.failure_class == "tool_invalid_response"
    assert str(error) == "upstream_http_403"
