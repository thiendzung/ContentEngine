"""Run the allow-listed Journal operator worker continuously for local operations."""

from __future__ import annotations

import asyncio
import json
import signal

from scripts.run_operator_worker import _run

_IDLE_SECONDS = 2.5
_FAILURE_SECONDS = 5.0


async def _wait_for_stop(stop: asyncio.Event, timeout: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=timeout)
    except TimeoutError:
        pass


async def _loop(stop: asyncio.Event | None = None) -> None:
    stop_event = stop or asyncio.Event()
    while not stop_event.is_set():
        delay = _IDLE_SECONDS
        try:
            await _run(emit_idle=False)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": "worker_iteration_failed",
                        "error": str(exc)[:2000],
                    },
                    sort_keys=True,
                )
            )
            delay = _FAILURE_SECONDS

        if stop_event.is_set():
            return
        await _wait_for_stop(stop_event, delay)


def _install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop.set)
        except NotImplementedError:  # pragma: no cover - non-POSIX event loops
            pass


async def _main() -> None:
    stop = asyncio.Event()
    _install_signal_handlers(stop)
    await _loop(stop)


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
