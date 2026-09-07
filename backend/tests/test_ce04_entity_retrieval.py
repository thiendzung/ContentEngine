from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.knowledge.ingest import (
    DocumentIngestResult,
    ingest_source_document,
    register_source,
)
from app.modules.knowledge.models import Entity, Source
from app.modules.knowledge.retrieval import (
    ENTITY_LINKER_VERSION,
    RetrievalRankingPolicy,
    RetrievalRequest,
    link_document_entities,
    retrieve_chunks,
)


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


async def add_source_document(
    session: AsyncSession,
    *,
    project_id: UUID,
    content: str,
    source_type: str = "web",
    locale: str | None = "en",
    authority_hint: str | None = None,
    commercial_bias: str | None = None,
    metadata_json: dict[str, object] | None = None,
) -> tuple[Source, DocumentIngestResult]:
    source_ref = f"ce04-pr-b:{uuid4()}"
    source = (
        await register_source(
            session,
            project_id=project_id,
            source_type=source_type,
            canonical_url=f"https://example.test/{uuid4()}",
            provenance_json={"source_ref": source_ref, "method": "test"},
            captured_at=datetime.now(UTC),
            locale=locale,
            authority_hint=authority_hint,
            commercial_bias=commercial_bias,
        )
    ).source
    result = await ingest_source_document(
        session,
        source_id=source.id,
        content_markdown=content,
        fetched_at=datetime.now(UTC),
        metadata_json=metadata_json,
        reader="test",
        provider="manual",
        max_chunk_chars=2000,
    )
    return source, result


@pytest.mark.asyncio
async def test_entity_linking_is_project_scoped_idempotent_and_skips_ambiguous_aliases() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        other_project = Project(
            slug=f"other-{uuid4().hex}",
            name="Other project",
            status="active",
            default_locale="en",
        )
        session.add(other_project)
        await session.flush()

        hoa = Entity(
            project_id=project.id,
            entity_type="artist",
            canonical_key=f"hoa-le-{uuid4().hex}",
            canonical_name="Hoa Lê",
            aliases_json=["Hoa Le"],
            external_refs_json=[],
        )
        ambiguous_one = Entity(
            project_id=project.id,
            entity_type="place",
            canonical_key=f"place-one-{uuid4().hex}",
            canonical_name="Old Quarter",
            aliases_json=["Hanoi Core"],
            external_refs_json=[],
        )
        ambiguous_two = Entity(
            project_id=project.id,
            entity_type="place",
            canonical_key=f"place-two-{uuid4().hex}",
            canonical_name="Central Hanoi",
            aliases_json=["Hanoi Core"],
            external_refs_json=[],
        )
        short_name = Entity(
            project_id=project.id,
            entity_type="concept",
            canonical_key=f"art-{uuid4().hex}",
            canonical_name="Art",
            aliases_json=[],
            external_refs_json=[],
        )
        same_alias_other_project = Entity(
            project_id=other_project.id,
            entity_type="artist",
            canonical_key=f"other-hoa-{uuid4().hex}",
            canonical_name="Other Hoa",
            aliases_json=["Hoa Le"],
            external_refs_json=[],
        )
        session.add_all(
            [
                hoa,
                ambiguous_one,
                ambiguous_two,
                short_name,
                same_alias_other_project,
            ]
        )
        await session.flush()

        _, ingested = await add_source_document(
            session,
            project_id=project.id,
            content="Hoa Le works near the Hanoi Core. The artist welcomes visitors.",
        )

        first = await link_document_entities(
            session,
            source_document_id=ingested.document.id,
        )
        second = await link_document_entities(
            session,
            source_document_id=ingested.document.id,
        )

        assert len(first) == 1
        assert [link.entity_id for link in first[0].linked_entities] == [hoa.id]
        assert first[0].ambiguous_aliases == ("hanoi core",)
        assert first[0].changed is True
        assert second[0].changed is False

        metadata = ingested.chunks[0].metadata_json
        assert metadata["entity_linker_version"] == ENTITY_LINKER_VERSION
        assert metadata["entity_links"] == [
            {
                "entity_id": str(hoa.id),
                "canonical_key": hoa.canonical_key,
                "matched_aliases": ["hoa le"],
                "method": "exact_alias",
            }
        ]
        assert metadata["entity_link_conflicts"] == ["hanoi core"]
        assert str(short_name.id) not in str(metadata["entity_links"])
        assert str(same_alias_other_project.id) not in str(metadata["entity_links"])


