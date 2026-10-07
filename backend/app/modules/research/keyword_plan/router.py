from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.content_engine.models import Project
from app.modules.research.keyword_plan.content_architecture import (
    ContentArchitectureError,
    build_content_architecture,
)
from app.modules.research.keyword_plan.create_handoff import (
    CreateProductionHandoffError,
    CreateProductionHandoffResult,
    materialize_create_handoff,
)
from app.modules.research.keyword_plan.opportunity_planner_v2 import (
    OpportunityPlannerError,
    build_opportunity_plan_v2,
)
from app.modules.research.keyword_plan.opportunity_selection_v2 import (
    OpportunitySelectionError,
    OpportunitySelectionRequest,
    OpportunitySelectionResult,
    persist_selected_opportunity,
)
from app.modules.research.keyword_plan.production_admission import (
    ProductionAdmissionError,
    ProductionAdmissionResult,
    build_production_admission,
)
from app.modules.research.keyword_plan.production_decision_router import (
    ProductionDecisionRoute,
    ProductionDecisionRouterError,
    build_production_decision_route,
)
from app.modules.research.keyword_plan.question_coverage import (
    QuestionCoverageError,
    build_question_coverage,
)
from app.modules.research.keyword_plan.question_map import (
    QuestionMapError,
    build_question_map,
)
from app.modules.research.keyword_plan.reconciliation_handoff import (
    MergeProductionHandoffError,
    MergeProductionHandoffResult,
    materialize_merge_handoff,
)
from app.modules.research.keyword_plan.revision_handoff import (
    RevisionProductionHandoffError,
    RevisionProductionHandoffResult,
    materialize_revision_handoff,
)

router = APIRouter(prefix="/question-map", tags=["question-map"])


class CreateProductionHandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_slug: str = Field(default="motgu", min_length=1, max_length=100)
    expected_route_snapshot_hash: str = Field(min_length=64, max_length=64)
    expected_admission_snapshot_hash: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=200)


class RevisionProductionHandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_slug: str = Field(default="motgu", min_length=1, max_length=100)
    expected_route_snapshot_hash: str = Field(min_length=64, max_length=64)
    expected_admission_snapshot_hash: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=200)


class MergeProductionHandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_slug: str = Field(default="motgu", min_length=1, max_length=100)
    survivor_content_item_id: UUID
    founder_reason: str = Field(min_length=1, max_length=2000)
    expected_route_snapshot_hash: str = Field(min_length=64, max_length=64)
    expected_admission_snapshot_hash: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=200)


def _question_map_http_error(
    exc: (
        QuestionMapError
        | QuestionCoverageError
        | ContentArchitectureError
        | OpportunityPlannerError
        | OpportunitySelectionError
        | CreateProductionHandoffError
        | RevisionProductionHandoffError
        | MergeProductionHandoffError
        | ProductionAdmissionError
        | ProductionDecisionRouterError
    ),
) -> HTTPException:
    not_found = {
        "question_map_project_not_found",
        "question_map_need_not_found",
        "content_coverage_project_not_found",
        "content_coverage_need_not_found",
        "opportunity_planner_project_not_found",
        "opportunity_planner_need_not_found",
        "opportunity_selection_need_not_found",
        "production_route_opportunity_not_found",
        "create_handoff_opportunity_not_found",
        "revision_handoff_opportunity_not_found",
        "merge_handoff_opportunity_not_found",
    }
    invalid = {
        "create_handoff_route_hash_invalid",
        "create_handoff_admission_hash_invalid",
        "create_handoff_idempotency_key_invalid",
        "revision_handoff_route_hash_invalid",
        "revision_handoff_admission_hash_invalid",
        "revision_handoff_idempotency_key_invalid",
        "merge_handoff_route_hash_invalid",
        "merge_handoff_admission_hash_invalid",
        "merge_handoff_idempotency_key_invalid",
        "merge_handoff_founder_reason_invalid",
    }
    if exc.code in not_found:
        status_code = 404
    elif exc.code in invalid:
        status_code = 422
    else:
        status_code = 409
    return HTTPException(
        status_code=status_code,
        detail={
            "code": exc.code,
            "message": "Question Map state is unavailable or inconsistent.",
        },
    )


async def _project_id_from_slug(
    session: AsyncSession,
    *,
    project_slug: str,
) -> UUID:
    slug = project_slug.strip()
    if not slug:
        raise QuestionMapError("question_map_project_not_found")
    project_id = await session.scalar(
        select(Project.id).where(Project.slug == slug)
    )
    if project_id is None:
        raise QuestionMapError("question_map_project_not_found")
    return project_id


