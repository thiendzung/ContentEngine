from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.content_engine.content_coverage import (
    ContentCoverageError,
    build_content_coverage,
)
from app.modules.content_engine.models import Project

router = APIRouter(prefix="/content-coverage", tags=["content-coverage"])


def _coverage_http_error(exc: ContentCoverageError) -> HTTPException:
    not_found = {
        "content_coverage_project_not_found",
        "content_coverage_need_not_found",
    }
    status_code = 404 if exc.code in not_found else 409
    return HTTPException(
        status_code=status_code,
        detail={
            "code": exc.code,
            "message": "Content Coverage state is unavailable or inconsistent.",
        },
    )


async def _project_id_from_slug(
    session: AsyncSession,
    *,
    project_slug: str,
) -> UUID:
    slug = project_slug.strip()
    if not slug:
        raise ContentCoverageError("content_coverage_project_not_found")
    project_id = await session.scalar(
        select(Project.id).where(Project.slug == slug)
    )
    if project_id is None:
        raise ContentCoverageError("content_coverage_project_not_found")
    return project_id


@router.get("", response_model=dict[str, object])
async def get_content_coverage(
    project_slug: str = Query(default="motgu", min_length=1, max_length=100),
    locale: str | None = Query(default=None, min_length=1, max_length=32),
    audience_id: UUID | None = None,
    need_id: UUID | None = None,
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    try:
        project_id = await _project_id_from_slug(
            session,
            project_slug=project_slug,
        )
        return await build_content_coverage(
            session,
            project_id=project_id,
            locale=locale,
            audience_id=audience_id,
            need_id=need_id,
        )
    except ContentCoverageError as exc:
        raise _coverage_http_error(exc) from exc