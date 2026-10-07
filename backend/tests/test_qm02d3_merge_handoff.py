from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    HumanSelection,
    LocaleVariant,
)
from app.modules.content_engine.persistence import (
    create_next_content_version,
)
from app.modules.harness.models import ContentRun, Job, StepRun
from app.modules.research.keyword_plan.production_admission import (
    build_production_admission,
)
from app.modules.research.keyword_plan.production_decision_router import (
    build_production_decision_route,
)
from app.modules.research.keyword_plan.reconciliation_handoff import (
    MergeProductionHandoffError,
    materialize_merge_handoff,
)
from test_qm02c_production_admission import (
    _need,
    _project,
    _run,
    _selected_opportunity,
    _target_item,
    isolated_session,
)


async def _merge_fixture(session: AsyncSession):
    project = await _project(session)
    need = await _need(session, project_id=project.id)
    first = await _target_item(
        session,
        project=project,
        need=need,
        suffix="merge-a",
    )
    second = await _target_item(
        session,
        project=project,
        need=need,
        suffix="merge-b",
    )
    opportunity, _ = await _selected_opportunity(
        session,
        project=project,
        need=need,
        decision="MERGE",
        target_ids=[first.id, second.id],
    )
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
    assert route.route == "RECONCILE_CONTENT"
    assert route.reconciliation_required is True
    assert admission.status == "RECONCILIATION_REQUIRED"
    return project, need, opportunity, first, second, route, admission


async def _counts(session: AsyncSession) -> dict[str, int]:
    models = {
        "opportunity": ContentOpportunity,
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
async def test_merge_handoff_freezes_conflict_set_without_destructive_effects() -> None:
    async with isolated_session() as session:
        (
            project,
            _need_row,
            opportunity,
            first,
            second,
            route,
            admission,
        ) = await _merge_fixture(session)
        before = await _counts(session)

        result = await materialize_merge_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            survivor_content_item_id=first.id,
            founder_reason=(
                "Keep the stronger canonical article and reconcile the duplicate."
            ),
            expected_route_snapshot_hash=route.snapshot_hash,
            expected_admission_snapshot_hash=admission.snapshot_hash,
            idempotency_key=f"qm02d3:merge:{uuid4()}",
        )
        after = await _counts(session)

        assert result.replayed is False
        assert result.survivor_content_item_id == first.id
        assert {
            row.content_item_id for row in result.target_snapshots
        } == {first.id, second.id}
        assert all(
            row.current_content_version_id is not None
            for row in result.target_snapshots
        )
        assert len(result.conflict_set_hash) == 64

        reconciliation_case = await session.get(
            ContentCase,
            result.reconciliation_content_case_id,
        )
        source_variant = await session.get(
            LocaleVariant,
            result.source_locale_variant_id,
        )
        receipt = await session.get(OperatorCommand, result.command_id)
        assert reconciliation_case is not None
        assert reconciliation_case.content_opportunity_id == opportunity.id
        assert source_variant is not None
        assert source_variant.content_case_id == reconciliation_case.id
        assert len(source_variant.keyword_notes_json) == 1
        plan = source_variant.keyword_notes_json[0]
        assert isinstance(plan, dict)
        assert plan["kind"] == "qm_merge_reconciliation_plan"
        assert plan["conflict_set_hash"] == result.conflict_set_hash
        assert plan["survivor_content_item_id"] == str(first.id)
        assert len(plan["target_snapshots"]) == 2

        assert receipt is not None
        assert receipt.content_case_id == reconciliation_case.id
        assert receipt.result_ref_id == result.survivor_content_version_id
        assert (
            receipt.resolved_action_key
            == "materialize_question_map_merge"
        )
        assert receipt.run_id is None
        assert receipt.step_run_id is None
        assert receipt.job_id is None

        assert after["case"] == before["case"] + 1
        assert after["variant"] == before["variant"] + 1
        assert after["command"] == before["command"] + 1
        for key in (
            "opportunity",
            "selection",
            "item",
            "version",
            "run",
            "step",
            "job",
        ):
            assert after[key] == before[key]

        first_after = await session.get(ContentItem, first.id)
        second_after = await session.get(ContentItem, second.id)
        assert first_after is not None and first_after.status == first.status
        assert second_after is not None and second_after.status == second.status

        post_admission = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route.snapshot_hash,
        )
        assert post_admission.status == "BLOCKED_ALREADY_MATERIALIZED"
        assert post_admission.reason_codes == [
            "production_admission_merge_already_materialized"
        ]


