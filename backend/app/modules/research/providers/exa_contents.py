from __future__ import annotations

import httpx

from app.modules.research.contracts import (
    PageDocument,
    PageReadResponse,
    ProviderCallArtifact,
)
from app.modules.research.providers.base import ResearchProviderError
from app.modules.research.providers.http import post_json
from app.modules.research.utils import (
    dict_items,
    string_value,
    validate_public_http_url,
)


class ExaContentsReader:
    """Retrieve readable content for an already-selected public URL via Exa Contents."""

    name = "exa_contents"
    _contents_url = "https://api.exa.ai/contents"

    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient,
        *,
        max_content_chars: int = 100_000,
    ) -> None:
        if not api_key:
            raise ValueError("exa_api_key_required")
        if max_content_chars <= 0:
            raise ValueError("exa_contents_max_content_chars_invalid")
        self._api_key = api_key
        self._client = client
        self._max_content_chars = max_content_chars

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        requested_url = validate_public_http_url(url)
        body = await post_json(
            provider=self.name,
            operation="read",
            client=self._client,
            url=self._contents_url,
            headers={
                "x-api-key": self._api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            payload={
                "urls": [requested_url],
                "text": {"maxCharacters": self._max_content_chars},
            },
        )

        results = dict_items(body.get("results"))
        if not results:
            raise ResearchProviderError(
                self.name,
                "read",
                "contents_result_missing",
                failure_class="tool_invalid_response",
            )

        result = results[0]
        content = string_value(result.get("text")).strip()
        if not content:
            raise ResearchProviderError(
                self.name,
                "read",
                "contents_text_missing",
                failure_class="tool_invalid_response",
            )

        resolved_url = string_value(result.get("url")).strip() or requested_url
        try:
            resolved_url = validate_public_http_url(resolved_url)
        except ValueError as exc:
            raise ResearchProviderError(
                self.name,
                "read",
                "contents_url_invalid",
                failure_class="tool_invalid_response",
            ) from exc

        title = string_value(result.get("title")).strip() or None
        document = PageDocument(
            provider=self.name,
            url=resolved_url,
            requested_url=requested_url,
            final_url=resolved_url if resolved_url != requested_url else None,
            title=title,
            provider_timestamp=None,
            content=content[: self._max_content_chars],
            links=(),
            content_truncated=len(content) > self._max_content_chars,
            links_truncated=False,
        )
        call = ProviderCallArtifact(
            provider=self.name,
            operation="read",
            query=query,
            purpose="selected_url_exa_contents_fallback",
            status="ok",
            result_count=1,
            raw_excerpt="",
        )
        return PageReadResponse(document=document, call=call)
