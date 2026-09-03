from fastapi import FastAPI

from app.modules.system.router import router as system_router

app = FastAPI(title="MOTGU ContentEngine", version="0.1.0-ce01")
app.include_router(system_router)
