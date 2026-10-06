from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentExperiment,
    ContentItem,
    ContentOpportunity,
    ContentOpportunitySignal,
    ContentVersion,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.research.keyword_plan.opportunity_handoff_models import (
    OpportunityPlannerHandoff,
)
from app.modules.research.keyword_plan.opportunity_handoff_v2 import (
    OpportunityHandoffError,
    select_opportunity_plan_v2,
)
from app.modules.research.keyword_plan.opportunity_planner_v2 import (
    build_opportunity_plan_v2,
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


async def _project(session: AsyncSession) -> Project:
    project = Project(
        slug=f"qm02a-{uuid4().hex[:8]}",
        name="QM-02A",
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


async def _need(
    session: AsyncSession,
    project: Project,
    *,
    status: str = "SUPPORTED",
) -> NeedHypothesis:
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement="Buyer needs budget clarity.",
        audience_scope="first-time buyer",
        situation="considering an artwork",
        origin="customer_intelligence",
        status=status,
        alternative_explanations_json=[],
        missing_evidence_json=[],
        version=2,
    )
    session.add(need)
    await session.flush()
    return need


async def _signal(
    session: AsyncSession,
    project: Project,
    need: NeedHypothesis,
    *,
    text_value: str,
    relation: str = "supports",
    source_kind: str = "SEARCH",
    locale: str = "en",
) -> Signal:
    signal = Signal(
        project_id=project.id,
        source_kind=source_kind,
        scope="market_web" if source_kind != "MOTGU" else "motgu_direct",
        observed_text=text_value,
        source_url=f"https://example.com/{uuid4().hex}",
        locale=locale,
        context="QM-02A fixture",
        captured_at=datetime.now(UTC),
        fingerprint=uuid4().hex,
        independence_group=uuid4().hex,
        provenance_json={
            "provider": "fixture",
            "method": (
                "people_also_ask"
                if source_kind == "SEARCH"
                else "reviewed_motgu_direct_observation"
            ),
        },
    )
    session.add(signal)
    await session.flush()
    session.add(
        NeedHypothesisSignal(
            need_hypothesis_id=need.id,
            signal_id=signal.id,
            relation=relation,
        )
    )
    await session.flush()
    return signal


async def _budget_search_inputs(
    session: AsyncSession,
    project: Project,
    need: NeedHypothesis,
) -> tuple[Signal, Signal]:
    first = await _signal(
        session,
        project,
        need,
        text_value="How much should I spend on art?",
    )
    second = await _signal(
        session,
        project,
        need,
        text_value="What budget should I set for my first painting?",
    )
    return first, second


async def _planner(
    session: AsyncSession,
    project: Project,
    need: NeedHypothesis,
) -> tuple[dict[str, object], dict[str, object]]:
    plan = await build_opportunity_plan_v2(
        session,
        project_id=project.id,
        need_id=need.id,
        locale="en",
    )
    recommendations = plan["recommendations"]
    assert isinstance(recommendations, list)
    assert len(recommendations) == 1
    row = recommendations[0]
    assert isinstance(row, dict)
    return plan, row


async def _selected_plan(
    session: AsyncSession,
    project: Project,
    need: NeedHypothesis,
    *,
    decision: str = "CREATE",
) -> tuple[ContentOpportunity, HumanSelection]:
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader=need.audience_scope,
        situation=need.situation,
        need=need.statement,
        question="What budget should I set for a painting?",
        intent="evaluate",
        promise="Help the reader plan a budget.",
        coverage_requirements_json=[],
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Existing selected planning fixture.",
        next_discovery_step="Relevant Artwork / Artist",
        decision=decision,
        priority="NEXT" if decision != "DO_NOT_WRITE" else "NO",
        reasons_json=["fixture"],
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
        selected_by="founder",
        selected_at=datetime.now(UTC),
        selection_reason="Existing selected plan.",
    )
    session.add(opportunity)
    await session.flush()
    selection = HumanSelection(
        content_opportunity_id=opportunity.id,
        selected_by="founder",
        reason="Existing selected plan.",
        selected_at=opportunity.selected_at,
    )
    session.add(selection)
    await session.flush()
    return opportunity, selection


async def _published_primary(
    session: AsyncSession,
    project: Project,
    need: NeedHypothesis,
) -> ContentItem:
    seed_opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader=need.audience_scope,
        situation=need.situation,
        need=need.statement,
        question="Legacy seed planning row",
        intent="learn",
        promise="Seed published content.",
        coverage_requirements_json=[],
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Seed only.",
        next_discovery_step="None",
        decision="CREATE",
        priority="LATER",
        reasons_json=["seed"],
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
    )
    session.add(seed_opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=seed_opportunity.id,
        desired_action="read",
        content_hypothesis="Existing content answers the budget question.",
        originality_statement="Fixture.",
        reader_before="uncertain",
        reader_after="better informed",
        status="draft",
    )
    session.add(content_case)
    await session.flush()
    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="cluster",
        primary_question="What budget should I set for a painting?",
        primary_intent="evaluate",
        status="draft",
    )
    session.add(variant)
    await session.flush()
    item = ContentItem(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_type="journal",
        status="published",
        canonical_key=f"journal:qm02a-{uuid4().hex}",
    )
    session.add(item)
    await session.flush()
    session.add(
        ContentVersion(
            content_item_id=item.id,
            version_no=1,
            change_reason="QM-02A fixture",
            status="published",
            content_json={"title": "Budget guide"},
        )
    )
    await session.flush()
    return item


