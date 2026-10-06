from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.models import (
    ContentCase,
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
from app.modules.content_engine.persistence import create_next_content_version
from app.modules.harness.models import ContentRun, Job, StepRun
from app.modules.research.keyword_plan.content_architecture import (
    build_content_architecture,
)
from app.modules.research.keyword_plan.opportunity_selection_v2 import (
    OpportunitySelectionRequest,
    persist_selected_opportunity,
)
from app.modules.research.keyword_plan.production_admission import (
    build_production_admission,
)
from app.modules.research.keyword_plan.production_decision_router import (
    build_production_decision_route,
)
from app.modules.research.keyword_plan.revision_handoff import (
    RevisionProductionHandoffError,
    materialize_revision_handoff,
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
    row = Project(
        slug=f"qm02d2-{uuid4().hex[:8]}",
        name="QM-02D2",
        default_locale="en",
    )
    session.add(row)
    await session.flush()
    return row


async def _need(
    session: AsyncSession,
    *,
    project_id: UUID,
    status: str = "PROPOSED",
) -> NeedHypothesis:
    row = NeedHypothesis(
        project_id=project_id,
        type="question",
        statement="Choose an original artwork with budget confidence.",
        audience_scope="first-time art buyer",
        situation="considering a first original painting",
        origin="customer_intelligence",
        status=status,
        alternative_explanations_json=[],
        missing_evidence_json=["First-party evidence is still limited."],
        version=1,
    )
    session.add(row)
    await session.flush()
    return row


async def _search_signal(
    session: AsyncSession,
    *,
    project: Project,
    need: NeedHypothesis,
    text: str,
) -> Signal:
    row = Signal(
        project_id=project.id,
        source_kind="SEARCH",
        scope="market_web",
        observed_text=text,
        source_url=f"https://example.com/{uuid4().hex}",
        locale="en",
        context="QM-02D2 fixture",
        captured_at=datetime.now(UTC),
        fingerprint=uuid4().hex,
        independence_group=uuid4().hex,
        provenance_json={
            "provider": "fixture",
            "method": "people_also_ask",
            "question_eligible": True,
        },
    )
    session.add(row)
    await session.flush()
    session.add(
        NeedHypothesisSignal(
            need_hypothesis_id=need.id,
            signal_id=row.id,
            relation="supports",
        )
    )
    await session.flush()
    return row


async def _target_item(
    session: AsyncSession,
    *,
    project: Project,
    need: NeedHypothesis,
    refresh: bool,
) -> ContentItem:
    source = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader=need.audience_scope,
        situation=need.situation,
        need=need.statement,
        question="How much should I spend on my first painting?",
        intent="evaluate",
        promise="Existing budget guidance.",
        coverage_requirements_json=[],
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Existing canonical content.",
        next_discovery_step="None.",
        decision="CREATE",
        priority="NEXT",
        reasons_json=["fixture"],
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
    )
    session.add(source)
    await session.flush()

    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=source.id,
        desired_action="Keep first-art budget guidance useful.",
        content_hypothesis="Budget guidance helps the buyer decide.",
        originality_statement="Fixture.",
        reader_before="uncertain about budget",
        reader_after="has a practical budget range",
        status="draft",
    )
    session.add(content_case)
    await session.flush()

    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="cluster",
        primary_question=source.question,
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
        status="published" if refresh else "draft",
        canonical_key=f"journal:qm02d2-{uuid4().hex}:en",
    )
    session.add(item)
    await session.flush()

    await create_next_content_version(
        session,
        content_item_id=item.id,
        change_reason="Initial canonical answer.",
        content_json={"body": "Existing budget answer."},
        status="published" if refresh else "draft",
    )
    if refresh:
        await create_next_content_version(
            session,
            content_item_id=item.id,
            change_reason="Unpublished newer revision.",
            content_json={"body": "Newer draft budget answer."},
            status="draft",
        )
    return item