@pytest.mark.asyncio
async def test_merge_handoff_exact_replay_returns_frozen_plan() -> None:
    async with isolated_session() as session:
        (
            project,
            need,
            opportunity,
            first,
            _second,
            route,
            admission,
        ) = await _merge_fixture(session)
        key = f"qm02d3:replay:{uuid4()}"
        reason = "Founder explicitly selected the canonical survivor."
        first_result = await materialize_merge_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            survivor_content_item_id=first.id,
            founder_reason=reason,
            expected_route_snapshot_hash=route.snapshot_hash,
            expected_admission_snapshot_hash=admission.snapshot_hash,
            idempotency_key=key,
        )
        before = await _counts(session)

        need.status = "REJECTED"
        need.version += 1
        await session.flush()

        replay = await materialize_merge_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            survivor_content_item_id=first.id,
            founder_reason=reason,
            expected_route_snapshot_hash=route.snapshot_hash,
            expected_admission_snapshot_hash=admission.snapshot_hash,
            idempotency_key=key,
        )

        assert replay.replayed is True
        assert replay.command_id == first_result.command_id
        assert (
            replay.reconciliation_content_case_id
            == first_result.reconciliation_content_case_id
        )
        assert replay.conflict_set_hash == first_result.conflict_set_hash
        assert replay.target_snapshots == first_result.target_snapshots
        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_merge_handoff_same_key_rejects_changed_survivor() -> None:
    async with isolated_session() as session:
        (
            project,
            _need_row,
            opportunity,
            first,
            second,
            route,
            admission,
        ) = await _merge_fixture(session)
        key = f"qm02d3:conflict:{uuid4()}"
        reason = "Founder selected a canonical survivor."
        await materialize_merge_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            survivor_content_item_id=first.id,
            founder_reason=reason,
            expected_route_snapshot_hash=route.snapshot_hash,
            expected_admission_snapshot_hash=admission.snapshot_hash,
            idempotency_key=key,
        )

        with pytest.raises(
            MergeProductionHandoffError,
            match="merge_handoff_idempotency_conflict",
        ):
            await materialize_merge_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                survivor_content_item_id=second.id,
                founder_reason=reason,
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=key,
            )


