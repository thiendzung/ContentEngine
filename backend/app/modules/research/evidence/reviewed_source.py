from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import ContentCase
from app.modules.knowledge.models import Claim, Evidence, KnowledgeChunk, Source, SourceDocument
from app.modules.knowledge.persistence import content_hash
from app.modules.research.evidence.contracts import EvidenceRelation, PersistedEvidenceLink


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _review_locator(source_document_id: UUID, excerpt: str) -> str:
    digest = content_hash(_normalized_text(excerpt))[:16]
    return f"reviewed_excerpt:{source_document_id}:{digest}"


async def persist_reviewed_existing_source_evidence(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    source_document_id: UUID,
    statement: str,
    excerpt: str,
    relation: EvidenceRelation,
    reviewed_by: str,
    claim_type: str = "fact",
    importance: str = "normal",
) -> PersistedEvidenceLink:
    reviewer = reviewed_by.strip()
    claim_statement = statement.strip()
    exact_excerpt = excerpt.strip()
    if not reviewer:
        raise ValueError("reviewed_existing_source_reviewer_required")
    if not claim_statement:
        raise ValueError("claim_statement_required")
    if not exact_excerpt:
        raise ValueError("evidence_excerpt_required")
    if importance not in {"low", "normal", "high", "critical"}:
        raise ValueError("invalid_claim_importance")

    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None:
        raise ValueError("reviewed_existing_source_content_case_not_found")
    document = await session.get(SourceDocument, source_document_id)
    if document is None:
        raise ValueError("reviewed_existing_source_document_not_found")
    source = await session.get(Source, document.source_id)
    if source is None:
        raise ValueError("reviewed_existing_source_missing_source")
    if source.project_id != content_case.project_id:
        raise ValueError("reviewed_existing_source_project_mismatch")
    if _normalized_text(exact_excerpt) not in _normalized_text(document.content_markdown):
        raise ValueError("evidence_excerpt_not_found_in_source_document")

    chunk_id: UUID | None = None
    chunks = tuple(
        (
            await session.execute(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.source_document_id == document.id)
                .order_by(KnowledgeChunk.ordinal.asc())
            )
        )
        .scalars()
        .all()
    )
    for chunk in chunks:
        if _normalized_text(exact_excerpt) in _normalized_text(chunk.text):
            chunk_id = chunk.id
            break

    claim = (
        await session.execute(
            select(Claim)
            .where(
                Claim.project_id == content_case.project_id,
                Claim.statement == claim_statement,
                Claim.claim_type == claim_type,
            )
            .order_by(Claim.created_at.asc(), Claim.id.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if claim is None:
        claim = Claim(
            project_id=content_case.project_id,
            statement=claim_statement,
            claim_type=claim_type,
            importance=importance,
            status="unverified",
            confidence=None,
            entity_refs_json=[],
        )
        session.add(claim)
        await session.flush()

    locator = _review_locator(document.id, exact_excerpt)
    evidence = (
        await session.execute(
            select(Evidence)
            .where(
                Evidence.claim_id == claim.id,
                Evidence.source_document_id == document.id,
                Evidence.locator == locator,
                Evidence.excerpt == exact_excerpt,
                Evidence.relation == relation.value,
            )
            .order_by(Evidence.created_at.asc(), Evidence.id.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if evidence is None:
        evidence = Evidence(
            claim_id=claim.id,
            source_document_id=document.id,
            chunk_id=chunk_id,
            locator=locator,
            excerpt=exact_excerpt,
            relation=relation.value,
            authority_level=source.authority_hint,
            quality_metadata_json={
                "source_type": source.source_type,
                "commercial_bias": source.commercial_bias,
                "authority_hint": source.authority_hint,
                "search_rank_used_as_authority": False,
                "human_reviewed": True,
                "review_method": "existing_source_document",
                "reviewed_by": reviewer,
            },
            provenance_json={
                "method": "human_review_existing_source",
                "reviewed_by": reviewer,
                "content_case_id": str(content_case.id),
                "source_id": str(source.id),
                "source_document_id": str(document.id),
                "source_document_hash": document.content_hash,
                "reader": document.reader,
                "provider": document.provider,
            },
            verified_at=datetime.now(UTC),
        )
        session.add(evidence)
        await session.flush()
    else:
        existing_reviewer = str(evidence.provenance_json.get("reviewed_by") or "").strip()
        if existing_reviewer and existing_reviewer != reviewer:
            raise ValueError("reviewed_existing_source_reviewer_mismatch")

    return PersistedEvidenceLink(
        claim_id=claim.id,
        evidence_id=evidence.id,
        relation=EvidenceRelation(evidence.relation),
    )