async def _selected_revision_opportunity(
    session: AsyncSession,
    *,
    project: Project,
    need: NeedHypothesis,
    decision: str,
) -> tuple[ContentOpportunity, ContentItem, dict[str, object]]:
    await _search_signal(
        session,
        project=project,
        need=need,
        text="How much should I spend on my first painting?",
    )
    await _search_signal(
        session,
        project=project,
        need=need,
        text="What budget should I set for my first painting?",
    )
    target = await _target_item(
        session,
        project=project,
        need=need,
        refresh=decision == "REFRESH",
    )
    architecture = await build_content_architecture(
        session,
        project_id=project.id,
        need_id=need.id,
        locale="en",
    )
    candidates = architecture["candidates"]
    assert isinstance(candidates, list)
    matches = [
        row
        for row in candidates
        if isinstance(row, dict)
        and row.get("role") == "cluster"
        and row.get("decision") == decision
    ]
    assert len(matches) == 1
    candidate = matches[0]
    assert candidate["selection_readiness"] == "READY_FOR_HUMAN_SELECTION"
    assert candidate["existing_content_refs"] == [str(target.id)]

    selected = await persist_selected_opportunity(
        session,
        project_id=project.id,
        request=OpportunitySelectionRequest(
            project_slug=project.slug,
            need_id=need.id,
            locale="en",
            architecture_candidate_key=str(candidate["candidate_key"]),
            expected_architecture_snapshot_hash=str(
                architecture["snapshot_hash"]
            ),
            expected_planner_snapshot_hash=str(
                architecture["planner_snapshot_hash"]
            ),
            selected_by="founder",
            selection_reason=(
                f"Founder selected the exact {decision} candidate."
            ),
            promise="Keep the existing canonical answer useful and current.",
            coverage_requirements=[
                "Preserve the canonical target identity.",
                "Address the exact current question gap.",
            ],
        ),
    )
    opportunity = await session.get(
        ContentOpportunity,
        selected.content_opportunity_id,
    )
    assert opportunity is not None
    return opportunity, target, architecture


async def _route_and_admission(
    session: AsyncSession,
    *,
    project: Project,
    opportunity: ContentOpportunity,
):
    route = await build_production_decision_route(
        session,
        project_id=project.id,
        opportunity_id=opportunity.id,
    )
    admission = await build_production_admission(
        session,
        project_id=project.id,
        opportunity_id=opportunity.id,
        expected_route_snapshot_hash=route.snapshot_hash,
    )
    assert admission.status == "ADMITTED"
    return route, admission


async def _counts(session: AsyncSession) -> dict[str, int]:
    models = {
        "opportunity": ContentOpportunity,
        "opportunity_signal": ContentOpportunitySignal,
        "selection": HumanSelection,
        "case": ContentCase,
        "variant": LocaleVariant,
        "item": ContentItem,
        "version": ContentVersion,
        "run": ContentRun,
        "step": StepRun,
        "job": Job,
        "command": OperatorCommand,
    }
    result: dict[str, int] = {}
    for key, model in models.items():
        value = await session.scalar(
            select(func.count()).select_from(model)
        )
        result[key] = int(value or 0)
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision", "expected_route"),
    [
        ("UPDATE", "REVISE_EXISTING_CONTENT"),
        ("REFRESH", "REFRESH_EXISTING_CONTENT"),
    ],
)
async def test_revision_handoff_materializes_only_revision_scope_and_receipt(
    decision: str,
    expected_route: str,
) -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity, target, _ = await _selected_revision_opportunity(
            session,
            project=project,
            need=need,
            decision=decision,
        )
        route, admission = await _route_and_admission(
            session,
            project=project,
            opportunity=opportunity,
        )
        assert route.route == expected_route
        assert len(route.target_snapshots) == 1
        target_snapshot = route.target_snapshots[0]
        assert target_snapshot.content_item_id == target.id
        assert target_snapshot.current_content_version_id is not None

        before = await _counts(session)
        result = await materialize_revision_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route.snapshot_hash,
            expected_admission_snapshot_hash=admission.snapshot_hash,
            idempotency_key=f"qm02d2:{decision}:{uuid4()}",
        )
        after = await _counts(session)

        assert result.replayed is False
        assert result.decision == decision
        assert result.target_content_item_id == target.id
        assert (
            result.target_content_version_id
            == target_snapshot.current_content_version_id
        )
        assert result.state.status == "NOT_READY"
        assert result.state.blocker_code == "operator_pipeline_start_not_wired"

        revision_case = await session.get(
            ContentCase,
            result.revision_content_case_id,
        )
        source_variant = await session.get(
            LocaleVariant,
            result.source_locale_variant_id,
        )
        receipt = await session.get(OperatorCommand, result.command_id)
        assert revision_case is not None
        assert revision_case.content_opportunity_id == opportunity.id
        assert source_variant is not None
        assert source_variant.content_case_id == revision_case.id
        assert receipt is not None
        assert receipt.content_case_id == revision_case.id
        assert receipt.result_ref_id == result.target_content_version_id
        assert receipt.run_id is None
        assert receipt.step_run_id is None
        assert receipt.job_id is None
        assert receipt.resolved_action_key == (
            "materialize_question_map_update"
            if decision == "UPDATE"
            else "materialize_question_map_refresh"
        )

        assert after["case"] == before["case"] + 1
        assert after["variant"] == before["variant"] + 1
        assert after["command"] == before["command"] + 1
        for key in (
            "opportunity",
            "opportunity_signal",
            "selection",
            "item",
            "version",
            "run",
            "step",
            "job",
        ):
            assert after[key] == before[key]


