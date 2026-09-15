from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.knowledge.harvest import harvest_knowledge
from app.modules.knowledge.harvest_models import KnowledgeHarvest
from app.modules.knowledge.topic_graph import ensure_topic_node

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
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


async def empty_topic(session: AsyncSession, *, project: Project):
    return await ensure_topic_node(
        session,
        project_id=project.id,
        canonical_key=f"k3-replay-{uuid4().hex}",
        name="K3 replay fixture",
        node_type="topic",
    )


@pytest.mark.asyncio
async def test_exact_semantic_replay_is_actor_independent() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await empty_topic(session, project=project)
        first = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-first-actor",
        )
        replay = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=T0,
            created_by="operator:k3-second-actor",
        )

        assert replay.id == first.id
        assert replay.snapshot_hash == first.snapshot_hash
        assert replay.created_by == "policy:k3-first-actor"


@pytest.mark.asyncio
async def test_database_rejects_blank_harvest_audit_actor() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await empty_topic(session, project=project)
        invalid = KnowledgeHarvest(
            project_id=project.id,
            content_case_id=None,
            locale="en",
            as_of=T0,
            requested_topic_ids_json=[str(topic.id)],
            expanded_topic_ids_json=[str(topic.id)],
            items_json=[],
            harvest_method="approved_candidate_topic_scope_v1",
            snapshot_hash="a" * 64,
            created_by="   ",
        )
        session.add(invalid)
        with pytest.raises(DBAPIError, match="ck_knowledge_harvests_created_by_required"):
            await session.flush()
