from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.evidence_set_approval import approve_evidence_set
from app.modules.knowledge.models import (
    Claim,
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
_REUSE_SNAPSHOT_MARKER = "contentengine-reuse-snapshot-v1-sha256:"


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


async def _reusable_snapshot_hash(
    session: AsyncSession,
    *,
    evidence_set: EvidenceSet,
) -> str:
    members = evidence_set.evidence_ids_json
    if not isinstance(members, list) or not members:
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

    evidence_rows = list(
        (
            await session.scalars(
                select(Evidence).where(Evidence.id.in_(evidence_ids))
            )
        ).all()
    )
    evidence_by_id = {row.id: row for row in evidence_rows}
    if set(evidence_by_id) != set(evidence_ids):
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_member_invalid"
        )

    claim_ids = {row.claim_id for row in evidence_rows}
    claims = list(
        (await session.scalars(select(Claim).where(Claim.id.in_(claim_ids)))).all()
    )
    claims_by_id = {row.id: row for row in claims}
    if len(claims_by_id) != len(claim_ids):
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

    snapshot_members: list[dict[str, object]] = []
    for evidence_id in evidence_ids:
        evidence = evidence_by_id[evidence_id]
        claim = claims_by_id.get(evidence.claim_id)
        document = (
            documents_by_id.get(evidence.source_document_id)
            if evidence.source_document_id is not None
            else None
        )
        source = sources_by_id.get(document.source_id) if document is not None else None
        provenance = evidence.provenance_json
        if (
            claim is None
            or claim.project_id != evidence_set.project_id
            or document is None
            or source is None
            or source.project_id != evidence_set.project_id
            or evidence.verified_at is None
            or not isinstance(provenance, dict)
            or not isinstance(evidence.quality_metadata_json, dict)
            or not isinstance(document.content_markdown, str)
            or document.content_hash != content_hash(document.content_markdown)
            or not isinstance(evidence.excerpt, str)
            or not evidence.excerpt.strip()
            or _normalized_text(evidence.excerpt)
            not in _normalized_text(document.content_markdown)
        ):
            raise ReusableEvidenceSetError(
                "operator_worker_reusable_evidence_snapshot_invalid"
            )

        method = provenance.get("method")
        if (
            method not in _ALLOWED_PROVENANCE_METHODS
            or provenance.get("source_document_id") != str(document.id)
            or provenance.get("source_document_hash") != document.content_hash
        ):
            raise ReusableEvidenceSetError(
                "operator_worker_reusable_evidence_provenance_invalid"
            )
        if method == "human_review_existing_source":
            reviewer = provenance.get("reviewed_by")
            if (
                evidence.quality_metadata_json.get("human_reviewed") is not True
                or not isinstance(reviewer, str)
                or not reviewer.strip()
                or evidence.quality_metadata_json.get("reviewed_by") != reviewer
            ):
                raise ReusableEvidenceSetError(
                    "operator_worker_reusable_evidence_review_invalid"
                )

        snapshot_members.append(
            {
                "evidence": {
                    "id": str(evidence.id),
                    "claim_id": str(evidence.claim_id),
                    "source_document_id": str(evidence.source_document_id),
                    "chunk_id": (
                        str(evidence.chunk_id) if evidence.chunk_id is not None else None
                    ),
                    "media_observation_id": (
                        str(evidence.media_observation_id)
                        if evidence.media_observation_id is not None
                        else None
                    ),
                    "locator": evidence.locator,
                    "excerpt": evidence.excerpt,
                    "relation": evidence.relation,
                    "authority_level": evidence.authority_level,
                    "quality_metadata": evidence.quality_metadata_json,
                    "provenance": provenance,
                    "verified_at": _iso(evidence.verified_at),
                },
                "claim": {
                    "id": str(claim.id),
                    "project_id": str(claim.project_id),
                    "subject_entity_id": (
                        str(claim.subject_entity_id)
                        if claim.subject_entity_id is not None
                        else None
                    ),
                    "statement": claim.statement,
                    "claim_type": claim.claim_type,
                    "importance": claim.importance,
                    "status": claim.status,
                    "confidence": claim.confidence,
                    "entity_refs": claim.entity_refs_json,
                },
                "source_document": {
                    "id": str(document.id),
                    "source_id": str(document.source_id),
                    "document_version": document.document_version,
                    "canonical_url": document.canonical_url,
                    "fetched_at": _iso(document.fetched_at),
                    "content_hash": document.content_hash,
                    "metadata": document.metadata_json,
                    "reader": document.reader,
                    "provider": document.provider,
                    "supersedes_id": (
                        str(document.supersedes_id)
                        if document.supersedes_id is not None
                        else None
                    ),
                },
                "source": {
                    "id": str(source.id),
                    "project_id": str(source.project_id),
                    "source_type": source.source_type,
                    "title": source.title,
                    "publisher": source.publisher,
                    "author": source.author,
                    "canonical_url": source.canonical_url,
                    "locator": source.locator,
                    "locale": source.locale,
                    "commercial_bias": source.commercial_bias,
                    "authority_hint": source.authority_hint,
                    "provenance": source.provenance_json,
                    "captured_at": _iso(source.captured_at),
                    "fingerprint": source.fingerprint,
                },
            }
        )

    return _canonical_hash(
        {
            "schema_version": 1,
            "evidence_set": {
                "id": str(evidence_set.id),
                "project_id": str(evidence_set.project_id),
                "content_case_id": (
                    str(evidence_set.content_case_id)
                    if evidence_set.content_case_id is not None
                    else None
                ),
                "version": evidence_set.version,
                "evidence_ids": members,
                "content_hash": evidence_set.content_hash,
            },
            "members": snapshot_members,
        }
    )


