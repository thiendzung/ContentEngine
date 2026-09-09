from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.research.production as production_module
from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    Source,
    SourceDocument,
)
from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    PageDocument,
    PageReadResponse,
    ProductionResearchRequest,
    ProductionResearchResult,
    ProviderCallArtifact,
    ProviderResponse,
    ResearchDepth,
    SearchRequest,
    SourceCandidate,
    SourceRelation,
)
from app.modules.research.evidence.contracts import ClaimCandidate
from app.modules.research.evidence.persistence import (
    persist_claim_evidence,
    persist_read_documents,
)
from app.modules.research.production import ResearchRouter
from app.modules.research.utils import dedupe_sources

SUMMARY_URL = "https://summary.example/artwork-pricing-guide"
ORIGINAL_URL = "https://museum.example/original-valuation-guidance"
ORIGINAL_EXCERPT = (
    "The museum guidance says comparable works and current market conditions "
    "should be considered together when assessing an artwork valuation."
)
SUMMARY_ONLY_TEXT = "The summary claims that every listed artwork price is fair."
O4_OPPORTUNITY_ID = UUID("068991ab-de34-4787-9c38-8935c3f0e2da")
O4_CONTENT_CASE_ID = UUID("9ec6133b-5f14-46d0-9866-e3b049e537b5")
O4_EVIDENCE_SET_ID = UUID("c5d46edb-3557-4efb-a479-8dd5702ae6c9")
O4_ORIGINALITY_PACK_ID = UUID("6bd287ec-43f9-4d69-957c-2223f258f909")


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


async def _empty_retrieval(*args: object, **kwargs: object) -> tuple[object, ...]:
    del args, kwargs
    return ()


class StubSearchProvider:
    def __init__(self, name: str, response: ProviderResponse) -> None:
        self.name = name
        self.response = response
        self.requests: list[SearchRequest] = []

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return 1

    async def search(self, request: SearchRequest) -> ProviderResponse:
        self.requests.append(request)
        return self.response


