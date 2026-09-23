from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.control_center.daily_digest import (
    DailyDigest,
    DailyDigestError,
    build_daily_digest,
)

router = APIRouter(prefix="/daily-digest", tags=["daily-digest"])


@router.get("", response_model=DailyDigest)
async def get_daily_digest(
    digest_date: date = Query(alias="date"),
    timezone: str = Query(min_length=1, max_length=100),
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> DailyDigest:
    try:
        return await build_daily_digest(
            session,
            project_slug=project_slug,
            local_date=digest_date,
            timezone_name=timezone,
        )
    except DailyDigestError as exc:
        if exc.code == "daily_digest_project_not_found":
            status_code = 404
        elif exc.code == "daily_digest_timezone_invalid":
            status_code = 422
        else:
            status_code = 409
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": exc.code,
                "message": "Daily Digest state is unavailable or inconsistent.",
            },
        ) from exc


__all__ = ["router"]
