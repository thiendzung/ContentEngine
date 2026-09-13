from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.modules.system.test_database import TestDatabasePreparationError, prepare_test_database


async def _main() -> int:
    settings = get_settings()
    try:
        prepared = await prepare_test_database(settings)
    except TestDatabasePreparationError as exc:
        print(f"TEST_DATABASE: BLOCKED ({exc.code})")
        return 2

    state = "created" if prepared.created else "ready"
    print(f"TEST_DATABASE: READY ({state}; database={prepared.database_name})")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
