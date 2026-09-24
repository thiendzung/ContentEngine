from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.publishing.rank_math_gateway import (
    RankMathBridgeConfig,
    RankMathBridgeError,
    RankMathBridgeGateway,
)


def _config() -> RankMathBridgeConfig:
    return RankMathBridgeConfig(
        base_url="https://motgu.example",
        secret=SecretStr("a" * 64),
        timeout_seconds=5.0,
    )


def _envelope(
    *,
    route_key: str,
    post_id: int = 42,
    safe_data: dict[str, object] | None = None,
) -> dict[str, object]:
    capabilities = {
        "seo-meta": "rank-math/get-post-seo-meta",
        "schema": "rank-math/get-post-schema",
        "links": "rank-math/get-post-links",
    }
    if safe_data is None:
        if route_key == "seo-meta":
            safe_data = {
                "post_id": post_id,
                "title": "SEO title",
                "description": "Description",
                "focus_keyword": "oil painting",
                "robots": ["index", "follow"],
                "canonical": f"https://motgu.example/?p={post_id}",
                "seo_score": 84,
            }
        elif route_key == "schema":
            safe_data = {
                "post_id": post_id,
                "schema_types": ["Article"],
                "schemas": [
                    {
                        "@type": "Article",
                        "headline": "Certificate of Authenticity",
                    }
                ],
            }
        else:
            safe_data = {
                "post_id": post_id,
                "internal": [
                    {
                        "url": "https://motgu.example/artwork/",
                        "anchor": "Artwork",
                        "dofollow": True,
                        "target_post_id": 9,
                    }
                ],
                "external": [],
                "counts": {"internal": 1, "external": 0},
            }
    return {
        "payload_schema_version": "1",
        "source": "rank_math",
        "upstream_source": "rank_math_native",
        "capability": capabilities[route_key],
        "wordpress_post_id": str(post_id),
        "wordpress_url": f"https://motgu.example/?p={post_id}",
        "wordpress_modified_gmt": "2026-09-24T06:00:00",
        "wordpress_status": "publish",
        "rank_math_free_version": "1.0.279",
        "rank_math_pro_version": "3.0.119",
        "captured_at": "2026-09-24T06:30:00+00:00",
        "safe_data": safe_data,
    }


@pytest.mark.asyncio
async def test_rank_math_gateway_signs_exact_get_route_and_parses_seo_meta() -> None:
    seen: list[httpx.Request] = []
    clock_value = 1_790_228_200
    route = "/motgu-contentengine/v1/rank-math/posts/42/seo-meta"
    expected_signature = hmac.new(
        ("a" * 64).encode(),
        f"GET\n{route}\n{clock_value}".encode(),
        hashlib.sha256,
    ).hexdigest()

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "GET"
        assert request.url.path == f"/wp-json{route}"
        assert request.headers["x-motgu-bridge-timestamp"] == str(clock_value)
        assert request.headers["x-motgu-bridge-signature"] == expected_signature
        assert request.headers["cache-control"] == "no-store"
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            json=_envelope(route_key="seo-meta"),
            request=request,
        )

    async with RankMathBridgeGateway(
        _config(),
        transport=httpx.MockTransport(handler),
        clock=lambda: float(clock_value),
    ) as gateway:
        result = await gateway.get_post_seo_meta("42")

    assert len(seen) == 1
    assert result.source == "rank_math"
    assert result.upstream_source == "rank_math_native"
    assert result.capability == "rank-math/get-post-seo-meta"
    assert result.wordpress_post_id == "42"
    assert result.wordpress_modified_gmt == "2026-09-24T06:00:00"
    assert result.rank_math_free_version == "1.0.279"
    assert result.rank_math_pro_version == "3.0.119"
    assert result.captured_at == datetime(2026, 9, 24, 6, 30, tzinfo=UTC)
    assert result.safe_data["post_id"] == 42
    assert "a" * 64 not in json.dumps(result.safe_data)


