from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import cast

import pytest
import test_ce05_angle_approval as angle_fixture_module
from sqlalchemy import select
from test_ce05_review_revise import _source_draft, isolated_session
from test_ce05_writer import _draft_payload

from app.modules.content_engine.journal.review_revise_orchestration import (
    REVIEW_REVISE_EN_TASK_KEY,
    ReviewReviseEnOrchestrationAdapter,
    ReviewReviseEnRequest,
    prepare_review_revise_en_orchestration,
    run_review_revise_en_orchestration,
)
from app.modules.content_engine.models import LocaleVariant, SettingsSnapshot
from app.modules.harness.agent_runner import (
    CODEX_CLI_APPROVED_VERSION,
    AgentCapability,
    AgentRunnerRegistry,
    AgentRunRequest,
    AgentRunResult,
)
from app.modules.harness.bounded_orchestration import OrchestrationOutcome
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.models import ContentRun, ModelCall, StepRun
from app.modules.harness.persistence import transition_run
from app.modules.harness.repository_snapshot import RepositorySnapshotSpec
from app.modules.system.settings_service import settings_hash


class OrchestrationRunner:
    def __init__(
        self,
        worker_outputs: list[object],
        *,
        plan_task: str = REVIEW_REVISE_EN_TASK_KEY,
    ) -> None:
        self.worker_outputs = worker_outputs
        self.plan_task = plan_task
        self.requests: list[AgentRunRequest] = []
        self.coordinator_calls = 0
        self.worker_calls = 0

    async def preflight(self) -> AgentCapability:
        return AgentCapability(
            provider="codex_cli",
            executable="codex",
            version=CODEX_CLI_APPROVED_VERSION,
            authenticated=True,
            auth_mode="test",
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.requests.append(request)
        required = request.structured_output_schema.get("required", [])
        if isinstance(required, list) and "task_key" in required:
            self.coordinator_calls += 1
            output: object = {
                "schema_version": 1,
                "decision": "delegate",
                "task_key": self.plan_task,
                "worker_kind": "subagent",
                "worker_key": "review-revise-en",
                "provider": "codex_cli",
                "model": "test-model",
            }
        else:
            self.worker_calls += 1
            output = self.worker_outputs[min(self.worker_calls - 1, len(self.worker_outputs) - 1)]
        return AgentRunResult(
            provider=request.provider,
            model=request.model,
            runner_version=CODEX_CLI_APPROVED_VERSION,
            structured_output=output,
            raw_output_hash="d" * 64,
            exit_code=0,
            usage={"input_tokens": 10, "output_tokens": 20},
            duration_ms=7,
            session_id=f"test-{len(self.requests)}",
            repository_revision=(request.repository.revision if request.repository else None),
            repository_tree_hash="e" * 40 if request.repository else None,
        )


def _settings(*, antigravity: bool = False) -> dict[str, object]:
    provider = "antigravity_cli" if antigravity else "codex_cli"
    worker_kind = "application" if antigravity else "subagent"
    worker_key = "antigravity" if antigravity else "review-revise-en"
    runner_version = "agy-test" if antigravity else CODEX_CLI_APPROVED_VERSION
    return {
        "models": {"angle": {"route": "agent_angle"}},
        "model_routes": {
            "agent_angle": {"provider": "codex_cli", "model": "test-model"}
        },
        "delegation": {
            "enabled": True,
            "routes": {
                REVIEW_REVISE_EN_TASK_KEY: {
                    "worker_kind": worker_kind,
                    "worker_key": worker_key,
                    "provider": provider,
                    "model": "test-model",
                    "runner_version": runner_version,
                }
            },
        },
    }


async def _source_draft_with_settings(
    session,
    monkeypatch: pytest.MonkeyPatch,
    *,
    locale: str,
    unresolved: bool,
    antigravity: bool = False,
):
    settings = _settings(antigravity=antigravity)

    async def _run_and_step(session_, *, project, content_case):
        variant = LocaleVariant(
            content_case_id=content_case.id,
            locale="en",
            content_role="primary",
            primary_question="How should a buyer evaluate an artwork price?",
            primary_intent="evaluate",
        )
        snapshot = SettingsSnapshot(
            project_id=project.id,
            resolved_settings_json=copy.deepcopy(settings),
            source_version_refs_json=["test:t05.22e"],
            content_hash=settings_hash(settings),
        )
        session_.add_all([variant, snapshot])
        await session_.flush()
        run = ContentRun(
            project_id=project.id,
            content_case_id=content_case.id,
            locale_variant_id=variant.id,
            run_mode="create",
            status="running",
            current_step="journal_input_bundle",
            settings_snapshot_id=snapshot.id,
            started_at=datetime.now(UTC),
        )
        session_.add(run)
        await session_.flush()
        step = StepRun(
            run_id=run.id,
            step_key="journal_input_bundle",
            attempt=1,
            status="running",
            started_at=datetime.now(UTC),
        )
        session_.add(step)
        await session_.flush()
        return run, step

    monkeypatch.setattr(angle_fixture_module, "_run_and_step", _run_and_step)
    return await _source_draft(session, locale=locale, unresolved=unresolved)


def _request(fixture, source) -> ReviewReviseEnRequest:
    return ReviewReviseEnRequest(
        writer_run_id=fixture.writer_input.writer_run.id,
        source_draft_artifact_id=source.artifact.id,
        source_draft_version=source.artifact.version,
        source_draft_hash=source.artifact.content_hash,
        outline_artifact_id=fixture.outline_result.artifact.id,
        outline_artifact_version=fixture.outline_result.artifact.version,
        outline_artifact_hash=fixture.outline_result.artifact.content_hash,
        repository=RepositorySnapshotSpec(
            repository_root="/tmp/contentengine-test-repository",
            revision="a" * 40,
        ),
    )


def _registry(runner: OrchestrationRunner) -> AgentRunnerRegistry:
    registry = AgentRunnerRegistry()
    registry.register("codex_cli", runner)
    return registry


@pytest.mark.asyncio
async def test_review_revise_en_runs_through_coordinator_and_controlled_delegation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
        )
        revised = _draft_payload(fixture.writer_input, "en")
        request = _request(fixture, source)
        runner = OrchestrationRunner([revised])

        result = await run_review_revise_en_orchestration(
            session,
            request=request,
            runner_registry=_registry(runner),
        )

        assert result.orchestration.final_outcome == OrchestrationOutcome.COMPLETE
        assert result.revised_draft_artifact_id is not None
        assert runner.coordinator_calls == 1
        assert runner.worker_calls == 1
        assert len(result.orchestration.cycles) == 1
        assert result.orchestration.cycles[0].attempt == 1

        calls = list(
            (
                await session.scalars(
                    select(ModelCall).where(ModelCall.run_id == fixture.writer_input.writer_run.id)
                )
            ).all()
        )
        coordinator = next(call for call in calls if call.task_key == "delegation_plan")
        worker = next(call for call in calls if call.task_key == REVIEW_REVISE_EN_TASK_KEY)
        assert coordinator.runtime_metadata_json is not None
        assert coordinator.runtime_metadata_json["repository_revision"] == "a" * 40
        assert coordinator.runtime_metadata_json["repository_tree_hash"] == "e" * 40
        assert worker.runtime_metadata_json is not None
        assert worker.runtime_metadata_json["repository_revision"] == "a" * 40
        assert worker.runtime_metadata_json["repository_tree_hash"] == "e" * 40


