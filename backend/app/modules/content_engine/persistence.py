from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    HumanSelection,
    NeedHypothesis,
    Signal,
)


def signal_has_traceable_locator(signal: Signal) -> bool:
    provenance = signal.provenance_json
    return bool(
        signal.source_url
        or signal.external_id
        or provenance.get("source_ref")
        or provenance.get("artifact_ref")
        or provenance.get("locator")
    )


def opportunity_has_required_existing_target(
    opportunity: ContentOpportunity,
) -> bool:
    decisions_requiring_target = {"UPDATE", "REFRESH", "MERGE", "LINK_ONLY"}
    return (
        opportunity.decision not in decisions_requiring_target
        or bool(opportunity.existing_content_refs_json)
    )


async def record_human_selection(
    session: AsyncSession,
    *,
    opportunity_id: UUID,
    selected_by: str,
    reason: str,
) -> HumanSelection:
    selection = HumanSelection(
        content_opportunity_id=opportunity_id,
        selected_by=selected_by,
        reason=reason,
    )
    session.add(selection)
    await session.flush()
    return selection


async def create_next_content_version(
    session: AsyncSession,
    *,
    content_item_id: UUID,
    change_reason: str,
    content_json: dict[str, object],
    status: str = "draft",
) -> ContentVersion:
    current_max = await session.scalar(
        select(func.max(ContentVersion.version_no)).where(
            ContentVersion.content_item_id == content_item_id
        )
    )
    version = ContentVersion(
        content_item_id=content_item_id,
        version_no=(current_max or 0) + 1,
        change_reason=change_reason,
        status=status,
        content_json=content_json,
    )
    session.add(version)
    await session.flush()
    return version


async def get_content_item_by_canonical_key(
    session: AsyncSession,
    *,
    project_id: UUID,
    canonical_key: str,
) -> ContentItem | None:
    result = await session.execute(
        select(ContentItem).where(
            ContentItem.project_id == project_id,
            ContentItem.canonical_key == canonical_key,
        )
    )
    return result.scalars().one_or_none()


async def get_need_hypothesis(
    session: AsyncSession,
    hypothesis_id: UUID,
) -> NeedHypothesis | None:
    return await session.get(NeedHypothesis, hypothesis_id)
