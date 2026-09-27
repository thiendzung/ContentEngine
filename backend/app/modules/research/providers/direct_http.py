from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urljoin

import httpx
from pypdf import PdfReader

from app.modules.research.contracts import (
    PageDocument,
    PageLink,
    PageReadResponse,
    ProviderCallArtifact,
)
from app.modules.research.providers.base import ResearchProviderError
from app.modules.research.utils import validate_public_http_url


def _status_failure_class(status_code: int) -> str:
    if status_code == 429:
        return "provider_rate_limit"
    if status_code >= 500:
        return "provider_transient"
    return "tool_invalid_response"


class _HtmlExtractor(HTMLParser):
    _BLOCK_TAGS = {
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "svg", "template"}

    def __init__(self, *, base_url: str, max_links: int) -> None:
        super().__init__(convert_charrefs=True)
        self._base_url = base_url
        self._max_links = max_links
        self._parts: list[str] = []
        self._title_parts: list[str] = []
        self._links: list[PageLink] = []
        self._seen_links: set[str] = set()
        self._skip_stack: list[str] = []
        self._in_title = False
        self.links_truncated = False

    @property
    def content(self) -> str:
        lines: list[str] = []
        for raw in "".join(self._parts).splitlines():
            line = " ".join(raw.split())
            if line and (not lines or lines[-1] != line):
                lines.append(line)
        return "\n".join(lines)

    @property
    def title(self) -> str | None:
        title = " ".join(" ".join(self._title_parts).split())
        return title or None

    @property
    def links(self) -> tuple[PageLink, ...]:
        return tuple(self._links)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        if normalized in self._SKIP_TAGS:
            self._skip_stack.append(normalized)
            return
        if self._skip_stack:
            return
        if normalized == "title":
            self._in_title = True
        if normalized in self._BLOCK_TAGS:
            self._parts.append("\n")
        if normalized != "a":
            return
        href = next((value for key, value in attrs if key.casefold() == "href"), None)
        if not href or self.links_truncated:
            return
        try:
            resolved = validate_public_http_url(urljoin(self._base_url, href))
        except ValueError:
            return
        if resolved in self._seen_links:
            return
        if len(self._links) >= self._max_links:
            self.links_truncated = True
            return
        self._seen_links.add(resolved)
        self._links.append(PageLink(url=resolved))

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if self._skip_stack:
            if normalized == self._skip_stack[-1]:
                self._skip_stack.pop()
            return
        if normalized == "title":
            self._in_title = False
        if normalized in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_stack:
            return
        if self._in_title:
            self._title_parts.append(data)
        self._parts.append(data)


