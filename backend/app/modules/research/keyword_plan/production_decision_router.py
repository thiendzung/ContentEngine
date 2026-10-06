"""QM-02B: deterministic read-only production decision router."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    HumanSelection,
    LocaleVariant,
)

PRODUCTION_DECISION_ROUTER_SCHEMA_VERSION = 1
PRODUCTION_DECISION_ROUTER_POLICY_VERSION = "qm-production-router-v1"

ProductionRoute = Literal[
    "CREATE_NEW_CONTENT",
    "REVISE_EXISTING_CONTENT",
    "REFRESH_EXISTING_CONTENT",
    "RECONCILE_CONTENT",
    "NO_PRODUCTION",
    "STOP",
]


class ProductionDecisionRouterError(ValueError):
    """Fail-closed production routing error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ProductionDecisionRoute(BaseModel):
    schema_version: int
    policy_version: str
    project_id: UUID
    opportunity_id: UUID
    opportunity_version: int
    human_selection_id: UUID
    selection_snapshot_hash: str
    need_hypothesis_id: UUID
    locale: str
    decision: str
    route: ProductionRoute
    target_content_item_ids: list[UUID]
    admission_candidate: bool
    reconciliation_required: bool
    production_forbidden: bool
    reason_codes: list[str]
    snapshot_hash: str


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _selection_snapshot_hash(selection: HumanSelection) -> str:
    return _stable_hash(
        {
            "id": str(selection.id),
            "content_opportunity_id": str(selection.content_opportunity_id),
            "selected_by": selection.selected_by,
            "reason": selection.reason,
            "selected_at": selection.selected_at.isoformat(),
        }
    )


def _parse_target_refs(values: object) -> list[UUID]:
    if not isinstance(values, list):
        raise ProductionDecisionRouterError(
            "production_route_target_refs_invalid"
        )
    refs: list[UUID] = []
    for raw in values:
        if not isinstance(raw, str) or not raw.strip():
            raise ProductionDecisionRouterError(
                "production_route_target_refs_invalid"
            )
        try:
            refs.append(UUID(raw.strip()))
        except ValueError as exc:
            raise ProductionDecisionRouterError(
                "production_route_target_refs_invalid"
            ) from exc
    if len(refs) != len(set(refs)):
        raise ProductionDecisionRouterError(
            "production_route_target_refs_duplicate"
        )
    return sorted(refs, key=str)


def _route_for_decision(
    decision: str,
    target_count: int,
) -> tuple[ProductionRoute, bool, bool, bool, list[str]]:
    if decision == "CREATE":
        if target_count != 0:
            raise ProductionDecisionRouterError(
                "production_route_create_target_conflict"
            )
        return (
            "CREATE_NEW_CONTENT",
            True,
            False,
            False,
            ["selected_create_requires_new_content"],
        )
    if decision == "UPDATE":
        if target_count != 1:
            raise ProductionDecisionRouterError(
                "production_route_update_target_count_invalid"
            )
        return (
            "REVISE_EXISTING_CONTENT",
            True,
            False,
            False,
            ["selected_update_requires_existing_revision"],
        )
    if decision == "REFRESH":
        if target_count != 1:
            raise ProductionDecisionRouterError(
                "production_route_refresh_target_count_invalid"
            )
        return (
            "REFRESH_EXISTING_CONTENT",
            True,
            False,
            False,
            ["selected_refresh_requires_existing_revision"],
        )
    if decision == "MERGE":
        if target_count < 2:
            raise ProductionDecisionRouterError(
                "production_route_merge_target_count_invalid"
            )
        return (
            "RECONCILE_CONTENT",
            False,
            True,
            False,
            ["selected_merge_requires_reconciliation"],
        )
    if decision == "LINK_ONLY":
        if target_count != 1:
            raise ProductionDecisionRouterError(
                "production_route_link_only_target_count_invalid"
            )
        return (
            "NO_PRODUCTION",
            False,
            False,
            True,
            ["selected_link_only_requires_no_new_production"],
        )
    if decision == "DO_NOT_WRITE":
        if target_count != 0:
            raise ProductionDecisionRouterError(
                "production_route_do_not_write_target_conflict"
            )
        return (
            "STOP",
            False,
            False,
            True,
            ["selected_do_not_write_stops_production"],
        )
    raise ProductionDecisionRouterError(
        "production_route_decision_invalid"
    )


async def _exact_selection(
    session: AsyncSession,
    *,
    opportunity: ContentOpportunity,
) -> HumanSelection:
    rows = list(
        (
            await session.scalars(
                select(HumanSelection)
                .where(
                    HumanSelection.content_opportunity_id == opportunity.id
                )
                .order_by(HumanSelection.selected_at, HumanSelection.id)
            )
        ).all()
    )
    if len(rows) != 1:
        raise ProductionDecisionRouterError(
            "production_route_selection_count_invalid"
        )
    selection = rows[0]
    if (
        opportunity.selected_by is None
        or opportunity.selected_at is None
        or opportunity.selection_reason is None
        or selection.selected_by != opportunity.selected_by
        or selection.selected_at != opportunity.selected_at
        or selection.reason != opportunity.selection_reason
    ):
        raise ProductionDecisionRouterError(
            "production_route_selection_mismatch"
        )
    return selection


