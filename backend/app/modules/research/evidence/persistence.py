from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import ContentCase, ContentOpportunity, NeedHypothesis
from app.modules.knowledge.ingest import ingest_source_document, register_source
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    EvidenceSet,
    KnowledgeChunk,
    OriginalityPack,
    Source,
    SourceDocument,
)
from app.modules.knowledge.persistence import content_hash
from app.modules.research.contracts import PageDocument, ProductionResearchResult, SourceCandidate
from app.modules.research.evidence.contracts import (
    ClaimCandidate,
    EvidenceRelation,
    PersistedEvidenceLink,
    PersistedPageRef,
)


async def ensure_selected_content_case(
    session: AsyncSession,
    *,
    project_id: UUID,
    content_opportunity_id: UUID,
    need_hypothesis_id: UUID,
) -> tuple[ContentCase, ContentOpportunity, NeedHypothesis]:
    opportunity = (
        await session.execute(
            select(ContentOpportunity)
            .where(ContentOpportunity.id == content_opportunity_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if opportunity is None:
        raise ValueError("selected_content_opportunity_not_found")
    if opportunity.project_id != project_id:
        raise ValueError("selected_content_opportunity_project_mismatch")
    if opportunity.need_hypothesis_id != need_hypothesis_id:
        raise ValueError("selected_content_opportunity_hypothesis_mismatch")
    if opportunity.selected_by is None:
        raise ValueError("human_selected_content_opportunity_required")
    if opportunity.suggested_content_type != "journal":
        raise ValueError("pr_e_requires_selected_journal_opportunity")

    hypothesis = await session.get(NeedHypothesis, need_hypothesis_id)
    if hypothesis is None:
        raise ValueError("selected_need_hypothesis_not_found")
    if hypothesis.project_id != project_id:
        raise ValueError("selected_need_hypothesis_project_mismatch")
    if hypothesis.status != "PROPOSED":
        raise ValueError("pr_e_does_not_auto_promote_need_hypothesis")

    existing = tuple(
        (
            await session.execute(
                select(ContentCase)
                .where(ContentCase.content_opportunity_id == content_opportunity_id)
                .order_by(ContentCase.created_at.asc(), ContentCase.id.asc())
            )
        )
        .scalars()
        .all()
    )
    if len(existing) > 1:
        raise ValueError("multiple_content_cases_for_selected_opportunity")
    if existing:
        content_case = existing[0]
        if (
            content_case.project_id != project_id
            or content_case.need_hypothesis_id != need_hypothesis_id
            or content_case.content_type != "journal"
        ):
            raise ValueError("existing_content_case_selection_mismatch")
        return content_case, opportunity, hypothesis

    content_case = ContentCase(
        project_id=project_id,
        content_type="journal",
        audience_hypothesis_id=hypothesis.audience_hypothesis_id,
        need_hypothesis_id=need_hypothesis_id,
        content_opportunity_id=content_opportunity_id,
        desired_action=f"Resolve the selected question: {opportunity.question}",
        content_hypothesis=opportunity.promise,
        originality_statement=(
            "External evidence and MOTGU-owned originality remain separate; "
            "OriginalityPack records only MOTGU material."
        ),
        reader_before=opportunity.situation,
        reader_after=opportunity.promise,
        status="draft",
    )
    session.add(content_case)
    await session.flush()
    return content_case, opportunity, hypothesis


def _normalize_url(url: str) -> str:
    candidate = url.strip()
    parts = urlsplit(candidate)
    if not parts.scheme or not parts.netloc:
        return candidate.rstrip("/").casefold()
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    ).casefold()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _candidate_urls(candidate: SourceCandidate) -> tuple[str, ...]:
    return (_normalize_url(candidate.url),)


def _document_urls(document: PageDocument) -> tuple[str, ...]:
    values = (document.url, document.requested_url, document.final_url)
    return tuple(_normalize_url(value) for value in values if value)


def _authority_hint(candidate: SourceCandidate | None) -> str | None:
    if candidate is None:
        return None
    if candidate.source_type == "institutional":
        return "institutional_candidate"
    if candidate.source_type == "community_or_review":
        return "audience_observation_candidate"
    if candidate.source_type == "editorial":
        return "secondary_editorial_context"
    if candidate.source_type == "commercial":
        return "commercial_context_only"
    return None


def _candidate_for_document(
    production: ProductionResearchResult,
    document: PageDocument,
) -> SourceCandidate | None:
    document_urls = set(_document_urls(document))
    for candidate in production.source_candidates:
        if document_urls.intersection(_candidate_urls(candidate)):
            return candidate
    return None


async def persist_read_documents(
    session: AsyncSession,
    *,
    production: ProductionResearchResult,
) -> dict[str, PersistedPageRef]:
    refs: dict[str, PersistedPageRef] = {}
    persisted_document_ids: set[UUID] = set()

    for document in production.documents:
        candidate = _candidate_for_document(production, document)
        canonical_url = document.final_url or document.url or document.requested_url
        if not canonical_url:
            raise ValueError("read_document_url_required")
        source_type = candidate.source_type if candidate is not None else "web"
        commercial_bias = (
            candidate.commercial_bias.value if candidate is not None else None
        )
        authority_hint = _authority_hint(candidate)
        provenance: dict[str, object] = {
            "method": "evidence_read",
            "provider": document.provider,
            "query": production.request.query,
            "source_ref": canonical_url,
            "evidence_candidate": True,
        }
        if candidate is not None:
            provenance.update(
                {
                    "discovered_by": candidate.provider,
                    "found_via": candidate.found_via,
                    "relation": candidate.relation.value,
                    "intended_use": candidate.intended_use.value,
                    "parent_url": candidate.parent_url,
                }
            )

        registered = await register_source(
            session,
            project_id=production.request.project_id,
            source_type=source_type,
            title=document.title or (candidate.title if candidate is not None else None),
            canonical_url=canonical_url,
            locale=production.request.locale,
            commercial_bias=commercial_bias,
            authority_hint=authority_hint,
            captured_at=_parse_datetime(document.captured_at),
            provenance_json=provenance,
        )
        ingested = await ingest_source_document(
            session,
            source_id=registered.source.id,
            content_markdown=document.content,
            fetched_at=_parse_datetime(document.captured_at),
            canonical_url=canonical_url,
            reader=document.provider,
            provider=document.provider,
            metadata_json={
                "evidence_research_query": production.request.query,
                "content_truncated": document.content_truncated,
                "links_truncated": document.links_truncated,
            },
        )
        page_ref = PersistedPageRef(
            source_id=registered.source.id,
            source_document_id=ingested.document.id,
            chunk_ids=tuple(chunk.id for chunk in ingested.chunks),
            canonical_url=canonical_url,
        )
        for url in _document_urls(document):
            refs[url] = page_ref
        refs[_normalize_url(canonical_url)] = page_ref
        persisted_document_ids.add(ingested.document.id)

    if len(persisted_document_ids) > len(production.documents):
        raise AssertionError("persisted_document_count_exceeds_read_documents")
    return refs


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


async def persist_claim_evidence(
    session: AsyncSession,
    *,
    project_id: UUID,
    page_refs: dict[str, PersistedPageRef],
    candidate: ClaimCandidate,
) -> PersistedEvidenceLink:
    statement = candidate.statement.strip()
    locator = candidate.locator.strip()
    excerpt = candidate.excerpt.strip()
    if not statement:
        raise ValueError("claim_statement_required")
    if not locator:
        raise ValueError("evidence_locator_required")
    if not excerpt:
        raise ValueError("evidence_excerpt_required")
    if candidate.importance not in {"low", "normal", "high", "critical"}:
        raise ValueError("invalid_claim_importance")

    page_ref = page_refs.get(_normalize_url(candidate.source_url))
    if page_ref is None:
        raise ValueError("evidence_source_must_be_successfully_read")
    document = await session.get(SourceDocument, page_ref.source_document_id)
    source = await session.get(Source, page_ref.source_id)
    if document is None or source is None:
        raise ValueError("persisted_evidence_source_missing")
    if source.project_id != project_id:
        raise ValueError("evidence_source_project_mismatch")
    if _normalized_text(excerpt) not in _normalized_text(document.content_markdown):
        raise ValueError("evidence_excerpt_not_found_in_source_document")

    chunk_id: UUID | None = None
    if page_ref.chunk_ids:
        chunks = tuple(
            (
                await session.execute(
                    select(KnowledgeChunk)
                    .where(KnowledgeChunk.id.in_(page_ref.chunk_ids))
                    .order_by(KnowledgeChunk.ordinal.asc())
                )
            )
            .scalars()
            .all()
        )
        for chunk in chunks:
            if _normalized_text(excerpt) in _normalized_text(chunk.text):
                chunk_id = chunk.id
                break

    claim = (
        await session.execute(
            select(Claim)
            .where(
                Claim.project_id == project_id,
                Claim.statement == statement,
                Claim.claim_type == candidate.claim_type,
            )
            .order_by(Claim.created_at.asc(), Claim.id.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if claim is None:
        claim = Claim(
            project_id=project_id,
            statement=statement,
            claim_type=candidate.claim_type,
            importance=candidate.importance,
            status="unverified",
            confidence=None,
            entity_refs_json=[],
        )
        session.add(claim)
        await session.flush()

    evidence = (
        await session.execute(
            select(Evidence)
            .where(
                Evidence.claim_id == claim.id,
                Evidence.source_document_id == document.id,
                Evidence.locator == locator,
                Evidence.excerpt == excerpt,
                Evidence.relation == candidate.relation.value,
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
            excerpt=excerpt,
            relation=candidate.relation.value,
            authority_level=source.authority_hint,
            quality_metadata_json={
                "source_type": source.source_type,
                "commercial_bias": source.commercial_bias,
                "authority_hint": source.authority_hint,
                "search_rank_used_as_authority": False,
            },
            provenance_json={
                "method": "read_excerpt_link",
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

    return PersistedEvidenceLink(
        claim_id=claim.id,
        evidence_id=evidence.id,
        relation=EvidenceRelation(evidence.relation),
    )


def _evidence_set_hash(evidence_ids: tuple[UUID, ...]) -> str:
    payload = json.dumps(
        [str(evidence_id) for evidence_id in evidence_ids],
        separators=(",", ":"),
        sort_keys=True,
    )
    return content_hash(payload)


async def create_or_reuse_evidence_set(
    session: AsyncSession,
    *,
    project_id: UUID,
    content_case_id: UUID,
    evidence_ids: list[UUID],
) -> EvidenceSet:
    normalized_ids = tuple(sorted(set(evidence_ids), key=str))
    if not normalized_ids:
        raise ValueError("evidence_set_requires_evidence")

    content_case = (
        await session.execute(
            select(ContentCase)
            .where(ContentCase.id == content_case_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if content_case is None:
        raise ValueError("evidence_set_content_case_not_found")
    if content_case.project_id != project_id:
        raise ValueError("evidence_set_content_case_project_mismatch")

    rows = tuple(
        (
            await session.execute(select(Evidence).where(Evidence.id.in_(normalized_ids)))
        )
        .scalars()
        .all()
    )
    if len(rows) != len(normalized_ids):
        raise ValueError("evidence_set_contains_missing_evidence")
    for row in rows:
        claim = await session.get(Claim, row.claim_id)
        if claim is None or claim.project_id != project_id:
            raise ValueError("evidence_set_contains_cross_project_evidence")

    set_hash = _evidence_set_hash(normalized_ids)
    existing = (
        await session.execute(
            select(EvidenceSet)
            .where(
                EvidenceSet.project_id == project_id,
                EvidenceSet.content_case_id == content_case_id,
                EvidenceSet.content_hash == set_hash,
            )
            .order_by(EvidenceSet.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    latest_version = await session.scalar(
        select(func.coalesce(func.max(EvidenceSet.version), 0)).where(
            EvidenceSet.project_id == project_id,
            EvidenceSet.content_case_id == content_case_id,
        )
    )
    evidence_set = EvidenceSet(
        project_id=project_id,
        content_case_id=content_case_id,
        version=int(latest_version or 0) + 1,
        evidence_ids_json=[str(evidence_id) for evidence_id in normalized_ids],
        content_hash=set_hash,
        status="draft",
    )
    session.add(evidence_set)
    await session.flush()
    return evidence_set


async def lock_evidence_set(
    session: AsyncSession,
    *,
    evidence_set_id: UUID,
    locked_by: str,
) -> EvidenceSet:
    reviewer = locked_by.strip()
    if not reviewer:
        raise ValueError("evidence_set_locker_required")
    evidence_set = (
        await session.execute(
            select(EvidenceSet)
            .where(EvidenceSet.id == evidence_set_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if evidence_set is None:
        raise ValueError("evidence_set_not_found")
    if evidence_set.status == "locked":
        if evidence_set.locked_by != reviewer:
            raise ValueError("evidence_set_already_locked_by_different_reviewer")
        return evidence_set
    if not evidence_set.evidence_ids_json:
        raise ValueError("cannot_lock_empty_evidence_set")

    evidence_set.status = "locked"
    evidence_set.locked_at = datetime.now(UTC)
    evidence_set.locked_by = reviewer
    await session.flush()
    return evidence_set


async def build_originality_pack(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    motgu_material_refs: list[str],
) -> OriginalityPack:
    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None:
        raise ValueError("originality_pack_content_case_not_found")

    refs = tuple(dict.fromkeys(ref.strip() for ref in motgu_material_refs if ref.strip()))
    items: list[object] = [
        {"type": "motgu_material_ref", "ref": ref}
        for ref in refs
    ]
    if items:
        summary = (
            "MOTGU-owned material references are available for editorial use. "
            "External web evidence is intentionally excluded from this pack."
        )
    else:
        summary = (
            "Originality gap: no approved MOTGU-owned material reference is attached to "
            "the selected opportunity yet. Do not invent first-party detail."
        )

    existing = tuple(
        (
            await session.execute(
                select(OriginalityPack)
                .where(OriginalityPack.content_case_id == content_case_id)
                .order_by(OriginalityPack.created_at.asc(), OriginalityPack.id.asc())
            )
        )
        .scalars()
        .all()
    )
    for pack in existing:
        if pack.status != "retired" and pack.item_refs_json == items and pack.summary == summary:
            return pack

    pack = OriginalityPack(
        content_case_id=content_case_id,
        item_refs_json=items,
        summary=summary,
        status="draft",
    )
    session.add(pack)
    await session.flush()
    return pack
