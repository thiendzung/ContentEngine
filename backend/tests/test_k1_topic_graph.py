from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.knowledge.ingest import ingest_source_document, register_source
from app.modules.knowledge.models import Claim, Entity, KnowledgeCandidate
from app.modules.knowledge.topic_graph import (
    TopicGraphError,
    descendant_topic_ids,
    ensure_knowledge_topic_link,
    ensure_topic_edge,
    ensure_topic_node,
    normalize_topic_key,
)
from app.modules.knowledge.topic_models import KnowledgeTopicLink


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


async def add_other_project(session: AsyncSession) -> Project:
    project = Project(
        slug=f"topic-other-{uuid4().hex}",
        name="Topic Graph Other Project",
        status="active",
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


@pytest.mark.asyncio
async def test_topic_node_normalization_replay_and_conflict() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)

        first = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key="  Vietnamese   Ceramics  ",
            name="Vietnamese Ceramics",
            node_type="cluster",
        )
        replay = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key="vietnamese-ceramics",
            name="Vietnamese Ceramics",
            node_type="cluster",
        )

        assert first.id == replay.id
        assert first.canonical_key == "vietnamese-ceramics"
        assert normalize_topic_key("  Bát Tràng / Buying  ") == "bát-tràng-buying"

        with pytest.raises(TopicGraphError) as exc_info:
            await ensure_topic_node(
                session,
                project_id=project.id,
                canonical_key="vietnamese ceramics",
                name="Different Name",
                node_type="cluster",
            )
        assert exc_info.value.code == "topic_node_replay_conflict"


@pytest.mark.asyncio
async def test_topic_graph_supports_multiple_parents_and_contains_only_expansion() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        art = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key="vietnamese-art",
            name="Vietnamese Art",
            node_type="pillar",
        )
        ceramics = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key="vietnamese-ceramics",
            name="Vietnamese Ceramics",
            node_type="cluster",
        )
        travel = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key="vietnam-travel",
            name="Vietnam Travel",
            node_type="pillar",
        )
        hanoi_day_trips = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key="hanoi-day-trips",
            name="Hanoi Day Trips",
            node_type="cluster",
        )
        bat_trang = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key="bat-trang",
            name="Bat Trang",
            node_type="topic",
        )
        glazing = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key="bat-trang-glazing",
            name="Bat Trang Glazing",
            node_type="subtopic",
        )

        await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=art.id,
            child_topic_id=ceramics.id,
            relation_type="contains",
            created_by="test",
        )
        await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=travel.id,
            child_topic_id=hanoi_day_trips.id,
            relation_type="contains",
            created_by="test",
        )
        ceramics_parent = await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=ceramics.id,
            child_topic_id=bat_trang.id,
            relation_type="contains",
            created_by="test",
        )
        travel_parent = await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=hanoi_day_trips.id,
            child_topic_id=bat_trang.id,
            relation_type="contains",
            created_by="test",
        )
        await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=bat_trang.id,
            child_topic_id=glazing.id,
            relation_type="contains",
            created_by="test",
        )
        related = await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=ceramics.id,
            child_topic_id=hanoi_day_trips.id,
            relation_type="related",
            created_by="test",
        )
        related_replay = await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=hanoi_day_trips.id,
            child_topic_id=ceramics.id,
            relation_type="related",
            created_by="test",
        )

        assert ceramics_parent.id != travel_parent.id
        assert related.id == related_replay.id

        art_scope = await descendant_topic_ids(
            session,
            project_id=project.id,
            root_topic_id=art.id,
        )
        travel_scope = await descendant_topic_ids(
            session,
            project_id=project.id,
            root_topic_id=travel.id,
        )

        assert set(art_scope) == {art.id, ceramics.id, bat_trang.id, glazing.id}
        assert set(travel_scope) == {
            travel.id,
            hanoi_day_trips.id,
            bat_trang.id,
            glazing.id,
        }
        assert hanoi_day_trips.id not in art_scope
        assert ceramics.id not in travel_scope

        with pytest.raises(TopicGraphError) as cycle_info:
            await ensure_topic_edge(
                session,
                project_id=project.id,
                parent_topic_id=glazing.id,
                child_topic_id=art.id,
                relation_type="contains",
                created_by="test",
            )
        assert cycle_info.value.code == "topic_contains_cycle"

        unrelated_cluster = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key="other-cluster",
            name="Other Cluster",
            node_type="cluster",
        )
        with pytest.raises(TopicGraphError) as hierarchy_info:
            await ensure_topic_edge(
                session,
                project_id=project.id,
                parent_topic_id=glazing.id,
                child_topic_id=unrelated_cluster.id,
                relation_type="contains",
                created_by="test",
            )
        assert hierarchy_info.value.code == "topic_contains_hierarchy_invalid"


