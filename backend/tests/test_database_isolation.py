from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.core.config import Settings
from app.core.database import engine
from app.core.database import settings as database_settings

APPLICATION_DATABASE_URL = (
    "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine"
)
DEDICATED_TEST_DATABASE_URL = (
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine_t0434_test",
    )
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": "test",
        "database_url": APPLICATION_DATABASE_URL,
        "test_database_url": DEDICATED_TEST_DATABASE_URL,
    }
    values.update(overrides)
    return Settings(**values)


def _database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def test_test_database_url_is_required() -> None:
    with pytest.raises(ValidationError, match="test_database_url_required"):
        _settings(test_database_url=None)


def test_test_database_must_not_match_application_target() -> None:
    same_target_url = DEDICATED_TEST_DATABASE_URL
    with pytest.raises(
        ValidationError,
        match="test_database_must_differ_from_application_database",
    ):
        _settings(database_url=same_target_url, test_database_url=same_target_url)


def test_test_database_name_must_be_safe() -> None:
    with pytest.raises(ValidationError, match="unsafe_test_database_name"):
        _settings(
            test_database_url=(
                "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine_ci"
            )
        )


def test_safe_test_database_url_is_accepted() -> None:
    configured = _settings()
    assert configured.resolved_database_url == DEDICATED_TEST_DATABASE_URL


def test_application_engine_uses_resolved_test_database_url() -> None:
    assert database_settings.resolved_database_url == DEDICATED_TEST_DATABASE_URL
    assert engine.url.database == _database_name(DEDICATED_TEST_DATABASE_URL)


def test_alembic_resolution_uses_the_same_canonical_test_target() -> None:
    assert database_settings.resolved_database_url == _settings().resolved_database_url


@pytest.mark.asyncio
async def test_current_database_is_dedicated_test_database() -> None:
    async with engine.connect() as connection:
        current_database = (
            await connection.execute(text("select current_database()"))
        ).scalar_one()

    assert "test" in str(current_database).lower()
    assert str(current_database) != _database_name(APPLICATION_DATABASE_URL)
