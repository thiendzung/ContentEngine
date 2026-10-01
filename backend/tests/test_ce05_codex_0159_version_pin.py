from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.modules.harness.agent_runner import (
    CODEX_NO_TOOL_FEATURES,
    CODEX_REQUIRED_EXEC_FLAGS,
    AgentRunnerError,
    CodexCliRunner,
    runner_versions_compatible,
)


class _VersionProcess:
    def __init__(self, *, stdout: bytes, exit_code: int = 0) -> None:
        self.stdout = stdout
        self.stderr = b""
        self.returncode = exit_code

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.stdout, self.stderr


def _feature_output() -> bytes:
    return b"\n".join(
        f"{feature} stable true".encode()
        for feature in CODEX_NO_TOOL_FEATURES
    )


@pytest.mark.asyncio
async def test_codex_patch_drift_is_allowed_when_capability_contract_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    async def fake_exec(*argv: str, **_kwargs: Any) -> _VersionProcess:
        calls.append(argv)
        if argv[1:] == ("--version",):
            return _VersionProcess(stdout=b"codex-cli 0.159.2")
        if argv[1:] == ("exec", "--help"):
            return _VersionProcess(
                stdout=" ".join(CODEX_REQUIRED_EXEC_FLAGS).encode()
            )
        if argv[1:] == ("features", "list"):
            return _VersionProcess(stdout=_feature_output())
        if argv[1:] == ("login", "status"):
            return _VersionProcess(stdout=b"Logged in using ChatGPT")
        pytest.fail(f"unexpected subprocess: {argv!r}")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/codex")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    capability = await CodexCliRunner().preflight()

    assert capability.version == "codex-cli 0.159.2"
    assert calls == [
        ("/usr/local/bin/codex", "--version"),
        ("/usr/local/bin/codex", "exec", "--help"),
        ("/usr/local/bin/codex", "features", "list"),
        ("/usr/local/bin/codex", "login", "status"),
    ]


@pytest.mark.asyncio
async def test_codex_missing_required_exec_flag_fails_before_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    async def fake_exec(*argv: str, **_kwargs: Any) -> _VersionProcess:
        calls.append(argv)
        if argv[1:] == ("--version",):
            return _VersionProcess(stdout=b"codex-cli 0.159.2")
        if argv[1:] == ("exec", "--help"):
            missing = [
                flag
                for flag in CODEX_REQUIRED_EXEC_FLAGS
                if flag != "--output-schema"
            ]
            return _VersionProcess(stdout=" ".join(missing).encode())
        pytest.fail(f"unexpected subprocess after capability failure: {argv!r}")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/codex")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    with pytest.raises(AgentRunnerError, match="agent_tool_disable_unsupported"):
        await CodexCliRunner().preflight()

    assert calls == [
        ("/usr/local/bin/codex", "--version"),
        ("/usr/local/bin/codex", "exec", "--help"),
    ]


def test_runner_version_policy_is_capability_family_for_codex_and_exact_elsewhere() -> None:
    assert runner_versions_compatible(
        provider="codex_cli",
        expected="codex-cli 0.159.0",
        observed="codex-cli 0.159.2",
    )
    assert not runner_versions_compatible(
        provider="codex_cli",
        expected="codex-cli 0.159.0",
        observed="not-codex 0.159.2",
    )
    assert runner_versions_compatible(
        provider="antigravity_cli",
        expected="agy-1",
        observed="agy-1",
    )
    assert not runner_versions_compatible(
        provider="antigravity_cli",
        expected="agy-1",
        observed="agy-2",
    )
