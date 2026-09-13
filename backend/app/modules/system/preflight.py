from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.modules.harness.agent_runner import (
    AgentRunnerError,
    AntigravityCliRunner,
    CodexCliRunner,
)
from app.modules.system.test_database import (
    TestDatabasePreparationError,
    validate_test_database_target,
)


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    key: str
    status: str
    detail: str


async def _database_check() -> PreflightCheck:
    try:
        async with engine.connect() as connection:
            database_name = (
                await connection.execute(text("select current_database()"))
            ).scalar_one()
    except Exception:
        return PreflightCheck("database", "BLOCKED", "database_unavailable")
    return PreflightCheck("database", "READY", f"database={database_name}")


async def _migration_check() -> PreflightCheck:
    try:
        async with engine.connect() as connection:
            version = (
                await connection.execute(text("select version_num from alembic_version"))
            ).scalar_one_or_none()
    except Exception:
        return PreflightCheck("migration", "BLOCKED", "migration_state_unavailable")
    if not version:
        return PreflightCheck("migration", "BLOCKED", "migration_version_missing")
    return PreflightCheck("migration", "READY", f"revision={version}")


def _test_database_check() -> PreflightCheck:
    settings = get_settings()
    if not settings.test_database_url:
        return PreflightCheck("test_database", "BLOCKED", "test_database_url_required")
    try:
        target = validate_test_database_target(
            database_url=settings.database_url,
            test_database_url=settings.test_database_url,
        )
    except TestDatabasePreparationError as exc:
        return PreflightCheck("test_database", "BLOCKED", exc.code)
    return PreflightCheck("test_database", "READY", f"database={target.database}")


async def _agent_check(*, provider: str) -> PreflightCheck:
    if provider == "codex_cli":
        runner = CodexCliRunner()
        blocked_status = "BLOCKED"
    else:
        runner = AntigravityCliRunner()
        blocked_status = "OPTIONAL"
    try:
        capability = await runner.preflight()
    except AgentRunnerError as exc:
        return PreflightCheck(provider, blocked_status, exc.code)
    return PreflightCheck(
        provider,
        "READY",
        f"version={capability.version}; auth={capability.auth_mode}",
    )


def _postgres_tools_check() -> PreflightCheck:
    missing = [name for name in ("pg_dump", "pg_restore") if shutil.which(name) is None]
    if missing:
        return PreflightCheck(
            "postgres_tools",
            "BLOCKED",
            "missing=" + ",".join(missing),
        )
    return PreflightCheck("postgres_tools", "READY", "pg_dump+pg_restore")


async def build_operational_preflight() -> dict[str, object]:
    checks = [
        await _database_check(),
        await _migration_check(),
        _test_database_check(),
        await _agent_check(provider="codex_cli"),
        await _agent_check(provider="antigravity_cli"),
        _postgres_tools_check(),
    ]
    required = [check for check in checks if check.status != "OPTIONAL"]
    ready = all(check.status == "READY" for check in required)
    return {
        "status": "READY" if ready else "BLOCKED",
        "checks": [asdict(check) for check in checks],
    }
