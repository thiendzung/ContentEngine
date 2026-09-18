from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.postgres_tools import postgres_tool_capability, postgres_tool_command
from app.modules.system.recovery import (
    DatabaseFingerprint,
    RecoverySafetyError,
    database_fingerprint,
    validate_operational_database_source,
)


class BackupSafetyError(RuntimeError):
    """Raised when the requested backup destination is unsafe."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _backup_dir() -> Path:
    configured = os.environ.get("CONTENTENGINE_BACKUP_DIR")
    if configured:
        candidate = Path(configured).expanduser().resolve()
    else:
        candidate = (Path.home() / ".local" / "share" / "contentengine" / "backups").resolve()

    repository_root = _repository_root()
    if candidate == repository_root or repository_root in candidate.parents:
        raise BackupSafetyError("backup_directory_inside_repository")
    return candidate


def _pg_connection_args(url: URL, *, container_mode: bool) -> tuple[list[str], dict[str, str]]:
    args: list[str] = []
    if not container_mode and url.host:
        args.extend(["--host", url.host])
    if not container_mode and url.port:
        args.extend(["--port", str(url.port)])
    if url.username:
        args.extend(["--username", url.username])
    if url.database:
        args.extend(["--dbname", url.database])
    env = os.environ.copy()
    if not container_mode and url.password:
        env["PGPASSWORD"] = url.password
    return args, env


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _source_state(database_url: str) -> tuple[str, DatabaseFingerprint]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            revision = (
                await connection.execute(text("select version_num from alembic_version"))
            ).scalar_one_or_none()
        if revision is None:
            raise BackupSafetyError("source_migration_revision_missing")
        fingerprint = await database_fingerprint(engine)
    except BackupSafetyError:
        raise
    except Exception as exc:
        raise BackupSafetyError("source_state_failed") from exc
    finally:
        await engine.dispose()
    return str(revision), fingerprint


async def _main() -> int:
    capability = postgres_tool_capability()
    if capability is None:
        print("BACKUP: BLOCKED (pg_dump_unavailable)")
        return 2

    try:
        backup_dir = _backup_dir()
    except BackupSafetyError as exc:
        print(f"BACKUP: BLOCKED ({exc.code})")
        return 2

    settings = get_settings()
    if settings.app_env.strip().lower() == "test":
        print("BACKUP: BLOCKED (test_environment_not_operational)")
        return 2
    try:
        source_url = validate_operational_database_source(settings.database_url)
    except RecoverySafetyError as exc:
        print(f"BACKUP: BLOCKED ({exc.code})")
        return 2

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    stem = f"contentengine-{source_url.database}-{stamp}"
    dump_path = backup_dir / f"{stem}.dump"
    manifest_path = backup_dir / f"{stem}.json"

    try:
        source_revision_before, fingerprint_before = await _source_state(
            settings.database_url
        )
    except BackupSafetyError as exc:
        print(f"BACKUP: BLOCKED ({exc.code})")
        return 2

    container_mode = capability.mode == "container"
    connection_args, env = _pg_connection_args(source_url, container_mode=container_mode)
    command = [
        *postgres_tool_command("pg_dump"),
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        *connection_args,
    ]
    with dump_path.open("wb") as dump_handle:
        result = subprocess.run(
            command,
            env=env,
            stdout=dump_handle,
            stderr=subprocess.PIPE,
            check=False,
        )
    if result.returncode != 0 or not dump_path.is_file() or dump_path.stat().st_size == 0:
        dump_path.unlink(missing_ok=True)
        print("BACKUP: BLOCKED (pg_dump_failed)")
        return 2

    try:
        source_revision_after, fingerprint_after = await _source_state(
            settings.database_url
        )
    except BackupSafetyError as exc:
        dump_path.unlink(missing_ok=True)
        print(f"BACKUP: BLOCKED ({exc.code})")
        return 2
    if (
        source_revision_after != source_revision_before
        or fingerprint_after != fingerprint_before
    ):
        dump_path.unlink(missing_ok=True)
        print("BACKUP: BLOCKED (source_changed_during_backup)")
        return 2

    manifest = {
        "format_version": 2,
        "created_at": datetime.now(UTC).isoformat(),
        "source_database": source_url.database,
        "source_host": (source_url.host or "").lower(),
        "source_port": source_url.port or 5432,
        "source_migration_revision": source_revision_before,
        "tool_mode": capability.mode,
        "dump_sha256": _sha256(dump_path),
        "fingerprint": fingerprint_before.to_dict(),
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "BACKUP: READY "
        f"(mode={capability.mode}; revision={source_revision_before}; "
        f"dump={dump_path}; manifest={manifest_path})"
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
