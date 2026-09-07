from collections.abc import Mapping
from typing import cast

import httpx

from app.modules.research.providers.base import ResearchProviderError


def _http_failure_class(status_code: int) -> str:
    if status_code in {401, 403}:
        return "provider_auth"
    if status_code == 429:
        return "provider_rate_limit"
    if status_code >= 500:
        return "provider_transient"
    return "tool_invalid_response"


async def post_json(
    *,
    provider: str,
    operation: str,
    client: httpx.AsyncClient,
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, object],
) -> dict[str, object]:
    try:
        response = await client.post(url, headers=headers, json=dict(payload))
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        raise ResearchProviderError(
            provider,
            operation,
            f"http_{status_code}",
            failure_class=_http_failure_class(status_code),
        ) from exc
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise ResearchProviderError(
            provider,
            operation,
            type(exc).__name__,
            failure_class="provider_transient",
        ) from exc
    except httpx.HTTPError as exc:
        raise ResearchProviderError(
            provider,
            operation,
            type(exc).__name__,
            failure_class="provider_transient",
        ) from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise ResearchProviderError(
            provider,
            operation,
            "invalid_json_response",
            failure_class="tool_invalid_response",
        ) from exc
    if not isinstance(body, dict):
        raise ResearchProviderError(
            provider,
            operation,
            "provider_response_not_object",
            failure_class="tool_invalid_response",
        )
    return cast(dict[str, object], body)
