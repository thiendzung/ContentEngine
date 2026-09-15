from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.knowledge.models import Claim
from app.modules.knowledge.topic_graph import ensure_topic_node
from app.modules.knowledge.topic_models import KnowledgeTopicLink, TopicEdge


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


async def other_project(session: AsyncSession) -> Project:
    project = Project(
        slug=f"k1-db-guard-{uuid4().hex}",
        name="K1 DB Guard Other Project",
        status="active",
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


@pytest.mark.asyncio
async def test_database_rejects_cross_project_edge_and_knowledge_link() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        other = await other_project(session)
        local_pillar = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key=f"local-pillar-{uuid4().hex}",
            name="Local Pillar",
            node_type="pillar",
        )
        foreign_cluster = await ensure_topic_node(
            session,
            project_id=other.id,
            canonical_key=f"foreign-cluster-{uuid4().hex}",
            name="Foreign Cluster",
            node_type="cluster",
        )
        foreign_claim = Claim(
            project_id=other.id,
            subject_entity_id=None,
            statement=f"Foreign K1 claim {uuid4()}",
            claim_type="fact",
            importance="normal",
            status="unverified",
            confidence=None,
            entity_refs_json=[],
        )
        session.add(foreign_claim)
        await session.flush()

        with pytest.raises(DBAPIError, match="topic_edge_project_mismatch"):
            async with session.begin_nested():
                session.add(
                    TopicEdge(
                        project_id=project.id,
                        parent_topic_id=local_pillar.id,
                        child_topic_id=foreign_cluster.id,
                        relation_type="contains",
                        created_by="test",
                        metadata_json={},
                    )
                )
                await session.flush()

        with pytest.raises(DBAPIError, match="topic_link_target_project_mismatch"):
            async with session.begin_nested():
                session.add(
                    KnowledgeTopicLink(
                        project_id=project.id,
                        topic_id=local_pillar.id,
                        claim_id=foreign_claim.id,
                        knowledge_candidate_id=None,
                        chunk_id=None,
                        entity_id=None,
                        relevance_score=1000,
                        link_method="manual",
                        linked_by="test",
                        metadata_json={},
                    )
                )
                await session.flush()


@pytest.mark.asyncio
async def test_database_rejects_invalid_hierarchy_and_reverse_related_storage() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        pillar = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key=f"pillar-{uuid4().hex}",
            name="Pillar",
            node_type="pillar",
        )
        cluster = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key=f"cluster-{uuid4().hex}",
            name="Cluster",
            node_type="cluster",
        )
        topic = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key=f"topic-{uuid4().hex}",
            name="Topic",
            node_type="topic",
        )

        with pytest.raises(DBAPIError, match="topic_contains_hierarchy_invalid"):
            async with session.begin_nested():
                session.add(
                    TopicEdge(
                        project_id=project.id,
                        parent_topic_id=topic.id,
                        child_topic_id=cluster.id,
                        relation_type="contains",
                        created_by="test",
                        metadata_json={},
                    )
                )
                await session.flush()

        first_id, second_id = sorted((pillar.id, topic.id), key=str)
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    TopicEdge(
                        project_id=project.id,
                        parent_topic_id=second_id,
                        child_topic_id=first_id,
                        relation_type="related",
                        created_by="test",
                        metadata_json={},
                    )
                )
                await session.flush()
