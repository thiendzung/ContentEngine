from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

import scripts.run_operator_worker as worker
from app.modules.system import runtime_maintenance as maintenance


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one(self) -> object:
        return self._value


class _FakeConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.commits = 0

    async def execute(
        self,
        statement: object,
        _params: dict[str, object] | None = None,
    ) -> _ScalarResult:
        sql = str(statement)
        self.statements.append(sql)
        if "pg_try_advisory_lock" in sql:
            return _ScalarResult(True)
        if "pg_advisory_unlock_shared" in sql:
            return _ScalarResult(True)
        if "pg_advisory_unlock" in sql:
            return _ScalarResult(True)
        return _ScalarResult(None)

    async def commit(self) -> None:
        self.commits += 1


class _ConnectionContext:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _FakeConnection:
        return self.connection

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _tb: object,
    ) -> None:
        return None


class _FakeEngine:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    def connect(self) -> _ConnectionContext:
        return _ConnectionContext(self.connection)


@pytest.mark.asyncio
async def test_exclusive_maintenance_gate_uses_session_advisory_lock() -> None:
    connection = _FakeConnection()

    acquired = await maintenance.try_acquire_maintenance_exclusive(
        cast(AsyncConnection, connection)
    )
    await maintenance.release_maintenance_exclusive(
        cast(AsyncConnection, connection)
    )

    assert acquired is True
    assert connection.statements == [
        "select pg_try_advisory_lock(:lock_key)",
        "select pg_advisory_unlock(:lock_key)",
    ]
    assert connection.commits == 2


@pytest.mark.asyncio
async def test_worker_runtime_gate_holds_shared_lock_for_invocation() -> None:
    connection = _FakeConnection()
    engine = _FakeEngine(connection)
    inside = False

    async with maintenance.worker_runtime_gate(cast(AsyncEngine, engine)):
        inside = True
        assert connection.statements == [
            "select pg_advisory_lock_shared(:lock_key)",
        ]

    assert inside is True
    assert connection.statements == [
        "select pg_advisory_lock_shared(:lock_key)",
        "select pg_advisory_unlock_shared(:lock_key)",
    ]
    assert connection.commits == 2


@pytest.mark.asyncio
async def test_operator_worker_enters_maintenance_gate_before_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    @asynccontextmanager
    async def fake_gate(_engine: object) -> AsyncIterator[None]:
        events.append("gate-enter")
        yield
        events.append("gate-exit")

    async def fake_run_after_gate(*, emit_idle: bool = True) -> None:
        events.append(f"run:{emit_idle}")

    monkeypatch.setattr(worker, "worker_runtime_gate", fake_gate)
    monkeypatch.setattr(worker, "_run_after_maintenance_gate", fake_run_after_gate)

    await worker._run(emit_idle=False)

    assert events == ["gate-enter", "run:False", "gate-exit"]
