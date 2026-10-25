"""Versioned project policy for trusted evidence-authority hosts."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import Project, SettingsVersion
from app.modules.research.utils import normalize_trusted_evidence_hosts


class ResearchAuthoritySettingsError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ResearchAuthoritySettingsResult:
    project_id: UUID
    settings_version_id: UUID
    version: int
    trusted_evidence_hosts: tuple[str, ...]
    replayed: bool


def _required_text(value: str, code: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ResearchAuthoritySettingsError(code)
    return normalized


async def configure_research_authority_hosts(
    session: AsyncSession,
    *,
    project_slug: str,
    trusted_evidence_hosts: list[str],
    approved_by: str,
    change_reason: str,
) -> ResearchAuthoritySettingsResult:
    project_key = _required_text(project_slug, "research_authority_project_required")
    actor = _required_text(approved_by, "research_authority_approver_required")
    reason = _required_text(change_reason, "research_authority_change_reason_required")
    try:
        hosts = normalize_trusted_evidence_hosts(trusted_evidence_hosts)
    except ValueError as exc:
        raise ResearchAuthoritySettingsError(
            "research_authority_host_invalid"
        ) from exc
    if not hosts:
        raise ResearchAuthoritySettingsError("research_authority_hosts_required")

    project = await session.scalar(
        select(Project).where(Project.slug == project_key).limit(1)
    )
    if project is None:
        raise ResearchAuthoritySettingsError("research_authority_project_not_found")

    rows = list(
        (
            await session.scalars(
                select(SettingsVersion)
                .where(
                    SettingsVersion.project_id == project.id,
                    SettingsVersion.scope_type == "project",
                    SettingsVersion.scope_key == project.slug,
                )
                .order_by(SettingsVersion.version, SettingsVersion.id)
                .with_for_update()
            )
        ).all()
    )
    active = [row for row in rows if row.status == "active"]
    if len(active) > 1:
        raise ResearchAuthoritySettingsError(
            "research_authority_active_settings_conflict"
        )

    current = active[0] if active else None
    settings_json: dict[str, object] = (
        copy.deepcopy(current.settings_json) if current is not None else {}
    )
    research_raw = settings_json.get("research")
    if research_raw is None:
        research: dict[str, object] = {}
    elif isinstance(research_raw, dict):
        research = copy.deepcopy(research_raw)
    else:
        raise ResearchAuthoritySettingsError("research_authority_settings_invalid")

    current_hosts_raw = research.get("trusted_evidence_hosts")
    if current_hosts_raw is None:
        current_hosts: tuple[str, ...] = ()
    elif isinstance(current_hosts_raw, list) and all(
        isinstance(value, str) for value in current_hosts_raw
    ):
        try:
            current_hosts = normalize_trusted_evidence_hosts(current_hosts_raw)
        except ValueError as exc:
            raise ResearchAuthoritySettingsError(
                "research_authority_settings_invalid"
            ) from exc
    else:
        raise ResearchAuthoritySettingsError("research_authority_settings_invalid")

    if current is not None and current_hosts == hosts:
        return ResearchAuthoritySettingsResult(
            project_id=project.id,
            settings_version_id=current.id,
            version=current.version,
            trusted_evidence_hosts=hosts,
            replayed=True,
        )

    max_version = int(
        await session.scalar(
            select(func.coalesce(func.max(SettingsVersion.version), 0)).where(
                SettingsVersion.project_id == project.id,
                SettingsVersion.scope_type == "project",
                SettingsVersion.scope_key == project.slug,
            )
        )
        or 0
    )

    research["trusted_evidence_hosts"] = list(hosts)
    settings_json["research"] = research

    if current is not None:
        current.status = "retired"
        await session.flush()

    new_version = SettingsVersion(
        project_id=project.id,
        scope_type="project",
        scope_key=project.slug,
        version=max_version + 1,
        settings_json=settings_json,
        status="active",
        change_reason=reason,
        approved_by=actor,
    )
    session.add(new_version)
    await session.flush()

    return ResearchAuthoritySettingsResult(
        project_id=project.id,
        settings_version_id=new_version.id,
        version=new_version.version,
        trusted_evidence_hosts=hosts,
        replayed=False,
    )


__all__ = [
    "ResearchAuthoritySettingsError",
    "ResearchAuthoritySettingsResult",
    "configure_research_authority_hosts",
]
