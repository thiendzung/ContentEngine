"""QM-02C: deterministic read-only production admission gate."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import ContentCase, ContentItem
from app.modules.harness.models import ContentRun
from app.modules.research.keyword_plan.production_decision_router import (
    ProductionDecisionRoute,
    ProductionDecisionRouterError,
    ProductionRoute,
    build_production_decision_route,
)

PRODUCTION_ADMISSION_SCHEMA_VERSION = 1
PRODUCTION_ADMISSION_POLICY_VERSION = "qm-production-admission-v1"

ProductionAdmissionStatus = Literal[
    "ADMITTED",
    "NO_PRODUCTION",
    "RECONCILIATION_REQUIRED",
    "BLOCKED_ROUTE_STALE",
    "BLOCKED_SELECTION_STALE",
    "BLOCKED_OPPORTUNITY_STALE",
    "BLOCKED_TARGET_STALE",
    "BLOCKED_ALREADY_MATERIALIZED",
    "BLOCKED_PRODUCTION_CONFLICT",
]


class ProductionAdmissionError(ValueError):
    """Fail-closed admission input error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ProductionAdmissionResult(BaseModel):
    schema_version: int
    policy_version: str
    project_id: UUID
    opportunity_id: UUID
    expected_route_snapshot_hash: str
    current_route_snapshot_hash: str | None
    route: ProductionRoute | None
    selection_snapshot_hash: str | None
    target_content_item_ids: list[UUID]
    status: ProductionAdmissionStatus
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