@pytest.mark.asyncio
async def test_review_revise_en_retry_uses_new_attempt_and_dedupe_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
        )
        invalid = _draft_payload(fixture.writer_input, "en")
        cast(list[str], invalid["unresolved_factual_claims"]).append("still unsupported")
        revised = _draft_payload(fixture.writer_input, "en")
        request = _request(fixture, source)
        runner = OrchestrationRunner([invalid, revised])

        result = await run_review_revise_en_orchestration(
            session,
            request=request,
            runner_registry=_registry(runner),
        )

        assert result.orchestration.final_outcome == OrchestrationOutcome.COMPLETE
        assert [cycle.attempt for cycle in result.orchestration.cycles] == [1, 2]
        first_dedupe = result.orchestration.cycles[0].dedupe_key
        second_dedupe = result.orchestration.cycles[1].dedupe_key
        assert first_dedupe != second_dedupe
        assert first_dedupe.split(":")[3] != second_dedupe.split(":")[3]
        assert runner.coordinator_calls == 1
        assert runner.worker_calls == 2
        executions = list(
            (
                await session.scalars(
                    select(DelegationExecution)
                    .where(DelegationExecution.run_id == fixture.writer_input.writer_run.id)
                    .order_by(DelegationExecution.attempt)
                )
            ).all()
        )
        assert [item.attempt for item in executions] == [1, 2]


