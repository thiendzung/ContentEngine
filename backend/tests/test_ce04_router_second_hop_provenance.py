from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.research.production as production_module
from app.modules.knowledge.retrieval import RetrievalHit
from app.modules.research.contracts import (
    CommercialBias,
    PageDocument,
    PageReadResponse,
    ProductionResearchRequest,
    ProviderCallArtifact,
    ProviderResponse,
    ResearchDepth,
    ResearchSignalKind,
    SearchRequest,
    SearchSignal,
    SourceCandidate,
    SourceRelation,
)
from app.modules.research.production import ProductionSufficiencyPolicy, ResearchRouter
from app.modules.research.utils import dedupe_sources


class CapturingProvider:
    def __init__(
        self,
        name: str,
        *,
        second_hop: bool = False,
        generic_sufficient: bool = True,
    ) -> None:
        self.name = name
        self.second_hop = second_hop
        self.generic_sufficient = generic_sufficient
        self.requests: list[SearchRequest] = []

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return 1

    async def search(self, request: SearchRequest) -> ProviderResponse:
        self.requests.append(request)
        if self.second_hop:
            return ProviderResponse(
                (),
                (
                    SourceCandidate(
                        provider=self.name,
                        query=request.query,
                        url="https://museum.example/original",
                        title="Original source",
                        source_type="institutional",
                        commercial_bias=CommercialBias.LOW,
                        found_via="exa_second_hop",
                        relation=SourceRelation.SECOND_HOP,
                        parent_url=request.parent_url,
                    ),
                ),
                (),
            )
        if not self.generic_sufficient:
            return ProviderResponse((), (), ())
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
                url=f"https://search.example/source-{index}",
                title=f"Search source {index}",
                source_type="institutional" if index == 0 else "editorial_or_unknown",
                commercial_bias=(
                    CommercialBias.LOW if index == 0 else CommercialBias.UNKNOWN
                ),
            )
            for index in range(3)
        )
        return ProviderResponse(signals, sources, ())


class CapturingReader:
    name = "jina"

    def __init__(self) -> None:
        self.urls: list[str] = []

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        self.urls.append(url)
        return PageReadResponse(
            document=PageDocument(provider=self.name, url=url, content="clean page"),
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


def _internal_hit() -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid4(),
        source_document_id=uuid4(),
        source_id=uuid4(),
        document_version=1,
        text="exact internal context",
        source_type="motgu",
        authority_hint="canonical",
        commercial_bias="low",
        matched_terms=("exact",),
        matched_entity_ids=(),
        exact_phrase=True,
        ranking_reasons=("ranking_policy:ce04-v1",),
    )


def _session() -> AsyncSession:
    return cast(AsyncSession, object())


@pytest.mark.asyncio
async def test_second_hop_forces_exa_even_when_serper_is_generically_sufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = CapturingProvider("serper")
    exa = CapturingProvider("exa", second_hop=True)
    router = ResearchRouter(serper=serper, exa=exa)
    parent_url = "https://summary.example/article"

    result = await router.run(
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
    assert result.stop_reason == "exa_sufficient"
    assert result.sufficient is True
    second_hop = next(
        source
        for source in result.source_candidates
        if source.relation is SourceRelation.SECOND_HOP
    )
    assert second_hop.parent_url == parent_url


@pytest.mark.asyncio
async def test_one_second_hop_candidate_can_satisfy_source_chase_without_paa_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = CapturingProvider("serper", generic_sufficient=False)
    exa = CapturingProvider("exa", second_hop=True)
    router = ResearchRouter(serper=serper, exa=exa)

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="original source",
            max_pages_to_read=0,
            parent_url="https://summary.example/article",
        ),
    )

    assert result.sufficient is True
    assert result.stop_reason == "exa_sufficient"


@pytest.mark.asyncio
async def test_internal_knowledge_does_not_short_circuit_explicit_second_hop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def retrieve(*args: object, **kwargs: object) -> tuple[RetrievalHit, ...]:
        del args, kwargs
        return (_internal_hit(),)

    monkeypatch.setattr(production_module, "retrieve_chunks", retrieve)
    serper = CapturingProvider("serper")
    exa = CapturingProvider("exa", second_hop=True)
    router = ResearchRouter(
        serper=serper,
        exa=exa,
        sufficiency=ProductionSufficiencyPolicy(min_internal_hits=1),
    )

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="original source",
            max_pages_to_read=0,
            parent_url="https://summary.example/article",
        ),
    )

    assert len(result.internal_hits) == 1
    assert len(serper.requests) == 1
    assert len(exa.requests) == 1
    assert result.sufficient is True
    assert result.decisions[0].reason == (
        "internal_context_available_but_second_hop_requires_external"
    )


@pytest.mark.asyncio
async def test_jina_reads_second_hop_source_before_generic_serper_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = CapturingProvider("serper")
    exa = CapturingProvider("exa", second_hop=True)
    reader = CapturingReader()
    router = ResearchRouter(serper=serper, exa=exa, reader=reader)

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="original source",
            max_pages_to_read=1,
            parent_url="https://summary.example/article",
        ),
    )

    assert result.selected_sources[0].relation is SourceRelation.SECOND_HOP
    assert reader.urls == ["https://museum.example/original"]


@pytest.mark.asyncio
async def test_second_hop_does_not_fake_success_without_exa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    serper = CapturingProvider("serper")
    tavily = CapturingProvider("tavily")
    router = ResearchRouter(serper=serper, tavily=tavily)

    result = await router.run(
        _session(),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="find the original source behind this summary",
            max_pages_to_read=0,
            parent_url="https://summary.example/article",
        ),
    )

    assert len(serper.requests) == 1
    assert len(tavily.requests) == 0
    assert result.stop_reason == "exa_required_for_second_hop"
    assert result.sufficient is False


def test_dedupe_keeps_second_hop_provenance_for_duplicate_url() -> None:
    url = "https://museum.example/original"
    direct = SourceCandidate(
        provider="serper",
        query="seed",
        url=url,
        title="Original source",
    )
    second_hop = SourceCandidate(
        provider="exa",
        query="seed",
        url=url,
        title="Original source",
        relation=SourceRelation.SECOND_HOP,
        parent_url="https://summary.example/article",
    )

    deduped = dedupe_sources((direct, second_hop))

    assert len(deduped) == 1
    assert deduped[0].provider == "exa"
    assert deduped[0].relation is SourceRelation.SECOND_HOP
    assert deduped[0].parent_url == "https://summary.example/article"
