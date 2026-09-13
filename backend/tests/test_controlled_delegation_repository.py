from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.modules.harness.agent_runner import (
    AgentCapability,
    AgentRunnerRegistry,
    AgentRunRequest,
    AgentRunResult,
)
from app.modules.harness.controlled_delegation import ControlledDelegationBridge
from app.modules.harness.models import ModelCall
from app.modules.harness.repository_snapshot import RepositorySnapshotSpec
from test_controlled_delegation import _fixture, _request, isolated_session


class RepoAwareFakeRunner:
    def __init__(self, revision: str, tree_hash: str) -> None:
        self.revision = revision
        self.tree_hash = tree_hash
        self.request: AgentRunRequest | None = None
        self.calls = 0

    async def preflight(self) -> AgentCapability:
        return AgentCapability(
            provider="antigravity_cli",
            executable="fake-worker",
            version="agy-test-1",
            authenticated=True,
            auth_mode="cached_session",
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.calls += 1
        self.request = request
        return AgentRunResult(
            provider=request.provider,
            model=request.model,
            runner_version="agy-test-1",
            structured_output={"ok": True},
            raw_output_hash="f" * 64,
            exit_code=0,
            usage=None,
            duration_ms=11,
            repository_revision=self.revision,
            repository_tree_hash=self.tree_hash,
        )


@pytest.mark.asyncio
async def test_controlled_delegation_propagates_repository_spec_and_persists_safe_provenance(
    tmp_path: Path,
) -> None:
    revision = "a" * 40
    tree_hash = "b" * 40
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    async with isolated_session() as session:
        fixture = await _fixture(session)
        runner = RepoAwareFakeRunner(revision, tree_hash)
        registry = AgentRunnerRegistry()
        registry.register("antigravity_cli", runner)
        request = replace(
            _request(fixture),
            repository=RepositorySnapshotSpec(
                repository_root=str(repo_root),
                revision=revision,
            ),
        )

        result = await ControlledDelegationBridge(registry).execute(
            session,
            request=request,
        )

        assert result.status == "completed"
        assert runner.calls == 1
        assert runner.request is not None
        assert runner.request.repository == request.repository
        call = await session.get(ModelCall, result.worker_model_call_id)
        assert call is not None
        assert call.runtime_metadata_json is not None
        assert call.runtime_metadata_json["repository_revision"] == revision
        assert call.runtime_metadata_json["repository_tree_hash"] == tree_hash
        assert str(repo_root) not in str(call.runtime_metadata_json)
