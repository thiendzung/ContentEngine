from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from app.modules.harness.agent_runner import (
    CODEX_CLI_APPROVED_VERSION,
    AgentCapability,
    AgentRunnerError,
    AgentRunRequest,
)
from app.modules.harness.repo_aware_agent_runner import (
    CODEX_REPOSITORY_DISABLED_FEATURES,
    RepoAwareAntigravityCliRunner,
    RepoAwareCodexCliRunner,
)
from app.modules.harness.repository_snapshot import RepositorySnapshotSpec


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "ContentEngine Test")
    _git(root, "config", "user.email", "test@example.invalid")
    (root / "AGENTS.md").write_text("tracked contract\n", encoding="utf-8")
    (root / "backend").mkdir()
    (root / "backend" / "README.md").write_text("tracked backend\n", encoding="utf-8")
    _git(root, "add", "AGENTS.md", "backend/README.md")
    _git(root, "commit", "-m", "fixture")
    return root, _git(root, "rev-parse", "HEAD")


class FakeStdin:
    def write(self, data: bytes) -> None:
        self.data = data

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None


class FakeProcess:
    def __init__(self, *, stdout: bytes = b"", returncode: int = 0) -> None:
        self.stdin = FakeStdin()
        self.stdout = stdout
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.stdout, b""

    def kill(self) -> None:
        self.returncode = -9


@pytest.mark.asyncio
async def test_codex_runner_executes_inside_exact_scoped_tracked_snapshot(
    monkeypatch,
    tmp_path: Path,
) -> None:
    root, revision = _repo(tmp_path)
    (root / ".env").write_text("SECRET=must-not-cross\n", encoding="utf-8")
    (root / "private-local.txt").write_text("private\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("dirty working tree\n", encoding="utf-8")

    runner = RepoAwareCodexCliRunner()

    async def fake_preflight() -> AgentCapability:
        return AgentCapability(
            provider="codex_cli",
            executable="codex",
            version=CODEX_CLI_APPROVED_VERSION,
            authenticated=True,
            auth_mode="cached_session",
        )

    seen: dict[str, object] = {}

    async def fake_exec(*argv: str, **kwargs: Any) -> FakeProcess:
        cwd = Path(kwargs["cwd"])
        seen["cwd"] = cwd
        seen["argv"] = argv
        seen["tracked"] = (cwd / "AGENTS.md").read_text(encoding="utf-8")
        seen["backend"] = (cwd / "backend" / "README.md").read_text(encoding="utf-8")
        seen["env_exists"] = (cwd / ".env").exists()
        seen["private_exists"] = (cwd / "private-local.txt").exists()
        seen["git_exists"] = (cwd / ".git").exists()
        result_path = Path(argv[argv.index("--output-last-message") + 1])
        result_path.write_text(json.dumps({"ok": True}), encoding="utf-8")
        return FakeProcess()

    monkeypatch.setattr(runner, "preflight", fake_preflight)
    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    result = await runner.run(
        AgentRunRequest(
            provider="codex_cli",
            model="test-model",
            prompt="Inspect the repository contract and return JSON.",
            structured_output_schema={"type": "object"},
            working_context={"safe_ref": "fixture"},
            timeout=1.0,
            repository=RepositorySnapshotSpec(
                repository_root=str(root),
                revision=revision,
            ),
        )
    )

    assert result.structured_output == {"ok": True}
    assert result.repository_revision == revision
    assert result.repository_tree_hash is not None
    assert seen["tracked"] == "tracked contract\n"
    assert seen["backend"] == "tracked backend\n"
    assert seen["env_exists"] is False
    assert seen["private_exists"] is False
    assert seen["git_exists"] is False
    assert seen["cwd"] != root

    argv = seen["argv"]
    assert isinstance(argv, tuple)
    pairs = set(zip(argv, argv[1:], strict=False))
    assert "--sandbox" not in argv
    assert ("--disable", "shell_tool") not in pairs
    for feature in CODEX_REPOSITORY_DISABLED_FEATURES:
        assert ("--disable", feature) in pairs
    overrides = [argv[index + 1] for index, part in enumerate(argv[:-1]) if part == "-c"]
    assert 'approval_policy="never"' in overrides
    assert 'default_permissions="content_engine_repository"' in overrides
    filesystem = next(
        value
        for value in overrides
        if value.startswith("permissions.content_engine_repository.filesystem=")
    )
    assert '":root"="deny"' in filesystem
    assert '":minimal"="read"' in filesystem
    assert f'{json.dumps(str(seen["cwd"]))}="read"' in filesystem
    assert "permissions.content_engine_repository.network.enabled=false" in overrides
    assert set(_git(root, "status", "--porcelain").splitlines()) == {
        " M AGENTS.md",
        "?? .env",
        "?? private-local.txt",
    }


@pytest.mark.asyncio
async def test_invalid_repository_revision_fails_before_model_process(
    monkeypatch,
    tmp_path: Path,
) -> None:
    root, _revision = _repo(tmp_path)
    runner = RepoAwareCodexCliRunner()

    async def fake_preflight() -> AgentCapability:
        return AgentCapability(
            provider="codex_cli",
            executable="codex",
            version=CODEX_CLI_APPROVED_VERSION,
            authenticated=True,
            auth_mode="cached_session",
        )

    calls = 0

    async def fake_exec(*argv: str, **kwargs: Any) -> FakeProcess:
        nonlocal calls
        del argv, kwargs
        calls += 1
        return FakeProcess()

    monkeypatch.setattr(runner, "preflight", fake_preflight)
    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    with pytest.raises(AgentRunnerError, match="repository_revision_invalid"):
        await runner.run(
            AgentRunRequest(
                provider="codex_cli",
                model="test-model",
                prompt="Return JSON.",
                structured_output_schema={"type": "object"},
                working_context={"safe_ref": "fixture"},
                timeout=1.0,
                repository=RepositorySnapshotSpec(
                    repository_root=str(root),
                    revision="main",
                ),
            )
        )

    assert calls == 0


@pytest.mark.asyncio
async def test_antigravity_repository_access_fails_closed_until_isolation_is_proven(
    tmp_path: Path,
) -> None:
    root, revision = _repo(tmp_path)
    runner = RepoAwareAntigravityCliRunner()

    with pytest.raises(AgentRunnerError, match="agent_repository_isolation_unproven"):
        await runner.run(
            AgentRunRequest(
                provider="antigravity_cli",
                model="test-model",
                prompt="Return JSON.",
                structured_output_schema={"type": "object"},
                working_context={"safe_ref": "fixture"},
                timeout=1.0,
                repository=RepositorySnapshotSpec(
                    repository_root=str(root),
                    revision=revision,
                ),
            )
        )
