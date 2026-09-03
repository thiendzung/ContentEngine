from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine

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
