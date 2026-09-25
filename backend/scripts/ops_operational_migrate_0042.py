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

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.recovery import (
    RecoverySafetyError,
    database_fingerprint,
    validate_operational_database_source,
)

_EXPECTED_SOURCE_DATABASE = "contentengine"
_EXPECTED_SOURCE_REVISION = "20260915_0034"
_EXPECTED_TARGET_REVISION = "20260923_0042"
_EXPECTED_UPGRADE_CHAIN = (
    "20260921_0035",
    "20260921_0036",
    "20260921_0037",
    "20260922_0038",
    "20260922_0039",
    "20260922_0040",
    "20260922_0041",
    "20260923_0042",
)
_EXPECTED_TABLES = (
    "customer_insights",
    "customer_insight_signals",
    "customer_insight_reviews",
    "customer_insight_need_links",
    "content_case_supporting_needs",
    "content_item_journey_stages",
    "published_contents",
    "publish_events",
    "performance_snapshots",
    "performance_metrics",
    "content_performance_observations",
    "learning_candidates",
    "learning_candidate_assessments",
    "learning_candidate_signals",
    "learning_candidate_observations",
    "learning_candidate_reviews",
    "learning_applications",
    "learning_validations",
    "learning_resolutions",
    "learning_resolution_applications",
)
_EXPECTED_FUNCTIONS = (
    "prevent_content_experiment_rebind",
    "validate_published_content_scope",
    "validate_publish_event_scope",
    "prevent_publish_event_mutation",
    "validate_performance_identity",
)
_EXPECTED_TRIGGERS = {
    "content_experiment_binding_immutable": "content_experiments",
    "published_content_scope_guard": "published_contents",
    "publish_event_scope_guard": "publish_events",
    "publish_events_immutable": "publish_events",
    "learning_validations_guard": "learning_validations",
    "learning_resolutions_guard": "learning_resolutions",
    "learning_resolution_applications_guard": "learning_resolution_applications",
}
_FROZEN_TABLES = (
    "jobs",
    "step_runs",
    "model_calls",
    "tool_calls",
    "outbox_intents",
)
_RUNTIME_PORTS = (8000, 3000)
_BACKEND_PROCESS_MARKERS = ("uvicorn app.main:app",)
_FRONTEND_PROCESS_MARKERS = ("next dev", "next start")
_WORKER_MARKERS = (
    "scripts.run_operator_worker",
    "scripts.run_operator_worker_loop",
    "celery",
)
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CurrentOperationalMigrationError(RuntimeError):
    """Raised when the bounded 0034 -> 0042 migration contract is not satisfied."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed operational migration from ContentEngine rev-0034 to rev-0042"
        )
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--authorized-head", required=True)
    parser.add_argument("--expected-dump-sha256", required=True)
    parser.add_argument("--expected-source-documents-count", type=int, required=True)
    parser.add_argument("--expected-source-documents-sha256", required=True)
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
        raise CurrentOperationalMigrationError("git_state_unavailable")
    return result.stdout.strip()


def _validate_authorized_checkout(authorized_head: str) -> dict[str, object]:
    if not _FULL_SHA.fullmatch(authorized_head):
        raise CurrentOperationalMigrationError("authorized_head_invalid")
    actual_head = _run_git("rev-parse", "HEAD")
    if actual_head != authorized_head:
        raise CurrentOperationalMigrationError("authorized_head_mismatch")
    if _run_git("status", "--porcelain") != "":
        raise CurrentOperationalMigrationError("migration_checkout_dirty")
    return {"head": actual_head, "clean": True}


def _port_listening(port: int) -> bool:
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except OSError:
            continue
    return False


def _runtime_guard() -> dict[str, object]:
    active_ports = [port for port in _RUNTIME_PORTS if _port_listening(port)]
    result = subprocess.run(
        ["ps", "-axo", "pid=,command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise CurrentOperationalMigrationError("runtime_process_state_unavailable")

    backend_processes: list[str] = []
    frontend_processes: list[str] = []
    worker_processes: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if any(marker in lowered for marker in _BACKEND_PROCESS_MARKERS):
            backend_processes.append(line)
        if any(marker in lowered for marker in _FRONTEND_PROCESS_MARKERS):
            frontend_processes.append(line)
        if any(marker in lowered for marker in _WORKER_MARKERS):
            worker_processes.append(line)

    if 8000 in active_ports or backend_processes:
        raise CurrentOperationalMigrationError("backend_runtime_active")
    if 3000 in active_ports or frontend_processes:
        raise CurrentOperationalMigrationError("frontend_runtime_active")
    if worker_processes:
        raise CurrentOperationalMigrationError("worker_runtime_active")

    return {
        "backend_port_8000": "STOPPED",
        "frontend_port_3000": "STOPPED",
        "backend_processes": [],
        "frontend_processes": [],
        "worker_processes": [],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_fingerprint(manifest: dict[str, object]) -> dict[str, object]:
    fingerprint = manifest.get("fingerprint")
    if not isinstance(fingerprint, dict):
        raise CurrentOperationalMigrationError("manifest_fingerprint_missing")
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
        raise CurrentOperationalMigrationError("manifest_fingerprint_shape_invalid")
    return fingerprint


def _load_manifest(
    backup: Path,
    manifest_path: Path,
    *,
    expected_dump_sha256: str,
) -> dict[str, object]:
    if not _SHA256.fullmatch(expected_dump_sha256):
        raise CurrentOperationalMigrationError("expected_dump_sha256_invalid")
    if not backup.is_file() or not manifest_path.is_file():
        raise CurrentOperationalMigrationError("backup_or_manifest_missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CurrentOperationalMigrationError("manifest_invalid") from exc
    if not isinstance(manifest, dict):
        raise CurrentOperationalMigrationError("manifest_invalid")
    if manifest.get("format_version") != 2:
        raise CurrentOperationalMigrationError("manifest_format_v2_required")

    try:
        actual_dump_sha256 = _sha256(backup)
    except OSError as exc:
        raise CurrentOperationalMigrationError("backup_hash_unavailable") from exc
    if actual_dump_sha256 != expected_dump_sha256:
        raise CurrentOperationalMigrationError("authorized_backup_hash_mismatch")
    if manifest.get("dump_sha256") != actual_dump_sha256:
        raise CurrentOperationalMigrationError("backup_hash_mismatch")
    _expected_fingerprint(manifest)
    return manifest


def _manifest_source_revision(manifest: dict[str, object], source: URL) -> str:
    if manifest.get("source_database") != source.database:
        raise CurrentOperationalMigrationError("manifest_source_database_mismatch")
    if manifest.get("source_host") != (source.host or "").lower():
        raise CurrentOperationalMigrationError("manifest_source_host_mismatch")
    if manifest.get("source_port") != (source.port or 5432):
        raise CurrentOperationalMigrationError("manifest_source_port_mismatch")
    revision = manifest.get("source_migration_revision")
    if not isinstance(revision, str) or not revision:
        raise CurrentOperationalMigrationError("manifest_migration_revision_missing")
    if revision != _EXPECTED_SOURCE_REVISION:
        raise CurrentOperationalMigrationError("unexpected_source_migration_revision")
    return revision


def _alembic_script() -> ScriptDirectory:
    config = Config(str(_backend_root() / "alembic.ini"))
    return ScriptDirectory.from_config(config)


def _upgrade_chain(
    script: ScriptDirectory,
    source_revision: str,
) -> tuple[str, ...]:
    if script.get_current_head() != _EXPECTED_TARGET_REVISION:
        raise CurrentOperationalMigrationError("unexpected_code_migration_head")

    revision = script.get_revision(_EXPECTED_TARGET_REVISION)
    if revision is None:
        raise CurrentOperationalMigrationError("target_revision_missing")

    reverse_path: list[str] = []
    while revision.revision != source_revision:
        reverse_path.append(revision.revision)
        down_revision = revision.down_revision
        if not isinstance(down_revision, str):
            raise CurrentOperationalMigrationError("migration_chain_not_linear")
        revision = script.get_revision(down_revision)
        if revision is None:
            raise CurrentOperationalMigrationError("source_revision_not_in_chain")

    path = tuple(reversed(reverse_path))
    if path != _EXPECTED_UPGRADE_CHAIN:
        raise CurrentOperationalMigrationError("unexpected_migration_chain")
    return path


async def _current_database(engine: AsyncEngine) -> str:
    async with engine.connect() as connection:
        value = (await connection.execute(text("select current_database()"))).scalar_one()
    return str(value)


async def _migration_revision(engine: AsyncEngine) -> str | None:
    async with engine.connect() as connection:
        value = (
            await connection.execute(text("select version_num from alembic_version"))
        ).scalar_one_or_none()
    return None if value is None else str(value)


async def _source_documents_fingerprint(engine: AsyncEngine) -> dict[str, object]:
    async with engine.connect() as connection:
        rows = list(
            (
                await connection.execute(
                    text(
                        """
                        select
                            id::text,
                            fetched_at::text,
                            content_hash,
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
    ).encode()
    return {
        "count": len(rows),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


async def _table_fingerprint(
    engine: AsyncEngine,
    *,
    table_name: str,
) -> dict[str, object]:
    if table_name not in _FROZEN_TABLES:
        raise CurrentOperationalMigrationError("unsupported_table_fingerprint")
    async with engine.connect() as connection:
        rows = list(
            (
                await connection.execute(
                    text(f"select row_to_json(t)::text from {table_name} t order by id")
                )
            ).scalars()
        )
    payload = json.dumps(
        [str(row) for row in rows],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return {
        "count": len(rows),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


async def _frozen_table_fingerprints(
    engine: AsyncEngine,
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for table_name in _FROZEN_TABLES:
        result[table_name] = await _table_fingerprint(engine, table_name=table_name)
    return result


async def _schema_objects(engine: AsyncEngine) -> dict[str, list[str]]:
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


def _require_no_future_schema(objects: dict[str, list[str]]) -> None:
    if any(objects.values()):
        raise CurrentOperationalMigrationError("unexpected_future_schema_objects_present")


def _require_expected_schema(objects: dict[str, list[str]]) -> None:
    expected_triggers = {
        f"{table_name}.{trigger_name}"
        for trigger_name, table_name in _EXPECTED_TRIGGERS.items()
    }
    if set(objects["tables"]) != set(_EXPECTED_TABLES):
        raise CurrentOperationalMigrationError("required_tables_missing")
    if set(objects["functions"]) != set(_EXPECTED_FUNCTIONS):
        raise CurrentOperationalMigrationError("required_functions_missing")
    if set(objects["triggers"]) != expected_triggers:
        raise CurrentOperationalMigrationError("required_triggers_missing")


def _run_source_upgrade(source: URL) -> None:
    if source.database != _EXPECTED_SOURCE_DATABASE:
        raise CurrentOperationalMigrationError("unexpected_operational_database")
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
        raise CurrentOperationalMigrationError("alembic_upgrade_failed")


def _final_document(
    *,
    status: str,
    payload: dict[str, object],
    blocker: str | None = None,
    secondary_blockers: list[str] | None = None,
    migration_attempted: bool | None = None,
) -> dict[str, object]:
    document = dict(payload)
    document["status"] = status
    if blocker is not None:
        document["blocker"] = blocker
    if secondary_blockers is not None:
        document["secondary_blockers"] = list(secondary_blockers)
    if migration_attempted is not None:
        document["migration_attempted"] = migration_attempted
    return document


async def _main() -> int:
    args = _parse_args()
    backup = args.backup.expanduser().resolve()
    manifest_path = (
        args.manifest.expanduser().resolve()
        if args.manifest
        else backup.with_suffix(".json")
    )

    if args.expected_source_documents_count < 0:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "operational_source_migration_0034_0042",
                    "blocker": "expected_source_documents_count_invalid",
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2
    if not _SHA256.fullmatch(args.expected_source_documents_sha256):
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "operational_source_migration_0034_0042",
                    "blocker": "expected_source_documents_sha256_invalid",
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    try:
        checkout = _validate_authorized_checkout(args.authorized_head)
        runtime_before = _runtime_guard()
        manifest = _load_manifest(
            backup,
            manifest_path,
            expected_dump_sha256=args.expected_dump_sha256,
        )

        settings = get_settings()
        if settings.app_env.strip().lower() == "test":
            raise CurrentOperationalMigrationError("test_environment_not_operational")

        source = validate_operational_database_source(settings.database_url)
        if source.database != _EXPECTED_SOURCE_DATABASE:
            raise CurrentOperationalMigrationError("unexpected_operational_database")

        source_revision_manifest = _manifest_source_revision(manifest, source)
        chain = _upgrade_chain(_alembic_script(), source_revision_manifest)
        expected_fingerprint = _expected_fingerprint(manifest)
    except (CurrentOperationalMigrationError, RecoverySafetyError) as exc:
        code = exc.code
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "operational_source_migration_0034_0042",
                    "blocker": code,
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
                    "mode": "operational_source_migration_0034_0042",
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

    fingerprint_before = None
    source_documents_before: dict[str, object] | None = None
    frozen_before: dict[str, dict[str, object]] | None = None

    try:
        actual_database_before = await _current_database(engine)
        if actual_database_before != _EXPECTED_SOURCE_DATABASE:
            raise CurrentOperationalMigrationError("database_identity_mismatch")

        revision_before = await _migration_revision(engine)
        fingerprint_before = await database_fingerprint(engine)
        source_documents_before = await _source_documents_fingerprint(engine)
        frozen_before = await _frozen_table_fingerprints(engine)

        if revision_before != _EXPECTED_SOURCE_REVISION:
            raise CurrentOperationalMigrationError("source_revision_drift")
        if fingerprint_before.to_dict() != expected_fingerprint:
            raise CurrentOperationalMigrationError("source_fingerprint_drift")
        if source_documents_before != {
            "count": args.expected_source_documents_count,
            "sha256": args.expected_source_documents_sha256,
        }:
            raise CurrentOperationalMigrationError("source_documents_drift")

        _require_no_future_schema(await _schema_objects(engine))

        migration_attempted = True
        _run_source_upgrade(source)

        actual_database_after = await _current_database(engine)
        revision_after = await _migration_revision(engine)
        fingerprint_after = await database_fingerprint(engine)
        source_documents_after = await _source_documents_fingerprint(engine)
        frozen_after = await _frozen_table_fingerprints(engine)

        if actual_database_after != _EXPECTED_SOURCE_DATABASE:
            raise CurrentOperationalMigrationError("database_identity_mismatch")
        if revision_after != _EXPECTED_TARGET_REVISION:
            raise CurrentOperationalMigrationError("migrated_revision_mismatch")
        if fingerprint_after != fingerprint_before:
            raise CurrentOperationalMigrationError("core_fingerprint_changed_by_migration")
        if source_documents_after != source_documents_before:
            raise CurrentOperationalMigrationError(
                "source_documents_changed_by_migration"
            )
        if frozen_after != frozen_before:
            raise CurrentOperationalMigrationError(
                "operational_telemetry_changed_by_migration"
            )

        schema_objects = await _schema_objects(engine)
        _require_expected_schema(schema_objects)
        runtime_after = _runtime_guard()

        result_payload = {
            "mode": "operational_source_migration_0034_0042",
            "checkout": checkout,
            "runtime_before": runtime_before,
            "runtime_after": runtime_after,
            "source_database": source.database,
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
            "frozen_tables_before": frozen_before,
            "frozen_tables_after": frozen_after,
            "schema_objects": schema_objects,
            "application_runtime": "STOPPED",
        }
    except CurrentOperationalMigrationError as exc:
        blocker = exc.code
    except Exception:
        blocker = "operational_migration_unexpected_failure"
    finally:
        if migration_attempted and blocker is not None:
            try:
                failure_revision = await _migration_revision(engine)
                failure_fingerprint = await database_fingerprint(engine)
                failure_source_documents = await _source_documents_fingerprint(engine)
                failure_frozen = await _frozen_table_fingerprints(engine)
                result_payload["failure_state"] = {
                    "revision": failure_revision,
                    "core_fingerprint": failure_fingerprint.to_dict(),
                    "source_documents": failure_source_documents,
                    "frozen_tables": failure_frozen,
                }
                if (
                    fingerprint_before is not None
                    and failure_fingerprint != fingerprint_before
                    and blocker != "core_fingerprint_changed_by_migration"
                ):
                    secondary_blockers.append("core_fingerprint_changed_by_migration")
                if (
                    source_documents_before is not None
                    and failure_source_documents != source_documents_before
                    and blocker != "source_documents_changed_by_migration"
                ):
                    secondary_blockers.append(
                        "source_documents_changed_by_migration"
                    )
                if (
                    frozen_before is not None
                    and failure_frozen != frozen_before
                    and blocker != "operational_telemetry_changed_by_migration"
                ):
                    secondary_blockers.append(
                        "operational_telemetry_changed_by_migration"
                    )
            except Exception:
                secondary_blockers.append("post_migration_source_verification_failed")

        try:
            _runtime_guard()
        except CurrentOperationalMigrationError as exc:
            if blocker is None:
                blocker = exc.code
            elif exc.code != blocker:
                secondary_blockers.append(exc.code)

        await engine.dispose()

    if blocker is not None:
        print(
            json.dumps(
                _final_document(
                    status="BLOCKED",
                    payload=result_payload,
                    blocker=blocker,
                    secondary_blockers=secondary_blockers,
                    migration_attempted=migration_attempted,
                ),
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    result_payload["secondary_blockers"] = secondary_blockers
    print(
        json.dumps(
            _final_document(status="READY", payload=result_payload),
            sort_keys=True,
            indent=2,
        )
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
