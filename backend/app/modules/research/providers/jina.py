from urllib.parse import urljoin

import httpx

from app.modules.research.contracts import (
    PageDocument,
    PageLink,
    PageReadResponse,
    ProviderCallArtifact,
)
from app.modules.research.providers.base import ResearchProviderError
from app.modules.research.utils import as_dict, bounded_json_excerpt, validate_public_http_url


class JinaReader:
    name = "jina"
    _reader_base_url = "https://r.jina.ai/"

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str | None = None,
        *,
        max_content_chars: int = 100_000,
        raw_excerpt_chars: int = 8000,
        token_budget: int = 20_000,
        max_links: int = 100,
    ) -> None:
        if token_budget <= 0 or max_content_chars <= 0 or raw_excerpt_chars < 0 or max_links < 0:
            raise ValueError("invalid_reader_limits")
        self._client = client
        self._api_key = api_key
        self._max_content_chars = max_content_chars
        self._raw_excerpt_chars = raw_excerpt_chars
        self._token_budget = token_budget
        self._max_links = max_links

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        validated_url = validate_public_http_url(url)
        headers = {
            "Accept": "application/json",
            "X-With-Links-Summary": "true",
            "X-Base": "final",
            "X-Token-Budget": str(self._token_budget),
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = await self._client.get(
                f"{self._reader_base_url}{validated_url}",
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # No response body, credentials or automatic higher-budget retry in errors.
            reason = f"http_{exc.response.status_code}"
            raise ResearchProviderError(self.name, "read", reason) from exc
        except httpx.HTTPError as exc:
            raise ResearchProviderError(self.name, "read", type(exc).__name__) from exc

        try:
            payload = as_dict(response.json())
            data = as_dict(payload.get("data")) if payload else None
            if data is None or payload is None or payload.get("code", 200) != 200:
                raise ValueError("invalid_json_envelope")
            full_content = data.get("content")
            if not isinstance(full_content, str) or not full_content.strip():
                raise ValueError("missing_content")
            http_status = data.get("httpStatus")
            if (
                http_status is not None
                and (isinstance(http_status, bool) or not isinstance(http_status, int))
            ):
                raise ValueError("invalid_http_status")
            if isinstance(http_status, int) and http_status >= 400:
                raise ValueError("upstream_page_error")
            returned_url = data.get("url")
            if returned_url is not None and not isinstance(returned_url, str):
                raise ValueError("invalid_final_url")
            final_url = validate_public_http_url(returned_url) if returned_url else None
            effective_url = final_url or validated_url
            title = data.get("title")
            if title is not None and not isinstance(title, str):
                raise ValueError("invalid_title")
            timestamp = data.get("publishedTime", data.get("timestamp"))
            if isinstance(timestamp, bool) or not isinstance(timestamp, (str, int, float)):
                timestamp = None
            links, links_truncated = self._links(data.get("links"), effective_url)
        except ValueError as exc:
            raise ResearchProviderError(self.name, "read", "invalid_reader_response") from exc

        content = full_content[: self._max_content_chars]
        document = PageDocument(
            provider=self.name,
            url=effective_url,
            requested_url=validated_url,
            final_url=final_url,
            title=title,
            provider_timestamp=timestamp,
            content=content,
            links=links,
            content_truncated=len(content) < len(full_content),
            links_truncated=links_truncated,
        )
        call = ProviderCallArtifact(
            provider=self.name,
            operation="read",
            query=query,
            purpose="selected_url_read",
            status="ok",
            result_count=1,
            raw_excerpt=bounded_json_excerpt(payload, self._raw_excerpt_chars)[
                : self._raw_excerpt_chars
            ],
        )
        return PageReadResponse(document=document, call=call)

    def _links(self, value: object, base_url: str) -> tuple[tuple[PageLink, ...], bool]:
        """Jina JSON links are anchor-text → URL; missing summary is allowed."""
        if value is None:
            return (), False
        entries = as_dict(value)
        if entries is None:
            raise ValueError("invalid_links")
        links: list[PageLink] = []
        seen: set[str] = set()
        for label, raw_url in entries.items():
            if not isinstance(raw_url, str) or not raw_url.strip():
                continue
            try:
                url = validate_public_http_url(urljoin(base_url, raw_url))
            except ValueError:
                continue
            if url in seen:
                continue
            seen.add(url)
            if len(links) >= self._max_links:
                return tuple(links), True
            links.append(PageLink(url=url, text=label[:1000]))
        return tuple(links), False
