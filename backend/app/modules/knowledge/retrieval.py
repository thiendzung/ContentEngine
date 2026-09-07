from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import Entity, KnowledgeChunk, Source, SourceDocument

ENTITY_LINKER_VERSION = "ce04-v1"

_DEFAULT_AUTHORITY_TIERS = (
    ("low",),
    ("secondary", "medium"),
    ("institution", "institutional", "academic", "high"),
    ("canonical", "primary", "official", "artist_approved"),
)
_DEFAULT_COMMERCIAL_BIAS_TIERS = (
    ("high",),
    ("medium",),
    ("none", "low"),
)


@dataclass(frozen=True)
class LinkedEntity:
    entity_id: UUID
    canonical_key: str
    canonical_name: str
    matched_aliases: tuple[str, ...]


@dataclass(frozen=True)
class ChunkEntityLinkResult:
    chunk_id: UUID
    linked_entities: tuple[LinkedEntity, ...]
    ambiguous_aliases: tuple[str, ...]
    changed: bool


@dataclass(frozen=True)
class RetrievalRankingPolicy:
    version: str = "ce04-v1"
    authority_tiers: tuple[tuple[str, ...], ...] = _DEFAULT_AUTHORITY_TIERS
    authority_unknown_rank: int = 2
    commercial_bias_tiers: tuple[tuple[str, ...], ...] = _DEFAULT_COMMERCIAL_BIAS_TIERS
    commercial_bias_unknown_rank: int = 2


DEFAULT_RETRIEVAL_RANKING_POLICY = RetrievalRankingPolicy()


@dataclass(frozen=True)
class RetrievalRequest:
    project_id: UUID
    query: str
    locale: str | None = None
    limit: int = 10
    preferred_source_types: tuple[str, ...] = ()
    ranking_policy: RetrievalRankingPolicy = DEFAULT_RETRIEVAL_RANKING_POLICY


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: UUID
    source_document_id: UUID
    source_id: UUID
    document_version: int
    text: str
    source_type: str
    authority_hint: str | None
    commercial_bias: str | None
    matched_terms: tuple[str, ...]
    matched_entity_ids: tuple[UUID, ...]
    exact_phrase: bool
    ranking_reasons: tuple[str, ...]


@dataclass(frozen=True)
class _EntityTarget:
    entity_id: UUID
    canonical_key: str
    canonical_name: str


@dataclass(frozen=True)
class _RankedHit:
    hit: RetrievalHit
    exact_phrase_rank: int
    matched_term_rank: int
    matched_entity_rank: int
    preferred_source_type_rank: int
    authority_rank: int
    commercial_bias_rank: int


def normalize_retrieval_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def retrieval_terms(text: str) -> tuple[str, ...]:
    normalized = normalize_retrieval_text(text)
    terms: list[str] = []
    seen: set[str] = set()
    for term in re.findall(r"\w+", normalized, flags=re.UNICODE):
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return tuple(terms)


def _contains_exact_alias(*, normalized_text: str, normalized_alias: str) -> bool:
    if not normalized_alias:
        return False
    pattern = rf"(?<!\w){re.escape(normalized_alias)}(?!\w)"
    return re.search(pattern, normalized_text, flags=re.UNICODE) is not None


def _entity_alias_index(
    entities: tuple[Entity, ...],
) -> tuple[dict[str, _EntityTarget], set[str]]:
    candidates: dict[str, dict[UUID, _EntityTarget]] = defaultdict(dict)

    for entity in entities:
        target = _EntityTarget(
            entity_id=entity.id,
            canonical_key=entity.canonical_key,
            canonical_name=entity.canonical_name,
        )
        aliases = (entity.canonical_name, *entity.aliases_json)
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            normalized_alias = normalize_retrieval_text(alias)
            if len(normalized_alias) < 2:
                continue
            candidates[normalized_alias][entity.id] = target

    unique: dict[str, _EntityTarget] = {}
    ambiguous: set[str] = set()
    for alias, targets in candidates.items():
        if len(targets) == 1:
            unique[alias] = next(iter(targets.values()))
        else:
            ambiguous.add(alias)
    return unique, ambiguous


def _match_entities(
    *,
    text: str,
    entities: tuple[Entity, ...],
) -> tuple[tuple[LinkedEntity, ...], tuple[str, ...]]:
    normalized_text = normalize_retrieval_text(text)
    unique_aliases, ambiguous_aliases = _entity_alias_index(entities)

    matched: dict[UUID, tuple[_EntityTarget, set[str]]] = {}
    for alias, target in unique_aliases.items():
        if not _contains_exact_alias(
            normalized_text=normalized_text,
            normalized_alias=alias,
        ):
            continue
        existing = matched.get(target.entity_id)
        if existing is None:
            matched[target.entity_id] = (target, {alias})
        else:
            existing[1].add(alias)

    conflicts = tuple(
        sorted(
            alias
            for alias in ambiguous_aliases
            if _contains_exact_alias(
                normalized_text=normalized_text,
                normalized_alias=alias,
            )
        )
    )
    linked = tuple(
        LinkedEntity(
            entity_id=target.entity_id,
            canonical_key=target.canonical_key,
            canonical_name=target.canonical_name,
            matched_aliases=tuple(sorted(aliases)),
        )
        for target, aliases in sorted(
            matched.values(),
            key=lambda item: (item[0].canonical_key, str(item[0].entity_id)),
        )
    )
    return linked, conflicts


