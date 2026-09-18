from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.modules.harness.agent_runner import (
    CODEX_CLI_APPROVED_VERSION,
    AgentRunnerError,
    CodexCliRunner,
)


class _VersionProcess:
    def __init__(self, *, stdout: bytes) -> None:
        self.stdout = stdout
        self.returncode = 0

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.stdout, b""


@pytest.mark.asyncio
async def test_codex_0155_alpha9_pin_rejects_previous_alpha2_6_before_capability_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    async def fake_exec(*argv: str, **_kwargs: Any) -> _VersionProcess:
        calls.append(argv)
        if argv[1:] == ("--version",):
            return _VersionProcess(stdout=b"codex-cli 0.155.0-alpha.2.6")
        pytest.fail(f"unexpected subprocess after version mismatch: {argv!r}")

    assert CODEX_CLI_APPROVED_VERSION == "codex-cli 0.155.0-alpha.9"
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/codex")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    with pytest.raises(AgentRunnerError, match="agent_runner_version_not_approved"):
        await CodexCliRunner().preflight()

    assert calls == [("codex", "--version")]
