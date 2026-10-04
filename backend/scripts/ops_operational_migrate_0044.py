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
from app.modules.system.recovery import RecoverySafetyError, validate_operational_database_source
from app.modules.system.runtime_maintenance import (
    RuntimeMaintenanceError,
    release_maintenance_exclusive,
    try_acquire_maintenance_exclusive,
)
from scripts.ops_data02_rehearsal import (
    Data02RehearsalError,
    _EXPECTED_UPGRADE_CHAIN,
    _SOURCE_REVISION,
    _TARGET_REVISION,
    _alembic_script,
    _database_state,
    _expected_fingerprint,
    _full_data_fingerprint,
    _load_manifest,
    _manifest_source_revision,
    _sha256,
    _source_documents_fingerprint,
    _upgrade_chain,
)

_EXPECTED_SOURCE_DATABASE = "contentengine"
_RUNTIME_PORTS = (8000, 3000)
_FROZEN_TABLES = (
    "jobs",
    "step_runs",
    "model_calls",
    "tool_calls",
    "outbox_intents",
)
_PROMPT_KEYS = (
    "journal_coverage_support_depth_en",
    "journal_coverage_support_depth_vi",
)
_RECIPE_KEYS = (
    "journal_coverage_support_depth_en_v1",
    "journal_coverage_support_depth_vi_v1",
)
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OperationalMigration0044Error(RuntimeError):
    """Raised when the bounded 0034 -> 0044 operational contract is unsafe."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed operational migration from ContentEngine rev-0034 "
            "to rev-0044 using an exact fresh recovery point"
        )
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--authorized-head", required=True)
    parser.add_argument("--expected-dump-sha256", required=True)
    parser.add_argument("--expected-source-documents-count", type=int, required=True)
    parser.add_argument("--expected-source-documents-sha256", required=True)
    parser.add_argument("--expected-source-full-data-sha256", required=True)
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
        raise OperationalMigration0044Error("git_state_unavailable")
    return result.stdout.strip()


def _validate_authorized_checkout(authorized_head: str) -> dict[str, object]:
    if not _FULL_SHA.fullmatch(authorized_head):
        raise OperationalMigration0044Error("authorized_head_invalid")
    actual_head = _run_git("rev-parse", "HEAD")
    if actual_head != authorized_head:
        raise OperationalMigration0044Error("authorized_head_mismatch")
    if _run_git("status", "--porcelain") != "":
        raise OperationalMigration0044Error("migration_checkout_dirty")
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
    if 8000 in active_ports:
        raise OperationalMigration0044Error("backend_runtime_active")
    if 3000 in active_ports:
        raise OperationalMigration0044Error("frontend_runtime_active")
    return {
        "backend_port_8000": "STOPPED",
        "frontend_port_3000": "STOPPED",
    }


def _load_authorized_manifest(
    backup: Path,
    manifest_path: Path,
    *,
    expected_dump_sha256: str,
) -> dict[str, object]:
    if not _SHA256.fullmatch(expected_dump_sha256):
        raise OperationalMigration0044Error("expected_dump_sha256_invalid")
    try:
        manifest = _load_manifest(backup, manifest_path)
        actual_dump_sha256 = _sha256(backup)
    except Data02RehearsalError as exc:
        raise OperationalMigration0044Error(exc.code) from exc
    except OSError as exc:
        raise OperationalMigration0044Error("backup_hash_unavailable") from exc
    if actual_dump_sha256 != expected_dump_sha256:
        raise OperationalMigration0044Error("authorized_backup_hash_mismatch")
    if manifest.get("dump_sha256") != expected_dump_sha256:
        raise OperationalMigration0044Error("backup_hash_mismatch")
    return manifest


def _validate_expected_source_fingerprints(
    *,
    expected_source_documents_count: int,
    expected_source_documents_sha256: str,
    expected_source_full_data_sha256: str,
) -> None:
    if expected_source_documents_count < 0:
        raise OperationalMigration0044Error("expected_source_documents_count_invalid")
    if not _SHA256.fullmatch(expected_source_documents_sha256):
        raise OperationalMigration0044Error("expected_source_documents_sha256_invalid")
    if not _SHA256.fullmatch(expected_source_full_data_sha256):
        raise OperationalMigration0044Error("expected_source_full_data_sha256_invalid")


async def _current_database(engine: AsyncEngine) -> str:
    async with engine.connect() as connection:
        value = (await connection.execute(text("select current_database()"))).scalar_one()
    return str(value)


async def _table_fingerprint(
    engine: AsyncEngine,
    *,
    table_name: str,
) -> dict[str, object]:
    if table_name not in _FROZEN_TABLES:
        raise OperationalMigration0044Error("unsupported_table_fingerprint")
    async with engine.connect() as connection:
        rows = [
            str(value)
            for value in (
                await connection.execute(
                    text(f"select row_to_json(t)::text from {table_name} t order by id")
                )
            ).scalars()
        ]
    payload = "\n".join(rows).encode("utf-8")
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


async def _runtime_work_state(engine: AsyncEngine) -> dict[str, int]:
    statements = {
        "queued_or_leased_jobs": (
            "select count(*) from jobs where status in ('queued','leased')"
        ),
        "pending_or_running_steps": (
            "select count(*) from step_runs where status in ('pending','running')"
        ),
        "pending_or_running_runs": (
            "select count(*) from content_runs where status in ('pending','running')"
        ),
        "pending_or_running_model_calls": (
            "select count(*) from model_calls where status in ('pending','running')"
        ),
        "pending_or_running_tool_calls": (
            "select count(*) from tool_calls where status in ('pending','running')"
        ),
        "active_outbox_intents": (
            "select count(*) from outbox_intents "
            "where status in ('pending','processing','needs_reconciliation')"
        ),
    }
    async with engine.connect() as connection:
        return {
            key: int((await connection.execute(text(statement))).scalar_one())
            for key, statement in statements.items()
        }


def _require_quiescent(state: dict[str, int]) -> None:
    active = {key: value for key, value in state.items() if value != 0}
    if active:
        raise OperationalMigration0044Error("operational_runtime_not_quiescent")


def _run_source_upgrade(source: URL) -> None:
    if source.database != _EXPECTED_SOURCE_DATABASE:
        raise OperationalMigration0044Error("unexpected_operational_database")
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
            _TARGET_REVISION,
        ],
        cwd=_backend_root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise OperationalMigration0044Error("alembic_upgrade_failed")


async def _post_0044_contract(engine: AsyncEngine) -> dict[str, object]:
    async with engine.connect() as connection:
        publication_tables = {
            table_name: (
                await connection.execute(
                    text("select to_regclass(:qualified_name)"),
                    {"qualified_name": f"public.{table_name}"},
                )
            ).scalar_one()
            is not None
            for table_name in ("published_contents", "publish_events")
        }
        if not all(publication_tables.values()):
            raise OperationalMigration0044Error("required_publication_tables_missing")

        publication_counts = {
            "published_contents": int(
                (
                    await connection.execute(
                        text("select count(*) from published_contents")
                    )
                ).scalar_one()
            ),
            "publish_events": int(
                (
                    await connection.execute(text("select count(*) from publish_events"))
                ).scalar_one()
            ),
        }
        if any(publication_counts.values()):
            raise OperationalMigration0044Error("publication_rows_created_by_migration")

        coverage_column = (
            await connection.execute(
                text(
                    """
                    select is_nullable
                    from information_schema.columns
                    where table_schema = 'public'
                      and table_name = 'content_opportunities'
                      and column_name = 'coverage_requirements_json'
                    """
                )
            )
        ).scalar_one_or_none()
        if coverage_column != "NO":
            raise OperationalMigration0044Error("coverage_requirements_column_invalid")

        null_coverage = int(
            (
                await connection.execute(
                    text(
                        "select count(*) from content_opportunities "
                        "where coverage_requirements_json is null"
                    )
                )
            ).scalar_one()
        )
        if null_coverage != 0:
            raise OperationalMigration0044Error("coverage_requirements_backfill_invalid")

        prompt_rows = list(
            (
                await connection.execute(
                    text(
                        """
                        select prompt_key, version, status
                        from prompt_definitions
                        where prompt_key in (
                            'journal_coverage_support_depth_en',
                            'journal_coverage_support_depth_vi'
                        )
                        order by prompt_key, version
                        """
                    )
                )
            ).all()
        )
        expected_prompts = {(key, 1, "active") for key in _PROMPT_KEYS}
        if set(prompt_rows) != expected_prompts:
            raise OperationalMigration0044Error("coverage_support_prompt_seed_invalid")

        recipe_rows = list(
            (
                await connection.execute(
                    text(
                        """
                        select recipe_key, version, status
                        from recipe_definitions
                        where recipe_key in (
                            'journal_coverage_support_depth_en_v1',
                            'journal_coverage_support_depth_vi_v1'
                        )
                        order by recipe_key, version
                        """
                    )
                )
            ).all()
        )
        expected_recipes = {(key, 1, "active") for key in _RECIPE_KEYS}
        if set(recipe_rows) != expected_recipes:
            raise OperationalMigration0044Error("coverage_support_recipe_seed_invalid")

    return {
        "publication_tables": publication_tables,
        "publication_counts": publication_counts,
        "coverage_requirements_null_rows": null_coverage,
        "coverage_support_prompts": [list(row) for row in prompt_rows],
        "coverage_support_recipes": [list(row) for row in recipe_rows],
    }


def _final_document(
    *,
    status: str,
    payload: dict[str, object],
    blocker: str | None = None,
    secondary_blockers: list[str] | None = None,
    migration_attempted: bool | None = None,
) -> dict[str, object]:
    result = dict(payload)
    result["status"] = status
    if blocker is not None:
        result["blocker"] = blocker
    if secondary_blockers is not None:
        result["secondary_blockers"] = list(secondary_blockers)
    if migration_attempted is not None:
        result["migration_attempted"] = migration_attempted
    return result


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
        _validate_expected_source_fingerprints(
            expected_source_documents_count=args.expected_source_documents_count,
            expected_source_documents_sha256=args.expected_source_documents_sha256,
            expected_source_full_data_sha256=args.expected_source_full_data_sha256,
        )
        manifest = _load_authorized_manifest(
            backup,
            manifest_path,
            expected_dump_sha256=args.expected_dump_sha256,
        )
        settings = get_settings()
        if settings.app_env.strip().lower() == "test":
            raise OperationalMigration0044Error("test_environment_not_operational")
        source = validate_operational_database_source(settings.database_url)
        if source.database != _EXPECTED_SOURCE_DATABASE:
            raise OperationalMigration0044Error("unexpected_operational_database")
        source_revision_manifest = _manifest_source_revision(manifest, source)
        chain = _upgrade_chain(_alembic_script(), source_revision_manifest)
        if chain != _EXPECTED_UPGRADE_CHAIN:
            raise OperationalMigration0044Error("unexpected_migration_chain")
        expected_fingerprint = _expected_fingerprint(manifest)
    except (OperationalMigration0044Error, Data02RehearsalError) as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "operational_source_migration_0034_0044",
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
                    "mode": "operational_source_migration_0034_0044",
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
                    "mode": "operational_source_migration_0034_0044",
                    "blocker": "operational_migration_0044_preflight_failed",
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
    exclusive_lock_acquired = False
    evidence: dict[str, object] = {
        "mode": "operational_source_migration_0034_0044",
        "checkout": checkout,
        "runtime_before": runtime_before,
        "source_database": source.database,
        "backup": str(backup),
        "manifest": str(manifest_path),
        "dump_sha256": manifest.get("dump_sha256"),
        "upgrade_chain": list(chain),
    }

    revision_before: str | None = None
    core_before = None
    source_documents_before: dict[str, object] | None = None
    full_data_before: dict[str, object] | None = None
    frozen_before: dict[str, dict[str, object]] | None = None

    try:
        actual_database = await _current_database(engine)
        if actual_database != _EXPECTED_SOURCE_DATABASE:
            raise OperationalMigration0044Error("database_identity_mismatch")

        revision_before, core_before = await _database_state(engine)
        source_documents_before = await _source_documents_fingerprint(engine)
        full_data_before = await _full_data_fingerprint(engine)
        frozen_before = await _frozen_table_fingerprints(engine)
        runtime_work_before = await _runtime_work_state(engine)

        if revision_before != _SOURCE_REVISION:
            raise OperationalMigration0044Error("source_revision_drift")
        if core_before.to_dict() != expected_fingerprint:
            raise OperationalMigration0044Error("source_fingerprint_drift")
        if source_documents_before != {
            "count": args.expected_source_documents_count,
            "sha256": args.expected_source_documents_sha256,
        }:
            raise OperationalMigration0044Error("source_documents_drift")
        if full_data_before.get("sha256") != args.expected_source_full_data_sha256:
            raise OperationalMigration0044Error("source_full_data_drift")
        _require_quiescent(runtime_work_before)

        async with engine.connect() as maintenance_connection:
            exclusive_lock_acquired = await try_acquire_maintenance_exclusive(
                maintenance_connection
            )
            if not exclusive_lock_acquired:
                raise OperationalMigration0044Error("worker_runtime_active")

            try:
                runtime_during_lock = await _runtime_work_state(engine)
                _require_quiescent(runtime_during_lock)
                runtime_locked = _runtime_guard()

                evidence.update(
                    {
                        "revision_before": revision_before,
                        "core_fingerprint_before": core_before.to_dict(),
                        "source_documents_before": source_documents_before,
                        "source_full_data_before": {
                            "table_count": full_data_before["table_count"],
                            "row_count": full_data_before["row_count"],
                            "sha256": full_data_before["sha256"],
                        },
                        "frozen_tables_before": frozen_before,
                        "runtime_work_before": runtime_work_before,
                        "runtime_work_during_lock": runtime_during_lock,
                        "runtime_locked": runtime_locked,
                        "maintenance_gate": "EXCLUSIVE",
                    }
                )

                migration_attempted = True
                _run_source_upgrade(source)

                revision_after, core_after = await _database_state(engine)
                source_documents_after = await _source_documents_fingerprint(engine)
                frozen_after = await _frozen_table_fingerprints(engine)
                runtime_work_after = await _runtime_work_state(engine)
                post_contract = await _post_0044_contract(engine)

                if revision_after != _TARGET_REVISION:
                    raise OperationalMigration0044Error("migrated_revision_mismatch")
                if core_after != core_before:
                    raise OperationalMigration0044Error(
                        "core_fingerprint_changed_by_migration"
                    )
                if source_documents_after != source_documents_before:
                    raise OperationalMigration0044Error(
                        "source_documents_changed_by_migration"
                    )
                if frozen_after != frozen_before:
                    raise OperationalMigration0044Error(
                        "frozen_runtime_tables_changed_by_migration"
                    )
                _require_quiescent(runtime_work_after)

                evidence.update(
                    {
                        "revision_after": revision_after,
                        "core_fingerprint_after": core_after.to_dict(),
                        "source_documents_after": source_documents_after,
                        "frozen_tables_after": frozen_after,
                        "runtime_work_after": runtime_work_after,
                        "post_0044_contract": post_contract,
                        "runtime_after": _runtime_guard(),
                        "application_runtime": "STOPPED",
                    }
                )
            finally:
                if exclusive_lock_acquired:
                    await release_maintenance_exclusive(maintenance_connection)
                    exclusive_lock_acquired = False
    except (
        OperationalMigration0044Error,
        Data02RehearsalError,
        RuntimeMaintenanceError,
    ) as exc:
        blocker = exc.code
    except Exception:
        blocker = "operational_migration_0044_unexpected_failure"
    finally:
        if migration_attempted and blocker is not None:
            try:
                revision_final, core_final = await _database_state(engine)
                source_documents_final = await _source_documents_fingerprint(engine)
                frozen_final = await _frozen_table_fingerprints(engine)
                runtime_work_final = await _runtime_work_state(engine)
                evidence["failure_state"] = {
                    "revision": revision_final,
                    "core_fingerprint": core_final.to_dict(),
                    "source_documents": source_documents_final,
                    "frozen_tables": frozen_final,
                    "runtime_work": runtime_work_final,
                }
                if core_before is not None and core_final != core_before:
                    secondary_blockers.append("core_fingerprint_changed_by_migration")
                if (
                    source_documents_before is not None
                    and source_documents_final != source_documents_before
                ):
                    secondary_blockers.append("source_documents_changed_by_migration")
                if frozen_before is not None and frozen_final != frozen_before:
                    secondary_blockers.append(
                        "frozen_runtime_tables_changed_by_migration"
                    )
            except Exception:
                secondary_blockers.append("post_migration_source_verification_failed")

        try:
            _runtime_guard()
        except OperationalMigration0044Error as exc:
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
                    payload=evidence,
                    blocker=blocker,
                    secondary_blockers=secondary_blockers,
                    migration_attempted=migration_attempted,
                ),
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    evidence["secondary_blockers"] = secondary_blockers
    print(
        json.dumps(
            _final_document(status="READY", payload=evidence),
            sort_keys=True,
            indent=2,
        )
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()