from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.recovery import database_fingerprint


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


def _pg_connection_args(url: URL) -> tuple[list[str], dict[str, str]]:
    args: list[str] = []
    if url.host:
        args.extend(["--host", url.host])
    if url.port:
        args.extend(["--port", str(url.port)])
    if url.username:
        args.extend(["--username", url.username])
    if url.database:
        args.extend(["--dbname", url.database])
    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = url.password
    return args, env


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _main() -> int:
    if shutil.which("pg_dump") is None:
        print("BACKUP: BLOCKED (pg_dump_missing)")
        return 2

    try:
        backup_dir = _backup_dir()
    except BackupSafetyError as exc:
        print(f"BACKUP: BLOCKED ({exc.code})")
        return 2

    settings = get_settings()
    source_url = make_url(settings.database_url)
    if source_url.get_backend_name() != "postgresql" or not source_url.database:
        print("BACKUP: BLOCKED (operational_database_unsupported)")
        return 2

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    stem = f"contentengine-{source_url.database}-{stamp}"
    dump_path = backup_dir / f"{stem}.dump"
    manifest_path = backup_dir / f"{stem}.json"

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        fingerprint = await database_fingerprint(engine)
    except Exception:
        print("BACKUP: BLOCKED (source_fingerprint_failed)")
        return 2
    finally:
        await engine.dispose()

    connection_args, env = _pg_connection_args(source_url)
    command = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(dump_path),
        *connection_args,
    ]
    result = subprocess.run(command, env=env, capture_output=True, check=False)
    if result.returncode != 0 or not dump_path.is_file():
        dump_path.unlink(missing_ok=True)
        print("BACKUP: BLOCKED (pg_dump_failed)")
        return 2

    manifest = {
        "format_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "source_database": source_url.database,
        "dump_sha256": _sha256(dump_path),
        "fingerprint": fingerprint.to_dict(),
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"BACKUP: READY (dump={dump_path}; manifest={manifest_path})")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
