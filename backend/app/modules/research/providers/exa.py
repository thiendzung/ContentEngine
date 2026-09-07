from dataclasses import replace

import httpx

from app.modules.research.contracts import (
    ProviderCallArtifact,
    ProviderResponse,
    ResearchSignalKind,
    SearchRequest,
    SearchSignal,
    SourceCandidate,
    SourceRelation,
)
from app.modules.research.providers.http import post_json
from app.modules.research.utils import (
    annotate_source,
    bounded_json_excerpt,
    dict_items,
    string_value,
)


class ExaProvider:
    name = "exa"
    _search_url = "https://api.exa.ai/search"

    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient,
        *,
        raw_excerpt_chars: int = 8000,
    ) -> None:
        if not api_key:
            raise ValueError("exa_api_key_required")
        self._api_key = api_key
        self._client = client
        self._raw_excerpt_chars = raw_excerpt_chars

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return 1

    async def search(self, request: SearchRequest) -> ProviderResponse:
        body = await post_json(
            provider=self.name,
            operation="search",
            client=self._client,
            url=self._search_url,
            headers={"x-api-key": self._api_key, "Content-Type": "application/json"},
            payload={"query": request.query, "numResults": request.limit, "type": "auto"},
        )
        items = dict_items(body.get("results"))
        signals: list[SearchSignal] = []
        sources: list[SourceCandidate] = []
        second_hop = request.parent_url is not None
        for item in items:
            title = string_value(item.get("title"))
            url = string_value(item.get("url"))
            snippet = string_value(item.get("text"))
            if not url:
                continue
            signals.append(
                SearchSignal(
                    provider=self.name,
                    query=request.query,
                    kind=ResearchSignalKind.SOURCE_DISCOVERY,
                    text=title or url,
                    title=title or None,
                    url=url,
                    snippet=snippet or None,
                )
            )
            source = annotate_source(
                provider=self.name,
                query=request.query,
                url=url,
                title=title,
                snippet=snippet,
                found_via=(
                    "exa_second_hop" if second_hop else "exa_semantic_discovery"
                ),
            )
            if second_hop:
                source = replace(
                    source,
                    relation=SourceRelation.SECOND_HOP,
                    parent_url=request.parent_url,
                )
            sources.append(source)
        call = ProviderCallArtifact(
            provider=self.name,
            operation="search",
            query=request.query,
            purpose=(
                "second_hop_source_discovery"
                if second_hop
                else "semantic_or_second_hop_discovery"
            ),
            status="ok",
            result_count=len(items),
            raw_excerpt=bounded_json_excerpt(body, self._raw_excerpt_chars),
        )
        return ProviderResponse(tuple(signals), tuple(sources), (call,))
