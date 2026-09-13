from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class TestDatabasePreparationError(RuntimeError):
    """Raised when the dedicated test database cannot be prepared safely."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PreparedTestDatabase:
    database_name: str
    created: bool


def _target_identity(url: URL) -> tuple[str, int | None, str]:
    database = url.database or ""
    return ((url.host or "").lower(), url.port, database.lower())


def validate_test_database_target(*, database_url: str, test_database_url: str) -> URL:
    operational = make_url(database_url)
    target = make_url(test_database_url)
    database_name = target.database

    if target.get_backend_name() != "postgresql":
        raise TestDatabasePreparationError("test_database_backend_unsupported")
    if not database_name or not _SAFE_IDENTIFIER.fullmatch(database_name):
        raise TestDatabasePreparationError("unsafe_test_database_name")
    if _target_identity(operational) == _target_identity(target):
        raise TestDatabasePreparationError("test_database_matches_operational_database")
    if "test" not in database_name.lower():
        raise TestDatabasePreparationError("unsafe_test_database_name")
    return target


async def prepare_test_database(settings: Settings) -> PreparedTestDatabase:
    if not settings.test_database_url:
        raise TestDatabasePreparationError("test_database_url_required")

    target = validate_test_database_target(
        database_url=settings.database_url,
        test_database_url=settings.test_database_url,
    )
    database_name = target.database
    if database_name is None:  # guarded above; keeps the type contract explicit
        raise TestDatabasePreparationError("unsafe_test_database_name")

    admin_url = target.set(database="postgres")
    admin_engine = create_async_engine(
        admin_url,
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    created = False
    try:
        async with admin_engine.connect() as connection:
            exists = (
                await connection.execute(
                    text("select 1 from pg_database where datname = :database_name"),
                    {"database_name": database_name},
                )
            ).scalar_one_or_none()
            if exists is None:
                # The identifier is restricted above; CREATE DATABASE cannot bind its name.
                await connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
                created = True
    except Exception as exc:
        raise TestDatabasePreparationError("test_database_prepare_failed") from exc
    finally:
        await admin_engine.dispose()

    target_engine = create_async_engine(target, poolclass=NullPool)
    try:
        async with target_engine.connect() as connection:
            current_database = (
                await connection.execute(text("select current_database()"))
            ).scalar_one()
    except Exception as exc:
        raise TestDatabasePreparationError("test_database_connect_failed") from exc
    finally:
        await target_engine.dispose()

    if str(current_database) != database_name:
        raise TestDatabasePreparationError("test_database_identity_mismatch")

    return PreparedTestDatabase(database_name=database_name, created=created)
