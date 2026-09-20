from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from test_ce05_review_revise import isolated_session

import scripts.activate_journal_coverage_registry as activation_script
from app.core.config import Settings
from app.modules.content_engine.models import PromptDefinition, RecipeDefinition
from app.modules.system.journal_coverage_registry import (
    ANGLE_PROMPT_KEY,
    ANGLE_RECIPE_KEY,
    JOURNAL_COVERAGE_REGISTRY_VERSION,
    OUTLINE_PROMPT_KEY,
    OUTLINE_RECIPE_KEY,
    JournalCoverageRegistryActivationError,
    activate_journal_promise_coverage_registry,
)
from app.modules.system.recovery import RecoverySafetyError
from scripts.activate_journal_coverage_registry import (
    _activation_payload,
    _validate_database_state,
    _validated_operational_source,
)


async def _prompt(session, key: str, version: int) -> PromptDefinition:
    row = await session.scalar(
        select(PromptDefinition).where(
            PromptDefinition.prompt_key == key,
            PromptDefinition.version == version,
        )
    )
    assert row is not None
    return row


async def _recipe(session, key: str, version: int) -> RecipeDefinition:
    row = await session.scalar(
        select(RecipeDefinition).where(
            RecipeDefinition.recipe_key == key,
            RecipeDefinition.version == version,
        )
    )
    assert row is not None
    return row


def test_coverage_registry_activation_target_guards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        activation_script,
        "get_settings",
        lambda: Settings(
            app_env="test",
            database_url=(
                "postgresql+asyncpg://contentengine:contentengine@127.0.0.1:5432/"
                "contentengine"
            ),
        ),
    )
    with pytest.raises(
        JournalCoverageRegistryActivationError,
        match="journal_coverage_registry_test_environment_forbidden",
    ):
        _validated_operational_source()

    monkeypatch.setattr(
        activation_script,
        "get_settings",
        lambda: Settings(
            app_env="development",
            database_url=(
                "postgresql+asyncpg://contentengine:contentengine@127.0.0.1:5432/"
                "contentengine_restore_test"
            ),
        ),
    )
    with pytest.raises(
        RecoverySafetyError,
        match="operational_database_looks_disposable",
    ):
        _validated_operational_source()

    with pytest.raises(
        JournalCoverageRegistryActivationError,
        match="journal_coverage_registry_database_mismatch",
    ):
        _validate_database_state(
            expected_database="contentengine",
            current_database="another_database",
            revision="20260920_0035",
        )
    with pytest.raises(
        JournalCoverageRegistryActivationError,
        match="journal_coverage_registry_schema_revision_mismatch",
    ):
        _validate_database_state(
            expected_database="contentengine",
            current_database="contentengine",
            revision="20260915_0034",
        )
    _validate_database_state(
        expected_database="contentengine",
        current_database="contentengine",
        revision="20260920_0035",
    )


@pytest.mark.asyncio
async def test_coverage_registry_activation_is_explicit_exact_and_idempotent() -> None:
    async with isolated_session() as session:
        angle_prompt = await _prompt(
            session,
            ANGLE_PROMPT_KEY,
            JOURNAL_COVERAGE_REGISTRY_VERSION,
        )
        outline_prompt = await _prompt(
            session,
            OUTLINE_PROMPT_KEY,
            JOURNAL_COVERAGE_REGISTRY_VERSION,
        )
        angle_recipe = await _recipe(
            session,
            ANGLE_RECIPE_KEY,
            JOURNAL_COVERAGE_REGISTRY_VERSION,
        )
        outline_recipe = await _recipe(
            session,
            OUTLINE_RECIPE_KEY,
            JOURNAL_COVERAGE_REGISTRY_VERSION,
        )
        assert {row.status for row in (angle_prompt, outline_prompt)} == {"draft"}
        assert {row.status for row in (angle_recipe, outline_recipe)} == {"draft"}
        assert all(
            row.approved_by is None
            for row in (angle_prompt, outline_prompt, angle_recipe, outline_recipe)
        )

        first = await activate_journal_promise_coverage_registry(
            session,
            approved_by="founder:test-coverage",
        )
        assert first.replayed is False
        assert first.approved_by == "founder:test-coverage"
        assert all(
            row.status == "active" and row.approved_by == "founder:test-coverage"
            for row in (angle_prompt, outline_prompt, angle_recipe, outline_recipe)
        )

        replay = await activate_journal_promise_coverage_registry(
            session,
            approved_by="founder:test-coverage",
        )
        assert replay.replayed is True
        assert replay.angle_prompt_id == first.angle_prompt_id
        assert replay.angle_recipe_id == first.angle_recipe_id
        assert replay.outline_prompt_id == first.outline_prompt_id
        assert replay.outline_recipe_id == first.outline_recipe_id

        payload = _activation_payload(replay)
        assert json.loads(json.dumps(payload, sort_keys=True))["status"] == "READY"

        with pytest.raises(
            JournalCoverageRegistryActivationError,
            match="journal_coverage_registry_active_approver_mismatch",
        ):
            await activate_journal_promise_coverage_registry(
                session,
                approved_by="someone-else",
            )


@pytest.mark.asyncio
async def test_coverage_registry_activation_retires_exact_active_v1_rows() -> None:
    async with isolated_session() as session:
        old_angle_prompt = await _prompt(session, ANGLE_PROMPT_KEY, 1)
        old_outline_prompt = await _prompt(session, OUTLINE_PROMPT_KEY, 1)
        old_angle_recipe = await _recipe(session, ANGLE_RECIPE_KEY, 1)
        old_outline_recipe = await _recipe(session, OUTLINE_RECIPE_KEY, 1)
        old_rows = (
            old_angle_prompt,
            old_outline_prompt,
            old_angle_recipe,
            old_outline_recipe,
        )
        assert old_angle_prompt.status == "draft"
        assert old_angle_recipe.status == "draft"
        assert old_outline_prompt.status == "active"
        assert old_outline_recipe.status == "active"
        for row in (old_angle_prompt, old_angle_recipe):
            row.status = "active"
            row.approved_by = "founder:legacy"
        await session.flush()

        result = await activate_journal_promise_coverage_registry(
            session,
            approved_by="founder:coverage-v2",
        )
        assert result.replayed is False
        assert all(row.status == "retired" for row in old_rows)

        new_rows = (
            await _prompt(session, ANGLE_PROMPT_KEY, 2),
            await _prompt(session, OUTLINE_PROMPT_KEY, 2),
            await _recipe(session, ANGLE_RECIPE_KEY, 2),
            await _recipe(session, OUTLINE_RECIPE_KEY, 2),
        )
        assert all(
            row.status == "active" and row.approved_by == "founder:coverage-v2"
            for row in new_rows
        )


@pytest.mark.asyncio
async def test_coverage_registry_partial_activation_fails_closed() -> None:
    async with isolated_session() as session:
        angle_prompt = await _prompt(session, ANGLE_PROMPT_KEY, 2)
        assert angle_prompt.status == "draft"
        angle_prompt.status = "active"
        angle_prompt.approved_by = "founder:test"
        await session.flush()

        with pytest.raises(
            JournalCoverageRegistryActivationError,
            match="journal_coverage_registry_partial_activation",
        ):
            await activate_journal_promise_coverage_registry(
                session,
                approved_by="founder:test",
            )
