from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import KnowledgeChunk, Source, SourceDocument
from app.modules.knowledge.persistence import (
    content_hash,
    stable_chunk_fingerprint,
    stable_chunk_id,
    stable_document_id,
)

CANONICALIZATION_VERSION = "ce04-v1"
CHUNKER_VERSION = "ce04-v1"
DEFAULT_MAX_CHUNK_CHARS = 1600


class SourceIdentityError(ValueError):
    """Raised when a source has no stable locator for registry identity."""


class ChunkingConflictError(RuntimeError):
    """Raised when stored chunks disagree with deterministic chunking output."""


@dataclass(frozen=True)
class SourceRegistration:
    source: Source
    created: bool


@dataclass(frozen=True)
class DocumentIngestResult:
    source: Source
    document: SourceDocument
    chunks: tuple[KnowledgeChunk, ...]
    document_created: bool


def normalize_source_url(url: str | None) -> str | None:
    """Normalize a source URL without changing query semantics."""

    if url is None:
        return None
    candidate = url.strip()
    if not candidate:
        return None

    parts = urlsplit(candidate)
    if not parts.scheme or not parts.netloc:
        return candidate

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def source_fingerprint(
    *,
    source_type: str,
    canonical_url: str | None,
    locator: str | None,
    provenance_json: dict[str, object],
) -> str:
    """Build a stable registry fingerprint from the source's durable locator."""

    normalized_url = normalize_source_url(canonical_url)
    normalized_locator = locator.strip() if locator and locator.strip() else None
    provenance_ref = provenance_json.get("source_ref")
    normalized_ref = provenance_ref.strip() if isinstance(provenance_ref, str) else None

    identity = normalized_url or normalized_locator or normalized_ref
    if identity is None:
        raise SourceIdentityError(
            "source requires canonical_url, locator, or provenance_json['source_ref']"
        )

    payload = json.dumps(
        {"source_type": source_type.strip().lower(), "identity": identity},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return content_hash(payload)


def canonicalize_markdown(text: str) -> str:
    """Create the stable text/Markdown representation used for hashing and chunking."""

    normalized = unicodedata.normalize("NFC", text.lstrip("\ufeff"))
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = normalized.strip()
    if not normalized:
        raise ValueError("canonical document content cannot be empty")
    return normalized


def chunk_markdown(text: str, *, max_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> tuple[str, ...]:
    """Split canonical Markdown deterministically while keeping every chunk bounded."""

    if max_chars < 1:
        raise ValueError("max_chars must be positive")

    remaining = canonicalize_markdown(text)
    chunks: list[str] = []
    min_boundary = max(1, max_chars // 2)

    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        split_at = max_chars

        for marker in ("\n\n", "\n", ". ", " "):
            index = window.rfind(marker, min_boundary, max_chars + 1)
            if index >= min_boundary:
                split_at = index + len(marker)
                break

        chunk = remaining[:split_at].strip()
        if not chunk:
            chunk = remaining[:max_chars]
            split_at = max_chars
        chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)

    if any(len(chunk) > max_chars for chunk in chunks):
        raise AssertionError("chunker produced an oversized chunk")
    return tuple(chunks)


def estimate_tokens(text: str) -> int:
    """Return a stable rough token estimate without depending on a model tokenizer."""

    return max(1, (len(text) + 3) // 4)


async def register_source(
    session: AsyncSession,
    *,
    project_id: UUID,
    source_type: str,
    captured_at: datetime,
    provenance_json: dict[str, object],
    title: str | None = None,
    publisher: str | None = None,
    author: str | None = None,
    canonical_url: str | None = None,
    locator: str | None = None,
    locale: str | None = None,
    commercial_bias: str | None = None,
    authority_hint: str | None = None,
) -> SourceRegistration:
    """Register one durable source identity without creating duplicate Source rows."""

    normalized_url = normalize_source_url(canonical_url)
    normalized_locator = locator.strip() if locator and locator.strip() else None
    fingerprint = source_fingerprint(
        source_type=source_type,
        canonical_url=normalized_url,
        locator=normalized_locator,
        provenance_json=provenance_json,
    )
    existing = (
        await session.execute(
            select(Source).where(
                Source.project_id == project_id,
                Source.fingerprint == fingerprint,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return SourceRegistration(source=existing, created=False)

    source = Source(
        project_id=project_id,
        source_type=source_type.strip().lower(),
        title=title,
        publisher=publisher,
        author=author,
        canonical_url=normalized_url,
        locator=normalized_locator,
        locale=locale,
        commercial_bias=commercial_bias,
        authority_hint=authority_hint,
        provenance_json=dict(provenance_json),
        captured_at=captured_at,
        fingerprint=fingerprint,
    )
    session.add(source)
    await session.flush()
    return SourceRegistration(source=source, created=True)


async def ingest_source_document(
    session: AsyncSession,
    *,
    source_id: UUID,
    content_markdown: str,
    fetched_at: datetime,
    metadata_json: dict[str, object] | None = None,
    canonical_url: str | None = None,
    reader: str | None = None,
    provider: str | None = None,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> DocumentIngestResult:
    """Canonicalize, version, dedupe and chunk one source document atomically."""

    source = (
        await session.execute(select(Source).where(Source.id == source_id).with_for_update())
    ).scalar_one()
    canonical = canonicalize_markdown(content_markdown)
    document_hash = content_hash(canonical)

    existing = (
        await session.execute(
            select(SourceDocument).where(
                SourceDocument.source_id == source.id,
                SourceDocument.content_hash == document_hash,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        chunks = await _ensure_chunks(
            session,
            document=existing,
            max_chunk_chars=max_chunk_chars,
        )
        return DocumentIngestResult(
            source=source,
            document=existing,
            chunks=chunks,
            document_created=False,
        )

    latest = (
        await session.execute(
            select(SourceDocument)
            .where(SourceDocument.source_id == source.id)
            .order_by(SourceDocument.document_version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    version = 1 if latest is None else latest.document_version + 1

    metadata = dict(metadata_json or {})
    metadata["canonicalization_version"] = CANONICALIZATION_VERSION
    document = SourceDocument(
        id=stable_document_id(
            source_id=source.id,
            document_content_hash=document_hash,
        ),
        source_id=source.id,
        document_version=version,
        canonical_url=normalize_source_url(canonical_url) or source.canonical_url,
        fetched_at=fetched_at,
        content_hash=document_hash,
        content_markdown=canonical,
        metadata_json=metadata,
        reader=reader,
        provider=provider,
        supersedes_id=latest.id if latest is not None else None,
    )
    session.add(document)
    await session.flush()
    chunks = await _ensure_chunks(
        session,
        document=document,
        max_chunk_chars=max_chunk_chars,
    )
    return DocumentIngestResult(
        source=source,
        document=document,
        chunks=chunks,
        document_created=True,
    )


async def _ensure_chunks(
    session: AsyncSession,
    *,
    document: SourceDocument,
    max_chunk_chars: int,
) -> tuple[KnowledgeChunk, ...]:
    expected_texts = chunk_markdown(document.content_markdown, max_chars=max_chunk_chars)
    existing = tuple(
        (
            await session.execute(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.source_document_id == document.id)
                .order_by(KnowledgeChunk.ordinal)
            )
        )
        .scalars()
        .all()
    )
    existing_by_ordinal = {chunk.ordinal: chunk for chunk in existing}

    if any(chunk.ordinal >= len(expected_texts) for chunk in existing):
        raise ChunkingConflictError("stored chunk count exceeds deterministic output")

    output: list[KnowledgeChunk] = []
    for ordinal, text in enumerate(expected_texts):
        fingerprint = stable_chunk_fingerprint(text=text, ordinal=ordinal)
        stored = existing_by_ordinal.get(ordinal)
        if stored is not None:
            if stored.text != text or stored.fingerprint != fingerprint:
                raise ChunkingConflictError(
                    f"stored chunk {ordinal} disagrees with deterministic output"
                )
            output.append(stored)
            continue

        chunk = KnowledgeChunk(
            id=stable_chunk_id(
                source_document_id=document.id,
                text=text,
                ordinal=ordinal,
            ),
            source_document_id=document.id,
            ordinal=ordinal,
            text=text,
            token_estimate=estimate_tokens(text),
            fingerprint=fingerprint,
            status="active",
            metadata_json={
                "chunker_version": CHUNKER_VERSION,
                "max_chars": max_chunk_chars,
            },
        )
        session.add(chunk)
        output.append(chunk)

    await session.flush()
    return tuple(output)
