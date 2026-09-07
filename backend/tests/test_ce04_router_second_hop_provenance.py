from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.research.production as production_module
from app.modules.knowledge.retrieval import RetrievalHit
from app.modules.research.contracts import (
    ProductionResearchRequest,
    ProviderResponse,
    ResearchDepth,
    SearchRequest,
)
from app.modules.research.production import ResearchRouter


class CapturingProvider:
    def __init__(self, name: str) -> None:
        self.name = name
        self.requests: list[SearchRequest] = []

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return 1

    async def search(self, request: SearchRequest) -> ProviderResponse:
        self.requests.append(request)
        return ProviderResponse((), (), ())


async def _empty_retrieval(*args: object, **kwargs: object) -> tuple[RetrievalHit, ...]:
    del args, kwargs
    return ()


def _session() -> AsyncSession:
    return cast(AsyncSession, object())


@pytest.mark.asyncio
async def test_deep_route_preserves_parent_url_for_exa_second_hop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = CapturingProvider("serper")
    exa = CapturingProvider("exa")
    router = ResearchRouter(serper=serper, exa=exa)
    parent_url = "https://summary.example/article"

    await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="find the original source behind this summary",
            depth=ResearchDepth.DEEP,
            max_pages_to_read=0,
            parent_url=parent_url,
        ),
    )

    assert len(serper.requests) == 1
    assert len(exa.requests) == 1
    assert exa.requests[0].parent_url == parent_url
