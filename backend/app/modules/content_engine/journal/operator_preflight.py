"""Journal-specific preflight for the browser operator vertical slice.

The generic operational preflight proves local infrastructure. This layer adds
only dependencies that the durable ``start_to_angle`` worker will require after
a Founder presses Start, so the browser does not advertise READY for a job that
is guaranteed to fail later.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.content_engine.journal.agent_bridge import (
    ANGLE_PROMPT_KEY,
    ANGLE_RECIPE_KEY,
    ANGLE_TASK_KEY,
)
from app.modules.content_engine.models import Project, SettingsSnapshot, SettingsVersion
from app.modules.harness.runtime import RuntimeConfigurationError, SettingsModelRouter
from app.modules.system.preflight import build_operational_preflight
from app.modules.system.settings_service import (
    SettingsResolutionError,
    active_prompt_definition,
    active_recipe_definition,
)

_PROJECT_SLUG = "motgu"
_CONTENT_TYPE = "journal"
_SUPPORTED_SOURCE_LOCALES = ("en", "vi")
_ALLOWED_ANGLE_PROVIDER = "codex_cli"
_UNRESOLVED_MODELS = {"pending", "pending_human_selection", "todo", "tbd"}


def _check(key: str, status: str, detail: str) -> dict[str, object]:
    return {"key": key, "status": status, "detail": detail}


def _serper_check() -> dict[str, object]:
    secret = get_settings().serper_api_key
    if secret is None or not secret.get_secret_value().strip():
        return _check(
            "journal_research_serper",
            "BLOCKED",
            "operator_worker_serper_required",
        )
    return _check("journal_research_serper", "READY", "configured")


async def _angle_settings_check(session: AsyncSession) -> dict[str, object]:
    project = await session.scalar(select(Project).where(Project.slug == _PROJECT_SLUG))
    if project is None:
        return _check("journal_angle_settings", "BLOCKED", "operator_project_not_found")

    rows = list(
        (
            await session.scalars(
                select(SettingsVersion)
                .where(
                    SettingsVersion.project_id == project.id,
                    SettingsVersion.scope_type == "content_type",
                    SettingsVersion.scope_key == _CONTENT_TYPE,
                    SettingsVersion.status == "active",
                )
                .order_by(SettingsVersion.version, SettingsVersion.id)
            )
        ).all()
    )
    if not rows:
        return _check(
            "journal_angle_settings",
            "BLOCKED",
            "journal_angle_active_settings_missing",
        )
    if len(rows) != 1:
        return _check(
            "journal_angle_settings",
            "BLOCKED",
            "journal_angle_active_settings_duplicate",
        )

    row = rows[0]
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json=dict(row.settings_json),
        source_version_refs_json=[],
        content_hash="0" * 64,
    )
    try:
        route = SettingsModelRouter().resolve(
            task_key=ANGLE_TASK_KEY,
            settings_snapshot=snapshot,
        )
    except RuntimeConfigurationError:
        return _check(
            "journal_angle_settings",
            "BLOCKED",
            "journal_angle_model_route_invalid",
        )

    model = route.primary.model.strip()
    if route.primary.provider != _ALLOWED_ANGLE_PROVIDER:
        return _check(
            "journal_angle_settings",
            "BLOCKED",
            "journal_angle_provider_not_allowed",
        )
    if not model or model.lower() in _UNRESOLVED_MODELS or model.lower().startswith("pending_"):
        return _check(
            "journal_angle_settings",
            "BLOCKED",
            "journal_angle_model_unresolved",
        )
    return _check(
        "journal_angle_settings",
        "READY",
        f"provider={route.primary.provider}; model={model}; settings_version={row.version}",
    )


async def _angle_prompt_check(session: AsyncSession) -> dict[str, object]:
    try:
        prompt = await active_prompt_definition(session, prompt_key=ANGLE_PROMPT_KEY)
    except SettingsResolutionError as exc:
        return _check("journal_angle_prompt", "BLOCKED", exc.code)
    return _check(
        "journal_angle_prompt",
        "READY",
        f"{prompt.prompt_key}:v{prompt.version}",
    )


async def _angle_recipe_check(session: AsyncSession) -> dict[str, object]:
    recipe = None
    for locale in _SUPPORTED_SOURCE_LOCALES:
        try:
            candidate = await active_recipe_definition(
                session,
                recipe_key=ANGLE_RECIPE_KEY,
                content_type=_CONTENT_TYPE,
                locale=locale,
                task_key=ANGLE_TASK_KEY,
            )
        except SettingsResolutionError as exc:
            return _check(
                "journal_angle_recipe",
                "BLOCKED",
                f"locale={locale}; {exc.code}",
            )
        if recipe is None:
            recipe = candidate
        elif candidate.id != recipe.id:
            return _check(
                "journal_angle_recipe",
                "BLOCKED",
                "journal_angle_recipe_locale_mismatch",
            )
    assert recipe is not None
    return _check(
        "journal_angle_recipe",
        "READY",
        f"{recipe.recipe_key}:v{recipe.version}; locales=en,vi",
    )


async def build_journal_operator_preflight(
    session: AsyncSession,
) -> dict[str, object]:
    """Return generic local checks plus fail-closed Start-to-Angle dependencies."""

    base = await build_operational_preflight()
    raw_checks = base.get("checks")
    checks: list[dict[str, object]] = (
        [dict(item) for item in raw_checks if isinstance(item, dict)]
        if isinstance(raw_checks, list)
        else []
    )
    checks.extend(
        [
            _serper_check(),
            await _angle_settings_check(session),
            await _angle_prompt_check(session),
            await _angle_recipe_check(session),
        ]
    )
    ready = all(check.get("status") in {"READY", "OPTIONAL"} for check in checks)
    return {"status": "READY" if ready else "BLOCKED", "checks": checks}


__all__ = ["build_journal_operator_preflight"]
