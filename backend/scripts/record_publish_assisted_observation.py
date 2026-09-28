from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from app.core.database import SessionLocal
from app.modules.publishing.assisted import record_publish_assisted_observation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record one publish-assisted operational observation."
    )
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--phase", choices=("draft", "published"), required=True)
    parser.add_argument("--actor-id", default="founder")
    parser.add_argument("--content-file", required=True)
    parser.add_argument("--source-artifact-id")
    parser.add_argument("--canonical-url")
    parser.add_argument("--external-id")
    parser.add_argument("--note")
    return parser


async def _run(args: argparse.Namespace) -> None:
    content_path = Path(args.content_file)
    content = content_path.read_text(encoding="utf-8")
    async with SessionLocal() as session:
        async with session.begin():
            result = await record_publish_assisted_observation(
                session,
                source_run_id=UUID(args.source_run_id),
                phase=args.phase,
                actor_id=args.actor_id,
                content_markdown=content,
                source_artifact_id=(
                    UUID(args.source_artifact_id)
                    if args.source_artifact_id
                    else None
                ),
                canonical_url=args.canonical_url,
                external_id=args.external_id,
                note=args.note,
            )
        artifact = result.artifact
        print(
            json.dumps(
                {
                    "status": "ok",
                    "artifact_id": str(artifact.id),
                    "version": artifact.version,
                    "content_hash": artifact.content_hash,
                    "phase": args.phase,
                    "replayed": result.replayed,
                },
                sort_keys=True,
            )
        )


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
