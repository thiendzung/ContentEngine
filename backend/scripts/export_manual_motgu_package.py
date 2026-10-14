"""Export a Founder-authored article to MOTGU CONTENT02 without model/DB/provider calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.modules.content_engine.manual_motgu_handoff import (
    ManualMotguHandoffError,
    build_manual_motgu_handoff,
    write_manual_motgu_handoff,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build one deterministic HUMAN-authored MOTGU CONTENT02 package."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance-output", type=Path, required=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Explicitly allow replacing existing output files.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        raw = args.input.read_text(encoding="utf-8")
        source = json.loads(raw)
        if not isinstance(source, dict):
            raise ManualMotguHandoffError("manual_handoff_source_invalid")
        handoff = build_manual_motgu_handoff(source)
        write_manual_motgu_handoff(
            handoff,
            package_path=args.output,
            provenance_path=args.provenance_output,
            overwrite=args.force,
        )
    except (OSError, json.JSONDecodeError, ManualMotguHandoffError) as exc:
        code = (
            exc.code
            if isinstance(exc, ManualMotguHandoffError)
            else "manual_handoff_input_invalid"
        )
        print(json.dumps({"ok": False, "error": code}, sort_keys=True))
        return 2

    print(
        json.dumps(
            {
                "ok": True,
                "content_id": handoff.package["content_id"],
                "package_version": str(handoff.package["package_version"]),
                "package_hash": handoff.package["package_hash"],
                "package_bytes": handoff.provenance["package_bytes"],
                "authoring_provenance": "HUMAN",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
