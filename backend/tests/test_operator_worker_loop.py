from __future__ import annotations

import asyncio

import pytest

from scripts import run_operator_worker_loop as worker_loop


@pytest.mark.asyncio
async def test_worker_loop_does_not_claim_when_stop_is_already_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def fake_run(*, emit_idle: bool) -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(worker_loop, "_run", fake_run)
    stop = asyncio.Event()
    stop.set()

    await worker_loop._loop(stop)

    assert calls == 0


@pytest.mark.asyncio
async def test_worker_loop_finishes_current_iteration_then_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    stop = asyncio.Event()

    async def fake_run(*, emit_idle: bool) -> None:
        nonlocal calls
        assert emit_idle is False
        calls += 1
        stop.set()

    monkeypatch.setattr(worker_loop, "_run", fake_run)

    await worker_loop._loop(stop)

    assert calls == 1


@pytest.mark.asyncio
async def test_worker_loop_failure_wait_can_be_interrupted_by_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    stop = asyncio.Event()

    async def fake_run(*, emit_idle: bool) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    async def fake_wait(stop_event: asyncio.Event, timeout: float) -> None:
        assert timeout == worker_loop._FAILURE_SECONDS
        stop_event.set()

    monkeypatch.setattr(worker_loop, "_run", fake_run)
    monkeypatch.setattr(worker_loop, "_wait_for_stop", fake_wait)

    await worker_loop._loop(stop)

    assert calls == 1
    assert stop.is_set()
