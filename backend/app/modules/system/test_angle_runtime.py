"""Guarded, test-only activation for the seeded Journal Angle runtime.

This exists only to prepare a dedicated local acceptance database. It never
selects a model implicitly and it refuses operational/non-loopback databases.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.content_engine.models import (
    Project,
    PromptDefinition,
    RecipeDefinition,
    SettingsVersion,
)
from app.modules.system.test_database import (
    TestDatabasePreparationError,
    validate_test_database_target,
)

ANGLE_PROMPT_KEY = "journal_angle_candidates"
ANGLE_RECIPE_KEY = "journal_angle_v1"
ANGLE_SETTINGS_SCOPE_TYPE = "content_type"
ANGLE_SETTINGS_SCOPE_KEY = "journal"
ANGLE_SETTINGS_VERSION = 1
ANGLE_PROMPT_VERSION = 2
ANGLE_RECIPE_VERSION = 2
ANGLE_PROVIDER = "codex_cli"
_PENDING_MODELS = {"pending", "pending_human_selection", "todo", "tbd"}


class TestAngleRuntimeActivationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TestAngleRuntimeActivation:
    project_id: UUID
    settings_id: UUID
    prompt_id: UUID
    recipe_id: UUID
    provider: str
    model: str
    approved_by: str
    replayed: bool


def validate_test_angle_activation_target(settings: Settings) -> URL:
    if settings.app_env.strip().lower() != "test":
        raise TestAngleRuntimeActivationError("test_angle_activation_requires_test_env")
    if not settings.test_database_url or not settings.test_database_url.strip():
        raise TestAngleRuntimeActivationError("test_database_url_required")
    try:
        return validate_test_database_target(
            database_url=settings.database_url,
            test_database_url=settings.test_database_url,
        )
    except TestDatabasePreparationError as exc:
        raise TestAngleRuntimeActivationError(exc.code) from exc


def _require_text(value: str, code: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise TestAngleRuntimeActivationError(code)
    return cleaned


def _route_from_settings(row: SettingsVersion) -> tuple[str, str, dict[str, object]]:
    payload = copy.deepcopy(row.settings_json)
    models = payload.get("models")
    routes = payload.get("model_routes")
    if not isinstance(models, dict) or not isinstance(routes, dict):
        raise TestAngleRuntimeActivationError("test_angle_settings_shape_invalid")
    angle = models.get("angle")
    if not isinstance(angle, dict):
        raise TestAngleRuntimeActivationError("test_angle_settings_shape_invalid")
    route_key = angle.get("route")
    if not isinstance(route_key, str) or not route_key.strip():
        raise TestAngleRuntimeActivationError("test_angle_route_missing")
    route = routes.get(route_key)
    if not isinstance(route, dict):
        raise TestAngleRuntimeActivationError("test_angle_route_missing")
    provider = route.get("provider")
    model = route.get("model")
    if not isinstance(provider, str) or not isinstance(model, str):
        raise TestAngleRuntimeActivationError("test_angle_route_invalid")
    return provider.strip(), model.strip(), payload


def _set_route_model(payload: dict[str, object], model: str) -> dict[str, object]:
    models = payload["models"]
    routes = payload["model_routes"]
    assert isinstance(models, dict)
    assert isinstance(routes, dict)
    angle = models["angle"]
    assert isinstance(angle, dict)
    route_key = angle["route"]
    assert isinstance(route_key, str)
    route = routes[route_key]
    assert isinstance(route, dict)
    route["model"] = model
    return payload


async def activate_test_journal_angle_runtime(
    session: AsyncSession,
    *,
    settings: Settings,
    model: str,
    approved_by: str,
    project_slug: str = "motgu",
) -> TestAngleRuntimeActivation:
    """Activate only the seeded test model route; the coverage-aware registry must already be active."""

    target = validate_test_angle_activation_target(settings)
    requested_model = _require_text(model, "test_angle_model_required")
    approver = _require_text(approved_by, "test_angle_approver_required")
    normalized_model = requested_model.casefold()
    if normalized_model in _PENDING_MODELS or normalized_model.startswith("pending_"):
        raise TestAngleRuntimeActivationError("test_angle_model_unresolved")

    current_database = str(
        (await session.execute(text("select current_database()"))).scalar_one()
    )
    if current_database != target.database:
        raise TestAngleRuntimeActivationError("test_angle_session_database_mismatch")

    project = await session.scalar(select(Project).where(Project.slug == project_slug))
    if project is None:
        raise TestAngleRuntimeActivationError("test_angle_project_not_found")

    settings_row = await session.scalar(
        select(SettingsVersion).where(
            SettingsVersion.project_id == project.id,
            SettingsVersion.scope_type == ANGLE_SETTINGS_SCOPE_TYPE,
            SettingsVersion.scope_key == ANGLE_SETTINGS_SCOPE_KEY,
            SettingsVersion.version == ANGLE_SETTINGS_VERSION,
        )
    )
    prompt = await session.scalar(
        select(PromptDefinition).where(
            PromptDefinition.prompt_key == ANGLE_PROMPT_KEY,
            PromptDefinition.version == ANGLE_PROMPT_VERSION,
        )
    )
    recipe = await session.scalar(
        select(RecipeDefinition).where(
            RecipeDefinition.recipe_key == ANGLE_RECIPE_KEY,
            RecipeDefinition.version == ANGLE_RECIPE_VERSION,
        )
    )
    if settings_row is None or prompt is None or recipe is None:
        raise TestAngleRuntimeActivationError("test_angle_seeded_runtime_missing")

    provider, persisted_model, payload = _route_from_settings(settings_row)
    if provider != ANGLE_PROVIDER:
        raise TestAngleRuntimeActivationError("test_angle_provider_mismatch")
    if prompt.status != "active" or recipe.status != "active":
        raise TestAngleRuntimeActivationError("test_angle_registry_not_active")
    if (
        not isinstance(prompt.approved_by, str)
        or not prompt.approved_by.strip()
        or not isinstance(recipe.approved_by, str)
        or not recipe.approved_by.strip()
    ):
        raise TestAngleRuntimeActivationError("test_angle_registry_approval_missing")

    if settings_row.status == "active":
        if persisted_model != requested_model:
            raise TestAngleRuntimeActivationError("test_angle_active_model_mismatch")
        if settings_row.approved_by != approver:
            raise TestAngleRuntimeActivationError("test_angle_active_approver_mismatch")
        return TestAngleRuntimeActivation(
            project_id=project.id,
            settings_id=settings_row.id,
            prompt_id=prompt.id,
            recipe_id=recipe.id,
            provider=provider,
            model=persisted_model,
            approved_by=approver,
            replayed=True,
        )

    if settings_row.status != "draft":
        raise TestAngleRuntimeActivationError("test_angle_partial_activation_forbidden")
    normalized_persisted = persisted_model.casefold()
    if (
        normalized_persisted not in _PENDING_MODELS
        and not normalized_persisted.startswith("pending_")
        and persisted_model != requested_model
    ):
        raise TestAngleRuntimeActivationError("test_angle_draft_model_mismatch")

    settings_row.settings_json = _set_route_model(payload, requested_model)
    settings_row.status = "active"
    settings_row.approved_by = approver
    settings_row.change_reason = (
        "Test-only acceptance activation of the seeded Angle model route; "
        f"model={requested_model}"
    )
    await session.flush()

    return TestAngleRuntimeActivation(
        project_id=project.id,
        settings_id=settings_row.id,
        prompt_id=prompt.id,
        recipe_id=recipe.id,
        provider=ANGLE_PROVIDER,
        model=requested_model,
        approved_by=approver,
        replayed=False,
    )


__all__ = [
    "TestAngleRuntimeActivation",
    "TestAngleRuntimeActivationError",
    "activate_test_journal_angle_runtime",
    "validate_test_angle_activation_target",
]
