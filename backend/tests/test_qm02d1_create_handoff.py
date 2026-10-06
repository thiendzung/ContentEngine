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
    ContentExperiment,
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.harness.models import ContentRun, Job, StepRun
from app.modules.research.keyword_plan.create_handoff import (
    CreateProductionHandoffError,
    materialize_create_handoff,
)
from app.modules.research.keyword_plan.opportunity_planner_v2 import (
    build_opportunity_plan_v2,
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
        slug=f"qm02d1-{uuid4().hex[:8]}",
        name="QM-02D1",
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


async def _need(
    session: AsyncSession,
    *,
    project_id: UUID,
    status: str = "SUPPORTED",
) -> NeedHypothesis:
    need = NeedHypothesis(
        project_id=project_id,
        type="question",
        statement="Buyer needs confidence choosing original art.",
        audience_scope="first-time art buyer",
        situation="considering a painting",
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
    *,
    project: Project,
    need: NeedHypothesis,
    text: str,
) -> Signal:
    signal = Signal(
        project_id=project.id,
        source_kind="SEARCH",
        scope="market_web",
        observed_text=text,
        source_url=f"https://example.com/{uuid4().hex}",
        locale="en",
        context="QM-02D1 fixture",
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


async def _selected_opportunity(
    session: AsyncSession,
    *,
    project: Project,
    need: NeedHypothesis,
    decision: str,
    target_ids: list[UUID],
) -> ContentOpportunity:
    if (
        decision == "CREATE"
        and not target_ids
        and need.status in {"PROPOSED", "TESTING", "SUPPORTED"}
    ):
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
            text="What budget should I set for a painting?",
        )
        plan = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        recommendations = plan["recommendations"]
        assert isinstance(recommendations, list)
        assert len(recommendations) == 1
        recommendation = recommendations[0]
        assert isinstance(recommendation, dict)
        assert recommendation["decision"] == "CREATE"
        assert (
            recommendation["selection_readiness"]
            == "READY_FOR_HUMAN_SELECTION"
        )
        result = await persist_selected_opportunity(
            session,
            project_id=project.id,
            request=OpportunitySelectionRequest(
                project_slug=project.slug,
                need_id=need.id,
                locale="en",
                cluster_key=str(recommendation["cluster_key"]),
                expected_planner_snapshot_hash=str(plan["snapshot_hash"]),
                selected_by="founder",
                selection_reason=(
                    "Founder selected this exact opportunity."
                ),
                promise="Give a practical decision path.",
                coverage_requirements=[
                    "Explain the decision criteria.",
                    "Show what the buyer should verify.",
                ],
            ),
        )
        opportunity = await session.get(
            ContentOpportunity,
            result.content_opportunity_id,
        )
        assert opportunity is not None
        return opportunity

    selected_at = datetime.now(UTC)
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader=need.audience_scope,
        situation=need.situation,
        need=need.statement,
        question="How do I choose original art with confidence?",
        intent="evaluate",
        promise="Give a practical decision path.",
        coverage_requirements_json=[
            "Explain the decision criteria.",
            "Show what the buyer should verify.",
        ],
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[str(value) for value in target_ids],
        what_is_actually_new="Founder-selected planning context.",
        next_discovery_step="Materialize only after admission.",
        decision=decision,
        priority="NOW" if decision == "CREATE" else "NEXT",
        reasons_json=["manual_fixture"],
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
        selected_by="founder",
        selected_at=selected_at,
        selection_reason="Founder selected this exact opportunity.",
    )
    session.add(opportunity)
    await session.flush()
    session.add(
        HumanSelection(
            content_opportunity_id=opportunity.id,
            selected_by="founder",
            reason=opportunity.selection_reason,
            selected_at=selected_at,
        )
    )
    await session.flush()
    return opportunity


async def _target_item(
    session: AsyncSession,
    *,
    project: Project,
    need: NeedHypothesis,
) -> ContentItem:
    selected_at = datetime.now(UTC)
    source = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader=need.audience_scope,
        situation=need.situation,
        need=need.statement,
        question="Existing buyer question.",
        intent="evaluate",
        promise="Existing answer.",
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
        selected_by="founder",
        selected_at=selected_at,
        selection_reason="Existing fixture selection.",
    )
    session.add(source)
    await session.flush()
    session.add(
        HumanSelection(
            content_opportunity_id=source.id,
            selected_by="founder",
            reason=source.selection_reason,
            selected_at=selected_at,
        )
    )
    await session.flush()

    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=source.id,
        desired_action="Keep the existing answer useful.",
        content_hypothesis="Existing content answers the Need.",
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
        primary_question=source.question,
        primary_intent=source.intent,
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
        canonical_key=f"journal:qm02d1-{uuid4().hex}:en",
    )
    session.add(item)
    await session.flush()
    return item


