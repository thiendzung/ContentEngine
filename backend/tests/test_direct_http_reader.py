import httpx
import pytest

import app.modules.research.providers.direct_http as direct_http_module
from app.modules.research.providers.base import ResearchProviderError
from app.modules.research.providers.direct_http import DirectHttpReader


@pytest.mark.asyncio
async def test_direct_http_reader_reads_bounded_public_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.org/guide"
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "text/html; charset=utf-8"},
            text=(
                "<html><head><title>Artwork Guide</title>"
                "<script>secret chrome</script></head><body>"
                "<main><h1>Buying original artwork</h1>"
                "<p>Ask what the work is, who made it, and what documentation exists.</p>"
                '<a href="/evidence">Evidence</a></main></body></html>'
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await DirectHttpReader(client, max_links=5).read(
            "https://example.org/guide",
            query="original artwork",
        )

    assert result.document.provider == "direct_http"
    assert result.document.requested_url == "https://example.org/guide"
    assert result.document.url == "https://example.org/guide"
    assert result.document.title == "Artwork Guide"
    assert "Buying original artwork" in result.document.content
    assert "Ask what the work is" in result.document.content
    assert "secret chrome" not in result.document.content
    assert [link.url for link in result.document.links] == [
        "https://example.org/evidence"
    ]
    assert result.call.provider == "direct_http"
    assert result.call.purpose == "selected_url_direct_read_fallback"
    assert result.call.raw_excerpt == ""


@pytest.mark.asyncio
async def test_direct_http_reader_rejects_private_redirect_target() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            request=request,
            headers={"location": "http://127.0.0.1/private"},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await DirectHttpReader(client).read(
                "https://example.org/guide",
                query="original artwork",
            )

    assert str(exc_info.value) == "unsafe_redirect_target"
    assert exc_info.value.failure_class == "tool_invalid_response"


@pytest.mark.asyncio
async def test_direct_http_reader_reads_bounded_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class FakeMetadata:
        title = "Official Art Guidance"

    class FakePdf:
        is_encrypted = False
        metadata = FakeMetadata()
        pages = [
            FakePage("Page one: original artwork guidance."),
            FakePage("Page two: documentation and ownership."),
            FakePage("Page three should be outside the page limit."),
        ]

    monkeypatch.setattr(
        direct_http_module,
        "PdfReader",
        lambda *args, **kwargs: FakePdf(),
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/pdf"},
            content=b"%PDF-1.7 fixture",
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await DirectHttpReader(client, max_pdf_pages=2).read(
            "https://example.org/guide.pdf",
            query="original artwork",
        )

    assert result.document.provider == "direct_http"
    assert result.document.title == "Official Art Guidance"
    assert "Page one: original artwork guidance." in result.document.content
    assert "Page two: documentation and ownership." in result.document.content
    assert "Page three should be outside the page limit." not in result.document.content
    assert result.document.content_truncated is True
    assert result.document.links == ()


@pytest.mark.asyncio
async def test_direct_http_reader_bounds_response_bytes() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            headers={"content-type": "text/plain"},
            content=b"x" * 64,
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await DirectHttpReader(client, max_response_bytes=32).read(
                "https://example.org/guide",
                query="original artwork",
            )

    assert str(exc_info.value) == "response_too_large"
    assert exc_info.value.failure_class == "tool_invalid_response"


@pytest.mark.asyncio
async def test_direct_http_reader_classifies_public_403_as_page_failure() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            403,
            request=request,
            text="do-not-copy-page-body",
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ResearchProviderError) as exc_info:
            await DirectHttpReader(client).read(
                "https://example.org/guide",
                query="original artwork",
            )

    assert str(exc_info.value) == "http_403"
    assert exc_info.value.failure_class == "tool_invalid_response"
    assert "do-not-copy-page-body" not in str(exc_info.value)
