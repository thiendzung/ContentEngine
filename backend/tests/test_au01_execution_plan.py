from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError
from test_ce05_review_console import _approved_fixture, isolated_session

from app.modules.content_engine.models import SettingsSnapshot, SettingsVersion
from app.modules.harness.execution_plan import (
    ExecutionPlanError,
    authorize_execution_plan,
    persist_execution_plan_artifact,
)
from app.modules.harness.models import Artifact, ContentRun, StepRun
from app.modules.system.settings_service import create_settings_snapshot


def _policy(
    *,
    capabilities: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    allowed_actions: list[str] | None = None,
    forbidden_actions: list[str] | None = None,
    max_attempts: int = 3,
    max_timeout_seconds: int = 300,
) -> dict[str, object]:
    return {
        "autopilot": {
            "capability_policy": {
                "schema_version": 1,
                "enabled": True,
                "workers": {
                    "customer-map-worker": {
                        "capabilities": (
                            capabilities
                            if capabilities is not None
                            else [
                                "READ",
                                "WRITE_ARTIFACT",
                                "RUN_TOOL",
                                "WRITE_DATABASE",
                            ]
                        ),
                        "allowed_actions": (
                            allowed_actions
                            if allowed_actions is not None
                            else [
                                "read.customer",
                                "database.write.customer_map",
                                "artifact.write.customer_map",
                            ]
                        ),
                        "forbidden_actions": (
                            forbidden_actions
                            if forbidden_actions is not None
                            else [
                                "publish.execute",
                                "settings.change",
                                "workflow.change",
                            ]
                        ),
                        "allowed_tools": (
                            allowed_tools
                            if allowed_tools is not None
                            else ["customer_store", "dedupe"]
                        ),
                        "budget_ceiling": {
                            "max_tool_calls": 12,
                            "max_model_calls": 2,
                            "max_output_tokens": 8000,
                            "max_estimated_cost": "1.50",
                            "max_wall_clock_seconds": 240,
                        },
                        "max_timeout_seconds": max_timeout_seconds,
                        "max_attempts": max_attempts,
                    }
                },
            }
        }
    }


def _plan(**overrides: object) -> dict[str, object]:
    plan: dict[str, object] = {
        "schema_version": 1,
        "task_key": "customer_map_refresh",
        "worker_key": "customer-map-worker",
        "goal": "Refresh one bounded customer map from approved inputs.",
        "input_refs": ["customer_insight:fixture", "coverage:fixture"],
        "expected_output_types": ["customer_map_snapshot"],
        "required_capabilities": [
            "READ",
            "WRITE_ARTIFACT",
            "RUN_TOOL",
            "WRITE_DATABASE",
        ],
        "allowed_actions": [
            "read.customer",
            "database.write.customer_map",
            "artifact.write.customer_map",
        ],
        "forbidden_actions": [
            "publish.execute",
            "settings.change",
            "workflow.change",
        ],
        "allowed_tools": ["customer_store", "dedupe"],
        "budget": {
            "max_tool_calls": 6,
            "max_model_calls": 1,
            "max_output_tokens": 4000,
            "max_estimated_cost": "0.50",
            "max_wall_clock_seconds": 120,
        },
        "timeout_seconds": 120,
        "max_attempts": 2,
        "stop_conditions": [
            "required input is missing",
            "project scope is ambiguous",
        ],
        "required_checks": [
            "schema_valid",
            "project_scope_valid",
            "output_traceable",
        ],
        "reviewer": "customer-map-reviewer",
        "next_on_pass": "coverage_refresh",
        "next_on_fail": "blocked",
        "human_gate_required": False,
    }
    plan.update(overrides)
    return plan


async def _approved_policy_snapshot(
    session,
    *,
    project_id,
    settings: dict[str, object],
) -> SettingsSnapshot:
    version = SettingsVersion(
        project_id=None,
        scope_type="system",
        scope_key=f"au01-{uuid4().hex[:12]}",
        version=1,
        settings_json=settings,
        status="active",
        change_reason="AU-01 capability policy test fixture",
        approved_by="founder",
    )
    session.add(version)
    await session.flush()
    return await create_settings_snapshot(
        session,
        project_id=project_id,
        resolved_settings=settings,
        source_version_refs=[f"settings_version:{version.id}:v{version.version}"],
    )


