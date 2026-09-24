from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.modules.measurement.search_console import (
    SearchConsoleError,
    SearchConsoleGateway,
)


class _TokenProvider:
    def __init__(self, token: str = "test-token") -> None:
        self.token = token
        self.calls = 0

    async def access_token(self) -> str:
        self.calls += 1
        return self.token


def _window() -> tuple[datetime, datetime]:
    return (
        datetime(2026, 9, 1, 12, tzinfo=UTC),
        datetime(2026, 9, 3, 23, 59, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_search_console_acquires_exact_page_daily_metrics() -> None:
    token_provider = _TokenProvider()
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "POST"
        assert str(request.url) == (
            "https://www.googleapis.com/webmasters/v3/sites/"
            "sc-domain%3Amotgu.com/searchAnalytics/query"
        )
        assert request.headers["authorization"] == "Bearer test-token"
        body = json.loads(request.content.decode("utf-8"))
        assert body == {
            "startDate": "2026-09-01",
            "endDate": "2026-09-03",
            "dimensions": ["date"],
            "dimensionFilterGroups": [
                {
                    "filters": [
                        {
                            "dimension": "page",
                            "operator": "equals",
                            "expression": "https://motgu.com/journal/certificate-authenticity/",
                        }
                    ]
                }
            ],
            "rowLimit": 25000,
        }
        return httpx.Response(
            200,
            json={
                "rows": [
                    {
                        "keys": ["2026-09-01"],
                        "clicks": 3,
                        "impressions": 21,
                        "ctr": 0.142857,
                        "position": 5.2,
                    },
                    {
                        "keys": ["2026-09-03"],
                        "clicks": 0,
                        "impressions": 4,
                        "ctr": 0,
                        "position": 9.0,
                    },
                ],
                "responseAggregationType": "byPage",
            },
            request=request,
        )

    start, end = _window()
    async with SearchConsoleGateway(
        site_url="sc-domain:motgu.com",
        token_provider=token_provider,
        transport=httpx.MockTransport(handler),
    ) as gateway:
        result = await gateway.acquire_page(
            canonical_url="https://motgu.com/journal/certificate-authenticity/",
            window_start=start,
            window_end=end,
        )

    assert token_provider.calls == 1
    assert len(seen) == 1
    assert [
        (row.metric_date, row.metric_name, str(row.metric_value), row.dimensions)
        for row in result.metrics
    ] == [
        (
            datetime(2026, 9, 1, 12, tzinfo=UTC),
            "clicks",
            "3",
            {
                "page": "https://motgu.com/journal/certificate-authenticity/",
                "provider_date": "2026-09-01",
            },
        ),
        (
            datetime(2026, 9, 1, 12, tzinfo=UTC),
            "impressions",
            "21",
            {
                "page": "https://motgu.com/journal/certificate-authenticity/",
                "provider_date": "2026-09-01",
            },