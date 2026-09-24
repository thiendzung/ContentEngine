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
        assert request.url.path == (
            "/webmasters/v3/sites/sc-domain%3Amotgu.com/searchAnalytics/query"
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
        ),
        (
            datetime(2026, 9, 3, 12, tzinfo=UTC),
            "clicks",
            "0",
            {
                "page": "https://motgu.com/journal/certificate-authenticity/",
                "provider_date": "2026-09-03",
            },
        ),
        (
            datetime(2026, 9, 3, 12, tzinfo=UTC),
            "impressions",
            "4",
            {
                "page": "https://motgu.com/journal/certificate-authenticity/",
                "provider_date": "2026-09-03",
            },
        ),
    ]
    request_audit = result.raw_metrics["request"]
    assert isinstance(request_audit, dict)
    assert "authorization" not in request_audit
    assert "test-token" not in json.dumps(result.raw_metrics)


@pytest.mark.asyncio
async def test_search_console_zero_rows_is_valid_and_does_not_invent_zeroes() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={}, request=request)

    start, end = _window()
    async with SearchConsoleGateway(
        site_url="https://www.motgu.com/",
        token_provider=_TokenProvider(),
        transport=httpx.MockTransport(handler),
    ) as gateway:
        result = await gateway.acquire_page(
            canonical_url="https://www.motgu.com/journal/example/",
            window_start=start,
            window_end=end,
        )

    assert result.metrics == ()
    assert result.raw_metrics["response"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "search_console_unauthorized"),
        (403, "search_console_forbidden"),
        (429, "search_console_rate_limited"),
        (503, "search_console_upstream_error"),
        (418, "search_console_http_error"),
    ],
)
async def test_search_console_http_failures_are_stable(
    status: int,
    code: str,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "redacted"}, request=request)

    start, end = _window()
    async with SearchConsoleGateway(
        site_url="sc-domain:motgu.com",
        token_provider=_TokenProvider(),
        transport=httpx.MockTransport(handler),
    ) as gateway:
        with pytest.raises(SearchConsoleError, match=code) as exc_info:
            await gateway.acquire_page(
                canonical_url="https://motgu.com/example/",
                window_start=start,
                window_end=end,
            )

    assert exc_info.value.code == code


@pytest.mark.asyncio
async def test_search_console_rejects_duplicate_or_negative_provider_rows() -> None:
    payloads = [
        {
            "rows": [
                {"keys": ["2026-09-01"], "clicks": 1, "impressions": 2},
                {"keys": ["2026-09-01"], "clicks": 2, "impressions": 3},
            ]
        },
        {
            "rows": [
                {"keys": ["2026-09-01"], "clicks": -1, "impressions": 2},
            ]
        },
    ]
    expected_codes = [
        "search_console_response_duplicate_date",
        "search_console_clicks_invalid",
    ]

    start, end = _window()
    for payload, expected_code in zip(payloads, expected_codes, strict=True):
        async def handler(
            request: httpx.Request,
            *,
            response_payload: dict[str, object] = payload,
        ) -> httpx.Response:
            return httpx.Response(200, json=response_payload, request=request)

        async with SearchConsoleGateway(
            site_url="sc-domain:motgu.com",
            token_provider=_TokenProvider(),
            transport=httpx.MockTransport(handler),
        ) as gateway:
            with pytest.raises(SearchConsoleError, match=expected_code):
                await gateway.acquire_page(
                    canonical_url="https://motgu.com/example/",
                    window_start=start,
                    window_end=end,
                )


@pytest.mark.asyncio
async def test_search_console_rejects_invalid_property_page_and_window() -> None:
    with pytest.raises(SearchConsoleError, match="search_console_site_url_invalid"):
        SearchConsoleGateway(
            site_url="sc-domain:",
            token_provider=_TokenProvider(),
        )

    async with SearchConsoleGateway(
        site_url="sc-domain:motgu.com",
        token_provider=_TokenProvider(),
    ) as gateway:
        with pytest.raises(SearchConsoleError, match="search_console_page_url_invalid"):
            await gateway.acquire_page(
                canonical_url="not-a-url",
                window_start=datetime(2026, 9, 1, 12, tzinfo=UTC),
                window_end=datetime(2026, 9, 2, tzinfo=UTC),
            )
        with pytest.raises(
            SearchConsoleError,
            match="search_console_window_timezone_required",
        ):
            await gateway.acquire_page(
                canonical_url="https://motgu.com/example/",
                window_start=datetime(2026, 9, 1),
                window_end=datetime(2026, 9, 2),
            )

@pytest.mark.asyncio
async def test_search_console_metric_timestamps_are_bounded_by_partial_review_window() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "rows": [
                    {"keys": ["2026-09-01"], "clicks": 1, "impressions": 2},
                    {"keys": ["2026-09-02"], "clicks": 3, "impressions": 4},
                ]
            },
            request=request,
        )

    window_start = datetime(2026, 9, 1, 18, tzinfo=UTC)
    window_end = datetime(2026, 9, 2, 8, tzinfo=UTC)
    async with SearchConsoleGateway(
        site_url="sc-domain:motgu.com",
        token_provider=_TokenProvider(),
        transport=httpx.MockTransport(handler),
    ) as gateway:
        result = await gateway.acquire_page(
            canonical_url="https://motgu.com/example/",
            window_start=window_start,
            window_end=window_end,
        )

    timestamps = {metric.metric_date for metric in result.metrics}
    assert timestamps == {window_start, window_end}
    assert all(window_start <= value <= window_end for value in timestamps)