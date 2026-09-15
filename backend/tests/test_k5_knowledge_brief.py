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
from app.modules.knowledge.brief import (
    BRIEF_METHOD,
    KnowledgeBriefError,
    derive_knowledge_brief,
    materialize_knowledge_brief,
    rebuild_knowledge_brief_snapshot,
    verify_knowledge_brief,
)
from app.modules.knowledge.brief_models import KnowledgeBrief
from app.modules.knowledge.coverage import (
    PLANNER_METHOD,
    derive_knowledge_coverage,
    plan_knowledge_coverage,
    rebuild_knowledge_coverage_plan_snapshot,
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
        slug=f"k5-{label}-{uuid4().hex}",
        name=f"K5 {label}",
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
        statement=f"K5 DB guard need {uuid4()}",
        audience_scope="test",
        situation="testing K5 DB guards",
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
        situation="testing K5 DB guards",
        need="test deterministic brief",
        question="What is reusable or missing?",
        intent="learn",
        promise="test",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new=f"K5 guard {uuid4()}",
        next_discovery_step="none",
        decision="CREATE",
        priority="NOW",
        reasons_json=[],
        suggested_content_type="journal",
        selected_by="founder",
        selected_at=T0,
        selection_reason="K5 test",
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
        canonical_key=f"k5-{label}-{uuid4().hex}",
        name=f"K5 {label}",
        node_type=node_type,  # type: ignore[arg-type]
        metadata_json={"fixture": "k5"},
    )


def topic_snapshot(topic_id: UUID, *, node_type: str, label: str) -> dict[str, object]:
    return {
        "topic_id": str(topic_id),
        "canonical_key": f"k5-{label}",
        "name": f"K5 {label}",
        "node_type": node_type,
        "description": None,
        "status": "active",
        "metadata": {"fixture": "k5"},
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
            "linked_by": "policy:k5-test",
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
            "review_reason": "Synthetic K5 fixture",
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
            "evidence_refs": [{"fixture": "k5"}],
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
    harvest = KnowledgeHarvest(
        id=UUID(int=999_101),
        project_id=UUID(int=1),
        content_case_id=None,
        locale="en",
        as_of=T0,
        requested_topic_ids_json=[str(root_topic_id)],
        expanded_topic_ids_json=[str(value["topic_id"]) for value in ordered_topics],
        scope_graph_json={
            "topics": ordered_topics,
            "contains_edges": ordered_edges,
        },
        items_json=ordered_items,
        harvest_method=HARVEST_METHOD,
        snapshot_hash="0" * 64,
        created_by="policy:k3-test",
    )
    _, snapshot_hash = rebuild_knowledge_harvest_snapshot(harvest)
    harvest.snapshot_hash = snapshot_hash
    return harvest


def synthetic_plan(harvest: KnowledgeHarvest) -> KnowledgeCoveragePlan:
    lanes, summary = derive_knowledge_coverage(harvest)
    plan = KnowledgeCoveragePlan(
        id=UUID(int=999_102),
        project_id=harvest.project_id,
        knowledge_harvest_id=harvest.id,
        content_case_id=harvest.content_case_id,
        locale=harvest.locale,
        harvest_snapshot_hash=harvest.snapshot_hash,
        planner_method=PLANNER_METHOD,
        lanes_json=lanes,
        summary_json=summary,
        snapshot_hash="0" * 64,
        created_by="policy:k4-test",
    )
    _, snapshot_hash = rebuild_knowledge_coverage_plan_snapshot(plan, harvest=harvest)
    plan.snapshot_hash = snapshot_hash
    return plan


def one_leaf_fixture(
    state: str,
) -> tuple[KnowledgeHarvest, KnowledgeCoveragePlan, dict[str, object]]:
    root = UUID(int=10)
    leaf = UUID(int=11)
    item = candidate_item(UUID(int=101), state=state, topic_ids=(leaf,))
    harvest = synthetic_harvest(
        root_topic_id=root,
        topics=[
            topic_snapshot(root, node_type="pillar", label="root"),
            topic_snapshot(leaf, node_type="topic", label="leaf"),
        ],
        edges=[edge_snapshot(root, leaf, edge_id=UUID(int=201))],
        items=[item],
    )
    return harvest, synthetic_plan(harvest), item


@pytest.mark.parametrize(
    ("state", "reusable", "research", "refresh", "policy"),
    [
        ("FRESH", True, False, False, False),
        ("DUE", True, False, True, False),
        ("STALE", False, True, False, False),
        ("UNKNOWN", False, True, False, False),
        ("UNCLASSIFIED", False, False, False, True),
    ],
)
def test_brief_preserves_freshness_semantics_without_inference(
    state: str,
    reusable: bool,
    research: bool,
    refresh: bool,
    policy: bool,
) -> None:
    harvest, plan, item = one_leaf_fixture(state)
    payload = derive_knowledge_brief(plan, harvest=harvest)

    assert payload["brief_method"] == BRIEF_METHOD
    reusable_items = payload["reusable_knowledge"]
    assert isinstance(reusable_items, list)
    assert bool(reusable_items) is reusable
    if reusable:
        assert reusable_items == [item]
    assert bool(payload["research_targets"]) is research
    assert bool(payload["refresh_recommendations"]) is refresh
    assert bool(payload["policy_required_targets"]) is policy


def test_missing_context_target_and_mixed_states_remain_orthogonal() -> None:
    root = UUID(int=20)
    missing = UUID(int=21)
    mixed = UUID(int=22)
    fresh = candidate_item(UUID(int=110), state="FRESH", topic_ids=(mixed,))
    stale = candidate_item(UUID(int=111), state="STALE", topic_ids=(mixed,))
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
        items=[fresh, stale],
    )
    payload = derive_knowledge_brief(synthetic_plan(harvest), harvest=harvest)

    reusable = payload["reusable_knowledge"]
    assert isinstance(reusable, list)
    assert [item["candidate_id"] for item in reusable] == [fresh["candidate_id"]]
    research_targets = payload["research_targets"]
    assert isinstance(research_targets, list)
    assert [target["topic_id"] for target in research_targets] == [
        str(missing),
        str(mixed),
    ]
    assert research_targets[0]["candidate_ids"] == []
    assert research_targets[1]["candidate_ids"] == [stale["candidate_id"]]
    assert str(root) not in {target["topic_id"] for target in research_targets}


