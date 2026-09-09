# ruff: noqa: E402

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from app.modules.research.evidence.persistence import lock_evidence_set


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lock one exact reviewed CE04 EvidenceSet without provider calls."
    )
    parser.add_argument("--evidence-set-id", required=True)
    parser.add_argument("--locked-by", required=True)
    parser.add_argument("--approval-id", type=UUID)
    return parser


async def _run(args: argparse.Namespace) -> None:
    evidence_set_id = UUID(str(args.evidence_set_id))
    async with SessionLocal() as session:
        evidence_set = await lock_evidence_set(
            session,
            evidence_set_id=evidence_set_id,
            locked_by=str(args.locked_by),
            approval_id=args.approval_id,
        )
        await session.commit()

    print(
        json.dumps(
            {
                "evidence_set_id": str(evidence_set.id),
                "version": evidence_set.version,
                "status": evidence_set.status,
                "locked_by": evidence_set.locked_by,
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
