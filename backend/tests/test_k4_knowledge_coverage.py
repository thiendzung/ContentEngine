from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

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
from app.modules.knowledge.coverage import (
    KnowledgeCoveragePlanError,
    derive_knowledge_coverage,
    plan_knowledge_coverage,
    rebuild_knowledge_coverage_plan_snapshot,
    verify_knowledge_coverage_plan,
)
from app.modules.knowledge.coverage_models import KnowledgeCoveragePlan
from app.modules.knowledge.harvest import (
    HARVEST_METHOD,
    harvest_knowledge,
    rebuild_knowledge_harvest_snapshot,
)
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


async def create_project(session: AsyncSession, *, label: str) -> Project:
    project = Project(
        slug=f"k4-{label}-{uuid4().hex}",
        name=f"K4 {label}",
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
        statement=f"K4 DB guard need {uuid4()}",
        audience_scope="test",
        situation="testing K4 DB guards",
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
        situation="testing K4 DB guards",
        need="test deterministic coverage",
        question="What is reusable or missing?",
        intent="learn",
        promise="test",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new=f"K4 guard {uuid4()}",
        next_discovery_step="none",
        decision="CREATE",
        priority="NOW",
        reasons_json=[],
        suggested_content_type="journal",
        selected_by="founder",
        selected_at=T0,
        selection_reason="K4 test",
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
    node_type: str = "topic",
) -> TopicNode:
    return await ensure_topic_node(
        session,
        project_id=project.id,
        canonical_key=f"k4-{label}-{uuid4().hex}",
        name=f"K4 {label}",
        node_type=node_type,  # type: ignore[arg-type]
        metadata_json={"fixture": "k4"},
    )


def topic_snapshot(topic_id: UUID, *, node_type: str, label: str) -> dict[str, object]:
    return {
        "topic_id": str(topic_id),
        "canonical_key": f"k4-{label}",
        "name": f"K4 {label}",
        "node_type": node_type,
        "description": None,
        "status": "active",
        "metadata": {"fixture": "k4"},
    }


def edge_snapshot(parent_id: UUID, child_id: UUID, *, edge_id: UUID) -> dict[str, object]:
    return {
        "edge_id": str(edge_id),
        "parent_topic_id": str(parent_id),
        "child_topic_id": str(child_id),
        "relation_type": "contains",
        "created_by": "test",
        "metadata": {},
    }


def candidate_item(
    candidate_id: UUID,
    *,
    state: str,
    topic_ids: tuple[UUID, ...],
) -> dict[str, object]:
    scoped_links = [
        {
            "link_id": str(UUID(int=10_000 + candidate_id.int * 10 + index)),
            "topic_id": str(topic_id),
            "relevance_score": 900,
            "link_method": "deterministic",
            "linked_by": "policy:k4-test",
            "metadata": {},
        }
        for index, topic_id in enumerate(sorted(topic_ids, key=str), start=1)
    ]
    base = candidate_id.int * 100
    return {
        "candidate_id": str(candidate_id),
        "candidate_content_hash": f"{candidate_id.int:064x}",
        "locale": "en",
        "statement": f"Synthetic statement {candidate_id}",
        "summary": f"Synthetic summary {candidate_id}",
        "entity_refs": [],
        "admission": {
            "status": "APPROVED",
            "reviewer": "founder",
            "review_reason": "Synthetic K4 fixture",
        },
        "scoped_topic_links": scoped_links,
        "freshness": {"state": state, "reasons": []},
        "lineage": {
            "evidence_set": {
                "id": str(UUID(int=base + 1)),
                "version": 1,
                "content_hash": "a" * 64,
            },
            "claim_id": str(UUID(int=base + 2)),
            "evidence_ids": [str(UUID(int=base + 3))],
            "source_document_ids": [str(UUID(int=base + 4))],
            "source_ids": [str(UUID(int=base + 5))],
            "relation_counts": {"supports": 1},
            "evidence_refs": [{"fixture": "k4"}],
        },
    }


