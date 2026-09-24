"""Read-only Google Search Console acquisition for PM-01 measurement."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast
from urllib.parse import quote, urlsplit

import httpx
from google.auth.exceptions import GoogleAuthError  # type: ignore[import-untyped]
from google.auth.transport.requests import Request as GoogleAuthRequest  # type: ignore[import-untyped]
from google.oauth2 import service_account  # type: ignore[import-untyped]

from app.core.config import Settings
from app.modules.measurement.service import MetricInput

_READONLY_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
_API_ROOT = "https://www.googleapis.com/webmasters/v3"


class SearchConsoleError(ValueError):
    """Stable fail-closed Search Console acquisition error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SearchConsoleTokenProvider(Protocol):
    async def access_token(self) -> str:
        """Return one bearer token without exposing credential material."""


@dataclass(frozen=True, slots=True)
class SearchConsoleConfig:
    site_url: str
    service_account_json: str
    timeout_seconds: float = 20.0


@dataclass(frozen=True, slots=True)
class SearchConsoleAcquisition:
    raw_metrics: dict[str, object]
    metrics: tuple[MetricInput, ...]


class GoogleServiceAccountTokenProvider:
    """Cached service-account token source scoped to Search Console read-only."""

    def __init__(self, service_account_json: str) -> None:
        raw = service_account_json.strip()
        if not raw:
            raise SearchConsoleError("search_console_credentials_required")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SearchConsoleError("search_console_credentials_invalid") from exc
        if not isinstance(parsed, dict):
            raise SearchConsoleError("search_console_credentials_invalid")
        try:
            self._credentials = service_account.Credentials.from_service_account_info(
                cast(dict[str, object], parsed),
                scopes=[_READONLY_SCOPE],
            )
        except (GoogleAuthError, ValueError, TypeError) as exc:
            raise SearchConsoleError("search_console_credentials_invalid") from exc
        self._lock = asyncio.Lock()

    async def access_token(self) -> str:
        async with self._lock:
            if not self._credentials.valid or not self._credentials.token:
                try:
                    await asyncio.to_thread(
                        self._credentials.refresh,
                        GoogleAuthRequest(),
                    )
                except GoogleAuthError as exc:
                    raise SearchConsoleError("search_console_auth_failed") from exc
            token = self._credentials.token
            if not isinstance(token, str) or not token.strip():
                raise SearchConsoleError("search_console_auth_failed")
            return token


