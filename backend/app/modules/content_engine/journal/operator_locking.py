"""Transaction-scoped locks for Journal operator mutations."""

from __future__ import annotations

import hashlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _lock_key(value: str) -> int:
    """Map an idempotency key to PostgreSQL's signed 64-bit advisory-lock space."""
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


async def lock_operator_idempotency(session: AsyncSession, *, key: str) -> None:
    """Serialize all mutations using the same public idempotency key until commit/rollback."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _lock_key(key)},
    )


__all__ = ["lock_operator_idempotency"]
