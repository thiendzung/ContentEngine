from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import func, select
from test_ce05_review_actions import _pending_fixture
from test_ce05_review_console import isolated_session
from test_ll01d_learning_regression import (
    _applied_need,
    _second_experiment_search_signal,
)

from app.main import app
from app.modules.content_engine.models import Project
from app.modules.control_center.read_model import (
    ControlCenterError,
    build_control_center,
)
from app.modules.harness.models import Approval, ModelCall, ToolCall
from app.modules.learning.regression import create_learning_validation


async def _execution_counts(session) -> tuple[int, int]:
    return (
        int(await session.scalar(select(func.count()).select_from(ModelCall)) or 0),
        int(await session.scalar(select(func.count()).select_from(ToolCall)) or 0),
    )


@pytest.mark.asyncio
async def test_ux01a_needs_me_is_project_scoped_and_read_only() -> None:
    async with isolated_session() as session:
        target = await _pending_fixture(session)
        other = await _pending_fixture(session)
        target_project = await session.get(Project, target.writer_run.project_id)
        assert target_project is not None
        before = await _execution_counts(session)

        snapshot = await build_control_center(
            session,
            project_slug=target_project.slug,
            timezone_name="UTC",
            as_of=datetime.now(UTC),
        )

        assert await _execution_counts(session) == before
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
async def test_ux01a_surfaces_only_actionable_learning_validation() -> None:
    async with isolated_session() as session:
        fixture, _mapping, _baseline_signal, _candidate, application = await _applied_need(
            session,
            pytest.MonkeyPatch(),
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