async def _snapshots(
    session: AsyncSession,
    *,
    project: Project,
    opportunity: ContentOpportunity,
) -> tuple[str, str]:
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
    return route.snapshot_hash, admission.snapshot_hash


async def _counts(session: AsyncSession) -> dict[str, int]:
    models = {
        "need": NeedHypothesis,
        "opportunity": ContentOpportunity,
        "selection": HumanSelection,
        "case": ContentCase,
        "variant": LocaleVariant,
        "item": ContentItem,
        "version": ContentVersion,
        "experiment": ContentExperiment,
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
async def test_create_handoff_requires_qm02a_selection_lineage() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id, status="PROPOSED")
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        opportunity.reasons_json = ["manual_fixture_without_qm02a_lineage"]
        await session.flush()
        route_hash, admission_hash = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        before = await _counts(session)

        with pytest.raises(
            CreateProductionHandoffError,
            match="create_handoff_qm02a_lineage_required",
        ):
            await materialize_create_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash=route_hash,
                expected_admission_snapshot_hash=admission_hash,
                idempotency_key=f"qm02d1:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["PROPOSED", "TESTING", "SUPPORTED"])
async def test_create_handoff_allows_materializable_need_states(
    status: str,
) -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(
            session,
            project_id=project.id,
            status=status,
        )
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        route_hash, admission_hash = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        before = await _counts(session)

        result = await materialize_create_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
            expected_admission_snapshot_hash=admission_hash,
            idempotency_key=f"qm02d1:{uuid4()}",
        )
        after = await _counts(session)

        stored_need = await session.get(NeedHypothesis, need.id)
        assert stored_need is not None
        assert stored_need.status == status
        assert result.replayed is False
        assert after["case"] == before["case"] + 1
        assert after["variant"] == before["variant"] + 1
        assert after["command"] == before["command"] + 1
        for key in ("run", "step", "job"):
            assert after[key] == before[key]


@pytest.mark.asyncio
async def test_create_handoff_materializes_only_case_variant_and_receipt() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        route_hash, admission_hash = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        before = await _counts(session)

        result = await materialize_create_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
            expected_admission_snapshot_hash=admission_hash,
            idempotency_key=f"qm02d1:{uuid4()}",
        )
        after = await _counts(session)

        assert result.replayed is False
        assert result.route_snapshot_hash == route_hash
        assert result.admission_snapshot_hash == admission_hash
        assert result.state.status == "NOT_READY"
        assert result.state.blocker_code == "operator_pipeline_start_not_wired"
        receipt = await session.get(OperatorCommand, result.command_id)
        assert receipt is not None
        assert receipt.run_id is None
        assert receipt.step_run_id is None
        assert receipt.job_id is None
        assert receipt.result_ref_id == result.source_locale_variant_id
        assert receipt.resolved_action_key == "materialize_question_map_create"
        assert after["case"] == before["case"] + 1
        assert after["variant"] == before["variant"] + 1
        assert after["command"] == before["command"] + 1
        for key in (
            "need",
            "opportunity",
            "selection",
            "item",
            "version",
            "experiment",
            "run",
            "step",
            "job",
        ):
            assert after[key] == before[key]


@pytest.mark.asyncio
async def test_exact_replay_returns_same_receipt_without_new_rows() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        route_hash, admission_hash = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        key = f"qm02d1:{uuid4()}"
        first = await materialize_create_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
            expected_admission_snapshot_hash=admission_hash,
            idempotency_key=key,
        )
        before_replay = await _counts(session)

        replay = await materialize_create_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
            expected_admission_snapshot_hash=admission_hash,
            idempotency_key=key,
        )
        after_replay = await _counts(session)

        assert replay.replayed is True
        assert replay.command_id == first.command_id
        assert replay.content_case_id == first.content_case_id
        assert replay.source_locale_variant_id == first.source_locale_variant_id
        assert after_replay == before_replay


@pytest.mark.asyncio
async def test_exact_replay_survives_later_need_rejection() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id, status="PROPOSED")
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        route_hash, admission_hash = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        key = f"qm02d1:{uuid4()}"
        first = await materialize_create_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
            expected_admission_snapshot_hash=admission_hash,
            idempotency_key=key,
        )
        before_replay = await _counts(session)

        need.status = "REJECTED"
        need.version += 1
        await session.flush()

        replay = await materialize_create_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
            expected_admission_snapshot_hash=admission_hash,
            idempotency_key=key,
        )
        after_replay = await _counts(session)

        assert replay.replayed is True
        assert replay.command_id == first.command_id
        assert replay.content_case_id == first.content_case_id
        assert replay.source_locale_variant_id == first.source_locale_variant_id
        assert after_replay == before_replay


