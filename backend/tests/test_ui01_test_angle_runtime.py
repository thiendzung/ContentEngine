from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.database import engine
from app.modules.content_engine.models import PromptDefinition, RecipeDefinition, SettingsVersion
from app.modules.system.test_angle_runtime import (
    TestAngleRuntimeActivationError,
    activate_test_journal_angle_runtime,
)


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
                PromptDefinition.version == 1,
            )
        )
        recipe = await session.scalar(
            select(RecipeDefinition).where(
                RecipeDefinition.recipe_key == "journal_angle_v1",
                RecipeDefinition.version == 1,
            )
        )
        assert settings_row is not None and settings_row.status == "active"
        assert prompt is not None and prompt.status == "active"
        assert recipe is not None and recipe.status == "active"
        assert settings_row.approved_by == "founder:test-acceptance"
        assert prompt.approved_by == "founder:test-acceptance"
        assert recipe.approved_by == "founder:test-acceptance"
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
