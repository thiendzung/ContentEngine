from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.research.production as production_module
from app.modules.harness.policy import BudgetLimits
from app.modules.knowledge.retrieval import RetrievalHit
from app.modules.research.contracts import (
    CommercialBias,
    PageDocument,
    PageReadResponse,
    ProductionResearchRequest,
    ProviderCallArtifact,
    ProviderResponse,
    ResearchSignalKind,
    SearchRequest,
    SearchSignal,
    SourceCandidate,
)
from app.modules.research.production import ResearchRouter


class SufficientProvider:
    name = "serper"

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return 1

    async def search(self, request: SearchRequest) -> ProviderResponse:
        return ProviderResponse(
            signals=tuple(
                SearchSignal(
                    provider=self.name,
                    query=request.query,
                    kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                    text=f"question-{index}",
                )
                for index in range(3)
            ),
            sources=tuple(
                SourceCandidate(
                    provider=self.name,
                    query=request.query,
                    url=f"https://example.test/source-{index}",
                    title=f"source-{index}",
                    commercial_bias=(
                        CommercialBias.LOW if index == 0 else CommercialBias.UNKNOWN
                    ),
                )
                for index in range(3)
            ),
            calls=(),
        )


class CountingReader:
    name = "jina"

    def __init__(self) -> None:
        self.calls = 0

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        self.calls += 1
        return PageReadResponse(
            document=PageDocument(provider=self.name, url=url, content="page"),
            call=ProviderCallArtifact(
                provider=self.name,
                operation="read",
                query=query,
                purpose="selected_url_read",
                status="ok",
                result_count=1,
                raw_excerpt="{}",
            ),
        )


async def _empty_retrieval(*args: object, **kwargs: object) -> tuple[RetrievalHit, ...]:
    del args, kwargs
    return ()


@pytest.mark.asyncio
async def test_budget_exhausted_before_jina_is_visible_stop_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    reader = CountingReader()
    router = ResearchRouter(
        serper=SufficientProvider(),
        reader=reader,
        budget_limits=BudgetLimits(max_tool_calls=1),
    )

    result = await router.run(
        cast(AsyncSession, object()),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art price",
            max_pages_to_read=1,
        ),
    )

    assert result.sufficient is True
    assert reader.calls == 0
    assert result.stop_reason == "budget_exceeded_before_jina"
    assert result.decisions[-1].failure_class == "budget_exceeded"
