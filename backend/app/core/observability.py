"""Safe operational logging and HTTP correlation for ContentEngine.

This module intentionally logs identifiers, states, timings and error classes only.
Request bodies, prompts, provider payloads, secrets and chain-of-thought are not log fields.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from time import perf_counter
from typing import Final, TextIO
from uuid import uuid4

from fastapi import Request, Response

from app.core.config import Settings

_REQUEST_ID: ContextVar[str | None] = ContextVar("contentengine_request_id", default=None)
_SAFE_EXTRA_FIELDS: Final[tuple[str, ...]] = (
    "event",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "content_case_id",
    "content_run_id",
    "step_run_id",
    "execution_id",
    "task_key",
    "worker_key",
    "worker_kind",
    "status",
    "error_class",
    "app_env",
    "app_version",
)
_LOGGER_NAMESPACE = "contentengine"


class _ContentEngineHandler(logging.StreamHandler[TextIO]):
    """Marker handler so repeated app/test initialization stays idempotent."""


class SafeJsonFormatter(logging.Formatter):
    """Serialize only an explicit operational field allowlist."""

    def format(self, record: logging.LogRecord) -> str:
        request_id = _REQUEST_ID.get()
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if request_id is not None:
            payload["request_id"] = request_id
        for key in _SAFE_EXTRA_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = _safe_value(value)
        if record.exc_info is not None and record.exc_info[0] is not None:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class SafeTextFormatter(logging.Formatter):
    """Readable local fallback that keeps the same safe field allowlist."""

    def format(self, record: logging.LogRecord) -> str:
        parts = [record.levelname, record.name, record.getMessage()]
        request_id = _REQUEST_ID.get()
        if request_id is not None:
            parts.append(f"request_id={request_id}")
        for key in _SAFE_EXTRA_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                parts.append(f"{key}={_safe_value(value)}")
        if record.exc_info is not None and record.exc_info[0] is not None:
            parts.append(f"exception_type={record.exc_info[0].__name__}")
        return " | ".join(parts)


def configure_logging(settings: Settings) -> None:
    """Configure the ContentEngine logger without mutating third-party loggers."""

    logger = logging.getLogger(_LOGGER_NAMESPACE)
    level = getattr(logging, settings.resolved_log_level)
    logger.setLevel(level)
    logger.propagate = False
    for handler in list(logger.handlers):
        if isinstance(handler, _ContentEngineHandler):
            logger.removeHandler(handler)
    handler = _ContentEngineHandler()
    handler.setLevel(level)
    handler.setFormatter(SafeJsonFormatter() if settings.log_json else SafeTextFormatter())
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    normalized = name.strip(".")
    suffix = f".{normalized}" if normalized else ""
    return logging.getLogger(f"{_LOGGER_NAMESPACE}{suffix}")


def current_request_id() -> str | None:
    return _REQUEST_ID.get()


def _safe_request_id(value: str | None) -> str:
    if value is None:
        return uuid4().hex
    candidate = value.strip()
    if not candidate or len(candidate) > 100:
        return uuid4().hex
    if not all(character.isalnum() or character in "-_." for character in candidate):
        return uuid4().hex
    return candidate


def _safe_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


async def observe_http_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log one safe request lifecycle and propagate a correlation ID."""

    request_id = _safe_request_id(request.headers.get("x-request-id"))
    token = _REQUEST_ID.set(request_id)
    logger = get_logger("http")
    started = perf_counter()
    common = {
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
    }
    logger.debug("http_request_started", extra=common)
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(
            "http_request_failed",
            extra={
                **common,
                "duration_ms": int((perf_counter() - started) * 1000),
                "error_class": type(exc).__name__,
            },
        )
        raise
    else:
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request_completed",
            extra={
                **common,
                "status_code": response.status_code,
                "duration_ms": int((perf_counter() - started) * 1000),
            },
        )
        return response
    finally:
        _REQUEST_ID.reset(token)


__all__ = [
    "SafeJsonFormatter",
    "SafeTextFormatter",
    "configure_logging",
    "current_request_id",
    "get_logger",
    "observe_http_request",
]