class StubReader:
    name = "jina"

    def __init__(self) -> None:
        self.urls: list[str] = []

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        self.urls.append(url)
        return PageReadResponse(
            document=PageDocument(
                provider=self.name,
                url=url,
                requested_url=url,
                final_url=url,
                title="Original valuation guidance",
                content=f"Original source.\n\n{ORIGINAL_EXCERPT}",
            ),
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


def _request(project_id: UUID, *, max_pages_to_read: int = 1) -> ProductionResearchRequest:
    return ProductionResearchRequest(
        project_id=project_id,
        query="original source for artwork pricing",
        locale="en",
        country="us",
        limit=2,
        depth=ResearchDepth.DEEP,
        max_pages_to_read=max_pages_to_read,
        parent_url=SUMMARY_URL,
    )


def _direct_summary_candidate() -> SourceCandidate:
    return SourceCandidate(
        provider="serper",
        query="original source for artwork pricing",
        url=SUMMARY_URL,
        title="Summary artwork pricing guide",
        snippet="A summary page linking to original valuation guidance.",
        source_type="editorial",
        commercial_bias=CommercialBias.MEDIUM,
        found_via="google_organic",
        relation=SourceRelation.DIRECT,
    )


def _second_hop_candidate(*, parent_url: str | None = SUMMARY_URL) -> SourceCandidate:
    return SourceCandidate(
        provider="exa",
        query="original source for artwork pricing",
        url=ORIGINAL_URL,
        title="Original museum valuation guidance",
        snippet="Original-source candidate discovered from the summary.",
        source_type="institutional",
        commercial_bias=CommercialBias.LOW,
        found_via="exa_second_hop",
        relation=SourceRelation.SECOND_HOP,
        intended_use=IntendedUse.EVIDENCE_CANDIDATE,
        parent_url=parent_url,
    )


def _router(*, include_exa: bool, reader: StubReader | None = None) -> tuple[
    ResearchRouter, StubSearchProvider, StubSearchProvider | None
]:
    serper = StubSearchProvider(
        "serper",
        ProviderResponse((), (_direct_summary_candidate(),), ()),
    )
    exa = (
        StubSearchProvider(
            "exa",
            ProviderResponse((), (_second_hop_candidate(),), ()),
        )
        if include_exa
        else None
    )
    return ResearchRouter(serper=serper, exa=exa, reader=reader), serper, exa


@pytest.mark.asyncio
async def test_second_hop_request_and_candidate_preserve_exact_parent_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    router, _, exa = _router(include_exa=True)
    assert exa is not None

    result = await router.run(
        cast(AsyncSession, object()),
        request=_request(uuid4(), max_pages_to_read=0),
    )

    assert len(exa.requests) == 1
    assert exa.requests[0].parent_url == SUMMARY_URL
    second_hop = next(
        source
        for source in result.source_candidates
        if source.relation is SourceRelation.SECOND_HOP
    )
    assert second_hop.provider == "exa"
    assert second_hop.relation is SourceRelation.SECOND_HOP
    assert second_hop.parent_url == SUMMARY_URL
    assert second_hop.url == ORIGINAL_URL
    assert second_hop.found_via == "exa_second_hop"
    assert second_hop.intended_use == "evidence_candidate"


@pytest.mark.asyncio
async def test_second_hop_is_selected_and_persisted_to_original_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    reader = StubReader()
    router, _, _ = _router(include_exa=True, reader=reader)

    async with isolated_session() as session:
        project_id = (
            await session.execute(select(Project.id).limit(1))
        ).scalar_one()
        result = await router.run(
            session,
            request=_request(project_id),
        )

        assert result.selected_sources[0].relation is SourceRelation.SECOND_HOP
        assert result.selected_sources[0].url == ORIGINAL_URL
        assert reader.urls == [ORIGINAL_URL]

        page_refs = await persist_read_documents(session, production=result)
        page_ref = page_refs[ORIGINAL_URL]
        source = await session.get(Source, page_ref.source_id)
        document = await session.get(SourceDocument, page_ref.source_document_id)
        assert source is not None
        assert document is not None
        assert source.canonical_url == ORIGINAL_URL
        assert document.canonical_url == ORIGINAL_URL
        assert document.source_id == source.id
        assert source.provenance_json == {
            "method": "evidence_read",
            "provider": "jina",
            "query": result.request.query,
            "source_ref": ORIGINAL_URL,
            "evidence_candidate": True,
            "discovered_by": "exa",
            "found_via": "exa_second_hop",
            "relation": "second_hop",
            "intended_use": "evidence_candidate",
            "parent_url": SUMMARY_URL,
        }

        link = await persist_claim_evidence(
            session,
            project_id=project_id,
            page_refs=page_refs,
            candidate=ClaimCandidate(
                statement=ORIGINAL_EXCERPT,
                source_url=ORIGINAL_URL,
                locator="document_sentence:2",
                excerpt=ORIGINAL_EXCERPT,
            ),
        )
        evidence = await session.get(Evidence, link.evidence_id)
        claim = await session.get(Claim, link.claim_id)
        assert evidence is not None
        assert claim is not None
        assert evidence.source_document_id == document.id
        assert evidence.excerpt == ORIGINAL_EXCERPT
        assert evidence.excerpt in document.content_markdown
        assert SUMMARY_URL not in {source.canonical_url, document.canonical_url}
        assert evidence.provenance_json["source_id"] == str(source.id)
        assert evidence.provenance_json["source_document_id"] == str(document.id)
        assert evidence.provenance_json["source_document_hash"] == document.content_hash
        assert "parent_url" not in evidence.provenance_json


@pytest.mark.asyncio
async def test_summary_only_excerpt_cannot_become_original_source_evidence() -> None:
    async with isolated_session() as session:
        project_id = (
            await session.execute(select(Project.id).limit(1))
        ).scalar_one()
        production = _production_with_document(
            project_id,
            source_candidates=[_second_hop_candidate()],
        )
        page_refs = await persist_read_documents(session, production=production)
        before_claims = int(await session.scalar(select(func.count()).select_from(Claim)))
        before_evidence = int(await session.scalar(select(func.count()).select_from(Evidence)))

        with pytest.raises(ValueError, match="evidence_excerpt_not_found_in_source_document"):
            await persist_claim_evidence(
                session,
                project_id=project_id,
                page_refs=page_refs,
                candidate=ClaimCandidate(
                    statement=SUMMARY_ONLY_TEXT,
                    source_url=ORIGINAL_URL,
                    locator="summary:snippet:1",
                    excerpt=SUMMARY_ONLY_TEXT,
                ),
            )

        assert (
            int(await session.scalar(select(func.count()).select_from(Claim)))
            == before_claims
        )
        assert (
            int(await session.scalar(select(func.count()).select_from(Evidence)))
            == before_evidence
        )


@pytest.mark.asyncio
async def test_missing_parent_provenance_is_rejected_before_source_persistence() -> None:
    async with isolated_session() as session:
        project_id = (
            await session.execute(select(Project.id).limit(1))
        ).scalar_one()
        before_sources = int(await session.scalar(select(func.count()).select_from(Source)))
        with pytest.raises(ValueError, match="second_hop_parent_url_required"):
            await persist_read_documents(
                session,
                production=_production_with_document(
                    project_id,
                    source_candidates=[_second_hop_candidate(parent_url=None)],
                ),
            )
        assert (
            int(await session.scalar(select(func.count()).select_from(Source)))
            == before_sources
        )


@pytest.mark.asyncio
async def test_wrong_parent_provenance_is_rejected() -> None:
    async with isolated_session() as session:
        project_id = (
            await session.execute(select(Project.id).limit(1))
        ).scalar_one()
        with pytest.raises(ValueError, match="second_hop_parent_url_mismatch"):
            await persist_read_documents(
                session,
                production=_production_with_document(
                    project_id,
                    source_candidates=[
                        _second_hop_candidate(parent_url="https://summary.example/wrong")
                    ],
                ),
            )


def test_dedupe_keeps_second_hop_provenance_for_duplicate_original_url() -> None:
    direct = SourceCandidate(
        provider="serper",
        query="original source for artwork pricing",
        url=ORIGINAL_URL,
        title="Direct result",
        relation=SourceRelation.DIRECT,
    )
    second_hop = _second_hop_candidate()

    deduped = dedupe_sources((direct, second_hop))

    assert len(deduped) == 1
    assert deduped[0].relation is SourceRelation.SECOND_HOP
    assert deduped[0].parent_url == SUMMARY_URL
    assert deduped[0].provider == "exa"


@pytest.mark.asyncio
async def test_unavailable_exa_does_not_promote_direct_result_to_second_hop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(production_module, "retrieve_chunks", _empty_retrieval)
    router, serper, _ = _router(include_exa=False)

    result = await router.run(
        cast(AsyncSession, object()),
        request=_request(uuid4(), max_pages_to_read=0),
    )

    assert len(serper.requests) == 1
    assert serper.requests[0].parent_url == SUMMARY_URL
    assert result.sufficient is False
    assert result.stop_reason == "exa_required_for_second_hop"
    assert not any(
        source.relation is SourceRelation.SECOND_HOP
        for source in result.source_candidates
    )


def _production_with_document(
    project_id: UUID,
    *,
    source_candidates: list[SourceCandidate],
) -> ProductionResearchResult:
    return ProductionResearchResult(
        request=_request(project_id),
        source_candidates=source_candidates,
        selected_sources=source_candidates,
        documents=[
            PageDocument(
                provider="jina",
                url=ORIGINAL_URL,
                requested_url=ORIGINAL_URL,
                final_url=ORIGINAL_URL,
                title="Original valuation guidance",
                content=f"Original source.\n\n{ORIGINAL_EXCERPT}",
            )
        ],
        sufficient=True,
        stop_reason="synthetic_read_success",
    )
