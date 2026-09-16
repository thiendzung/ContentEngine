"""Run the allow-listed Journal operator worker continuously for local operations."""

from __future__ import annotations

import asyncio
import json

from scripts.run_operator_worker import _run

_IDLE_SECONDS = 2.5
_FAILURE_SECONDS = 5.0


async def _loop() -> None:
    while True:
        try:
            await _run(emit_idle=False)
        except (KeyboardInterrupt, asyncio.CancelledError):
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
            await asyncio.sleep(_FAILURE_SECONDS)
        else:
            await asyncio.sleep(_IDLE_SECONDS)


def main() -> None:
    try:
        asyncio.run(_loop())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
