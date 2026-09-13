"""System module: health, version and runtime settings.

Keep package initialization side-effect free. Operational CLI modules import this package
before the full application graph is loaded, so eager imports here can create a circular
path through content_engine package initialization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.system.settings_service import (
        SettingsResolutionError,
        active_prompt_definition,
        active_recipe_definition,
        resolve_settings,
        resolve_settings_snapshot,
    )

__all__ = [
    "SettingsResolutionError",
    "active_prompt_definition",
    "active_recipe_definition",
    "resolve_settings",
    "resolve_settings_snapshot",
]


def __getattr__(name: str) -> object:
    """Preserve legacy re-exports without importing settings_service eagerly."""
    if name not in __all__:
        raise AttributeError(name)

    from app.modules.system import settings_service

    return getattr(settings_service, name)