def _normalize_expected_hash(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(
        char not in "0123456789abcdef" for char in normalized
    ):
        raise ProductionAdmissionError(
            "production_admission_route_hash_invalid"
        )
    return normalized


def _router_error_status(code: str) -> ProductionAdmissionStatus:
    if code in {
        "production_route_selection_count_invalid",
        "production_route_selection_mismatch",
    }:
        return "BLOCKED_SELECTION_STALE"

    if code.startswith("production_route_target_"):
        return "BLOCKED_TARGET_STALE"

    return "BLOCKED_OPPORTUNITY_STALE"


async def _active_run_count(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> int:
    value = await session.scalar(
        select(func.count(ContentRun.id)).where(
            ContentRun.content_case_id == content_case_id,
            ContentRun.status.in_(
                ("pending", "running", "waiting_approval")
            ),
        )
    )
    return int(value or 0)


async def _status_for_current_route(
    session: AsyncSession,
    *,
    route: ProductionDecisionRoute,
) -> tuple[ProductionAdmissionStatus, list[str]]:
    if route.production_forbidden:
        return (
            "NO_PRODUCTION",
            ["production_admission_route_forbids_production"],
        )

    if route.reconciliation_required:
        return (
            "RECONCILIATION_REQUIRED",
            ["production_admission_requires_reconciliation"],
        )

    if not route.admission_candidate:
        return (
            "BLOCKED_PRODUCTION_CONFLICT",
            ["production_admission_route_not_admissible"],
        )

    bound_cases = list(
        (
            await session.scalars(
                select(ContentCase)
                .where(
                    ContentCase.content_opportunity_id == route.opportunity_id
                )
                .order_by(ContentCase.id)
            )
        ).all()
    )

    if route.route == "CREATE_NEW_CONTENT":
        if len(bound_cases) == 1 and bound_cases[0].content_type == "journal":
            return (
                "BLOCKED_ALREADY_MATERIALIZED",
                ["production_admission_create_already_materialized"],
            )
        if bound_cases:
            return (
                "BLOCKED_PRODUCTION_CONFLICT",
                ["production_admission_case_binding_conflict"],
            )
        return (
            "ADMITTED",
            ["production_admission_create_ready"],
        )

    if route.route in {
        "REVISE_EXISTING_CONTENT",
        "REFRESH_EXISTING_CONTENT",
    }:
        if bound_cases:
            return (
                "BLOCKED_PRODUCTION_CONFLICT",
                ["production_admission_revision_has_new_case_binding"],
            )
        if len(route.target_content_item_ids) != 1:
            return (
                "BLOCKED_TARGET_STALE",
                ["production_admission_revision_target_count_invalid"],
            )
        item = await session.get(
            ContentItem,
            route.target_content_item_ids[0],
        )
        if item is None:
            return (
                "BLOCKED_TARGET_STALE",
                ["production_admission_target_missing"],
            )
        if await _active_run_count(
            session,
            content_case_id=item.content_case_id,
        ):
            return (
                "BLOCKED_PRODUCTION_CONFLICT",
                ["production_admission_target_has_active_run"],
            )
        return (
            "ADMITTED",
            ["production_admission_revision_ready"],
        )

    return (
        "BLOCKED_PRODUCTION_CONFLICT",
        ["production_admission_route_unsupported"],
    )


def _result(
    *,
    project_id: UUID,
    opportunity_id: UUID,
    expected_route_snapshot_hash: str,
    current_route_snapshot_hash: str | None,
    route: ProductionRoute | None,
    selection_snapshot_hash: str | None,
    target_content_item_ids: list[UUID],
    status: ProductionAdmissionStatus,
    reason_codes: list[str],
) -> ProductionAdmissionResult:
    snapshot: dict[str, object] = {
        "schema_version": PRODUCTION_ADMISSION_SCHEMA_VERSION,
        "policy_version": PRODUCTION_ADMISSION_POLICY_VERSION,
        "project_id": str(project_id),
        "opportunity_id": str(opportunity_id),
        "expected_route_snapshot_hash": expected_route_snapshot_hash,
        "current_route_snapshot_hash": current_route_snapshot_hash,
        "route": route,
        "selection_snapshot_hash": selection_snapshot_hash,
        "target_content_item_ids": [
            str(value) for value in target_content_item_ids
        ],
        "status": status,
        "reason_codes": reason_codes,
    }
    return ProductionAdmissionResult(
        schema_version=PRODUCTION_ADMISSION_SCHEMA_VERSION,
        policy_version=PRODUCTION_ADMISSION_POLICY_VERSION,
        project_id=project_id,
        opportunity_id=opportunity_id,
        expected_route_snapshot_hash=expected_route_snapshot_hash,
        current_route_snapshot_hash=current_route_snapshot_hash,
        route=route,
        selection_snapshot_hash=selection_snapshot_hash,
        target_content_item_ids=target_content_item_ids,
        status=status,
        reason_codes=reason_codes,
        snapshot_hash=_stable_hash(snapshot),
    )


async def build_production_admission(
    session: AsyncSession,
    *,
    project_id: UUID,
    opportunity_id: UUID,
    expected_route_snapshot_hash: str,
) -> ProductionAdmissionResult:
    expected_hash = _normalize_expected_hash(
        expected_route_snapshot_hash
    )

    try:
        route = await build_production_decision_route(
            session,
            project_id=project_id,
            opportunity_id=opportunity_id,
        )
    except ProductionDecisionRouterError as exc:
        return _result(
            project_id=project_id,
            opportunity_id=opportunity_id,
            expected_route_snapshot_hash=expected_hash,
            current_route_snapshot_hash=None,
            route=None,
            selection_snapshot_hash=None,
            target_content_item_ids=[],
            status=_router_error_status(exc.code),
            reason_codes=[exc.code],
        )

    if route.snapshot_hash != expected_hash:
        return _result(
            project_id=project_id,
            opportunity_id=opportunity_id,
            expected_route_snapshot_hash=expected_hash,
            current_route_snapshot_hash=route.snapshot_hash,
            route=route.route,
            selection_snapshot_hash=route.selection_snapshot_hash,
            target_content_item_ids=route.target_content_item_ids,
            status="BLOCKED_ROUTE_STALE",
            reason_codes=[
                "production_admission_route_snapshot_mismatch"
            ],
        )

    status, reason_codes = await _status_for_current_route(
        session,
        route=route,
    )
    return _result(
        project_id=project_id,
        opportunity_id=opportunity_id,
        expected_route_snapshot_hash=expected_hash,
        current_route_snapshot_hash=route.snapshot_hash,
        route=route.route,
        selection_snapshot_hash=route.selection_snapshot_hash,
        target_content_item_ids=route.target_content_item_ids,
        status=status,
        reason_codes=reason_codes,
    )


__all__ = [
    "PRODUCTION_ADMISSION_POLICY_VERSION",
    "PRODUCTION_ADMISSION_SCHEMA_VERSION",
    "ProductionAdmissionError",
    "ProductionAdmissionResult",
    "ProductionAdmissionStatus",
    "build_production_admission",
]
