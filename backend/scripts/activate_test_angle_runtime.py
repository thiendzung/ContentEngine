from __future__ import annotations

import argparse
import asyncio
import json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.content_engine.journal.operator_preflight import (
    build_journal_operator_preflight,
)
from app.modules.system.test_angle_runtime import (
    TestAngleRuntimeActivation,
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


def _activation_payload(result: TestAngleRuntimeActivation) -> dict[str, object]:
    return {
        "status": "READY",
        "project_id": str(result.project_id),
        "settings_id": str(result.settings_id),
        "prompt_id": str(result.prompt_id),
        "recipe_id": str(result.recipe_id),
        "provider": result.provider,
        "model": result.model,
        "approved_by": result.approved_by,
        "replayed": result.replayed,
    }


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
                preflight = await build_journal_operator_preflight(session)
                if preflight.get("status") != "READY":
                    blockers = [
                        {
                            "key": item.get("key"),
                            "detail": item.get("detail"),
                        }
                        for item in preflight.get("checks", [])
                        if isinstance(item, dict) and item.get("status") == "BLOCKED"
                    ]
                    raise TestAngleRuntimeActivationError(
                        "test_angle_activation_preflight_blocked:" + json.dumps(blockers)
                    )
    except TestAngleRuntimeActivationError as exc:
        print(f"TEST_ANGLE_RUNTIME: BLOCKED ({exc.code})")
        return 2
    except Exception:
        print("TEST_ANGLE_RUNTIME: BLOCKED (test_angle_activation_failed)")
        return 2

    print(json.dumps(_activation_payload(result), sort_keys=True))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
