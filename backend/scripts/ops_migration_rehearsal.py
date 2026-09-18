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

_EXPECTED_SOURCE_REVISION = "20260914_0027"
_EXPECTED_TARGET_REVISION = "20260915_0034"
_EXPECTED_DUMP_SHA256 = "488ce3bfdc8978f8343e2f2803dd79e17db269ab77221d87a46afb520a98a1d9"
_EXPECTED_UPGRADE_CHAIN = (
    "20260915_0028",
    "20260915_0029",
    "20260915_0030",
    "20260915_0031",
    "20260915_0032",
    "20260915_0033",
    "20260915_0034",
)
_EXPECTED_TABLES = (
    "topic_nodes",
    "topic_edges",
    "knowledge_topic_links",
    "source_document_observations",
    "freshness_policies",
    "freshness_assignments",
    "freshness_verifications",
    "knowledge_harvests",
    "knowledge_coverage_plans",
    "knowledge_briefs",
    "journal_knowledge_brief_bindings",
    "model_route_decisions",
)
_EXPECTED_FUNCTIONS = (
    "validate_topic_edge_scope",
    "validate_knowledge_topic_link_scope",
    "validate_source_document_observation",
    "enforce_freshness_policy_lifecycle",
    "validate_freshness_assignment",
    "validate_freshness_verification",
    "validate_knowledge_harvest",
    "validate_knowledge_coverage_plan",
    "validate_knowledge_brief",
    "validate_journal_knowledge_brief_binding",
    "validate_model_route_decision",
    "protect_routed_model_call_identity",
)
_EXPECTED_TRIGGERS = {
    "topic_edges_scope_guard": "topic_edges",
    "knowledge_topic_links_scope_guard": "knowledge_topic_links",
    "source_document_observations_guard": "source_document_observations",
    "freshness_policies_lifecycle_guard": "freshness_policies",
    "freshness_assignments_guard": "freshness_assignments",
    "freshness_verifications_guard": "freshness_verifications",
    "knowledge_harvests_guard": "knowledge_harvests",
    "knowledge_coverage_plans_guard": "knowledge_coverage_plans",
    "knowledge_briefs_guard": "knowledge_briefs",
    "journal_knowledge_brief_binding_guard": "journal_knowledge_brief_bindings",
    "model_route_decisions_guard": "model_route_decisions",
    "routed_model_calls_guard": "model_calls",
}