async def _count(
    session: AsyncSession,
    model: type[object],
) -> int:
    value = await session.scalar(select(func.count()).select_from(model))
    assert value is not None
    return int(value)


@pytest.mark.asyncio
async def test_qm02a_selects_missing_cluster_once_with_exact_lineage() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project)
        search_a, search_b = await _budget_search_inputs(
            session,
            project,
            need,
        )
        plan, recommendation = await _planner(session, project, need)
        assert recommendation["decision"] == "CREATE"
        assert (
            recommendation["selection_readiness"]
            == "READY_FOR_HUMAN_SELECTION"
        )

        before_cases = await _count(session, ContentCase)
        before_experiments = await _count(session, ContentExperiment)

        receipt = await select_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
            cluster_key=str(recommendation["cluster_key"]),
            expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
            idempotency_key="qm02a-select-create-once",
            selected_by="founder",
            reason="Select this cluster for durable planning.",
        )

        assert receipt["resolution"] == "SELECTED"
        assert receipt["replayed"] is False
        assert receipt["planner_snapshot_hash"] == plan["snapshot_hash"]
        assert (
            receipt["question_coverage_snapshot_hash"]
            == plan["question_coverage_snapshot_hash"]
        )
        assert receipt["semantics"]["drafting_authorized"] is False

        opportunity = await session.get(
            ContentOpportunity,
            UUID(str(receipt["content_opportunity_id"])),
        )
        selection = await session.get(
            HumanSelection,
            UUID(str(receipt["human_selection_id"])),
        )
        assert opportunity is not None
        assert selection is not None
        assert opportunity.selected_by == "founder"
        assert opportunity.decision == "CREATE"
        assert opportunity.suggested_content_type == "journal"
        assert opportunity.suggested_role == "cluster"
        assert opportunity.coverage_requirements_json == []
        assert opportunity.motgu_material_refs_json == []
        assert "does not prove MOTGU Right-to-Win" in (
            " ".join(opportunity.material_gaps_json)
        )

        linked = set(
            await session.scalars(
                select(ContentOpportunitySignal.signal_id).where(
                    ContentOpportunitySignal.content_opportunity_id
                    == opportunity.id
                )
            )
        )
        assert linked == {search_a.id, search_b.id}
        assert await _count(session, ContentCase) == before_cases
        assert await _count(session, ContentExperiment) == before_experiments
        assert await _count(session, OpportunityPlannerHandoff) == 1

        replay = await select_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
            cluster_key=str(recommendation["cluster_key"]),
            expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
            idempotency_key="qm02a-select-create-once",
            selected_by="founder",
            reason="Select this cluster for durable planning.",
        )
        assert replay["handoff_id"] == receipt["handoff_id"]
        assert replay["content_opportunity_id"] == (
            receipt["content_opportunity_id"]
        )
        assert replay["human_selection_id"] == receipt["human_selection_id"]
        assert replay["replayed"] is True
        assert await _count(session, OpportunityPlannerHandoff) == 1


@pytest.mark.asyncio
async def test_qm02a_idempotency_conflict_and_stale_snapshot_fail_closed() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project)
        await _budget_search_inputs(session, project, need)
        plan, recommendation = await _planner(session, project, need)

        with pytest.raises(
            OpportunityHandoffError,
            match="opportunity_handoff_planner_snapshot_stale",
        ):
            await select_opportunity_plan_v2(
                session,
                project_id=project.id,
                need_id=need.id,
                locale="en",
                cluster_key=str(recommendation["cluster_key"]),
                expected_planner_snapshot_hash="b" * 64,
                idempotency_key="qm02a-stale",
                selected_by="founder",
                reason="Stale request.",
            )
        assert await _count(session, OpportunityPlannerHandoff) == 0
        assert await _count(session, HumanSelection) == 0

        await select_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
            cluster_key=str(recommendation["cluster_key"]),
            expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
            idempotency_key="qm02a-conflict",
            selected_by="founder",
            reason="Original selection.",
        )
        with pytest.raises(
            OpportunityHandoffError,
            match="opportunity_handoff_idempotency_conflict",
        ):
            await select_opportunity_plan_v2(
                session,
                project_id=project.id,
                need_id=need.id,
                locale="en",
                cluster_key=str(recommendation["cluster_key"]),
                expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
                idempotency_key="qm02a-conflict",
                selected_by="founder",
                reason="Different selection reason.",
            )