def synthetic_harvest(
    *,
    root_topic_id: UUID,
    topics: list[dict[str, object]],
    edges: list[dict[str, object]],
    items: list[dict[str, object]],
) -> KnowledgeHarvest:
    ordered_topics = sorted(topics, key=lambda value: str(value["topic_id"]))
    ordered_edges = sorted(
        edges,
        key=lambda value: (
            str(value["parent_topic_id"]),
            str(value["child_topic_id"]),
            str(value["edge_id"]),
        ),
    )
    ordered_items = sorted(items, key=lambda value: str(value["candidate_id"]))
    expanded_ids = [str(value["topic_id"]) for value in ordered_topics]
    harvest = KnowledgeHarvest(
        id=UUID(int=999_001),
        project_id=UUID(int=1),
        content_case_id=None,
        locale="en",
        as_of=T0,
        requested_topic_ids_json=[str(root_topic_id)],
        expanded_topic_ids_json=expanded_ids,
        scope_graph_json={
            "topics": ordered_topics,
            "contains_edges": ordered_edges,
        },
        items_json=ordered_items,
        harvest_method=HARVEST_METHOD,
        snapshot_hash="0" * 64,
        created_by="policy:k4-test",
    )
    _, snapshot_hash = rebuild_knowledge_harvest_snapshot(harvest)
    harvest.snapshot_hash = snapshot_hash
    return harvest


def lane_by_id(
    lanes: list[dict[str, object]],
    topic_id: UUID,
) -> dict[str, object]:
    return next(lane for lane in lanes if lane["topic_id"] == str(topic_id))


@pytest.mark.parametrize(
    ("state", "reuse_ready", "research_required", "refresh", "policy"),
    [
        ("FRESH", True, False, False, False),
        ("DUE", True, False, True, False),
        ("STALE", False, True, False, False),
        ("UNKNOWN", False, True, False, False),
        ("UNCLASSIFIED", False, False, False, True),
    ],
)
def test_leaf_freshness_states_are_classified_without_collapsing_semantics(
    state: str,
    reuse_ready: bool,
    research_required: bool,
    refresh: bool,
    policy: bool,
) -> None:
    root = UUID(int=10)
    leaf = UUID(int=11)
    candidate = UUID(int=101)
    harvest = synthetic_harvest(
        root_topic_id=root,
        topics=[
            topic_snapshot(root, node_type="pillar", label="root"),
            topic_snapshot(leaf, node_type="topic", label="leaf"),
        ],
        edges=[edge_snapshot(root, leaf, edge_id=UUID(int=201))],
        items=[candidate_item(candidate, state=state, topic_ids=(leaf,))],
    )

    lanes, summary = derive_knowledge_coverage(harvest)
    root_lane = lane_by_id(lanes, root)
    leaf_lane = lane_by_id(lanes, leaf)

    assert root_lane["coverage_role"] == "context"
    assert root_lane["research_required"] is False
    assert leaf_lane["coverage_role"] == "target"
    assert leaf_lane["reuse_ready"] is reuse_ready
    assert leaf_lane["research_required"] is research_required
    assert leaf_lane["refresh_recommended"] is refresh
    assert leaf_lane["policy_required"] is policy
    assert summary["target_topic_ids"] == [str(leaf)]


def test_missing_context_and_target_and_mixed_states_remain_orthogonal() -> None:
    root = UUID(int=20)
    missing = UUID(int=21)
    mixed = UUID(int=22)
    fresh_candidate = UUID(int=110)
    stale_candidate = UUID(int=111)
    harvest = synthetic_harvest(
        root_topic_id=root,
        topics=[
            topic_snapshot(root, node_type="pillar", label="root"),
            topic_snapshot(missing, node_type="subtopic", label="missing"),
            topic_snapshot(mixed, node_type="topic", label="mixed"),
        ],
        edges=[
            edge_snapshot(root, missing, edge_id=UUID(int=220)),
            edge_snapshot(root, mixed, edge_id=UUID(int=221)),
        ],
        items=[
            candidate_item(fresh_candidate, state="FRESH", topic_ids=(mixed,)),
            candidate_item(stale_candidate, state="STALE", topic_ids=(mixed,)),
        ],
    )

    lanes, summary = derive_knowledge_coverage(harvest)
    root_lane = lane_by_id(lanes, root)
    missing_lane = lane_by_id(lanes, missing)
    mixed_lane = lane_by_id(lanes, mixed)

    assert root_lane["research_required"] is False
    assert "context_missing_candidate_not_required" in root_lane["reason_codes"]
    assert missing_lane["research_required"] is True
    assert "target_missing_candidate_requires_research" in missing_lane["reason_codes"]
    assert mixed_lane["reuse_ready"] is True
    assert mixed_lane["research_required"] is True
    assert mixed_lane["reuse_candidate_ids"] == [str(fresh_candidate)]
    assert mixed_lane["research_candidate_ids"] == [str(stale_candidate)]
    assert summary["research_required_topic_ids"] == [str(missing), str(mixed)]


