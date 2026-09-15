from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import Project
from app.modules.knowledge.harvest_models import KnowledgeHarvest
from app.modules.knowledge.topic_graph import ensure_topic_edge, ensure_topic_node
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


async def topic(
    session: AsyncSession,
    *,
    project: Project,
    label: str,
    node_type: str = "topic",
) -> TopicNode:
    return await ensure_topic_node(
        session,
        project_id=project.id,
        canonical_key=f"k3-db-semantic-{label}-{uuid4().hex}",
        name=f"K3 DB semantic {label}",
        node_type=node_type,  # type: ignore[arg-type]
        metadata_json={"fixture": "k3-db-semantic"},
    )


def topic_snapshot(value: TopicNode) -> dict[str, object]:
    return {
        "topic_id": str(value.id),
        "canonical_key": value.canonical_key,
        "name": value.name,
        "node_type": value.node_type,
        "description": value.description,
        "status": value.status,
        "metadata": value.metadata_json,
    }


def scope_graph(topics: list[TopicNode]) -> dict[str, object]:
    return {
        "topics": [topic_snapshot(value) for value in sorted(topics, key=lambda row: str(row.id))],
        "contains_edges": [],
    }


def row(
    *,
    project: Project,
    requested: list[str],
    expanded: list[str],
    snapshot_hash: str,
    graph: dict[str, object] | None = None,
) -> KnowledgeHarvest:
    return KnowledgeHarvest(
        project_id=project.id,
        content_case_id=None,
        locale="en",
        as_of=T0,
        requested_topic_ids_json=requested,
        expanded_topic_ids_json=expanded,
        scope_graph_json=graph or {"topics": [], "contains_edges": []},
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


@pytest.mark.asyncio
async def test_database_rejects_scope_topic_semantic_snapshot_mismatch() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        scoped = await topic(session, project=project, label="semantic-mismatch")
        graph = deepcopy(scope_graph([scoped]))
        topics = graph["topics"]
        assert isinstance(topics, list)
        snapshot = topics[0]
        assert isinstance(snapshot, dict)
        snapshot["name"] = "Wrong historical meaning"

        with pytest.raises(
            DBAPIError,
            match="knowledge_harvest_scope_topic_snapshot_mismatch",
        ):
            async with session.begin_nested():
                session.add(
                    row(
                        project=project,
                        requested=[str(scoped.id)],
                        expanded=[str(scoped.id)],
                        graph=graph,
                        snapshot_hash="4" * 64,
                    )
                )
                await session.flush()


@pytest.mark.asyncio
async def test_database_rejects_missing_induced_contains_edge() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        root = await topic(
            session,
            project=project,
            label="edge-root",
            node_type="pillar",
        )
        child = await topic(
            session,
            project=project,
            label="edge-child",
            node_type="topic",
        )
        await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=root.id,
            child_topic_id=child.id,
            relation_type="contains",
            created_by="test",
        )
        expanded = sorted([str(root.id), str(child.id)])

        with pytest.raises(DBAPIError, match="knowledge_harvest_scope_edge_set_mismatch"):
            async with session.begin_nested():
                session.add(
                    row(
                        project=project,
                        requested=[str(root.id)],
                        expanded=expanded,
                        graph=scope_graph([root, child]),
                        snapshot_hash="5" * 64,
                    )
                )
                await session.flush()