def _approval_snapshot_hash(approval: EvidenceSetApproval) -> str:
    reason = approval.approval_reason
    if not isinstance(reason, str):
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_approval_invalid"
        )
    matches = re.findall(
        rf"(?m)^{re.escape(_REUSE_SNAPSHOT_MARKER)}([0-9a-f]{{64}})$",
        reason,
    )
    if len(matches) != 1:
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_approval_snapshot_missing"
        )
    return matches[0]


async def approve_reusable_evidence_set(
    session: AsyncSession,
    *,
    evidence_set_id: UUID,
    expected_version: int,
    expected_content_hash: str,
    approved_by: str,
    approval_reason: str,
) -> EvidenceSetApproval:
    """Approve one exact reusable EvidenceSet and bind all reachable factual bytes."""

    reason = approval_reason.strip()
    if not reason:
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_approval_reason_required"
        )
    if _REUSE_SNAPSHOT_MARKER in reason:
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_approval_reason_invalid"
        )
    evidence_set = await session.get(EvidenceSet, evidence_set_id)
    if evidence_set is None:
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_snapshot_invalid"
        )
    snapshot_hash = await _reusable_snapshot_hash(
        session,
        evidence_set=evidence_set,
    )
    return await approve_evidence_set(
        session,
        evidence_set_id=evidence_set_id,
        expected_version=expected_version,
        expected_content_hash=expected_content_hash,
        approved_by=approved_by,
        approval_reason=(
            f"{reason}\n{_REUSE_SNAPSHOT_MARKER}{snapshot_hash}"
        ),
    )


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
        or not isinstance(evidence_set.locked_by, str)
        or not evidence_set.locked_by.strip()
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
    approved_snapshot_hash = _approval_snapshot_hash(approval)

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

    current_snapshot_hash = await _reusable_snapshot_hash(
        session,
        evidence_set=evidence_set,
    )
    if current_snapshot_hash != approved_snapshot_hash:
        raise ReusableEvidenceSetError(
            "operator_worker_reusable_evidence_approval_snapshot_mismatch"
        )

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