def test_one_candidate_linked_to_multiple_targets_is_classified_in_each_lane() -> None:
    root = UUID(int=30)
    first = UUID(int=31)
    second = UUID(int=32)
    candidate = UUID(int=120)
    harvest = synthetic_harvest(
        root_topic_id=root,
        topics=[
            topic_snapshot(root, node_type="cluster", label="root"),
            topic_snapshot(first, node_type="topic", label="first"),
            topic_snapshot(second, node_type="subtopic", label="second"),
        ],
        edges=[
            edge_snapshot(root, first, edge_id=UUID(int=230)),
            edge_snapshot(root, second, edge_id=UUID(int=231)),
        ],
        items=[
            candidate_item(
                candidate,
                state="FRESH",
                topic_ids=(first, second),
            )
        ],
    )

    lanes, _ = derive_knowledge_coverage(harvest)
    for topic_id in (first, second):
        lane = lane_by_id(lanes, topic_id)
        assert lane["reuse_candidate_ids"] == [str(candidate)]
        assert lane["reuse_ready"] is True
        assert lane["research_required"] is False


@pytest.mark.asyncio
async def test_exact_replay_is_actor_independent_and_historical_graph_is_frozen() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        root = await create_topic(session, project=project, label="historical")
        harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(root.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-harvest",
        )
        first = await plan_knowledge_coverage(
            session,
            knowledge_harvest_id=harvest.id,
            created_by="policy:k4-first",
        )
        first_hash = first.snapshot_hash
        first_lanes = list(first.lanes_json)
        assert first_lanes[0]["coverage_role"] == "target"
        assert first_lanes[0]["research_required"] is True

        child = await create_topic(
            session,
            project=project,
            label="live-child",
            node_type="subtopic",
        )
        await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=root.id,
            child_topic_id=child.id,
            relation_type="contains",
            created_by="test",
        )

        replay = await plan_knowledge_coverage(
            session,
            knowledge_harvest_id=harvest.id,
            created_by="different-replay-actor",
        )
        assert replay.id == first.id
        assert replay.snapshot_hash == first_hash
        assert replay.created_by == "policy:k4-first"
        assert replay.lanes_json == first_lanes
        await verify_knowledge_coverage_plan(session, plan=replay)

        later_harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(root.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-harvest",
        )
        assert later_harvest.id != harvest.id
        later = await plan_knowledge_coverage(
            session,
            knowledge_harvest_id=later_harvest.id,
            created_by="policy:k4-later",
        )
        assert later.id != first.id
        assert later.snapshot_hash != first.snapshot_hash
        later_root = next(
            lane for lane in later.lanes_json if lane["topic_id"] == str(root.id)
        )
        later_child = next(
            lane for lane in later.lanes_json if lane["topic_id"] == str(child.id)
        )
        assert later_root["coverage_role"] == "context"
        assert later_root["research_required"] is False
        assert later_child["coverage_role"] == "target"
        assert later_child["research_required"] is True


@pytest.mark.asyncio
async def test_corrupted_harvest_or_plan_fails_closed() -> None:
    root = UUID(int=40)
    leaf = UUID(int=41)
    harvest = synthetic_harvest(
        root_topic_id=root,
        topics=[
            topic_snapshot(root, node_type="pillar", label="root"),
            topic_snapshot(leaf, node_type="topic", label="leaf"),
        ],
        edges=[edge_snapshot(root, leaf, edge_id=UUID(int=240))],
        items=[],
    )
    original_hash = harvest.snapshot_hash
    harvest.snapshot_hash = "0" * 64
    with pytest.raises(ValueError, match="knowledge_harvest_snapshot_hash_mismatch"):
        derive_knowledge_coverage(harvest)
    harvest.snapshot_hash = original_hash

    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await create_topic(session, project=project, label="corrupt-plan")
        persisted_harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-harvest",
        )
        plan = await plan_knowledge_coverage(
            session,
            knowledge_harvest_id=persisted_harvest.id,
            created_by="policy:k4-test",
        )
        await session.flush()
        session.expunge(plan)
        plan.lanes_json = []
        with pytest.raises(
            KnowledgeCoveragePlanError,
            match="knowledge_coverage_plan_lanes_mismatch",
        ):
            await verify_knowledge_coverage_plan(session, plan=plan)

        valid = await plan_knowledge_coverage(
            session,
            knowledge_harvest_id=persisted_harvest.id,
            created_by="policy:k4-test",
        )
        payload, recomputed_hash = rebuild_knowledge_coverage_plan_snapshot(
            valid,
            harvest=persisted_harvest,
        )
        assert payload["harvest_snapshot_hash"] == persisted_harvest.snapshot_hash
        assert recomputed_hash == valid.snapshot_hash


