from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.recovery import (
    RecoverySafetyError,
    validate_operational_database_source,
)
from scripts.ops_migration_rehearsal import (
    _EXPECTED_FUNCTIONS,
    _EXPECTED_SOURCE_REVISION,
    _EXPECTED_TABLES,
    _EXPECTED_TARGET_REVISION,
    _EXPECTED_TRIGGERS,
    _alembic_script,
    _database_state,
    _expected_fingerprint,
    _load_manifest,
    _manifest_source_revision,
    _source_documents_fingerprint,
    _upgrade_chain,
    _verify_backfill,
    _verify_schema_objects,
)

_EXPECTED_SOURCE_DATABASE = "contentengine"
_EXPECTED_SOURCE_DOCUMENTS = {
    "count": 6,
    "sha256": "865bd5952be18b5ecb14867db335988dfd9f8863683036fb0a911baff3036037",
}
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_BACKEND_PROCESS_MARKERS = ("uvicorn app.main:app",)
_FRONTEND_PROCESS_MARKERS = ("next dev", "next start")
_WORKER_MARKERS = (
    "scripts.run_operator_worker",
    "scripts.run_operator_worker_loop",
    "celery",
)


class OperationalMigrationError(RuntimeError):
    """Raised when O1.2B cannot prove a safe operational source migration."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed operational migration from the approved O1 source state"
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--authorized-head", required=True)
    return parser.parse_args()


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=_repository_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise OperationalMigrationError("git_state_unavailable")
    return result.stdout.strip()


def _validate_authorized_checkout(authorized_head: str) -> dict[str, object]:
    if not _FULL_SHA.fullmatch(authorized_head):
        raise OperationalMigrationError("authorized_head_invalid")
    actual_head = _run_git("rev-parse", "HEAD")
    if actual_head != authorized_head:
        raise OperationalMigrationError("authorized_head_mismatch")
    clean = _run_git("status", "--porcelain") == ""
    if not clean:
        raise OperationalMigrationError("migration_checkout_dirty")
    return {"head": actual_head, "clean": clean}


def _port_listening(port: int) -> bool:
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except OSError:
            continue
    return False


def _runtime_guard() -> dict[str, object]:
    backend_listening = _port_listening(8000)
    frontend_listening = _port_listening(3000)

    result = subprocess.run(
        ["ps", "-axo", "pid=,command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise OperationalMigrationError("runtime_process_state_unavailable")

    backend_processes: list[str] = []
    frontend_processes: list[str] = []
    workers: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if any(marker in lowered for marker in _BACKEND_PROCESS_MARKERS):
            backend_processes.append(line)
        if any(marker in lowered for marker in _FRONTEND_PROCESS_MARKERS):
            frontend_processes.append(line)
        if any(marker in lowered for marker in _WORKER_MARKERS):
            workers.append(line)

    if backend_listening or backend_processes:
        raise OperationalMigrationError("backend_runtime_active")
    if frontend_listening or frontend_processes:
        raise OperationalMigrationError("frontend_runtime_active")
    if workers:
        raise OperationalMigrationError("worker_runtime_active")

    return {
        "backend_port_8000": "STOPPED",
        "frontend_port_3000": "STOPPED",
        "backend_processes": [],
        "frontend_processes": [],
        "worker_processes": [],
    }


async def _current_database(engine: AsyncEngine) -> str:
    async with engine.connect() as connection:
        database = (await connection.execute(text("select current_database()"))).scalar_one()
    return str(database)


async def _whole_table_fingerprint(
    engine: AsyncEngine,
    *,
    table_name: str,
) -> dict[str, object]:
    if table_name != "model_calls":
        raise OperationalMigrationError("unsupported_table_fingerprint")
    async with engine.connect() as connection:
        rows = list(
            (
                await connection.execute(
                    text("select row_to_json(t)::text from model_calls t order by id")
                )
            ).scalars()
        )
    payload = json.dumps(
        [str(row) for row in rows],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "count": len(rows),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


async def _future_schema_objects_present(engine: AsyncEngine) -> dict[str, list[str]]:
    tables: list[str] = []
    functions: list[str] = []
    triggers: list[str] = []

    async with engine.connect() as connection:
        for table_name in _EXPECTED_TABLES:
            exists = (
                await connection.execute(
                    text("select to_regclass(:qualified_name)"),
                    {"qualified_name": f"public.{table_name}"},
                )
            ).scalar_one()
            if exists is not None:
                tables.append(table_name)

        for function_name in _EXPECTED_FUNCTIONS:
            exists = bool(
                (
                    await connection.execute(
                        text(
                            """
                            select exists(
                                select 1
                                from pg_proc p
                                join pg_namespace n on n.oid = p.pronamespace
                                where n.nspname = 'public' and p.proname = :function_name
                            )
                            """
                        ),
                        {"function_name": function_name},
                    )
                ).scalar_one()
            )
            if exists:
                functions.append(function_name)

        for trigger_name, table_name in _EXPECTED_TRIGGERS.items():
            exists = bool(
                (
                    await connection.execute(
                        text(
                            """
                            select exists(
                                select 1
                                from pg_trigger t
                                join pg_class c on c.oid = t.tgrelid
                                join pg_namespace n on n.oid = c.relnamespace
                                where n.nspname = 'public'
                                  and c.relname = :table_name
                                  and t.tgname = :trigger_name
                                  and not t.tgisinternal
                            )
                            """
                        ),
                        {
                            "table_name": table_name,
                            "trigger_name": trigger_name,
                        },
                    )
                ).scalar_one()
            )
            if exists:
                triggers.append(f"{table_name}.{trigger_name}")

    return {
        "tables": tables,
        "functions": functions,
        "triggers": triggers,
    }


def _run_source_upgrade(source: URL) -> None:
    if source.database != _EXPECTED_SOURCE_DATABASE:
        raise OperationalMigrationError("unexpected_operational_database")
    env = os.environ.copy()
    env["APP_ENV"] = "development"
    env["DATABASE_URL"] = source.render_as_string(hide_password=False)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "upgrade",
            _EXPECTED_TARGET_REVISION,
        ],
        cwd=_backend_root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise OperationalMigrationError("alembic_upgrade_failed")


async def _main() -> int:
    args = _parse_args()
    backup = args.backup.expanduser().resolve()
    manifest_path = (
        args.manifest.expanduser().resolve()
        if args.manifest
        else backup.with_suffix(".json")
    )

    try:
        checkout = _validate_authorized_checkout(args.authorized_head)
        runtime_before = _runtime_guard()
        manifest = _load_manifest(backup, manifest_path)

        settings = get_settings()
        if settings.app_env.strip().lower() == "test":
            raise OperationalMigrationError("test_environment_not_operational")

        source = validate_operational_database_source(settings.database_url)
        if source.database != _EXPECTED_SOURCE_DATABASE:
            raise OperationalMigrationError("unexpected_operational_database")

        source_revision_manifest = _manifest_source_revision(manifest, source)
        chain = _upgrade_chain(_alembic_script(), source_revision_manifest)
        expected_fingerprint = _expected_fingerprint(manifest)
    except OperationalMigrationError as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "operational_source_migration",
                    "blocker": exc.code,
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2
    except RecoverySafetyError as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "operational_source_migration",
                    "blocker": exc.code,
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2
    except Exception:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "operational_source_migration",
                    "blocker": "operational_migration_preflight_failed",
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    blocker: str | None = None
    secondary_blockers: list[str] = []
    migration_attempted = False
    result_payload: dict[str, object] = {}

    revision_before: str | None = None
    fingerprint_before = None
    source_documents_before: dict[str, object] | None = None
    model_calls_before: dict[str, object] | None = None

    try:
        actual_database_before = await _current_database(engine)
        if actual_database_before != _EXPECTED_SOURCE_DATABASE:
            raise OperationalMigrationError("database_identity_mismatch")

        revision_before, fingerprint_before = await _database_state(engine)
        source_documents_before = await _source_documents_fingerprint(engine)
        model_calls_before = await _whole_table_fingerprint(
            engine,
            table_name="model_calls",
        )

        if revision_before != _EXPECTED_SOURCE_REVISION:
            raise OperationalMigrationError("source_revision_drift")
        if fingerprint_before.to_dict() != expected_fingerprint:
            raise OperationalMigrationError("source_fingerprint_drift")
        if source_documents_before != _EXPECTED_SOURCE_DOCUMENTS:
            raise OperationalMigrationError("source_documents_drift")

        future_objects = await _future_schema_objects_present(engine)
        if any(future_objects.values()):
            raise OperationalMigrationError("unexpected_future_schema_objects_present")

        migration_attempted = True
        _run_source_upgrade(source)

        actual_database_after = await _current_database(engine)
        if actual_database_after != _EXPECTED_SOURCE_DATABASE:
            raise OperationalMigrationError("database_identity_mismatch")

        revision_after, fingerprint_after = await _database_state(engine)
        source_documents_after = await _source_documents_fingerprint(engine)
        model_calls_after = await _whole_table_fingerprint(
            engine,
            table_name="model_calls",
        )

        if revision_after != _EXPECTED_TARGET_REVISION:
            raise OperationalMigrationError("migrated_revision_mismatch")
        if fingerprint_after != fingerprint_before:
            raise OperationalMigrationError("core_fingerprint_changed_by_migration")
        if source_documents_after != source_documents_before:
            raise OperationalMigrationError("source_documents_changed_by_migration")
        if model_calls_after != model_calls_before:
            raise OperationalMigrationError("model_calls_changed_by_migration")

        backfill = await _verify_backfill(engine)
        schema_objects = await _verify_schema_objects(engine)
        runtime_after = _runtime_guard()

        result_payload = {
            "mode": "operational_source_migration",
            "checkout": checkout,
            "runtime_before": runtime_before,
            "runtime_after": runtime_after,
            "source_database": source.database,
            "actual_database_before": actual_database_before,
            "actual_database_after": actual_database_after,
            "backup": str(backup),
            "manifest": str(manifest_path),
            "dump_sha256": manifest.get("dump_sha256"),
            "revision_before": revision_before,
            "revision_after": revision_after,
            "upgrade_chain": list(chain),
            "core_fingerprint_before": fingerprint_before.to_dict(),
            "core_fingerprint_after": fingerprint_after.to_dict(),
            "source_documents_before": source_documents_before,
            "source_documents_after": source_documents_after,
            "model_calls_before": model_calls_before,
            "model_calls_after": model_calls_after,
            "backfill": backfill,
            "schema_objects": schema_objects,
            "application_runtime": "STOPPED",
        }
    except OperationalMigrationError as exc:
        blocker = exc.code
    except Exception:
        blocker = "operational_migration_unexpected_failure"
    finally:
        if migration_attempted and revision_before is not None and blocker is not None:
            try:
                revision_final, fingerprint_final = await _database_state(engine)
                source_documents_final = await _source_documents_fingerprint(engine)
                model_calls_final = await _whole_table_fingerprint(
                    engine,
                    table_name="model_calls",
                )
                result_payload["failure_state"] = {
                    "revision": revision_final,
                    "core_fingerprint": fingerprint_final.to_dict(),
                    "source_documents": source_documents_final,
                    "model_calls": model_calls_final,
                }

                if (
                    fingerprint_before is not None
                    and fingerprint_final != fingerprint_before
                    and blocker != "core_fingerprint_changed_by_migration"
                ):
                    secondary_blockers.append("core_fingerprint_changed_by_migration")
                if (
                    source_documents_before is not None
                    and source_documents_final != source_documents_before
                    and blocker != "source_documents_changed_by_migration"
                ):
                    secondary_blockers.append("source_documents_changed_by_migration")
                if (
                    model_calls_before is not None
                    and model_calls_final != model_calls_before
                    and blocker != "model_calls_changed_by_migration"
                ):
                    secondary_blockers.append("model_calls_changed_by_migration")
            except Exception:
                secondary_blockers.append("post_migration_source_verification_failed")

        try:
            _runtime_guard()
        except OperationalMigrationError as exc:
            if blocker is None:
                blocker = exc.code
            elif exc.code != blocker:
                secondary_blockers.append(exc.code)

        await engine.dispose()

    if blocker is not None:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "operational_source_migration",
                    "blocker": blocker,
                    "secondary_blockers": secondary_blockers,
                    "migration_attempted": migration_attempted,
                    **result_payload,
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    result_payload["secondary_blockers"] = secondary_blockers
    print(
        json.dumps(
            {"status": "READY", **result_payload},
            sort_keys=True,
            indent=2,
        )
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
