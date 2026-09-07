from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    PageDocument,
    ProductionResearchRequest,
    ProductionResearchResult,
    SourceCandidate,
)
from app.modules.research.evidence import EvidenceResearchWorkflow


class _UnusedRouter:
    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> ProductionResearchResult:
        raise AssertionError("router should not be called in extraction unit test")


def _source(url: str) -> SourceCandidate:
    return SourceCandidate(
        provider="serper",
        query="art valuation",
        url=url,
        title=url,
        source_type="institutional",
        commercial_bias=CommercialBias.LOW,
        intended_use=IntendedUse.EVIDENCE_CANDIDATE,
    )


def test_claim_extraction_skips_page_chrome_and_balances_documents() -> None:
    urls = [
        "https://museum.example/valuation",
        "https://institute.example/appraisal",
        "https://archive.example/market",
    ]
    off_scope_url = "https://dealstream.example/museums/rules-of-thumb"
    sources = [_source(url) for url in (*urls, off_scope_url)]
    request = ProductionResearchRequest(
        project_id=uuid4(),
        query=(
            "artwork valuation factors provenance condition size medium "
            "comparable sales artist market history"
        ),
        max_pages_to_read=4,
    )
    result = ProductionResearchResult(
        request=request,
        source_candidates=sources,
        selected_sources=sources,
        documents=[
            PageDocument(
                provider="jina",
                url=urls[0],
                final_url=urls[0],
                content=(
                    "[Skip to content](https://museum.example/valuation#main)\n\n"
                    "![Artwork valuation](https://museum.example/image.jpg)\n\n"
                    "Artwork Valuation Factors\n\n"
                    "Condition and documented provenance can affect how an artwork is "
                    "evaluated because they change what buyers can verify about the work."
                ),
            ),
            PageDocument(
                provider="jina",
                url=urls[1],
                final_url=urls[1],
                content=(
                    "Comparable sales for genuinely similar artworks can provide useful market "
                    "context when judging an asking price, but they do not create a "
                    "universal formula."
                ),
            ),
            PageDocument(
                provider="jina",
                url=urls[2],
                final_url=urls[2],
                content=(
                    "An artist's market history, the medium, and the size of a work are commonly "
                    "considered alongside provenance and condition during valuation."
                ),
            ),
            PageDocument(
                provider="jina",
                url=off_scope_url,
                final_url=off_scope_url,
                content=(
                    "While no single metric can fully capture a museum's multifaceted value, "
                    "comparable sales, revenue multiples, and real estate benchmarks can provide "
                    "a structured framework for preliminary museum valuation."
                ),
            ),
        ],
        sufficient=True,
    )

    workflow = EvidenceResearchWorkflow(router=_UnusedRouter())
    candidates = workflow._extract_claim_candidates(
        result,
        subject_text=(
            "A first-time art buyer wants to understand whether an original artwork price "
            "makes sense before deciding to buy."
        ),
        topic_texts=(
            "How do I know if an original artwork is fairly priced?",
            "evaluate the price of an artwork",
        ),
        limit=6,
    )

    assert {candidate.source_url for candidate in candidates} == set(urls)
    assert all(candidate.relation.value == "supports" for candidate in candidates)
    assert not any("Skip to content" in candidate.statement for candidate in candidates)
    assert not any(candidate.statement.startswith("![") for candidate in candidates)
    assert not any(candidate.statement == "Artwork Valuation Factors" for candidate in candidates)
    assert not any(candidate.source_url == off_scope_url for candidate in candidates)
    assert any("provenance" in candidate.statement.casefold() for candidate in candidates)
    assert any("Comparable sales" in candidate.statement for candidate in candidates)
    assert any("market history" in candidate.statement for candidate in candidates)


def test_claim_extraction_uses_need_statement_not_planning_label() -> None:
    artwork_url = "https://museumexchange.com/art-appraisals"
    price_only_url = "https://example.com/auction-price"
    sources = [
        SourceCandidate(
            provider="serper",
            query="art appraisal",
            url=artwork_url,
            title="Art appraisal guide",
            source_type="institutional",
            commercial_bias=CommercialBias.LOW,
            intended_use=IntendedUse.EVIDENCE_CANDIDATE,
        ),
        SourceCandidate(
            provider="serper",
            query="art appraisal",
            url=price_only_url,
            title="Auction result",
            source_type="institutional",
            commercial_bias=CommercialBias.LOW,
            intended_use=IntendedUse.EVIDENCE_CANDIDATE,
        ),
    ]
    production = ProductionResearchResult(
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="art appraisal valuation factors comparable sales price",
            max_pages_to_read=2,
        ),
        source_candidates=sources,
        selected_sources=sources,
        documents=[
            PageDocument(
                provider="jina",
                url=artwork_url,
                final_url=artwork_url,
                content=(
                    "In preparing an appraisal, the appraiser will assess a number of factors "
                    "pertaining to the artwork and use these to contextualize it with comparable "
                    "artworks that have transacted on the open market."
                ),
            ),
            PageDocument(
                provider="jina",
                url=price_only_url,
                final_url=price_only_url,
                content="The price was $9,500 and the lot closed after a short auction.",
            ),
        ],
        sufficient=True,
    )

    workflow = EvidenceResearchWorkflow(router=_UnusedRouter())
    candidates = workflow._extract_claim_candidates(
        production,
        subject_text=(
            "A first-time art buyer wants to understand whether an original artwork price "
            "makes sense before deciding to buy."
        ),
        topic_texts=("Artsy prices",),
        limit=2,
    )

    assert [candidate.source_url for candidate in candidates] == [artwork_url]
    assert "comparable artworks" in candidates[0].statement
    assert "9,500" not in candidates[0].statement