@pytest.mark.asyncio
async def test_same_idempotency_key_with_different_request_fails_closed() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        route_hash, admission_hash = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        key = f"qm02d1:{uuid4()}"
        await materialize_create_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
            expected_admission_snapshot_hash=admission_hash,
            idempotency_key=key,
        )

        with pytest.raises(
            CreateProductionHandoffError,
            match="create_handoff_idempotency_conflict",
        ):
            await materialize_create_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash=route_hash,
                expected_admission_snapshot_hash="f" * 64,
                idempotency_key=key,
            )


@pytest.mark.asyncio
async def test_stale_route_hash_fails_before_materialization() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        _, admission_hash = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        before = await _counts(session)

        with pytest.raises(
            CreateProductionHandoffError,
            match="create_handoff_route_stale",
        ):
            await materialize_create_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash="0" * 64,
                expected_admission_snapshot_hash=admission_hash,
                idempotency_key=f"qm02d1:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_stale_admission_hash_fails_before_materialization() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        route_hash, _ = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        before = await _counts(session)

        with pytest.raises(
            CreateProductionHandoffError,
            match="create_handoff_admission_stale",
        ):
            await materialize_create_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash=route_hash,
                expected_admission_snapshot_hash="0" * 64,
                idempotency_key=f"qm02d1:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_non_create_route_is_rejected() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        target = await _target_item(
            session,
            project=project,
            need=need,
        )
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="UPDATE",
            target_ids=[target.id],
        )
        route_hash, admission_hash = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        before = await _counts(session)

        with pytest.raises(
            CreateProductionHandoffError,
            match="create_handoff_requires_create_route",
        ):
            await materialize_create_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash=route_hash,
                expected_admission_snapshot_hash=admission_hash,
                idempotency_key=f"qm02d1:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_current_non_admitted_create_is_rejected() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        route_hash, _ = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        preexisting = ContentCase(
            project_id=project.id,
            content_type="journal",
            need_hypothesis_id=need.id,
            content_opportunity_id=opportunity.id,
            desired_action="Already materialized.",
            content_hypothesis=opportunity.promise,
            originality_statement="Fixture.",
            reader_before=opportunity.situation,
            reader_after=opportunity.promise,
        )
        session.add(preexisting)
        await session.flush()
        current_admission = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route_hash,
        )
        assert current_admission.status == "BLOCKED_ALREADY_MATERIALIZED"

        with pytest.raises(
            CreateProductionHandoffError,
            match="create_handoff_not_admitted",
        ):
            await materialize_create_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash=route_hash,
                expected_admission_snapshot_hash=current_admission.snapshot_hash,
                idempotency_key=f"qm02d1:{uuid4()}",
            )




@pytest.mark.asyncio
async def test_rejected_need_state_drift_blocks_materialization() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        route_hash, admission_hash = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        before = await _counts(session)

        need.status = "REJECTED"
        need.version += 1
        await session.flush()

        with pytest.raises(
            CreateProductionHandoffError,
            match="create_handoff_need_rejected",
        ):
            await materialize_create_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash=route_hash,
                expected_admission_snapshot_hash=admission_hash,
                idempotency_key=f"qm02d1:{uuid4()}",
            )

        after = await _counts(session)
        assert after["case"] == before["case"]
        assert after["variant"] == before["variant"]
        assert after["command"] == before["command"]
        for key in ("item", "version", "experiment", "run", "step", "job"):
            assert after[key] == before[key]


@pytest.mark.asyncio
async def test_insufficient_evidence_need_blocks_materialization() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(
            session,
            project_id=project.id,
            status="INSUFFICIENT_EVIDENCE",
        )
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )
        route_hash, admission_hash = await _snapshots(
            session,
            project=project,
            opportunity=opportunity,
        )
        before = await _counts(session)

        with pytest.raises(
            CreateProductionHandoffError,
            match="create_handoff_need_insufficient_evidence",
        ):
            await materialize_create_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash=route_hash,
                expected_admission_snapshot_hash=admission_hash,
                idempotency_key=f"qm02d1:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_invalid_hash_and_idempotency_inputs_fail_closed() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        opportunity = await _selected_opportunity(
            session,
            project=project,
            need=need,
            decision="CREATE",
            target_ids=[],
        )

        with pytest.raises(
            CreateProductionHandoffError,
            match="create_handoff_route_hash_invalid",
        ):
            await materialize_create_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash="bad",
                expected_admission_snapshot_hash="0" * 64,
                idempotency_key="valid-key",
            )

        with pytest.raises(
            CreateProductionHandoffError,
            match="create_handoff_idempotency_key_invalid",
        ):
            await materialize_create_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                expected_route_snapshot_hash="0" * 64,
                expected_admission_snapshot_hash="0" * 64,
                idempotency_key=" ",
            )
