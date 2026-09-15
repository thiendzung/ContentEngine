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
from app.modules.knowledge.harvest_models import KnowledgeHarvest
from app.modules.knowledge.topic_graph import ensure_topic_node
from app.modules.knowledge.topic_models import TopicNode

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


async def topic(session: AsyncSession, *, project: Project, label: str) -> TopicNode:
    return await ensure_topic_node(
        session,
        project_id=project.id,
        canonical_key=f"k3-db-semantic-{label}-{uuid4().hex}",
        name=f"K3 DB semantic {label}",
        node_type="topic",
    )


def row(
    *,
    project: Project,
    requested: list[str],
    expanded: list[str],
    snapshot_hash: str,
) -> KnowledgeHarvest:
    return KnowledgeHarvest(
        project_id=project.id,
        content_case_id=None,
        locale="en",
        as_of=T0,
        requested_topic_ids_json=requested,
        expanded_topic_ids_json=expanded,
        scope_graph_json={"topics": [], "contains_edges": []},
        items_json=[],
        harvest_method="approved_candidate_topic_scope_v1",
        snapshot_hash=snapshot_hash,
        created_by="test",
    )


@pytest.mark.asyncio
async def test_database_rejects_requested_topic_outside_expanded_scope() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        requested = await topic(session, project=project, label="requested")
        expanded = await topic(session, project=project, label="expanded")
        with pytest.raises(DBAPIError, match="knowledge_harvest_requested_not_in_expanded"):
            async with session.begin_nested():
                session.add(
                    row(
                        project=project,
                        requested=[str(requested.id)],
                        expanded=[str(expanded.id)],
                        snapshot_hash="1" * 64,
                    )
                )
                await session.flush()


@pytest.mark.asyncio
async def test_database_rejects_duplicate_expanded_topics() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        scoped = await topic(session, project=project, label="duplicate")
        with pytest.raises(DBAPIError, match="knowledge_harvest_expanded_topic_duplicate"):
            async with session.begin_nested():
                session.add(
                    row(
                        project=project,
                        requested=[str(scoped.id)],
                        expanded=[str(scoped.id), str(scoped.id)],
                        snapshot_hash="2" * 64,
                    )
                )
                await session.flush()


@pytest.mark.asyncio
async def test_database_rejects_noncanonical_expanded_topic_order() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        first = await topic(session, project=project, label="order-a")
        second = await topic(session, project=project, label="order-b")
        canonical = sorted([str(first.id), str(second.id)])
        reversed_order = list(reversed(canonical))
        with pytest.raises(DBAPIError, match="knowledge_harvest_expanded_topics_not_canonical"):
            async with session.begin_nested():
                session.add(
                    row(
                        project=project,
                        requested=[canonical[0]],
                        expanded=reversed_order,
                        snapshot_hash="3" * 64,
                    )
                )
                await session.flush()
