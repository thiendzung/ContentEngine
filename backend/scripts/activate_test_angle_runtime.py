from __future__ import annotations

import argparse
import asyncio
import json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.system.test_angle_runtime import (
    TestAngleRuntimeActivationError,
    activate_test_journal_angle_runtime,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Activate exact seeded Journal Angle v1 runtime on dedicated test DB only"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--approved-by", required=True)
    return parser.parse_args()


async def _main() -> int:
    args = _parse_args()
    try:
        settings = get_settings()
        async with SessionLocal() as session:
            async with session.begin():
                result = await activate_test_journal_angle_runtime(
                    session,
                    settings=settings,
                    model=args.model,
                    approved_by=args.approved_by,
                )
    except TestAngleRuntimeActivationError as exc:
        print(f"TEST_ANGLE_RUNTIME: BLOCKED ({exc.code})")
        return 2
    except Exception:
        print("TEST_ANGLE_RUNTIME: BLOCKED (test_angle_activation_failed)")
        return 2

    print(
        json.dumps(
            {
                "status": "READY",
                "project_id": result.project_id,
                "settings_id": result.settings_id,
                "prompt_id": result.prompt_id,
                "recipe_id": result.recipe_id,
                "provider": result.provider,
                "model": result.model,
                "approved_by": result.approved_by,
                "replayed": result.replayed,
            },
            sort_keys=True,
        )
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
