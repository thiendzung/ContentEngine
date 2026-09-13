from __future__ import annotations

import pytest
from test_ce05_review_console import isolated_session
from test_controlled_delegation import FakeRunner, _fixture, _request

from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.controlled_delegation import ControlledDelegationBridge
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.models import Artifact, ModelCall


@pytest.mark.asyncio
async def test_completed_delegation_replay_restores_durable_worker_output() -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session)
        runner = FakeRunner()
        registry = AgentRunnerRegistry()
        registry.register("antigravity_cli", runner)
        bridge = ControlledDelegationBridge(registry)

        first = await bridge.execute(session, request=_request(fixture))
        assert first.result_artifact_id is not None
        execution = await session.get(DelegationExecution, first.execution_id)
        assert execution is not None
        assert execution.result_artifact_id == first.result_artifact_id
        artifact = await session.get(Artifact, first.result_artifact_id)
        assert artifact is not None
        assert artifact.content_json is not None
        assert artifact.content_json["structured_output"] == {"ok": True}
        call = await session.get(ModelCall, first.worker_model_call_id)
        assert call is not None
        assert call.result_artifact_id == artifact.id

        replay = await bridge.execute(session, request=_request(fixture))

        assert replay.replayed is True
        assert replay.execution_id == first.execution_id
        assert replay.worker_model_call_id == first.worker_model_call_id
        assert replay.result_artifact_id == first.result_artifact_id
        assert replay.structured_output == {"ok": True}
        assert replay.raw_output_hash == "f" * 64
        assert runner.calls == 1
