"""Extract Knowledge Candidates from one exact locked EvidenceSet."""

# ruff: noqa: E402

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from app.modules.knowledge.candidates import extract_knowledge_candidates


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract or reuse Knowledge Candidates from one locked EvidenceSet."
    )
    parser.add_argument("--evidence-set-id", required=True, type=_uuid_arg)
    return parser


async def _run(args: argparse.Namespace) -> None:
    evidence_set_id = cast(UUID, args.evidence_set_id)
    async with SessionLocal() as session:
        candidates = await extract_knowledge_candidates(
            session,
            evidence_set_id=evidence_set_id,
        )
        await session.commit()

    print(
        json.dumps(
            {
                "evidence_set_id": str(evidence_set_id),
                "candidate_ids": [str(candidate.id) for candidate in candidates],
                "candidate_count": len(candidates),
                "statuses": [candidate.status for candidate in candidates],
                "provider_calls": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