def test_reusable_candidate_is_emitted_once_across_multiple_topics() -> None:
    root = UUID(int=30)
    first = UUID(int=31)
    second = UUID(int=32)
    candidate = candidate_item(
        UUID(int=120),
        state="FRESH",
        topic_ids=(first, second),
    )
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
        items=[candidate],
    )
    payload = derive_knowledge_brief(synthetic_plan(harvest), harvest=harvest)

    reusable = payload["reusable_knowledge"]
    assert isinstance(reusable, list)
    assert reusable == [candidate]
    assert len(reusable[0]["scoped_topic_links"]) == 2
    contexts = payload["topic_contexts"]
    assert isinstance(contexts, list)
    target_contexts = [lane for lane in contexts if lane["coverage_role"] == "target"]
    assert all(
        lane["reuse_candidate_ids"] == [candidate["candidate_id"]]
        for lane in target_contexts
    )


def test_corrupted_k3_or_k4_fails_closed_before_brief_derivation() -> None:
    harvest, plan, _ = one_leaf_fixture("FRESH")
    plan_hash = plan.snapshot_hash
    plan.snapshot_hash = "0" * 64
    with pytest.raises(KnowledgeBriefError, match="knowledge_brief_coverage_plan_hash_mismatch"):
        derive_knowledge_brief(plan, harvest=harvest)
    plan.snapshot_hash = plan_hash

    harvest_hash = harvest.snapshot_hash
    harvest.snapshot_hash = "0" * 64
    with pytest.raises(KnowledgeBriefError, match="knowledge_harvest_snapshot_hash_mismatch"):
        derive_knowledge_brief(plan, harvest=harvest)
    harvest.snapshot_hash = harvest_hash


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
        plan = await plan_knowledge_coverage(
            session,
            knowledge_harvest_id=harvest.id,
            created_by="policy:k4-plan",
        )
        first = await materialize_knowledge_brief(
            session,
            knowledge_coverage_plan_id=plan.id,
            created_by="policy:k5-first",
        )
        first_payload = first.brief_json
        first_hash = first.snapshot_hash

        replay = await materialize_knowledge_brief(
            session,
            knowledge_coverage_plan_id=plan.id,
            created_by="another-actor",
        )
        assert replay.id == first.id
        assert replay.snapshot_hash == first_hash
        assert replay.created_by == "policy:k5-first"

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

        historical = await materialize_knowledge_brief(
            session,
            knowledge_coverage_plan_id=plan.id,
            created_by="third-actor",
        )
        assert historical.id == first.id
        assert historical.brief_json == first_payload

        later_harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(root.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-harvest",
        )
        later_plan = await plan_knowledge_coverage(
            session,
            knowledge_harvest_id=later_harvest.id,
            created_by="policy:k4-plan",
        )
        later = await materialize_knowledge_brief(
            session,
            knowledge_coverage_plan_id=later_plan.id,
            created_by="policy:k5-later",
        )
        assert later.id != first.id
        assert later.snapshot_hash != first.snapshot_hash
        assert later.brief_json["expanded_topic_ids"] != first_payload["expanded_topic_ids"]