def _validated_site_url(value: str) -> str:
    site_url = value.strip()
    if not site_url:
        raise SearchConsoleError("search_console_site_url_required")
    if site_url.startswith("sc-domain:"):
        domain = site_url.removeprefix("sc-domain:").strip()
        if (
            not domain
            or "/" in domain
            or "@" in domain
            or domain.startswith(".")
            or domain.endswith(".")
        ):
            raise SearchConsoleError("search_console_site_url_invalid")
        return f"sc-domain:{domain}"

    parsed = urlsplit(site_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise SearchConsoleError("search_console_site_url_invalid")
    return site_url


def _validated_page_url(value: str) -> str:
    page_url = value.strip()
    parsed = urlsplit(page_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise SearchConsoleError("search_console_page_url_invalid")
    return page_url


def _validated_window(window_start: datetime, window_end: datetime) -> tuple[date, date]:
    if window_start.tzinfo is None or window_end.tzinfo is None:
        raise SearchConsoleError("search_console_window_timezone_required")
    if window_end < window_start:
        raise SearchConsoleError("search_console_window_invalid")
    return window_start.date(), window_end.date()


def _decimal(value: object, *, code: str) -> Decimal:
    if isinstance(value, bool):
        raise SearchConsoleError(code)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SearchConsoleError(code) from exc
    if not parsed.is_finite() or parsed < 0:
        raise SearchConsoleError(code)
    return parsed


def _metric_datetime(provider_date: date) -> datetime:
    return datetime.combine(provider_date, time.min, tzinfo=UTC)


def _parse_rows(
    payload: dict[str, object],
    *,
    canonical_url: str,
) -> tuple[MetricInput, ...]:
    rows = payload.get("rows", [])
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise SearchConsoleError("search_console_response_invalid")

    metrics: list[MetricInput] = []
    seen_dates: set[date] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SearchConsoleError("search_console_response_invalid")
        typed_row = cast(dict[str, object], row)
        keys = typed_row.get("keys")
        if (
            not isinstance(keys, list)
            or len(keys) != 1
            or not isinstance(keys[0], str)
        ):
            raise SearchConsoleError("search_console_response_invalid")
        try:
            provider_date = date.fromisoformat(keys[0])
        except ValueError as exc:
            raise SearchConsoleError("search_console_response_invalid") from exc
        if provider_date in seen_dates:
            raise SearchConsoleError("search_console_response_duplicate_date")
        seen_dates.add(provider_date)

        clicks = _decimal(
            typed_row.get("clicks"),
            code="search_console_clicks_invalid",
        )
        impressions = _decimal(
            typed_row.get("impressions"),
            code="search_console_impressions_invalid",
        )
        dimensions = {
            "page": canonical_url,
            "provider_date": provider_date.isoformat(),
        }
        metric_date = _metric_datetime(provider_date)
        metrics.extend(
            (
                MetricInput(
                    metric_date=metric_date,
                    metric_name="clicks",
                    metric_value=clicks,
                    dimensions=dimensions,
                ),
                MetricInput(
                    metric_date=metric_date,
                    metric_name="impressions",
                    metric_value=impressions,
                    dimensions=dimensions,
                ),
            )
        )
    return tuple(metrics)


class SearchConsoleGateway:
    """Acquire page-bound Search Analytics rows without persisting or interpreting them."""

    def __init__(
        self,
        *,
        site_url: str,
        token_provider: SearchConsoleTokenProvider,
        timeout_seconds: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise SearchConsoleError("search_console_timeout_invalid")
        self._site_url = _validated_site_url(site_url)
        self._token_provider = token_provider
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            transport=transport,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> "SearchConsoleGateway":
        site_url = settings.search_console_site_url or ""
        secret = (
            settings.search_console_service_account_json.get_secret_value()
            if settings.search_console_service_account_json is not None
            else ""
        )
        return cls(
            site_url=site_url,
            token_provider=GoogleServiceAccountTokenProvider(secret),
            timeout_seconds=settings.search_console_request_timeout_seconds,
            transport=transport,
        )

    async def __aenter__(self) -> "SearchConsoleGateway":
        return self

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _traceback: object,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def acquire_page(
        self,
        *,
        canonical_url: str,
        window_start: datetime,
        window_end: datetime,
    ) -> SearchConsoleAcquisition:
        page_url = _validated_page_url(canonical_url)
        start_date, end_date = _validated_window(window_start, window_end)
        token = await self._token_provider.access_token()

        endpoint = (
            f"{_API_ROOT}/sites/{quote(self._site_url, safe='')}"
            "/searchAnalytics/query"
        )
        request_body: dict[str, object] = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["date"],
            "dimensionFilterGroups": [
                {
                    "filters": [
                        {
                            "dimension": "page",
                            "operator": "equals",
                            "expression": page_url,
                        }
                    ]
                }
            ],
            "rowLimit": 25000,
        }
        try:
            response = await self._client.post(
                endpoint,
                json=request_body,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            raise SearchConsoleError("search_console_transport_error") from exc

        if response.status_code == 401:
            raise SearchConsoleError("search_console_unauthorized")
        if response.status_code == 403:
            raise SearchConsoleError("search_console_forbidden")
        if response.status_code == 429:
            raise SearchConsoleError("search_console_rate_limited")
        if 500 <= response.status_code <= 599:
            raise SearchConsoleError("search_console_upstream_error")
        if not 200 <= response.status_code < 300:
            raise SearchConsoleError("search_console_http_error")

        try:
            payload = response.json()
        except ValueError as exc:
            raise SearchConsoleError("search_console_response_invalid") from exc
        if not isinstance(payload, dict):
            raise SearchConsoleError("search_console_response_invalid")
        typed_payload = cast(dict[str, object], payload)
        metrics = _parse_rows(typed_payload, canonical_url=page_url)

        raw_metrics: dict[str, object] = {
            "request": {
                "site_url": self._site_url,
                "canonical_url": page_url,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "dimensions": ["date"],
                "page_filter_operator": "equals",
            },
            "response": typed_payload,
        }
        return SearchConsoleAcquisition(
            raw_metrics=raw_metrics,
            metrics=metrics,
        )


__all__ = [
    "GoogleServiceAccountTokenProvider",
    "SearchConsoleAcquisition",
    "SearchConsoleConfig",
    "SearchConsoleError",
    "SearchConsoleGateway",
    "SearchConsoleTokenProvider",
]
