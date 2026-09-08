"""Check Content Memory and recommend CREATE, UPDATE, or REFRESH."""

# ruff: noqa: E402

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import cast
from uuid import UUID

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from app.modules.content_engine.memory_gap import recommend_memory_gap


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _datetime_arg(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "must be an ISO-8601 datetime, for example 2026-09-08T00:00:00+00:00"
        ) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a deterministic, read-only Content Memory gap report."
    )
    parser.add_argument("--content-opportunity-id", required=True, type=_uuid_arg)
    parser.add_argument("--refresh-before", type=_datetime_arg)
    return parser


async def _run(args: argparse.Namespace) -> None:
    opportunity_id = cast(UUID, args.content_opportunity_id)
    refresh_before = cast(datetime | None, args.refresh_before)
    async with SessionLocal() as session:
        report = await recommend_memory_gap(
            session,
            content_opportunity_id=opportunity_id,
            refresh_before=refresh_before,
        )
    print(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
