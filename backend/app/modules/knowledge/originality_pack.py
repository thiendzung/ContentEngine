"""Approval and snapshot identity helpers for MOTGU OriginalityPack records."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import OriginalityPack
from app.modules.research.evidence.contracts import count_usable_originality_items

_CONTENT_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class OriginalityPackApprovalError(ValueError):
    """Raised when a pack cannot receive or retain an exact approval."""


def originality_pack_snapshot_hash(pack: OriginalityPack) -> str:
    """Hash the pack identity and content, excluding mutable approval metadata."""

    payload = {
        "id": str(pack.id),
        "content_case_id": str(pack.content_case_id),
        "item_refs": pack.item_refs_json,
        "summary": pack.summary,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_text(value: str, error: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise OriginalityPackApprovalError(error)
    return normalized


def _is_content_hash(value: object) -> bool:
    return isinstance(value, str) and _CONTENT_HASH_PATTERN.fullmatch(value) is not None


async def approve_originality_pack(
    session: AsyncSession,
    *,
    originality_pack_id: UUID,
    expected_snapshot_hash: str,
    approved_by: str,
    approval_reason: str,
) -> OriginalityPack:
    """Approve one exact draft pack snapshot with durable reviewer metadata."""

    approver = _require_text(approved_by, "originality_pack_approver_required")
    reason = _require_text(approval_reason, "originality_pack_approval_reason_required")
    if not _is_content_hash(expected_snapshot_hash):
        raise OriginalityPackApprovalError("originality_pack_snapshot_hash_invalid")

    pack = await session.scalar(
        select(OriginalityPack)
        .where(OriginalityPack.id == originality_pack_id)
        .with_for_update()
    )
    if pack is None:
        raise OriginalityPackApprovalError("originality_pack_not_found")
    if pack.status == "retired":
        raise OriginalityPackApprovalError("originality_pack_retired")

    current_hash = originality_pack_snapshot_hash(pack)
    if pack.status == "approved":
        if (
            pack.snapshot_hash == current_hash
            and pack.snapshot_hash == expected_snapshot_hash
            and pack.approved_by == approver
            and pack.approval_reason == reason
        ):
            return pack
        raise OriginalityPackApprovalError("originality_pack_approval_conflict")
    if pack.status != "draft":
        raise OriginalityPackApprovalError("originality_pack_status_not_approvable")
    if count_usable_originality_items(pack.item_refs_json) == 0:
        raise OriginalityPackApprovalError("originality_pack_motgu_material_required")
    if current_hash != expected_snapshot_hash:
        raise OriginalityPackApprovalError("originality_pack_snapshot_hash_mismatch")

    pack.status = "approved"
    pack.approved_at = datetime.now(UTC)
    pack.approved_by = approver
    pack.approval_reason = reason
    pack.snapshot_hash = current_hash
    await session.flush()
    return pack


__all__ = [
    "OriginalityPackApprovalError",
    "approve_originality_pack",
    "originality_pack_snapshot_hash",
]
