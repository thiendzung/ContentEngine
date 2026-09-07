from typing import Protocol

from app.modules.research.contracts import PageReadResponse, ProviderResponse, SearchRequest


class ResearchProviderError(RuntimeError):
    def __init__(
        self,
        provider: str,
        operation: str,
        message: str,
        *,
        failure_class: str = "provider_transient",
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.operation = operation
        self.failure_class = failure_class


class SearchProvider(Protocol):
    name: str

    def estimated_calls(self, request: SearchRequest) -> int: ...

    async def search(self, request: SearchRequest) -> ProviderResponse: ...


class PageReader(Protocol):
    name: str

    async def read(self, url: str, *, query: str) -> PageReadResponse: ...
