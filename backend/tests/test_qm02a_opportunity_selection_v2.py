from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentExperiment,
    ContentItem,
    ContentOpportunity,
    ContentOpportunitySignal,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.research.keyword_plan.opportunity_planner_v2 import (
    build_opportunity_plan_v2,
)
from app.modules.research.keyword_plan.opportunity_selection_v2 import (
    OpportunitySelectionError,
    OpportunitySelectionRequest,
    persist_selected_opportunity,
)
from app.modules.research.keyword_plan.router import select_opportunity_plan_v2


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
        audience_scope="first-time art buyer",
        situation="considering a first painting",
        origin="customer_intelligence",
        status=status,
        alternative_explanations_json=[],
        missing_evidence_json=[],
        version=1,
    )
    session.add(need)
    await session.flush()
    return need


async def _search_signal(
    session: AsyncSession,
    project: Project,
    need: NeedHypothesis,
    *,
    text: str,
) -> Signal:
    signal = Signal(
        project_id=project.id,
        source_kind="SEARCH",
        scope="market_web",
        observed_text=text,
        source_url=f"https://example.com/{uuid4().hex}",
        locale="en",
        context="QM-02A fixture",
        captured_at=datetime.now(UTC),
        fingerprint=uuid4().hex,
        independence_group=uuid4().hex,
        provenance_json={
            "provider": "fixture",
            "method": "people_also_ask",
        },
    )
    session.add(signal)
    await session.flush()
    session.add(
        NeedHypothesisSignal(
            need_hypothesis_id=need.id,
            signal_id=signal.id,
            relation="supports",
        )
    )
    await session.flush()
    return signal


async def _canonical_inputs(
    session: AsyncSession,
    *,
    status: str = "SUPPORTED",
) -> tuple[Project, NeedHypothesis, list[Signal]]:
    project = await _project(session)
    need = await _need(session, project, status=status)
    signals = [
        await _search_signal(
            session,
            project,
            need,
            text="How much should I spend on my first painting?",
        ),
        await _search_signal(
            session,
            project,
            need,
            text="What budget should I set for a painting?",
        ),
    ]
    return project, need, signals


def _one_recommendation(plan: dict[str, object]) -> dict[str, object]:
    rows = plan["recommendations"]
    assert isinstance(rows, list)
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, dict)
    return row


def _request(
    *,
    project: Project,
    need: NeedHypothesis,
    plan: dict[str, object],
    promise: str = "Give a practical budget path without pretending price proves quality.",
) -> OpportunitySelectionRequest:
    recommendation = _one_recommendation(plan)
    return OpportunitySelectionRequest(
        project_slug=project.slug,
        need_id=need.id,
        locale="en",
        cluster_key=str(recommendation["cluster_key"]),
        expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
        selected_by="founder",
        selection_reason="Founder selected this exact planning recommendation.",
        promise=promise,
        coverage_requirements=[
            "Explain how to set a first-art budget without treating price as proof of quality.",
            "Separate artwork price from framing, shipping and other ownership costs.",
        ],
    )


async def _existing_primary_item(
    session: AsyncSession,
    *,
    project: Project,
    need: NeedHypothesis,
) -> ContentItem:
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader=need.audience_scope,
        situation=need.situation,
        need=need.statement,
        question="What budget should I set for a painting?",
        intent="evaluate",
        promise="Existing draft budget guidance.",
        coverage_requirements_json=[],
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Existing fixture.",
        next_discovery_step="None",
        decision="CREATE",
        priority="NEXT",
        reasons_json=["fixture"],
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="read",
        content_hypothesis="Budget guidance helps the buyer decide.",
        originality_statement="Fixture.",
        reader_before="uncertain",
        reader_after="better informed",
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
        status="draft",
        canonical_key=f"journal:qm02a-existing-{uuid4().hex}:en",
    )
    session.add(item)
    await session.flush()
    return item


