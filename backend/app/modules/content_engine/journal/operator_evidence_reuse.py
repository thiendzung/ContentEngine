from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import (
    Evidence,
    EvidenceSet,
    EvidenceSetApproval,
    Source,
    SourceDocument,
)
from app.modules.knowledge.persistence import content_hash, evidence_set_hash


@dataclass(frozen=True, slots=True)
class ReusableEvidenceSet:
    evidence_set: EvidenceSet
    relation_counts: dict[str, int]


class ReusableEvidenceSetError(ValueError):
    """Raised when a locked ContentCase EvidenceSet cannot be safely reused."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_FACTUAL_RELATIONS = {"supports", "qualifies"}
_ALLOWED_PROVENANCE_METHODS = {
    "read_excerpt_link",
    "human_review_existing_source",
}


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


async def load_latest_reusable_evidence_set(
    session: AsyncSession,
    *,
    project_id: UUID,
    content_case_id: UUID,
) -> ReusableEvidenceSet | None:
    """Return the latest exact approved+locked EvidenceSet, or None when absent.

    A locked snapshot is an explicit upstream decision, so malformed or unapproved
    locked state fails closed instead of silently falling back to fresh research.
    """

    evidence_set = await session.scalar(
        select(EvidenceSet)
        .where(
            EvidenceSet.project_id == project_id,
            EvidenceSet.content_case_id == content_case_id,
            EvidenceSet.status == "locked",
        )
        .order_by(
            EvidenceSet.version.desc(),
            EvidenceSet.created_at.desc(),
            EvidenceSet.id.desc(),
        )
        .limit(1)
    )
    if evidence_set is None:
        return None

    members = evidence_set.evidence_ids_json
    if (
        evidence_set.locked_at is None
        or not isinstance(members, list)
        or not members
        or not all(isinstance(value, str) and value.strip() for value in members)
        or evidence_set.content_hash != evidence_set_hash(members)
    ):
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_snapshot_invalid"
        )

    try:
        evidence_ids = [UUID(value) for value in members]
    except (TypeError, ValueError) as exc:
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_snapshot_invalid"
        ) from exc
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_snapshot_invalid"
        )

    approval = await session.scalar(
        select(EvidenceSetApproval).where(
            EvidenceSetApproval.evidence_set_id == evidence_set.id,
            EvidenceSetApproval.evidence_set_version == evidence_set.version,
            EvidenceSetApproval.evidence_set_content_hash == evidence_set.content_hash,
        )
    )
    if approval is None:
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_approval_missing"
        )
    if (
        not isinstance(approval.approved_by, str)
        or not approval.approved_by.strip()
        or not isinstance(approval.approval_reason, str)
        or not approval.approval_reason.strip()
    ):
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_approval_invalid"
        )

    evidence_rows = list(
        (
            await session.scalars(
                select(Evidence).where(Evidence.id.in_(evidence_ids))
            )
        ).all()
    )
    if len(evidence_rows) != len(evidence_ids) or {
        row.id for row in evidence_rows
    } != set(evidence_ids):
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_member_invalid"
        )

    document_ids = {
        row.source_document_id
        for row in evidence_rows
        if row.source_document_id is not None
    }
    documents = list(
        (
            await session.scalars(
                select(SourceDocument).where(SourceDocument.id.in_(document_ids))
            )
        ).all()
    )
    documents_by_id = {document.id: document for document in documents}
    if len(documents_by_id) != len(document_ids):
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_document_invalid"
        )

    source_ids = {document.source_id for document in documents}
    sources = list(
        (await session.scalars(select(Source).where(Source.id.in_(source_ids)))).all()
    )
    sources_by_id = {source.id: source for source in sources}
    if len(sources_by_id) != len(source_ids):
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_source_invalid"
        )

    relation_counts = Counter(row.relation for row in evidence_rows)
    factual_support = False
    for evidence in evidence_rows:
        if (
            evidence.source_document_id is None
            or evidence.verified_at is None
            or evidence.relation not in {
                "supports",
                "qualifies",
                "contradicts",
                "context_only",
            }
        ):
            raise ReusableEvidenceSetError(
                "operator_worker_reusable_evidence_member_invalid"
            )

        document = documents_by_id.get(evidence.source_document_id)
        provenance = evidence.provenance_json
        if document is None or not isinstance(provenance, dict):
            raise ReusableEvidenceSetError(
                "operator_worker_reusable_evidence_provenance_invalid"
            )
        source = sources_by_id.get(document.source_id)
        if (
            source is None
            or source.project_id != project_id
            or not isinstance(document.content_markdown, str)
            or document.content_hash != content_hash(document.content_markdown)
        ):
            raise ReusableEvidenceSetError(
                "operator_worker_reusable_evidence_document_invalid"
            )

        method = provenance.get("method")
        if (
            method not in _ALLOWED_PROVENANCE_METHODS
            or provenance.get("source_document_id") != str(document.id)
            or provenance.get("source_document_hash") != document.content_hash
            or not isinstance(evidence.excerpt, str)
            or not evidence.excerpt.strip()
            or _normalized_text(evidence.excerpt)
            not in _normalized_text(document.content_markdown)
        ):
            raise ReusableEvidenceSetError(
                "operator_worker_reusable_evidence_provenance_invalid"
            )

        if method == "human_review_existing_source":
            quality = evidence.quality_metadata_json
            reviewer = provenance.get("reviewed_by")
            if (
                not isinstance(quality, dict)
                or quality.get("human_reviewed") is not True
                or not isinstance(reviewer, str)
                or not reviewer.strip()
                or quality.get("reviewed_by") != reviewer
            ):
                raise ReusableEvidenceSetError(
                    "operator_worker_reusable_evidence_review_invalid"
                )

        factual_support = factual_support or evidence.relation in _FACTUAL_RELATIONS

    if not factual_support:
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_no_factual_support"
        )
    return ReusableEvidenceSet(
        evidence_set=evidence_set,
        relation_counts={
            relation: relation_counts.get(relation, 0)
            for relation in ("supports", "qualifies", "contradicts", "context_only")
        },
    )