@pytest.mark.asyncio
async def test_qm02a_same_snapshot_cluster_cannot_be_selected_twice() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project)
        await _budget_search_inputs(session, project, need)
        plan, recommendation = await _planner(session, project, need)

        await select_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
            cluster_key=str(recommendation["cluster_key"]),
            expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
            idempotency_key="qm02a-first-key",
            selected_by="founder",
            reason="First exact selection.",
        )
        with pytest.raises(
            OpportunityHandoffError,
            match="opportunity_handoff_cluster_already_selected",
        ):
            await select_opportunity_plan_v2(
                session,
                project_id=project.id,
                need_id=need.id,
                locale="en",
                cluster_key=str(recommendation["cluster_key"]),
                expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
                idempotency_key="qm02a-second-key",
                selected_by="founder",
                reason="Second key must not duplicate the same selection.",
            )


@pytest.mark.asyncio
async def test_qm02a_reuses_existing_selected_plan_without_duplicate_plan() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project)
        await _budget_search_inputs(session, project, need)
        existing, selection = await _selected_plan(
            session,
            project,
            need,
        )
        plan, recommendation = await _planner(session, project, need)

        assert recommendation["decision"] == "CREATE"
        assert recommendation["selection_readiness"] == "REUSE_EXISTING_PLAN"
        assert recommendation["existing_plan_refs"] == [str(existing.id)]

        before_opportunities = await _count(session, ContentOpportunity)
        before_selections = await _count(session, HumanSelection)
        receipt = await select_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
            cluster_key=str(recommendation["cluster_key"]),
            expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
            idempotency_key="qm02a-reuse-plan",
            selected_by="founder",
            reason="Reuse the already selected plan.",
        )

        assert receipt["resolution"] == "REUSED"
        assert receipt["content_opportunity_id"] == str(existing.id)
        assert receipt["human_selection_id"] == str(selection.id)
        assert await _count(session, ContentOpportunity) == before_opportunities
        assert await _count(session, HumanSelection) == before_selections
        assert await _count(session, OpportunityPlannerHandoff) == 1


@pytest.mark.asyncio
async def test_qm02a_blocks_research_required_and_do_not_write() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        proposed = await _need(
            session,
            project,
            status="PROPOSED",
        )
        await _budget_search_inputs(session, project, proposed)
        plan, recommendation = await _planner(session, project, proposed)
        assert recommendation["selection_readiness"] == "RESEARCH_REQUIRED"

        with pytest.raises(
            OpportunityHandoffError,
            match="opportunity_handoff_research_required",
        ):
            await select_opportunity_plan_v2(
                session,
                project_id=project.id,
                need_id=proposed.id,
                locale="en",
                cluster_key=str(recommendation["cluster_key"]),
                expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
                idempotency_key="qm02a-proposed-block",
                selected_by="founder",
                reason="Must not bypass Need review.",
            )

    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project)
        await _budget_search_inputs(session, project, need)
        await _selected_plan(
            session,
            project,
            need,
            decision="DO_NOT_WRITE",
        )
        plan, recommendation = await _planner(session, project, need)
        assert recommendation["decision"] == "DO_NOT_WRITE"

        with pytest.raises(
            OpportunityHandoffError,
            match="opportunity_handoff_do_not_write_not_selectable",
        ):
            await select_opportunity_plan_v2(
                session,
                project_id=project.id,
                need_id=need.id,
                locale="en",
                cluster_key=str(recommendation["cluster_key"]),
                expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
                idempotency_key="qm02a-do-not-write-block",
                selected_by="founder",
                reason="Must not convert stop advice into production work.",
            )


@pytest.mark.asyncio
async def test_qm02a_link_only_preserves_exact_primary_content_target() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project)
        await _budget_search_inputs(session, project, need)
        item = await _published_primary(session, project, need)
        plan, recommendation = await _planner(session, project, need)

        assert recommendation["decision"] == "LINK_ONLY"
        assert recommendation["existing_content_refs"] == [str(item.id)]

        receipt = await select_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
            cluster_key=str(recommendation["cluster_key"]),
            expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
            idempotency_key="qm02a-link-only",
            selected_by="founder",
            reason="Keep the existing answer and link to it.",
        )
        opportunity = await session.get(
            ContentOpportunity,
            UUID(str(receipt["content_opportunity_id"])),
        )
        assert opportunity is not None
        assert opportunity.decision == "LINK_ONLY"
        assert opportunity.existing_content_refs_json == [str(item.id)]


@pytest.mark.asyncio
async def test_qm02a_handoff_lineage_is_database_immutable() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project)
        await _budget_search_inputs(session, project, need)
        plan, recommendation = await _planner(session, project, need)
        receipt = await select_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
            cluster_key=str(recommendation["cluster_key"]),
            expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
            idempotency_key="qm02a-immutable",
            selected_by="founder",
            reason="Create immutable lineage.",
        )

        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                await session.execute(
                    text(
                        "UPDATE opportunity_planner_handoffs "
                        "SET selection_reason = 'mutated' "
                        "WHERE id = CAST(:id AS uuid)"
                    ),
                    {"id": receipt["handoff_id"]},
                )
                await session.flush()

        stored = await session.get(
            OpportunityPlannerHandoff,
            UUID(str(receipt["handoff_id"])),
        )
        assert stored is not None
        assert stored.selection_reason == "Create immutable lineage."
