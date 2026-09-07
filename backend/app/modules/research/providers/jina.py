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


def _read_failure_class(status_code: int) -> str:
    if status_code in {401, 403}:
        return "provider_auth"
    if status_code == 429:
        return "provider_rate_limit"
    if status_code >= 500:
        return "provider_transient"
    return "tool_invalid_response"


def _upstream_failure_class(status_code: int) -> str:
    if status_code >= 500:
        return "provider_transient"
    return "tool_invalid_response"


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
            status_code = exc.response.status_code
            raise ResearchProviderError(
                self.name,
                "read",
                f"http_{status_code}",
                failure_class=_read_failure_class(status_code),
            ) from exc
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

        try:
            decoded = response.json()
        except ValueError as exc:
            raise ResearchProviderError(
                self.name,
                "read",
                "invalid_reader_response:invalid_json",
                failure_class="tool_invalid_response",
            ) from exc

        payload = as_dict(decoded)
        if payload is None:
            raise ResearchProviderError(
                self.name,
                "read",
                "invalid_reader_response:invalid_envelope",
                failure_class="tool_invalid_response",
            )

        code = payload.get("code", 200)
        if isinstance(code, bool) or not isinstance(code, int):
            raise ResearchProviderError(
                self.name,
                "read",
                "invalid_reader_response:invalid_code",
                failure_class="tool_invalid_response",
            )
        if code != 200:
            raise ResearchProviderError(
                self.name,
                "read",
                f"reader_code_{code}",
                failure_class=_read_failure_class(code),
            )

        try:
            data = as_dict(payload.get("data"))
            if data is None:
                raise ValueError("missing_data")

            http_status = data.get("httpStatus")
            if (
                http_status is not None
                and (isinstance(http_status, bool) or not isinstance(http_status, int))
            ):
                raise ValueError("invalid_http_status")
            if isinstance(http_status, int) and http_status >= 400:
                raise ResearchProviderError(
                    self.name,
                    "read",
                    f"upstream_http_{http_status}",
                    failure_class=_upstream_failure_class(http_status),
                )

            full_content = data.get("content")
            if not isinstance(full_content, str) or not full_content.strip():
                raise ValueError("missing_content")

            returned_url = data.get("url")
            if returned_url is not None and not isinstance(returned_url, str):
                raise ValueError("invalid_final_url")
            try:
                final_url = validate_public_http_url(returned_url) if returned_url else None
            except ValueError as exc:
                raise ValueError("invalid_final_url") from exc
            effective_url = final_url or validated_url

            title = data.get("title")
            if title is not None and not isinstance(title, str):
                raise ValueError("invalid_title")
            timestamp = data.get("publishedTime", data.get("timestamp"))
            if isinstance(timestamp, bool) or not isinstance(timestamp, (str, int, float)):
                timestamp = None
            links, links_truncated = self._links(data.get("links"), effective_url)
        except ResearchProviderError:
            raise
        except ValueError as exc:
            raise ResearchProviderError(
                self.name,
                "read",
                f"invalid_reader_response:{exc}",
                failure_class="tool_invalid_response",
            ) from exc

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
