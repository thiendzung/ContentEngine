from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

_OPERATIONAL_MAINTENANCE_LOCK_KEY = 43450044


class RuntimeMaintenanceError(RuntimeError):
    """Raised when the operational runtime maintenance gate cannot be used safely."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


async def try_acquire_maintenance_exclusive(connection: AsyncConnection) -> bool:
    """Try to hold the process-wide operational maintenance gate.

    The lock is session-scoped, so commit immediately to avoid leaving an idle
    transaction open while the migration runs. Current-code workers hold the
    matching shared advisory lock for the lifetime of one worker invocation.
    """

    value = (
        await connection.execute(
            text("select pg_try_advisory_lock(:lock_key)"),
            {"lock_key": _OPERATIONAL_MAINTENANCE_LOCK_KEY},
        )
    ).scalar_one()
    await connection.commit()
    return bool(value)


async def release_maintenance_exclusive(connection: AsyncConnection) -> None:
    value = (
        await connection.execute(
            text("select pg_advisory_unlock(:lock_key)"),
            {"lock_key": _OPERATIONAL_MAINTENANCE_LOCK_KEY},
        )
    ).scalar_one()
    await connection.commit()
    if not bool(value):
        raise RuntimeMaintenanceError("maintenance_exclusive_lock_not_held")


@asynccontextmanager
async def worker_runtime_gate(engine: AsyncEngine) -> AsyncIterator[None]:
    """Block a worker at the database boundary while maintenance is exclusive.

    PostgreSQL advisory-lock waiting is event-driven: no process scanning,
    polling loop, sleep, ps, or pgrep is required.
    """

    async with engine.connect() as connection:
        await connection.execute(
            text("select pg_advisory_lock_shared(:lock_key)"),
            {"lock_key": _OPERATIONAL_MAINTENANCE_LOCK_KEY},
        )
        await connection.commit()
        try:
            yield
        finally:
            value = (
                await connection.execute(
                    text("select pg_advisory_unlock_shared(:lock_key)"),
                    {"lock_key": _OPERATIONAL_MAINTENANCE_LOCK_KEY},
                )
            ).scalar_one()
            await connection.commit()
            if not bool(value):
                raise RuntimeMaintenanceError("worker_shared_lock_not_held")
