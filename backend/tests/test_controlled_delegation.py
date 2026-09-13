from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import func, select
from test_ce05_review_console import _approved_fixture, isolated_session

from app.modules.content_engine.journal.production_board import list_production_board_cases
from app.modules.harness.agent_runner import (
    CODEX_CLI_APPROVED_VERSION,
    AgentCapability,
    AgentRunRequest,
    AgentRunResult,
    AgentRunnerError,
    AgentRunnerRegistry,
)
from app.modules.harness.controlled_delegation import (
    COORDINATOR_TASK_KEY,
    ControlledDelegationBridge,
    ControlledDelegationError,
    ControlledDelegationRequest,
    persist_delegation_plan_artifact,
)
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.models import ContentRun, ModelCall, StepRun
from app.modules.harness.runtime import (
    ContextInputs,
    ModelCandidate,
    ModelResponse,
    build_context_manifest,
    complete_model_call,
    start_model_call,
)
from app.modules.system.settings_service import create_settings_snapshot


@dataclass
class ControlledFixture:
    run: ContentRun
    step: StepRun
    coordinator_call: ModelCall
    worker_context_manifest_id: UUID


class FakeRunner:
    def __init__(
        self,
        *,
        provider: str = "antigravity_cli",
        version: str = "agy-test-1",
        fail_code: str | None = None,
    ) -> None:
        self.provider = provider
        self.version = version
        self.fail_code = fail_code
        self.calls = 0

    async def preflight(self) -> AgentCapability:
        return AgentCapability(
            provider=self.provider,
            executable="fake-worker",
            version=self.version,
            authenticated=True,
            auth_mode="cached_session",
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.calls += 1
        if self.fail_code is not None:
            raise AgentRunnerError(self.fail_code)
        return AgentRunResult(
            provider=request.provider,
            model=request.model,
            runner_version=self.version,
            structured_output={"ok": True},
            raw_output_hash="f" * 64,
            exit_code=0,
            usage={"input_tokens": 10, "output_tokens": 4},
            duration_ms=17,
            session_id="fake-session-001",
        )


async def _fixture(
    session,
    *,
    plan_worker_key: str = "antigravity",
    route_worker_key: str = "antigravity",
    runner_version: str = "agy-test-1",
) -> ControlledFixture:
    base = await _approved_fixture(session)
    source = base.writer_runs["en"]
    snapshot = await create_settings_snapshot(
        session,
        project_id=source.project_id,
        resolved_settings={
            "delegation": {
                "enabled": True,
                "routes": {
                    "journal_writer_en": {
                        "worker_kind": "application",
                        "worker_key": route_worker_key,
                        "provider": "antigravity_cli",
                        "model": "worker-test-model",
                        "runner_version": runner_version,
                    }
                },
            }
        },
        source_version_refs=["controlled-delegation-test"],
    )
    run = ContentRun(
        project_id=source.project_id,
        content_case_id=source.content_case_id,
        locale_variant_id=source.locale_variant_id,
        content_item_id=source.content_item_id,
        run_mode="update",
        status="running",
        current_step="delegation_control",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    step = StepRun(
        run_id=run.id,
        step_key="delegation_control",
        attempt=1,
        status="running",
        input_artifact_refs_json=[],
        output_artifact_refs_json=[],
        started_at=datetime.now(UTC),
    )
    session.add(step)
    await session.flush()

    coordinator_manifest = await build_context_manifest(
        session,
        run_id=run.id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version="delegation-plan:v1",
            recipe_version="delegation-plan:v1",
        ),
    )
    coordinator_call = await start_model_call(
        session,
        run_id=run.id,
        step_run_id=step.id,
        context_manifest_id=coordinator_manifest.id,
        task_key=COORDINATOR_TASK_KEY,
        route=ModelCandidate(provider="codex_cli", model="gpt-5.6-luna"),
        purpose="Choose one bounded delegated worker",
        prompt_version="delegation-plan:v1",
    )
    plan = await persist_delegation_plan_artifact(
        session,
        run_id=run.id,
        step_run_id=step.id,
        plan={
            "schema_version": 1,
            "decision": "delegate",
            "task_key": "journal_writer_en",
            "worker_kind": "application",
            "worker_key": plan_worker_key,
            "provider": "antigravity_cli",
            "model": "worker-test-model",
        },
    )
    await complete_model_call(
        session,
        call_id=coordinator_call.id,
        response=ModelResponse(content="delegation plan", finish_reason="stop"),
        result_artifact_id=plan.id,
        runtime_metadata={"runner_version": CODEX_CLI_APPROVED_VERSION},
    )
    worker_manifest = await build_context_manifest(
        session,
        run_id=run.id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version="worker:v1",
            recipe_version="worker:v1",
        ),
    )
    return ControlledFixture(
        run=run,
        step=step,
        coordinator_call=coordinator_call,
        worker_context_manifest_id=worker_manifest.id,
    )