def copied_plan(
    plan: KnowledgeCoveragePlan,
    *,
    snapshot_hash: str,
    project_id: UUID | None = None,
    content_case_id: UUID | None | object = ...,
    locale: str | None = None,
    harvest_snapshot_hash: str | None = None,
    created_by: str = "test",
) -> KnowledgeCoveragePlan:
    case_id = plan.content_case_id if content_case_id is ... else content_case_id
    assert case_id is None or isinstance(case_id, UUID)
    return KnowledgeCoveragePlan(
        project_id=project_id or plan.project_id,
        knowledge_harvest_id=plan.knowledge_harvest_id,
        content_case_id=case_id,
        locale=locale or plan.locale,
        harvest_snapshot_hash=harvest_snapshot_hash or plan.harvest_snapshot_hash,
        planner_method=plan.planner_method,
        lanes_json=plan.lanes_json,
        summary_json=plan.summary_json,
        snapshot_hash=snapshot_hash,
        created_by=created_by,
    )


@pytest.mark.asyncio
async def test_database_rejects_wrong_harvest_bindings_blank_actor_and_duplicate() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await create_topic(session, project=project, label="db-bindings")
        harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-harvest",
        )
        plan = await plan_knowledge_coverage(
            session,
            knowledge_harvest_id=harvest.id,
            created_by="policy:k4-test",
        )
        other_project = await create_project(session, label="wrong-project")
        other_case = await create_case(session, project=project)

        invalid_rows = [
            (
                copied_plan(
                    plan,
                    snapshot_hash="1" * 64,
                    project_id=other_project.id,
                ),
                "knowledge_coverage_plan_project_mismatch",
            ),
            (
                copied_plan(
                    plan,
                    snapshot_hash="2" * 64,
                    content_case_id=other_case.id,
                ),
                "knowledge_coverage_plan_case_mismatch",
            ),
            (
                copied_plan(plan, snapshot_hash="3" * 64, locale="vi"),
                "knowledge_coverage_plan_locale_mismatch",
            ),
            (
                copied_plan(
                    plan,
                    snapshot_hash="4" * 64,
                    harvest_snapshot_hash="f" * 64,
                ),
                "knowledge_coverage_plan_harvest_hash_mismatch",
            ),
            (
                copied_plan(
                    plan,
                    snapshot_hash="5" * 64,
                    created_by="   ",
                ),
                "ck_knowledge_coverage_plans_created_by_required",
            ),
            (
                copied_plan(plan, snapshot_hash="6" * 64),
                "uq_knowledge_coverage_plans_harvest_method",
            ),
        ]
        for invalid, expected in invalid_rows:
            with pytest.raises(DBAPIError, match=expected):
                async with session.begin_nested():
                    session.add(invalid)
                    await session.flush()


@pytest.mark.asyncio
async def test_database_rejects_coverage_plan_update_and_delete() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await create_topic(session, project=project, label="immutable")
        harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-harvest",
        )
        plan = await plan_knowledge_coverage(
            session,
            knowledge_harvest_id=harvest.id,
            created_by="policy:k4-test",
        )

        with pytest.raises(DBAPIError, match="knowledge_coverage_plan_is_immutable"):
            async with session.begin_nested():
                plan.created_by = "changed"
                await session.flush()

        await session.refresh(plan)
        with pytest.raises(DBAPIError, match="knowledge_coverage_plan_is_immutable"):
            async with session.begin_nested():
                await session.delete(plan)
                await session.flush()
