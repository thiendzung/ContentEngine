from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Shared SQLAlchemy declarative base for persisted application data."""


settings = get_settings()
# NullPool keeps async connections bound to the active event loop and is sufficient
# for the current small CE02 service. A tuned pool belongs to a later runtime task.
engine = create_async_engine(settings.database_url, poolclass=NullPool)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
