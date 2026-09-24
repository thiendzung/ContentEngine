"""Read-only ContentEngine client for the MOTGU Rank Math bridge."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from app.core.config import Settings

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
_POST_ID_RE = re.compile(r"^[1-9][0-9]*$")
_MODIFIED_GMT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_PAYLOAD_SCHEMA_VERSION = "1"
_MAX_RESPONSE_BYTES = 600 * 1024
_MAX_SAFE_DATA_BYTES = 512 * 1024
_MAX_SCHEMA_DEPTH = 12
_MAX_LINK_ITEMS = 1000
_WORDPRESS_STATUSES = {"draft", "publish", "future", "private", "pending"}

_ROUTE_CAPABILITIES = {
    "seo-meta": "rank-math/get-post-seo-meta",
    "schema": "rank-math/get-post-schema",
    "links": "rank-math/get-post-links",
}

_ENVELOPE_KEYS = {
    "payload_schema_version",
    "source",
    "upstream_source",
    "capability",
    "wordpress_post_id",
    "wordpress_url",
    "wordpress_modified_gmt",
    "wordpress_status",
    "rank_math_free_version",
    "rank_math_pro_version",
    "captured_at",
    "safe_data",
}

_SEO_META_KEYS = {
    "post_id",
    "title",
    "description",
    "focus_keyword",
    "robots",
    "canonical",
    "og_title",
    "og_description",
    "twitter_title",
    "twitter_description",
    "seo_score",
}

_SECRET_KEYS = {
    "access_token",
    "refresh_token",
    "auth_token",
    "id_token",
    "api_key",
    "apikey",
    "client_secret",
    "private_key",
    "secret",
    "password",
    "authorization",
    "cookie",
    "credential",
    "credentials",
}


class RankMathBridgeError(ValueError):
    """Stable fail-closed bridge error safe for logs and callers."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RankMathBridgeConfig:
    base_url: str
    secret: SecretStr
    timeout_seconds: float = 20.0


@dataclass(frozen=True, slots=True)
class RankMathInspection:
    payload_schema_version: str
    source: str
    upstream_source: str
    capability: str
    wordpress_post_id: str
    wordpress_url: str
    wordpress_modified_gmt: str
    wordpress_status: str
    rank_math_free_version: str
    rank_math_pro_version: str | None
    captured_at: datetime
    safe_data: dict[str, object]


def _validated_config(config: RankMathBridgeConfig) -> RankMathBridgeConfig:
    base_url = config.base_url.strip().rstrip("/")
    if not isinstance(config.secret, SecretStr):
        raise RankMathBridgeError("rank_math_bridge_configuration_incomplete")
    secret = config.secret.get_secret_value()
    if not base_url or len(secret) < 32:
        raise RankMathBridgeError("rank_math_bridge_configuration_incomplete")
    if config.timeout_seconds <= 0:
        raise RankMathBridgeError("rank_math_bridge_timeout_invalid")

    parsed = urlsplit(base_url)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise RankMathBridgeError("rank_math_bridge_base_url_invalid")
    if parsed.scheme != "https" and host not in _LOOPBACK_HOSTS:
        raise RankMathBridgeError("rank_math_bridge_https_required")

    return RankMathBridgeConfig(
        base_url=base_url,
        secret=SecretStr(secret),
        timeout_seconds=config.timeout_seconds,
    )


def _validate_post_id(value: str | int) -> str:
    if isinstance(value, bool):
        raise RankMathBridgeError("rank_math_bridge_post_id_invalid")
    normalized = str(value)
    if not _POST_ID_RE.fullmatch(normalized):
        raise RankMathBridgeError("rank_math_bridge_post_id_invalid")
    return normalized


