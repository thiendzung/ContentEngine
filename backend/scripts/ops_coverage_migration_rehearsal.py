from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.recovery import RecoverySafetyError, validate_operational_database_source, validate_restore_target
from scripts.ops_backup import _model_calls_fingerprint, _source_documents_fingerprint
from scripts.ops_migration_rehearsal import (
    _alembic_script,
    _database_state,
    _drop_database,
    _expected_fingerprint,
    _pg_connection_args,
    _recreate_database,
    _restore_backup,
    _verify_backfill,
    _verify_schema_objects,
)

_EXPECTED_SOURCE_REVISION = "20260915_0034"
_EXPECTED_TARGET_REVISION = "20260920_0035"
_EXPECTED_UPGRADE_CHAIN = ("20260920_0035",)
_ANGLE_PROMPT_ID = "7d90f444-d78e-4bf5-8dc9-7f184f9e4b01"
_ANGLE_RECIPE_ID = "7d90f444-d78e-4bf5-8dc9-7f184f9e4b02"
_OUTLINE_PROMPT_ID = "7d90f444-d78e-4bf5-8dc9-7f184f9e4b03"
_OUTLINE_RECIPE_ID = "7d90f444-d78e-4bf5-8dc9-7f184f9e4b04"


class CoverageMigrationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Restore a fresh rev-0034 operational backup, migrate only the "
            "disposable DB to rev-0035, and verify promise-coverage invariants"
        )
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


def _fingerprint_field(
    manifest: dict[str, object],
    key: str,
) -> dict[str, object]:
    value = manifest.get(key)
    if (
        not isinstance(value, dict)
        or set(value) != {"count", "sha256"}
        or isinstance(value.get("count"), bool)
        or not isinstance(value.get("count"), int)
        or value["count"] < 0
        or not isinstance(value.get("sha256"), str)
        or len(value["sha256"]) != 64
    ):
        raise CoverageMigrationError(f"manifest_{key}_invalid")
    return value


