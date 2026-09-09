"""Deterministic, read-only Content Memory gap recommendations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
)


class MemoryGapError(ValueError):
    """A Content Memory request cannot be evaluated safely."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class ContentVersionMemory:
    id: UUID
    version: int
    status: str
    created_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "version": self.version,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class MatchedContentItem:
    content_item_id: UUID
    canonical_key: str
    content_case_id: UUID
    item_status: str
    latest_version: ContentVersionMemory | None
    latest_published_version: ContentVersionMemory | None
    match_basis: tuple[str, ...]

    @property
    def latest_content_version(self) -> ContentVersionMemory | None:
        return self.latest_version

    def to_dict(self) -> dict[str, object]:
        return {
            "content_item_id": str(self.content_item_id),
            "canonical_key": self.canonical_key,
            "content_case_id": str(self.content_case_id),
            "item_status": self.item_status,
            "latest_content_version": (
                self.latest_version.to_dict() if self.latest_version else None
            ),
            "latest_published_version": (
                self.latest_published_version.to_dict()
                if self.latest_published_version
                else None
            ),
            "match_basis": list(self.match_basis),
        }


@dataclass(frozen=True, slots=True)
class MemoryGapReport:
    opportunity_id: UUID
    project_id: UUID
    locale: str
    question: str
    intent: str
    stored_opportunity_decision: str
    matched_content_items: tuple[MatchedContentItem, ...]
    match_basis: dict[str, tuple[str, ...]]
    unresolved_refs: tuple[str, ...]
    recommendation: str | None
    reasons: tuple[str, ...]
    material_gaps: tuple[str, ...]
    what_is_actually_new: str
    refresh_before: datetime | None
    freshness_basis: str
    requires_human_review: bool
    planning_decision_mismatch: bool
    provider_calls: int = 0

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe report without changing persisted state."""

        return {
            "opportunity_id": str(self.opportunity_id),
            "project_id": str(self.project_id),
            "locale": self.locale,
            "question": self.question,
            "intent": self.intent,
            "stored_opportunity_decision": self.stored_opportunity_decision,
            "matched_content_items": [
                item.to_dict() for item in self.matched_content_items
            ],
            "match_basis": {
                item_id: list(basis) for item_id, basis in self.match_basis.items()
            },
            "unresolved_refs": list(self.unresolved_refs),
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
            "material_gaps": list(self.material_gaps),
            "what_is_actually_new": self.what_is_actually_new,
            "refresh_before": (
                self.refresh_before.isoformat() if self.refresh_before else None
            ),
            "freshness_basis": self.freshness_basis,
            "requires_human_review": self.requires_human_review,
            "planning_decision_mismatch": self.planning_decision_mismatch,
            "provider_calls": self.provider_calls,
        }

    as_dict = to_dict


def _normalise_refresh_before(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value


def _string_ref(value: object) -> str:
    return str(value)


def _parse_uuid_ref(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return UUID(value.strip())
    except ValueError:
        return None


async def _load_explicit_targets(
    session: AsyncSession,
    *,
    opportunity: ContentOpportunity,
) -> tuple[dict[UUID, tuple[ContentItem, ContentCase, LocaleVariant]], tuple[str, ...]]:
    refs = opportunity.existing_content_refs_json
    parsed_refs: list[tuple[str, UUID]] = []
    unresolved: list[str] = []
    seen_ref_values: set[str] = set()
    for raw_ref in refs:
        ref = _string_ref(raw_ref)
        if ref in seen_ref_values:
            continue
        seen_ref_values.add(ref)
        parsed = _parse_uuid_ref(raw_ref)
        if parsed is None:
            unresolved.append(ref)
        else:
            parsed_refs.append((ref, parsed))

    if not parsed_refs:
        return {}, tuple(unresolved)

    requested_ids = {item_id for _, item_id in parsed_refs}
    result = await session.execute(
        select(ContentItem, ContentCase, LocaleVariant)
        .join(ContentCase, ContentCase.id == ContentItem.content_case_id)
        .join(LocaleVariant, LocaleVariant.id == ContentItem.locale_variant_id)
        .where(
            ContentItem.id.in_(requested_ids),
            LocaleVariant.content_case_id == ContentCase.id,
        )
    )
    rows = {
        item.id: (item, content_case, locale_variant)
        for item, content_case, locale_variant in result.all()
    }
    targets: dict[UUID, tuple[ContentItem, ContentCase, LocaleVariant]] = {}
    for ref, item_id in parsed_refs:
        row = rows.get(item_id)
        if row is None:
            unresolved.append(ref)
            continue
        item, content_case, locale_variant = row
        if (
            item.project_id != opportunity.project_id
            or content_case.project_id != opportunity.project_id
        ):
            raise MemoryGapError("memory_gap_explicit_ref_project_mismatch", ref)
        if locale_variant.locale != opportunity.locale:
            raise MemoryGapError("memory_gap_explicit_ref_locale_mismatch", ref)
        targets[item_id] = row

    return targets, tuple(dict.fromkeys(unresolved))


async def _load_structural_targets(
    session: AsyncSession,
    *,
    opportunity: ContentOpportunity,
) -> dict[UUID, tuple[ContentItem, ContentCase, LocaleVariant]]:
    result = await session.execute(
        select(ContentItem, ContentCase, LocaleVariant)
        .join(ContentCase, ContentCase.id == ContentItem.content_case_id)
        .join(LocaleVariant, LocaleVariant.id == ContentItem.locale_variant_id)
        .where(
            ContentItem.project_id == opportunity.project_id,
            ContentCase.project_id == opportunity.project_id,
            ContentCase.need_hypothesis_id == opportunity.need_hypothesis_id,
            LocaleVariant.content_case_id == ContentCase.id,
            LocaleVariant.locale == opportunity.locale,
            LocaleVariant.primary_intent == opportunity.intent,
        )
    )
    return {
        item.id: (item, content_case, locale_variant)
        for item, content_case, locale_variant in result.all()
    }


async def _load_versions(
    session: AsyncSession,
    *,
    item_ids: set[UUID],
) -> dict[UUID, list[ContentVersion]]:
    if not item_ids:
        return {}
    result = await session.execute(
        select(ContentVersion)
        .where(ContentVersion.content_item_id.in_(item_ids))
        .order_by(ContentVersion.content_item_id, ContentVersion.version_no)
    )
    versions: dict[UUID, list[ContentVersion]] = defaultdict(list)
    for version in result.scalars():
        versions[version.content_item_id].append(version)
    return versions


def _version_memory(version: ContentVersion) -> ContentVersionMemory:
    return ContentVersionMemory(
        id=version.id,
        version=version.version_no,
        status=version.status,
        created_at=version.created_at,
    )


def _latest_version(versions: list[ContentVersion]) -> ContentVersion | None:
    if not versions:
        return None
    return max(versions, key=lambda row: (row.version_no, row.created_at, str(row.id)))


def _latest_published_version(versions: list[ContentVersion]) -> ContentVersion | None:
    published = [version for version in versions if version.status == "published"]
    if not published:
        return None
    return max(published, key=lambda row: (row.created_at, row.version_no, str(row.id)))


async def recommend_memory_gap(
    session: AsyncSession,
    *,
    content_opportunity_id: UUID,
    refresh_before: datetime | None = None,
) -> MemoryGapReport:
    """Build a deterministic memory-gap report without database mutation."""

    opportunity = await session.get(ContentOpportunity, content_opportunity_id)
    if opportunity is None:
        raise MemoryGapError("memory_gap_opportunity_not_found", str(content_opportunity_id))

    normalised_refresh_before = _normalise_refresh_before(refresh_before)
    explicit_targets, unresolved_refs = await _load_explicit_targets(
        session,
        opportunity=opportunity,
    )
    structural_targets = await _load_structural_targets(session, opportunity=opportunity)

    target_rows = dict(explicit_targets)
    basis_by_id: dict[UUID, set[str]] = {
        item_id: {"explicit_ref"} for item_id in explicit_targets
    }
    for item_id, row in structural_targets.items():
        target_rows[item_id] = row
        basis_by_id.setdefault(item_id, set()).add("structural_match")

    versions_by_item = await _load_versions(session, item_ids=set(target_rows))
    matched_items: list[MatchedContentItem] = []
    for item_id in sorted(target_rows, key=str):
        item, content_case, _locale_variant = target_rows[item_id]
        versions = versions_by_item.get(item_id, [])
        latest = _latest_version(versions)
        latest_published = _latest_published_version(versions)
        matched_items.append(
            MatchedContentItem(
                content_item_id=item.id,
                canonical_key=item.canonical_key,
                content_case_id=content_case.id,
                item_status=item.status,
                latest_version=_version_memory(latest) if latest else None,
                latest_published_version=(
                    _version_memory(latest_published) if latest_published else None
                ),
                match_basis=tuple(sorted(basis_by_id[item_id])),
            )
        )

    reasons: list[str]
    recommendation: str | None
    requires_human_review = bool(unresolved_refs)
    if not matched_items:
        recommendation = "CREATE"
        reasons = ["no_existing_content_item_target"]
    elif len(matched_items) > 1:
        recommendation = None
        requires_human_review = True
        reasons = ["multiple_existing_targets"]
    else:
        recommendation = "UPDATE"
        reasons = ["existing_content_item_target"]
        published = matched_items[0].latest_published_version
        if (
            published is not None
            and normalised_refresh_before is not None
            and published.created_at < normalised_refresh_before
        ):
            recommendation = "REFRESH"
            reasons = ["published_content_version_before_refresh_before"]

    if unresolved_refs:
        reasons.append("unresolved_explicit_refs")
    planning_decision_mismatch = opportunity.decision != recommendation
    if planning_decision_mismatch:
        reasons.append("planning_decision_mismatch")

    basis_report = {
        str(item_id): tuple(sorted(basis_by_id[item_id]))
        for item_id in sorted(basis_by_id, key=str)
    }
    return MemoryGapReport(
        opportunity_id=opportunity.id,
        project_id=opportunity.project_id,
        locale=opportunity.locale,
        question=opportunity.question,
        intent=opportunity.intent,
        stored_opportunity_decision=opportunity.decision,
        matched_content_items=tuple(matched_items),
        match_basis=basis_report,
        unresolved_refs=unresolved_refs,
        recommendation=recommendation,
        reasons=tuple(reasons),
        material_gaps=tuple(opportunity.material_gaps_json),
        what_is_actually_new=opportunity.what_is_actually_new,
        refresh_before=normalised_refresh_before,
        freshness_basis="content_version_created_at",
        requires_human_review=requires_human_review,
        planning_decision_mismatch=planning_decision_mismatch,
    )


check_memory_gap = recommend_memory_gap
build_memory_gap_report = recommend_memory_gap


__all__ = [
    "ContentVersionMemory",
    "MatchedContentItem",
    "MemoryGapError",
    "MemoryGapReport",
    "build_memory_gap_report",
    "check_memory_gap",
    "recommend_memory_gap",
]
