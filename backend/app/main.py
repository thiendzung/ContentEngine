from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.content_engine.journal.router import router as journal_router
from app.modules.system.router import router as system_router

settings = get_settings()

app = FastAPI(title="MOTGU ContentEngine", version="0.1.0-ce05")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.resolved_cors_allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
)
app.include_router(system_router)
app.include_router(journal_router)
