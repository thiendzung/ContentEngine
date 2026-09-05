import httpx

from app.modules.research.contracts import (
    ProviderCallArtifact,
    ProviderResponse,
    ResearchSignalKind,
    SearchRequest,
    SearchSignal,
    SourceCandidate,
)
from app.modules.research.providers.http import post_json
from app.modules.research.utils import (
    annotate_source,
    bounded_json_excerpt,
    dict_items,
    string_value,
)


class TavilyProvider:
    name = "tavily"
    _search_url = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient,
        *,
        raw_excerpt_chars: int = 8000,
    ) -> None:
        if not api_key:
            raise ValueError("tavily_api_key_required")
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
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            payload={
                "query": request.query,
                "search_depth": "basic",
                "max_results": request.limit,
                "include_answer": False,
                "include_raw_content": False,
            },
        )
        items = dict_items(body.get("results"))
        signals: list[SearchSignal] = []
        sources: list[SourceCandidate] = []
        for item in items:
            title = string_value(item.get("title"))
            url = string_value(item.get("url"))
            snippet = string_value(item.get("content"))
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
            sources.append(
                annotate_source(
                    provider=self.name,
                    query=request.query,
                    url=url,
                    title=title,
                    snippet=snippet,
                    found_via="tavily_source_discovery",
                )
            )
        call = ProviderCallArtifact(
            provider=self.name,
            operation="search",
            query=request.query,
            purpose="source_discovery",
            status="ok",
            result_count=len(items),
            raw_excerpt=bounded_json_excerpt(body, self._raw_excerpt_chars),
        )
        return ProviderResponse(tuple(signals), tuple(sources), (call,))