@pytest.mark.asyncio
async def test_rank_math_gateway_supports_schema_and_links_fixed_routes() -> None:
    observed: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request.url.path)
        route_key = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(
            200,
            json=_envelope(route_key=route_key),
            request=request,
        )

    async with RankMathBridgeGateway(
        _config(),
        transport=httpx.MockTransport(handler),
        clock=lambda: 1_790_228_200.0,
    ) as gateway:
        schema = await gateway.get_post_schema(42)
        links = await gateway.get_post_links(42)

    assert observed == [
        "/wp-json/motgu-contentengine/v1/rank-math/posts/42/schema",
        "/wp-json/motgu-contentengine/v1/rank-math/posts/42/links",
    ]
    assert schema.capability == "rank-math/get-post-schema"
    assert schema.safe_data["schema_types"] == ["Article"]
    assert links.capability == "rank-math/get-post-links"
    assert links.safe_data["counts"] == {"internal": 1, "external": 0}


@pytest.mark.asyncio
async def test_rank_math_gateway_rejects_incomplete_or_insecure_configuration() -> None:
    with pytest.raises(
        RankMathBridgeError,
        match="rank_math_bridge_configuration_incomplete",
    ):
        RankMathBridgeGateway(
            RankMathBridgeConfig(
                base_url="https://motgu.example",
                secret=SecretStr("short"),
            )
        )

    with pytest.raises(RankMathBridgeError, match="rank_math_bridge_https_required"):
        RankMathBridgeGateway(
            RankMathBridgeConfig(
                base_url="http://motgu.example",
                secret=SecretStr("a" * 64),
            )
        )

    async with RankMathBridgeGateway(
        RankMathBridgeConfig(
            base_url="http://127.0.0.1:8080",
            secret=SecretStr("a" * 64),
        )
    ) as gateway:
        assert gateway is not None


def test_rank_math_gateway_config_repr_does_not_expose_secret() -> None:
    config = _config()
    assert "a" * 64 not in repr(config)

    with pytest.raises(
        RankMathBridgeError,
        match="rank_math_bridge_configuration_incomplete",
    ):
        RankMathBridgeGateway(
            RankMathBridgeConfig(
                base_url="https://motgu.example",
                secret="a" * 64,  # type: ignore[arg-type]
            )
        )


