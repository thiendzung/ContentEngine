import pytest
from sqlalchemy import text

from app.core.database import engine


@pytest.mark.asyncio
async def test_database_connection() -> None:
    async with engine.connect() as connection:
        result = await connection.execute(text("select 1"))

    assert result.scalar_one() == 1
