from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.observability import configure_logging, get_logger, observe_http_request
from app.modules.content_engine.journal.router import router as journal_router
from app.modules.system.router import router as system_router

settings = get_settings()
configure_logging(settings)
logger = get_logger("startup")

app = FastAPI(title="MOTGU ContentEngine", version="0.1.0-ce05")
app.middleware("http")(observe_http_request)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.resolved_cors_allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
)
app.include_router(system_router)
app.include_router(journal_router)

logger.info(
    "application_configured",
    extra={
        "event": "application_configured",
        "app_env": settings.app_env,
        "app_version": settings.app_version,
    },
)
