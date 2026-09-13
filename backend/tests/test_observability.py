from __future__ import annotations

import json
import logging
from typing import cast

import pytest
from fastapi import Request, Response
from starlette.types import Scope

from app.core.config import Settings
from app.core.observability import SafeJsonFormatter, observe_http_request


def test_development_defaults_to_debug_logging() -> None:
    settings = Settings(app_env="development")

    assert settings.resolved_log_level == "DEBUG"
    assert settings.log_json is True


def test_production_debug_is_clamped_without_explicit_override() -> None:
    settings = Settings(
        app_env="production",
        log_level="DEBUG",
        allow_debug_in_production=False,
    )

    assert settings.resolved_log_level == "INFO"


def test_production_debug_can_be_explicitly_enabled() -> None:
    settings = Settings(
        app_env="production",
        log_level="DEBUG",
        allow_debug_in_production=True,
    )

    assert settings.resolved_log_level == "DEBUG"


def test_invalid_log_level_fails_closed() -> None:
    settings = Settings(log_level="verbose")

    with pytest.raises(ValueError, match="invalid_log_level"):
        _ = settings.resolved_log_level


def test_json_formatter_keeps_allowlisted_fields_and_drops_secret_extras() -> None:
    record = logging.LogRecord(
        name="contentengine.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="safe_event",
        args=(),
        exc_info=None,
    )
    setattr(record, "path", "/journal/production-board")
    setattr(record, "status_code", 200)
    setattr(record, "api_key", "do-not-log-me")
    payload = cast(dict[str, object], json.loads(SafeJsonFormatter().format(record)))

    assert payload["message"] == "safe_event"
    assert payload["path"] == "/journal/production-board"
    assert payload["status_code"] == 200
    assert "api_key" not in payload
    assert "do-not-log-me" not in json.dumps(payload)


async def test_http_observer_adds_correlation_id_without_reading_request_body() -> None:
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/journal/production-board",
        "raw_path": b"/journal/production-board",
        "query_string": b"token=must-not-be-logged",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    request = Request(scope)

    async def call_next(_: Request) -> Response:
        return Response(content="ok", status_code=200)

    response = await observe_http_request(request, call_next)

    assert response.status_code == 200
    assert response.headers["x-request-id"]