def _request(fixture: ControlledFixture) -> ControlledDelegationRequest:
    return ControlledDelegationRequest(
        run_id=fixture.run.id,
        step_run_id=fixture.step.id,
        coordinator_model_call_id=fixture.coordinator_call.id,
        worker_context_manifest_id=fixture.worker_context_manifest_id,
        prompt_version="worker:v1",
        prompt="Return the bounded JSON result.",
        structured_output_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["ok"],
            "properties": {"ok": {"type": "boolean"}},
        },
        working_context={"safe_ref": "fixture"},
        purpose="Execute one approved delegated worker",
        dedupe_key=f"controlled:{fixture.run.id}:journal-writer-en:1",
    )


@pytest.mark.asyncio
async def test_controlled_delegation_executes_once_and_replays_without_rerun() -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session)
        runner = FakeRunner()
        registry = AgentRunnerRegistry()
        registry.register("antigravity_cli", runner)
        bridge = ControlledDelegationBridge(registry)

        first = await bridge.execute(session, request=_request(fixture))
        assert first.status == "completed"
        assert first.replayed is False
        assert first.structured_output == {"ok": True}
        assert runner.calls == 1

        execution = await session.get(DelegationExecution, first.execution_id)
        assert execution is not None
        assert execution.coordinator_model_call_id == fixture.coordinator_call.id
        assert execution.decision_artifact_id == fixture.coordinator_call.result_artifact_id
        assert execution.worker_model_call_id == first.worker_model_call_id
        assert execution.worker_key == "antigravity"
        assert execution.external_execution_id == "fake-session-001"

        call = await session.get(ModelCall, first.worker_model_call_id)
        assert call is not None
        assert call.provider == "antigravity_cli"
        assert call.model == "worker-test-model"
        assert call.status == "completed"
        assert call.runtime_metadata_json is not None
        assert call.runtime_metadata_json["delegation_execution_id"] == str(execution.id)

        replay = await bridge.execute(session, request=_request(fixture))
        assert replay.replayed is True
        assert replay.execution_id == first.execution_id
        assert runner.calls == 1

        rows = await list_production_board_cases(session)
        row = next(item for item in rows if item.id == fixture.run.content_case_id)
        delegated = [event for event in row.execution_chain if event.execution_id == execution.id]
        assert len(delegated) == 1
        assert delegated[0].provider == "antigravity_cli"
        assert delegated[0].model == "worker-test-model"
        assert not any(
            event.kind == "model" and event.provider == "antigravity_cli"
            for event in row.execution_chain
        )


@pytest.mark.asyncio
async def test_controlled_delegation_plan_must_match_immutable_route() -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, plan_worker_key="rogue-worker")
        runner = FakeRunner()
        registry = AgentRunnerRegistry()
        registry.register("antigravity_cli", runner)

        with pytest.raises(ControlledDelegationError, match="delegation_plan_route_mismatch"):
            await ControlledDelegationBridge(registry).execute(
                session,
                request=_request(fixture),
            )
        count = int(
            await session.scalar(select(func.count()).select_from(DelegationExecution)) or 0
        )
        assert count == 0
        assert runner.calls == 0


@pytest.mark.asyncio
async def test_controlled_delegation_runner_version_mismatch_is_persisted_failure() -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, runner_version="agy-approved")
        runner = FakeRunner(version="agy-other")
        registry = AgentRunnerRegistry()
        registry.register("antigravity_cli", runner)

        with pytest.raises(
            ControlledDelegationError,
            match="delegation_runner_identity_mismatch",
        ):
            await ControlledDelegationBridge(registry).execute(
                session,
                request=_request(fixture),
            )
        execution = await session.scalar(select(DelegationExecution))
        assert execution is not None
        assert execution.status == "failed"
        assert execution.error_class == "delegation_runner_identity_mismatch"
        assert execution.worker_model_call_id is None
        assert runner.calls == 0


@pytest.mark.asyncio
async def test_controlled_delegation_worker_failure_closes_both_records() -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session)
        runner = FakeRunner(fail_code="worker_unavailable")
        registry = AgentRunnerRegistry()
        registry.register("antigravity_cli", runner)

        with pytest.raises(ControlledDelegationError, match="worker_unavailable"):
            await ControlledDelegationBridge(registry).execute(
                session,
                request=_request(fixture),
            )
        execution = await session.scalar(select(DelegationExecution))
        assert execution is not None
        assert execution.status == "failed"
        assert execution.error_class == "worker_unavailable"
        assert execution.worker_model_call_id is not None
        call = await session.get(ModelCall, execution.worker_model_call_id)
        assert call is not None
        assert call.status == "failed"
        assert call.error_class == "worker_unavailable"


@pytest.mark.asyncio
async def test_delegation_plan_rejects_free_form_reasoning_fields() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        source = fixture.writer_runs["en"]
        with pytest.raises(
            ControlledDelegationError,
            match="delegation_plan_contains_unapproved_fields",
        ):
            await persist_delegation_plan_artifact(
                session,
                run_id=source.id,
                step_run_id=None,
                plan={
                    "schema_version": 1,
                    "decision": "delegate",
                    "task_key": "journal_writer_en",
                    "worker_kind": "application",
                    "worker_key": "antigravity",
                    "provider": "antigravity_cli",
                    "model": "worker-test-model",
                    "reasoning": "must never be persisted",
                },
            )
