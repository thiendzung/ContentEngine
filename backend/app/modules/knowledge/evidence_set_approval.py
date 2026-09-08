from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import EvidenceSet, EvidenceSetApproval
from app.modules.knowledge.persistence import evidence_set_hash

_CONTENT_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class EvidenceSetApprovalError(ValueError):
    pass


def _require_text(value: str, error: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise EvidenceSetApprovalError(error)
    return normalized


def _is_content_hash(value: object) -> bool:
    return isinstance(value, str) and _CONTENT_HASH_PATTERN.fullmatch(value) is not None


async def approve_evidence_set(
    session: AsyncSession,
    *,
    evidence_set_id: UUID,
    expected_version: int,
    expected_content_hash: str,
    approved_by: str,
    approval_reason: str,
) -> EvidenceSetApproval:
    """Persist an immutable human approval for one exact draft EvidenceSet snapshot."""
    approver = _require_text(approved_by, "evidence_set_approver_required")
    reason = _require_text(approval_reason, "evidence_set_approval_reason_required")

    evidence_set = await session.scalar(
        select(EvidenceSet)
        .where(EvidenceSet.id == evidence_set_id)
        .with_for_update()
    )
    if evidence_set is None:
        raise EvidenceSetApprovalError("evidence_set_not_found")
    if evidence_set.status != "draft":
        raise EvidenceSetApprovalError("evidence_set_approval_requires_draft_evidence_set")
    if not isinstance(evidence_set.evidence_ids_json, list) or not evidence_set.evidence_ids_json:
        raise EvidenceSetApprovalError("evidence_set_approval_requires_evidence")
    if not all(isinstance(evidence_id, str) for evidence_id in evidence_set.evidence_ids_json):
        raise EvidenceSetApprovalError("evidence_set_content_hash_invalid")
    if expected_version != evidence_set.version:
        raise EvidenceSetApprovalError("evidence_set_approval_version_mismatch")

    recomputed_content_hash = evidence_set_hash(evidence_set.evidence_ids_json)
    if (
        not _is_content_hash(evidence_set.content_hash)
        or evidence_set.content_hash != recomputed_content_hash
    ):
        raise EvidenceSetApprovalError("evidence_set_content_hash_invalid")
    if (
        not _is_content_hash(expected_content_hash)
        or expected_content_hash != evidence_set.content_hash
    ):
        raise EvidenceSetApprovalError("evidence_set_approval_hash_mismatch")

    existing = await session.scalar(
        select(EvidenceSetApproval).where(
            EvidenceSetApproval.evidence_set_id == evidence_set.id,
            EvidenceSetApproval.evidence_set_version == evidence_set.version,
            EvidenceSetApproval.evidence_set_content_hash == evidence_set.content_hash,
        )
    )
    if existing is not None:
        if (
            existing.approved_by == approver
            and existing.approval_reason == reason
        ):
            return existing
        raise EvidenceSetApprovalError("evidence_set_approval_conflict")

    approval = EvidenceSetApproval(
        evidence_set_id=evidence_set.id,
        evidence_set_version=evidence_set.version,
        evidence_set_content_hash=evidence_set.content_hash,
        approved_by=approver,
        approval_reason=reason,
        approved_at=datetime.now(UTC),
    )
    session.add(approval)
    await session.flush()
    return approval