@pytest.mark.asyncio
async def test_persisted_payload_or_hash_corruption_fails_closed() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await create_topic(session, project=project, label="corruption")
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
            created_by="policy:k4-plan",
        )
        brief = await materialize_knowledge_brief(
            session,
            knowledge_coverage_plan_id=plan.id,
            created_by="policy:k5-test",
        )
        payload, recomputed_hash = rebuild_knowledge_brief_snapshot(
            brief,
            plan=plan,
            harvest=harvest,
        )
        assert payload == brief.brief_json
        assert recomputed_hash == brief.snapshot_hash

        await session.flush()
        session.expunge(brief)
        brief.brief_json = {**brief.brief_json, "reusable_knowledge": [{"forged": True}]}
        with pytest.raises(KnowledgeBriefError, match="knowledge_brief_payload_mismatch"):
            await verify_knowledge_brief(session, brief=brief)

        brief.brief_json = payload
        brief.snapshot_hash = "0" * 64
        with pytest.raises(KnowledgeBriefError, match="knowledge_brief_snapshot_hash_mismatch"):
            await verify_knowledge_brief(session, brief=brief)


def copied_brief(
    brief: KnowledgeBrief,
    *,
    snapshot_hash: str,
    project_id: UUID | None = None,
    plan_id: UUID | None = None,
    harvest_id: UUID | None = None,
    content_case_id: UUID | None | object = ...,
    locale: str | None = None,
    plan_hash: str | None = None,
    harvest_hash: str | None = None,
    created_by: str = "test",
) -> KnowledgeBrief:
    case_id = brief.content_case_id if content_case_id is ... else content_case_id
    assert case_id is None or isinstance(case_id, UUID)
    return KnowledgeBrief(
        project_id=project_id or brief.project_id,
        knowledge_coverage_plan_id=plan_id or brief.knowledge_coverage_plan_id,
        knowledge_harvest_id=harvest_id or brief.knowledge_harvest_id,
        content_case_id=case_id,
        locale=locale or brief.locale,
        coverage_plan_snapshot_hash=plan_hash or brief.coverage_plan_snapshot_hash,
        harvest_snapshot_hash=harvest_hash or brief.harvest_snapshot_hash,
        brief_method=BRIEF_METHOD,
        brief_json=brief.brief_json,
        snapshot_hash=snapshot_hash,
        created_by=created_by,
    )


@pytest.mark.asyncio
async def test_database_rejects_wrong_parent_bindings_blank_actor_and_duplicate() -> None:
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
            created_by="policy:k4-plan",
        )
        brief = await materialize_knowledge_brief(
            session,
            knowledge_coverage_plan_id=plan.id,
            created_by="policy:k5-test",
        )
        other_project = await create_project(session, label="wrong-project")
        other_case = await create_case(session, project=project)
        other_topic = await create_topic(session, project=project, label="other-harvest")
        other_harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(other_topic.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-harvest",
        )

        invalid_rows = [
            (
                copied_brief(
                    brief,
                    snapshot_hash="1" * 64,
                    project_id=other_project.id,
                ),
                "knowledge_brief_project_mismatch",
            ),
            (
                copied_brief(
                    brief,
                    snapshot_hash="2" * 64,
                    harvest_id=other_harvest.id,
                ),
                "knowledge_brief_harvest_mismatch",
            ),
            (
                copied_brief(
                    brief,
                    snapshot_hash="3" * 64,
                    content_case_id=other_case.id,
                ),
                "knowledge_brief_case_mismatch",
            ),
            (
                copied_brief(brief, snapshot_hash="4" * 64, locale="vi"),
                "knowledge_brief_locale_mismatch",
            ),
            (
                copied_brief(
                    brief,
                    snapshot_hash="5" * 64,
                    plan_hash="f" * 64,
                ),
                "knowledge_brief_plan_hash_mismatch",
            ),
            (
                copied_brief(
                    brief,
                    snapshot_hash="6" * 64,
                    harvest_hash="e" * 64,
                ),
                "knowledge_brief_harvest_hash_mismatch",
            ),
            (
                copied_brief(
                    brief,
                    snapshot_hash="7" * 64,
                    created_by="   ",
                ),
                "ck_knowledge_briefs_created_by_required",
            ),
            (
                copied_brief(brief, snapshot_hash="8" * 64),
                "uq_knowledge_briefs_plan_method",
            ),
        ]
        for invalid, expected in invalid_rows:
            with pytest.raises(DBAPIError, match=expected):
                async with session.begin_nested():
                    session.add(invalid)
                    await session.flush()


@pytest.mark.asyncio
async def test_database_rejects_brief_update_and_delete() -> None:
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
            created_by="policy:k4-plan",
        )
        brief = await materialize_knowledge_brief(
            session,
            knowledge_coverage_plan_id=plan.id,
            created_by="policy:k5-test",
        )

        with pytest.raises(DBAPIError, match="knowledge_brief_is_immutable"):
            async with session.begin_nested():
                brief.created_by = "changed"
                await session.flush()

        await session.refresh(brief)
        with pytest.raises(DBAPIError, match="knowledge_brief_is_immutable"):
            async with session.begin_nested():
                await session.delete(brief)
                await session.flush()
