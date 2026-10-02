from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.postgres_tools import postgres_tool_capability, postgres_tool_command
from app.modules.system.recovery import (
    DatabaseFingerprint,
    RecoverySafetyError,
    database_fingerprint,
    validate_operational_database_source,
    validate_restore_target,
)

_SOURCE_REVISION = "20260915_0034"
_TARGET_REVISION = "20260926_0044"
_EXPECTED_UPGRADE_CHAIN = (
    "20260921_0035",
    "20260921_0036",
    "20260921_0037",
    "20260922_0038",
    "20260922_0039",
    "20260922_0040",
    "20260922_0041",
    "20260923_0042",
    "20260925_0043",
    "20260926_0044",
)


class Data02RehearsalError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Restore a fresh operational backup into a disposable DB, rehearse "
            "20260915_0034 -> 20260926_0044, and prove source invariance"
        )
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--keep", action="store_true")
    return parser.parse_args()


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(backup: Path, manifest_path: Path) -> dict[str, object]:
    if not backup.is_file() or not manifest_path.is_file():
        raise Data02RehearsalError("backup_or_manifest_missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Data02RehearsalError("manifest_invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("format_version") != 2:
        raise Data02RehearsalError("manifest_format_v2_required")
    try:
        dump_hash = _sha256(backup)
    except OSError as exc:
        raise Data02RehearsalError("backup_hash_unavailable") from exc
    if manifest.get("dump_sha256") != dump_hash:
        raise Data02RehearsalError("backup_hash_mismatch")
    _expected_fingerprint(manifest)
    return manifest


def _expected_fingerprint(manifest: dict[str, object]) -> dict[str, object]:
    fingerprint = manifest.get("fingerprint")
    if not isinstance(fingerprint, dict):
        raise Data02RehearsalError("manifest_fingerprint_missing")
    required = {
        "content_cases",
        "content_runs",
        "approvals",
        "artifacts",
        "content_versions",
        "artifact_hash",
        "lineage_hash",
    }
    if set(fingerprint) != required:
        raise Data02RehearsalError("manifest_fingerprint_shape_invalid")
    return fingerprint


def _manifest_source_revision(manifest: dict[str, object], source: URL) -> str:
    if manifest.get("source_database") != source.database:
        raise Data02RehearsalError("manifest_source_database_mismatch")
    if manifest.get("source_host") != (source.host or "").lower():
        raise Data02RehearsalError("manifest_source_host_mismatch")
    if manifest.get("source_port") != (source.port or 5432):
        raise Data02RehearsalError("manifest_source_port_mismatch")
    revision = manifest.get("source_migration_revision")
    if not isinstance(revision, str) or not revision:
        raise Data02RehearsalError("manifest_migration_revision_missing")
    if revision != _SOURCE_REVISION:
        raise Data02RehearsalError("unexpected_source_migration_revision")
    return revision


def _alembic_script() -> ScriptDirectory:
    backend_root = _backend_root()
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    return ScriptDirectory.from_config(config)


def _upgrade_chain(script: ScriptDirectory, source_revision: str) -> tuple[str, ...]:
    revision = script.get_revision(_TARGET_REVISION)
    if revision is None:
        raise Data02RehearsalError("target_revision_missing")

    reverse_path: list[str] = []
    while revision.revision != source_revision:
        reverse_path.append(revision.revision)
        down_revision = revision.down_revision
        if not isinstance(down_revision, str):
            raise Data02RehearsalError("migration_chain_not_linear")
        revision = script.get_revision(down_revision)
        if revision is None:
            raise Data02RehearsalError("source_revision_not_in_chain")

    path = tuple(reversed(reverse_path))
    if path != _EXPECTED_UPGRADE_CHAIN:
        raise Data02RehearsalError("unexpected_migration_chain")
    return path


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


async def _migration_revision(engine: AsyncEngine) -> str | None:
    async with engine.connect() as connection:
        revision = (
            await connection.execute(text("select version_num from alembic_version"))
        ).scalar_one_or_none()
    return None if revision is None else str(revision)


async def _database_state(
    engine: AsyncEngine,
) -> tuple[str | None, DatabaseFingerprint]:
    return await _migration_revision(engine), await database_fingerprint(engine)


async def _source_documents_fingerprint(engine: AsyncEngine) -> dict[str, object]:
    async with engine.connect() as connection:
        rows = list(
            (
                await connection.execute(
                    text(
                        """
                        select
                            id::text,
                            source_id::text,
                            document_version::text,
                            fetched_at::text,
                            content_hash,
                            coalesce(canonical_url, ''),
                            coalesce(provider, ''),
                            coalesce(reader, '')
                        from source_documents
                        order by id
                        """
                    )
                )
            ).all()
        )
    payload = json.dumps(
        [[str(value) for value in row] for row in rows],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "count": len(rows),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


async def _recreate_database(target: URL) -> None:
    database_name = target.database
    if database_name is None:
        raise Data02RehearsalError("unsafe_rehearsal_database_name")
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


def _restore_backup(backup: Path, target: URL) -> str:
    capability = postgres_tool_capability()
    if capability is None:
        raise Data02RehearsalError("pg_restore_unavailable")
    connection_args, env = _pg_connection_args(
        target,
        container_mode=capability.mode == "container",
    )
    command = [
        *postgres_tool_command("pg_restore"),
        "--no-owner",
        "--no-privileges",
        "--exit-on-error",
        *connection_args,
    ]
    with backup.open("rb") as backup_handle:
        result = subprocess.run(
            command,
            env=env,
            stdin=backup_handle,
            capture_output=True,
            check=False,
        )
    if result.returncode != 0:
        raise Data02RehearsalError("pg_restore_failed")
    return capability.mode


def _run_alembic_upgrade(target: URL) -> None:
    env = os.environ.copy()
    env["APP_ENV"] = "development"
    env["DATABASE_URL"] = target.render_as_string(hide_password=False)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "upgrade",
            _TARGET_REVISION,
        ],
        cwd=_backend_root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise Data02RehearsalError("alembic_upgrade_failed")


async def _main() -> int:
    args = _parse_args()
    backup = args.backup.expanduser().resolve()
    manifest_path = (
        args.manifest.expanduser().resolve()
        if args.manifest
        else backup.with_suffix(".json")
    )

    try:
        manifest = _load_manifest(backup, manifest_path)
        settings = get_settings()
        if settings.app_env.strip().lower() == "test":
            raise Data02RehearsalError("test_environment_not_operational")
        source = validate_operational_database_source(settings.database_url)
        source_revision_manifest = _manifest_source_revision(manifest, source)
        chain = _upgrade_chain(_alembic_script(), source_revision_manifest)
        expected_fingerprint = _expected_fingerprint(manifest)
        target_url = source.set(database=f"{source.database}_data02_restore_test")
        target = validate_restore_target(
            source_url=settings.database_url,
            restore_url=target_url.render_as_string(hide_password=False),
        )
    except (Data02RehearsalError, RecoverySafetyError) as exc:
        print(json.dumps({"status": "BLOCKED", "blocker": exc.code}, sort_keys=True))
        return 2
    except Exception:
        print(
            json.dumps(
                {"status": "BLOCKED", "blocker": "data02_preflight_failed"},
                sort_keys=True,
            )
        )
        return 2

    source_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    target_created = False
    blocker: str | None = None
    secondary: list[str] = []
    evidence: dict[str, object] = {}

    source_revision_before: str | None = None
    source_fingerprint_before: DatabaseFingerprint | None = None
    source_documents_before: dict[str, object] | None = None

    try:
        source_revision_before, source_fingerprint_before = await _database_state(
            source_engine
        )
        source_documents_before = await _source_documents_fingerprint(source_engine)

        if source_revision_before != _SOURCE_REVISION:
            raise Data02RehearsalError("source_revision_drift")
        if source_fingerprint_before.to_dict() != expected_fingerprint:
            raise Data02RehearsalError("source_fingerprint_drift")

        await _recreate_database(target)
        target_created = True
        restore_mode = _restore_backup(backup, target)

        target_engine = create_async_engine(target, poolclass=NullPool)
        try:
            restored_revision, restored_fingerprint = await _database_state(target_engine)
            restored_documents = await _source_documents_fingerprint(target_engine)
            if restored_revision != _SOURCE_REVISION:
                raise Data02RehearsalError("restored_source_revision_mismatch")
            if restored_fingerprint.to_dict() != expected_fingerprint:
                raise Data02RehearsalError("restored_source_fingerprint_mismatch")
            if restored_documents != source_documents_before:
                raise Data02RehearsalError("restored_source_documents_mismatch")

            _run_alembic_upgrade(target)

            migrated_revision, migrated_fingerprint = await _database_state(target_engine)
            migrated_documents = await _source_documents_fingerprint(target_engine)
            if migrated_revision != _TARGET_REVISION:
                raise Data02RehearsalError("migrated_revision_mismatch")
            if migrated_fingerprint.to_dict() != expected_fingerprint:
                raise Data02RehearsalError("core_fingerprint_changed_by_migration")
            if migrated_documents != source_documents_before:
                raise Data02RehearsalError("source_documents_changed_by_migration")
        finally:
            await target_engine.dispose()

        source_revision_after, source_fingerprint_after = await _database_state(source_engine)
        source_documents_after = await _source_documents_fingerprint(source_engine)
        if source_revision_after != source_revision_before:
            raise Data02RehearsalError("source_revision_changed")
        if source_fingerprint_after != source_fingerprint_before:
            raise Data02RehearsalError("source_fingerprint_changed")
        if source_documents_after != source_documents_before:
            raise Data02RehearsalError("source_documents_changed")

        evidence = {
            "status": "READY",
            "mode": "data02_isolated_migration_rehearsal",
            "source_database": source.database,
            "source_revision_before": source_revision_before,
            "source_revision_after": source_revision_after,
            "source_fingerprint": source_fingerprint_after.to_dict(),
            "source_documents_fingerprint": source_documents_after,
            "backup": str(backup),
            "manifest": str(manifest_path),
            "dump_sha256": manifest.get("dump_sha256"),
            "restore_mode": restore_mode,
            "rehearsal_database": target.database,
            "restored_revision": restored_revision,
            "target_revision": migrated_revision,
            "upgrade_chain": list(chain),
            "core_fingerprint_after_migration": migrated_fingerprint.to_dict(),
            "source_documents_after_migration": migrated_documents,
        }
    except Data02RehearsalError as exc:
        blocker = exc.code
    except Exception:
        blocker = "data02_rehearsal_unexpected_failure"
    finally:
        if (
            source_revision_before is not None
            and source_fingerprint_before is not None
            and source_documents_before is not None
        ):
            try:
                source_revision_after, source_fingerprint_after = await _database_state(
                    source_engine
                )
                source_documents_after = await _source_documents_fingerprint(source_engine)
                post_blocker: str | None = None
                if source_revision_after != source_revision_before:
                    post_blocker = "source_revision_changed"
                elif source_fingerprint_after != source_fingerprint_before:
                    post_blocker = "source_fingerprint_changed"
                elif source_documents_after != source_documents_before:
                    post_blocker = "source_documents_changed"
                if post_blocker is not None:
                    if blocker is None:
                        blocker = post_blocker
                    elif post_blocker != blocker:
                        secondary.append(post_blocker)
            except Exception:
                if blocker is None:
                    blocker = "source_post_rehearsal_verification_failed"
                else:
                    secondary.append("source_post_rehearsal_verification_failed")
        await source_engine.dispose()

        if target_created and not args.keep:
            try:
                await _drop_database(target)
            except Exception:
                if blocker is None:
                    blocker = "rehearsal_database_cleanup_failed"
                else:
                    secondary.append("rehearsal_database_cleanup_failed")

    if blocker is not None:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "data02_isolated_migration_rehearsal",
                    "blocker": blocker,
                    "secondary_blockers": secondary,
                    "rehearsal_database": target.database,
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    evidence["rehearsal_database_cleanup"] = (
        "RETAINED_FOR_DIAGNOSIS" if args.keep else "DROPPED"
    )
    print(json.dumps(evidence, sort_keys=True, indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
