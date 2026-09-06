from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.knowledge.ingest import (
    ChunkingConflictError,
    canonicalize_markdown,
    chunk_markdown,
    ingest_source_document,
    normalize_source_url,
    register_source,
    source_fingerprint,
)
from app.modules.knowledge.models import KnowledgeChunk, Source, SourceDocument
from app.modules.knowledge.persistence import stable_chunk_id, stable_document_id


@asynccontextmanager
async def isolated_session():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


async def motgu_project(session: AsyncSession) -> Project:
    return (await session.execute(select(Project).where(Project.slug == "motgu"))).scalar_one()


def test_canonicalization_url_and_source_fingerprint_are_stable() -> None:
    assert canonicalize_markdown("\ufeff# Title\r\n\r\n\r\nBody   \r\n") == "# Title\n\nBody"
    assert normalize_source_url("HTTPS://Example.TEST/path/#fragment") == (
        "https://example.test/path"
    )

    first = source_fingerprint(
        source_type="WEB",
        canonical_url="HTTPS://Example.TEST/path/#fragment",
        locator=None,
        provenance_json={"source_ref": "ignored-a"},
    )
    second = source_fingerprint(
        source_type="web",
        canonical_url="https://example.test/path",
        locator=None,
        provenance_json={"source_ref": "ignored-b"},
    )
    assert first == second


def test_chunk_markdown_is_deterministic_and_bounded() -> None:
    text = "\n\n".join(
        [
            "First paragraph has enough words to create a useful semantic boundary.",
            "Second paragraph also has enough words to make the split deterministic.",
            "X" * 190,
        ]
    )
    first = chunk_markdown(text, max_chars=80)
    second = chunk_markdown(text, max_chars=80)

    assert first == second
    assert len(first) > 2
    assert all(chunk for chunk in first)
    assert all(len(chunk) <= 80 for chunk in first)


@pytest.mark.asyncio
async def test_source_registry_is_idempotent() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        source_ref = f"manual:{uuid4()}"
        captured_at = datetime.now(UTC)

        first = await register_source(
            session,
            project_id=project.id,
            source_type="manual_document",
            title="Source title",
            locator=source_ref,
            provenance_json={"source_ref": source_ref, "method": "manual"},
            captured_at=captured_at,
            locale="en",
        )
        second = await register_source(
            session,
            project_id=project.id,
            source_type="manual_document",
            title="A later label must not create another source",
            locator=source_ref,
            provenance_json={"source_ref": source_ref, "method": "manual"},
            captured_at=captured_at,
            locale="en",
        )

        assert first.created is True
        assert second.created is False
        assert first.source.id == second.source.id
        count = await session.scalar(
            select(func.count(Source.id)).where(Source.fingerprint == first.source.fingerprint)
        )
        assert count == 1


@pytest.mark.asyncio
async def test_ingest_dedupes_same_content_and_versions_changed_content() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        source_ref = f"web:{uuid4()}"
        source = (
            await register_source(
                session,
                project_id=project.id,
                source_type="web",
                title="Example article",
                canonical_url=f"https://example.test/{source_ref}",
                provenance_json={"source_ref": source_ref, "method": "test"},
                captured_at=datetime.now(UTC),
                authority_hint="secondary",
                commercial_bias="low",
            )
        ).source

        first = await ingest_source_document(
            session,
            source_id=source.id,
            content_markdown="# Heading\r\n\r\nParagraph one.\r\n\r\nParagraph two.",
            fetched_at=datetime.now(UTC),
            reader="test",
            provider="manual",
            max_chunk_chars=40,
        )
        duplicate = await ingest_source_document(
            session,
            source_id=source.id,
            content_markdown="# Heading\n\nParagraph one.\n\n\nParagraph two.\n",
            fetched_at=datetime.now(UTC),
            reader="test",
            provider="manual",
            max_chunk_chars=40,
        )

        assert first.document_created is True
        assert duplicate.document_created is False
        assert duplicate.document.id == first.document.id
        assert duplicate.document.document_version == 1
        assert duplicate.document.id == stable_document_id(
            source_id=source.id,
            document_content_hash=first.document.content_hash,
        )
        assert [chunk.id for chunk in duplicate.chunks] == [chunk.id for chunk in first.chunks]
        assert all(len(chunk.text) <= 40 for chunk in first.chunks)
        for chunk in first.chunks:
            assert chunk.id == stable_chunk_id(
                source_document_id=first.document.id,
                text=chunk.text,
                ordinal=chunk.ordinal,
            )

        changed = await ingest_source_document(
            session,
            source_id=source.id,
            content_markdown="# Heading\n\nParagraph one changed.\n\nParagraph two.",
            fetched_at=datetime.now(UTC),
            reader="test",
            provider="manual",
            max_chunk_chars=40,
        )

        assert changed.document_created is True
        assert changed.document.document_version == 2
        assert changed.document.supersedes_id == first.document.id
        assert changed.document.id != first.document.id

        documents = tuple(
            (
                await session.execute(
                    select(SourceDocument)
                    .where(SourceDocument.source_id == source.id)
                    .order_by(SourceDocument.document_version)
                )
            )
            .scalars()
            .all()
        )
        assert [document.document_version for document in documents] == [1, 2]

        chunk_count = await session.scalar(
            select(func.count(KnowledgeChunk.id)).where(
                KnowledgeChunk.source_document_id == first.document.id
            )
        )
        assert chunk_count == len(first.chunks)


@pytest.mark.asyncio
async def test_existing_document_rejects_silent_rechunking() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        source_ref = f"manual:{uuid4()}"
        source = (
            await register_source(
                session,
                project_id=project.id,
                source_type="manual_document",
                locator=source_ref,
                provenance_json={"source_ref": source_ref},
                captured_at=datetime.now(UTC),
            )
        ).source
        content = "One paragraph with enough text that changing the chunk bound changes output."

        await ingest_source_document(
            session,
            source_id=source.id,
            content_markdown=content,
            fetched_at=datetime.now(UTC),
            max_chunk_chars=30,
        )

        with pytest.raises(ChunkingConflictError):
            await ingest_source_document(
                session,
                source_id=source.id,
                content_markdown=content,
                fetched_at=datetime.now(UTC),
                max_chunk_chars=60,
            )
