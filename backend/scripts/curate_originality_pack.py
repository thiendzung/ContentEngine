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
from app.modules.research.evidence.contracts import (
    OriginalityMaterialInput,
    count_usable_originality_items,
)
from app.modules.research.evidence.persistence import build_originality_pack


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create or reuse one draft OriginalityPack from reviewed MOTGU-owned "
            "material without provider calls."
        )
    )
    parser.add_argument("--content-case-id", required=True, type=_uuid_arg)
    items = parser.add_mutually_exclusive_group(required=True)
    items.add_argument(
        "--item-json",
        dest="item_json",
        action="append",
        help="One JSON structured item; repeat for each reviewed material item.",
    )
    items.add_argument(
        "--items-file",
        type=Path,
        help="JSON file containing a list of structured material items.",
    )
    return parser


def _load_items(args: argparse.Namespace) -> list[OriginalityMaterialInput]:
    raw_items: object
    if args.items_file is not None:
        raw_items = json.loads(cast(Path, args.items_file).read_text(encoding="utf-8"))
    else:
        raw_items = [json.loads(raw_item) for raw_item in (args.item_json or [])]
    if not isinstance(raw_items, list):
        raise ValueError("originality_items_must_be_a_json_list")
    return cast(list[OriginalityMaterialInput], raw_items)


async def curate_originality_pack(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    items: list[OriginalityMaterialInput],
) -> dict[str, object]:
    pack = await build_originality_pack(
        session,
        content_case_id=content_case_id,
        motgu_material_refs=items,
    )
    return {
        "content_case_id": str(content_case_id),
        "originality_pack_id": str(pack.id),
        "status": pack.status,
        "item_refs": pack.item_refs_json,
        "item_count": len(pack.item_refs_json),
        "usable_item_count": count_usable_originality_items(pack.item_refs_json),
        "provider_calls": 0,
    }


async def _run(args: argparse.Namespace) -> None:
    async with SessionLocal() as session:
        summary = await curate_originality_pack(
            session,
            content_case_id=cast(UUID, args.content_case_id),
            items=_load_items(args),
        )
        await session.commit()

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
