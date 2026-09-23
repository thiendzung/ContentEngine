from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.learning.read_model import (
    LearningOverview,
    LearningReadError,
    build_learning_overview,
)

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("", response_model=LearningOverview)
async def get_learning_overview(
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> LearningOverview:
    try:
        return await build_learning_overview(
            session,
            project_slug=project_slug,
        )
    except LearningReadError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": exc.code,
                "message": "Learning state is unavailable for this project.",
            },
        ) from exc


__all__ = ["router"]