async def _validate_targets(
    session: AsyncSession,
    *,
    opportunity: ContentOpportunity,
    target_ids: list[UUID],
) -> None:
    if not target_ids:
        return

    rows = (
        await session.execute(
            select(ContentItem, ContentCase, LocaleVariant)
            .join(
                ContentCase,
                ContentCase.id == ContentItem.content_case_id,
            )
            .join(
                LocaleVariant,
                LocaleVariant.id == ContentItem.locale_variant_id,
            )
            .where(ContentItem.id.in_(target_ids))
        )
    ).all()
    if len(rows) != len(target_ids):
        raise ProductionDecisionRouterError(
            "production_route_target_not_found"
        )

    found_ids: set[UUID] = set()
    for item, content_case, variant in rows:
        found_ids.add(item.id)
        if (
            item.project_id != opportunity.project_id
            or content_case.project_id != opportunity.project_id
        ):
            raise ProductionDecisionRouterError(
                "production_route_target_project_mismatch"
            )
        if content_case.need_hypothesis_id != opportunity.need_hypothesis_id:
            raise ProductionDecisionRouterError(
                "production_route_target_not_primary_need"
            )
        if variant.content_case_id != content_case.id:
            raise ProductionDecisionRouterError(
                "production_route_target_variant_case_mismatch"
            )
        if variant.locale.strip().casefold() != opportunity.locale.strip().casefold():
            raise ProductionDecisionRouterError(
                "production_route_target_locale_mismatch"
            )
    if found_ids != set(target_ids):
        raise ProductionDecisionRouterError(
            "production_route_target_not_found"
        )


async def build_production_decision_route(
    session: AsyncSession,
    *,
    project_id: UUID,
    opportunity_id: UUID,
) -> ProductionDecisionRoute:
    opportunity = await session.get(ContentOpportunity, opportunity_id)
    if opportunity is None or opportunity.project_id != project_id:
        raise ProductionDecisionRouterError(
            "production_route_opportunity_not_found"
        )
    if opportunity.suggested_content_type != "journal":
        raise ProductionDecisionRouterError(
            "production_route_content_type_unsupported"
        )
    if opportunity.version <= 0:
        raise ProductionDecisionRouterError(
            "production_route_opportunity_version_invalid"
        )
    locale = opportunity.locale.strip().casefold()
    if not locale:
        raise ProductionDecisionRouterError(
            "production_route_locale_invalid"
        )

    selection = await _exact_selection(
        session,
        opportunity=opportunity,
    )
    target_ids = _parse_target_refs(
        opportunity.existing_content_refs_json
    )
    (
        route,
        admission_candidate,
        reconciliation_required,
        production_forbidden,
        reason_codes,
    ) = _route_for_decision(
        opportunity.decision,
        len(target_ids),
    )
    await _validate_targets(
        session,
        opportunity=opportunity,
        target_ids=target_ids,
    )

    snapshot: dict[str, object] = {
        "schema_version": PRODUCTION_DECISION_ROUTER_SCHEMA_VERSION,
        "policy_version": PRODUCTION_DECISION_ROUTER_POLICY_VERSION,
        "project_id": str(project_id),
        "opportunity_id": str(opportunity.id),
        "opportunity_version": opportunity.version,
        "human_selection_id": str(selection.id),
        "selection_snapshot_hash": _selection_snapshot_hash(selection),
        "need_hypothesis_id": str(opportunity.need_hypothesis_id),
        "locale": locale,
        "decision": opportunity.decision,
        "route": route,
        "target_content_item_ids": [str(value) for value in target_ids],
        "admission_candidate": admission_candidate,
        "reconciliation_required": reconciliation_required,
        "production_forbidden": production_forbidden,
        "reason_codes": reason_codes,
    }
    return ProductionDecisionRoute(
        schema_version=PRODUCTION_DECISION_ROUTER_SCHEMA_VERSION,
        policy_version=PRODUCTION_DECISION_ROUTER_POLICY_VERSION,
        project_id=project_id,
        opportunity_id=opportunity.id,
        opportunity_version=opportunity.version,
        human_selection_id=selection.id,
        selection_snapshot_hash=_selection_snapshot_hash(selection),
        need_hypothesis_id=opportunity.need_hypothesis_id,
        locale=locale,
        decision=opportunity.decision,
        route=route,
        target_content_item_ids=target_ids,
        admission_candidate=admission_candidate,
        reconciliation_required=reconciliation_required,
        production_forbidden=production_forbidden,
        reason_codes=reason_codes,
        snapshot_hash=_stable_hash(snapshot),
    )


__all__ = [
    "PRODUCTION_DECISION_ROUTER_POLICY_VERSION",
    "PRODUCTION_DECISION_ROUTER_SCHEMA_VERSION",
    "ProductionDecisionRoute",
    "ProductionDecisionRouterError",
    "ProductionRoute",
    "build_production_decision_route",
]
