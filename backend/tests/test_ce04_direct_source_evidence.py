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


class CanonicalizingReader(FakeReader):
    async def read(self, url: str, *, query: str) -> PageReadResponse:
        self.urls.append(url)
        normalized = url.rstrip("/")
        return PageReadResponse(
            document=PageDocument(
                provider="jina",
                url=normalized,
                requested_url=normalized,
                final_url=normalized,
                title="Canonicalized source",
                content="A canonical direct-source document with enough factual text for testing.",
            ),
            call=ProviderCallArtifact(
                provider="jina",
                operation="read",
                query=query,
                purpose="selected_url_read",
                status="ok",
                result_count=1,
                raw_excerpt="canonicalized source",
            ),
        )


class RedirectingReader(FakeReader):
    async def read(self, url: str, *, query: str) -> PageReadResponse:
        self.urls.append(url)
        tracker = "https://match.adsrvr.org/track/cmf/google"
        return PageReadResponse(
            document=PageDocument(
                provider="jina",
                url=tracker,
                requested_url=url,
                final_url=tracker,
                title=tracker,
                content="A 1x1 image, likely be a tracker probe.",
            ),
            call=ProviderCallArtifact(
                provider="jina",
                operation="read",
                query=query,
                purpose="selected_url_read",
                status="ok",
                result_count=1,
                raw_excerpt="tracker probe",
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
    assert source.source_type == "educational"
    assert source.commercial_bias.value == "low"
    assert source.intended_use.value == "discovery"
    assert source.found_via == "human_review_locked_url"


@pytest.mark.asyncio
async def test_direct_source_runner_accepts_benign_trailing_slash_normalization() -> None:
    url = "https://americanart.si.edu/research/my-art/object-worth/"
    reader = CanonicalizingReader()
    runner = DirectSourceResearchRunner(reader=reader, source_url=url)
    result = await runner.run(
        cast(AsyncSession, object()),
        request=ProductionResearchRequest(
            project_id=uuid4(),
            query="artwork value",
            max_pages_to_read=1,
        ),
    )

    assert reader.urls == [url]
    assert result.selected_sources[0].url == url
    assert result.documents[0].final_url == url.rstrip("/")


@pytest.mark.asyncio
async def test_direct_source_runner_rejects_reader_url_escape() -> None:
    url = "https://americanart.si.edu/research/my-art/prints-posters"
    reader = RedirectingReader()
    runner = DirectSourceResearchRunner(reader=reader, source_url=url)

    with pytest.raises(ValueError, match="direct_source_url_binding_mismatch"):
        await runner.run(
            cast(AsyncSession, object()),
            request=ProductionResearchRequest(
                project_id=uuid4(),
                query="original print edition reproduction",
                max_pages_to_read=1,
            ),
        )

    assert reader.urls == [url]


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
