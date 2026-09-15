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
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    NeedHypothesis,
    Project,
)
from app.modules.knowledge.harvest import harvest_knowledge
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


async def create_project(session: AsyncSession, *, label: str) -> Project:
    project = Project(
        slug=f"k3-{label}-{uuid4().hex}",
        name=f"K3 {label}",
        status="active",
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


async def create_case(session: AsyncSession, *, project: Project) -> ContentCase:
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement=f"K3 DB guard need {uuid4()}",
        audience_scope="test",
        situation="test",
        origin="founder_proposed",
        status="PROPOSED",
        alternative_explanations_json=[],
        missing_evidence_json=[],
    )
    session.add(need)
    await session.flush()
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader="test",
        situation="test",
        need="test",
        question="test?",
        intent="learn",
        promise="test",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new=f"K3 guard {uuid4()}",
        next_discovery_step="none",
        decision="CREATE",
        priority="NOW",
        reasons_json=[],
        suggested_content_type="journal",
        selected_by="founder",
        selected_at=T0,
        selection_reason="test",
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="test",
        content_hypothesis="test",
        originality_statement="test",
        reader_before="before",
        reader_after="after",
        status="draft",
    )
    session.add(content_case)
    await session.flush()
    return content_case


async def create_topic(
    session: AsyncSession,
    *,
    project: Project,
    label: str,
) -> TopicNode:
    return await ensure_topic_node(
        session,
        project_id=project.id,
        canonical_key=f"k3-{label}-{uuid4().hex}",
        name=f"K3 {label}",
        node_type="topic",
    )


def scope_graph(topic: TopicNode) -> dict[str, object]:
    return {
        "topics": [
            {
                "topic_id": str(topic.id),
                "canonical_key": topic.canonical_key,
                "name": topic.name,
                "node_type": topic.node_type,
                "description": topic.description,
                "status": topic.status,
                "metadata": topic.metadata_json,
            }
        ],
        "contains_edges": [],
    }


@pytest.mark.asyncio
async def test_database_rejects_cross_project_case_and_topic_scope() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await create_topic(session, project=project, label="local")
        other = await create_project(session, label="other")
        foreign_case = await create_case(session, project=other)

        with pytest.raises(DBAPIError, match="knowledge_harvest_case_project_mismatch"):
            async with session.begin_nested():
                session.add(
                    KnowledgeHarvest(
                        project_id=project.id,
                        content_case_id=foreign_case.id,
                        locale="en",
                        as_of=T0,
                        requested_topic_ids_json=[str(topic.id)],
                        expanded_topic_ids_json=[str(topic.id)],
                        scope_graph_json=scope_graph(topic),
                        items_json=[],
                        harvest_method="approved_candidate_topic_scope_v1",
                        snapshot_hash="a" * 64,
                        created_by="test",
                    )
                )
                await session.flush()

    async with isolated_session() as session:
        project = await motgu_project(session)
        other = await create_project(session, label="foreign-topic")
        foreign_topic = await create_topic(session, project=other, label="foreign")

        with pytest.raises(DBAPIError, match="knowledge_harvest_topic_project_mismatch"):
            async with session.begin_nested():
                session.add(
                    KnowledgeHarvest(
                        project_id=project.id,
                        content_case_id=None,
                        locale="en",
                        as_of=T0,
                        requested_topic_ids_json=[str(foreign_topic.id)],
                        expanded_topic_ids_json=[str(foreign_topic.id)],
                        scope_graph_json=scope_graph(foreign_topic),
                        items_json=[],
                        harvest_method="approved_candidate_topic_scope_v1",
                        snapshot_hash="b" * 64,
                        created_by="test",
                    )
                )
                await session.flush()


@pytest.mark.asyncio
async def test_database_rejects_harvest_update() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await create_topic(session, project=project, label="immutable-update")
        harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-harvest",
        )
        harvest.created_by = "changed"
        with pytest.raises(DBAPIError, match="knowledge_harvest_is_immutable"):
            async with session.begin_nested():
                await session.flush()


@pytest.mark.asyncio
async def test_database_rejects_harvest_delete() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await create_topic(session, project=project, label="immutable-delete")
        harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-harvest",
        )
        with pytest.raises(DBAPIError, match="knowledge_harvest_is_immutable"):
            async with session.begin_nested():
                await session.delete(harvest)
                await session.flush()
