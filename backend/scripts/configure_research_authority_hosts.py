from __future__ import annotations

import argparse
import asyncio
import json

from app.core.database import SessionLocal
from app.modules.system.research_authority import (
    ResearchAuthoritySettingsError,
    configure_research_authority_hosts,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Version and activate explicit research evidence-authority hosts."
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--host", action="append", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--reason", required=True)
    return parser


async def _run(args: argparse.Namespace) -> int:
    async with SessionLocal() as session:
        try:
            result = await configure_research_authority_hosts(
                session,
                project_slug=args.project,
                trusted_evidence_hosts=list(args.host),
                approved_by=args.approved_by,
                change_reason=args.reason,
            )
        except ResearchAuthoritySettingsError as exc:
            await session.rollback()
            print(json.dumps({"status": "BLOCKED", "code": exc.code}))
            return 2
        await session.commit()
        print(
            json.dumps(
                {
                    "status": "OK",
                    "project_id": str(result.project_id),
                    "settings_version_id": str(result.settings_version_id),
                    "version": result.version,
                    "trusted_evidence_hosts": list(result.trusted_evidence_hosts),
                    "replayed": result.replayed,
                },
                sort_keys=True,
            )
        )
        return 0


def main() -> int:
    return asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
