from __future__ import annotations

import pytest
from sqlalchemy import func, select
from test_ce05_review_revise import isolated_session
from test_operator_preflight import (
    _checks_by_key,
    _ready_base_preflight,
    _settings_with_serper,
)

import app.modules.content_engine.journal.operator_preflight as operator_preflight
from app.modules.system.journal_coverage_registry import (
    activate_journal_promise_coverage_registry,
)
from app.modules.content_engine.models import (
    PromptDefinition,
    RecipeDefinition,
    SettingsSnapshot,
    SettingsVersion,
)


async def _activate_policy_angle_runtime(
    session,
    *,
    candidate_provider: str = "codex_cli",
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
        "models": {
            "angle": {
                "policy": "journal_production",
                "capability": "balanced_reasoning",
            }
        },
        "model_policies": {
            "journal_production": {
                "version": 1,
                "allowed_providers": ["codex_cli"],
                "capabilities": {
                    "balanced_reasoning": {
                        "candidates": [
                            {
                                "provider": candidate_provider,
                                "model": "gpt-5.6-luna",
                            }
                        ],
                        "max_escalations": 0,
                        "allowed_escalation_reasons": [],
                        "max_model_calls_per_step": 1,
                    }
                },
            }
        },
    }
    settings.status = "active"
    settings.approved_by = "test-founder"
    settings.change_reason = "Synthetic policy-mode preflight test only."
    await session.flush()


@pytest.mark.asyncio
async def test_journal_preflight_accepts_policy_mode_without_persisting_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        operator_preflight,
        "build_operational_preflight",
        _ready_base_preflight,
    )
    monkeypatch.setattr(operator_preflight, "get_settings", _settings_with_serper)

    async with isolated_session() as session:
        await _activate_policy_angle_runtime(session)
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
    assert checks["journal_angle_settings"]["status"] == "READY"
    assert "provider=codex_cli" in str(checks["journal_angle_settings"]["detail"])
    assert "model=gpt-5.6-luna" in str(checks["journal_angle_settings"]["detail"])


@pytest.mark.asyncio
async def test_journal_preflight_blocks_invalid_policy_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        operator_preflight,
        "build_operational_preflight",
        _ready_base_preflight,
    )
    monkeypatch.setattr(operator_preflight, "get_settings", _settings_with_serper)

    async with isolated_session() as session:
        await _activate_policy_angle_runtime(
            session,
            candidate_provider="unapproved_provider",
        )
        before = int(
            await session.scalar(select(func.count()).select_from(SettingsSnapshot)) or 0
        )
        result = await operator_preflight.build_journal_operator_preflight(session)
        after = int(
            await session.scalar(select(func.count()).select_from(SettingsSnapshot)) or 0
        )

    checks = _checks_by_key(result)
    assert result["status"] == "BLOCKED"
    assert after == before
    assert checks["journal_angle_settings"]["status"] == "BLOCKED"
    assert checks["journal_angle_settings"]["detail"] == "journal_angle_model_route_invalid"