@pytest.mark.asyncio
async def test_distinct_key_cannot_duplicate_merge_materialization() -> None:
    async with isolated_session() as session:
        (
            project,
            _need_row,
            opportunity,
            first,
            _second,
            route,
            admission,
        ) = await _merge_fixture(session)
        reason = "Founder selected a canonical survivor."
        await materialize_merge_handoff(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            survivor_content_item_id=first.id,
            founder_reason=reason,
            expected_route_snapshot_hash=route.snapshot_hash,
            expected_admission_snapshot_hash=admission.snapshot_hash,
            idempotency_key=f"qm02d3:first:{uuid4()}",
        )
        before = await _counts(session)

        with pytest.raises(
            MergeProductionHandoffError,
            match="merge_handoff_admission_stale",
        ):
            await materialize_merge_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                survivor_content_item_id=first.id,
                founder_reason=reason,
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=f"qm02d3:second:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_merge_handoff_target_version_drift_fails_closed() -> None:
    async with isolated_session() as session:
        (
            project,
            _need_row,
            opportunity,
            first,
            second,
            route,
            admission,
        ) = await _merge_fixture(session)
        await create_next_content_version(
            session,
            content_item_id=second.id,
            change_reason="Conflict target changed after Founder selection.",
            content_json={"body": "Changed duplicate answer."},
            status="draft",
        )
        before = await _counts(session)

        with pytest.raises(
            MergeProductionHandoffError,
            match="merge_handoff_route_stale",
        ):
            await materialize_merge_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                survivor_content_item_id=first.id,
                founder_reason="Keep first item.",
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=f"qm02d3:stale:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_merge_handoff_active_target_run_fails_closed() -> None:
    async with isolated_session() as session:
        (
            project,
            _need_row,
            opportunity,
            first,
            second,
            route,
            admission,
        ) = await _merge_fixture(session)
        await _run(
            session,
            project=project,
            item=second,
            status="running",
        )
        blocked = await build_production_admission(
            session,
            project_id=project.id,
            opportunity_id=opportunity.id,
            expected_route_snapshot_hash=route.snapshot_hash,
        )
        assert blocked.status == "BLOCKED_PRODUCTION_CONFLICT"
        assert blocked.reason_codes == [
            "production_admission_target_has_unresolved_run"
        ]
        before = await _counts(session)

        with pytest.raises(
            MergeProductionHandoffError,
            match="merge_handoff_admission_stale",
        ):
            await materialize_merge_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                survivor_content_item_id=first.id,
                founder_reason="Keep first item.",
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=f"qm02d3:active:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_merge_handoff_requires_explicit_survivor_in_conflict_set() -> None:
    async with isolated_session() as session:
        (
            project,
            _need_row,
            opportunity,
            _first,
            _second,
            route,
            admission,
        ) = await _merge_fixture(session)

        with pytest.raises(
            MergeProductionHandoffError,
            match="merge_handoff_survivor_not_in_conflict_set",
        ):
            await materialize_merge_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                survivor_content_item_id=uuid4(),
                founder_reason="Choose a survivor explicitly.",
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=f"qm02d3:survivor:{uuid4()}",
            )


@pytest.mark.asyncio
async def test_merge_handoff_rejects_incompatible_target_intent() -> None:
    async with isolated_session() as session:
        (
            project,
            _need_row,
            opportunity,
            first,
            second,
            route,
            admission,
        ) = await _merge_fixture(session)
        second_item = await session.get(ContentItem, second.id)
        assert second_item is not None
        variant = await session.get(
            LocaleVariant,
            second_item.locale_variant_id,
        )
        assert variant is not None
        variant.primary_intent = "learn"
        await session.flush()

        with pytest.raises(
            MergeProductionHandoffError,
            match="merge_handoff_target_intent_mismatch",
        ):
            await materialize_merge_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                survivor_content_item_id=first.id,
                founder_reason="Keep first item.",
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=f"qm02d3:intent:{uuid4()}",
            )

@pytest.mark.asyncio
async def test_merge_handoff_target_status_drift_fails_closed() -> None:
    async with isolated_session() as session:
        (
            project,
            _need_row,
            opportunity,
            first,
            second,
            route,
            admission,
        ) = await _merge_fixture(session)
        second.status = "published"
        await session.flush()
        before = await _counts(session)

        with pytest.raises(
            MergeProductionHandoffError,
            match="merge_handoff_route_stale",
        ):
            await materialize_merge_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                survivor_content_item_id=first.id,
                founder_reason="Keep first item.",
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=f"qm02d3:status-drift:{uuid4()}",
            )

        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_rejected_need_blocks_new_merge_handoff() -> None:
    async with isolated_session() as session:
        (
            project,
            need,
            opportunity,
            first,
            _second,
            route,
            admission,
        ) = await _merge_fixture(session)
        need.status = "REJECTED"
        need.version += 1
        await session.flush()
        before = await _counts(session)

        with pytest.raises(
            MergeProductionHandoffError,
            match="merge_handoff_need_rejected",
        ):
            await materialize_merge_handoff(
                session,
                project_id=project.id,
                opportunity_id=opportunity.id,
                survivor_content_item_id=first.id,
                founder_reason="Keep first item.",
                expected_route_snapshot_hash=route.snapshot_hash,
                expected_admission_snapshot_hash=admission.snapshot_hash,
                idempotency_key=f"qm02d3:rejected:{uuid4()}",
            )

        assert await _counts(session) == before