@pytest.mark.asyncio
async def test_rank_math_gateway_from_settings_uses_secretstr() -> None:
    settings = Settings(
        _env_file=None,
        rank_math_bridge_base_url="https://motgu.example",
        rank_math_bridge_secret=SecretStr("b" * 64),
        rank_math_bridge_request_timeout_seconds=7.0,
    )
    async with RankMathBridgeGateway.from_settings(settings) as gateway:
        assert gateway is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (301, "rank_math_bridge_redirect_rejected"),
        (401, "rank_math_bridge_unauthorized"),
        (403, "rank_math_bridge_forbidden"),
        (404, "rank_math_bridge_not_found"),
        (429, "rank_math_bridge_rate_limited"),
        (503, "rank_math_bridge_upstream_error"),
        (418, "rank_math_bridge_http_error"),
    ],
)
async def test_rank_math_gateway_http_failures_are_stable(
    status: int,
    code: str,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"code": "redacted"}, request=request)

    async with RankMathBridgeGateway(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as gateway:
        with pytest.raises(RankMathBridgeError, match=code) as exc_info:
            await gateway.get_post_seo_meta(42)

    assert exc_info.value.code == code


@pytest.mark.asyncio
async def test_rank_math_gateway_rejects_identity_capability_and_provenance_drift() -> None:
    payloads = [
        (
            {**_envelope(route_key="seo-meta"), "wordpress_post_id": "43"},
            "rank_math_bridge_identity_mismatch",
        ),
        (
            {
                **_envelope(route_key="seo-meta"),
                "capability": "rank-math/get-post-schema",
            },
            "rank_math_bridge_capability_mismatch",
        ),
        (
            {**_envelope(route_key="seo-meta"), "source": "wordpress"},
            "rank_math_bridge_provenance_mismatch",
        ),
        (
            {**_envelope(route_key="seo-meta"), "payload_schema_version": "2"},
            "rank_math_bridge_schema_version_unsupported",
        ),
    ]

    for payload, expected_code in payloads:
        async def handler(
            request: httpx.Request,
            response_payload: dict[str, object] = payload,
        ) -> httpx.Response:
            return httpx.Response(200, json=response_payload, request=request)

        async with RankMathBridgeGateway(
            _config(),
            transport=httpx.MockTransport(handler),
        ) as gateway:
            with pytest.raises(RankMathBridgeError, match=expected_code):
                await gateway.get_post_seo_meta(42)


@pytest.mark.asyncio
async def test_rank_math_gateway_rejects_unknown_or_sensitive_safe_data() -> None:
    payloads = [
        _envelope(
            route_key="seo-meta",
            safe_data={
                "post_id": 42,
                "title": "Title",
                "access_token": "must-not-pass",
            },
        ),
        _envelope(
            route_key="schema",
            safe_data={
                "post_id": 42,
                "schema_types": ["Article"],
                "schemas": [
                    {
                        "@type": "Article",
                        "client_secret": "must-not-pass",
                    }
                ],
            },
        ),
        _envelope(
            route_key="links",
            safe_data={
                "post_id": 42,
                "internal": [],
                "external": [],
                "counts": {"internal": 1, "external": 0},
            },
        ),
    ]

    for payload in payloads:
        async def handler(
            request: httpx.Request,
            response_payload: dict[str, object] = payload,
        ) -> httpx.Response:
            return httpx.Response(200, json=response_payload, request=request)

        async with RankMathBridgeGateway(
            _config(),
            transport=httpx.MockTransport(handler),
        ) as gateway:
            capability = payload["capability"]
            with pytest.raises(
                RankMathBridgeError,
                match="rank_math_bridge_safe_data_invalid",
            ):
                if capability == "rank-math/get-post-seo-meta":
                    await gateway.get_post_seo_meta(42)
                elif capability == "rank-math/get-post-schema":
                    await gateway.get_post_schema(42)
                else:
                    await gateway.get_post_links(42)


@pytest.mark.asyncio
async def test_rank_math_gateway_does_not_retry_upstream_failure() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"code": "upstream"}, request=request)

    async with RankMathBridgeGateway(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as gateway:
        with pytest.raises(
            RankMathBridgeError,
            match="rank_math_bridge_upstream_error",
        ):
            await gateway.get_post_seo_meta(42)

    assert calls == 1


@pytest.mark.asyncio
async def test_rank_math_gateway_rejects_non_finite_schema_value() -> None:
    payload = _envelope(
        route_key="schema",
        safe_data={
            "post_id": 42,
            "schema_types": ["Article"],
            "schemas": [{"@type": "Article", "ratingValue": float("nan")}],
        },
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    async with RankMathBridgeGateway(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as gateway:
        with pytest.raises(
            RankMathBridgeError,
            match="rank_math_bridge_safe_data_invalid",
        ):
            await gateway.get_post_schema(42)


@pytest.mark.asyncio
async def test_rank_math_gateway_rejects_oversized_response_before_parsing() -> None:
    oversized = b"x" * (600 * 1024 + 1)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=oversized, request=request)

    async with RankMathBridgeGateway(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as gateway:
        with pytest.raises(
            RankMathBridgeError,
            match="rank_math_bridge_response_too_large",
        ):
            await gateway.get_post_seo_meta(42)


@pytest.mark.asyncio
async def test_rank_math_gateway_rejects_invalid_post_id_before_transport() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={}, request=request)

    async with RankMathBridgeGateway(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as gateway:
        for value in (0, -1, "01", "abc", True):
            with pytest.raises(
                RankMathBridgeError,
                match="rank_math_bridge_post_id_invalid",
            ):
                await gateway.get_post_seo_meta(value)

    assert calls == 0