@pytest.mark.asyncio
async def test_revision_handoff_exact_replay_returns_same_receipt() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity, _, _ = await _selected_revision_opportunity(
            session,
            project=project,
            need=need,
            decision="UPDATE",
        )
        route, admission = await _route_and_admission(
            session,
            project=project,
            opportunity=opportunity,
        )
        key = f"qm02d2:update:{uuid4()}"
        first = await materialize_revision_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route.snapshot_hash,
            expected_admission_snapshot_hash=admission.snapshot_hash,
            idempotency_key=key,
        )
        before_replay = await _counts(session)

        replay = await materialize_revision_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route.snapshot_hash,
            expected_admission_snapshot_hash=admission.snapshot_hash,
            idempotency_key=key,
        )

        assert replay.replayed is True
        assert replay.command_id == first.command_id
        assert replay.revision_content_case_id == first.revision_content_case_id
        assert replay.source_locale_variant_id == first.source_locale_variant_id
        assert replay.target_content_item_id == first.target_content_item_id
        assert replay.target_content_version_id == first.target_content_version_id
        assert await _counts(session) == before_replay


@pytest.mark.asyncio
async def test_distinct_key_cannot_duplicate_revision_materialization() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity, _, _ = await _selected_revision_opportunity(
            session,
            project=project,
            need=need,
            decision="UPDATE",
        )
        route, admission = await _route_and_admission(
            session,
            project=project,
            opportunity=opportunity,
        )
        await materialize_revision_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route.snapshot_hash,
            expected_admission_snapshot_hash=admission.snapshot_hash,
            idempotency_key=f"qm02d2:first:{uuid4()}",
        )
        before = await _counts(session)

        with pytest.raises(
            RevisionProductionHandoffError,
            match="revision_handoff_admission_stale",
        ):
            await materialize_revision_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=f"qm02d2:second:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_target_version_drift_fails_closed_before_materialization() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity, target, _ = await _selected_revision_opportunity(
            session,
            project=project,
            need=need,
            decision="UPDATE",
        )
        route, admission = await _route_and_admission(
            session,
            project=project,
            opportunity=opportunity,
        )
        await create_next_content_version(
            session,
            content_item_id=target.id,
            change_reason="Target changed after Founder selection.",
            content_json={"body": "Changed target."},
            status="draft",
        )
        before = await _counts(session)

        with pytest.raises(
            RevisionProductionHandoffError,
            match="revision_handoff_route_stale",
        ):
            await materialize_revision_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=f"qm02d2:stale-version:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_target_status_drift_fails_closed_before_materialization() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity, target, _ = await _selected_revision_opportunity(
            session,
            project=project,
            need=need,
            decision="UPDATE",
        )
        route, admission = await _route_and_admission(
            session,
            project=project,
            opportunity=opportunity,
        )
        target.status = "published"
        await session.flush()
        before = await _counts(session)

        with pytest.raises(
            RevisionProductionHandoffError,
            match="revision_handoff_route_stale",
        ):
            await materialize_revision_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=f"qm02d2:stale-status:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_revision_replay_survives_later_need_rejection() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity, _, _ = await _selected_revision_opportunity(
            session,
            project=project,
            need=need,
            decision="REFRESH",
        )
        route, admission = await _route_and_admission(
            session,
            project=project,
            opportunity=opportunity,
        )
        key = f"qm02d2:refresh:{uuid4()}"
        first = await materialize_revision_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route.snapshot_hash,
            expected_admission_snapshot_hash=admission.snapshot_hash,
            idempotency_key=key,
        )
        before = await _counts(session)

        need.status = "REJECTED"
        need.version += 1
        await session.flush()

        replay = await materialize_revision_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route.snapshot_hash,
            expected_admission_snapshot_hash=admission.snapshot_hash,
            idempotency_key=key,
        )

        assert replay.replayed is True
        assert replay.command_id == first.command_id
        assert replay.target_content_version_id == first.target_content_version_id
        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_rejected_need_blocks_new_revision_handoff() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity, _, _ = await _selected_revision_opportunity(
            session,
            project=project,
            need=need,
            decision="UPDATE",
        )
        route, admission = await _route_and_admission(
            session,
            project=project,
            opportunity=opportunity,
        )
        need.status = "REJECTED"
        need.version += 1
        await session.flush()
        before = await _counts(session)

        with pytest.raises(
            RevisionProductionHandoffError,
            match="revision_handoff_need_rejected",
        ):
            await materialize_revision_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=f"qm02d2:rejected:{uuid4()}",
            )

        assert await _counts(session) == before
