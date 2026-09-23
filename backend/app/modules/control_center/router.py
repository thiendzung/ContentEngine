from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.control_center.read_model import (
    ControlCenterError,
    ControlCenterSummary,
    NeedsMeItem,
    build_control_center,
)

router = APIRouter(prefix="/control-center", tags=["control-center"])


def _http_error(exc: ControlCenterError) -> HTTPException:
    status_code = (
        404
        if exc.code == "control_center_project_not_found"
        else 422
        if exc.code == "control_center_timezone_invalid"
        else 409
    )
    return HTTPException(
        status_code=status_code,
        detail={
            "code": exc.code,
            "message": "Control Center state is unavailable or inconsistent.",
        },
    )


@router.get("/summary", response_model=ControlCenterSummary)
async def get_control_center_summary(
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    timezone: str = Query(default="UTC", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> ControlCenterSummary:
    try:
        snapshot = await build_control_center(
            session,
            project_slug=project_slug,
            timezone_name=timezone,
        )
        return snapshot.summary
    except ControlCenterError as exc:
        raise _http_error(exc) from exc


@router.get("/needs-me", response_model=list[NeedsMeItem])
async def get_control_center_needs_me(
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    timezone: str = Query(default="UTC", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[NeedsMeItem]:
    try:
        snapshot = await build_control_center(
            session,
            project_slug=project_slug,
            timezone_name=timezone,
        )
        return snapshot.needs_me
    except ControlCenterError as exc:
        raise _http_error(exc) from exc


__all__ = ["router"]