@router.get("", response_model=dict[str, object])
async def get_question_map(
    need_id: UUID,
    locale: str = Query(min_length=1, max_length=32),
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    try:
        project_id = await _project_id_from_slug(
            session,
            project_slug=project_slug,
        )
        return await build_question_map(
            session,
            project_id=project_id,
            need_id=need_id,
            locale=locale,
        )
    except QuestionMapError as exc:
        raise _question_map_http_error(exc) from exc


@router.get("/coverage", response_model=dict[str, object])
async def get_question_coverage(
    need_id: UUID,
    locale: str = Query(min_length=1, max_length=32),
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    try:
        project_id = await _project_id_from_slug(
            session,
            project_slug=project_slug,
        )
        return await build_question_coverage(
            session,
            project_id=project_id,
            need_id=need_id,
            locale=locale,
        )
    except (QuestionMapError, QuestionCoverageError) as exc:
        raise _question_map_http_error(exc) from exc


@router.get("/architecture", response_model=dict[str, object])
async def get_content_architecture(
    need_id: UUID,
    locale: str = Query(min_length=1, max_length=32),
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    try:
        project_id = await _project_id_from_slug(
            session,
            project_slug=project_slug,
        )
        return await build_content_architecture(
            session,
            project_id=project_id,
            need_id=need_id,
            locale=locale,
        )
    except (
        QuestionMapError,
        QuestionCoverageError,
        ContentArchitectureError,
        OpportunityPlannerError,
    ) as exc:
        raise _question_map_http_error(exc) from exc


@router.get("/opportunities", response_model=dict[str, object])
async def get_opportunity_plan_v2(
    need_id: UUID,
    locale: str = Query(min_length=1, max_length=32),
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    try:
        project_id = await _project_id_from_slug(
            session,
            project_slug=project_slug,
        )
        return await build_opportunity_plan_v2(
            session,
            project_id=project_id,
            need_id=need_id,
            locale=locale,
        )
    except (
        QuestionMapError,
        QuestionCoverageError,
        OpportunityPlannerError,
    ) as exc:
        raise _question_map_http_error(exc) from exc


@router.post(
    "/opportunities/select",
    response_model=OpportunitySelectionResult,
)
async def select_opportunity_plan_v2(
    request: OpportunitySelectionRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> OpportunitySelectionResult:
    try:
        async with session.begin():
            project_id = await _project_id_from_slug(
                session,
                project_slug=request.project_slug,
            )
            return await persist_selected_opportunity(
                session,
                project_id=project_id,
                request=request,
            )
    except (
        QuestionMapError,
        QuestionCoverageError,
        OpportunityPlannerError,
        OpportunitySelectionError,
    ) as exc:
        raise _question_map_http_error(exc) from exc


@router.get(
    "/opportunities/{opportunity_id}/route",
    response_model=ProductionDecisionRoute,
)
async def get_production_decision_route(
    opportunity_id: UUID,
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> ProductionDecisionRoute:
    try:
        project_id = await _project_id_from_slug(
            session,
            project_slug=project_slug,
        )
        return await build_production_decision_route(
            session,
            project_id=project_id,
            opportunity_id=opportunity_id,
        )
    except (
        QuestionMapError,
        ProductionDecisionRouterError,
    ) as exc:
        raise _question_map_http_error(exc) from exc


@router.get(
    "/opportunities/{opportunity_id}/admission",
    response_model=ProductionAdmissionResult,
)
async def get_production_admission(
    opportunity_id: UUID,
    expected_route_snapshot_hash: str = Query(min_length=64, max_length=64),
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> ProductionAdmissionResult:
    try:
        project_id = await _project_id_from_slug(
            session,
            project_slug=project_slug,
        )
        return await build_production_admission(
            session,
            project_id=project_id,
            opportunity_id=opportunity_id,
            expected_route_snapshot_hash=expected_route_snapshot_hash,
        )
    except (
        QuestionMapError,
        ProductionAdmissionError,
    ) as exc:
        raise _question_map_http_error(exc) from exc


@router.post(
    "/opportunities/{opportunity_id}/materialize-merge",
    response_model=MergeProductionHandoffResult,
)
async def create_merge_handoff(
    opportunity_id: UUID,
    request: MergeProductionHandoffRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> MergeProductionHandoffResult:
    try:
        async with session.begin():
            project_id = await _project_id_from_slug(
                session,
                project_slug=request.project_slug,
            )
            return await materialize_merge_handoff(
                session,
                project_id=project_id,
                opportunity_id=opportunity_id,
                survivor_content_item_id=(
                    request.survivor_content_item_id
                ),
                founder_reason=request.founder_reason,
                expected_route_snapshot_hash=(
                    request.expected_route_snapshot_hash
                ),
                expected_admission_snapshot_hash=(
                    request.expected_admission_snapshot_hash
                ),
                idempotency_key=request.idempotency_key,
                actor_id="founder",
            )
    except (
        QuestionMapError,
        MergeProductionHandoffError,
    ) as exc:
        raise _question_map_http_error(exc) from exc


@router.post(
    "/opportunities/{opportunity_id}/materialize-revision",
    response_model=RevisionProductionHandoffResult,
)
async def create_revision_handoff(
    opportunity_id: UUID,
    request: RevisionProductionHandoffRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> RevisionProductionHandoffResult:
    try:
        async with session.begin():
            project_id = await _project_id_from_slug(
                session,
                project_slug=request.project_slug,
            )
            return await materialize_revision_handoff(
                session,
                project_id=project_id,
                opportunity_id=opportunity_id,
                expected_route_snapshot_hash=(
                    request.expected_route_snapshot_hash
                ),
                expected_admission_snapshot_hash=(
                    request.expected_admission_snapshot_hash
                ),
                idempotency_key=request.idempotency_key,
                actor_id="founder",
            )
    except (
        QuestionMapError,
        RevisionProductionHandoffError,
    ) as exc:
        raise _question_map_http_error(exc) from exc


@router.post(
    "/opportunities/{opportunity_id}/materialize-create",
    response_model=CreateProductionHandoffResult,
)
async def create_production_handoff(
    opportunity_id: UUID,
    request: CreateProductionHandoffRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> CreateProductionHandoffResult:
    try:
        async with session.begin():
            project_id = await _project_id_from_slug(
                session,
                project_slug=request.project_slug,
            )
            return await materialize_create_handoff(
                session,
                project_id=project_id,
                opportunity_id=opportunity_id,
                expected_route_snapshot_hash=(
                    request.expected_route_snapshot_hash
                ),
                expected_admission_snapshot_hash=(
                    request.expected_admission_snapshot_hash
                ),
                idempotency_key=request.idempotency_key,
                actor_id="founder",
            )
    except (
        QuestionMapError,
        CreateProductionHandoffError,
    ) as exc:
        raise _question_map_http_error(exc) from exc