def _entity_link_metadata(
    *,
    linked_entities: tuple[LinkedEntity, ...],
    ambiguous_aliases: tuple[str, ...],
) -> dict[str, object]:
    return {
        "entity_linker_version": ENTITY_LINKER_VERSION,
        "entity_links": [
            {
                "entity_id": str(link.entity_id),
                "canonical_key": link.canonical_key,
                "matched_aliases": list(link.matched_aliases),
                "method": "exact_alias",
            }
            for link in linked_entities
        ],
        "entity_link_conflicts": list(ambiguous_aliases),
    }


async def link_document_entities(
    session: AsyncSession,
    *,
    source_document_id: UUID,
) -> tuple[ChunkEntityLinkResult, ...]:
    """Link known project Entities into one document's active chunks deterministically."""

    document_source = (
        await session.execute(
            select(SourceDocument, Source)
            .join(Source, SourceDocument.source_id == Source.id)
            .where(SourceDocument.id == source_document_id)
        )
    ).one()
    document: SourceDocument = document_source[0]
    source: Source = document_source[1]

    entities = tuple(
        (
            await session.execute(
                select(Entity)
                .where(Entity.project_id == source.project_id)
                .order_by(Entity.canonical_key, Entity.id)
            )
        )
        .scalars()
        .all()
    )
    chunks = tuple(
        (
            await session.execute(
                select(KnowledgeChunk)
                .where(
                    KnowledgeChunk.source_document_id == document.id,
                    KnowledgeChunk.status == "active",
                )
                .order_by(KnowledgeChunk.ordinal, KnowledgeChunk.id)
            )
        )
        .scalars()
        .all()
    )

    results: list[ChunkEntityLinkResult] = []
    for chunk in chunks:
        linked_entities, ambiguous_aliases = _match_entities(
            text=chunk.text,
            entities=entities,
        )
        derived = _entity_link_metadata(
            linked_entities=linked_entities,
            ambiguous_aliases=ambiguous_aliases,
        )
        metadata = dict(chunk.metadata_json)
        changed = any(metadata.get(key) != value for key, value in derived.items())
        if changed:
            metadata.update(derived)
            chunk.metadata_json = metadata
            session.add(chunk)

        results.append(
            ChunkEntityLinkResult(
                chunk_id=chunk.id,
                linked_entities=linked_entities,
                ambiguous_aliases=ambiguous_aliases,
                changed=changed,
            )
        )

    await session.flush()
    return tuple(results)


def _stored_entity_ids(metadata: dict[str, object]) -> tuple[UUID, ...]:
    raw_links = metadata.get("entity_links")
    if not isinstance(raw_links, list):
        return ()

    output: list[UUID] = []
    for raw_link in raw_links:
        if not isinstance(raw_link, dict):
            continue
        raw_id = raw_link.get("entity_id")
        if not isinstance(raw_id, str):
            continue
        try:
            entity_id = UUID(raw_id)
        except ValueError:
            continue
        if entity_id not in output:
            output.append(entity_id)
    return tuple(output)


def _tier_rank(
    value: str | None,
    *,
    tiers: tuple[tuple[str, ...], ...],
    unknown_rank: int,
) -> int:
    normalized = normalize_retrieval_text(value or "")
    if not normalized:
        return unknown_rank
    for rank, tier in enumerate(tiers, start=1):
        normalized_tier = {normalize_retrieval_text(item) for item in tier}
        if normalized in normalized_tier:
            return rank
    return unknown_rank


def _authority_rank(value: str | None, *, policy: RetrievalRankingPolicy) -> int:
    return _tier_rank(
        value,
        tiers=policy.authority_tiers,
        unknown_rank=policy.authority_unknown_rank,
    )


def _commercial_bias_rank(value: str | None, *, policy: RetrievalRankingPolicy) -> int:
    return _tier_rank(
        value,
        tiers=policy.commercial_bias_tiers,
        unknown_rank=policy.commercial_bias_unknown_rank,
    )