def _text(value: object, *, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RankMathBridgeError(code)
    return value.strip()


def _nullable_text(value: object, *, code: str) -> str | None:
    if value is None:
        return None
    return _text(value, code=code)


def _validate_url(value: object) -> str:
    url = _text(value, code="rank_math_bridge_response_invalid")
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise RankMathBridgeError("rank_math_bridge_response_invalid")
    return url


def _validate_modified_gmt(value: object) -> str:
    raw = _text(value, code="rank_math_bridge_response_invalid")
    if not _MODIFIED_GMT_RE.fullmatch(raw):
        raise RankMathBridgeError("rank_math_bridge_response_invalid")
    try:
        datetime.fromisoformat(raw)
    except ValueError as exc:
        raise RankMathBridgeError("rank_math_bridge_response_invalid") from exc
    return raw


def _validate_captured_at(value: object) -> datetime:
    raw = _text(value, code="rank_math_bridge_response_invalid")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RankMathBridgeError("rank_math_bridge_response_invalid") from exc
    if parsed.tzinfo is None:
        raise RankMathBridgeError("rank_math_bridge_response_invalid")
    return parsed.astimezone(UTC)


def _is_sensitive_key(key: str) -> bool:
    return key.strip().lower().replace("-", "_") in _SECRET_KEYS


def _validate_json_value(value: object, *, depth: int = 0) -> object:
    if depth > _MAX_SCHEMA_DEPTH:
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
        return value
    if isinstance(value, list):
        return [_validate_json_value(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or _is_sensitive_key(key):
                raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
            result[key] = _validate_json_value(item, depth=depth + 1)
        return result
    raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")


def _validate_seo_meta(data: dict[str, object], post_id: str) -> dict[str, object]:
    if set(data) - _SEO_META_KEYS:
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
    if data.get("post_id") != int(post_id):
        raise RankMathBridgeError("rank_math_bridge_identity_mismatch")

    result: dict[str, object] = {"post_id": int(post_id)}
    for key in (
        "title",
        "description",
        "focus_keyword",
        "canonical",
        "og_title",
        "og_description",
        "twitter_title",
        "twitter_description",
    ):
        if key in data:
            value = data[key]
            if not isinstance(value, str):
                raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
            result[key] = value

    if "robots" in data:
        robots = data["robots"]
        if not isinstance(robots, list) or not all(isinstance(item, str) for item in robots):
            raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
        result["robots"] = list(robots)

    if "seo_score" in data:
        score = data["seo_score"]
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
            raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
        result["seo_score"] = score
    return result


def _validate_schema(data: dict[str, object], post_id: str) -> dict[str, object]:
    if set(data) != {"post_id", "schema_types", "schemas"}:
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
    if data.get("post_id") != int(post_id):
        raise RankMathBridgeError("rank_math_bridge_identity_mismatch")

    schema_types = data["schema_types"]
    schemas = data["schemas"]
    if (
        not isinstance(schema_types, list)
        or not all(isinstance(item, str) for item in schema_types)
        or not isinstance(schemas, list)
    ):
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")

    validated_schemas = [_validate_json_value(item) for item in schemas]
    return {
        "post_id": int(post_id),
        "schema_types": list(schema_types),
        "schemas": validated_schemas,
    }


def _validate_link_item(item: object, *, internal: bool) -> dict[str, object]:
    if not isinstance(item, dict):
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
    typed = cast(dict[str, object], item)
    allowed = {"url", "anchor", "dofollow"}
    if internal:
        allowed.add("target_post_id")
    if set(typed) - allowed or "url" not in typed:
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")

    result: dict[str, object] = {
        "url": _validate_url(typed["url"]),
    }
    anchor = typed.get("anchor")
    if anchor is not None and not isinstance(anchor, str):
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
    result["anchor"] = anchor

    dofollow = typed.get("dofollow")
    if dofollow is not None and not isinstance(dofollow, bool):
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
    result["dofollow"] = dofollow

    if internal:
        target = typed.get("target_post_id")
        if isinstance(target, bool) or not isinstance(target, int) or target <= 0:
            raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
        result["target_post_id"] = target
    return result


def _validate_links(data: dict[str, object], post_id: str) -> dict[str, object]:
    if set(data) != {"post_id", "internal", "external", "counts"}:
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
    if data.get("post_id") != int(post_id):
        raise RankMathBridgeError("rank_math_bridge_identity_mismatch")

    internal = data["internal"]
    external = data["external"]
    counts = data["counts"]
    if (
        not isinstance(internal, list)
        or not isinstance(external, list)
        or not isinstance(counts, dict)
    ):
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
    if len(internal) + len(external) > _MAX_LINK_ITEMS:
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")

    typed_counts = cast(dict[str, object], counts)
    if set(typed_counts) != {"internal", "external"}:
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
    expected_internal = len(internal)
    expected_external = len(external)
    if (
        typed_counts.get("internal") != expected_internal
        or typed_counts.get("external") != expected_external
    ):
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")

    return {
        "post_id": int(post_id),
        "internal": [_validate_link_item(item, internal=True) for item in internal],
        "external": [_validate_link_item(item, internal=False) for item in external],
        "counts": {
            "internal": expected_internal,
            "external": expected_external,
        },
    }


def _validate_safe_data(
    *,
    route_key: str,
    post_id: str,
    value: object,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RankMathBridgeError("rank_math_bridge_safe_data_invalid")
    data = cast(dict[str, object], value)
    if route_key == "seo-meta":
        result = _validate_seo_meta(data, post_id)
    elif route_key == "schema":
        result = _validate_schema(data, post_id)
    elif route_key == "links":
        result = _validate_links(data, post_id)
    else:
        raise RankMathBridgeError("rank_math_bridge_capability_invalid")

    encoded = json.dumps(result, separators=(",", ":"), ensure_ascii=False).encode()
    if len(encoded) > _MAX_SAFE_DATA_BYTES:
        raise RankMathBridgeError("rank_math_bridge_safe_data_too_large")
    return result


def _parse_inspection(
    *,
    payload: object,
    route_key: str,
    post_id: str,
) -> RankMathInspection:
    if not isinstance(payload, dict):
        raise RankMathBridgeError("rank_math_bridge_response_invalid")
    data = cast(dict[str, object], payload)
    if set(data) != _ENVELOPE_KEYS:
        raise RankMathBridgeError("rank_math_bridge_response_invalid")

    schema_version = _text(
        data["payload_schema_version"],
        code="rank_math_bridge_response_invalid",
    )
    if schema_version != _PAYLOAD_SCHEMA_VERSION:
        raise RankMathBridgeError("rank_math_bridge_schema_version_unsupported")
    if data["source"] != "rank_math" or data["upstream_source"] != "rank_math_native":
        raise RankMathBridgeError("rank_math_bridge_provenance_mismatch")

    expected_capability = _ROUTE_CAPABILITIES[route_key]
    if data["capability"] != expected_capability:
        raise RankMathBridgeError("rank_math_bridge_capability_mismatch")

    observed_post_id = _text(
        data["wordpress_post_id"],
        code="rank_math_bridge_response_invalid",
    )
    if observed_post_id != post_id:
        raise RankMathBridgeError("rank_math_bridge_identity_mismatch")

    status = _text(data["wordpress_status"], code="rank_math_bridge_response_invalid")
    if status not in _WORDPRESS_STATUSES:
        raise RankMathBridgeError("rank_math_bridge_response_invalid")

    free_version = _text(
        data["rank_math_free_version"],
        code="rank_math_bridge_response_invalid",
    )
    pro_version = _nullable_text(
        data["rank_math_pro_version"],
        code="rank_math_bridge_response_invalid",
    )

    return RankMathInspection(
        payload_schema_version=schema_version,
        source="rank_math",
        upstream_source="rank_math_native",
        capability=expected_capability,
        wordpress_post_id=post_id,
        wordpress_url=_validate_url(data["wordpress_url"]),
        wordpress_modified_gmt=_validate_modified_gmt(data["wordpress_modified_gmt"]),
        wordpress_status=status,
        rank_math_free_version=free_version,
        rank_math_pro_version=pro_version,
        captured_at=_validate_captured_at(data["captured_at"]),
        safe_data=_validate_safe_data(
            route_key=route_key,
            post_id=post_id,
            value=data["safe_data"],
        ),
    )


class RankMathBridgeGateway:
    """Bounded GET-only client for the MOTGU-owned WordPress bridge."""

    def __init__(
        self,
        config: RankMathBridgeConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._config = _validated_config(config)
        self._clock = clock
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._config.timeout_seconds),
            follow_redirects=False,
            transport=transport,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.time,
    ) -> "RankMathBridgeGateway":
        secret = (
            settings.rank_math_bridge_secret.get_secret_value()
            if settings.rank_math_bridge_secret is not None
            else ""
        )
        return cls(
            RankMathBridgeConfig(
                base_url=settings.rank_math_bridge_base_url or "",
                secret=SecretStr(secret),
                timeout_seconds=settings.rank_math_bridge_request_timeout_seconds,
            ),
            transport=transport,
            clock=clock,
        )

    async def __aenter__(self) -> "RankMathBridgeGateway":
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

    async def get_post_seo_meta(self, post_id: str | int) -> RankMathInspection:
        return await self._get_inspection(post_id=post_id, route_key="seo-meta")

    async def get_post_schema(self, post_id: str | int) -> RankMathInspection:
        return await self._get_inspection(post_id=post_id, route_key="schema")

    async def get_post_links(self, post_id: str | int) -> RankMathInspection:
        return await self._get_inspection(post_id=post_id, route_key="links")

    async def _get_inspection(
        self,
        *,
        post_id: str | int,
        route_key: str,
    ) -> RankMathInspection:
        normalized_post_id = _validate_post_id(post_id)
        if route_key not in _ROUTE_CAPABILITIES:
            raise RankMathBridgeError("rank_math_bridge_capability_invalid")

        route = (
            f"/motgu-contentengine/v1/rank-math/posts/"
            f"{normalized_post_id}/{route_key}"
        )
        timestamp = str(int(self._clock()))
        message = f"GET\n{route}\n{timestamp}".encode()
        signature = hmac.new(
            self._config.secret.get_secret_value().encode(),
            message,
            hashlib.sha256,
        ).hexdigest()
        url = f"{self._config.base_url}/wp-json{route}"

        headers = {
            "X-MOTGU-Bridge-Timestamp": timestamp,
            "X-MOTGU-Bridge-Signature": signature,
            "Cache-Control": "no-store",
        }
        try:
            async with self._client.stream("GET", url, headers=headers) as response:
                if response.status_code == 401:
                    raise RankMathBridgeError("rank_math_bridge_unauthorized")
                if response.status_code == 403:
                    raise RankMathBridgeError("rank_math_bridge_forbidden")
                if response.status_code == 404:
                    raise RankMathBridgeError("rank_math_bridge_not_found")
                if response.status_code == 429:
                    raise RankMathBridgeError("rank_math_bridge_rate_limited")
                if 300 <= response.status_code <= 399:
                    raise RankMathBridgeError("rank_math_bridge_redirect_rejected")
                if 500 <= response.status_code <= 599:
                    raise RankMathBridgeError("rank_math_bridge_upstream_error")
                if not 200 <= response.status_code < 300:
                    raise RankMathBridgeError("rank_math_bridge_http_error")

                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        declared_length = int(content_length)
                    except ValueError as exc:
                        raise RankMathBridgeError(
                            "rank_math_bridge_response_invalid"
                        ) from exc
                    if declared_length < 0 or declared_length > _MAX_RESPONSE_BYTES:
                        raise RankMathBridgeError("rank_math_bridge_response_too_large")

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > _MAX_RESPONSE_BYTES:
                        raise RankMathBridgeError("rank_math_bridge_response_too_large")
        except RankMathBridgeError:
            raise
        except httpx.HTTPError as exc:
            raise RankMathBridgeError("rank_math_bridge_transport_error") from exc

        try:
            payload = json.loads(bytes(body))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RankMathBridgeError("rank_math_bridge_response_invalid") from exc

        return _parse_inspection(
            payload=payload,
            route_key=route_key,
            post_id=normalized_post_id,
        )


__all__ = [
    "RankMathBridgeConfig",
    "RankMathBridgeError",
    "RankMathBridgeGateway",
    "RankMathInspection",
]