from __future__ import annotations

import argparse
import asyncio
import json

from app.core.database import SessionLocal
from app.modules.content_engine.journal.operator_preflight import (
    build_journal_operator_preflight,
)
from app.modules.system.journal_coverage_registry import (
    JournalCoverageRegistryActivation,
    JournalCoverageRegistryActivationError,
    activate_journal_promise_coverage_registry,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Activate exact Journal promise-coverage prompt/recipe registry v2 "
            "with an explicit approver"
        )
    )
    parser.add_argument("--approved-by", required=True)
    return parser.parse_args()


def _activation_payload(
    result: JournalCoverageRegistryActivation,
) -> dict[str, object]:
    return {
        "status": "READY",
        "angle_prompt_id": str(result.angle_prompt_id),
        "angle_recipe_id": str(result.angle_recipe_id),
        "outline_prompt_id": str(result.outline_prompt_id),
        "outline_recipe_id": str(result.outline_recipe_id),
        "approved_by": result.approved_by,
        "replayed": result.replayed,
    }


async def _main() -> int:
    args = _parse_args()
    try:
        async with SessionLocal() as session:
            async with session.begin():
                result = await activate_journal_promise_coverage_registry(
                    session,
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
                    raise JournalCoverageRegistryActivationError(
                        "journal_coverage_registry_preflight_blocked:"
                        + json.dumps(blockers, sort_keys=True)
                    )
    except JournalCoverageRegistryActivationError as exc:
        print(f"JOURNAL_COVERAGE_REGISTRY: BLOCKED ({exc.code})")
        return 2
    except Exception:
        print("JOURNAL_COVERAGE_REGISTRY: BLOCKED (activation_failed)")
        return 2

    print(json.dumps(_activation_payload(result), sort_keys=True))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
