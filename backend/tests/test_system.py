import pytest
from httpx import ASGITransport, AsyncClient

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
async def test_operational_preflight_is_safe_and_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_preflight() -> dict[str, object]:
        return {
            "status": "READY",
            "checks": [
                {"key": "database", "status": "READY", "detail": "database=test"},
                {"key": "antigravity_cli", "status": "OPTIONAL", "detail": "unproven"},
            ],
        }

    monkeypatch.setattr(
        "app.modules.system.preflight.build_operational_preflight",
        fake_preflight,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/system/preflight")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "READY"
    assert payload["checks"][1]["status"] == "OPTIONAL"
    assert "password" not in response.text.lower()
    assert "contentengine:contentengine" not in response.text


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
async def test_local_frontend_origin_can_preflight_review_post() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/journal/review-cases/00000000-0000-0000-0000-000000000001/"
            "locales/00000000-0000-0000-0000-000000000002/decision",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]


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
    settings = Settings(app_env="development", cors_allowed_origins="*")
    with pytest.raises(ValueError, match="cors_wildcard_not_allowed"):
        assert settings.resolved_cors_allowed_origins
