"""QM-02C: deterministic read-only production admission gate."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.models import ContentCase, ContentItem
from app.modules.harness.models import ContentRun
from app.modules.research.keyword_plan.production_decision_router import (
    ProductionDecisionRoute,
    ProductionDecisionRouterError,
    ProductionRoute,
    build_production_decision_route,
)

PRODUCTION_ADMISSION_SCHEMA_VERSION = 2
PRODUCTION_ADMISSION_POLICY_VERSION = "qm-production-admission-v2"

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
    target_snapshot_hashes: list[str]
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


async def _blocking_run_count(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> int:
    value = await session.scalar(
        select(func.count(ContentRun.id)).where(
            ContentRun.content_case_id == content_case_id,
            ContentRun.status.in_(
                ("pending", "running", "waiting_approval", "failed")
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

    if route.reconciliation_required:
        if (
            route.route != "RECONCILE_CONTENT"
            or len(route.target_content_item_ids) < 2
            or len(route.target_snapshots)
            != len(route.target_content_item_ids)
        ):
            return (
                "BLOCKED_TARGET_STALE",
                ["production_admission_merge_target_count_invalid"],
            )

        for target in route.target_snapshots:
            if target.current_content_version_id is None:
                return (
                    "BLOCKED_TARGET_STALE",
                    ["production_admission_merge_target_version_missing"],
                )
            item = await session.get(ContentItem, target.content_item_id)
            if item is None or item.content_case_id != target.content_case_id:
                return (
                    "BLOCKED_TARGET_STALE",
                    ["production_admission_target_missing"],
                )
            if await _blocking_run_count(
                session,
                content_case_id=item.content_case_id,
            ):
                return (
                    "BLOCKED_PRODUCTION_CONFLICT",
                    ["production_admission_target_has_unresolved_run"],
                )

        if bound_cases:
            if len(bound_cases) == 1:
                reconciliation_case = bound_cases[0]
                matching_receipts = list(
                    (
                        await session.scalars(
                            select(OperatorCommand)
                            .where(
                                OperatorCommand.content_case_id
                                == reconciliation_case.id,
                                OperatorCommand.resolved_action_key
                                == "materialize_question_map_merge",
                                OperatorCommand.status.in_(
                                    ("accepted", "queued", "completed")
                                ),
                            )
                            .order_by(OperatorCommand.id)
                        )
                    ).all()
                )
                if len(matching_receipts) == 1:
                    return (
                        "BLOCKED_ALREADY_MATERIALIZED",
                        [
                            "production_admission_merge_"
                            "already_materialized"
                        ],
                    )
            return (
                "BLOCKED_PRODUCTION_CONFLICT",
                ["production_admission_merge_case_binding_conflict"],
            )

        return (
            "RECONCILIATION_REQUIRED",
            ["production_admission_requires_reconciliation"],
        )

    if not route.admission_candidate:
        return (
            "BLOCKED_PRODUCTION_CONFLICT",
            ["production_admission_route_not_admissible"],
        )

    if route.route == "CREATE_NEW_CONTENT":
        if len(bound_cases) == 1:
            existing = bound_cases[0]
            if (
                existing.content_type == "journal"
                and existing.project_id == route.project_id
                and existing.need_hypothesis_id == route.need_hypothesis_id
            ):
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
        if (
            len(route.target_content_item_ids) != 1
            or len(route.target_snapshots) != 1
        ):
            return (
                "BLOCKED_TARGET_STALE",
                ["production_admission_revision_target_count_invalid"],
            )
        target = route.target_snapshots[0]
        if target.current_content_version_id is None:
            return (
                "BLOCKED_TARGET_STALE",
                ["production_admission_revision_target_version_missing"],
            )
        item = await session.get(
            ContentItem,
            route.target_content_item_ids[0],
        )
        if item is None or item.content_case_id != target.content_case_id:
            return (
                "BLOCKED_TARGET_STALE",
                ["production_admission_target_missing"],
            )

        if bound_cases:
            if len(bound_cases) == 1:
                revision_case = bound_cases[0]
                expected_action = (
                    "materialize_question_map_update"
                    if route.route == "REVISE_EXISTING_CONTENT"
                    else "materialize_question_map_refresh"
                )
                matching_receipts = list(
                    (
                        await session.scalars(
                            select(OperatorCommand)
                            .where(
                                OperatorCommand.content_case_id
                                == revision_case.id,
                                OperatorCommand.result_ref_id
                                == target.current_content_version_id,
                                OperatorCommand.resolved_action_key
                                == expected_action,
                                OperatorCommand.status.in_(
                                    ("accepted", "queued", "completed")
                                ),
                            )
                            .order_by(OperatorCommand.id)
                        )
                    ).all()
                )
                if len(matching_receipts) == 1:
                    return (
                        "BLOCKED_ALREADY_MATERIALIZED",
                        [
                            "production_admission_revision_"
                            "already_materialized"
                        ],
                    )
            return (
                "BLOCKED_PRODUCTION_CONFLICT",
                ["production_admission_revision_case_binding_conflict"],
            )

        if await _blocking_run_count(
            session,
            content_case_id=item.content_case_id,
        ):
            return (
                "BLOCKED_PRODUCTION_CONFLICT",
                ["production_admission_target_has_unresolved_run"],
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
    target_snapshot_hashes: list[str],
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
        "target_snapshot_hashes": target_snapshot_hashes,
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
        target_snapshot_hashes=target_snapshot_hashes,
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
            target_snapshot_hashes=[],
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
            target_snapshot_hashes=[
                row.snapshot_hash for row in route.target_snapshots
            ],
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
        target_snapshot_hashes=[
            row.snapshot_hash for row in route.target_snapshots
        ],
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
