from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.preflight import build_release_preflight
from app.modules.system.recovery import (
    RecoverySafetyError,
    database_fingerprint,
    validate_operational_database_source,
)

_EXPECTED_DATABASE = "contentengine"
_EXPECTED_REVISION = "20260915_0034"
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_RUNTIME_PORTS = (8000, 3000)
_FINGERPRINT_TABLES = (
    "jobs",
    "step_runs",
    "model_calls",
    "tool_calls",
    "outbox_intents",
)
_TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled"}
_STARTUP_TIMEOUT_SECONDS = 25.0
_WORKER_STABILITY_SECONDS = 4.0
_SHUTDOWN_TIMEOUT_SECONDS = 10.0


class ReleaseLifecycleError(RuntimeError):
    """Raised when O1.3 cannot prove a safe runtime lifecycle."""

    def __init__(
        self,
        code: str,
        *,
        secondary_blockers: list[str] | None = None,
        evidence: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.secondary_blockers = list(secondary_blockers or [])
        self.evidence = dict(evidence or {})
        super().__init__(code)


def _final_document(
    *,
    status: str,
    evidence: dict[str, object],
    blocker: str | None = None,
    secondary_blockers: list[str] | None = None,
) -> dict[str, object]:
    document = dict(evidence)
    document["status"] = status
    if blocker is not None:
        document["blocker"] = blocker
    if secondary_blockers is not None:
        document["secondary_blockers"] = list(secondary_blockers)
    return document


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prove a bounded operational runtime startup/shutdown/restart lifecycle"
    )
    parser.add_argument("--authorized-head", required=True)
    return parser.parse_args()


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _frontend_root() -> Path:
    return _repository_root() / "frontend"


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=_repository_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseLifecycleError("git_state_unavailable")
    return result.stdout.strip()


def _validate_checkout(authorized_head: str) -> dict[str, object]:
    if not _FULL_SHA.fullmatch(authorized_head):
        raise ReleaseLifecycleError("authorized_head_invalid")
    actual_head = _run_git("rev-parse", "HEAD")
    if actual_head != authorized_head:
        raise ReleaseLifecycleError("authorized_head_mismatch")
    clean = _run_git("status", "--porcelain") == ""
    if not clean:
        raise ReleaseLifecycleError("release_checkout_dirty")

    venv_root = (_backend_root() / ".venv").absolute()
    expected_python = (venv_root / "bin" / "python").absolute()
    actual_python = Path(sys.executable).absolute()
    actual_prefix = Path(sys.prefix).absolute()
    pyvenv_cfg = venv_root / "pyvenv.cfg"
    venv_lib = venv_root / "lib"

    if actual_python != expected_python or actual_prefix != venv_root:
        raise ReleaseLifecycleError("release_python_environment_mismatch")
    if pyvenv_cfg.is_symlink() or venv_lib.is_symlink():
        raise ReleaseLifecycleError("release_python_environment_symlinked")
    if not pyvenv_cfg.is_file() or not venv_lib.is_dir():
        raise ReleaseLifecycleError("release_python_environment_incomplete")

    return {
        "head": actual_head,
        "clean": clean,
        "python": str(actual_python),
        "python_prefix": str(actual_prefix),
    }


def _validate_frontend_build() -> dict[str, str]:
    frontend = _frontend_root()
    node_modules = frontend / "node_modules"
    build_root = frontend / ".next"
    build_id = build_root / "BUILD_ID"
    next_binary = node_modules / ".bin" / "next"
    package_lock = frontend / "package-lock.json"

    if node_modules.is_symlink() or build_root.is_symlink():
        raise ReleaseLifecycleError("frontend_environment_symlinked")
    if not next_binary.is_file():
        raise ReleaseLifecycleError("frontend_dependencies_missing")
    if not build_id.is_file():
        raise ReleaseLifecycleError("frontend_production_build_missing")
    if not package_lock.is_file():
        raise ReleaseLifecycleError("frontend_package_lock_missing")

    npm = shutil.which("npm")
    if npm is None:
        raise ReleaseLifecycleError("npm_unavailable")

    package_lock_sha = hashlib.sha256(package_lock.read_bytes()).hexdigest()
    return {
        "npm": npm,
        "build_id": build_id.read_text(encoding="utf-8").strip(),
        "package_lock_sha256": package_lock_sha,
    }


def _port_listening(port: int) -> bool:
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except OSError:
            continue
    return False