@pytest.mark.asyncio
async def test_selection_persists_existing_need_opportunity_and_one_human_selection() -> None:
    async with isolated_session() as session:
        project, need, signals = await _canonical_inputs(session)
        plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        recommendation = _one_recommendation(plan)
        assert recommendation["decision"] == "CREATE"
        assert recommendation["selection_readiness"] == "READY_FOR_HUMAN_SELECTION"
        request = _request(project=project, need=need, plan=plan)

        before = (
            await session.scalar(select(func.count()).select_from(NeedHypothesis)),
            await session.scalar(select(func.count()).select_from(ContentOpportunity)),
            await session.scalar(select(func.count()).select_from(HumanSelection)),
            await session.scalar(select(func.count()).select_from(ContentExperiment)),
            await session.scalar(select(func.count()).select_from(ContentCase)),
        )

        result = await persist_selected_opportunity(
            session,
            project_id=project.id,
            request=request,
        )

        opportunity = await session.get(
            ContentOpportunity,
            result.content_opportunity_id,
        )
        selection = await session.get(
            HumanSelection,
            result.human_selection_id,
        )
        assert opportunity is not None
        assert selection is not None
        assert result.replayed is False
        assert opportunity.need_hypothesis_id == need.id
        assert opportunity.reader == need.audience_scope
        assert opportunity.situation == need.situation
        assert opportunity.need == need.statement
        assert opportunity.promise == request.promise
        assert opportunity.coverage_requirements_json == request.coverage_requirements
        assert opportunity.motgu_material_refs_json == []
        assert opportunity.suggested_content_type == "journal"
        assert opportunity.suggested_role == "cluster"
        assert opportunity.decision == "CREATE"
        assert opportunity.selected_by == "founder"
        assert selection.content_opportunity_id == opportunity.id
        assert selection.selected_by == "founder"
        assert any(
            reason == f"planner_snapshot:{plan['snapshot_hash']}"
            for reason in opportunity.reasons_json
        )

        linked = set(
            (
                await session.scalars(
                    select(ContentOpportunitySignal.signal_id).where(
                        ContentOpportunitySignal.content_opportunity_id
                        == opportunity.id
                    )
                )
            ).all()
        )
        assert linked == {signal.id for signal in signals}

        after = (
            await session.scalar(select(func.count()).select_from(NeedHypothesis)),
            await session.scalar(select(func.count()).select_from(ContentOpportunity)),
            await session.scalar(select(func.count()).select_from(HumanSelection)),
            await session.scalar(select(func.count()).select_from(ContentExperiment)),
            await session.scalar(select(func.count()).select_from(ContentCase)),
        )
        assert after[0] == before[0]
        assert after[1] == before[1] + 1
        assert after[2] == before[2] + 1
        assert after[3] == before[3]
        assert after[4] == before[4]


@pytest.mark.asyncio
async def test_exact_replay_is_idempotent_after_new_plan_changes_coverage() -> None:
    async with isolated_session() as session:
        project, need, _ = await _canonical_inputs(session)
        plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        request = _request(project=project, need=need, plan=plan)
        first = await persist_selected_opportunity(
            session,
            project_id=project.id,
            request=request,
        )

        changed_plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        assert changed_plan["snapshot_hash"] != plan["snapshot_hash"]

        replay = await persist_selected_opportunity(
            session,
            project_id=project.id,
            request=request,
        )

        assert replay.replayed is True
        assert replay.content_opportunity_id == first.content_opportunity_id
        assert replay.human_selection_id == first.human_selection_id
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ContentOpportunity)
                .where(ContentOpportunity.project_id == project.id)
            )
        ) == 1
        assert (
            await session.scalar(
                select(func.count())
                .select_from(HumanSelection)
                .where(
                    HumanSelection.content_opportunity_id
                    == first.content_opportunity_id
                )
            )
        ) == 1


@pytest.mark.asyncio
async def test_exact_replay_survives_later_need_state_change() -> None:
    async with isolated_session() as session:
        project, need, _ = await _canonical_inputs(session)
        plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        request = _request(project=project, need=need, plan=plan)
        first = await persist_selected_opportunity(
            session,
            project_id=project.id,
            request=request,
        )

        need.status = "REJECTED"
        need.statement = "Later reviewed state changed this Need."
        need.version += 1
        await session.flush()

        replay = await persist_selected_opportunity(
            session,
            project_id=project.id,
            request=request,
        )

        assert replay.replayed is True
        assert replay.content_opportunity_id == first.content_opportunity_id
        assert replay.human_selection_id == first.human_selection_id


