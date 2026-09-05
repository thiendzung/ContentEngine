import httpx

from app.modules.research.contracts import PageDocument, PageReadResponse, ProviderCallArtifact
from app.modules.research.providers.base import ResearchProviderError
from app.modules.research.utils import validate_public_http_url


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
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._max_content_chars = max_content_chars
        self._raw_excerpt_chars = raw_excerpt_chars

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        validated_url = validate_public_http_url(url)
        headers = {"Accept": "text/plain"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = await self._client.get(
                f"{self._reader_base_url}{validated_url}",
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ResearchProviderError(self.name, "read", str(exc)) from exc

        content = response.text[: self._max_content_chars]
        document = PageDocument(provider=self.name, url=validated_url, content=content)
        call = ProviderCallArtifact(
            provider=self.name,
            operation="read",
            query=query,
            purpose="selected_url_read",
            status="ok",
            result_count=1,
            raw_excerpt=content[: self._raw_excerpt_chars],
        )
        return PageReadResponse(document=document, call=call)
