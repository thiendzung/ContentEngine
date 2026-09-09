from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
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
    EvidenceSetApproval,
    KnowledgeChunk,
    OriginalityPack,
    Source,
    SourceDocument,
)
from app.modules.knowledge.persistence import evidence_set_hash
from app.modules.research.contracts import (
    PageDocument,
    ProductionResearchResult,
    SourceCandidate,
    SourceRelation,
)
from app.modules.research.evidence.contracts import (
    ORIGINALITY_MATERIAL_TYPE,
    ORIGINALITY_REFERENCE_ONLY_TYPE,
    ClaimCandidate,
    EvidenceRelation,
    OriginalityMaterialInput,
    PersistedEvidenceLink,
    PersistedPageRef,
    count_usable_originality_items,
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
    for source_candidate in production.source_candidates:
        if source_candidate.relation is not SourceRelation.SECOND_HOP:
            continue
        if not source_candidate.parent_url:
            raise ValueError("second_hop_parent_url_required")
        requested_parent_url = production.request.parent_url
        if (
            requested_parent_url is not None
            and source_candidate.parent_url != requested_parent_url
        ):
            raise ValueError("second_hop_parent_url_mismatch")

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

    set_hash = evidence_set_hash([str(evidence_id) for evidence_id in normalized_ids])
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
    approval_id: UUID | None = None,
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
    if approval_id is None:
        raise ValueError("evidence_set_approval_required")
    if not evidence_set.evidence_ids_json:
        raise ValueError("cannot_lock_empty_evidence_set")

    if not isinstance(evidence_set.evidence_ids_json, list) or not all(
        isinstance(evidence_id, str) for evidence_id in evidence_set.evidence_ids_json
    ):
        raise ValueError("evidence_set_content_hash_invalid")
    recomputed_hash = evidence_set_hash(evidence_set.evidence_ids_json)
    if evidence_set.content_hash != recomputed_hash:
        raise ValueError("evidence_set_content_hash_invalid")

    approval = await session.get(EvidenceSetApproval, approval_id)
    if approval is None:
        raise ValueError("evidence_set_approval_not_found")
    if approval.evidence_set_id != evidence_set.id:
        raise ValueError("evidence_set_approval_set_mismatch")
    if approval.evidence_set_version != evidence_set.version:
        raise ValueError("evidence_set_approval_version_mismatch")
    if approval.evidence_set_content_hash != evidence_set.content_hash:
        raise ValueError("evidence_set_approval_hash_mismatch")

    evidence_set.status = "locked"
    evidence_set.locked_at = datetime.now(UTC)
    evidence_set.locked_by = reviewer
    await session.flush()
    return evidence_set


_EXTERNAL_EVIDENCE_TYPES = {
    "claim",
    "evidence",
    "external_evidence",
    "irs_evidence",
    "mci_evidence",
    "web_evidence",
}
_REFERENCE_ONLY_TYPES = {
    ORIGINALITY_REFERENCE_ONLY_TYPE,
    "motgu_material_ref",
}
_REFERENCE_ONLY_KINDS = {"motgu_fact", "motgu_material_ref"}
_EXTERNAL_REFERENCE_PREFIXES = (
    "claim:",
    "evidence:",
    "external:",
    "external_evidence:",
    "irs:",
    "mci:",
    "source_document:",
)


def _is_external_evidence_reference(value: str) -> bool:
    candidate = value.strip().casefold()
    if not candidate:
        return False
    if candidate.startswith(_EXTERNAL_REFERENCE_PREFIXES):
        return True

    host = urlsplit(candidate).hostname
    if host is None:
        return "irs.gov" in candidate or "si.edu" in candidate
    return (
        host == "irs.gov"
        or host.endswith(".irs.gov")
        or host == "si.edu"
        or host.endswith(".si.edu")
    )


def _reference_only_item(value: object) -> dict[str, object] | None:
    if isinstance(value, str):
        source_ref = value.strip()
    elif isinstance(value, Mapping):
        raw_ref = value.get("source_ref", value.get("ref"))
        source_ref = raw_ref.strip() if isinstance(raw_ref, str) else ""
    else:
        return None

    if not source_ref or _is_external_evidence_reference(source_ref):
        return None
    return {"type": ORIGINALITY_REFERENCE_ONLY_TYPE, "source_ref": source_ref}


def normalize_originality_items(
    items: Sequence[OriginalityMaterialInput],
    *,
    excluded_evidence_refs: set[str] | frozenset[str] = frozenset(),
) -> list[object]:
    """Normalize legacy refs while preserving approved structured items verbatim."""

    normalized: list[object] = []
    seen: set[str] = set()
    for raw_item in items:
        item: dict[str, object] | None = None
        if isinstance(raw_item, str):
            item = _reference_only_item(raw_item)
        elif isinstance(raw_item, Mapping):
            raw_type = raw_item.get("type")
            raw_kind = raw_item.get("kind")
            item_type = raw_type.casefold() if isinstance(raw_type, str) else ""
            item_kind = raw_kind.casefold() if isinstance(raw_kind, str) else ""

            if raw_type == ORIGINALITY_MATERIAL_TYPE:
                source_ref = raw_item.get("source_ref")
                if (
                    isinstance(source_ref, str)
                    and (
                        _is_external_evidence_reference(source_ref)
                        or source_ref.casefold() in excluded_evidence_refs
                    )
                ):
                    continue
                item = dict(raw_item)
            elif item_type in _EXTERNAL_EVIDENCE_TYPES or item_kind in {
                *_EXTERNAL_EVIDENCE_TYPES,
                "external_evidence",
            }:
                continue
            elif item_type in _REFERENCE_ONLY_TYPES or item_kind in _REFERENCE_ONLY_KINDS:
                raw_ref = raw_item.get("source_ref", raw_item.get("ref"))
                if (
                    isinstance(raw_ref, str)
                    and raw_ref.casefold() in excluded_evidence_refs
                ):
                    continue
                item = _reference_only_item(raw_item)

        if item is None:
            continue
        source_ref = item.get("source_ref") if isinstance(item, dict) else None
        if isinstance(source_ref, str) and source_ref.casefold() in excluded_evidence_refs:
            continue
        fingerprint = json.dumps(
            item,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        normalized.append(item)
    return normalized


async def _evidence_reference_ids(
    session: AsyncSession,
    items: Sequence[OriginalityMaterialInput],
) -> set[str]:
    possible_ids: set[UUID] = set()
    for raw_item in items:
        values: tuple[object, ...]
        if isinstance(raw_item, str):
            values = (raw_item,)
        elif isinstance(raw_item, Mapping):
            values = tuple(
                raw_item.get(field_name)
                for field_name in ("id", "evidence_id", "source_ref", "ref")
            )
        else:
            values = ()
        for value in values:
            if not isinstance(value, str):
                continue
            try:
                possible_ids.add(UUID(value.strip()))
            except ValueError:
                continue

    if not possible_ids:
        return set()
    evidence_ids = await session.scalars(
        select(Evidence.id).where(Evidence.id.in_(possible_ids))
    )
    return {str(evidence_id).casefold() for evidence_id in evidence_ids}


async def build_originality_pack(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    motgu_material_refs: Sequence[OriginalityMaterialInput],
) -> OriginalityPack:
    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None:
        raise ValueError("originality_pack_content_case_not_found")

    excluded_evidence_refs = await _evidence_reference_ids(session, motgu_material_refs)
    items = normalize_originality_items(
        motgu_material_refs,
        excluded_evidence_refs=excluded_evidence_refs,
    )
    usable_item_count = count_usable_originality_items(items)
    if usable_item_count:
        summary = (
            "MOTGU-owned material is available for editorial use. "
            "External web evidence is intentionally excluded from this pack."
        )
    elif items:
        summary = (
            "Originality gap: only reference-only or incomplete MOTGU material is attached; "
            "do not treat it as usable originality material or invent first-party detail. "
            "External web evidence is intentionally excluded from this pack."
        )
    else:
        summary = (
            "Originality gap: no approved MOTGU-owned material is attached to the selected "
            "opportunity yet. Do not invent first-party detail."
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
