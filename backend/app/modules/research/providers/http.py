from collections.abc import Mapping
from typing import cast

import httpx

from app.modules.research.providers.base import ResearchProviderError


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
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ResearchProviderError(provider, operation, str(exc)) from exc
    if not isinstance(body, dict):
        raise ResearchProviderError(provider, operation, "provider_response_not_object")
    return cast(dict[str, object], body)
