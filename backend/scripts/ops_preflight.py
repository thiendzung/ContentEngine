from __future__ import annotations

import asyncio

from app.modules.system.preflight import build_operational_preflight


async def _main() -> int:
    result = await build_operational_preflight()
    for check in result["checks"]:
        if not isinstance(check, dict):
            continue
        print(f"{check['key']}: {check['status']} ({check['detail']})")
    print(f"PREFLIGHT: {result['status']}")
    return 0 if result["status"] == "READY" else 2


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
