from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.database import engine
from app.modules.harness.agent_runner import AgentRunnerError, CodexCliRunner
from app.modules.system.test_database import (
    TestDatabasePreparationError,
    validate_test_database_target,
)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    key: str
    status: str
    detail: str


def _local_database_target_check() -> PreflightCheck:
    settings = get_settings()
    target = make_url(settings.database_url)
    host = (target.host or "").lower()
    if host not in _LOCAL_HOSTS:
        return PreflightCheck("database_binding", "BLOCKED", "database_not_loopback")
    return PreflightCheck("database_binding", "READY", f"host={host}")


async def _database_check() -> PreflightCheck:
    try:
        async with engine.connect() as connection:
            database_name = (
                await connection.execute(text("select current_database()"))
            ).scalar_one()
    except Exception:
        return PreflightCheck("database", "BLOCKED", "database_unavailable")
    return PreflightCheck("database", "READY", f"database={database_name}")


def _expected_migration_head() -> str | None:
    backend_root = Path(__file__).resolve().parents[3]
    config = Config(str(backend_root / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()


async def _migration_check() -> PreflightCheck:
    try:
        expected = _expected_migration_head()
        async with engine.connect() as connection:
            current = (
                await connection.execute(text("select version_num from alembic_version"))
            ).scalar_one_or_none()
    except Exception:
        return PreflightCheck("migration", "BLOCKED", "migration_state_unavailable")
    if not current or not expected:
        return PreflightCheck("migration", "BLOCKED", "migration_version_missing")
    if str(current) != expected:
        return PreflightCheck(
            "migration",
            "BLOCKED",
            f"revision={current}; expected={expected}",
        )
    return PreflightCheck("migration", "READY", f"revision={current}")


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


async def _codex_check() -> PreflightCheck:
    try:
        capability = await CodexCliRunner().preflight()
    except AgentRunnerError as exc:
        return PreflightCheck("codex_cli", "BLOCKED", exc.code)
    return PreflightCheck(
        "codex_cli",
        "READY",
        f"version={capability.version}; auth={capability.auth_mode}",
    )


def _antigravity_check() -> PreflightCheck:
    return PreflightCheck(
        "antigravity_cli",
        "OPTIONAL",
        "agent_repository_isolation_unproven",
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
        _local_database_target_check(),
        await _database_check(),
        await _migration_check(),
        _test_database_check(),
        await _codex_check(),
        _antigravity_check(),
        _postgres_tools_check(),
    ]
    required = [check for check in checks if check.status != "OPTIONAL"]
    ready = all(check.status == "READY" for check in required)
    return {
        "status": "READY" if ready else "BLOCKED",
        "checks": [asdict(check) for check in checks],
    }
