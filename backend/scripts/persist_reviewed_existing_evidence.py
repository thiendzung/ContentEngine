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
from app.modules.research.evidence.contracts import EvidenceRelation
from app.modules.research.evidence.reviewed_source import (
    persist_reviewed_existing_source_evidence,
)


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Persist one human-reviewed Claim/Evidence link from an already stored "
            "SourceDocument with zero provider calls."
        )
    )
    parser.add_argument("--content-case-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-document-id", required=True, type=_uuid_arg)
    parser.add_argument("--statement", required=True)
    parser.add_argument("--excerpt", required=True)
    parser.add_argument(
        "--relation",
        default=EvidenceRelation.SUPPORTS.value,
        choices=[relation.value for relation in EvidenceRelation],
    )
    parser.add_argument("--reviewed-by", required=True)
    return parser


async def _run(args: argparse.Namespace) -> None:
    async with SessionLocal() as session:
        link = await persist_reviewed_existing_source_evidence(
            session,
            content_case_id=cast(UUID, args.content_case_id),
            source_document_id=cast(UUID, args.source_document_id),
            statement=cast(str, args.statement),
            excerpt=cast(str, args.excerpt),
            relation=EvidenceRelation(cast(str, args.relation)),
            reviewed_by=cast(str, args.reviewed_by),
        )
        await session.commit()

    print(
        json.dumps(
            {
                "claim_id": str(link.claim_id),
                "evidence_id": str(link.evidence_id),
                "relation": link.relation.value,
                "source_document_id": str(args.source_document_id),
                "content_case_id": str(args.content_case_id),
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
