"""Knowledge Candidate extraction from an exact locked EvidenceSet."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import ContentCase, ContentOpportunity
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    EvidenceSet,
    KnowledgeCandidate,
    KnowledgeChunk,
    MediaAsset,
    MediaObservation,
    Source,
    SourceDocument,
)

EXTRACTION_METHOD = "locked_evidence_set_extraction"
_RELATIONS = ("supports", "contradicts", "qualifies", "context_only")
_CANDIDATE_NAMESPACE = UUID("15efccae-584a-4d9e-9862-101b2cc09cf1")
_RAW_PROVENANCE_KEYS = {
    "body",
    "html",
    "payload",
    "raw",
    "raw_payload",
    "raw_response",
    "response",
    "result",
}


@dataclass(frozen=True)
class _EvidenceContext:
    evidence: Evidence
    source_document_ids: tuple[UUID, ...]
    source_ids: tuple[UUID, ...]


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _safe_provenance(value: object) -> object:
    """Keep audit metadata while excluding raw provider/page payload fields."""

    if isinstance(value, dict):
        return {
            str(key): _safe_provenance(item)
            for key, item in value.items()
            if str(key).casefold() not in _RAW_PROVENANCE_KEYS
        }
    if isinstance(value, list):
        return [_safe_provenance(item) for item in value]
    return value


def stable_knowledge_candidate_id(*, candidate_content_hash: str) -> UUID:
    """Return the deterministic identity for one candidate snapshot."""

    return uuid5(
        _CANDIDATE_NAMESPACE,
        f"contentengine:knowledge-candidate:{candidate_content_hash}",
    )


def deterministic_candidate_summary(
    *, statement: str, relation_counts: dict[str, int]
) -> str:
    """Build a bounded, provider-free summary from persisted values only."""

    return (
        f"{statement} "
        "[locked EvidenceSet relations: "
        f"supports={relation_counts['supports']}, "
        f"contradicts={relation_counts['contradicts']}, "
        f"qualifies={relation_counts['qualifies']}, "
        f"context_only={relation_counts['context_only']}]"
    )


async def _source_document_context(
    session: AsyncSession,
    *,
    source_document_id: UUID,
    evidence_set_project_id: UUID,
) -> tuple[UUID, UUID]:
    document = await session.get(SourceDocument, source_document_id)
    if document is None:
        raise ValueError("candidate_source_document_not_found")
    source = await session.get(Source, document.source_id)
    if source is None:
        raise ValueError("candidate_source_not_found")
    if source.project_id != evidence_set_project_id:
        raise ValueError("candidate_source_project_mismatch")
    return document.id, source.id


async def _resolve_evidence_context(
    session: AsyncSession,
    *,
    evidence: Evidence,
    evidence_set_project_id: UUID,
) -> _EvidenceContext:
    source_document_ids: set[UUID] = set()
    source_ids: set[UUID] = set()

    if evidence.source_document_id is not None:
        document_id, source_id = await _source_document_context(
            session,
            source_document_id=evidence.source_document_id,
            evidence_set_project_id=evidence_set_project_id,
        )
        source_document_ids.add(document_id)
        source_ids.add(source_id)

    if evidence.chunk_id is not None:
        chunk = await session.get(KnowledgeChunk, evidence.chunk_id)
        if chunk is None:
            raise ValueError("candidate_knowledge_chunk_not_found")
        document_id, source_id = await _source_document_context(
            session,
            source_document_id=chunk.source_document_id,
            evidence_set_project_id=evidence_set_project_id,
        )
        source_document_ids.add(document_id)
        source_ids.add(source_id)

    if evidence.media_observation_id is not None:
        observation = await session.get(MediaObservation, evidence.media_observation_id)
        if observation is None:
            raise ValueError("candidate_media_observation_not_found")
        asset = await session.get(MediaAsset, observation.media_asset_id)
        if asset is None:
            raise ValueError("candidate_media_asset_not_found")
        source = await session.get(Source, asset.source_id)
        if source is None:
            raise ValueError("candidate_source_not_found")
        if (
            asset.project_id != evidence_set_project_id
            or source.project_id != evidence_set_project_id
        ):
            raise ValueError("candidate_media_source_project_mismatch")
        source_ids.add(source.id)

    if not source_ids:
        raise ValueError("candidate_evidence_source_required")

    return _EvidenceContext(
        evidence=evidence,
        source_document_ids=tuple(sorted(source_document_ids, key=str)),
        source_ids=tuple(sorted(source_ids, key=str)),
    )


async def _load_locked_evidence_set(
    session: AsyncSession,
    *,
    evidence_set_id: UUID,
) -> tuple[EvidenceSet, ContentCase, str | None, list[_EvidenceContext]]:
    evidence_set = await session.get(EvidenceSet, evidence_set_id)
    if evidence_set is None:
        raise ValueError("candidate_evidence_set_not_found")
    if evidence_set.status != "locked":
        raise ValueError("candidate_requires_locked_evidence_set")
    if evidence_set.locked_at is None:
        raise ValueError("candidate_locked_evidence_set_missing_lock_timestamp")
    if evidence_set.content_case_id is None:
        raise ValueError("candidate_content_case_required")

    content_case = await session.get(ContentCase, evidence_set.content_case_id)
    if content_case is None:
        raise ValueError("candidate_content_case_not_found")
    if content_case.project_id != evidence_set.project_id:
        raise ValueError("candidate_content_case_project_mismatch")

    locale: str | None = None
    opportunity = await session.get(ContentOpportunity, content_case.content_opportunity_id)
    if opportunity is None:
        raise ValueError("candidate_content_opportunity_not_found")
    if opportunity.project_id != evidence_set.project_id:
        raise ValueError("candidate_content_opportunity_project_mismatch")
    locale = opportunity.locale

    raw_ids = evidence_set.evidence_ids_json
    if not raw_ids:
        raise ValueError("candidate_evidence_set_empty")
    if any(not isinstance(value, str) for value in raw_ids):
        raise ValueError("candidate_evidence_set_invalid_evidence_id")
    try:
        evidence_ids = [UUID(value) for value in raw_ids]
    except ValueError as exc:
        raise ValueError("candidate_evidence_set_invalid_evidence_id") from exc
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ValueError("candidate_evidence_set_duplicate_evidence_id")

    rows = tuple(
        (
            await session.execute(select(Evidence).where(Evidence.id.in_(evidence_ids)))
        )
        .scalars()
        .all()
    )
    if len(rows) != len(evidence_ids):
        raise ValueError("candidate_evidence_not_found")
    row_by_id = {row.id: row for row in rows}

    claim_ids = {row.claim_id for row in rows}
    claims = {
        claim.id: claim
        for claim in (
            await session.execute(select(Claim).where(Claim.id.in_(claim_ids)))
        )
        .scalars()
        .all()
    }
    if len(claims) != len(claim_ids):
        raise ValueError("candidate_claim_not_found")
    if any(claim.project_id != evidence_set.project_id for claim in claims.values()):
        raise ValueError("candidate_claim_project_mismatch")

    contexts = [
        await _resolve_evidence_context(
            session,
            evidence=row_by_id[evidence_id],
            evidence_set_project_id=evidence_set.project_id,
        )
        for evidence_id in sorted(evidence_ids, key=str)
    ]
    return evidence_set, content_case, locale, contexts


def _candidate_snapshot(
    *,
    evidence_set: EvidenceSet,
    claim: Claim,
    locale: str | None,
    contexts: list[_EvidenceContext],
) -> tuple[dict[str, Any], str]:
    sorted_contexts = sorted(contexts, key=lambda item: str(item.evidence.id))
    evidence_ids = [str(item.evidence.id) for item in sorted_contexts]
    source_document_ids = sorted(
        {
            source_document_id
            for item in sorted_contexts
            for source_document_id in item.source_document_ids
        },
        key=str,
    )
    source_ids = sorted(
        {source_id for item in sorted_contexts for source_id in item.source_ids},
        key=str,
    )
    relation_counts = {
        relation: sum(item.evidence.relation == relation for item in sorted_contexts)
        for relation in _RELATIONS
    }
    source_refs = [f"source:{source_id}" for source_id in source_ids]
    evidence_refs = [
        {
            "evidence_id": str(item.evidence.id),
            "relation": item.evidence.relation,
            "locator": item.evidence.locator,
            "source_document_ids": [str(value) for value in item.source_document_ids],
            "source_ids": [str(value) for value in item.source_ids],
            "provenance": _safe_provenance(item.evidence.provenance_json),
        }
        for item in sorted_contexts
    ]
    summary = deterministic_candidate_summary(
        statement=claim.statement,
        relation_counts=relation_counts,
    )
    snapshot: dict[str, Any] = {
        "evidence_set": {
            "id": str(evidence_set.id),
            "version": evidence_set.version,
            "content_hash": evidence_set.content_hash,
        },
        "claim_id": str(claim.id),
        "statement": claim.statement,
        "summary": summary,
        "locale": locale,
        "entity_refs": list(claim.entity_refs_json),
        "source_refs": source_refs,
        "evidence_ids": evidence_ids,
        "source_document_ids": [str(value) for value in source_document_ids],
        "source_ids": [str(value) for value in source_ids],
        "relation_counts": relation_counts,
        "evidence_refs": evidence_refs,
    }
    return snapshot, _sha256(snapshot)


def _candidate_matches(
    candidate: KnowledgeCandidate,
    *,
    project_id: UUID,
    locale: str | None,
    snapshot: dict[str, Any],
    candidate_content_hash: str,
) -> bool:
    provenance = candidate.provenance_json
    expected_provenance = {
        "method": EXTRACTION_METHOD,
        "evidence_set": snapshot["evidence_set"],
        "claim_id": snapshot["claim_id"],
        "evidence_ids": snapshot["evidence_ids"],
        "source_document_ids": snapshot["source_document_ids"],
        "source_ids": snapshot["source_ids"],
        "relation_counts": snapshot["relation_counts"],
        "evidence_refs": snapshot["evidence_refs"],
        "candidate_content_hash": candidate_content_hash,
    }
    return (
        candidate.project_id == project_id
        and candidate.locale == locale
        and candidate.statement == snapshot["statement"]
        and candidate.summary == snapshot["summary"]
        and candidate.source_refs_json == snapshot["source_refs"]
        and candidate.entity_refs_json == snapshot["entity_refs"]
        and provenance == expected_provenance
    )


async def extract_knowledge_candidates(
    session: AsyncSession,
    *,
    evidence_set_id: UUID,
) -> list[KnowledgeCandidate]:
    """Extract or reuse one candidate per supported Claim in a locked EvidenceSet."""

    evidence_set, _content_case, locale, contexts = await _load_locked_evidence_set(
        session,
        evidence_set_id=evidence_set_id,
    )
    by_claim: defaultdict[UUID, list[_EvidenceContext]] = defaultdict(list)
    for context in contexts:
        by_claim[context.evidence.claim_id].append(context)

    claims = {
        claim.id: claim
        for claim in (
            await session.execute(
                select(Claim).where(Claim.id.in_(list(by_claim)))
            )
        )
        .scalars()
        .all()
    }
    extracted: list[KnowledgeCandidate] = []
    for claim_id in sorted(by_claim, key=str):
        claim = claims[claim_id]
        claim_contexts = by_claim[claim_id]
        if not any(item.evidence.relation == "supports" for item in claim_contexts):
            continue

        snapshot, candidate_content_hash = _candidate_snapshot(
            evidence_set=evidence_set,
            claim=claim,
            locale=locale,
            contexts=claim_contexts,
        )
        candidate_id = stable_knowledge_candidate_id(
            candidate_content_hash=candidate_content_hash
        )
        candidate = await session.get(KnowledgeCandidate, candidate_id)
        if candidate is not None:
            if not _candidate_matches(
                candidate,
                project_id=evidence_set.project_id,
                locale=locale,
                snapshot=snapshot,
                candidate_content_hash=candidate_content_hash,
            ):
                raise ValueError("knowledge_candidate_fingerprint_collision")
            extracted.append(candidate)
            continue

        candidate = KnowledgeCandidate(
            id=candidate_id,
            project_id=evidence_set.project_id,
            locale=locale,
            statement=snapshot["statement"],
            summary=snapshot["summary"],
            source_refs_json=snapshot["source_refs"],
            provenance_json={
                "method": EXTRACTION_METHOD,
                "evidence_set": snapshot["evidence_set"],
                "claim_id": snapshot["claim_id"],
                "evidence_ids": snapshot["evidence_ids"],
                "source_document_ids": snapshot["source_document_ids"],
                "source_ids": snapshot["source_ids"],
                "relation_counts": snapshot["relation_counts"],
                "evidence_refs": snapshot["evidence_refs"],
                "candidate_content_hash": candidate_content_hash,
            },
            entity_refs_json=snapshot["entity_refs"],
            status="CANDIDATE",
            reviewer=None,
            review_reason=None,
        )
        session.add(candidate)
        await session.flush()
        extracted.append(candidate)

    return extracted
