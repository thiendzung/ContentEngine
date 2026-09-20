from __future__ import annotations

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from test_ce05_review_revise import isolated_session

import app.modules.content_engine.journal.operator_preflight as operator_preflight
from app.core.config import Settings
from app.modules.content_engine.models import (
    PromptDefinition,
    RecipeDefinition,
    SettingsSnapshot,
    SettingsVersion,
)
from app.modules.system.journal_coverage_registry import (
    activate_journal_promise_coverage_registry,
)


async def _ready_base_preflight() -> dict[str, object]:
    return {
        "status": "READY",
        "checks": [{"key": "base", "status": "READY", "detail": "fixture"}],
    }


def _settings_with_serper() -> Settings:
    return Settings(serper_api_key=SecretStr("synthetic-serper-key"))


async def _activate_angle_runtime(
    session,
    *,
    provider: str = "codex_cli",
    model: str = "gpt-5.6-luna",
) -> None:
    settings = await session.scalar(
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
    assert settings is not None and settings.status == "draft"
    assert prompt is not None and prompt.status == "draft"
    assert recipe is not None and recipe.status == "draft"
    await activate_journal_promise_coverage_registry(
        session,
        approved_by="test-founder",
    )

    settings.settings_json = {
        "models": {"angle": {"route": "agent_angle"}},
        "model_routes": {
            "agent_angle": {
                "provider": provider,
                "model": model,
            }
        },
    }
    settings.status = "active"
    settings.approved_by = "test-founder"
    settings.change_reason = "Test-only activation for operator preflight."
    await session.flush()


def _checks_by_key(result: dict[str, object]) -> dict[str, dict[str, object]]:
    raw = result["checks"]
    assert isinstance(raw, list)
    return {
        str(item["key"]): item
        for item in raw
        if isinstance(item, dict) and "key" in item
    }


@pytest.mark.asyncio
async def test_journal_preflight_blocks_missing_worker_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        operator_preflight,
        "build_operational_preflight",
        _ready_base_preflight,
    )
    monkeypatch.setattr(operator_preflight, "get_settings", lambda: Settings())

    async with isolated_session() as session:
        result = await operator_preflight.build_journal_operator_preflight(session)

    checks = _checks_by_key(result)
    assert result["status"] == "BLOCKED"
    assert checks["journal_research_serper"]["detail"] == "operator_worker_serper_required"
    assert checks["journal_angle_settings"]["detail"] == "journal_angle_active_settings_missing"
    assert checks["journal_angle_prompt"]["detail"] == "active_prompt_missing"
    assert "active_recipe_missing" in str(checks["journal_angle_recipe"]["detail"])
    assert (
        checks["journal_outline_prompt"]["detail"]
        == "journal_coverage_registry_activation_required"
    )
    assert (
        checks["journal_outline_recipe"]["detail"]
        == "journal_coverage_registry_activation_required"
    )


@pytest.mark.asyncio
async def test_journal_preflight_blocks_legacy_registry_v1_after_schema_upgrade() -> None:
    async with isolated_session() as session:
        prompt_rows = list(
            (
                await session.scalars(
                    select(PromptDefinition).where(
                        PromptDefinition.prompt_key.in_(
                            ["journal_angle_candidates", "journal_outline"]
                        ),
                        PromptDefinition.version == 1,
                    )
                )
            ).all()
        )
        recipe_rows = list(
            (
                await session.scalars(
                    select(RecipeDefinition).where(
                        RecipeDefinition.recipe_key.in_(
                            ["journal_angle_v1", "journal_outline_v1"]
                        ),
                        RecipeDefinition.version == 1,
                    )
                )
            ).all()
        )
        assert len(prompt_rows) == 2
        assert len(recipe_rows) == 2
        rows_by_key = {
            row.prompt_key: row for row in prompt_rows
        } | {
            row.recipe_key: row for row in recipe_rows
        }
        assert rows_by_key["journal_angle_candidates"].status == "draft"
        assert rows_by_key["journal_angle_v1"].status == "draft"
        assert rows_by_key["journal_outline"].status == "active"
        assert rows_by_key["journal_outline_v1"].status == "active"
        for key in ("journal_angle_candidates", "journal_angle_v1"):
            row = rows_by_key[key]
            row.status = "active"
            row.approved_by = "founder:legacy-v1"
        await session.flush()

        angle_prompt = await operator_preflight._angle_prompt_check(session)
        angle_recipe = await operator_preflight._angle_recipe_check(session)
        outline_prompt = await operator_preflight._outline_prompt_check(session)
        outline_recipe = await operator_preflight._outline_recipe_check(session)

        assert angle_prompt["detail"] == "journal_coverage_registry_activation_required"
        assert angle_recipe["detail"] == "journal_coverage_registry_activation_required"
        assert outline_prompt["detail"] == "journal_coverage_registry_activation_required"
        assert outline_recipe["detail"] == "journal_coverage_registry_activation_required"


@pytest.mark.asyncio
async def test_journal_preflight_blocks_unresolved_angle_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        operator_preflight,
        "build_operational_preflight",
        _ready_base_preflight,
    )
    monkeypatch.setattr(operator_preflight, "get_settings", _settings_with_serper)

    async with isolated_session() as session:
        await _activate_angle_runtime(session, model="pending_human_selection")
        result = await operator_preflight.build_journal_operator_preflight(session)

    checks = _checks_by_key(result)
    assert result["status"] == "BLOCKED"
    assert checks["journal_research_serper"]["status"] == "READY"
    assert checks["journal_angle_settings"]["detail"] == "journal_angle_model_unresolved"
    assert checks["journal_angle_prompt"]["status"] == "READY"
    assert checks["journal_angle_recipe"]["status"] == "READY"
    assert checks["journal_outline_prompt"]["status"] == "READY"
    assert checks["journal_outline_recipe"]["status"] == "READY"


@pytest.mark.asyncio
async def test_journal_preflight_ready_is_read_only_for_valid_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        operator_preflight,
        "build_operational_preflight",
        _ready_base_preflight,
    )
    monkeypatch.setattr(operator_preflight, "get_settings", _settings_with_serper)

    async with isolated_session() as session:
        await _activate_angle_runtime(session)
        before = int(
            await session.scalar(select(func.count()).select_from(SettingsSnapshot)) or 0
        )
        result = await operator_preflight.build_journal_operator_preflight(session)
        after = int(
            await session.scalar(select(func.count()).select_from(SettingsSnapshot)) or 0
        )

    checks = _checks_by_key(result)
    assert result["status"] == "READY"
    assert after == before
    assert checks["journal_research_serper"]["status"] == "READY"
    assert checks["journal_angle_settings"]["status"] == "READY"
    assert checks["journal_angle_prompt"]["status"] == "READY"
    assert checks["journal_angle_recipe"]["status"] == "READY"
    assert checks["journal_outline_prompt"]["status"] == "READY"
    assert checks["journal_outline_recipe"]["status"] == "READY"
