from fastapi import FastAPI

from app.modules.content_engine.journal.router import router as journal_router
from app.modules.system.router import router as system_router

app = FastAPI(title="MOTGU ContentEngine", version="0.1.0-ce05")
app.include_router(system_router)
app.include_router(journal_router)
