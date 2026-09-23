from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine, get_db
from app.modules.system import preflight
from app.modules.system.read_model import (
    SystemOverview,
    SystemReadError,
    build_system_overview,
)

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/version")
async def version() -> dict[str, str]:
    settings = get_settings()
    return {"version": settings.app_version, "environment": settings.app_env}


@router.get("/health/db")
async def database_health() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
    except Exception as exc:  # pragma: no cover - exact driver error varies by environment
        raise HTTPException(status_code=503, detail="database_unavailable") from exc
    return {"status": "ok"}


@router.get("/system/preflight")
async def operational_preflight() -> dict[str, object]:
    return await preflight.build_operational_preflight()

@router.get("/system/summary", response_model=SystemOverview)
async def system_summary(
    project_slug: str = "motgu",
    session=Depends(get_db),  # noqa: B008
) -> SystemOverview:
    try:
        return await build_system_overview(
            session,
            project_slug=project_slug,
        )
    except SystemReadError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": exc.code,
                "message": "System state is unavailable for this project.",
            },
        ) from exc
