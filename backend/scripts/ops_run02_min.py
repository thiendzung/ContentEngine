from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import tempfile
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.recovery import RecoverySafetyError, validate_operational_database_source, validate_restore_target
from scripts import ops_data02_rehearsal as data02
from scripts import ops_release_lifecycle as historical
from scripts import ops_release_lifecycle_0042 as event_runtime

_EXPECTED_SOURCE_REVISION = "20260915_0034"
_EXPECTED_TARGET_REVISION = "20260926_0044"
_BACKEND_HOST = "127.0.0.1"
_BACKEND_PORT = 8000
_FRONTEND_HOST = "127.0.0.1"
_FRONTEND_PORT = 3000


class Run02Error(RuntimeError):
    def __init__(self, code: str, *, evidence: dict[str, object] | None = None) -> None:
        self.code = code
        self.evidence = dict(evidence or {})
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prove the P1 RUN-02 minimum local runtime against a disposable "
            "0044 database using event-driven readiness and a one-shot idle worker"
        )
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--authorized-head", required=True)
    return parser.parse_args()


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _frontend_root() -> Path:
    return Path(__file__).resolve().parents[2] / "frontend"


def _require_port_free(host: str, port: int) -> None:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        if probe.connect_ex((host, port)) == 0:
            raise Run02Error(
                "runtime_port_in_use",
                evidence={"host": host, "port": port},
            )


def _validate_frontend_and_checkout(authorized_head: str) -> tuple[dict[str, object], dict[str, str]]:
    try:
        checkout = historical._validate_checkout(authorized_head)
        frontend = historical._validate_frontend_build()
    except historical.ReleaseLifecycleError as exc:
        raise Run02Error(exc.code, evidence=exc.evidence) from exc
    return checkout, frontend


async def _status_counts(engine: AsyncEngine, *, table_name: str) -> dict[str, int]:
    if table_name not in {"jobs", "outbox_intents"}:
        raise Run02Error("unsupported_status_table")
    async with engine.connect() as connection:
        rows = list(
            (
                await connection.execute(
                    text(
                        f"select status, count(*)::int from {table_name} "
                        "group by status order by status"
                    )
                )
            ).all()
        )
    return {str(status): int(count) for status, count in rows}


async def _require_one_shot_worker_idle(engine: AsyncEngine) -> dict[str, object]:
    jobs = await _status_counts(engine, table_name="jobs")
    active_jobs = {
        status: jobs.get(status, 0)
        for status in ("queued", "leased")
        if jobs.get(status, 0) > 0
    }
    if active_jobs:
        raise Run02Error("run02_claimable_job_present", evidence={"jobs": active_jobs})

    outbox = await _status_counts(engine, table_name="outbox_intents")
    active_outbox = {
        status: outbox.get(status, 0)
        for status in ("pending", "processing", "needs_reconciliation")
        if outbox.get(status, 0) > 0
    }
    if active_outbox:
        raise Run02Error(
            "run02_active_outbox_present",
            evidence={"outbox_intents": active_outbox},
        )
    return {"jobs": jobs, "outbox_intents": outbox}


