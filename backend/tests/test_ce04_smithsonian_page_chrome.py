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
        raise AssertionError("router should not be called")


def test_smithsonian_page_chrome_is_rejected_before_claim_ranking() -> None:
    url = "https://americanart.si.edu/research/my-art/object-worth"
    source = SourceCandidate(
        provider="direct_source",
        query="artwork appraisal fair market value condition comparable sales",
        url=url,
        title="How Much Is Your Object Worth?",
        source_type="institutional",
        commercial_bias=CommercialBias.LOW,
        intended_use=IntendedUse.EVIDENCE_CANDIDATE,
    )
    production = ProductionResearchResult(
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="artwork appraisal fair market value condition comparable sales",
            max_pages_to_read=1,
        ),
        source_candidates=[source],
        selected_sources=[source],
        documents=[
            PageDocument(
                provider="jina",
                url=url,
                final_url=url,
                content=(
                    "[Collection Highlights](https://americanart.si.edu/art/highlights)\n"
                    "* [Search Artworks](https://americanart.si.edu/search/artworks)\n"
                    "* [Search Artists](https://americanart.si.edu/search/artists)\n\n"
                    "[Latinx Art](https://americanart.si.edu/art/highlights/latinx)"
                    "[![Image: Latinx Art](https://example.test/latinx.jpg)]"
                    "(https://americanart.si.edu/art/highlights/latinx)\n\n"
                    "It is hard to establish fixed values for artworks because the amount "
                    "asked or offered can depend on the condition of the object and trends "
                    "in the market.\n\n"
                    "Current sale and auction prices for comparable artworks can help a buyer "
                    "understand market context, but they do not create one fixed value for "
                    "every artwork."
                ),
            )
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
        topic_texts=("How do I know if an original artwork is fairly priced?",),
        limit=8,
    )

    statements = [candidate.statement for candidate in candidates]
    assert len(statements) == 2
    assert all(candidate.relation.value == "supports" for candidate in candidates)
    assert any("condition of the object" in statement for statement in statements)
    assert any("comparable artworks" in statement for statement in statements)
    assert not any("Collection Highlights" in statement for statement in statements)
    assert not any("Search Artworks" in statement for statement in statements)
    assert not any("![" in statement for statement in statements)