class MigrationRehearsalError(RuntimeError):
    """Raised when isolated migration rehearsal cannot prove a safe result."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore an operational backup, migrate only the disposable DB, and verify it"
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument("--manifest", type=Path)
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
        raise MigrationRehearsalError("backup_or_manifest_missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationRehearsalError("manifest_invalid") from exc
    if not isinstance(manifest, dict):
        raise MigrationRehearsalError("manifest_invalid")
    if manifest.get("format_version") != 2:
        raise MigrationRehearsalError("manifest_format_v2_required")
    actual_dump_sha256 = _sha256(backup)
    if manifest.get("dump_sha256") != actual_dump_sha256:
        raise MigrationRehearsalError("backup_hash_mismatch")
    if actual_dump_sha256 != _EXPECTED_DUMP_SHA256:
        raise MigrationRehearsalError("unexpected_o1_1_backup_hash")
    fingerprint = manifest.get("fingerprint")
    if not isinstance(fingerprint, dict):
        raise MigrationRehearsalError("manifest_fingerprint_missing")
    return manifest


def _manifest_source_revision(manifest: dict[str, object], source: URL) -> str:
    if manifest.get("source_database") != source.database:
        raise MigrationRehearsalError("manifest_source_database_mismatch")
    if manifest.get("source_host") != (source.host or "").lower():
        raise MigrationRehearsalError("manifest_source_host_mismatch")
    if manifest.get("source_port") != (source.port or 5432):
        raise MigrationRehearsalError("manifest_source_port_mismatch")
    revision = manifest.get("source_migration_revision")
    if not isinstance(revision, str) or not revision:
        raise MigrationRehearsalError("manifest_migration_revision_missing")
    if revision != _EXPECTED_SOURCE_REVISION:
        raise MigrationRehearsalError("unexpected_source_migration_revision")
    return revision


def _alembic_script() -> ScriptDirectory:
    config = Config(str(_backend_root() / "alembic.ini"))
    return ScriptDirectory.from_config(config)


def _upgrade_chain(script: ScriptDirectory, source_revision: str) -> tuple[str, ...]:
    head = script.get_current_head()
    if head != _EXPECTED_TARGET_REVISION:
        raise MigrationRehearsalError("unexpected_code_migration_head")
    revision = script.get_revision(head)
    if revision is None:
        raise MigrationRehearsalError("code_migration_head_missing")

    reverse_path: list[str] = []
    while revision.revision != source_revision:
        reverse_path.append(revision.revision)
        down_revision = revision.down_revision
        if not isinstance(down_revision, str):
            raise MigrationRehearsalError("migration_chain_not_linear")
        revision = script.get_revision(down_revision)
        if revision is None:
            raise MigrationRehearsalError("source_revision_not_in_chain")

    path = tuple(reversed(reverse_path))
    if path != _EXPECTED_UPGRADE_CHAIN:
        raise MigrationRehearsalError("unexpected_migration_chain")
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
    revision = await _migration_revision(engine)
    fingerprint = await database_fingerprint(engine)
    return revision, fingerprint


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
    payload = "\n".join(
        ":".join(str(value) for value in row)
        for row in rows
    ).encode("utf-8")
    return {
        "count": len(rows),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


async def _recreate_database(target: URL) -> None:
    database_name = target.database
    if database_name is None:
        raise MigrationRehearsalError("unsafe_rehearsal_database_name")
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
        raise MigrationRehearsalError("pg_restore_unavailable")
    container_mode = capability.mode == "container"
    connection_args, env = _pg_connection_args(target, container_mode=container_mode)
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
        raise MigrationRehearsalError("pg_restore_failed")
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
            _EXPECTED_TARGET_REVISION,
        ],
        cwd=_backend_root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise MigrationRehearsalError("alembic_upgrade_failed")


async def _verify_backfill(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as connection:
        source_documents = int(
            (
                await connection.execute(text("select count(*) from source_documents"))
            ).scalar_one()
        )
        backfill_observations = int(
            (
                await connection.execute(
                    text(
                        "select count(*) from source_document_observations "
                        "where observation_method = 'migration_backfill'"
                    )
                )
            ).scalar_one()
        )
        missing_or_mismatched = int(
            (
                await connection.execute(
                    text(
                        """
                        select count(*)
                        from source_documents sd
                        left join source_document_observations sdo
                          on sdo.source_document_id = sd.id
                         and sdo.observation_method = 'migration_backfill'
                         and sdo.observed_at = sd.fetched_at
                         and sdo.content_hash = sd.content_hash
                         and sdo.provider is not distinct from sd.provider
                         and sdo.reader is not distinct from sd.reader
                        where sdo.id is null
                        """
                    )
                )
            ).scalar_one()
        )
        orphan_or_mismatched = int(
            (
                await connection.execute(
                    text(
                        """
                        select count(*)
                        from source_document_observations sdo
                        left join source_documents sd
                          on sd.id = sdo.source_document_id
                        where sdo.observation_method = 'migration_backfill'
                          and (
                            sd.id is null
                            or sdo.observed_at is distinct from sd.fetched_at
                            or sdo.content_hash is distinct from sd.content_hash
                            or sdo.provider is distinct from sd.provider
                            or sdo.reader is distinct from sd.reader
                          )
                        """
                    )
                )
            ).scalar_one()
        )

    if backfill_observations != source_documents:
        raise MigrationRehearsalError("freshness_backfill_count_mismatch")
    if missing_or_mismatched != 0 or orphan_or_mismatched != 0:
        raise MigrationRehearsalError("freshness_backfill_content_mismatch")

    return {
        "source_documents": source_documents,
        "migration_backfill_observations": backfill_observations,
        "missing_or_mismatched": missing_or_mismatched,
        "orphan_or_mismatched": orphan_or_mismatched,
    }


async def _verify_schema_objects(engine: AsyncEngine) -> dict[str, list[str]]:
    missing_tables: list[str] = []
    missing_functions: list[str] = []
    missing_triggers: list[str] = []

    async with engine.connect() as connection:
        for table_name in _EXPECTED_TABLES:
            exists = (
                await connection.execute(
                    text("select to_regclass(:qualified_name)"),
                    {"qualified_name": f"public.{table_name}"},
                )
            ).scalar_one()
            if exists is None:
                missing_tables.append(table_name)

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
            if not exists:
                missing_functions.append(function_name)

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
            if not exists:
                missing_triggers.append(f"{table_name}.{trigger_name}")

    if missing_tables:
        raise MigrationRehearsalError("migration_tables_missing")
    if missing_functions:
        raise MigrationRehearsalError("migration_functions_missing")
    if missing_triggers:
        raise MigrationRehearsalError("migration_triggers_missing")

    return {
        "tables": list(_EXPECTED_TABLES),
        "functions": list(_EXPECTED_FUNCTIONS),
        "triggers": [
            f"{table}.{trigger}" for trigger, table in _EXPECTED_TRIGGERS.items()
        ],
    }


def _expected_fingerprint(manifest: dict[str, object]) -> dict[str, object]:
    fingerprint = manifest.get("fingerprint")
    if not isinstance(fingerprint, dict):
        raise MigrationRehearsalError("manifest_fingerprint_missing")
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
        raise MigrationRehearsalError("manifest_fingerprint_shape_invalid")
    return fingerprint


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
    except MigrationRehearsalError as exc:
        print(json.dumps({"status": "BLOCKED", "blocker": exc.code}, indent=2))
        return 2

    settings = get_settings()
    if settings.app_env.strip().lower() == "test":
        print(
            json.dumps(
                {"status": "BLOCKED", "blocker": "test_environment_not_operational"},
                indent=2,
            )
        )
        return 2

    try:
        source = validate_operational_database_source(settings.database_url)
        source_revision_manifest = _manifest_source_revision(manifest, source)
        chain = _upgrade_chain(_alembic_script(), source_revision_manifest)
        expected_fingerprint = _expected_fingerprint(manifest)
        target_url = source.set(database=f"{source.database}_migration_restore_test")
        target = validate_restore_target(
            source_url=settings.database_url,
            restore_url=target_url.render_as_string(hide_password=False),
        )
    except (MigrationRehearsalError, RecoverySafetyError) as exc:
        code = exc.code
        print(json.dumps({"status": "BLOCKED", "blocker": code}, indent=2))
        return 2

    source_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    target_created = False
    blocker: str | None = None
    result_payload: dict[str, object] = {}
    source_revision_before: str | None = None
    source_fingerprint_before: DatabaseFingerprint | None = None
    source_documents_before: dict[str, object] | None = None
    source_revision_after: str | None = None
    source_fingerprint_after: DatabaseFingerprint | None = None
    source_documents_after: dict[str, object] | None = None

    try:
        source_revision_before, source_fingerprint_before = await _database_state(
            source_engine
        )
        source_documents_before = await _source_documents_fingerprint(source_engine)
        if source_revision_before != _EXPECTED_SOURCE_REVISION:
            raise MigrationRehearsalError("source_revision_drift")
        if source_fingerprint_before.to_dict() != expected_fingerprint:
            raise MigrationRehearsalError("source_fingerprint_drift")

        await _recreate_database(target)
        target_created = True
        restore_mode = _restore_backup(backup, target)

        target_engine = create_async_engine(target, poolclass=NullPool)
        try:
            restored_revision, restored_fingerprint = await _database_state(target_engine)
            restored_source_documents = await _source_documents_fingerprint(target_engine)
            if restored_revision != _EXPECTED_SOURCE_REVISION:
                raise MigrationRehearsalError("restored_source_revision_mismatch")
            if restored_fingerprint.to_dict() != expected_fingerprint:
                raise MigrationRehearsalError("restored_source_fingerprint_mismatch")
            if restored_source_documents != source_documents_before:
                raise MigrationRehearsalError("source_documents_drift_from_backup")

            _run_alembic_upgrade(target)

            migrated_revision, migrated_fingerprint = await _database_state(target_engine)
            if migrated_revision != _EXPECTED_TARGET_REVISION:
                raise MigrationRehearsalError("migrated_revision_mismatch")
            if migrated_fingerprint.to_dict() != expected_fingerprint:
                raise MigrationRehearsalError("core_fingerprint_changed_by_migration")

            backfill = await _verify_backfill(target_engine)
            schema_objects = await _verify_schema_objects(target_engine)
        finally:
            await target_engine.dispose()

        source_revision_after, source_fingerprint_after = await _database_state(source_engine)
        source_documents_after = await _source_documents_fingerprint(source_engine)
        if source_revision_after != source_revision_before:
            raise MigrationRehearsalError("source_revision_changed")
        if source_fingerprint_after != source_fingerprint_before:
            raise MigrationRehearsalError("source_fingerprint_changed")
        if source_documents_after != source_documents_before:
            raise MigrationRehearsalError("source_documents_changed")

        result_payload = {
            "status": "READY",
            "mode": "isolated_migration_rehearsal",
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
            "restored_source_documents_fingerprint": restored_source_documents,
            "target_revision": migrated_revision,
            "upgrade_chain": list(chain),
            "core_fingerprint_after_migration": migrated_fingerprint.to_dict(),
            "backfill": backfill,
            "schema_objects": schema_objects,
        }
    except MigrationRehearsalError as exc:
        blocker = exc.code
    except Exception:
        blocker = "migration_rehearsal_unexpected_failure"
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
                if source_revision_after != source_revision_before:
                    blocker = "source_revision_changed"
                elif source_fingerprint_after != source_fingerprint_before:
                    blocker = "source_fingerprint_changed"
                elif source_documents_after != source_documents_before:
                    blocker = "source_documents_changed"
            except Exception:
                blocker = "source_post_rehearsal_verification_failed"
        await source_engine.dispose()
        cleanup_error: str | None = None
        if target_created:
            try:
                await _drop_database(target)
            except Exception:
                cleanup_error = "rehearsal_database_cleanup_failed"
        if cleanup_error is not None:
            blocker = cleanup_error

    if blocker is not None:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "isolated_migration_rehearsal",
                    "blocker": blocker,
                    "rehearsal_database": target.database,
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    result_payload["rehearsal_database_cleanup"] = "DROPPED"
    print(json.dumps(result_payload, sort_keys=True, indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
