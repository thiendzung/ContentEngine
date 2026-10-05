from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.content_engine.models import Project
from app.modules.research.keyword_plan.question_coverage import (
    QuestionCoverageError,
    build_question_coverage,
)
from app.modules.research.keyword_plan.question_map import (
    QuestionMapError,
    build_question_map,
)

router = APIRouter(prefix="/question-map", tags=["question-map"])


def _question_map_http_error(
    exc: QuestionMapError | QuestionCoverageError,
) -> HTTPException:
    not_found = {
        "question_map_project_not_found",
        "question_map_need_not_found",
        "content_coverage_project_not_found",
        "content_coverage_need_not_found",
    }
    status_code = 404 if exc.code in not_found else 409
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
