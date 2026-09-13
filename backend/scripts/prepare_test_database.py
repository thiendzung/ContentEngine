from __future__ import annotations

import argparse
import asyncio

from app.core.config import get_settings
from app.modules.system.test_database import TestDatabasePreparationError, prepare_test_database


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the dedicated test database")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="drop and recreate only the validated dedicated test database",
    )
    return parser.parse_args()


async def _main() -> int:
    args = _parse_args()
    try:
        settings = get_settings()
    except Exception:
        print("TEST_DATABASE: BLOCKED (test_database_configuration_invalid)")
        return 2

    try:
        prepared = await prepare_test_database(settings, reset=args.reset)
    except TestDatabasePreparationError as exc:
        print(f"TEST_DATABASE: BLOCKED ({exc.code})")
        return 2

    if prepared.reset:
        state = "reset"
    elif prepared.created:
        state = "created"
    else:
        state = "ready"
    print(f"TEST_DATABASE: READY ({state}; database={prepared.database_name})")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
