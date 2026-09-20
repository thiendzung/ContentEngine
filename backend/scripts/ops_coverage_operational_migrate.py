from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.recovery import RecoverySafetyError, validate_operational_database_source
from scripts.ops_backup import _model_calls_fingerprint, _source_documents_fingerprint
from scripts.ops_coverage_migration_rehearsal import (
    _EXPECTED_SOURCE_REVISION,
    _EXPECTED_TARGET_REVISION,
    CoverageMigrationError,
    _assert_coverage_absent,
    _coverage_future_state,
    _fingerprint_field,
    _load_manifest,
    _manifest_source_revision,
    _registry_v1_fingerprint,
    _upgrade_chain,
    _verify_coverage_seed,
)
from scripts.ops_migration_rehearsal import (
    MigrationRehearsalError,
    _database_state,
    _expected_fingerprint,
    _verify_backfill,
    _verify_schema_objects,
)
from scripts.ops_operational_migrate import (
    _current_database,
    _final_document,
    _runtime_guard,
    _validate_authorized_checkout,
)

_EXPECTED_SOURCE_DATABASE = "contentengine"


class CoverageOperationalMigrationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed operational migration from exact rev-0034 to rev-0035 "
            "after a successful isolated coverage migration rehearsal"
        )
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--authorized-head", required=True)
    return parser.parse_args()


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_source_upgrade(source: URL) -> None:
    if source.database != _EXPECTED_SOURCE_DATABASE:
        raise CoverageOperationalMigrationError("unexpected_operational_database")
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
        raise CoverageOperationalMigrationError("alembic_upgrade_failed")


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
            raise CoverageOperationalMigrationError("test_environment_not_operational")
        source = validate_operational_database_source(settings.database_url)
        if source.database != _EXPECTED_SOURCE_DATABASE:
            raise CoverageOperationalMigrationError("unexpected_operational_database")
        source_revision = _manifest_source_revision(manifest, source)
        chain = _upgrade_chain(source_revision)
        expected_core = _expected_fingerprint(manifest)
        expected_documents = _fingerprint_field(
            manifest,
            "source_documents_fingerprint",
        )
        expected_model_calls = _fingerprint_field(
            manifest,
            "model_calls_fingerprint",
        )
    except (
        CoverageMigrationError,
        CoverageOperationalMigrationError,
        MigrationRehearsalError,
        RecoverySafetyError,
    ) as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "coverage_operational_migration",
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
                    "mode": "coverage_operational_migration",
                    "blocker": "coverage_operational_migration_preflight_failed",
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
    core_before = None
    documents_before: dict[str, object] | None = None
    model_calls_before: dict[str, object] | None = None
    registry_before: dict[str, object] | None = None

    try:
        actual_database_before = await _current_database(engine)
        if actual_database_before != _EXPECTED_SOURCE_DATABASE:
            raise CoverageOperationalMigrationError("database_identity_mismatch")

        revision_before, core_before = await _database_state(engine)
        documents_before = await _source_documents_fingerprint(engine)
        model_calls_before = await _model_calls_fingerprint(engine)
        registry_before = await _registry_v1_fingerprint(engine)
        future_before = await _coverage_future_state(engine)

        if revision_before != _EXPECTED_SOURCE_REVISION:
            raise CoverageOperationalMigrationError("source_revision_drift")
        if core_before.to_dict() != expected_core:
            raise CoverageOperationalMigrationError("source_fingerprint_drift")
        if documents_before != expected_documents:
            raise CoverageOperationalMigrationError("source_documents_drift_from_backup")
        if model_calls_before != expected_model_calls:
            raise CoverageOperationalMigrationError("model_calls_drift_from_backup")
        _assert_coverage_absent(future_before)

        migration_attempted = True
        _run_source_upgrade(source)

        actual_database_after = await _current_database(engine)
        if actual_database_after != _EXPECTED_SOURCE_DATABASE:
            raise CoverageOperationalMigrationError("database_identity_mismatch")

        revision_after, core_after = await _database_state(engine)
        documents_after = await _source_documents_fingerprint(engine)
        model_calls_after = await _model_calls_fingerprint(engine)
        registry_after = await _registry_v1_fingerprint(engine)

        if revision_after != _EXPECTED_TARGET_REVISION:
            raise CoverageOperationalMigrationError("migrated_revision_mismatch")
        if core_before is None or core_after != core_before:
            raise CoverageOperationalMigrationError("core_fingerprint_changed_by_migration")
        if documents_after != documents_before:
            raise CoverageOperationalMigrationError(
                "source_documents_changed_by_migration"
            )
        if model_calls_after != model_calls_before:
            raise CoverageOperationalMigrationError("model_calls_changed_by_migration")
        if registry_after != registry_before:
            raise CoverageOperationalMigrationError("registry_v1_changed_by_migration")

        backfill = await _verify_backfill(engine)
        schema_objects = await _verify_schema_objects(engine)
        coverage_seed = await _verify_coverage_seed(engine)
        runtime_after = _runtime_guard()

        result_payload = {
            "mode": "coverage_operational_migration",
            "checkout": checkout,
            "runtime_before": runtime_before,
            "runtime_after": runtime_after,
            "application_runtime": "STOPPED",
            "source_database": source.database,
            "actual_database_before": actual_database_before,
            "actual_database_after": actual_database_after,
            "backup": str(backup),
            "manifest": str(manifest_path),
            "dump_sha256": manifest.get("dump_sha256"),
            "revision_before": revision_before,
            "revision_after": revision_after,
            "upgrade_chain": list(chain),
            "core_fingerprint_before": core_before.to_dict(),
            "core_fingerprint_after": core_after.to_dict(),
            "source_documents_before": documents_before,
            "source_documents_after": documents_after,
            "model_calls_before": model_calls_before,
            "model_calls_after": model_calls_after,
            "registry_v1_before": registry_before,
            "registry_v1_after": registry_after,
            "backfill": backfill,
            "schema_objects": schema_objects,
            "coverage_seed": coverage_seed,
        }
    except (
        CoverageMigrationError,
        CoverageOperationalMigrationError,
        MigrationRehearsalError,
    ) as exc:
        blocker = exc.code
    except Exception:
        blocker = "coverage_operational_migration_unexpected_failure"
    finally:
        if migration_attempted and revision_before is not None and blocker is not None:
            try:
                revision_final, core_final = await _database_state(engine)
                documents_final = await _source_documents_fingerprint(engine)
                model_calls_final = await _model_calls_fingerprint(engine)
                registry_final = await _registry_v1_fingerprint(engine)
                result_payload["failure_state"] = {
                    "revision": revision_final,
                    "core_fingerprint": core_final.to_dict(),
                    "source_documents": documents_final,
                    "model_calls": model_calls_final,
                    "registry_v1": registry_final,
                }
                if (
                    core_before is not None
                    and core_final != core_before
                    and blocker != "core_fingerprint_changed_by_migration"
                ):
                    secondary_blockers.append("core_fingerprint_changed_by_migration")
                if (
                    documents_before is not None
                    and documents_final != documents_before
                    and blocker != "source_documents_changed_by_migration"
                ):
                    secondary_blockers.append(
                        "source_documents_changed_by_migration"
                    )
                if (
                    model_calls_before is not None
                    and model_calls_final != model_calls_before
                    and blocker != "model_calls_changed_by_migration"
                ):
                    secondary_blockers.append("model_calls_changed_by_migration")
                if (
                    registry_before is not None
                    and registry_final != registry_before
                    and blocker != "registry_v1_changed_by_migration"
                ):
                    secondary_blockers.append("registry_v1_changed_by_migration")
            except Exception:
                secondary_blockers.append("post_migration_source_verification_failed")

        try:
            _runtime_guard()
        except Exception:
            if blocker is None:
                blocker = "runtime_guard_failed_after_migration"
            else:
                secondary_blockers.append("runtime_guard_failed_after_migration")
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
