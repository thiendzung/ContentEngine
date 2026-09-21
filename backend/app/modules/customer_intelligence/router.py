from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.content_engine.models import Project
from app.modules.customer_intelligence.living_map import (
    CustomerMapError,
    customer_map_audience_detail,
    customer_map_changes,
    customer_map_need_detail,
    customer_map_summary,
)

router = APIRouter(prefix="/customer-map", tags=["customer-map"])


def _customer_map_http_error(exc: CustomerMapError) -> HTTPException:
    not_found = {
        "customer_map_project_not_found",
        "customer_map_audience_not_found",
        "customer_map_need_not_found",
    }
    status_code = 404 if exc.code in not_found else 409
    return HTTPException(
        status_code=status_code,
        detail={
            "code": exc.code,
            "message": "Customer Map state is unavailable or inconsistent.",
        },
    )


async def _project_id_from_slug(
    session: AsyncSession,
    *,
    project_slug: str,
) -> UUID:
    slug = project_slug.strip()
    if not slug:
        raise CustomerMapError("customer_map_project_not_found")
    project_id = await session.scalar(
        select(Project.id).where(Project.slug == slug)
    )
    if project_id is None:
        raise CustomerMapError("customer_map_project_not_found")
    return project_id


@router.get("/summary", response_model=dict[str, object])
async def get_customer_map_summary(
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    try:
        project_id = await _project_id_from_slug(
            session,
            project_slug=project_slug,
        )
        return await customer_map_summary(
            session,
            project_id=project_id,
        )
    except CustomerMapError as exc:
        raise _customer_map_http_error(exc) from exc


@router.get("/audiences/{audience_id}", response_model=dict[str, object])
async def get_customer_map_audience(
    audience_id: UUID,
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    try:
        project_id = await _project_id_from_slug(
            session,
            project_slug=project_slug,
        )
        return await customer_map_audience_detail(
            session,
            project_id=project_id,
            audience_id=audience_id,
        )
    except CustomerMapError as exc:
        raise _customer_map_http_error(exc) from exc


@router.get("/needs/{need_id}", response_model=dict[str, object])
async def get_customer_map_need(
    need_id: UUID,
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    try:
        project_id = await _project_id_from_slug(
            session,
            project_slug=project_slug,
        )
        return await customer_map_need_detail(
            session,
            project_id=project_id,
            need_id=need_id,
        )
    except CustomerMapError as exc:
        raise _customer_map_http_error(exc) from exc


@router.get("/changes", response_model=dict[str, object])
async def get_customer_map_changes(
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    try:
        project_id = await _project_id_from_slug(
            session,
            project_slug=project_slug,
        )
        return await customer_map_changes(
            session,
            project_id=project_id,
        )
    except CustomerMapError as exc:
        raise _customer_map_http_error(exc) from exc