from __future__ import annotations

import pytest
from sqlalchemy import select
from test_ce05_review_revise import isolated_session

from app.core.config import Settings, get_settings
from app.modules.content_engine.models import (
    PromptDefinition,
    RecipeDefinition,
    SettingsVersion,
)
from app.modules.system.test_angle_runtime import (
    TestAngleRuntimeActivationError,
    activate_test_journal_angle_runtime,
    validate_test_angle_activation_target,
)


def test_test_angle_activation_rejects_non_test_environment() -> None:
    settings = Settings(
        app_env="development",
        database_url=(
            "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine"
        ),
        test_database_url=(
            "postgresql+asyncpg://contentengine:contentengine@localhost:5432/"
            "contentengine_test"
        ),
    )
    with pytest.raises(TestAngleRuntimeActivationError) as raised:
        validate_test_angle_activation_target(settings)
    assert raised.value.code == "test_angle_activation_requires_test_env"


@pytest.mark.asyncio
async def test_exact_seeded_angle_runtime_activation_and_replay() -> None:
    async with isolated_session() as session:
        settings = get_settings()
        first = await activate_test_journal_angle_runtime(
            session,
            settings=settings,
            model="gpt-5.6-luna",
            approved_by="test-founder",
        )
        assert first.replayed is False
        assert first.provider == "codex_cli"
        assert first.model == "gpt-5.6-luna"
        assert first.approved_by == "test-founder"

        settings_row = await session.scalar(
            select(SettingsVersion).where(SettingsVersion.id == first.settings_id)
        )
        prompt = await session.scalar(
            select(PromptDefinition).where(PromptDefinition.id == first.prompt_id)
        )
        recipe = await session.scalar(
            select(RecipeDefinition).where(RecipeDefinition.id == first.recipe_id)
        )
        assert settings_row is not None and settings_row.status == "active"
        assert prompt is not None and prompt.status == "active"
        assert recipe is not None and recipe.status == "active"
        routes = settings_row.settings_json["model_routes"]
        assert isinstance(routes, dict)
        route = routes["agent_angle"]
        assert isinstance(route, dict)
        assert route["model"] == "gpt-5.6-luna"

        replay = await activate_test_journal_angle_runtime(
            session,
            settings=settings,
            model="gpt-5.6-luna",
            approved_by="test-founder",
        )
        assert replay.replayed is True
        assert replay.settings_id == first.settings_id
        assert replay.prompt_id == first.prompt_id
        assert replay.recipe_id == first.recipe_id


@pytest.mark.asyncio
async def test_active_runtime_replay_requires_exact_model_and_approver() -> None:
    async with isolated_session() as session:
        settings = get_settings()
        await activate_test_journal_angle_runtime(
            session,
            settings=settings,
            model="gpt-5.6-luna",
            approved_by="test-founder",
        )

        with pytest.raises(TestAngleRuntimeActivationError) as model_error:
            await activate_test_journal_angle_runtime(
                session,
                settings=settings,
                model="gpt-5.6-sol",
                approved_by="test-founder",
            )
        assert model_error.value.code == "test_angle_active_model_mismatch"

        with pytest.raises(TestAngleRuntimeActivationError) as approver_error:
            await activate_test_journal_angle_runtime(
                session,
                settings=settings,
                model="gpt-5.6-luna",
                approved_by="someone-else",
            )
        assert approver_error.value.code == "test_angle_active_approver_mismatch"


@pytest.mark.asyncio
async def test_partial_activation_is_rejected() -> None:
    async with isolated_session() as session:
        prompt = await session.scalar(
            select(PromptDefinition).where(
                PromptDefinition.prompt_key == "journal_angle_candidates",
                PromptDefinition.version == 2,
            )
        )
        assert prompt is not None and prompt.status == "active"
        prompt.status = "retired"
        await session.flush()

        with pytest.raises(TestAngleRuntimeActivationError) as raised:
            await activate_test_journal_angle_runtime(
                session,
                settings=get_settings(),
                model="gpt-5.6-luna",
                approved_by="test-founder",
            )
        assert raised.value.code == "test_angle_registry_not_active"
