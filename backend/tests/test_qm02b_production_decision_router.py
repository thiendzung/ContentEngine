from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.journal.operator_control import (
    OperatorControlError,
    create_or_reuse_journal_case,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    Project,
)
from app.modules.research.keyword_plan.production_decision_router import (
    ProductionDecisionRouterError,
    build_production_decision_route,
)
from app.modules.research.keyword_plan.router import (
    get_production_decision_route,
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
        slug=f"qm02b-{uuid4().hex[:8]}",
        name="QM-02B",
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


async def _need(
    session: AsyncSession,
    *,
    project_id: UUID,
    statement: str = "Buyer needs budget clarity.",
) -> NeedHypothesis:
    need = NeedHypothesis(
        project_id=project_id,
        type="question",
        statement=statement,
        audience_scope="first-time art buyer",
        situation="considering a painting",
        origin="customer_intelligence",
        status="SUPPORTED",
        alternative_explanations_json=[],
        missing_evidence_json=[],
        version=1,
    )
    session.add(need)
    await session.flush()
    return need


async def _source_opportunity(
    session: AsyncSession,
    *,
    project: Project,
    need: NeedHypothesis,
    suffix: str,
) -> ContentOpportunity:
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader=need.audience_scope,
        situation=need.situation,
        need=need.statement,
        question=f"Existing content question {suffix}",
        intent="evaluate",
        promise="Existing fixture promise.",
        coverage_requirements_json=[],
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Existing fixture.",
        next_discovery_step="None.",
        decision="CREATE",
        priority="NEXT",
        reasons_json=["fixture"],
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
    )
    session.add(opportunity)
    await session.flush()
    return opportunity


async def _target_item(
    session: AsyncSession,
    *,
    project: Project,
    need: NeedHypothesis,
    locale: str = "en",
    suffix: str,
) -> ContentItem:
    source = await _source_opportunity(
        session,
        project=project,
        need=need,
        suffix=suffix,
    )
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=source.id,
        desired_action="Read existing content.",
        content_hypothesis="Existing content helps answer the Need.",
        originality_statement="Fixture.",
        reader_before="uncertain",
        reader_after="informed",
    )
    session.add(content_case)
    await session.flush()
    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale=locale,
        content_role="cluster",
        primary_question=f"Existing content question {suffix}",
        primary_intent="evaluate",
        secondary_intent=None,
        primary_query=None,
        keyword_notes_json=[],
        emotion_arc_json=[],
        must_include_json=[],
        must_not_claim_json=[],
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
        canonical_key=f"journal:qm02b-{suffix}-{uuid4().hex}:en",
    )
    session.add(item)
    await session.flush()
    return item


async def _selected_opportunity(
    session: AsyncSession,
    *,
    project: Project,
    need: NeedHypothesis,
    decision: str,
    target_ids: list[UUID],
) -> tuple[ContentOpportunity, HumanSelection]:
    selected_at = datetime.now(UTC)
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader=need.audience_scope,
        situation=need.situation,
        need=need.statement,
        question="How much should I spend on a painting?",
        intent="evaluate",
        promise="Give a practical budget decision path.",
        coverage_requirements_json=[
            "Explain a practical first-art budget.",
        ],
        motgu_material_refs_json=[],
        material_gaps_json=["Originality still requires approved material."],
        existing_content_refs_json=[str(value) for value in target_ids],
        what_is_actually_new="Not established yet.",
        next_discovery_step="Prepare evidence and originality.",
        decision=decision,
        priority="NEXT" if decision != "DO_NOT_WRITE" else "NO",
        reasons_json=["qm02b_fixture"],
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
        selected_by="founder",
        selected_at=selected_at,
        selection_reason="Founder selected this exact opportunity.",
    )
    session.add(opportunity)
    await session.flush()
    selection = HumanSelection(
        content_opportunity_id=opportunity.id,
        selected_by="founder",
        reason=opportunity.selection_reason,
        selected_at=selected_at,
    )
    session.add(selection)
    await session.flush()
    return opportunity, selection


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision", "target_count", "route", "admission", "reconcile", "forbidden"),
    [
        ("CREATE", 0, "CREATE_NEW_CONTENT", True, False, False),
        ("UPDATE", 1, "REVISE_EXISTING_CONTENT", True, False, False),
        ("REFRESH", 1, "REFRESH_EXISTING_CONTENT", True, False, False),
        ("MERGE", 2, "RECONCILE_CONTENT", False, True, False),
        ("LINK_ONLY", 1, "NO_PRODUCTION", False, False, True),
        ("DO_NOT_WRITE", 0, "STOP", False, False, True),
    ],
)
async def test_all_decisions_map_to_exact_production_route(
    decision: str,
    target_count: int,
    route: str,
    admission: bool,
    reconcile: bool,
    forbidden: bool,
) -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        targets = [
            await _target_item(
                session,
                project=project,
                need=need,
                suffix=str(index),
            )
            for index in range(target_count)
        ]
        opportunity, selection = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision=decision,
            target_ids=[row.id for row in targets],
        )

        result = await build_production_decision_route(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
        )

        assert result.route == route
        assert result.human_selection_id == selection.id
        assert result.target_content_item_ids == sorted(
            [row.id for row in targets],
            key=str,
        )
        assert result.admission_candidate is admission
        assert result.reconciliation_required is reconcile
        assert result.production_forbidden is forbidden
        assert len(result.snapshot_hash) == 64


