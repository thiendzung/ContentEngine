from typing import Protocol

from app.modules.research.contracts import PageReadResponse, ProviderResponse, SearchRequest


class ResearchProviderError(RuntimeError):
    def __init__(self, provider: str, operation: str, message: str) -> None:
        super().__init__(message)
        self.provider = provider
        self.operation = operation


class SearchProvider(Protocol):
    name: str

    def estimated_calls(self, request: SearchRequest) -> int: ...

    async def search(self, request: SearchRequest) -> ProviderResponse: ...


class PageReader(Protocol):
    name: str

    async def read(self, url: str, *, query: str) -> PageReadResponse: ...
