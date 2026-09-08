# ruff: noqa: E402

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from app.modules.content_engine.models import ContentCase
from app.modules.knowledge.models import Evidence
from app.modules.research.evidence.contracts import EvidenceRelation
from app.modules.research.evidence.persistence import create_or_reuse_evidence_set


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create or reuse one draft EvidenceSet from reviewed Evidence IDs "
            "without provider calls."
        )
    )
    parser.add_argument("--content-case-id", required=True, type=_uuid_arg)
    parser.add_argument(
        "--evidence-id",
        dest="evidence_ids",
        required=True,
        action="append",
        type=_uuid_arg,
        help="Reviewed Evidence ID; repeat for each selected row.",
    )
    return parser


async def curate_evidence_set(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    evidence_ids: list[UUID],
) -> dict[str, object]:
    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None:
        raise ValueError("curation_content_case_not_found")

    evidence_set = await create_or_reuse_evidence_set(
        session,
        project_id=content_case.project_id,
        content_case_id=content_case.id,
        evidence_ids=evidence_ids,
    )
    normalized_ids = [UUID(value) for value in evidence_set.evidence_ids_json]
    rows = tuple(
        (
            await session.execute(select(Evidence).where(Evidence.id.in_(normalized_ids)))
        )
        .scalars()
        .all()
    )
    relation_counts = Counter(row.relation for row in rows)
    source_document_count = len(
        {row.source_document_id for row in rows if row.source_document_id is not None}
    )
    return {
        "content_case_id": str(content_case.id),
        "evidence_set_id": str(evidence_set.id),
        "version": evidence_set.version,
        "status": evidence_set.status,
        "evidence_ids": list(evidence_set.evidence_ids_json),
        "relation_counts": {
            relation.value: relation_counts.get(relation.value, 0)
            for relation in EvidenceRelation
        },
        "source_document_count": source_document_count,
        "provider_calls": 0,
    }


async def _run(args: argparse.Namespace) -> None:
    content_case_id = cast(UUID, args.content_case_id)
    evidence_ids = [cast(UUID, value) for value in args.evidence_ids]
    async with SessionLocal() as session:
        summary = await curate_evidence_set(
            session,
            content_case_id=content_case_id,
            evidence_ids=evidence_ids,
        )
        await session.commit()

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
