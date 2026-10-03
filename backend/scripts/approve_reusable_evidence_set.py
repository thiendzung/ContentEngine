# ruff: noqa: E402

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from app.modules.content_engine.journal.operator_evidence_reuse import (
    approve_reusable_evidence_set,
)


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Approve one exact reusable EvidenceSet snapshot with the immutable "
            "nested snapshot binding required by Journal reuse."
        )
    )
    parser.add_argument("--evidence-set-id", required=True, type=_uuid_arg)
    parser.add_argument("--expected-version", required=True, type=_positive_int)
    parser.add_argument("--expected-content-hash", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--approval-reason", required=True)
    return parser


async def approve_reusable_evidence_set_for_operator(
    session: AsyncSession,
    *,
    evidence_set_id: UUID,
    expected_version: int,
    expected_content_hash: str,
    approved_by: str,
    approval_reason: str,
) -> dict[str, object]:
    approval = await approve_reusable_evidence_set(
        session,
        evidence_set_id=evidence_set_id,
        expected_version=expected_version,
        expected_content_hash=expected_content_hash,
        approved_by=approved_by,
        approval_reason=approval_reason,
    )
    return {
        "approval_id": str(approval.id),
        "evidence_set_id": str(approval.evidence_set_id),
        "version": approval.evidence_set_version,
        "content_hash": approval.evidence_set_content_hash,
        "approved_by": approval.approved_by,
        "provider_calls": 0,
    }


async def _run(args: argparse.Namespace) -> None:
    async with SessionLocal() as session:
        summary = await approve_reusable_evidence_set_for_operator(
            session,
            evidence_set_id=cast(UUID, args.evidence_set_id),
            expected_version=cast(int, args.expected_version),
            expected_content_hash=cast(str, args.expected_content_hash),
            approved_by=cast(str, args.approved_by),
            approval_reason=cast(str, args.approval_reason),
        )
        await session.commit()

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
