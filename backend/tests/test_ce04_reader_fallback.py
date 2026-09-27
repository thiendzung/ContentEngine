from uuid import uuid4

import pytest

import app.modules.research.production as production_module
from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
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
from app.modules.research.providers.base import ResearchProviderError


async def _empty_retrieval(*args: object, **kwargs: object) -> list[object]:
    del args, kwargs
    return []


class SufficientSearch:
    name = "serper"

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return 1

    async def search(self, request: SearchRequest) -> ProviderResponse:
        signals = tuple(
            SearchSignal(
                provider=self.name,
                query=request.query,
                kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                text=f"question-{index}",
            )
            for index in range(3)
        )
        sources = tuple(
            SourceCandidate(
                provider=self.name,
                query=request.query,
                url=f"https://authority{index}.gov/guide",
                title=f"Authority {index}",
                source_type="institutional",
                commercial_bias=CommercialBias.LOW,
                intended_use=IntendedUse.EVIDENCE_CANDIDATE,
                found_via="fixture",
            )
            for index in range(3)
        )
        return ProviderResponse(signals, sources, ())


class FailingReader:
    def __init__(self, failure_class: str, *, name: str = "jina") -> None:
        self.name = name
        self.failure_class = failure_class
        self.calls = 0

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        del url, query
        self.calls += 1
        raise ResearchProviderError(
            self.name,
            "read",
            "controlled_failure",
            failure_class=self.failure_class,
        )


class SuccessReader:
    def __init__(self, *, name: str = "direct_http") -> None:
        self.name = name
        self.calls = 0

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        self.calls += 1
        return PageReadResponse(
            document=PageDocument(
                provider=self.name,
                url=url,
                requested_url=url,
                content=(
                    "Original artwork buyers can inspect the exact work, artist information, "
                    "and supporting documentation before deciding."
                ),
            ),
            call=ProviderCallArtifact(
                provider=self.name,
                operation="read",
                query=query,
                purpose="selected_url_direct_read_fallback",
                status="ok",
                result_count=1,
                raw_excerpt="",
            ),
        )


@pytest.mark.asyncio
async def test_reader_fallback_runs_once_after_tool_invalid_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    primary = FailingReader("tool_invalid_response")
    fallback = SuccessReader()
    router = ResearchRouter(
        serper=SufficientSearch(),
        reader=primary,
        fallback_reader=fallback,
    )

    result = await router.run(
        None,  # type: ignore[arg-type]
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="how to buy original artwork",
            required_intended_use=IntendedUse.EVIDENCE_CANDIDATE,
            max_pages_to_read=1,
        ),
    )

    assert primary.calls == 1
    assert fallback.calls == 1
    assert len(result.documents) == 1
    assert result.documents[0].provider == "direct_http"
    assert any(
        decision.provider == "jina"
        and decision.status.value == "failed"
        and decision.failure_class == "tool_invalid_response"
        for decision in result.decisions
    )
    assert any(
        decision.provider == "direct_http"
        and decision.status.value == "called"
        for decision in result.decisions
    )


@pytest.mark.asyncio
async def test_reader_fallback_does_not_mask_provider_auth_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    primary = FailingReader("provider_auth")
    fallback = SuccessReader()
    router = ResearchRouter(
        serper=SufficientSearch(),
        reader=primary,
        fallback_reader=fallback,
    )

    result = await router.run(
        None,  # type: ignore[arg-type]
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="how to buy original artwork",
            required_intended_use=IntendedUse.EVIDENCE_CANDIDATE,
            max_pages_to_read=1,
        ),
    )

    assert primary.calls == 1
    assert fallback.calls == 0
    assert result.documents == []
    assert result.stop_reason == "reader_candidates_exhausted"
    assert any(
        decision.provider == "jina"
        and decision.status.value == "failed"
        and decision.failure_class == "provider_auth"
        for decision in result.decisions
    )


