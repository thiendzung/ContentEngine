"""Concrete fail-closed WordPress REST transport for PM-01."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self, cast
from urllib.parse import urlsplit

import bleach  # type: ignore[import-untyped]
import httpx
import markdown  # type: ignore[import-untyped]

from app.core.config import Settings
from app.modules.publishing.service import (
    WordPressReconciliation,
    WordPressWriteRequest,
    WordPressWriteResult,
)

_ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h2",
    "h3",
    "h4",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}
_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel"],
}
_ALLOWED_PROTOCOLS = {"http", "https", "mailto"}
_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9:._-]{1,200}$")
_EXTERNAL_ID_RE = re.compile(r"^[1-9][0-9]*$")
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
_WORDPRESS_STATUSES = ("draft", "publish", "future", "private", "pending")


class WordPressGatewayConfigError(ValueError):
    """Raised when the concrete WordPress transport cannot be configured safely."""


@dataclass(frozen=True, slots=True)
class WordPressRestConfig:
    base_url: str
    username: str
    application_password: str
    timeout_seconds: float = 20.0


def _validated_config(config: WordPressRestConfig) -> WordPressRestConfig:
    base_url = config.base_url.strip().rstrip("/")
    username = config.username.strip()
    password = config.application_password.strip()
    if not base_url or not username or not password:
        raise WordPressGatewayConfigError("wordpress_configuration_incomplete")
    if config.timeout_seconds <= 0:
        raise WordPressGatewayConfigError("wordpress_timeout_invalid")

    parsed = urlsplit(base_url)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise WordPressGatewayConfigError("wordpress_base_url_invalid")
    if parsed.scheme != "https" and host not in _LOOPBACK_HOSTS:
        raise WordPressGatewayConfigError("wordpress_https_required")

    return WordPressRestConfig(
        base_url=base_url,
        username=username,
        application_password=password,
        timeout_seconds=config.timeout_seconds,
    )


def _render_markdown(body_markdown: str) -> str:
    rendered = markdown.markdown(
        body_markdown,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )
    return bleach.clean(
        rendered,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )


def _marker(request: WordPressWriteRequest) -> str:
    if not _IDEMPOTENCY_RE.fullmatch(request.idempotency_key):
        raise WordPressGatewayConfigError("wordpress_idempotency_key_invalid")
    return f"<!-- contentengine-idempotency:{request.idempotency_key} -->"


def _parse_gmt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _post_content_raw(post: dict[str, object]) -> str | None:
    content = post.get("content")
    if not isinstance(content, dict):
        return None
    typed_content = cast(dict[str, object], content)
    raw = typed_content.get("raw")
    return raw if isinstance(raw, str) else None


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


class WordPressRestGateway:
    """WordPress REST implementation with deterministic reconciliation markers."""

    def __init__(
        self,
        config: WordPressRestConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = _validated_config(config)
        self._posts_url = f"{self._config.base_url}/wp-json/wp/v2/posts"
        self._client = httpx.AsyncClient(
            auth=httpx.BasicAuth(
                self._config.username,
                self._config.application_password,
            ),
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
    ) -> Self:
        password = (
            settings.wordpress_application_password.get_secret_value()
            if settings.wordpress_application_password is not None
            else ""
        )
        return cls(
            WordPressRestConfig(
                base_url=settings.wordpress_base_url or "",
                username=settings.wordpress_username or "",
                application_password=password,
                timeout_seconds=settings.wordpress_request_timeout_seconds,
            ),
            transport=transport,
        )

    async def __aenter__(self) -> Self:
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

    async def _get(
        self,
        url: str,
        *,
        params: list[tuple[str, str | int | float | bool | None]] | None = None,
    ) -> httpx.Response | None:
        try:
            return await self._client.get(url, params=params)
        except httpx.HTTPError:
            return None

    async def _post(
        self,
        url: str,
        *,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> httpx.Response | None:
        try:
            return await self._client.post(
                url,
                json=payload,
                headers={"Idempotency-Key": idempotency_key},
            )
        except httpx.HTTPError:
            return None

    def _write_payload(self, request: WordPressWriteRequest) -> dict[str, object]:
        marker = _marker(request)
        body_html = _render_markdown(request.body_markdown)
        content = f"{body_html}\n{marker}" if body_html else marker
        return {
            "slug": request.slug,
            "title": request.title,
            "content": content,
            "excerpt": request.excerpt,
            "status": request.action,
        }

    async def _precondition_update(
        self,
        request: WordPressWriteRequest,
    ) -> WordPressWriteResult | None:
        external_id = request.expected_external_id
        if external_id is None:
            return None
        if not _EXTERNAL_ID_RE.fullmatch(external_id):
            return WordPressWriteResult(
                outcome="unknown",
                message="wordpress_external_id_invalid",
            )

        response = await self._get(
            f"{self._posts_url}/{external_id}",
            params=[("context", "edit")],
        )
        if response is None:
            return WordPressWriteResult(
                outcome="unknown",
                message="wordpress_update_precondition_transport_unknown",
            )
        if response.status_code == 404:
            return WordPressWriteResult(
                outcome="unknown",
                message="wordpress_expected_post_absent",
            )
        if not 200 <= response.status_code < 300:
            return WordPressWriteResult(
                outcome="unknown",
                message=f"wordpress_update_precondition_http_{response.status_code}",
            )
        try:
            post = response.json()
        except ValueError:
            return WordPressWriteResult(
                outcome="unknown",
                message="wordpress_update_precondition_response_invalid",
            )
        if not isinstance(post, dict):
            return WordPressWriteResult(
                outcome="unknown",
                message="wordpress_update_precondition_response_invalid",
            )
        observed_id = _text(post.get("id"))
        if observed_id != external_id:
            return WordPressWriteResult(
                outcome="unknown",
                message="wordpress_update_precondition_identity_mismatch",
            )

        expected_revision = request.expected_external_revision_id
        if expected_revision is not None:
            observed_revision = _text(post.get("modified_gmt"))
            if observed_revision != expected_revision:
                return WordPressWriteResult(
                    outcome="unknown",
                    message="wordpress_external_revision_mismatch",
                )
        return None

    def _success_from_post(
        self,
        post: dict[str, object],
        *,
        request: WordPressWriteRequest,
        require_marker: bool,
    ) -> WordPressWriteResult | None:
        external_id = _text(post.get("id"))
        slug = _text(post.get("slug"))
        status = _text(post.get("status"))
        link = _text(post.get("link"))
        revision = _text(post.get("modified_gmt"))
        if (
            external_id is None
            or not _EXTERNAL_ID_RE.fullmatch(external_id)
            or slug != request.slug
            or status != request.action
            or link is None
            or revision is None
        ):
            return None
        if (
            request.expected_external_id is not None
            and external_id != request.expected_external_id
        ):
            return None
        if require_marker:
            raw = _post_content_raw(post)
            if raw is None or _marker(request) not in raw:
                return None

        published_at = _parse_gmt(post.get("date_gmt")) if status == "publish" else None
        if status == "publish" and published_at is None:
            return None
        return WordPressWriteResult(
            outcome="confirmed_success",
            external_id=external_id,
            canonical_url=link,
            external_revision_id=revision,
            external_status=status,
            published_at=published_at,
        )

    async def execute(self, request: WordPressWriteRequest) -> WordPressWriteResult:
        precondition = await self._precondition_update(request)
        if precondition is not None:
            return precondition

        target = self._posts_url
        if request.expected_external_id is not None:
            target = f"{target}/{request.expected_external_id}"

        response = await self._post(
            target,
            payload=self._write_payload(request),
            idempotency_key=request.idempotency_key,
        )
        if response is None:
            return WordPressWriteResult(
                outcome="unknown",
                message="wordpress_transport_unknown",
            )
        if not 200 <= response.status_code < 300:
            return WordPressWriteResult(
                outcome="unknown",
                message=f"wordpress_http_{response.status_code}",
            )
        try:
            payload = response.json()
        except ValueError:
            return WordPressWriteResult(
                outcome="unknown",
                message="wordpress_response_invalid",
            )
        if not isinstance(payload, dict):
            return WordPressWriteResult(
                outcome="unknown",
                message="wordpress_response_invalid",
            )
        result = self._success_from_post(
            payload,
            request=request,
            require_marker=False,
        )
        if result is None:
            return WordPressWriteResult(
                outcome="unknown",
                message="wordpress_response_binding_invalid",
            )
        return result

    def _reconciliation_success(
        self,
        post: dict[str, object],
        *,
        request: WordPressWriteRequest,
    ) -> WordPressReconciliation:
        raw = _post_content_raw(post)
        if raw is None or _marker(request) not in raw:
            return WordPressReconciliation(
                outcome="conflict",
                message="wordpress_reconciliation_marker_mismatch",
            )
        result = self._success_from_post(
            post,
            request=request,
            require_marker=True,
        )
        if result is None:
            return WordPressReconciliation(
                outcome="conflict",
                message="wordpress_reconciliation_state_mismatch",
            )
        return WordPressReconciliation(
            outcome="confirmed_success",
            external_id=result.external_id,
            canonical_url=result.canonical_url,
            external_revision_id=result.external_revision_id,
            external_status=result.external_status,
            published_at=result.published_at,
        )

    async def reconcile(
        self,
        request: WordPressWriteRequest,
    ) -> WordPressReconciliation:
        if request.expected_external_id is not None:
            external_id = request.expected_external_id
            if not _EXTERNAL_ID_RE.fullmatch(external_id):
                return WordPressReconciliation(
                    outcome="conflict",
                    message="wordpress_external_id_invalid",
                )
            response = await self._get(
                f"{self._posts_url}/{external_id}",
                params=[("context", "edit")],
            )
            if response is None:
                return WordPressReconciliation(
                    outcome="unknown",
                    message="wordpress_reconciliation_transport_unknown",
                )
            if response.status_code == 404:
                return WordPressReconciliation(outcome="confirmed_absent")
            if not 200 <= response.status_code < 300:
                return WordPressReconciliation(
                    outcome="unknown",
                    message=f"wordpress_reconciliation_http_{response.status_code}",
                )
            try:
                payload = response.json()
            except ValueError:
                return WordPressReconciliation(
                    outcome="unknown",
                    message="wordpress_reconciliation_response_invalid",
                )
            if not isinstance(payload, dict):
                return WordPressReconciliation(
                    outcome="unknown",
                    message="wordpress_reconciliation_response_invalid",
                )
            if _text(payload.get("id")) != external_id:
                return WordPressReconciliation(
                    outcome="conflict",
                    message="wordpress_reconciliation_identity_mismatch",
                )
            return self._reconciliation_success(payload, request=request)

        params: list[tuple[str, str | int | float | bool | None]] = [
            ("context", "edit"),
            ("slug", request.slug),
            ("per_page", "10"),
        ]
        params.extend(("status[]", status) for status in _WORDPRESS_STATUSES)
        response = await self._get(self._posts_url, params=params)
        if response is None:
            return WordPressReconciliation(
                outcome="unknown",
                message="wordpress_reconciliation_transport_unknown",
            )
        if not 200 <= response.status_code < 300:
            return WordPressReconciliation(
                outcome="unknown",
                message=f"wordpress_reconciliation_http_{response.status_code}",
            )
        try:
            payload = response.json()
        except ValueError:
            return WordPressReconciliation(
                outcome="unknown",
                message="wordpress_reconciliation_response_invalid",
            )
        if not isinstance(payload, list):
            return WordPressReconciliation(
                outcome="unknown",
                message="wordpress_reconciliation_response_invalid",
            )
        candidates = [
            post
            for post in payload
            if isinstance(post, dict) and _text(post.get("slug")) == request.slug
        ]
        if not candidates:
            return WordPressReconciliation(outcome="confirmed_absent")

        marker = _marker(request)
        marker_matches = [
            post
            for post in candidates
            if (raw := _post_content_raw(post)) is not None and marker in raw
        ]
        if len(marker_matches) != 1 or len(candidates) != 1:
            return WordPressReconciliation(
                outcome="conflict",
                message="wordpress_reconciliation_slug_conflict",
            )
        return self._reconciliation_success(marker_matches[0], request=request)


__all__ = [
    "WordPressGatewayConfigError",
    "WordPressRestConfig",
    "WordPressRestGateway",
]