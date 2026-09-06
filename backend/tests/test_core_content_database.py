from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project


@asynccontextmanager
async def isolated_session():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


def project_row() -> Project:
    suffix = uuid4().hex[:8]
    return Project(slug=f"motgu-{suffix}", name="MOTGU", default_locale="en")


@pytest.mark.asyncio
async def test_project_slug_is_unique() -> None:
    async with isolated_session() as session:
        project = project_row()
        session.add(project)
        await session.flush()

        duplicate = Project(slug=project.slug, name="Duplicate", default_locale="en")
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(duplicate)
                await session.flush()
