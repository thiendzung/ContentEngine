from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.research.contracts import (
    PageReadResponse,
    ProductionResearchRequest,
    ProductionResearchResult,
    ProviderDecision,
    ProviderDecisionStatus,
)
from app.modules.research.utils import annotate_source


class PageReader(Protocol):
    async def read(self, url: str, *, query: str) -> PageReadResponse: ...


class DirectSourceResearchRunner:
    """Read one human-reviewed public URL without running search discovery."""

    def __init__(self, *, reader: PageReader, source_url: str) -> None:
        source_url = source_url.strip()
        if not source_url:
            raise ValueError("direct_source_url_required")
        self._reader = reader
        self._source_url = source_url

    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> ProductionResearchResult:
        del session, run_id, step_run_id
        if request.max_pages_to_read < 1:
            raise ValueError("direct_source_requires_one_page_read")

        page = await self._reader.read(self._source_url, query=request.query)
        source_url = page.document.final_url or page.document.url or self._source_url
        source = annotate_source(
            provider="direct_source",
            query=request.query,
            url=source_url,
            title=page.document.title or source_url,
            snippet="",
            found_via="human_review_locked_url",
        )
        return ProductionResearchResult(
            request=request,
            decisions=[
                ProviderDecision(
                    provider=page.call.provider,
                    status=ProviderDecisionStatus.CALLED,
                    reason="direct_source_locked_url_read",
                )
            ],
            calls=[page.call],
            source_candidates=[source],
            selected_sources=[source],
            documents=[page.document],
            stop_reason="direct_source_read_success",
            sufficient=True,
        )