@pytest.mark.asyncio
async def test_knowledge_topic_links_support_all_durable_target_types_and_replay() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key=f"bat-trang-{uuid4().hex}",
            name="Bat Trang",
            node_type="topic",
        )

        claim = Claim(
            project_id=project.id,
            subject_entity_id=None,
            statement=f"Synthetic topic graph claim {uuid4()}",
            claim_type="fact",
            importance="normal",
            status="unverified",
            confidence=None,
            entity_refs_json=[],
        )
        entity = Entity(
            project_id=project.id,
            entity_type="place",
            canonical_key=f"bat-trang-{uuid4().hex}",
            canonical_name="Bat Trang",
            aliases_json=[],
            external_refs_json=[],
        )
        candidate = KnowledgeCandidate(
            project_id=project.id,
            locale="en",
            statement=f"Synthetic candidate {uuid4()}",
            summary="Synthetic reusable knowledge candidate.",
            source_refs_json=[],
            provenance_json={},
            entity_refs_json=[],
            status="CANDIDATE",
            reviewer=None,
            review_reason=None,
        )
        session.add_all([claim, entity, candidate])
        await session.flush()

        source = (
            await register_source(
                session,
                project_id=project.id,
                source_type="web",
                canonical_url=f"https://example.test/topic/{uuid4()}",
                provenance_json={"source_ref": f"k1:{uuid4()}", "method": "test"},
                captured_at=datetime.now(UTC),
                locale="en",
            )
        ).source
        ingested = await ingest_source_document(
            session,
            source_id=source.id,
            content_markdown="Bat Trang is synthetic topic graph test content.",
            fetched_at=datetime.now(UTC),
            reader="test",
            provider="manual",
        )
        chunk = ingested.chunks[0]

        claim_link = await ensure_knowledge_topic_link(
            session,
            project_id=project.id,
            topic_id=topic.id,
            target_type="claim",
            target_id=claim.id,
            link_method="manual",
            linked_by="founder",
        )
        claim_replay = await ensure_knowledge_topic_link(
            session,
            project_id=project.id,
            topic_id=topic.id,
            target_type="claim",
            target_id=claim.id,
            link_method="manual",
            linked_by="founder",
        )
        candidate_link = await ensure_knowledge_topic_link(
            session,
            project_id=project.id,
            topic_id=topic.id,
            target_type="knowledge_candidate",
            target_id=candidate.id,
            link_method="manual",
            linked_by="founder",
        )
        chunk_link = await ensure_knowledge_topic_link(
            session,
            project_id=project.id,
            topic_id=topic.id,
            target_type="chunk",
            target_id=chunk.id,
            link_method="deterministic",
            linked_by="policy:k1-test",
            relevance_score=900,
        )
        entity_link = await ensure_knowledge_topic_link(
            session,
            project_id=project.id,
            topic_id=topic.id,
            target_type="entity",
            target_id=entity.id,
            link_method="manual",
            linked_by="founder",
        )

        assert claim_link.id == claim_replay.id
        assert claim_link.claim_id == claim.id
        assert candidate_link.knowledge_candidate_id == candidate.id
        assert chunk_link.chunk_id == chunk.id
        assert entity_link.entity_id == entity.id

        with pytest.raises(TopicGraphError) as conflict_info:
            await ensure_knowledge_topic_link(
                session,
                project_id=project.id,
                topic_id=topic.id,
                target_type="claim",
                target_id=claim.id,
                link_method="model",
                linked_by="agent",
            )
        assert conflict_info.value.code == "topic_link_replay_conflict"


@pytest.mark.asyncio
async def test_topic_links_reject_cross_project_targets_and_db_rejects_multiple_targets() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        other = await add_other_project(session)
        topic = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key=f"cross-project-{uuid4().hex}",
            name="Cross Project Guard",
            node_type="topic",
        )
        other_claim = Claim(
            project_id=other.id,
            subject_entity_id=None,
            statement=f"Other project claim {uuid4()}",
            claim_type="fact",
            importance="normal",
            status="unverified",
            confidence=None,
            entity_refs_json=[],
        )
        local_claim = Claim(
            project_id=project.id,
            subject_entity_id=None,
            statement=f"Local claim {uuid4()}",
            claim_type="fact",
            importance="normal",
            status="unverified",
            confidence=None,
            entity_refs_json=[],
        )
        local_entity = Entity(
            project_id=project.id,
            entity_type="concept",
            canonical_key=f"local-entity-{uuid4().hex}",
            canonical_name="Local Entity",
            aliases_json=[],
            external_refs_json=[],
        )
        session.add_all([other_claim, local_claim, local_entity])
        await session.flush()

        with pytest.raises(TopicGraphError) as project_info:
            await ensure_knowledge_topic_link(
                session,
                project_id=project.id,
                topic_id=topic.id,
                target_type="claim",
                target_id=other_claim.id,
                link_method="manual",
                linked_by="founder",
            )
        assert project_info.value.code == "topic_link_target_project_mismatch"

        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    KnowledgeTopicLink(
                        project_id=project.id,
                        topic_id=topic.id,
                        claim_id=local_claim.id,
                        knowledge_candidate_id=None,
                        chunk_id=None,
                        entity_id=local_entity.id,
                        relevance_score=1000,
                        link_method="manual",
                        linked_by="test",
                        metadata_json={},
                    )
                )
                await session.flush()