def _listener_evidence(port: int) -> list[str]:
    lsof = shutil.which("lsof")
    if lsof is None:
        raise ReleaseLifecycleError("lsof_unavailable")
    result = subprocess.run(
        [lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseLifecycleError("runtime_listener_evidence_unavailable")
    lines = [line.strip() for line in result.stdout.splitlines()[1:] if line.strip()]
    if not lines:
        raise ReleaseLifecycleError("runtime_listener_evidence_missing")
    expected = f"127.0.0.1:{port}"
    if any(expected not in line for line in lines):
        raise ReleaseLifecycleError("runtime_listener_not_loopback_only")
    return lines


def _process_table() -> str:
    result = subprocess.run(
        ["ps", "-axo", "pid=,command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseLifecycleError("runtime_process_state_unavailable")
    return result.stdout


def _prestart_runtime_guard() -> dict[str, object]:
    active_ports = [port for port in _RUNTIME_PORTS if _port_listening(port)]
    process_table = _process_table().lower()
    markers = (
        "uvicorn app.main:app",
        "next dev",
        "next start",
        "scripts.run_operator_worker",
        "celery",
    )
    active_markers = [marker for marker in markers if marker in process_table]
    if active_ports:
        raise ReleaseLifecycleError("application_runtime_port_active")
    if active_markers:
        raise ReleaseLifecycleError("application_runtime_process_active")
    return {
        "ports": {str(port): "STOPPED" for port in _RUNTIME_PORTS},
        "process_markers": [],
    }


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


async def _table_fingerprint(
    engine: AsyncEngine,
    *,
    table_name: str,
) -> dict[str, object]:
    if table_name not in _FINGERPRINT_TABLES:
        raise ReleaseLifecycleError("unsupported_runtime_fingerprint_table")
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
    ).encode("utf-8")
    return {
        "count": len(rows),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


async def _status_counts(
    engine: AsyncEngine,
    *,
    table_name: str,
) -> dict[str, int]:
    if table_name not in {
        "content_runs",
        "step_runs",
        "jobs",
        "model_calls",
        "tool_calls",
        "outbox_intents",
    }:
        raise ReleaseLifecycleError("unsupported_runtime_status_table")
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


async def _assert_idle_operational_state(engine: AsyncEngine) -> dict[str, object]:
    job_statuses = await _status_counts(engine, table_name="jobs")
    nonterminal_jobs = {
        status: count
        for status, count in job_statuses.items()
        if status not in _TERMINAL_JOB_STATUSES and count > 0
    }
    if nonterminal_jobs:
        raise ReleaseLifecycleError("nonterminal_jobs_present")

    step_statuses = await _status_counts(engine, table_name="step_runs")
    if step_statuses.get("running", 0) > 0:
        raise ReleaseLifecycleError("running_step_runs_present")

    run_statuses = await _status_counts(engine, table_name="content_runs")
    active_runs = {
        status: run_statuses.get(status, 0)
        for status in ("pending", "running")
        if run_statuses.get(status, 0) > 0
    }
    if active_runs:
        raise ReleaseLifecycleError("active_content_runs_present")

    model_statuses = await _status_counts(engine, table_name="model_calls")
    if model_statuses.get("pending", 0) > 0 or model_statuses.get("running", 0) > 0:
        raise ReleaseLifecycleError("active_model_calls_present")

    tool_statuses = await _status_counts(engine, table_name="tool_calls")
    if tool_statuses.get("pending", 0) > 0 or tool_statuses.get("running", 0) > 0:
        raise ReleaseLifecycleError("active_tool_calls_present")

    outbox_statuses = await _status_counts(engine, table_name="outbox_intents")
    active_outbox = {
        status: outbox_statuses.get(status, 0)
        for status in ("pending", "processing", "needs_reconciliation")
        if outbox_statuses.get(status, 0) > 0
    }
    if active_outbox:
        raise ReleaseLifecycleError("active_outbox_intents_present")

    return {
        "content_runs": run_statuses,
        "step_runs": step_statuses,
        "jobs": job_statuses,
        "model_calls": model_statuses,
        "tool_calls": tool_statuses,
        "outbox_intents": outbox_statuses,
    }


async def _durable_snapshot(engine: AsyncEngine) -> dict[str, object]:
    fingerprint = await database_fingerprint(engine)
    tables = {
        table_name: await _table_fingerprint(engine, table_name=table_name)
        for table_name in _FINGERPRINT_TABLES
    }
    return {
        "core": fingerprint.to_dict(),
        "tables": tables,
    }


def _require_snapshot_equal(
    baseline: dict[str, object],
    candidate: dict[str, object],
    *,
    code: str,
) -> None:
    if candidate != baseline:
        raise ReleaseLifecycleError(code)


def _spawn_process(
    *,
    name: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    log_dir: Path,
) -> dict[str, Any]:
    log_path = log_dir / f"{name}.log"
    handle = log_path.open("ab", buffering=0)
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except Exception:
        handle.close()
        raise
    return {
        "name": name,
        "process": process,
        "log_handle": handle,
        "log_path": str(log_path),
        "command": command,
    }


def _process_exit_code(runtime: dict[str, Any]) -> int | None:
    process = runtime["process"]
    assert isinstance(process, subprocess.Popen)
    return process.poll()


def _assert_process_alive(runtime: dict[str, Any], *, code: str) -> None:
    if _process_exit_code(runtime) is not None:
        raise ReleaseLifecycleError(code)


async def _wait_http(
    *,
    url: str,
    expected_status: int,
    timeout_seconds: float,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    async with httpx.AsyncClient(timeout=2.0, follow_redirects=False) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(url)
                if response.status_code == expected_status:
                    payload: object
                    try:
                        payload = response.json()
                    except ValueError:
                        payload = None
                    return {
                        "url": url,
                        "status": response.status_code,
                        "json": payload,
                    }
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.25)
    raise ReleaseLifecycleError(
        "backend_readiness_failed"
        if ":8000" in url
        else "frontend_readiness_failed"
    )


async def _prove_runtime_ready(
    runtimes: dict[str, dict[str, Any]],
    *,
    settings_version: str,
    settings_environment: str,
) -> dict[str, object]:
    for name, code in (
        ("backend", "backend_process_exited"),
        ("frontend", "frontend_process_exited"),
        ("worker", "worker_process_exited"),
    ):
        _assert_process_alive(runtimes[name], code=code)

    health = await _wait_http(
        url="http://127.0.0.1:8000/health",
        expected_status=200,
        timeout_seconds=_STARTUP_TIMEOUT_SECONDS,
    )
    db_health = await _wait_http(
        url="http://127.0.0.1:8000/health/db",
        expected_status=200,
        timeout_seconds=_STARTUP_TIMEOUT_SECONDS,
    )
    version = await _wait_http(
        url="http://127.0.0.1:8000/version",
        expected_status=200,
        timeout_seconds=_STARTUP_TIMEOUT_SECONDS,
    )
    frontend = await _wait_http(
        url="http://127.0.0.1:3000/",
        expected_status=200,
        timeout_seconds=_STARTUP_TIMEOUT_SECONDS,
    )

    if health.get("json") != {"status": "ok"}:
        raise ReleaseLifecycleError("backend_health_payload_invalid")
    if db_health.get("json") != {"status": "ok"}:
        raise ReleaseLifecycleError("backend_db_health_payload_invalid")
    if version.get("json") != {
        "version": settings_version,
        "environment": settings_environment,
    }:
        raise ReleaseLifecycleError("backend_version_payload_invalid")

    await asyncio.sleep(_WORKER_STABILITY_SECONDS)
    _assert_process_alive(runtimes["worker"], code="worker_process_exited")

    if not _port_listening(8000):
        raise ReleaseLifecycleError("backend_listener_missing")
    if not _port_listening(3000):
        raise ReleaseLifecycleError("frontend_listener_missing")

    listeners = {
        "backend": _listener_evidence(8000),
        "frontend": _listener_evidence(3000),
    }

    return {
        "backend_health": health,
        "backend_db_health": db_health,
        "backend_version": version,
        "frontend": {
            "url": frontend["url"],
            "status": frontend["status"],
        },
        "worker": "RUNNING",
        "listeners": listeners,
    }


def _stop_runtime(runtime: dict[str, Any]) -> dict[str, object]:
    process = runtime["process"]
    assert isinstance(process, subprocess.Popen)
    forced = False

    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            forced = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)

    handle = runtime["log_handle"]
    handle.close()
    return {
        "name": runtime["name"],
        "exit_code": process.returncode,
        "forced_kill": forced,
        "log_path": runtime["log_path"],
    }


def _stop_all(
    runtimes: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, object]], list[str]]:
    results: list[dict[str, object]] = []
    errors: list[str] = []
    for name in ("worker", "frontend", "backend"):
        runtime = runtimes.get(name)
        if runtime is None:
            continue
        try:
            results.append(_stop_runtime(runtime))
        except Exception:
            errors.append(f"{name}_shutdown_failed")
    return results, errors


def _assert_runtime_stopped() -> dict[str, object]:
    active_ports = [port for port in _RUNTIME_PORTS if _port_listening(port)]
    if active_ports:
        raise ReleaseLifecycleError("runtime_ports_still_active_after_shutdown")
    return {"ports": {str(port): "STOPPED" for port in _RUNTIME_PORTS}}


def _start_runtime(
    *,
    env: dict[str, str],
    log_dir: Path,
    npm: str,
) -> dict[str, dict[str, Any]]:
    backend = _spawn_process(
        name="backend",
        command=[
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--no-access-log",
        ],
        cwd=_backend_root(),
        env=env,
        log_dir=log_dir,
    )
    runtimes = {"backend": backend}
    try:
        frontend = _spawn_process(
            name="frontend",
            command=[
                npm,
                "run",
                "start",
                "--",
                "--hostname",
                "127.0.0.1",
                "--port",
                "3000",
            ],
            cwd=_frontend_root(),
            env=env,
            log_dir=log_dir,
        )
        runtimes["frontend"] = frontend

        worker = _spawn_process(
            name="worker",
            command=[
                sys.executable,
                "-m",
                "scripts.run_operator_worker_loop",
            ],
            cwd=_backend_root(),
            env=env,
            log_dir=log_dir,
        )
        runtimes["worker"] = worker
    except Exception:
        _stop_all(runtimes)
        raise
    return runtimes


async def _run_cycle(
    *,
    cycle: str,
    engine: AsyncEngine,
    baseline: dict[str, object],
    env: dict[str, str],
    log_root: Path,
    npm: str,
    settings_version: str,
    settings_environment: str,
) -> dict[str, object]:
    await _assert_idle_operational_state(engine)
    before = await _durable_snapshot(engine)
    _require_snapshot_equal(
        baseline,
        before,
        code=f"durable_state_changed_before_{cycle}",
    )

    runtimes: dict[str, dict[str, Any]] = {}
    readiness: dict[str, object] | None = None
    shutdown: list[dict[str, object]] = []
    primary: ReleaseLifecycleError | None = None
    secondary: list[str] = []
    cycle_evidence: dict[str, object] = {
        "cycle": cycle,
        "durable_before": "UNCHANGED",
    }

    try:
        runtimes = _start_runtime(
            env=env,
            log_dir=log_root / cycle,
            npm=npm,
        )
        readiness = await _prove_runtime_ready(
            runtimes,
            settings_version=settings_version,
            settings_environment=settings_environment,
        )
        cycle_evidence["readiness"] = readiness

        during = await _durable_snapshot(engine)
        _require_snapshot_equal(
            baseline,
            during,
            code=f"durable_state_changed_during_{cycle}",
        )
        cycle_evidence["durable_during"] = "UNCHANGED"
    except ReleaseLifecycleError as exc:
        primary = exc
    except Exception:
        primary = ReleaseLifecycleError(f"runtime_cycle_unexpected_failure_{cycle}")
    finally:
        if runtimes:
            try:
                shutdown, cleanup_errors = _stop_all(runtimes)
                cycle_evidence["shutdown"] = shutdown
                if cleanup_errors:
                    cycle_evidence["cleanup_errors"] = cleanup_errors
                    secondary.extend(
                        f"{code}_{cycle}" for code in cleanup_errors
                    )
            except Exception:
                secondary.append(f"runtime_cleanup_failed_{cycle}")

    try:
        stopped = _assert_runtime_stopped()
        cycle_evidence["stopped"] = stopped
    except ReleaseLifecycleError as exc:
        if primary is None:
            primary = exc
        elif exc.code != primary.code:
            secondary.append(exc.code)

    if shutdown and any(bool(row["forced_kill"]) for row in shutdown):
        code = f"forced_runtime_kill_{cycle}"
        if primary is None:
            primary = ReleaseLifecycleError(code)
        elif code != primary.code:
            secondary.append(code)

    try:
        idle_after = await _assert_idle_operational_state(engine)
        cycle_evidence["idle_after"] = idle_after
    except ReleaseLifecycleError as exc:
        if primary is None:
            primary = exc
        elif exc.code != primary.code:
            secondary.append(exc.code)

    try:
        after = await _durable_snapshot(engine)
        _require_snapshot_equal(
            baseline,
            after,
            code=f"durable_state_changed_after_{cycle}",
        )
        cycle_evidence["durable_after"] = "UNCHANGED"
    except ReleaseLifecycleError as exc:
        if primary is None:
            primary = exc
        elif exc.code != primary.code:
            secondary.append(exc.code)
    except Exception:
        code = f"durable_state_verification_failed_after_{cycle}"
        if primary is None:
            primary = ReleaseLifecycleError(code)
        else:
            secondary.append(code)

    if primary is not None:
        secondary.extend(
            code
            for code in primary.secondary_blockers
            if code != primary.code and code not in secondary
        )
        raise ReleaseLifecycleError(
            primary.code,
            secondary_blockers=secondary,
            evidence=cycle_evidence,
        )

    cycle_evidence["durable_state"] = "UNCHANGED"
    return cycle_evidence


async def _main() -> int:
    args = _parse_args()
    blocker: str | None = None
    secondary_blockers: list[str] = []
    evidence: dict[str, object] = {}
    engine: AsyncEngine | None = None

    try:
        checkout = _validate_checkout(args.authorized_head)
        frontend_build = _validate_frontend_build()
        runtime_before = _prestart_runtime_guard()

        settings = get_settings()
        if settings.app_env.strip().lower() == "test":
            raise ReleaseLifecycleError("test_environment_not_operational")

        source = validate_operational_database_source(settings.database_url)
        if source.database != _EXPECTED_DATABASE:
            raise ReleaseLifecycleError("unexpected_operational_database")

        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        actual_database = await _current_database(engine)
        if actual_database != _EXPECTED_DATABASE:
            raise ReleaseLifecycleError("database_identity_mismatch")

        revision = await _migration_revision(engine)
        if revision != _EXPECTED_REVISION:
            raise ReleaseLifecycleError("operational_revision_not_current")

        idle_state = await _assert_idle_operational_state(engine)
        baseline = await _durable_snapshot(engine)

        log_root = Path(
            tempfile.mkdtemp(prefix="contentengine-o1-3-lifecycle-")
        )
        (log_root / "startup").mkdir(parents=True, exist_ok=True)
        (log_root / "restart").mkdir(parents=True, exist_ok=True)

        evidence = {
            "mode": "controlled_release_lifecycle",
            "checkout": checkout,
            "frontend_build": frontend_build,
            "database": {
                "configured": source.database,
                "actual": actual_database,
                "revision": revision,
            },
            "runtime_before": runtime_before,
            "idle_state_before": idle_state,
            "baseline": baseline,
            "cycles": [],
            "log_root": str(log_root),
        }

        env = os.environ.copy()
        cycle_one = await _run_cycle(
            cycle="startup",
            engine=engine,
            baseline=baseline,
            env=env,
            log_root=log_root,
            npm=frontend_build["npm"],
            settings_version=settings.app_version,
            settings_environment=settings.app_env,
        )
        cycles = evidence["cycles"]
        assert isinstance(cycles, list)
        cycles.append(cycle_one)

        cycle_two = await _run_cycle(
            cycle="restart",
            engine=engine,
            baseline=baseline,
            env=env,
            log_root=log_root,
            npm=frontend_build["npm"],
            settings_version=settings.app_version,
            settings_environment=settings.app_env,
        )
        cycles.append(cycle_two)

        preflight = await build_release_preflight()
        evidence["post_release_preflight"] = preflight
        if preflight.get("status") != "READY":
            raise ReleaseLifecycleError("post_release_preflight_blocked")

        final_snapshot = await _durable_snapshot(engine)
        _require_snapshot_equal(
            baseline,
            final_snapshot,
            code="durable_state_changed_after_lifecycle",
        )
        final_idle = await _assert_idle_operational_state(engine)
        runtime_final = _assert_runtime_stopped()

        evidence["final_idle_state"] = final_idle
        evidence["runtime_final"] = runtime_final
        evidence["final_snapshot"] = final_snapshot
        evidence["content_model_publication_delta"] = "NONE"
    except ReleaseLifecycleError as exc:
        blocker = exc.code
        secondary_blockers.extend(exc.secondary_blockers)
        if exc.evidence:
            evidence["failure_cycle"] = exc.evidence
    except RecoverySafetyError as exc:
        blocker = exc.code
    except Exception:
        blocker = "release_lifecycle_unexpected_failure"
    finally:
        try:
            _prestart_runtime_guard()
        except ReleaseLifecycleError as exc:
            if blocker is None:
                blocker = exc.code
            elif exc.code != blocker:
                secondary_blockers.append(exc.code)
        if engine is not None:
            await engine.dispose()

    if blocker is not None:
        print(
            json.dumps(
                _final_document(
                    status="BLOCKED",
                    evidence={"mode": "controlled_release_lifecycle", **evidence},
                    blocker=blocker,
                    secondary_blockers=secondary_blockers,
                ),
                sort_keys=True,
                indent=2,
            )
        )
        return 2

    print(
        json.dumps(
            _final_document(
                status="READY",
                evidence=evidence,
                secondary_blockers=secondary_blockers,
            ),
            sort_keys=True,
            indent=2,
        )
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
