"""Apply one human admission decision to a KnowledgeCandidate."""

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
from app.modules.knowledge.admission import admit_knowledge_candidate
from app.modules.knowledge.models import KnowledgeCandidate


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _non_empty_arg(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply a verified human decision to one KnowledgeCandidate."
    )
    parser.add_argument("--candidate-id", required=True, type=_uuid_arg)
    parser.add_argument("--decision", required=True, choices=("approve", "reject"))
    parser.add_argument("--reviewer", required=True, type=_non_empty_arg)
    parser.add_argument("--review-reason", required=True, type=_non_empty_arg)
    parser.add_argument("--expected-content-hash", required=True, type=_non_empty_arg)
    return parser


async def _run(args: argparse.Namespace) -> None:
    candidate_id = cast(UUID, args.candidate_id)
    async with SessionLocal() as session:
        before = await session.get(KnowledgeCandidate, candidate_id)
        previous_status = before.status if before is not None else None
        candidate = await admit_knowledge_candidate(
            session,
            candidate_id=candidate_id,
            decision=cast(str, args.decision),
            reviewer=cast(str, args.reviewer),
            review_reason=cast(str, args.review_reason),
            expected_candidate_content_hash=cast(str, args.expected_content_hash),
        )
        await session.commit()

    print(
        json.dumps(
            {
                "candidate_id": str(candidate.id),
                "previous_status": previous_status,
                "status": candidate.status,
                "reviewer": candidate.reviewer,
                "review_reason": candidate.review_reason,
                "candidate_content_hash": candidate.provenance_json[
                    "candidate_content_hash"
                ],
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
