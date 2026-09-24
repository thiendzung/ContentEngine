from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.modules.publishing.service import WordPressWriteRequest
from app.modules.publishing.wordpress_gateway import (
    WordPressGatewayConfigError,
    WordPressRestConfig,
    WordPressRestGateway,
)


def _request(
    *,
    action: str = "draft",
    external_id: str | None = None,
    external_revision: str | None = None,
) -> WordPressWriteRequest:
    assert action in {"draft", "publish"}
    return WordPressWriteRequest(
        idempotency_key="pm01:" + "a" * 64,
        action=action,  # type: ignore[arg-type]
        slug="certificate-of-authenticity",
        title="What a Certificate of Authenticity Actually Proves",
        body_markdown=(
            "Start with the claim, not the paper.\n\n"
            "## What it can prove\n\n"
            "**Check** the issuer and scope.\n\n"
            "<script>alert('x')</script>"
        ),
        excerpt="A practical guide to reading a certificate of authenticity.",
        locale="en",
        content_type="journal",
        metadata={"contentengine": {"content_item_id": "item-1"}},
        expected_external_id=external_id,
        expected_external_revision_id=external_revision,
    )


def _config() -> WordPressRestConfig:
    return WordPressRestConfig(
        base_url="https://motgu.example",
        username="publisher",
        application_password="application-password",
        timeout_seconds=5.0,
    )


def _post_payload(
    request: WordPressWriteRequest,
    *,
    external_id: int = 42,
    status: str | None = None,
    marker: bool = True,
    modified_gmt: str = "2026-09-24T01:30:00",
) -> dict[str, object]:
    content = "<p>Rendered</p>"
    if marker:
        content += (
            f"\n<!-- contentengine-idempotency:{request.idempotency_key} -->"
        )
    return {
        "id": external_id,
        "slug": request.slug,
        "status": status or request.action,
        "link": f"https://motgu.example/?p={external_id}",
        "modified_gmt": modified_gmt,
        "date_gmt": "2026-09-24T01:00:00",
        "content": {"raw": content},
    }


def test_wordpress_gateway_rejects_incomplete_or_insecure_configuration() -> None:
    with pytest.raises(
        WordPressGatewayConfigError,
        match="wordpress_configuration_incomplete",
    ):
        WordPressRestGateway(
            WordPressRestConfig(
                base_url="",
                username="publisher",
                application_password="secret",
            )
        )

    with pytest.raises(
        WordPressGatewayConfigError,
        match="wordpress_https_required",
    ):
        WordPressRestGateway(
            WordPressRestConfig(
                base_url="http://motgu.example",
                username="publisher",
                application_password="secret",
            )
        )


@pytest.mark.asyncio
async def test_wordpress_execute_create_renders_sanitized_html_and_marker() -> None:
    request = _request()
    seen: list[httpx.Request] = []

    async def handler(http_request: httpx.Request) -> httpx.Response:
        seen.append(http_request)
        payload = json.loads(http_request.content.decode("utf-8"))
        assert http_request.method == "POST"
        assert http_request.url.path == "/wp-json/wp/v2/posts"
        assert http_request.headers["idempotency-key"] == request.idempotency_key
        assert http_request.headers["authorization"].startswith("Basic ")
        assert payload["status"] == "draft"
        assert payload["slug"] == request.slug
        assert "<h2>What it can prove</h2>" in payload["content"]
        assert "<strong>Check</strong>" in payload["content"]
        assert "<script>" not in payload["content"]
        assert (
            f"<!-- contentengine-idempotency:{request.idempotency_key} -->"
            in payload["content"]
        )
        return httpx.Response(
            201,
            json=_post_payload(request),
            request=http_request,
        )

    transport = httpx.MockTransport(handler)
    async with WordPressRestGateway(_config(), transport=transport) as gateway:
        result = await gateway.execute(request)

    assert len(seen) == 1
    assert result.outcome == "confirmed_success"
    assert result.external_id == "42"
    assert result.external_status == "draft"
    assert result.external_revision_id == "2026-09-24T01:30:00"
    assert result.published_at is None


@pytest.mark.asyncio
async def test_wordpress_update_fails_closed_before_write_on_revision_drift() -> None:
    request = _request(
        external_id="42",
        external_revision="2026-09-24T01:00:00",
    )
    methods: list[str] = []

    async def handler(http_request: httpx.Request) -> httpx.Response:
        methods.append(http_request.method)
        assert http_request.method == "GET"
        return httpx.Response(
            200,
            json=_post_payload(
                request,
                modified_gmt="2026-09-24T01:45:00",
            ),
            request=http_request,
        )

    async with WordPressRestGateway(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as gateway:
        result = await gateway.execute(request)

    assert methods == ["GET"]
    assert result.outcome == "unknown"
    assert result.message == "wordpress_external_revision_mismatch"


@pytest.mark.asyncio
async def test_wordpress_execute_ambiguous_http_result_returns_unknown() -> None:
    request = _request()

    async def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable", request=http_request)

    async with WordPressRestGateway(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as gateway:
        result = await gateway.execute(request)

    assert result.outcome == "unknown"
    assert result.message == "wordpress_http_503"


@pytest.mark.asyncio
async def test_wordpress_reconcile_by_slug_requires_exact_contentengine_marker() -> None:
    request = _request(action="publish")

    async def success_handler(http_request: httpx.Request) -> httpx.Response:
        assert http_request.method == "GET"
        assert http_request.url.path == "/wp-json/wp/v2/posts"
        return httpx.Response(
            200,
            json=[_post_payload(request, status="publish")],
            request=http_request,
        )

    async with WordPressRestGateway(
        _config(),
        transport=httpx.MockTransport(success_handler),
    ) as gateway:
        success = await gateway.reconcile(request)

    assert success.outcome == "confirmed_success"
    assert success.external_id == "42"
    assert success.external_status == "publish"
    assert success.published_at == datetime(2026, 9, 24, 1, 0, tzinfo=UTC)

    async def conflict_handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[_post_payload(request, status="publish", marker=False)],
            request=http_request,
        )

    async with WordPressRestGateway(
        _config(),
        transport=httpx.MockTransport(conflict_handler),
    ) as gateway:
        conflict = await gateway.reconcile(request)

    assert conflict.outcome == "conflict"
    assert conflict.message == "wordpress_reconciliation_slug_conflict"


@pytest.mark.asyncio
async def test_wordpress_reconcile_exact_id_distinguishes_absent() -> None:
    request = _request(
        external_id="42",
        external_revision="2026-09-24T01:30:00",
    )

    async def handler(http_request: httpx.Request) -> httpx.Response:
        assert http_request.url.path == "/wp-json/wp/v2/posts/42"
        return httpx.Response(404, json={"code": "rest_post_invalid_id"}, request=http_request)

    async with WordPressRestGateway(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as gateway:
        result = await gateway.reconcile(request)

    assert result.outcome == "confirmed_absent"
