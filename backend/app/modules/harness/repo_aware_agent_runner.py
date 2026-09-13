"""Repo-aware agent runners with fail-closed filesystem isolation.

Codex may receive shell read capability only inside an explicit permission profile:
all filesystem access is denied by default, the ephemeral runner directory is writable,
and the materialized repository snapshot is narrowed back to read-only. This avoids the
unsafe combination of enabling shell access under the legacy broad read-only sandbox.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.modules.harness.agent_runner import (
    CODEX_NO_TOOL_FEATURES,
    AgentRunnerError,
    AgentRunnerRegistry,
    AgentRunRequest,
    AgentRunResult,
    AntigravityCliRunner,
    CodexCliRunner,
)

_REPOSITORY_PERMISSION_PROFILE = "content_engine_repository"
# Shell is the single capability required for a Codex worker to inspect files in the
# snapshot. Every other optional/unsafe surface from the original runner remains off.
CODEX_REPOSITORY_DISABLED_FEATURES = tuple(
    feature for feature in CODEX_NO_TOOL_FEATURES if feature != "shell_tool"
)


def _toml_string(value: str) -> str:
    """JSON string syntax is a valid TOML basic string for these path values."""

    return json.dumps(value, ensure_ascii=False)


def _filesystem_profile_override(*, workdir: Path, repository_root: Path) -> str:
    entries = (
        (":root", "deny"),
        (":minimal", "read"),
        (str(workdir), "write"),
        (str(repository_root), "read"),
    )
    encoded = ",".join(
        f"{_toml_string(path)}={_toml_string(access)}" for path, access in entries
    )
    return f"permissions.{_REPOSITORY_PERMISSION_PROFILE}.filesystem={{{encoded}}}"


class RepoAwareCodexCliRunner(CodexCliRunner):
    """Codex runner that can inspect only an exact ephemeral repository snapshot."""

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        if request.repository is None:
            return await super().run(request)

        capability = await self.preflight()

        def argv(schema_path: Path, result_path: Path) -> list[str]:
            workdir = schema_path.parent
            repository_root = workdir / "repository"
            return [
                self.executable,
                "exec",
                "--model",
                request.model,
                "--json",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(result_path),
                *[
                    part
                    for feature in CODEX_REPOSITORY_DISABLED_FEATURES
                    for part in ("--disable", feature)
                ],
                "-c",
                'web_search="disabled"',
                "-c",
                'approval_policy="never"',
                "-c",
                f'default_permissions="{_REPOSITORY_PERMISSION_PROFILE}"',
                "-c",
                _filesystem_profile_override(
                    workdir=workdir,
                    repository_root=repository_root,
                ),
                "-c",
                f"permissions.{_REPOSITORY_PERMISSION_PROFILE}.network.enabled=false",
                "--skip-git-repo-check",
                "--ignore-user-config",
                "--ephemeral",
                "-",
            ]

        return await self._execute(
            request,
            runner_version=capability.version,
            argv_builder=argv,
        )


class RepoAwareAntigravityCliRunner(AntigravityCliRunner):
    """Fail closed until the actual Antigravity adapter proves scoped repo isolation."""

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        if request.repository is not None:
            raise AgentRunnerError("agent_repository_isolation_unproven")
        return await super().run(request)


def repo_aware_agent_runner_registry() -> AgentRunnerRegistry:
    """Registry for orchestration paths that may request exact repository context."""

    registry = AgentRunnerRegistry()
    registry.register("codex_cli", RepoAwareCodexCliRunner())
    registry.register("antigravity_cli", RepoAwareAntigravityCliRunner())
    return registry


__all__ = [
    "CODEX_REPOSITORY_DISABLED_FEATURES",
    "RepoAwareAntigravityCliRunner",
    "RepoAwareCodexCliRunner",
    "repo_aware_agent_runner_registry",
]