def _load_manifest(
    backup: Path,
    manifest_path: Path,
) -> dict[str, object]:
    if not backup.is_file() or not manifest_path.is_file():
        raise CoverageMigrationError("backup_or_manifest_missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageMigrationError("manifest_invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("format_version") != 2:
        raise CoverageMigrationError("manifest_format_v2_required")
    try:
        actual_hash = _sha256(backup)
    except OSError as exc:
        raise CoverageMigrationError("backup_hash_unavailable") from exc
    if manifest.get("dump_sha256") != actual_hash:
        raise CoverageMigrationError("backup_hash_mismatch")
    _expected_fingerprint(manifest)
    _fingerprint_field(manifest, "source_documents_fingerprint")
    _fingerprint_field(manifest, "model_calls_fingerprint")
    return manifest


def _manifest_source_revision(
    manifest: dict[str, object],
    source: URL,
) -> str:
    if manifest.get("source_database") != source.database:
        raise CoverageMigrationError("manifest_source_database_mismatch")
    if manifest.get("source_host") != (source.host or "").lower():
        raise CoverageMigrationError("manifest_source_host_mismatch")
    if manifest.get("source_port") != (source.port or 5432):
        raise CoverageMigrationError("manifest_source_port_mismatch")
    revision = manifest.get("source_migration_revision")
    if revision != _EXPECTED_SOURCE_REVISION:
        raise CoverageMigrationError("unexpected_source_migration_revision")
    return _EXPECTED_SOURCE_REVISION


def _upgrade_chain(source_revision: str) -> tuple[str, ...]:
    script = _alembic_script()
    head = script.get_current_head()
    if head != _EXPECTED_TARGET_REVISION:
        raise CoverageMigrationError("unexpected_code_migration_head")
    revision = script.get_revision(head)
    if revision is None:
        raise CoverageMigrationError("code_migration_head_missing")

    reverse_path: list[str] = []
    while revision.revision != source_revision:
        reverse_path.append(revision.revision)
        down_revision = revision.down_revision
        if not isinstance(down_revision, str):
            raise CoverageMigrationError("migration_chain_not_linear")
        revision = script.get_revision(down_revision)
        if revision is None:
            raise CoverageMigrationError("source_revision_not_in_chain")

    path = tuple(reversed(reverse_path))
    if path != _EXPECTED_UPGRADE_CHAIN:
        raise CoverageMigrationError("unexpected_migration_chain")
    return path


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
        raise CoverageMigrationError("alembic_upgrade_failed")


async def _registry_v1_fingerprint(engine: AsyncEngine) -> dict[str, object]:
    async with engine.connect() as connection:
        prompt_rows = list(
            (
                await connection.execute(
                    text(
                        """
                        select
                            id::text, prompt_key, version, status,
                            coalesce(approved_by, ''), purpose, body,
                            input_contract_json::text, output_schema_json::text
                        from prompt_definitions
                        where version = 1
                          and prompt_key in ('journal_angle_candidates', 'journal_outline')
                        order by prompt_key
                        """
                    )
                )
            ).all()
        )
        recipe_rows = list(
            (
                await connection.execute(
                    text(
                        """
                        select
                            id::text, recipe_key, version, status,
                            coalesce(approved_by, ''), selector_json::text,
                            recipe_json::text
                        from recipe_definitions
                        where version = 1
                          and recipe_key in ('journal_angle_v1', 'journal_outline_v1')
                        order by recipe_key
                        """
                    )
                )
            ).all()
        )
    rows = [
        ["prompt", *[str(value) for value in row]]
        for row in prompt_rows
    ] + [
        ["recipe", *[str(value) for value in row]]
        for row in recipe_rows
    ]
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "count": len(rows),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


async def _coverage_future_state(engine: AsyncEngine) -> dict[str, object]:
    async with engine.connect() as connection:
        column_exists = bool(
            (
                await connection.execute(
                    text(
                        """
                        select exists(
                            select 1
                            from information_schema.columns
                            where table_schema = 'public'
                              and table_name = 'content_opportunities'
                              and column_name = 'coverage_requirements_json'
                        )
                        """
                    )
                )
            ).scalar_one()
        )
        prompt_count = int(
            (
                await connection.execute(
                    text(
                        """
                        select count(*)
                        from prompt_definitions
                        where id in (
                            cast(:angle AS uuid),
                            cast(:outline AS uuid)
                        )
                        """
                    ),
                    {"angle": _ANGLE_PROMPT_ID, "outline": _OUTLINE_PROMPT_ID},
                )
            ).scalar_one()
        )
        recipe_count = int(
            (
                await connection.execute(
                    text(
                        """
                        select count(*)
                        from recipe_definitions
                        where id in (
                            cast(:angle AS uuid),
                            cast(:outline AS uuid)
                        )
                        """
                    ),
                    {"angle": _ANGLE_RECIPE_ID, "outline": _OUTLINE_RECIPE_ID},
                )
            ).scalar_one()
        )
    return {
        "coverage_column": column_exists,
        "v2_prompt_rows": prompt_count,
        "v2_recipe_rows": recipe_count,
    }


def _assert_coverage_absent(state: dict[str, object]) -> None:
    if (
        state.get("coverage_column") is not False
        or state.get("v2_prompt_rows") != 0
        or state.get("v2_recipe_rows") != 0
    ):
        raise CoverageMigrationError("coverage_future_state_present_before_migration")


async def _verify_coverage_seed(engine: AsyncEngine) -> dict[str, object]:
    async with engine.connect() as connection:
        column = (
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
        invalid_opportunities = int(
            (
                await connection.execute(
                    text(
                        """
                        select count(*)
                        from content_opportunities
                        where coverage_requirements_json is null
                           or json_typeof(coverage_requirements_json) <> 'array'
                        """
                    )
                )
            ).scalar_one()
        )
        prompt_rows = list(
            (
                await connection.execute(
                    text(
                        """
                        select id::text, prompt_key, version, status, approved_by
                        from prompt_definitions
                        where id in (
                            cast(:angle AS uuid),
                            cast(:outline AS uuid)
                        )
                        order by id
                        """
                    ),
                    {"angle": _ANGLE_PROMPT_ID, "outline": _OUTLINE_PROMPT_ID},
                )
            ).all()
        )
        recipe_rows = list(
            (
                await connection.execute(
                    text(
                        """
                        select id::text, recipe_key, version, status, approved_by
                        from recipe_definitions
                        where id in (
                            cast(:angle AS uuid),
                            cast(:outline AS uuid)
                        )
                        order by id
                        """
                    ),
                    {"angle": _ANGLE_RECIPE_ID, "outline": _OUTLINE_RECIPE_ID},
                )
            ).all()
        )

    expected_prompts = {
        (_ANGLE_PROMPT_ID, "journal_angle_candidates", 2, "draft", None),
        (_OUTLINE_PROMPT_ID, "journal_outline", 2, "draft", None),
    }
    expected_recipes = {
        (_ANGLE_RECIPE_ID, "journal_angle_v1", 2, "draft", None),
        (_OUTLINE_RECIPE_ID, "journal_outline_v1", 2, "draft", None),
    }
    if column != "NO" or invalid_opportunities != 0:
        raise CoverageMigrationError("coverage_column_invalid")
    if {tuple(row) for row in prompt_rows} != expected_prompts:
        raise CoverageMigrationError("coverage_prompt_seed_invalid")
    if {tuple(row) for row in recipe_rows} != expected_recipes:
        raise CoverageMigrationError("coverage_recipe_seed_invalid")
    return {
        "coverage_column_nullable": column,
        "invalid_opportunities": invalid_opportunities,
        "v2_prompt_rows": len(prompt_rows),
        "v2_recipe_rows": len(recipe_rows),
        "registry_state": "DRAFT_NOT_APPROVED",
    }


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
            raise CoverageMigrationError("test_environment_not_operational")
        source = validate_operational_database_source(settings.database_url)
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
        target_url = source.set(database=f"{source.database}_coverage_migration_restore_test")
        target = validate_restore_target(
            source_url=settings.database_url,
            restore_url=target_url.render_as_string(hide_password=False),
        )
    except (CoverageMigrationError, RecoverySafetyError) as exc:
        print(json.dumps({"status": "BLOCKED", "blocker": exc.code}, indent=2))
        return 2
    except Exception:
        print(
            json.dumps(
                {"status": "BLOCKED", "blocker": "coverage_migration_preflight_failed"},
                indent=2,
            )
        )
        return 2

    source_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    target_created = False
    blocker: str | None = None
    result_payload: dict[str, object] = {}

    try:
        source_revision_before, source_core_before = await _database_state(source_engine)
        source_documents_before = await _source_documents_fingerprint(source_engine)
        source_model_calls_before = await _model_calls_fingerprint(source_engine)
        source_registry_before = await _registry_v1_fingerprint(source_engine)
        source_future_before = await _coverage_future_state(source_engine)

        if source_revision_before != _EXPECTED_SOURCE_REVISION:
            raise CoverageMigrationError("source_revision_drift")
        if source_core_before.to_dict() != expected_core:
            raise CoverageMigrationError("source_fingerprint_drift")
        if source_documents_before != expected_documents:
            raise CoverageMigrationError("source_documents_drift_from_backup")
        if source_model_calls_before != expected_model_calls:
            raise CoverageMigrationError("model_calls_drift_from_backup")
        _assert_coverage_absent(source_future_before)

        target_created = True
        await _recreate_database(target)
        restore_mode = _restore_backup(backup, target)

        target_engine = create_async_engine(target, poolclass=NullPool)
        try:
            restored_revision, restored_core = await _database_state(target_engine)
            restored_documents = await _source_documents_fingerprint(target_engine)
            restored_model_calls = await _model_calls_fingerprint(target_engine)
            restored_registry = await _registry_v1_fingerprint(target_engine)
            restored_future = await _coverage_future_state(target_engine)

            if restored_revision != _EXPECTED_SOURCE_REVISION:
                raise CoverageMigrationError("restored_source_revision_mismatch")
            if restored_core.to_dict() != expected_core:
                raise CoverageMigrationError("restored_source_fingerprint_mismatch")
            if restored_documents != expected_documents:
                raise CoverageMigrationError("restored_source_documents_mismatch")
            if restored_model_calls != expected_model_calls:
                raise CoverageMigrationError("restored_model_calls_mismatch")
            if restored_registry != source_registry_before:
                raise CoverageMigrationError("restored_registry_v1_mismatch")
            _assert_coverage_absent(restored_future)

            _run_alembic_upgrade(target)

            migrated_revision, migrated_core = await _database_state(target_engine)
            migrated_documents = await _source_documents_fingerprint(target_engine)
            migrated_model_calls = await _model_calls_fingerprint(target_engine)
            migrated_registry = await _registry_v1_fingerprint(target_engine)

            if migrated_revision != _EXPECTED_TARGET_REVISION:
                raise CoverageMigrationError("migrated_revision_mismatch")
            if migrated_core != restored_core:
                raise CoverageMigrationError("core_fingerprint_changed_by_migration")
            if migrated_documents != restored_documents:
                raise CoverageMigrationError("source_documents_changed_by_migration")
            if migrated_model_calls != restored_model_calls:
                raise CoverageMigrationError("model_calls_changed_by_migration")
            if migrated_registry != restored_registry:
                raise CoverageMigrationError("registry_v1_changed_by_migration")

            backfill = await _verify_backfill(target_engine)
            schema_objects = await _verify_schema_objects(target_engine)
            coverage_seed = await _verify_coverage_seed(target_engine)
        finally:
            await target_engine.dispose()

        source_revision_after, source_core_after = await _database_state(source_engine)
        source_documents_after = await _source_documents_fingerprint(source_engine)
        source_model_calls_after = await _model_calls_fingerprint(source_engine)
        source_registry_after = await _registry_v1_fingerprint(source_engine)
        if (
            source_revision_after != source_revision_before
            or source_core_after != source_core_before
            or source_documents_after != source_documents_before
            or source_model_calls_after != source_model_calls_before
            or source_registry_after != source_registry_before
        ):
            raise CoverageMigrationError("source_database_changed_during_rehearsal")

        result_payload = {
            "mode": "coverage_migration_rehearsal",
            "restore_mode": restore_mode,
            "source_database": source.database,
            "target_database": target.database,
            "revision_before": source_revision_before,
            "revision_after": _EXPECTED_TARGET_REVISION,
            "upgrade_chain": list(chain),
            "core_fingerprint": expected_core,
            "source_documents_fingerprint": expected_documents,
            "model_calls_fingerprint": expected_model_calls,
            "registry_v1_fingerprint": source_registry_before,
            "backfill": backfill,
            "schema_objects": schema_objects,
            "coverage_seed": coverage_seed,
        }
    except (CoverageMigrationError, RecoverySafetyError) as exc:
        blocker = exc.code
    except Exception:
        blocker = "coverage_migration_unexpected_failure"
    finally:
        await source_engine.dispose()
        if target_created:
            try:
                await _drop_database(target)
            except Exception:
                if blocker is None:
                    blocker = "coverage_migration_cleanup_failed"

    if blocker is not None:
        print(
            json.dumps(
                {"status": "BLOCKED", "blocker": blocker, **result_payload},
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    print(json.dumps({"status": "READY", **result_payload}, sort_keys=True, indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
