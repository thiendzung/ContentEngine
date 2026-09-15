from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.knowledge.harvest import (
    harvest_knowledge,
    verify_knowledge_harvest_snapshot,
)
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


@pytest.mark.asyncio
async def test_topic_semantic_change_creates_new_harvest_and_preserves_history() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key=f"k3-history-{uuid4().hex}",
            name="Original K3 topic meaning",
            node_type="topic",
            description="Original semantic description.",
            metadata_json={"fixture": "before"},
        )
        before = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-history",
        )
        before_hash = before.snapshot_hash
        before_graph = before.scope_graph_json
        verify_knowledge_harvest_snapshot(before)

        topic.name = "Updated K3 topic meaning"
        topic.description = "Updated semantic description."
        topic.metadata_json = {"fixture": "after"}
        await session.flush()

        verify_knowledge_harvest_snapshot(before)
        after = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-history",
        )

        assert after.id != before.id
        assert after.snapshot_hash != before_hash
        assert before.scope_graph_json == before_graph
        before_topics = before.scope_graph_json["topics"]
        after_topics = after.scope_graph_json["topics"]
        assert isinstance(before_topics, list)
        assert isinstance(after_topics, list)
        assert isinstance(before_topics[0], dict)
        assert isinstance(after_topics[0], dict)
        assert before_topics[0]["name"] == "Original K3 topic meaning"
        assert before_topics[0]["metadata"] == {"fixture": "before"}
        assert after_topics[0]["name"] == "Updated K3 topic meaning"
        assert after_topics[0]["metadata"] == {"fixture": "after"}