@pytest.mark.asyncio
async def test_reader_fallback_does_not_direct_fetch_discovery_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)

    class DiscoverySearch(SufficientSearch):
        async def search(self, request: SearchRequest) -> ProviderResponse:
            response = await super().search(request)
            discovery = tuple(
                SourceCandidate(
                    provider=source.provider,
                    query=source.query,
                    url=source.url,
                    title=source.title,
                    source_type="editorial",
                    commercial_bias=CommercialBias.MEDIUM,
                    intended_use=IntendedUse.DISCOVERY,
                    found_via=source.found_via,
                )
                for source in response.sources
            )
            return ProviderResponse(response.signals, discovery, response.calls)

    primary = FailingReader("tool_invalid_response")
    fallback = SuccessReader()
    router = ResearchRouter(
        serper=DiscoverySearch(),
        reader=primary,
        fallback_reader=fallback,
    )

    result = await router.run(
        None,  # type: ignore[arg-type]
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="how to buy original artwork",
            max_pages_to_read=1,
        ),
    )

    assert primary.calls == 3
    assert fallback.calls == 0
    assert result.documents == []


@pytest.mark.asyncio
async def test_reader_fallback_does_not_mask_provider_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    primary = FailingReader("provider_rate_limit")
    fallback = SuccessReader()
    router = ResearchRouter(
        serper=SufficientSearch(),
        reader=primary,
        fallback_reader=fallback,
    )

    result = await router.run(
        None,  # type: ignore[arg-type]
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="how to buy original artwork",
            required_intended_use=IntendedUse.EVIDENCE_CANDIDATE,
            max_pages_to_read=1,
        ),
    )

    assert primary.calls == 1
    assert fallback.calls == 0
    assert result.documents == []
    assert result.stop_reason == "reader_candidates_exhausted"
    assert any(
        decision.provider == "jina"
        and decision.status.value == "failed"
        and decision.failure_class == "provider_rate_limit"
        for decision in result.decisions
    )


@pytest.mark.asyncio
async def test_reader_chain_uses_terminal_reader_after_provider_native_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    primary = FailingReader("tool_invalid_response", name="jina")
    provider_native = FailingReader("provider_transient", name="exa_contents")
    terminal = SuccessReader(name="direct_http")
    router = ResearchRouter(
        serper=SufficientSearch(),
        reader=primary,
        fallback_reader=provider_native,
        terminal_reader=terminal,
    )

    result = await router.run(
        None,  # type: ignore[arg-type]
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="how to buy original artwork",
            required_intended_use=IntendedUse.EVIDENCE_CANDIDATE,
            max_pages_to_read=1,
        ),
    )

    assert primary.calls == 1
    assert provider_native.calls == 1
    assert terminal.calls == 1
    assert len(result.documents) == 1
    assert result.documents[0].provider == "direct_http"
    assert any(
        decision.provider == "exa_contents"
        and decision.status.value == "failed"
        and decision.failure_class == "provider_transient"
        for decision in result.decisions
    )


@pytest.mark.asyncio
async def test_reader_chain_does_not_hide_provider_native_auth_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    primary = FailingReader("tool_invalid_response", name="jina")
    provider_native = FailingReader("provider_auth", name="exa_contents")
    terminal = SuccessReader(name="direct_http")
    router = ResearchRouter(
        serper=SufficientSearch(),
        reader=primary,
        fallback_reader=provider_native,
        terminal_reader=terminal,
    )

    result = await router.run(
        None,  # type: ignore[arg-type]
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="how to buy original artwork",
            required_intended_use=IntendedUse.EVIDENCE_CANDIDATE,
            max_pages_to_read=1,
        ),
    )

    assert primary.calls == 1
    assert provider_native.calls == 1
    assert terminal.calls == 0
    assert result.documents == []


@pytest.mark.asyncio
async def test_required_intended_use_selects_only_evidence_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)

    class MixedSearch(SufficientSearch):
        async def search(self, request: SearchRequest) -> ProviderResponse:
            response = await super().search(request)
            sources = list(response.sources)
            sources[2] = SourceCandidate(
                provider=self.name,
                query=request.query,
                url="https://editorial.example/guide",
                title="Editorial guide",
                source_type="editorial",
                commercial_bias=CommercialBias.MEDIUM,
                intended_use=IntendedUse.DISCOVERY,
                found_via="fixture",
            )
            return ProviderResponse(response.signals, tuple(sources), response.calls)

    router = ResearchRouter(serper=MixedSearch())
    result = await router.run(
        None,  # type: ignore[arg-type]
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="how to buy original artwork",
            required_intended_use=IntendedUse.EVIDENCE_CANDIDATE,
            max_pages_to_read=0,
        ),
    )

    assert len(result.selected_sources) == 2
    assert all(
        source.intended_use is IntendedUse.EVIDENCE_CANDIDATE
        for source in result.selected_sources
    )
    assert all("editorial.example" not in source.url for source in result.selected_sources)
