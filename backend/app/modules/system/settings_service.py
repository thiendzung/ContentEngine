import copy
import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import SettingsSnapshot, SettingsVersion


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
    session: AsyncSession, *, project_id: UUID
) -> list[SettingsVersion]:
    result = await session.execute(
        select(SettingsVersion)
        .where(
            (SettingsVersion.project_id == project_id) | (SettingsVersion.project_id.is_(None)),
            SettingsVersion.status == "active",
        )
        .order_by(SettingsVersion.scope_type, SettingsVersion.scope_key, SettingsVersion.version)
    )
    return list(result.scalars())
