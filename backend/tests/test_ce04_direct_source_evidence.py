from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.research.contracts import (
    PageDocument,
    PageReadResponse,
    ProductionResearchRequest,
    ProviderCallArtifact,
)
from app.modules.research.evidence.direct_source import DirectSourceResearchRunner


class FakeReader:
    def __init__(self) -> None:
        self.urls: list[str] = []

    async def read(self, url: str, *, query: str) -> PageReadResponse:
        self.urls.append(url)
        return PageReadResponse(
            document=PageDocument(
                provider="jina",
                url=url,
                requested_url=url,
                final_url=url,
                title="How Much Is Your Object Worth?",
                content=(
                    "It is hard to establish fixed values for antiques, artworks, and other "
                    "collectible items. The amount asked or offered is determined by many "
                    "factors, including the condition of the object and trends in the market."
                ),
            ),
            call=ProviderCallArtifact(
                provider="jina",
                operation="read",
                query=query,
                purpose="selected_url_read",
                status="ok",
                result_count=1,
                raw_excerpt="smithsonian excerpt",
            ),
        )


@pytest.mark.asyncio
async def test_direct_source_runner_reads_locked_url_without_search() -> None:
    url = "https://americanart.si.edu/research/my-art/object-worth"
    reader = FakeReader()
    runner = DirectSourceResearchRunner(reader=reader, source_url=url)
    result = await runner.run(
        cast(AsyncSession, object()),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="How do I know if an original artwork is fairly priced?",
            max_pages_to_read=1,
        ),
    )

    assert reader.urls == [url]
    assert result.stop_reason == "direct_source_read_success"
    assert result.sufficient is True
    assert result.external_provider_calls == 1
    assert result.signals == []
    assert len(result.documents) == 1
    assert len(result.selected_sources) == 1
    source = result.selected_sources[0]
    assert source.url == url
    assert source.source_type == "institutional"
    assert source.commercial_bias.value == "low"
    assert source.intended_use.value == "evidence_candidate"
    assert source.found_via == "human_review_locked_url"


@pytest.mark.asyncio
async def test_direct_source_runner_requires_page_budget() -> None:
    runner = DirectSourceResearchRunner(
        reader=FakeReader(),
        source_url="https://americanart.si.edu/research/my-art/object-worth",
    )
    with pytest.raises(ValueError, match="direct_source_requires_one_page_read"):
        await runner.run(
            cast(AsyncSession, object()),
            request=ProductionResearchRequest(
                project_id=uuid4(),
                query="artwork value",
                max_pages_to_read=0,
            ),
        )
