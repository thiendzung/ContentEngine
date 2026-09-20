from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.content_engine.journal.operator_preflight import (
    build_journal_operator_preflight,
)
from app.modules.system.journal_coverage_registry import (
    JournalCoverageRegistryActivation,
    JournalCoverageRegistryActivationError,
    activate_journal_promise_coverage_registry,
)
from app.modules.system.recovery import (
    RecoverySafetyError,
    validate_operational_database_source,
)

_EXPECTED_REVISION = "20260920_0035"


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
        settings = get_settings()
        if settings.app_env.strip().lower() == "test":
            raise JournalCoverageRegistryActivationError(
                "journal_coverage_registry_test_environment_forbidden"
            )
        source = validate_operational_database_source(settings.database_url)
        async with SessionLocal() as session:
            async with session.begin():
                current_database = str(
                    (
                        await session.execute(text("select current_database()"))
                    ).scalar_one()
                )
                if current_database != source.database:
                    raise JournalCoverageRegistryActivationError(
                        "journal_coverage_registry_database_mismatch"
                    )
                revision = (
                    await session.execute(
                        text("select version_num from alembic_version")
                    )
                ).scalar_one_or_none()
                if revision != _EXPECTED_REVISION:
                    raise JournalCoverageRegistryActivationError(
                        "journal_coverage_registry_schema_revision_mismatch"
                    )
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
    except RecoverySafetyError as exc:
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