@pytest.mark.asyncio
async def test_conflicting_replay_fails_closed() -> None:
    async with isolated_session() as session:
        project, need, _ = await _canonical_inputs(session)
        plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        request = _request(project=project, need=need, plan=plan)
        await persist_selected_opportunity(
            session,
            project_id=project.id,
            request=request,
        )
        conflict = _request(
            project=project,
            need=need,
            plan=plan,
            promise="A different promise must not overwrite the selected brief.",
        )

        with pytest.raises(
            OpportunitySelectionError,
            match="opportunity_selection_replay_conflict",
        ):
            await persist_selected_opportunity(
                session,
                project_id=project.id,
                request=conflict,
            )


@pytest.mark.asyncio
async def test_stale_unseen_planner_snapshot_is_rejected_before_persistence() -> None:
    async with isolated_session() as session:
        project, need, _ = await _canonical_inputs(session)
        plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        request = _request(project=project, need=need, plan=plan)
        request.expected_planner_snapshot_hash = "f" * 64

        with pytest.raises(
            OpportunitySelectionError,
            match="opportunity_selection_stale_planner_snapshot",
        ):
            await persist_selected_opportunity(
                session,
                project_id=project.id,
                request=request,
            )

        assert (
            await session.scalar(
                select(func.count())
                .select_from(ContentOpportunity)
                .where(ContentOpportunity.project_id == project.id)
            )
        ) == 0


@pytest.mark.asyncio
async def test_non_ready_recommendation_cannot_create_durable_plan() -> None:
    async with isolated_session() as session:
        project, need, _ = await _canonical_inputs(
            session,
            status="PROPOSED",
        )
        plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        recommendation = _one_recommendation(plan)
        assert recommendation["selection_readiness"] == "RESEARCH_REQUIRED"
        request = _request(project=project, need=need, plan=plan)

        with pytest.raises(
            OpportunitySelectionError,
            match="opportunity_selection_not_ready",
        ):
            await persist_selected_opportunity(
                session,
                project_id=project.id,
                request=request,
            )


@pytest.mark.asyncio
async def test_update_selection_preserves_exact_primary_content_target() -> None:
    async with isolated_session() as session:
        project, need, _ = await _canonical_inputs(session)
        item = await _existing_primary_item(
            session,
            project=project,
            need=need,
        )
        plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        recommendation = _one_recommendation(plan)
        assert recommendation["decision"] == "UPDATE"
        assert recommendation["existing_content_refs"] == [str(item.id)]
        assert recommendation["selection_readiness"] == "READY_FOR_HUMAN_SELECTION"

        result = await persist_selected_opportunity(
            session,
            project_id=project.id,
            request=_request(project=project, need=need, plan=plan),
        )
        opportunity = await session.get(
            ContentOpportunity,
            result.content_opportunity_id,
        )
        assert opportunity is not None
        assert opportunity.decision == "UPDATE"
        assert opportunity.existing_content_refs_json == [str(item.id)]


@pytest.mark.asyncio
async def test_existing_selected_plan_blocks_duplicate_selection_from_new_snapshot() -> None:
    async with isolated_session() as session:
        project, need, _ = await _canonical_inputs(session)
        first_plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        await persist_selected_opportunity(
            session,
            project_id=project.id,
            request=_request(
                project=project,
                need=need,
                plan=first_plan,
            ),
        )

        next_plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        recommendation = _one_recommendation(next_plan)
        assert recommendation["selection_readiness"] == "REUSE_EXISTING_PLAN"

        with pytest.raises(
            OpportunitySelectionError,
            match="opportunity_selection_not_ready",
        ):
            await persist_selected_opportunity(
                session,
                project_id=project.id,
                request=_request(
                    project=project,
                    need=need,
                    plan=next_plan,
                ),
            )

        assert (
            await session.scalar(
                select(func.count())
                .select_from(ContentOpportunity)
                .where(ContentOpportunity.project_id == project.id)
            )
        ) == 1


@pytest.mark.asyncio
async def test_selection_route_uses_exact_current_planner_and_returns_receipt() -> None:
    async with isolated_session() as session:
        project, need, _ = await _canonical_inputs(session)
        plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        request = _request(project=project, need=need, plan=plan)

        result = await select_opportunity_plan_v2(
            request=request,
            session=session,
        )

        assert result.schema_version == 1
        assert result.planner_snapshot_hash == plan["snapshot_hash"]
        assert result.cluster_key == request.cluster_key
        assert result.decision == "CREATE"
        assert result.replayed is False