async def _execution_fixture(
    session,
    *,
    settings: dict[str, object] | None = None,
) -> tuple[ContentRun, StepRun]:
    base = await _approved_fixture(session)
    source = base.writer_runs["en"]
    snapshot = await _approved_policy_snapshot(
        session,
        project_id=source.project_id,
        settings=settings or _policy(),
    )
    run = ContentRun(
        project_id=source.project_id,
        content_case_id=source.content_case_id,
        locale_variant_id=source.locale_variant_id,
        content_item_id=source.content_item_id,
        run_mode="update",
        status="running",
        current_step="customer_map_refresh",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    step = StepRun(
        run_id=run.id,
        step_key="customer_map_refresh",
        attempt=1,
        status="running",
        input_artifact_refs_json=[],
        output_artifact_refs_json=[],
        started_at=datetime.now(UTC),
    )
    session.add(step)
    await session.flush()
    return run, step


@pytest.mark.asyncio
async def test_execution_plan_persists_authorizes_and_exactly_replays() -> None:
    async with isolated_session() as session:
        run, step = await _execution_fixture(session)

        first = await persist_execution_plan_artifact(
            session,
            run_id=run.id,
            step_run_id=step.id,
            plan=_plan(),
        )
        replay = await persist_execution_plan_artifact(
            session,
            run_id=run.id,
            step_run_id=step.id,
            plan=_plan(),
        )
        authorized = await authorize_execution_plan(
            session,
            artifact_id=first.id,
            worker_key="customer-map-worker",
        )

        assert replay.id == first.id
        assert first.content_json is not None
        assert first.content_json["settings_snapshot_id"] == str(run.settings_snapshot_id)
        assert authorized.artifact_id == first.id
        assert authorized.plan.task_key == "customer_map_refresh"
        assert authorized.plan.max_attempts == 2
        assert authorized.policy.worker_key == "customer-map-worker"


@pytest.mark.asyncio
async def test_execution_plan_replay_conflict_fails_closed() -> None:
    async with isolated_session() as session:
        run, step = await _execution_fixture(session)
        await persist_execution_plan_artifact(
            session,
            run_id=run.id,
            step_run_id=step.id,
            plan=_plan(),
        )

        with pytest.raises(
            ExecutionPlanError,
            match="execution_plan_replay_conflict",
        ):
            await persist_execution_plan_artifact(
                session,
                run_id=run.id,
                step_run_id=step.id,
                plan=_plan(goal="Changed goal must require a new version."),
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("plan_override", "settings_override", "error_code"),
    [
        (
            {"required_capabilities": ["READ", "PUBLISH"]},
            {},
            "execution_plan_capability_not_allowed",
        ),
        (
            {"allowed_tools": ["shell"]},
            {},
            "execution_plan_tool_not_allowed",
        ),
        (
            {
                "required_capabilities": [
                    "READ",
                    "WRITE_ARTIFACT",
                    "RUN_TOOL",
                    "WRITE_DATABASE",
                    "RUN_MODEL",
                ],
                "allowed_actions": [
                    "read.customer",
                    "database.write.customer_map",
                    "artifact.write.customer_map",
                    "model.run.writer",
                ],
            },
            {},
            "execution_plan_action_not_allowed",
        ),
        (
            {
                "forbidden_actions": [
                    "publish.execute",
                    "settings.change",
                ]
            },
            {},
            "execution_plan_policy_forbidden_action_missing",
        ),
        (
            {"timeout_seconds": 301},
            {},
            "execution_plan_timeout_exceeds_policy",
        ),
        (
            {"max_attempts": 4},
            {},
            "execution_plan_attempts_exceed_policy",
        ),
        (
            {
                "budget": {
                    "max_tool_calls": 13,
                    "max_model_calls": 1,
                    "max_output_tokens": 4000,
                    "max_estimated_cost": "0.50",
                    "max_wall_clock_seconds": 120,
                }
            },
            {},
            "execution_plan_budget_exceeds_policy",
        ),
        (
            {
                "required_capabilities": ["READ", "WRITE_ARTIFACT", "RUN_TOOL"],
            },
            {},
            "execution_plan_action_capability_missing",
        ),
        (
            {
                "budget": {
                    "max_tool_calls": 6,
                    "max_model_calls": 1,
                    "max_output_tokens": 4000,
                    "max_estimated_cost": "0.50",
                }
            },
            {},
            "execution_plan_required_budget_missing",
        ),
    ],
)
async def test_execution_plan_policy_mismatch_fails_closed(
    plan_override: dict[str, object],
    settings_override: dict[str, object],
    error_code: str,
) -> None:
    async with isolated_session() as session:
        run, step = await _execution_fixture(
            session,
            settings=_policy(**settings_override),
        )

        with pytest.raises(ExecutionPlanError, match=error_code):
            await persist_execution_plan_artifact(
                session,
                run_id=run.id,
                step_run_id=step.id,
                plan=_plan(**plan_override),
            )


@pytest.mark.asyncio
async def test_sensitive_capability_requires_human_gate() -> None:
    async with isolated_session() as session:
        run, step = await _execution_fixture(
            session,
            settings=_policy(
                capabilities=["READ", "PUBLISH"],
                allowed_actions=["publish.execute"],
                forbidden_actions=["settings.change", "workflow.change"],
                allowed_tools=[],
            ),
        )
        sensitive = _plan(
            required_capabilities=["READ", "PUBLISH"],
            allowed_actions=["publish.execute"],
            forbidden_actions=["settings.change", "workflow.change"],
            allowed_tools=[],
            human_gate_required=False,
        )

        with pytest.raises(
            ExecutionPlanError,
            match="execution_plan_human_gate_required",
        ):
            await persist_execution_plan_artifact(
                session,
                run_id=run.id,
                step_run_id=step.id,
                plan=sensitive,
            )


@pytest.mark.asyncio
async def test_authorization_rejects_wrong_worker_and_stale_run_binding() -> None:
    async with isolated_session() as session:
        run, step = await _execution_fixture(session)
        artifact = await persist_execution_plan_artifact(
            session,
            run_id=run.id,
            step_run_id=step.id,
            plan=_plan(),
        )

        with pytest.raises(
            ExecutionPlanError,
            match="execution_plan_worker_mismatch",
        ):
            await authorize_execution_plan(
                session,
                artifact_id=artifact.id,
                worker_key="other-worker",
            )

        replacement = await _approved_policy_snapshot(
            session,
            project_id=run.project_id,
            settings=_policy(max_attempts=1),
        )
        run.settings_snapshot_id = replacement.id
        await session.flush()

        with pytest.raises(
            ExecutionPlanError,
            match="execution_plan_settings_snapshot_mismatch",
        ):
            await authorize_execution_plan(
                session,
                artifact_id=artifact.id,
                worker_key="customer-map-worker",
            )


@pytest.mark.asyncio
async def test_execution_plan_requires_approved_policy_source() -> None:
    async with isolated_session() as session:
        base = await _approved_fixture(session)
        source = base.writer_runs["en"]
        snapshot = await create_settings_snapshot(
            session,
            project_id=source.project_id,
            resolved_settings=_policy(),
            source_version_refs=["run_override:unapproved-policy"],
        )
        run = ContentRun(
            project_id=source.project_id,
            content_case_id=source.content_case_id,
            locale_variant_id=source.locale_variant_id,
            content_item_id=source.content_item_id,
            run_mode="update",
            status="running",
            current_step="customer_map_refresh",
            settings_snapshot_id=snapshot.id,
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()

        with pytest.raises(
            ExecutionPlanError,
            match="execution_plan_policy_approved_source_required",
        ):
            await persist_execution_plan_artifact(
                session,
                run_id=run.id,
                step_run_id=None,
                plan=_plan(),
            )


@pytest.mark.asyncio
async def test_execution_plan_rejects_policy_snapshot_source_mismatch() -> None:
    async with isolated_session() as session:
        base = await _approved_fixture(session)
        source = base.writer_runs["en"]
        approved = _policy(max_attempts=1)
        version = SettingsVersion(
            project_id=None,
            scope_type="system",
            scope_key=f"au01-mismatch-{uuid4().hex[:12]}",
            version=1,
            settings_json=approved,
            status="active",
            change_reason="AU-01 mismatch test",
            approved_by="founder",
        )
        session.add(version)
        await session.flush()
        snapshot = await create_settings_snapshot(
            session,
            project_id=source.project_id,
            resolved_settings=_policy(max_attempts=3),
            source_version_refs=[
                f"settings_version:{version.id}:v{version.version}"
            ],
        )
        run = ContentRun(
            project_id=source.project_id,
            content_case_id=source.content_case_id,
            locale_variant_id=source.locale_variant_id,
            content_item_id=source.content_item_id,
            run_mode="update",
            status="running",
            current_step="customer_map_refresh",
            settings_snapshot_id=snapshot.id,
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()

        with pytest.raises(
            ExecutionPlanError,
            match="execution_plan_policy_snapshot_source_mismatch",
        ):
            await persist_execution_plan_artifact(
                session,
                run_id=run.id,
                step_run_id=None,
                plan=_plan(),
            )


@pytest.mark.asyncio
async def test_execution_plan_and_settings_snapshot_are_database_immutable() -> None:
    async with isolated_session() as session:
        run, step = await _execution_fixture(session)
        artifact = await persist_execution_plan_artifact(
            session,
            run_id=run.id,
            step_run_id=step.id,
            plan=_plan(),
        )
        snapshot_row = await session.get(SettingsSnapshot, run.settings_snapshot_id)
        assert snapshot_row is not None

        with pytest.raises(DBAPIError, match="artifact_is_immutable"):
            async with session.begin_nested():
                artifact.content_hash = "0" * 64
                await session.flush()

        await session.refresh(artifact)
        with pytest.raises(DBAPIError, match="artifact_is_immutable"):
            async with session.begin_nested():
                await session.delete(artifact)
                await session.flush()

        with pytest.raises(DBAPIError, match="settings_snapshots_are_immutable"):
            async with session.begin_nested():
                snapshot_row.content_hash = "f" * 64
                await session.flush()

        await session.refresh(snapshot_row)
        with pytest.raises(DBAPIError, match="settings_snapshots_are_immutable"):
            async with session.begin_nested():
                await session.delete(snapshot_row)
                await session.flush()


@pytest.mark.asyncio
async def test_malformed_direct_execution_plan_artifact_is_not_authorized() -> None:
    async with isolated_session() as session:
        run, step = await _execution_fixture(session)
        malformed = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="execution_plan_deadbeefdeadbeefdeadbeef",
            locale=None,
            version=1,
            content_json={"schema_version": 1},
            content_hash="0" * 64,
        )
        session.add(malformed)
        await session.flush()

        with pytest.raises(
            ExecutionPlanError,
            match="execution_plan_artifact_hash_mismatch",
        ):
            await authorize_execution_plan(
                session,
                artifact_id=malformed.id,
                worker_key="customer-map-worker",
            )