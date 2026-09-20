from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.database import engine
from app.modules.content_engine.models import PromptDefinition, RecipeDefinition, SettingsVersion
from app.modules.system.test_angle_runtime import (
    TestAngleRuntimeActivation,
    TestAngleRuntimeActivationError,
    activate_test_journal_angle_runtime,
)
from scripts.activate_test_angle_runtime import _activation_payload


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


def _test_settings() -> Settings:
    return Settings(
        app_env="test",
        database_url=(
            "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine"
        ),
        test_database_url=(
            "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine_test"
        ),
    )


def test_activation_cli_payload_is_json_serializable() -> None:
    result = TestAngleRuntimeActivation(
        project_id=UUID("00000000-0000-0000-0000-000000000001"),
        settings_id=UUID("00000000-0000-0000-0000-000000000002"),
        prompt_id=UUID("00000000-0000-0000-0000-000000000003"),
        recipe_id=UUID("00000000-0000-0000-0000-000000000004"),
        provider="codex_cli",
        model="gpt-5.6-luna",
        approved_by="founder:test-acceptance",
        replayed=True,
    )

    payload = _activation_payload(result)
    rendered = json.dumps(payload, sort_keys=True)

    assert payload["project_id"] == "00000000-0000-0000-0000-000000000001"
    assert payload["settings_id"] == "00000000-0000-0000-0000-000000000002"
    assert payload["prompt_id"] == "00000000-0000-0000-0000-000000000003"
    assert payload["recipe_id"] == "00000000-0000-0000-0000-000000000004"
    assert '"status": "READY"' in rendered
    assert '"replayed": true' in rendered


@pytest.mark.asyncio
async def test_activation_is_explicit_idempotent_and_updates_exact_seeded_rows() -> None:
    async with isolated_session() as session:
        result = await activate_test_journal_angle_runtime(
            session,
            settings=_test_settings(),
            model="gpt-5.6-luna",
            approved_by="founder:test-acceptance",
        )
        assert result.replayed is False
        assert result.provider == "codex_cli"
        assert result.model == "gpt-5.6-luna"

        settings_row = await session.scalar(
            select(SettingsVersion).where(
                SettingsVersion.scope_type == "content_type",
                SettingsVersion.scope_key == "journal",
                SettingsVersion.version == 1,
            )
        )
        prompt = await session.scalar(
            select(PromptDefinition).where(
                PromptDefinition.prompt_key == "journal_angle_candidates",
                PromptDefinition.version == 2,
            )
        )
        recipe = await session.scalar(
            select(RecipeDefinition).where(
                RecipeDefinition.recipe_key == "journal_angle_v1",
                RecipeDefinition.version == 2,
            )
        )
        assert settings_row is not None and settings_row.status == "active"
        assert prompt is not None and prompt.status == "active"
        assert recipe is not None and recipe.status == "active"
        assert settings_row.approved_by == "founder:test-acceptance"
        assert isinstance(prompt.approved_by, str) and prompt.approved_by
        assert isinstance(recipe.approved_by, str) and recipe.approved_by
        routes = settings_row.settings_json["model_routes"]
        assert isinstance(routes, dict)
        angle_route = routes["agent_angle"]
        assert isinstance(angle_route, dict)
        assert angle_route["provider"] == "codex_cli"
        assert angle_route["model"] == "gpt-5.6-luna"

        replay = await activate_test_journal_angle_runtime(
            session,
            settings=_test_settings(),
            model="gpt-5.6-luna",
            approved_by="founder:test-acceptance",
        )
        assert replay.replayed is True
        assert replay.settings_id == result.settings_id
        assert replay.prompt_id == result.prompt_id
        assert replay.recipe_id == result.recipe_id
        assert replay.approved_by == "founder:test-acceptance"

        with pytest.raises(
            TestAngleRuntimeActivationError,
            match="test_angle_active_approver_mismatch",
        ):
            await activate_test_journal_angle_runtime(
                session,
                settings=_test_settings(),
                model="gpt-5.6-luna",
                approved_by="someone-else",
            )

        with pytest.raises(
            TestAngleRuntimeActivationError,
            match="test_angle_active_model_mismatch",
        ):
            await activate_test_journal_angle_runtime(
                session,
                settings=_test_settings(),
                model="gpt-5.6-sol",
                approved_by="founder:test-acceptance",
            )


@pytest.mark.asyncio
async def test_activation_rejects_unresolved_model_before_mutation() -> None:
    async with isolated_session() as session:
        with pytest.raises(
            TestAngleRuntimeActivationError,
            match="test_angle_model_unresolved",
        ):
            await activate_test_journal_angle_runtime(
                session,
                settings=_test_settings(),
                model="pending_human_selection",
                approved_by="founder:test-acceptance",
            )
        active_settings = list(
            (
                await session.scalars(
                    select(SettingsVersion).where(
                        SettingsVersion.scope_type == "content_type",
                        SettingsVersion.scope_key == "journal",
                        SettingsVersion.status == "active",
                    )
                )
            ).all()
        )
        assert active_settings == []
