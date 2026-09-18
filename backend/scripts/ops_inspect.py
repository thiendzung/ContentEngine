from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.recovery import database_fingerprint

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class OperationalInspectionError(RuntimeError):
    """Raised when O1 read-only inspection cannot prove a safe operational target."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _expected_migration_head() -> str | None:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()


def _database_identity(database_url: str) -> dict[str, object]:
    target = make_url(database_url)
    host = (target.host or "").lower()
    database = target.database or ""
    if target.get_backend_name() != "postgresql":
        raise OperationalInspectionError("operational_database_backend_unsupported")
    if host not in _LOCAL_HOSTS:
        raise OperationalInspectionError("operational_database_not_loopback")
    if not database:
        raise OperationalInspectionError("operational_database_name_missing")
    if "test" in database.lower() or "restore" in database.lower():
        raise OperationalInspectionError("operational_database_looks_disposable")
    return {
        "backend": target.get_backend_name(),
        "host": host,
        "port": target.port or 5432,
        "database": database,
    }


def _operational_repository_root() -> Path:
    configured = os.environ.get("CONTENTENGINE_OPERATIONAL_REPO")
    if not configured:
        return _repository_root()
    candidate = Path(configured).expanduser().resolve()
    if not candidate.is_dir():
        raise OperationalInspectionError("operational_repository_missing")
    return candidate


def _run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise OperationalInspectionError("git_state_unavailable")
    return result.stdout.strip()


def _repository_state(root: Path) -> dict[str, object]:
    return {
        "head": _run_git(root, "rev-parse", "HEAD"),
        "clean": _run_git(root, "status", "--porcelain") == "",
    }


async def _database_snapshot(database_url: str) -> dict[str, object]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "select current_database(), current_user, "
                        "inet_server_addr()::text, inet_server_port()"
                    )
                )
            ).one()
            revision = (
                await connection.execute(text("select version_num from alembic_version"))
            ).scalar_one_or_none()
            server_version = (
                await connection.execute(text("show server_version"))
            ).scalar_one()
        fingerprint = await database_fingerprint(engine)
    except Exception as exc:
        raise OperationalInspectionError("operational_database_inspection_failed") from exc
    finally:
        await engine.dispose()

    return {
        "current_database": str(row[0]),
        "current_user": str(row[1]),
        "server_address": None if row[2] is None else str(row[2]),
        "server_port": None if row[3] is None else int(row[3]),
        "server_version": str(server_version),
        "migration_revision": None if revision is None else str(revision),
        "fingerprint": fingerprint.to_dict(),
    }


async def build_operational_inspection() -> dict[str, object]:
    settings = get_settings()
    if settings.app_env.strip().lower() == "test":
        raise OperationalInspectionError("test_environment_not_operational")

    identity = _database_identity(settings.database_url)
    inspection_repository = _repository_state(_repository_root())
    operational_repository = _repository_state(_operational_repository_root())
    expected_revision = _expected_migration_head()
    database = await _database_snapshot(settings.database_url)

    blockers: list[str] = []
    if not inspection_repository["clean"]:
        blockers.append("inspection_repository_worktree_dirty")
    if not operational_repository["clean"]:
        blockers.append("operational_repository_worktree_dirty")
    if database["current_database"] != identity["database"]:
        blockers.append("database_identity_mismatch")
    if expected_revision is None:
        blockers.append("code_migration_head_missing")
    elif database["migration_revision"] != expected_revision:
        blockers.append("migration_revision_mismatch")

    return {
        "status": "READY" if not blockers else "BLOCKED",
        "mode": "read_only",
        "application": {
            "environment": settings.app_env,
            "version": settings.app_version,
        },
        "inspection_repository": inspection_repository,
        "operational_repository": operational_repository,
        "operational_repository_matches_inspection": (
            operational_repository["head"] == inspection_repository["head"]
        ),
        "configured_database": identity,
        "database": database,
        "code_migration_head": expected_revision,
        "blockers": blockers,
    }


async def _main() -> int:
    try:
        result = await build_operational_inspection()
    except OperationalInspectionError as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "read_only",
                    "blockers": [exc.code],
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["status"] == "READY" else 2


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
