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