class DirectHttpReader:
    """Bounded public HTTP fallback for readable HTML, plain text and PDFs.

    The reader validates every redirect target, refuses private/local addresses, bounds
    response bytes/text/pages, and fails closed on unsupported or unreadable formats.
    """

    name = "direct_http"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        max_response_bytes: int = 2_000_000,
        max_content_chars: int = 100_000,
        max_links: int = 100,
        max_redirects: int = 5,
        max_pdf_pages: int = 50,
    ) -> None:
        if (
            max_response_bytes <= 0
            or max_content_chars <= 0
            or max_links < 0
            or max_redirects < 0
            or max_pdf_pages <= 0
        ):
            raise ValueError("invalid_direct_reader_limits")
        self._client = client
        self._max_response_bytes = max_response_bytes
        self._max_content_chars = max_content_chars
        self._max_links = max_links
        self._max_redirects = max_redirects
        self._max_pdf_pages = max_pdf_pages

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        requested_url = validate_public_http_url(url)
        current_url = requested_url
        redirects = 0

        while True:
            try:
                async with self._client.stream(
                    "GET",
                    current_url,
                    headers={
                        "Accept": (
                            "text/html,application/xhtml+xml,application/pdf,"
                            "text/plain;q=0.9,*/*;q=0.1"
                        ),
                        "User-Agent": "ContentEngine/1.0 (+bounded evidence reader)",
                    },
                    follow_redirects=False,
                ) as response:
                    status_code = response.status_code
                    if 300 <= status_code < 400:
                        location = response.headers.get("location")
                        if not location:
                            raise ResearchProviderError(
                                self.name,
                                "read",
                                "redirect_location_missing",
                                failure_class="tool_invalid_response",
                            )
                        if redirects >= self._max_redirects:
                            raise ResearchProviderError(
                                self.name,
                                "read",
                                "redirect_limit_exceeded",
                                failure_class="tool_invalid_response",
                            )
                        try:
                            current_url = validate_public_http_url(
                                urljoin(current_url, location)
                            )
                        except ValueError as exc:
                            raise ResearchProviderError(
                                self.name,
                                "read",
                                "unsafe_redirect_target",
                                failure_class="tool_invalid_response",
                            ) from exc
                        redirects += 1
                        continue

                    if status_code >= 400:
                        raise ResearchProviderError(
                            self.name,
                            "read",
                            f"http_{status_code}",
                            failure_class=_status_failure_class(status_code),
                        )

                    content_type = (
                        response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .casefold()
                    )
                    if content_type not in {
                        "",
                        "text/html",
                        "application/xhtml+xml",
                        "application/pdf",
                        "text/plain",
                    }:
                        raise ResearchProviderError(
                            self.name,
                            "read",
                            f"unsupported_content_type:{content_type or 'unknown'}",
                            failure_class="tool_invalid_response",
                        )

                    declared_length = response.headers.get("content-length")
                    if declared_length is not None:
                        try:
                            if int(declared_length) > self._max_response_bytes:
                                raise ResearchProviderError(
                                    self.name,
                                    "read",
                                    "response_too_large",
                                    failure_class="tool_invalid_response",
                                )
                        except ValueError:
                            pass

                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self._max_response_bytes:
                            raise ResearchProviderError(
                                self.name,
                                "read",
                                "response_too_large",
                                failure_class="tool_invalid_response",
                            )
                    if not content_type:
                        prefix = bytes(body).lstrip()[:32].lower()
                        if prefix.startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
                            content_type = "text/html"
                        elif prefix.startswith(b"%pdf-"):
                            content_type = "application/pdf"
                        else:
                            raise ResearchProviderError(
                                self.name,
                                "read",
                                "unsupported_content_type:unknown",
                                failure_class="tool_invalid_response",
                            )
                    encoding = response.encoding or "utf-8"
                    last_modified = response.headers.get("last-modified")
            except ResearchProviderError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise ResearchProviderError(
                    self.name,
                    "read",
                    type(exc).__name__,
                    failure_class="provider_transient",
                ) from exc
            except httpx.HTTPError as exc:
                raise ResearchProviderError(
                    self.name,
                    "read",
                    type(exc).__name__,
                    failure_class="provider_transient",
                ) from exc
            break

        pdf_truncated = False
        if content_type == "application/pdf":
            full_content, title, pdf_truncated = self._extract_pdf(bytes(body))
            links: tuple[PageLink, ...] = ()
            links_truncated = False
        else:
            try:
                decoded = bytes(body).decode(encoding, errors="replace")
            except LookupError:
                decoded = bytes(body).decode("utf-8", errors="replace")

            if content_type == "text/plain":
                full_content = decoded.strip()
                title = None
                links = ()
                links_truncated = False
            else:
                parser = _HtmlExtractor(base_url=current_url, max_links=self._max_links)
                try:
                    parser.feed(decoded)
                    parser.close()
                except Exception as exc:
                    raise ResearchProviderError(
                        self.name,
                        "read",
                        "html_parse_failed",
                        failure_class="tool_invalid_response",
                    ) from exc
                full_content = parser.content.strip()
                title = parser.title
                links = parser.links
                links_truncated = parser.links_truncated

        if not full_content:
            raise ResearchProviderError(
                self.name,
                "read",
                "empty_readable_content",
                failure_class="tool_invalid_response",
            )

        content = full_content[: self._max_content_chars]
        document = PageDocument(
            provider=self.name,
            url=current_url,
            requested_url=requested_url,
            final_url=current_url if current_url != requested_url else None,
            title=title,
            provider_timestamp=last_modified,
            content=content,
            links=links,
            content_truncated=pdf_truncated or len(content) < len(full_content),
            links_truncated=links_truncated,
        )
        call = ProviderCallArtifact(
            provider=self.name,
            operation="read",
            query=query,
            purpose="selected_url_direct_read_fallback",
            status="ok",
            result_count=1,
            raw_excerpt="",
        )
        return PageReadResponse(document=document, call=call)

    def _extract_pdf(self, payload: bytes) -> tuple[str, str | None, bool]:
        try:
            reader = PdfReader(BytesIO(payload), strict=False)
            if reader.is_encrypted:
                raise ResearchProviderError(
                    self.name,
                    "read",
                    "pdf_encrypted",
                    failure_class="tool_invalid_response",
                )
            total_pages = len(reader.pages)
            page_limit = min(total_pages, self._max_pdf_pages)
            chunks: list[str] = []
            char_count = 0
            for index in range(page_limit):
                text = reader.pages[index].extract_text() or ""
                normalized_lines = (
                    " ".join(raw.split()) for raw in text.splitlines()
                )
                normalized = "\n".join(line for line in normalized_lines if line)
                if not normalized:
                    continue
                chunks.append(normalized)
                char_count += len(normalized) + 2
                if char_count >= self._max_content_chars:
                    break
            full_content = "\n\n".join(chunks).strip()
            metadata = reader.metadata
            title: str | None = None
            if metadata is not None and isinstance(metadata.title, str):
                title = metadata.title.strip() or None
            truncated = total_pages > page_limit or char_count >= self._max_content_chars
            return full_content, title, truncated
        except ResearchProviderError:
            raise
        except Exception as exc:
            raise ResearchProviderError(
                self.name,
                "read",
                "pdf_parse_failed",
                failure_class="tool_invalid_response",
            ) from exc

