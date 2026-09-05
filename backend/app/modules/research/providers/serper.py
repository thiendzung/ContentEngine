import httpx

from app.modules.research.contracts import (
    ProviderCallArtifact,
    ProviderResponse,
    ResearchSignalKind,
    SearchRequest,
    SearchSignal,
    SourceCandidate,
)
from app.modules.research.providers.base import ResearchProviderError
from app.modules.research.providers.http import post_json
from app.modules.research.utils import (
    annotate_source,
    bounded_json_excerpt,
    dict_items,
    int_value,
    string_value,
    suggestion_values,
)


class SerperProvider:
    name = "serper"
    _search_url = "https://google.serper.dev/search"
    _autocomplete_url = "https://google.serper.dev/autocomplete"

    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient,
        *,
        raw_excerpt_chars: int = 8000,
    ) -> None:
        if not api_key:
            raise ValueError("serper_api_key_required")
        self._api_key = api_key
        self._client = client
        self._raw_excerpt_chars = raw_excerpt_chars

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return 2

    async def search(self, request: SearchRequest) -> ProviderResponse:
        headers = {"X-API-KEY": self._api_key, "Content-Type": "application/json"}
        search_payload: dict[str, object] = {
            "q": request.query,
            "gl": request.country,
            "hl": request.locale,
            "num": request.limit,
        }
        search_body = await post_json(
            provider=self.name,
            operation="search",
            client=self._client,
            url=self._search_url,
            headers=headers,
            payload=search_payload,
        )
        autocomplete_error = ""
        try:
            autocomplete_body = await post_json(
                provider=self.name,
                operation="autocomplete",
                client=self._client,
                url=self._autocomplete_url,
                headers=headers,
                payload={"q": request.query, "gl": request.country, "hl": request.locale},
            )
        except ResearchProviderError as exc:
            autocomplete_body = {}
            autocomplete_error = str(exc)

        signals: list[SearchSignal] = []
        sources: list[SourceCandidate] = []

        for item in dict_items(search_body.get("peopleAlsoAsk")):
            question = string_value(item.get("question"))
            if question:
                signals.append(
                    SearchSignal(
                        provider=self.name,
                        query=request.query,
                        kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                        text=question,
                        url=string_value(item.get("link")) or None,
                        snippet=string_value(item.get("snippet")) or None,
                    )
                )

        for item in dict_items(search_body.get("relatedSearches")):
            related = string_value(item.get("query"))
            if related:
                signals.append(
                    SearchSignal(
                        provider=self.name,
                        query=request.query,
                        kind=ResearchSignalKind.RELATED_SEARCH,
                        text=related,
                    )
                )

        organic_items = dict_items(search_body.get("organic"))
        for item in organic_items:
            title = string_value(item.get("title"))
            link = string_value(item.get("link"))
            snippet = string_value(item.get("snippet"))
            position = int_value(item.get("position"))
            if title or link:
                signals.append(
                    SearchSignal(
                        provider=self.name,
                        query=request.query,
                        kind=ResearchSignalKind.ORGANIC,
                        text=title or link,
                        title=title or None,
                        url=link or None,
                        snippet=snippet or None,
                        position=position,
                    )
                )
            if link:
                sources.append(
                    annotate_source(
                        provider=self.name,
                        query=request.query,
                        url=link,
                        title=title,
                        snippet=snippet,
                        found_via="google_organic",
                    )
                )

        autocomplete_suggestions = suggestion_values(autocomplete_body.get("suggestions"))
        for suggestion in autocomplete_suggestions:
            signals.append(
                SearchSignal(
                    provider=self.name,
                    query=request.query,
                    kind=ResearchSignalKind.AUTOCOMPLETE,
                    text=suggestion,
                )
            )

        calls = (
            ProviderCallArtifact(
                provider=self.name,
                operation="search",
                query=request.query,
                purpose="discovery",
                status="ok",
                result_count=len(organic_items),
                raw_excerpt=bounded_json_excerpt(search_body, self._raw_excerpt_chars),
            ),
            ProviderCallArtifact(
                provider=self.name,
                operation="autocomplete",
                query=request.query,
                purpose="discovery",
                status="error" if autocomplete_error else "ok",
                result_count=len(autocomplete_suggestions),
                raw_excerpt=bounded_json_excerpt(autocomplete_body, self._raw_excerpt_chars),
                reason=autocomplete_error,
            ),
        )
        return ProviderResponse(tuple(signals), tuple(sources), calls)
