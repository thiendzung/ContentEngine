"""Persist and verify one exact Founder-approved Journal Outline snapshot."""

# ruff: noqa: E402

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from app.modules.content_engine.journal.outline_approval import (
    approve_outline_artifact,
    handoff_approved_outline,
)

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _positive_int_arg(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _non_empty_arg(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return value.strip()


def _hash_arg(value: str) -> str:
    normalized = value.strip().lower()
    if _HASH_PATTERN.fullmatch(normalized) is None:
        raise argparse.ArgumentTypeError("must be a 64-character lowercase SHA-256 hex value")
    return normalized


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist and verify one exact human-approved Journal Outline snapshot."
    )
    parser.add_argument("--outline-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--expected-artifact-version", required=True, type=_positive_int_arg)
    parser.add_argument("--expected-artifact-hash", required=True, type=_hash_arg)
    parser.add_argument("--approved-by", required=True, type=_non_empty_arg)
    parser.add_argument("--approval-reason", required=True, type=_non_empty_arg)
    return parser


async def _run(args: argparse.Namespace) -> None:
    outline_artifact_id = cast(UUID, args.outline_artifact_id)
    artifact_version = cast(int, args.expected_artifact_version)
    artifact_hash = cast(str, args.expected_artifact_hash)

    async with SessionLocal() as session:
        approval = await approve_outline_artifact(
            session,
            outline_artifact_id=outline_artifact_id,
            expected_artifact_version=artifact_version,
            expected_artifact_hash=artifact_hash,
            approved_by=cast(str, args.approved_by),
            approval_reason=cast(str, args.approval_reason),
        )
        await session.commit()
        approval_id = approval.id

    async with SessionLocal() as session:
        handoff = await handoff_approved_outline(
            session,
            outline_artifact_id=outline_artifact_id,
            expected_artifact_version=artifact_version,
            expected_artifact_hash=artifact_hash,
            expected_approval_id=approval_id,
        )

    print(
        json.dumps(
            {
                "approval_id": str(handoff.approval.id),
                "run_id": str(handoff.approval.run_id),
                "outline_artifact_id": str(handoff.artifact.id),
                "outline_artifact_version": handoff.artifact.version,
                "outline_artifact_hash": handoff.artifact.content_hash,
                "approved_by": handoff.approval.approved_by,
                "approval_reason": handoff.approval.approval_reason,
                "handoff_verified": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