async def _run_one_shot_worker(
    *,
    env: dict[str, str],
) -> dict[str, object]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "scripts.run_operator_worker",
        cwd=str(_backend_root()),
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Run02Error(
            "one_shot_worker_failed",
            evidence={
                "exit_code": process.returncode,
                "stderr_tail": stderr.decode("utf-8", errors="replace")[-1000:],
            },
        )

    lines = [
        line.strip()
        for line in stdout.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    if not lines:
        raise Run02Error("one_shot_worker_output_missing")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise Run02Error("one_shot_worker_output_invalid") from exc
    if not isinstance(payload, dict) or payload.get("status") != "idle":
        raise Run02Error(
            "one_shot_worker_not_idle",
            evidence={"worker_payload": payload if isinstance(payload, dict) else {}},
        )
    return {
        "status": "idle",
        "exit_code": process.returncode,
        "worker_id": payload.get("worker_id"),
    }


def _runtime_env(target: URL) -> dict[str, str]:
    env = os.environ.copy()
    env["APP_ENV"] = "development"
    env["DATABASE_URL"] = target.render_as_string(hide_password=False)
    env["NEXT_PUBLIC_API_BASE_URL"] = f"http://{_BACKEND_HOST}:{_BACKEND_PORT}"
    return env


async def _start_services(
    *,
    env: dict[str, str],
    npm: str,
    log_dir: Path,
) -> dict[str, event_runtime.AsyncRuntime]:
    runtimes: dict[str, event_runtime.AsyncRuntime] = {}
    try:
        runtimes["backend"] = await event_runtime._spawn_runtime(
            name="backend",
            command=[
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                _BACKEND_HOST,
                "--port",
                str(_BACKEND_PORT),
                "--no-access-log",
            ],
            cwd=_backend_root(),
            env=env,
            log_dir=log_dir,
            ready_markers=event_runtime._BACKEND_READY_MARKERS,
        )
        runtimes["frontend"] = await event_runtime._spawn_runtime(
            name="frontend",
            command=[
                npm,
                "run",
                "start",
                "--",
                "--hostname",
                _FRONTEND_HOST,
                "--port",
                str(_FRONTEND_PORT),
            ],
            cwd=_frontend_root(),
            env=env,
            log_dir=log_dir,
            ready_markers=event_runtime._FRONTEND_READY_MARKERS,
        )
    except Exception:
        if runtimes:
            await event_runtime._stop_all(runtimes)
        raise
    return runtimes


async def _await_services_ready(
    runtimes: dict[str, event_runtime.AsyncRuntime],
    *,
    settings_version: str,
    settings_environment: str,
) -> dict[str, object]:
    try:
        await event_runtime._await_ready_event(
            runtimes["backend"],
            timeout_seconds=event_runtime._STARTUP_TIMEOUT_SECONDS,
            code="backend_readiness_event_timeout",
        )
        await event_runtime._await_ready_event(
            runtimes["frontend"],
            timeout_seconds=event_runtime._STARTUP_TIMEOUT_SECONDS,
            code="frontend_readiness_event_timeout",
        )
        return await event_runtime._one_shot_http_readiness(
            settings_version=settings_version,
            settings_environment=settings_environment,
        )
    except historical.ReleaseLifecycleError as exc:
        raise Run02Error(exc.code, evidence=exc.evidence) from exc


def _require_graceful_shutdown(rows: list[dict[str, object]], errors: list[str]) -> None:
    if errors:
        raise Run02Error("runtime_shutdown_failed", evidence={"errors": errors})
    forced = [str(row.get("name")) for row in rows if bool(row.get("forced_kill"))]
    if forced:
        raise Run02Error("runtime_forced_kill", evidence={"runtimes": forced})


async def _prepare_runtime_database(
    *,
    backup: Path,
    manifest_path: Path,
    source_url: str,
) -> tuple[URL, dict[str, object]]:
    manifest = data02._load_manifest(backup, manifest_path)
    source = validate_operational_database_source(source_url)
    source_revision_manifest = data02._manifest_source_revision(manifest, source)
    if source_revision_manifest != _EXPECTED_SOURCE_REVISION:
        raise Run02Error("run02_source_revision_manifest_mismatch")
    chain = data02._upgrade_chain(data02._alembic_script(), source_revision_manifest)
    if not chain or chain[-1] != _EXPECTED_TARGET_REVISION:
        raise Run02Error("run02_upgrade_chain_invalid")

    expected_fingerprint = data02._expected_fingerprint(manifest)
    target_url = source.set(database=f"{source.database}_run02_restore_test")
    target = validate_restore_target(
        source_url=source_url,
        restore_url=target_url.render_as_string(hide_password=False),
    )

    source_engine = create_async_engine(source_url, poolclass=NullPool)
    target_created = False
    try:
        source_revision, source_fingerprint = await data02._database_state(source_engine)
        source_documents = await data02._source_documents_fingerprint(source_engine)
        source_full_data = await data02._full_data_fingerprint(source_engine)
        if source_revision != _EXPECTED_SOURCE_REVISION:
            raise Run02Error("run02_source_revision_drift")
        if source_fingerprint.to_dict() != expected_fingerprint:
            raise Run02Error("run02_source_fingerprint_drift")

        target_created = True
        await data02._recreate_database(target)
        data02._restore_backup(backup, target)

        target_engine = create_async_engine(target, poolclass=NullPool)
        try:
            restored_revision, restored_fingerprint = await data02._database_state(target_engine)
            restored_documents = await data02._source_documents_fingerprint(target_engine)
            restored_full_data = await data02._full_data_fingerprint(target_engine)
            if restored_revision != _EXPECTED_SOURCE_REVISION:
                raise Run02Error("run02_restored_revision_mismatch")
            if restored_fingerprint.to_dict() != expected_fingerprint:
                raise Run02Error("run02_restored_fingerprint_mismatch")
            if restored_documents != source_documents:
                raise Run02Error("run02_restored_source_documents_mismatch")
            if restored_full_data != source_full_data:
                raise Run02Error("run02_restored_full_data_mismatch")

            data02._run_alembic_upgrade(target)
            migrated_revision = await data02._migration_revision(target_engine)
            if migrated_revision != _EXPECTED_TARGET_REVISION:
                raise Run02Error("run02_target_revision_mismatch")
            runtime_fingerprint = await data02._full_data_fingerprint(target_engine)
        finally:
            await target_engine.dispose()

        return target, {
            "source_revision": source_revision,
            "upgrade_chain": list(chain),
            "runtime_revision": _EXPECTED_TARGET_REVISION,
            "source_core_fingerprint": source_fingerprint.to_dict(),
            "source_documents_fingerprint": source_documents,
            "source_full_data_fingerprint": {
                "table_count": source_full_data["table_count"],
                "row_count": source_full_data["row_count"],
                "sha256": source_full_data["sha256"],
            },
            "runtime_full_data_before": runtime_fingerprint,
        }
    except Exception:
        if target_created:
            try:
                await data02._drop_database(target)
            except Exception:
                pass
        raise
    finally:
        await source_engine.dispose()


async def _source_snapshot(source_url: str) -> dict[str, object]:
    engine = create_async_engine(source_url, poolclass=NullPool)
    try:
        revision, core = await data02._database_state(engine)
        documents = await data02._source_documents_fingerprint(engine)
        full = await data02._full_data_fingerprint(engine)
        return {
            "revision": revision,
            "core": core.to_dict(),
            "documents": documents,
            "full": full,
        }
    finally:
        await engine.dispose()


async def _main() -> int:
    args = _parse_args()
    backup = args.backup.expanduser().resolve()
    manifest_path = (
        args.manifest.expanduser().resolve()
        if args.manifest
        else backup.with_suffix(".json")
    )

    target: URL | None = None
    target_created = False
    runtimes: dict[str, event_runtime.AsyncRuntime] = {}
    blocker: Run02Error | None = None
    evidence: dict[str, object] = {}

    try:
        checkout, frontend = _validate_frontend_and_checkout(args.authorized_head)
        _require_port_free(_BACKEND_HOST, _BACKEND_PORT)
        _require_port_free(_FRONTEND_HOST, _FRONTEND_PORT)

        settings = get_settings()
        validate_operational_database_source(settings.database_url)
        source_before = await _source_snapshot(settings.database_url)
        if source_before["revision"] != _EXPECTED_SOURCE_REVISION:
            raise Run02Error("run02_operational_revision_drift")

        target, database_evidence = await _prepare_runtime_database(
            backup=backup,
            manifest_path=manifest_path,
            source_url=settings.database_url,
        )
        target_created = True

        runtime_engine = create_async_engine(target, poolclass=NullPool)
        try:
            worker_guard = await _require_one_shot_worker_idle(runtime_engine)
            runtime_before = await data02._full_data_fingerprint(runtime_engine)

            env = _runtime_env(target)
            with tempfile.TemporaryDirectory(prefix="contentengine-run02-") as raw_log_dir:
                log_dir = Path(raw_log_dir)
                runtimes = await _start_services(
                    env=env,
                    npm=frontend["npm"],
                    log_dir=log_dir,
                )
                readiness = await _await_services_ready(
                    runtimes,
                    settings_version=settings.app_version,
                    settings_environment="development",
                )
                worker = await _run_one_shot_worker(env=env)

                runtime_after_worker = await data02._full_data_fingerprint(runtime_engine)
                if runtime_after_worker != runtime_before:
                    raise Run02Error("run02_runtime_state_changed")

                shutdown, shutdown_errors = await event_runtime._stop_all(runtimes)
                runtimes = {}
                _require_graceful_shutdown(shutdown, shutdown_errors)

                _require_port_free(_BACKEND_HOST, _BACKEND_PORT)
                _require_port_free(_FRONTEND_HOST, _FRONTEND_PORT)

                runtime_after_stop = await data02._full_data_fingerprint(runtime_engine)
                if runtime_after_stop != runtime_before:
                    raise Run02Error("run02_runtime_state_changed_after_stop")

                evidence = {
                    "status": "READY",
                    "mode": "run02_min_event_driven",
                    "checkout": checkout,
                    "frontend_build": frontend,
                    "database": {
                        **database_evidence,
                        "runtime_database": target.database,
                    },
                    "worker_guard": worker_guard,
                    "readiness": readiness,
                    "one_shot_worker": worker,
                    "shutdown": shutdown,
                    "runtime_state": "UNCHANGED",
                    "coordination": "event_exit_driven",
                }
        finally:
            await runtime_engine.dispose()

        source_after = await _source_snapshot(settings.database_url)
        if source_after != source_before:
            raise Run02Error("run02_operational_source_changed")
        evidence["operational_source"] = {
            "revision_before": source_before["revision"],
            "revision_after": source_after["revision"],
            "unchanged": True,
        }
    except Run02Error as exc:
        blocker = exc
    except (data02.Data02RehearsalError, RecoverySafetyError) as exc:
        blocker = Run02Error(exc.code)
    except Exception as exc:
        blocker = Run02Error(
            "run02_unexpected_failure",
            evidence={"error_class": type(exc).__name__},
        )
    finally:
        if runtimes:
            shutdown, shutdown_errors = await event_runtime._stop_all(runtimes)
            try:
                _require_graceful_shutdown(shutdown, shutdown_errors)
            except Run02Error as cleanup_exc:
                if blocker is None:
                    blocker = cleanup_exc
        if target_created and target is not None:
            try:
                await data02._drop_database(target)
            except Exception:
                if blocker is None:
                    blocker = Run02Error("run02_database_cleanup_failed")

    if blocker is not None:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "run02_min_event_driven",
                    "blocker": blocker.code,
                    "evidence": blocker.evidence,
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    evidence["runtime_database_cleanup"] = "DROPPED"
    print(json.dumps(evidence, sort_keys=True, indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
