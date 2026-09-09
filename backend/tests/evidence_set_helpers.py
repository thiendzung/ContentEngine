from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.evidence_set_approval import approve_evidence_set
from app.modules.knowledge.models import EvidenceSet
from app.modules.knowledge.persistence import evidence_set_hash
from app.modules.research.evidence.persistence import lock_evidence_set


async def create_locked_evidence_set(
    session: AsyncSession,
    *,
    project_id: UUID,
    evidence_ids: list[str],
    content_case_id: UUID | None = None,
    version: int = 1,
    locked_by: str = "fixture reviewer",
) -> EvidenceSet:
    evidence_set = EvidenceSet(
        project_id=project_id,
        content_case_id=content_case_id,
        version=version,
        evidence_ids_json=evidence_ids,
        content_hash=evidence_set_hash(evidence_ids),
        status="draft",
    )
    session.add(evidence_set)
    await session.flush()
    approval = await approve_evidence_set(
        session,
        evidence_set_id=evidence_set.id,
        expected_version=evidence_set.version,
        expected_content_hash=evidence_set.content_hash,
        approved_by=locked_by,
        approval_reason="Fixture snapshot approved for this test.",
    )
    return await lock_evidence_set(
        session,
        evidence_set_id=evidence_set.id,
        locked_by=locked_by,
        approval_id=approval.id,
    )
