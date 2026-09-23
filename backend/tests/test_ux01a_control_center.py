from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from test_ce05_review_actions import _pending_fixture
from test_ce05_review_console import isolated_session
from test_ll01d_learning_regression import (
    _applied_need,
    _second_experiment_search_signal,
)
from test_operator_start_to_angle import (
    ControlledCodexRunner,
    ControlledEvidenceWorkflow,
    _activate_seeded_angle_runtime,
    _intake_kwargs,
    _ready_preflight,
)

import app.modules.content_engine.journal.operator_vertical_slice as vertical_slice
from app.main import app
from app.modules.content_engine.journal.operator_manual_intake import (
    create_founder_journal_intake,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    get_operator_state_v45,
    submit_operator_command_v45,
)
from app.modules.content_engine.journal.operator_worker import (
    claim_next_operator_job,
    execute_start_to_angle_job,
)
from app.modules.content_engine.models import Project
from app.modules.control_center.read_model import (
    ControlCenterError,
    build_control_center,
)
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import Approval, Artifact, ModelCall, ToolCall
from app.modules.learning.regression import create_learning_validation


async def _read_only_counts(session) -> tuple[int, int, int, int]:
    return (
        int(await session.scalar(select(func.count()).select_from(ModelCall)) or 0),
        int(await session.scalar(select(func.count()).select_from(ToolCall)) or 0),
        int(await session.scalar(select(func.count()).select_from(Approval)) or 0),
        int(await session.scalar(select(func.count()).select_from(Artifact)) or 0),
    )


@pytest.mark.asyncio
async def test_ux01a_needs_me_is_project_scoped_and_read_only() -> None:
    async with isolated_session() as session:
        target = await _pending_fixture(session)
        other = await _pending_fixture(session)
        target_project = await session.get(Project, target.writer_run.project_id)
        assert target_project is not None
        before = await _read_only_counts(session)

        snapshot = await build_control_center(
            session,
            project_slug=target_project.slug,
            timezone_name="UTC",
            as_of=datetime.now(UTC),
        )

        assert await _read_only_counts(session) == before
        assert snapshot.summary.project_id == target_project.id
        assert snapshot.summary.counts.needs_human == 1
        assert snapshot.summary.counts.blocked == 0
        assert len(snapshot.needs_me) == 1
        item = snapshot.needs_me[0]
        assert item.type == "content_approval"
        assert item.canonical_status == "WAITING_APPROVAL"
        assert item.destination.entity_id == str(target.content_case_id)
        assert str(other.content_case_id) not in item.id
        assert any(ref.startswith("artifact:") for ref in item.evidence_refs)


@pytest.mark.asyncio
async def test_ux01a_uses_operator_runtime_for_angle_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vertical_slice,
        "build_journal_operator_preflight",
        _ready_preflight,
    )
    async with isolated_session() as session:
        await _activate_seeded_angle_runtime(session)
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="ux01a-angle-gate"),
        )
        state = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="ux01a-angle-gate-start",
        )
        assert queued.job_id is not None
        leased = await claim_next_operator_job(
            session,
            worker_id="worker-ux01a-angle",
        )
        assert leased is not None
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", ControlledCodexRunner())
        await execute_start_to_angle_job(
            session,
            job_id=leased.id,
            worker_id="worker-ux01a-angle",
            evidence_workflow=ControlledEvidenceWorkflow(),  # type: ignore[arg-type]
            runner_registry=registry,
        )
        before = await _read_only_counts(session)

        snapshot = await build_control_center(
            session,
            project_slug="motgu",
            timezone_name="UTC",
        )

        assert await _read_only_counts(session) == before
        angle_items = [
            item
            for item in snapshot.needs_me
            if item.type == "content_approval"
            and item.destination.entity_id == str(created.content_case_id)
        ]
        assert len(angle_items) == 1
        item = angle_items[0]
        assert item.canonical_status == "AWAITING_APPROVAL"
        assert ":angle:" in item.destination.action_ref
        assert item.destination.href == f"/operator/journal/{created.content_case_id}"
        assert len(item.evidence_refs) == 1
        assert item.evidence_refs[0].startswith("artifact:")


@pytest.mark.asyncio
async def test_ux01a_stale_waiting_approval_fails_closed() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        project = await session.get(Project, fixture.writer_run.project_id)
        assert project is not None
        session.add(
            Approval(
                run_id=fixture.writer_run.id,
                step_key="final_review",
                artifact_id=fixture.final_artifact.id,
                decision="approved",
                actor_id="founder",
            )
        )
        await session.flush()

        snapshot = await build_control_center(
            session,
            project_slug=project.slug,
            timezone_name="UTC",
        )

        assert snapshot.summary.counts.needs_human == 0
        assert snapshot.summary.counts.blocked >= 1
        assert snapshot.needs_me == []
        assert any(
            issue.code == "control_center_pending_approval_stale"
            for issue in snapshot.summary.issues
        )


@pytest.mark.asyncio
async def test_ux01a_surfaces_only_actionable_learning_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, _baseline_signal, _candidate, application = await _applied_need(
            session,
            monkeypatch,
        )
        later_signal = await _second_experiment_search_signal(
            session,
            fixture=fixture,
            worker_id="ux01a-later-signal",
            impressions=180,
        )
        validation = await create_learning_validation(
            session,
            learning_application_id=application.id,
            validation_status="VALIDATED",
            signal_relations={later_signal.id: "supports"},
            metric_comparisons=[],
            alternative_explanations=["Distribution can still affect exposure."],
            missing_evidence=[],
        )

        snapshot = await build_control_center(
            session,
            project_slug=fixture.project.slug,
            timezone_name="UTC",
        )

        learning_items = [
            item for item in snapshot.needs_me if item.type == "learning_resolution"
        ]
        assert len(learning_items) == 1
        item = learning_items[0]
        assert item.destination.entity_id == str(validation.validation.id)
        assert item.canonical_status == "VALIDATED"
        assert f"signal:{later_signal.id}" in item.evidence_refs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "validation_status",
    ["NEEDS_MORE_EVIDENCE", "INCONCLUSIVE"],
)
async def test_ux01a_does_not_escalate_non_actionable_learning_states(
    monkeypatch: pytest.MonkeyPatch,
    validation_status: str,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, _baseline_signal, _candidate, application = await _applied_need(
            session,
            monkeypatch,
        )
        await create_learning_validation(
            session,
            learning_application_id=application.id,
            validation_status=validation_status,
            signal_relations={},
            metric_comparisons=[],
            alternative_explanations=[],
            missing_evidence=["Need later independent evidence."],
        )

        snapshot = await build_control_center(
            session,
            project_slug=fixture.project.slug,
            timezone_name="UTC",
        )

        assert all(
            item.type != "learning_resolution"
            for item in snapshot.needs_me
        )


@pytest.mark.asyncio
async def test_ux01a_invalid_timezone_fails_closed() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        project = await session.get(Project, fixture.writer_run.project_id)
        assert project is not None

        with pytest.raises(
            ControlCenterError,
            match="control_center_timezone_invalid",
        ):
            await build_control_center(
                session,
                project_slug=project.slug,
                timezone_name="Not/A_Real_Timezone",
            )


def test_ux01a_read_only_routes_are_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/control-center/summary" in paths
    assert "/control-center/needs-me" in paths
    assert set(paths["/control-center/summary"]) == {"get"}
    assert set(paths["/control-center/needs-me"]) == {"get"}