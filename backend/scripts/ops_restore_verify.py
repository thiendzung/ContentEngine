from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.recovery import (
    RecoverySafetyError,
    database_fingerprint,
    validate_restore_target,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore a backup into a disposable DB and verify it")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--restore-database")
    parser.add_argument("--keep", action="store_true")
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


async def _recreate_database(target: URL) -> None:
    database_name = target.database
    if database_name is None:
        raise RecoverySafetyError("unsafe_restore_database_name")
    admin = create_async_engine(
        target.set(database="postgres"),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with admin.connect() as connection:
            await connection.execute(
                text(
                    "select pg_terminate_backend(pid) from pg_stat_activity "
                    "where datname = :database_name and pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            await connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')
            await connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    finally:
        await admin.dispose()


async def _drop_database(target: URL) -> None:
    database_name = target.database
    if database_name is None:
        return
    admin = create_async_engine(
        target.set(database="postgres"),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with admin.connect() as connection:
            await connection.execute(
                text(
                    "select pg_terminate_backend(pid) from pg_stat_activity "
                    "where datname = :database_name and pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            await connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')
    finally:
        await admin.dispose()


async def _main() -> int:
    args = _parse_args()
    backup = args.backup.expanduser().resolve()
    manifest_path = (
        args.manifest.expanduser().resolve()
        if args.manifest
        else backup.with_suffix(".json")
    )
    if not backup.is_file() or not manifest_path.is_file():
        print("RESTORE_TEST: BLOCKED (backup_or_manifest_missing)")
        return 2
    if shutil.which("pg_restore") is None:
        print("RESTORE_TEST: BLOCKED (pg_restore_missing)")
        return 2

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("RESTORE_TEST: BLOCKED (manifest_invalid)")
        return 2
    if manifest.get("dump_sha256") != _sha256(backup):
        print("RESTORE_TEST: BLOCKED (backup_hash_mismatch)")
        return 2
    expected = manifest.get("fingerprint")
    if not isinstance(expected, dict):
        print("RESTORE_TEST: BLOCKED (manifest_fingerprint_missing)")
        return 2

    settings = get_settings()
    source = make_url(settings.database_url)
    if not source.database:
        print("RESTORE_TEST: BLOCKED (source_database_missing)")
        return 2
    restore_database = args.restore_database or f"{source.database}_restore_test"
    restore_url = source.set(database=restore_database)
    try:
        target = validate_restore_target(
            source_url=settings.database_url,
            restore_url=restore_url.render_as_string(hide_password=False),
        )
    except RecoverySafetyError as exc:
        print(f"RESTORE_TEST: BLOCKED ({exc.code})")
        return 2

    source_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        source_before = await database_fingerprint(source_engine)
    except Exception:
        print("RESTORE_TEST: BLOCKED (source_fingerprint_failed)")
        return 2

    try:
        await _recreate_database(target)
        connection_args, env = _pg_connection_args(target)
        result = subprocess.run(
            [
                "pg_restore",
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                *connection_args,
                str(backup),
            ],
            env=env,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            print("RESTORE_TEST: BLOCKED (pg_restore_failed)")
            return 2

        restored_engine = create_async_engine(target, poolclass=NullPool)
        try:
            restored = await database_fingerprint(restored_engine)
        finally:
            await restored_engine.dispose()

        source_after = await database_fingerprint(source_engine)
        if source_before != source_after:
            print("RESTORE_TEST: BLOCKED (source_database_changed)")
            return 2
        if restored.to_dict() != expected:
            print("RESTORE_TEST: BLOCKED (restored_fingerprint_mismatch)")
            return 2

        print(
            "RESTORE_TEST: READY "
            f"(database={target.database}; cases={restored.content_cases}; "
            f"runs={restored.content_runs}; approvals={restored.approvals}; "
            f"artifacts={restored.artifacts}; versions={restored.content_versions}; "
            f"artifact_hash={restored.artifact_hash}; lineage_hash={restored.lineage_hash})"
        )
        return 0
    finally:
        await source_engine.dispose()
        if not args.keep:
            await _drop_database(target)


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
