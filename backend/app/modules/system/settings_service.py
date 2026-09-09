import copy
import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    Project,
    PromptDefinition,
    RecipeDefinition,
    SettingsSnapshot,
    SettingsVersion,
)


class SettingsResolutionError(ValueError):
    """Raised when settings cannot be resolved without guessing policy."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def settings_hash(settings: dict[str, object]) -> str:
    encoded = json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


async def create_settings_snapshot(
    session: AsyncSession,
    *,
    project_id: UUID,
    resolved_settings: dict[str, object],
    source_version_refs: list[str],
) -> SettingsSnapshot:
    snapshot = SettingsSnapshot(
        project_id=project_id,
        resolved_settings_json=copy.deepcopy(resolved_settings),
        source_version_refs_json=list(source_version_refs),
        content_hash=settings_hash(resolved_settings),
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def active_settings_versions(
    session: AsyncSession,
    *,
    project_id: UUID,
    content_type: str | None = None,
    locale: str | None = None,
) -> list[SettingsVersion]:
    """Load active settings, optionally narrowed to the canonical applicable scopes."""

    if (content_type is None) != (locale is None):
        raise SettingsResolutionError("settings_resolution_scope_required")
    if content_type is not None and locale is not None:
        project = await session.get(Project, project_id)
        if project is None:
            raise SettingsResolutionError("settings_project_not_found")
        applicable = (
            (SettingsVersion.scope_type == "system")
            & SettingsVersion.project_id.is_(None)
        ) | (
            (SettingsVersion.scope_type == "project")
            & (SettingsVersion.project_id == project_id)
            & (SettingsVersion.scope_key == project.slug)
        ) | (
            (SettingsVersion.scope_type == "content_type")
            & (SettingsVersion.project_id == project_id)
            & (SettingsVersion.scope_key == content_type)
        ) | (
            (SettingsVersion.scope_type == "locale")
            & (SettingsVersion.project_id == project_id)
            & (SettingsVersion.scope_key == locale)
        )
    else:
        applicable = (
            (SettingsVersion.project_id == project_id)
            | SettingsVersion.project_id.is_(None)
        )
    result = await session.execute(
        select(SettingsVersion)
        .where(
            SettingsVersion.status == "active",
            applicable,
        )
        .order_by(SettingsVersion.scope_type, SettingsVersion.scope_key, SettingsVersion.version)
    )
    return list(result.scalars())


def _settings_version_ref(version: SettingsVersion) -> str:
    return f"settings_version:{version.id}:v{version.version}"


def _merge_settings(
    target: dict[str, object],
    incoming: dict[str, object],
    *,
    path: str = "",
) -> None:
    for key in sorted(incoming):
        value = incoming[key]
        current_path = f"{path}.{key}" if path else key
        if key not in target:
            target[key] = copy.deepcopy(value)
            continue
        existing = target[key]
        if isinstance(existing, dict) and isinstance(value, dict):
            _merge_settings(
                existing,
                value,
                path=current_path,
            )
            continue
        if existing != value:
            raise SettingsResolutionError("settings_override_policy_missing", current_path)


async def resolve_settings_snapshot(
    session: AsyncSession,
    *,
    project_id: UUID,
    content_type: str,
    locale: str,
    run_override: dict[str, object] | None = None,
) -> SettingsSnapshot:
    """Resolve active settings using the one canonical CE03 precedence order."""

    if not content_type.strip() or not locale.strip():
        raise SettingsResolutionError("settings_resolution_scope_required")
    rows = await active_settings_versions(
        session,
        project_id=project_id,
        content_type=content_type,
        locale=locale,
    )
    scope_order = {"system": 0, "project": 1, "content_type": 2, "locale": 3}
    rows.sort(
        key=lambda row: (scope_order[row.scope_type], row.scope_key, row.version, str(row.id))
    )

    seen_exact: set[tuple[UUID | None, str, str]] = set()
    for row in rows:
        exact_scope = (row.project_id, row.scope_type, row.scope_key)
        if exact_scope in seen_exact:
            raise SettingsResolutionError("settings_active_scope_duplicate", row.scope_key)
        seen_exact.add(exact_scope)

    resolved: dict[str, object] = {}
    source_refs: list[str] = []
    for scope_type in ("system", "project", "content_type", "locale"):
        layer_rows = [row for row in rows if row.scope_type == scope_type]
        layer: dict[str, object] = {}
        for row in layer_rows:
            _merge_settings(layer, row.settings_json)
            source_refs.append(_settings_version_ref(row))
        # Scope order is deterministic, but it is not an implicit override policy.
        # A later scope may add a disjoint path or repeat the same value only.
        _merge_settings(resolved, layer)
    if run_override is not None:
        if not isinstance(run_override, dict):
            raise SettingsResolutionError("settings_run_override_invalid")
        _merge_settings(resolved, run_override, path="run_override")
        source_refs.append(f"run_override:{settings_hash(run_override)}")

    resolved_copy = copy.deepcopy(resolved)
    for snapshot in list(
        (
            await session.scalars(
                select(SettingsSnapshot)
                .where(
                    SettingsSnapshot.project_id == project_id,
                    SettingsSnapshot.content_hash == settings_hash(resolved_copy),
                )
                .order_by(SettingsSnapshot.created_at, SettingsSnapshot.id)
            )
        ).all()
    ):
        if (
            snapshot.resolved_settings_json == resolved_copy
            and snapshot.source_version_refs_json == source_refs
        ):
            return snapshot
    return await create_settings_snapshot(
        session,
        project_id=project_id,
        resolved_settings=resolved_copy,
        source_version_refs=source_refs,
    )


async def active_prompt_definition(
    session: AsyncSession,
    *,
    prompt_key: str,
) -> PromptDefinition:
    rows = list(
        (
            await session.scalars(
                select(PromptDefinition)
                .where(
                    PromptDefinition.prompt_key == prompt_key,
                    PromptDefinition.status == "active",
                )
                .order_by(PromptDefinition.version, PromptDefinition.id)
            )
        ).all()
    )
    if not rows:
        raise SettingsResolutionError("active_prompt_missing", prompt_key)
    if len(rows) != 1:
        raise SettingsResolutionError("active_prompt_duplicate", prompt_key)
    return rows[0]


def _selector_matches(
    selector: dict[str, object],
    *,
    content_type: str,
    locale: str,
    task_key: str,
) -> bool:
    for key, actual in (
        ("content_type", content_type),
        ("locale", locale),
        ("task", task_key),
    ):
        expected = selector.get(key)
        if expected is None:
            continue
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif expected != actual:
            return False
    return True


async def active_recipe_definition(
    session: AsyncSession,
    *,
    recipe_key: str,
    content_type: str,
    locale: str,
    task_key: str,
) -> RecipeDefinition:
    rows = list(
        (
            await session.scalars(
                select(RecipeDefinition)
                .where(
                    RecipeDefinition.recipe_key == recipe_key,
                    RecipeDefinition.status == "active",
                )
                .order_by(RecipeDefinition.version, RecipeDefinition.id)
            )
        ).all()
    )
    if not rows:
        raise SettingsResolutionError("active_recipe_missing", recipe_key)
    if len(rows) != 1:
        raise SettingsResolutionError("active_recipe_duplicate", recipe_key)
    if not isinstance(rows[0].selector_json, dict):
        raise SettingsResolutionError("active_recipe_selector_invalid", recipe_key)
    if not _selector_matches(
        rows[0].selector_json,
        content_type=content_type,
        locale=locale,
        task_key=task_key,
    ):
        raise SettingsResolutionError("recipe_selector_mismatch", recipe_key)
    return rows[0]


resolve_settings = resolve_settings_snapshot
