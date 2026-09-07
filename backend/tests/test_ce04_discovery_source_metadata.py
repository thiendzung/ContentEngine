from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.research.contracts import (
    CommercialBias,
    ProductionResearchRequest,
    ProductionResearchResult,
    SourceCandidate,
)
from app.modules.research.discovery import DiscoveryResearchWorkflow, DiscoveryWorkflowRequest
from app.modules.research.keyword_plan.contracts import NeedType
from app.modules.research.keyword_plan.service import OpportunityMapRequest


class StaticRouter:
    def __init__(self, result: ProductionResearchResult) -> None:
        self.result = result

    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: object = None,
        step_run_id: object = None,
    ) -> ProductionResearchResult:
        del session, run_id, step_run_id
        assert request is self.result.request
        return self.result


@pytest.mark.asyncio
async def test_unknown_source_metadata_stays_unknown_instead_of_guessing_authority() -> None:
    request = ProductionResearchRequest(
        project_id=uuid4(),
        query="first-time art buyer questions",
        locale="en",
        max_pages_to_read=0,
    )
    source = SourceCandidate(
        provider="serper",
        query=request.query,
        url="https://example.test/general-page",
        title="General page",
        source_type="editorial_or_unknown",
        commercial_bias=CommercialBias.UNKNOWN,
        why_selected="Potentially relevant source; authority remains unverified.",
    )
    production = ProductionResearchResult(
        request=request,
        source_candidates=[source],
        selected_sources=[source],
        sufficient=False,
        stop_reason="bounded_search_exhausted",
    )
    workflow = DiscoveryResearchWorkflow(router=StaticRouter(production))

    result = await workflow.run(
        cast(AsyncSession, object()),
        request=DiscoveryWorkflowRequest(
            research=request,
            opportunity=OpportunityMapRequest(
                project_id="motgu",
                locale="en",
                audience_scope="international first-time art buyer",
                situation="considering original art",
                reader="international first-time art buyer",
                need_statement="I want to understand how to choose my first artwork.",
                need_type=NeedType.QUESTION,
            ),
        ),
    )

    metadata = result.source_metadata[0]
    assert metadata.source_type == "editorial_or_unknown"
    assert metadata.commercial_bias is CommercialBias.UNKNOWN
    assert metadata.authority_hint is None
    assert "rank/provider score is excluded" in metadata.metadata_reason
