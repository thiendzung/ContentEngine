from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    Project,
    SettingsSnapshot,
)
from app.modules.harness.models import ContentRun
from app.modules.research.keyword_plan.production_admission import (
    ProductionAdmissionError,
    build_production_admission,
)
from app.modules.research.keyword_plan.production_decision_router import (
    build_production_decision_route,
)
from app.modules.research.keyword_plan.router import get_production_admission


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
        slug=f"qm02c-{uuid4().hex[:8]}",
        name="QM-02C",
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
        question=f"Existing question {suffix}",
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
        locale="en",
        content_role="cluster",
        primary_question=f"Existing question {suffix}",
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
        canonical_key=f"journal:qm02c-{suffix}-{uuid4().hex}:en",
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
        coverage_requirements_json=[],
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[str(value) for value in target_ids],
        what_is_actually_new="Not established yet.",
        next_discovery_step="Prepare production.",
        decision=decision,
        priority="NEXT" if decision != "DO_NOT_WRITE" else "NO",
        reasons_json=["qm02c_fixture"],
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


async def _route_hash(
    session: AsyncSession,
    *,
    project: Project,
    opportunity: ContentOpportunity,
) -> str:
    route = await build_production_decision_route(
        session,
        project_id=project.id,
        opportunity_id=opportunity.id,
    )
    return route.snapshot_hash


async def _run(
    session: AsyncSession,
    *,
    project: Project,
    item: ContentItem,
    status: str,
) -> ContentRun:
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={},
        source_version_refs_json=[],
        content_hash="a" * 64,
    )
    session.add(snapshot)
    await session.flush()
    run = ContentRun(
        project_id=project.id,
        content_case_id=item.content_case_id,
        locale_variant_id=item.locale_variant_id,
        content_item_id=item.id,
        run_mode="update",
        status=status,
        current_step=None,
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
        completed_at=None,
        failure_code=None,
        failure_message=None,
    )
    session.add(run)
    await session.flush()
    return run


@pytest.mark.asyncio
async def test_create_route_is_admitted_and_deterministic() -> None:
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
        route_hash = await _route_hash(
            session,
            project=project,
            opportunity=opportunity,
        )

        first = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
        )
        replay = await get_production_admission(
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
            project_slug=project.slug,
            session=session,
        )

        assert first.status == "ADMITTED"
        assert first.route == "CREATE_NEW_CONTENT"
        assert first.snapshot_hash == replay.snapshot_hash
        assert first == replay


@pytest.mark.asyncio
async def test_stale_expected_route_hash_fails_closed() -> None:
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

        result = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash="0" * 64,
        )

        assert result.status == "BLOCKED_ROUTE_STALE"
        assert result.current_route_snapshot_hash is not None


@pytest.mark.asyncio
async def test_selection_drift_fails_closed() -> None:
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
        route_hash = await _route_hash(
            session,
            project=project,
            opportunity=opportunity,
        )
        await session.delete(selection)
        await session.flush()

        result = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
        )

        assert result.status == "BLOCKED_SELECTION_STALE"


@pytest.mark.asyncio
async def test_opportunity_drift_fails_closed() -> None:
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
        route_hash = await _route_hash(
            session,
            project=project,
            opportunity=opportunity,
        )
        opportunity.suggested_content_type = "artwork"
        await session.flush()

        result = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
        )

        assert result.status == "BLOCKED_OPPORTUNITY_STALE"


@pytest.mark.asyncio
async def test_target_drift_fails_closed() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        target = await _target_item(
            session,
            project=project,
            need=need,
            suffix="stale-target",
        )
        opportunity, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="UPDATE",
            target_ids=[target.id],
        )
        route_hash = await _route_hash(
            session,
            project=project,
            opportunity=opportunity,
        )
        await session.delete(target)
        await session.flush()

        result = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
        )

        assert result.status == "BLOCKED_TARGET_STALE"


@pytest.mark.asyncio
async def test_create_blocks_after_materialization() -> None:
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
        route_hash = await _route_hash(
            session,
            project=project,
            opportunity=opportunity,
        )
        session.add(
            ContentCase(
                project_id=project.id,
                content_type="journal",
                need_hypothesis_id=need.id,
                content_opportunity_id=opportunity.id,
                desired_action="Create the selected Journal.",
                content_hypothesis="Selected content helps the reader.",
                originality_statement="Pending downstream originality.",
                reader_before="uncertain",
                reader_after="informed",
            )
        )
        await session.flush()

        result = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
        )

        assert result.status == "BLOCKED_ALREADY_MATERIALIZED"


@pytest.mark.asyncio
async def test_update_without_active_run_is_admitted() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        target = await _target_item(
            session,
            project=project,
            need=need,
            suffix="update-ready",
        )
        opportunity, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="UPDATE",
            target_ids=[target.id],
        )
        route_hash = await _route_hash(
            session,
            project=project,
            opportunity=opportunity,
        )

        result = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
        )

        assert result.status == "ADMITTED"
        assert result.route == "REVISE_EXISTING_CONTENT"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "run_status",
    ["pending", "running", "waiting_approval", "failed"],
)
async def test_update_blocks_on_unresolved_target_run(
    run_status: str,
) -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        target = await _target_item(
            session,
            project=project,
            need=need,
            suffix=f"update-busy-{run_status}",
        )
        opportunity, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="UPDATE",
            target_ids=[target.id],
        )
        route_hash = await _route_hash(
            session,
            project=project,
            opportunity=opportunity,
        )
        await _run(
            session,
            project=project,
            item=target,
            status=run_status,
        )

        result = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
        )

        assert result.status == "BLOCKED_PRODUCTION_CONFLICT"
        assert result.reason_codes == [
            "production_admission_target_has_unresolved_run"
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision", "target_count", "expected_status"),
    [
        ("LINK_ONLY", 1, "NO_PRODUCTION"),
        ("DO_NOT_WRITE", 0, "NO_PRODUCTION"),
        ("MERGE", 2, "RECONCILIATION_REQUIRED"),
    ],
)
async def test_non_create_dispositions_do_not_enter_normal_production(
    decision: str,
    target_count: int,
    expected_status: str,
) -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        targets = [
            await _target_item(
                session,
                project=project,
                need=need,
                suffix=f"{decision.lower()}-{index}",
            )
            for index in range(target_count)
        ]
        opportunity, _ = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision=decision,
            target_ids=[row.id for row in targets],
        )
        route_hash = await _route_hash(
            session,
            project=project,
            opportunity=opportunity,
        )

        result = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
        )

        assert result.status == expected_status


@pytest.mark.asyncio
async def test_admission_is_read_only() -> None:
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
        route_hash = await _route_hash(
            session,
            project=project,
            opportunity=opportunity,
        )
        before = (
            await session.scalar(select(func.count()).select_from(ContentCase)),
            await session.scalar(select(func.count()).select_from(ContentItem)),
            await session.scalar(select(func.count()).select_from(ContentRun)),
        )

        await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
        )

        after = (
            await session.scalar(select(func.count()).select_from(ContentCase)),
            await session.scalar(select(func.count()).select_from(ContentItem)),
            await session.scalar(select(func.count()).select_from(ContentRun)),
        )
        assert after == before


@pytest.mark.asyncio
async def test_invalid_expected_hash_is_rejected() -> None:
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

        with pytest.raises(
            ProductionAdmissionError,
            match="production_admission_route_hash_invalid",
        ):
            await build_production_admission(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash="not-a-hash",
            )
