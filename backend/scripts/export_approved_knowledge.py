"""Export one approved KnowledgeCandidate to an explicit Obsidian vault path."""

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
from app.modules.knowledge.obsidian import export_approved_knowledge


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export one approved KnowledgeCandidate to an Obsidian vault."
    )
    parser.add_argument("--candidate-id", required=True, type=_uuid_arg)
    parser.add_argument("--vault-path", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser


async def _run(args: argparse.Namespace) -> None:
    candidate_id = cast(UUID, args.candidate_id)
    vault_path = cast(Path, args.vault_path)
    async with SessionLocal() as session:
        result = await export_approved_knowledge(
            session,
            candidate_id=candidate_id,
            vault_path=vault_path,
            dry_run=bool(args.dry_run),
        )
    print(
        json.dumps(
            {
                "candidate_id": str(result.candidate_id),
                "path": str(result.path),
                "dry_run": result.dry_run,
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