def _ranking_reasons(
    *,
    exact_phrase: bool,
    matched_terms: tuple[str, ...],
    query_term_count: int,
    matched_entity_ids: tuple[UUID, ...],
    source: Source,
    preferred_source_types: set[str],
    policy: RetrievalRankingPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = [f"ranking_policy:{policy.version}"]
    if exact_phrase:
        reasons.append("exact_phrase")
    reasons.append(f"terms:{len(matched_terms)}/{query_term_count}")
    if matched_entity_ids:
        reasons.append(f"entities:{len(matched_entity_ids)}")
    normalized_source_type = normalize_retrieval_text(source.source_type)
    if normalized_source_type in preferred_source_types:
        reasons.append(f"preferred_source_type:{normalized_source_type}")
    if source.authority_hint:
        reasons.append(f"authority_hint:{source.authority_hint}")
    if source.commercial_bias:
        reasons.append(f"commercial_bias:{source.commercial_bias}")
    return tuple(reasons)


async def retrieve_chunks(
    session: AsyncSession,
    *,
    request: RetrievalRequest,
) -> tuple[RetrievalHit, ...]:
    """Retrieve latest active project chunks with transparent multi-signal ranking."""

    if request.limit < 1 or request.limit > 50:
        raise ValueError("retrieval limit must be between 1 and 50")

    normalized_query = normalize_retrieval_text(request.query)
    query_terms = retrieval_terms(request.query)
    if not normalized_query or not query_terms:
        raise ValueError("retrieval query must contain searchable text")

    entities = tuple(
        (
            await session.execute(
                select(Entity)
                .where(Entity.project_id == request.project_id)
                .order_by(Entity.canonical_key, Entity.id)
            )
        )
        .scalars()
        .all()
    )
    query_entities, _ = _match_entities(text=request.query, entities=entities)
    query_entity_ids = {entity.entity_id for entity in query_entities}

    latest_versions = (
        select(
            SourceDocument.source_id.label("source_id"),
            func.max(SourceDocument.document_version).label("document_version"),
        )
        .group_by(SourceDocument.source_id)
        .subquery()
    )

    statement = (
        select(KnowledgeChunk, SourceDocument, Source)
        .join(SourceDocument, KnowledgeChunk.source_document_id == SourceDocument.id)
        .join(Source, SourceDocument.source_id == Source.id)
        .join(
            latest_versions,
            and_(
                latest_versions.c.source_id == SourceDocument.source_id,
                latest_versions.c.document_version == SourceDocument.document_version,
            ),
        )
        .where(
            Source.project_id == request.project_id,
            KnowledgeChunk.status == "active",
        )
    )
    if request.locale is not None:
        statement = statement.where(or_(Source.locale == request.locale, Source.locale.is_(None)))

    rows = (await session.execute(statement)).all()
    preferred_source_types = {
        normalize_retrieval_text(source_type)
        for source_type in request.preferred_source_types
        if normalize_retrieval_text(source_type)
    }
    query_term_set = set(query_terms)
    ranked: list[_RankedHit] = []

    for row in rows:
        chunk: KnowledgeChunk = row[0]
        document: SourceDocument = row[1]
        source: Source = row[2]

        normalized_chunk = normalize_retrieval_text(chunk.text)
        chunk_terms = set(retrieval_terms(chunk.text))
        matched_terms = tuple(sorted(query_term_set & chunk_terms))
        stored_entity_ids = set(_stored_entity_ids(chunk.metadata_json))
        matched_entity_ids = tuple(sorted(query_entity_ids & stored_entity_ids, key=str))
        exact_phrase = _contains_exact_alias(
            normalized_text=normalized_chunk,
            normalized_alias=normalized_query,
        )

        if not exact_phrase and not matched_terms and not matched_entity_ids:
            continue

        normalized_source_type = normalize_retrieval_text(source.source_type)
        hit = RetrievalHit(
            chunk_id=chunk.id,
            source_document_id=document.id,
            source_id=source.id,
            document_version=document.document_version,
            text=chunk.text,
            source_type=source.source_type,
            authority_hint=source.authority_hint,
            commercial_bias=source.commercial_bias,
            matched_terms=matched_terms,
            matched_entity_ids=matched_entity_ids,
            exact_phrase=exact_phrase,
            ranking_reasons=_ranking_reasons(
                exact_phrase=exact_phrase,
                matched_terms=matched_terms,
                query_term_count=len(query_terms),
                matched_entity_ids=matched_entity_ids,
                source=source,
                preferred_source_types=preferred_source_types,
                policy=request.ranking_policy,
            ),
        )
        ranked.append(
            _RankedHit(
                hit=hit,
                exact_phrase_rank=1 if exact_phrase else 0,
                matched_term_rank=len(matched_terms),
                matched_entity_rank=len(matched_entity_ids),
                preferred_source_type_rank=(
                    1 if normalized_source_type in preferred_source_types else 0
                ),
                authority_rank=_authority_rank(
                    source.authority_hint,
                    policy=request.ranking_policy,
                ),
                commercial_bias_rank=_commercial_bias_rank(
                    source.commercial_bias,
                    policy=request.ranking_policy,
                ),
            )
        )

    ranked.sort(
        key=lambda item: (
            -item.exact_phrase_rank,
            -item.matched_term_rank,
            -item.matched_entity_rank,
            -item.preferred_source_type_rank,
            -item.authority_rank,
            -item.commercial_bias_rank,
            str(item.hit.source_id),
            item.hit.document_version,
            str(item.hit.chunk_id),
        )
    )
    return tuple(item.hit for item in ranked[: request.limit])