@pytest.mark.asyncio
async def test_retrieval_uses_latest_document_and_ignores_search_rank_for_authority() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)

        primary_source, primary = await add_source_document(
            session,
            project_id=project.id,
            content="original art hanoi",
            authority_hint="primary",
            commercial_bias="low",
            metadata_json={"rank_position": 20},
        )
        low_source, low = await add_source_document(
            session,
            project_id=project.id,
            content="original art hanoi",
            authority_hint="low",
            commercial_bias="high",
            metadata_json={"rank_position": 1},
        )
        stale_source, stale_v1 = await add_source_document(
            session,
            project_id=project.id,
            content="original art hanoi",
            authority_hint="primary",
            commercial_bias="low",
            metadata_json={"rank_position": 1},
        )
        stale_v2 = await ingest_source_document(
            session,
            source_id=stale_source.id,
            content_markdown="replacement notice with no matching topic",
            fetched_at=datetime.now(UTC),
            metadata_json={"rank_position": 1},
            max_chunk_chars=2000,
        )
        assert stale_v2.document.document_version == 2

        request = RetrievalRequest(
            project_id=project.id,
            query="original art hanoi",
            locale="en",
            limit=10,
        )
        hits = await retrieve_chunks(session, request=request)
        repeated_hits = await retrieve_chunks(session, request=request)

        assert [hit.chunk_id for hit in repeated_hits] == [hit.chunk_id for hit in hits]
        assert [hit.source_id for hit in hits[:2]] == [primary_source.id, low_source.id]
        assert stale_source.id not in {hit.source_id for hit in hits}
        assert stale_v1.document.id != stale_v2.document.id
        assert hits[0].source_document_id == primary.document.id
        assert hits[1].source_document_id == low.document.id
        assert "ranking_policy:ce04-v1" in hits[0].ranking_reasons
        assert "authority_hint:primary" in hits[0].ranking_reasons
        assert "authority_hint:low" in hits[1].ranking_reasons
        assert all("rank_position" not in reason for hit in hits for reason in hit.ranking_reasons)

        reversed_policy = RetrievalRankingPolicy(
            version="test-reversed-authority",
            authority_tiers=(("primary",), ("low",)),
            authority_unknown_rank=1,
            commercial_bias_tiers=(("high", "medium", "none", "low"),),
            commercial_bias_unknown_rank=1,
        )
        reversed_hits = await retrieve_chunks(
            session,
            request=RetrievalRequest(
                project_id=project.id,
                query="original art hanoi",
                locale="en",
                limit=10,
                ranking_policy=reversed_policy,
            ),
        )
        assert [hit.source_id for hit in reversed_hits[:2]] == [low_source.id, primary_source.id]
        assert "ranking_policy:test-reversed-authority" in reversed_hits[0].ranking_reasons


@pytest.mark.asyncio
async def test_relevance_and_entity_match_beat_stronger_authority_when_text_is_better() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        hoa = Entity(
            project_id=project.id,
            entity_type="artist",
            canonical_key=f"retrieval-hoa-{uuid4().hex}",
            canonical_name="Hoa Lê",
            aliases_json=["Hoa Le"],
            external_refs_json=[],
        )
        session.add(hoa)
        await session.flush()

        relevant_source, relevant = await add_source_document(
            session,
            project_id=project.id,
            content="Hoa Le artwork price",
            authority_hint="low",
            commercial_bias="high",
        )
        authority_source, authority = await add_source_document(
            session,
            project_id=project.id,
            content="Hoa Le artwork",
            authority_hint="primary",
            commercial_bias="low",
        )
        _, vietnamese = await add_source_document(
            session,
            project_id=project.id,
            content="Hoa Le artwork price",
            locale="vi-VN",
            authority_hint="primary",
            commercial_bias="low",
        )

        await link_document_entities(session, source_document_id=relevant.document.id)
        await link_document_entities(session, source_document_id=authority.document.id)
        await link_document_entities(session, source_document_id=vietnamese.document.id)

        hits = await retrieve_chunks(
            session,
            request=RetrievalRequest(
                project_id=project.id,
                query="Hoa Le artwork price",
                locale="en",
            ),
        )

        assert hits[0].source_id == relevant_source.id
        assert hits[0].exact_phrase is True
        assert hits[0].matched_entity_ids == (hoa.id,)
        assert authority_source.id in {hit.source_id for hit in hits}
        assert vietnamese.document.id not in {hit.source_document_id for hit in hits}


@pytest.mark.asyncio
async def test_preferred_source_type_is_an_explicit_tie_break_not_global_authority() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        web_source, _ = await add_source_document(
            session,
            project_id=project.id,
            content="studio visit practical guide",
            source_type="web",
            authority_hint="secondary",
            commercial_bias="medium",
        )
        manual_source, _ = await add_source_document(
            session,
            project_id=project.id,
            content="studio visit practical guide",
            source_type="manual_document",
            authority_hint="secondary",
            commercial_bias="medium",
        )

        default_hits = await retrieve_chunks(
            session,
            request=RetrievalRequest(
                project_id=project.id,
                query="studio visit practical guide",
            ),
        )
        preferred_hits = await retrieve_chunks(
            session,
            request=RetrievalRequest(
                project_id=project.id,
                query="studio visit practical guide",
                preferred_source_types=("MANUAL_DOCUMENT",),
            ),
        )

        assert {default_hits[0].source_id, default_hits[1].source_id} == {
            web_source.id,
            manual_source.id,
        }
        assert preferred_hits[0].source_id == manual_source.id
        assert "preferred_source_type:manual_document" in preferred_hits[0].ranking_reasons


@pytest.mark.asyncio
async def test_retrieval_rejects_empty_query_and_unbounded_limit() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)

        with pytest.raises(ValueError, match="searchable text"):
            await retrieve_chunks(
                session,
                request=RetrievalRequest(project_id=project.id, query="   "),
            )

        with pytest.raises(ValueError, match="between 1 and 50"):
            await retrieve_chunks(
                session,
                request=RetrievalRequest(project_id=project.id, query="art", limit=51),
            )