@pytest.mark.asyncio
async def test_review_revise_en_retry_budget_exhaustion_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
        )
        invalid = _draft_payload(fixture.writer_input, "en")
        cast(list[str], invalid["unresolved_factual_claims"]).append("still unsupported")
        request = _request(fixture, source)
        runner = OrchestrationRunner([invalid, copy.deepcopy(invalid)])

        result = await run_review_revise_en_orchestration(
            session,
            request=request,
            runner_registry=_registry(runner),
        )

        assert result.orchestration.final_outcome == OrchestrationOutcome.BLOCKED
        assert [cycle.attempt for cycle in result.orchestration.cycles] == [1, 2]
        assert runner.worker_calls == 2


@pytest.mark.asyncio
async def test_review_revise_en_completed_replay_has_zero_new_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
        )
        revised = _draft_payload(fixture.writer_input, "en")
        request = _request(fixture, source)
        runner = OrchestrationRunner([revised])
        registry = _registry(runner)

        first = await run_review_revise_en_orchestration(
            session,
            request=request,
            runner_registry=registry,
        )
        request_count = len(runner.requests)
        second = await run_review_revise_en_orchestration(
            session,
            request=request,
            runner_registry=registry,
        )

        assert first.revised_draft_artifact_id == second.revised_draft_artifact_id
        assert second.orchestration.final_outcome == OrchestrationOutcome.COMPLETE
        assert second.orchestration.cycles == ()
        assert len(runner.requests) == request_count


@pytest.mark.asyncio
async def test_review_revise_en_wrong_plan_is_denied_before_worker_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
        )
        request = _request(fixture, source)
        runner = OrchestrationRunner(
            [_draft_payload(fixture.writer_input, "en")],
            plan_task="review_revise_vi",
        )

        result = await run_review_revise_en_orchestration(
            session,
            request=request,
            runner_registry=_registry(runner),
        )

        assert result.orchestration.final_outcome == OrchestrationOutcome.BLOCKED
        assert result.orchestration.error_code == "review_revise_action_not_allowed"
        assert runner.coordinator_calls == 1
        assert runner.worker_calls == 0


@pytest.mark.asyncio
async def test_review_revise_en_stale_state_is_denied_before_worker_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
        )
        request = _request(fixture, source)
        runner = OrchestrationRunner([_draft_payload(fixture.writer_input, "en")])
        prepared = await prepare_review_revise_en_orchestration(session, request=request)
        adapter = ReviewReviseEnOrchestrationAdapter(
            session,
            prepared=prepared,
            runner_registry=_registry(runner),
        )
        observation = await adapter.observe()
        plan = await adapter.plan(observation)
        prepared.step.output_artifact_refs_json = ["stale-marker"]
        await session.flush()

        decision = await adapter.policy_check(observation, plan)

        assert decision.allowed is False
        assert decision.error_code == "review_revise_state_version_stale"
        assert runner.coordinator_calls == 1
        assert runner.worker_calls == 0


@pytest.mark.asyncio
async def test_review_revise_en_human_gate_waits_without_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
        )
        run = fixture.writer_input.writer_run
        assert run.status == "pending"
        await transition_run(session, run_id=run.id, status="running")
        run.current_step = "outline"
        await session.flush()
        await transition_run(session, run_id=run.id, status="waiting_approval")
        request = _request(fixture, source)
        runner = OrchestrationRunner([_draft_payload(fixture.writer_input, "en")])

        result = await run_review_revise_en_orchestration(
            session,
            request=request,
            runner_registry=_registry(runner),
        )

        assert result.orchestration.final_outcome == OrchestrationOutcome.WAIT_HUMAN
        assert result.orchestration.human_gate == "outline"
        assert runner.requests == []


@pytest.mark.asyncio
async def test_review_revise_en_antigravity_route_remains_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft_with_settings(
            session,
            monkeypatch,
            locale="en",
            unresolved=True,
            antigravity=True,
        )
        request = _request(fixture, source)
        runner = OrchestrationRunner([_draft_payload(fixture.writer_input, "en")])

        result = await run_review_revise_en_orchestration(
            session,
            request=request,
            runner_registry=_registry(runner),
        )

        assert result.orchestration.final_outcome == OrchestrationOutcome.BLOCKED
        assert result.orchestration.error_code == "agent_repository_isolation_unproven"
        assert runner.coordinator_calls == 1
        assert runner.worker_calls == 0
