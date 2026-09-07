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
    sources = [_source(url) for url in urls]
    request = ProductionResearchRequest(
        project_id=uuid4(),
        query=(
            "artwork valuation factors provenance condition size medium "
            "comparable sales artist market history"
        ),
        max_pages_to_read=3,
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
                    "Comparable sales for genuinely similar works can provide useful market "
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
        ],
        sufficient=True,
    )

    workflow = EvidenceResearchWorkflow(router=_UnusedRouter())
    candidates = workflow._extract_claim_candidates(
        result,
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
    assert any("provenance" in candidate.statement.casefold() for candidate in candidates)
    assert any("Comparable sales" in candidate.statement for candidate in candidates)
    assert any("market history" in candidate.statement for candidate in candidates)
