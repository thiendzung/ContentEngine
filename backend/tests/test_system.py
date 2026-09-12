import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


@pytest.mark.asyncio
async def test_health() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_version() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"]
    assert payload["environment"]


@pytest.mark.asyncio
async def test_local_frontend_origin_can_read_backend() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.asyncio
async def test_unlisted_frontend_origin_is_not_allowed() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/health",
            headers={"Origin": "https://example.invalid"},
        )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_wildcard_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cors_wildcard_not_allowed"):
        Settings(app_env="development", cors_allowed_origins="*")
