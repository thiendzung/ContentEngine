from __future__ import annotations

import pytest

from app.modules.system import preflight


@pytest.mark.asyncio
async def test_release_preflight_excludes_test_database_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready = preflight.PreflightCheck

    monkeypatch.setattr(
        preflight,
        "_local_database_target_check",
        lambda: ready("database_binding", "READY", "host=127.0.0.1"),
    )

    async def database_check() -> preflight.PreflightCheck:
        return ready("database", "READY", "database=contentengine")

    async def migration_check() -> preflight.PreflightCheck:
        return ready("migration", "READY", "revision=20260915_0034")

    async def codex_check() -> preflight.PreflightCheck:
        return ready("codex_cli", "READY", "version=approved; auth=cached")

    def forbidden_test_database_check() -> preflight.PreflightCheck:
        raise AssertionError("release preflight must not require test database")

    monkeypatch.setattr(preflight, "_database_check", database_check)
    monkeypatch.setattr(preflight, "_migration_check", migration_check)
    monkeypatch.setattr(preflight, "_codex_check", codex_check)
    monkeypatch.setattr(
        preflight,
        "_test_database_check",
        forbidden_test_database_check,
    )
    monkeypatch.setattr(
        preflight,
        "_antigravity_check",
        lambda: ready("antigravity_cli", "OPTIONAL", "optional"),
    )
    monkeypatch.setattr(
        preflight,
        "_postgres_tools_check",
        lambda: ready("postgres_tools", "READY", "available"),
    )

    result = await preflight.build_release_preflight()

    assert result["status"] == "READY"
    checks = result["checks"]
    assert isinstance(checks, list)
    keys = {check["key"] for check in checks if isinstance(check, dict)}
    assert "test_database" not in keys
    assert {"database_binding", "database", "migration", "codex_cli", "postgres_tools"} <= keys


@pytest.mark.asyncio
async def test_release_preflight_keeps_codex_as_required_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready = preflight.PreflightCheck

    monkeypatch.setattr(
        preflight,
        "_local_database_target_check",
        lambda: ready("database_binding", "READY", "host=127.0.0.1"),
    )

    async def database_check() -> preflight.PreflightCheck:
        return ready("database", "READY", "database=contentengine")

    async def migration_check() -> preflight.PreflightCheck:
        return ready("migration", "READY", "revision=20260915_0034")

    async def codex_check() -> preflight.PreflightCheck:
        return ready("codex_cli", "BLOCKED", "agent_executable_missing")

    monkeypatch.setattr(preflight, "_database_check", database_check)
    monkeypatch.setattr(preflight, "_migration_check", migration_check)
    monkeypatch.setattr(preflight, "_codex_check", codex_check)
    monkeypatch.setattr(
        preflight,
        "_antigravity_check",
        lambda: ready("antigravity_cli", "OPTIONAL", "optional"),
    )
    monkeypatch.setattr(
        preflight,
        "_postgres_tools_check",
        lambda: ready("postgres_tools", "READY", "available"),
    )

    result = await preflight.build_release_preflight()

    assert result["status"] == "BLOCKED"
    checks = result["checks"]
    assert isinstance(checks, list)
    codex = next(
        check
        for check in checks
        if isinstance(check, dict) and check["key"] == "codex_cli"
    )
    assert codex["status"] == "BLOCKED"
    assert codex["detail"] == "agent_executable_missing"


@pytest.mark.asyncio
async def test_codex_preflight_exposes_resolved_executable_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRunner:
        async def preflight(self):
            return type(
                "Capability",
                (),
                {
                    "executable": "/Applications/ChatGPT.app/Contents/Resources/codex",
                    "version": "codex-cli 0.155.0-alpha.16.3",
                    "auth_mode": "cached_session",
                },
            )()

    monkeypatch.setattr(preflight, "CodexCliRunner", FakeRunner)

    check = await preflight._codex_check()

    assert check.status == "READY"
    assert check.detail == (
        "executable=/Applications/ChatGPT.app/Contents/Resources/codex; "
        "version=codex-cli 0.155.0-alpha.16.3; auth=cached_session"
    )