@pytest.mark.asyncio
async def test_route_is_deterministic_and_get_endpoint_is_read_only() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        before = (
            await session.scalar(select(func.count()).select_from(ContentOpportunity)),
            await session.scalar(select(func.count()).select_from(HumanSelection)),
            await session.scalar(select(func.count()).select_from(ContentCase)),
            await session.scalar(select(func.count()).select_from(ContentItem)),
        )

        first = await get_production_decision_route(
            opportunity_id=opportunity.id,
            project_slug=project.slug,
            session=session,
        )
        replay = await build_production_decision_route(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
        )

        assert first == replay
        assert first.snapshot_hash == replay.snapshot_hash
        after = (
            await session.scalar(select(func.count()).select_from(ContentOpportunity)),
            await session.scalar(select(func.count()).select_from(HumanSelection)),
            await session.scalar(select(func.count()).select_from(ContentCase)),
            await session.scalar(select(func.count()).select_from(ContentItem)),
        )
        assert after == before


@pytest.mark.asyncio
async def test_route_requires_exactly_one_matching_human_selection() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity, selection = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        await session.delete(selection)
        await session.flush()

        with pytest.raises(
            ProductionDecisionRouterError,
            match="production_route_selection_count_invalid",
        ):
            await build_production_decision_route(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
            )

        session.add(
            HumanSelection(
                content_opportunity_id=opportunity.id,
                selected_by="founder",
                reason=opportunity.selection_reason,
                selected_at=opportunity.selected_at,
            )
        )
        session.add(
            HumanSelection(
                content_opportunity_id=opportunity.id,
                selected_by="founder",
                reason=opportunity.selection_reason,
                selected_at=opportunity.selected_at,
            )
        )
        await session.flush()

        with pytest.raises(
            ProductionDecisionRouterError,
            match="production_route_selection_count_invalid",
        ):
            await build_production_decision_route(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
            )


@pytest.mark.asyncio
async def test_route_rejects_selection_convenience_field_mismatch() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        opportunity.selection_reason = "Different convenience-field reason."
        await session.flush()

        with pytest.raises(
            ProductionDecisionRouterError,
            match="production_route_selection_mismatch",
        ):
            await build_production_decision_route(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
            )


@pytest.mark.asyncio
async def test_route_rejects_invalid_decision_target_cardinality() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        target = await _target_item(
            session,
            project=project,
            need=need,
            suffix="one",
        )
        create, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[target.id],
        )
        merge, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="MERGE",
            target_ids=[target.id],
        )

        with pytest.raises(
            ProductionDecisionRouterError,
            match="production_route_create_target_conflict",
        ):
            await build_production_decision_route(
                session,
                project_id=project.id,
                opportunity_id=create.id,
            )
        with pytest.raises(
            ProductionDecisionRouterError,
            match="production_route_merge_target_count_invalid",
        ):
            await build_production_decision_route(
                session,
                project_id=project.id,
                opportunity_id=merge.id,
            )


@pytest.mark.asyncio
async def test_route_rejects_duplicate_target_refs() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        target = await _target_item(
            session,
            project=project,
            need=need,
            suffix="duplicate",
        )
        opportunity, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="LINK_ONLY",
            target_ids=[target.id, target.id],
        )

        with pytest.raises(
            ProductionDecisionRouterError,
            match="production_route_target_refs_duplicate",
        ):
            await build_production_decision_route(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
            )


@pytest.mark.asyncio
async def test_route_rejects_target_from_different_primary_need() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        foreign_need = await _need(
            session,
            project_id=project.id,
            statement="Different customer Need.",
        )
        target = await _target_item(
            session,
            project=project,
            need=foreign_need,
            suffix="foreign-need",
        )
        opportunity, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="UPDATE",
            target_ids=[target.id],
        )

        with pytest.raises(
            ProductionDecisionRouterError,
            match="production_route_target_not_primary_need",
        ):
            await build_production_decision_route(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
            )


@pytest.mark.asyncio
async def test_route_rejects_target_from_different_locale() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        target = await _target_item(
            session,
            project=project,
            need=need,
            locale="vi",
            suffix="vi",
        )
        opportunity, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="REFRESH",
            target_ids=[target.id],
        )

        with pytest.raises(
            ProductionDecisionRouterError,
            match="production_route_target_locale_mismatch",
        ):
            await build_production_decision_route(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
            )


@pytest.mark.asyncio
async def test_existing_operator_create_guard_still_rejects_update_route() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        target = await _target_item(
            session,
            project=project,
            need=need,
            suffix="operator-guard",
        )
        opportunity, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="UPDATE",
            target_ids=[target.id],
        )

        route = await build_production_decision_route(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
        )
        assert route.route == "REVISE_EXISTING_CONTENT"

        with pytest.raises(
            OperatorControlError,
            match="operator_create_requires_create_opportunity",
        ):
            await create_or_reuse_journal_case(
                session,
                content_opportunity_id=opportunity.id,
                expected_opportunity_version=opportunity.version,
            )


@pytest.mark.asyncio
async def test_route_rejects_non_journal_selected_opportunity() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        opportunity.suggested_content_type = "artwork"
        await session.flush()

        with pytest.raises(
            ProductionDecisionRouterError,
            match="production_route_content_type_unsupported",
        ):
            await build_production_decision_route(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
            )
