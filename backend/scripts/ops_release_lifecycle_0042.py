from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import signal
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.recovery import (
    RecoverySafetyError,
    validate_operational_database_source,
)
from scripts import ops_release_lifecycle as historical
from scripts.ops_release_provenance_0042 import (
    ReleaseProvenanceError,
    validate_release_provenance,
)

_EXPECTED_DATABASE = "contentengine"
_EXPECTED_REVISION = "20260923_0042"
_DEFAULT_PROVENANCE = Path("artifacts/release/release-0042-provenance.json")
_BACKEND_READY_MARKERS = (
    "uvicorn running on http://127.0.0.1:8000",
)
_FRONTEND_READY_MARKERS = (
    "ready in",
)
_STARTUP_TIMEOUT_SECONDS = 25.0
_WORKER_STABILITY_SECONDS = 4.0
_SHUTDOWN_TIMEOUT_SECONDS = 10.0
_CURRENT_FINGERPRINT_TABLES = (
    *historical._FINGERPRINT_TABLES,
    "published_contents",
    "publish_events",
)

ReleaseLifecycleError = historical.ReleaseLifecycleError


@dataclass(slots=True)
class AsyncRuntime:
    name: str
    process: asyncio.subprocess.Process
    log_path: Path
    log_task: asyncio.Task[None]
    ready_event: asyncio.Event


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prove a bounded rev-0042 operational startup/restart/shutdown lifecycle "
            "using event-driven readiness"
        )
    )
    parser.add_argument("--authorized-head", required=True)
    parser.add_argument("--provenance", type=Path, default=_DEFAULT_PROVENANCE)
    return parser.parse_args()


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _frontend_root() -> Path:
    return Path(__file__).resolve().parents[2] / "frontend"


def _validate_release_inputs(
    *,
    authorized_head: str,
    provenance_path: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, str]]:
    checkout = historical._validate_checkout(authorized_head)
    try:
        provenance = validate_release_provenance(
            authorized_head=authorized_head,
            provenance_path=provenance_path,
        )
    except ReleaseProvenanceError as exc:
        raise ReleaseLifecycleError(exc.code) from exc
    frontend_build = historical._validate_frontend_build()

    if provenance.get("next_build_id") != frontend_build.get("build_id"):
        raise ReleaseLifecycleError("release_build_id_mismatch")
    if provenance.get("package_lock_sha256") != frontend_build.get(
        "package_lock_sha256"
    ):
        raise ReleaseLifecycleError("release_package_lock_mismatch")

    return checkout, provenance, frontend_build


async def _drain_output(
    stream: asyncio.StreamReader,
    *,
    log_path: Path,
    markers: tuple[str, ...],
    ready_event: asyncio.Event,
) -> None:
    lowered_markers = tuple(marker.lower() for marker in markers)
    with log_path.open("ab", buffering=0) as handle:
        while True:
            chunk = await stream.readline()
            if not chunk:
                return
            handle.write(chunk)
            lowered = chunk.decode("utf-8", errors="replace").lower()
            if any(marker in lowered for marker in lowered_markers):
                ready_event.set()


async def _spawn_runtime(
    *,
    name: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    log_dir: Path,
    ready_markers: tuple[str, ...],
) -> AsyncRuntime:
    log_path = log_dir / f"{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )
    if process.stdout is None:
        raise ReleaseLifecycleError(f"{name}_stdout_unavailable")
    ready_event = asyncio.Event()
    log_task = asyncio.create_task(
        _drain_output(
            process.stdout,
            log_path=log_path,
            markers=ready_markers,
            ready_event=ready_event,
        )
    )
    return AsyncRuntime(
        name=name,
        process=process,
        log_path=log_path,
        log_task=log_task,
        ready_event=ready_event,
    )


async def _await_ready_event(
    runtime: AsyncRuntime,
    *,
    timeout_seconds: float,
    code: str,
) -> None:
    ready_task = asyncio.create_task(runtime.ready_event.wait())
    exit_task = asyncio.create_task(runtime.process.wait())
    try:
        done, _ = await asyncio.wait(
            {ready_task, exit_task},
            timeout=timeout_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            raise ReleaseLifecycleError(code)
        if exit_task in done and not runtime.ready_event.is_set():
            raise ReleaseLifecycleError(f"{runtime.name}_process_exited")
        if not runtime.ready_event.is_set():
            raise ReleaseLifecycleError(code)
    finally:
        for task in (ready_task, exit_task):
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task


async def _assert_worker_stable(runtime: AsyncRuntime) -> None:
    try:
        return_code = await asyncio.wait_for(
            runtime.process.wait(),
            timeout=_WORKER_STABILITY_SECONDS,
        )
    except TimeoutError:
        return
    raise ReleaseLifecycleError(
        "worker_process_exited",
        evidence={"worker_exit_code": return_code},
    )


async def _one_shot_http_readiness(
    *,
    settings_version: str,
    settings_environment: str,
) -> dict[str, object]:
    async with httpx.AsyncClient(timeout=2.0, follow_redirects=False) as client:
        try:
            health = await client.get("http://127.0.0.1:8000/health")
            db_health = await client.get("http://127.0.0.1:8000/health/db")
            version = await client.get("http://127.0.0.1:8000/version")
            frontend = await client.get("http://127.0.0.1:3000/")
        except httpx.HTTPError as exc:
            raise ReleaseLifecycleError("runtime_one_shot_http_failed") from exc

    if health.status_code != 200:
        raise ReleaseLifecycleError("backend_readiness_failed")
    if db_health.status_code != 200:
        raise ReleaseLifecycleError("backend_db_readiness_failed")
    if version.status_code != 200:
        raise ReleaseLifecycleError("backend_version_readiness_failed")
    if frontend.status_code != 200:
        raise ReleaseLifecycleError("frontend_readiness_failed")

    try:
        health_json = health.json()
        db_health_json = db_health.json()
        version_json = version.json()
    except ValueError as exc:
        raise ReleaseLifecycleError("runtime_readiness_payload_invalid") from exc

    if health_json != {"status": "ok"}:
        raise ReleaseLifecycleError("backend_health_payload_invalid")
    if db_health_json != {"status": "ok"}:
        raise ReleaseLifecycleError("backend_db_health_payload_invalid")
    if version_json != {
        "version": settings_version,
        "environment": settings_environment,
    }:
        raise ReleaseLifecycleError("backend_version_payload_invalid")

    return {
        "backend_health": {
            "status": health.status_code,
            "json": health_json,
        },
        "backend_db_health": {
            "status": db_health.status_code,
            "json": db_health_json,
        },
        "backend_version": {
            "status": version.status_code,
            "json": version_json,
        },
        "frontend": {
            "status": frontend.status_code,
        },
    }


async def _start_runtime(
    *,
    env: dict[str, str],
    log_dir: Path,
    npm: str,
) -> dict[str, AsyncRuntime]:
    runtimes: dict[str, AsyncRuntime] = {}
    try:
        runtimes["backend"] = await _spawn_runtime(
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
            ready_markers=_BACKEND_READY_MARKERS,
        )
        runtimes["frontend"] = await _spawn_runtime(
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
            ready_markers=_FRONTEND_READY_MARKERS,
        )
        runtimes["worker"] = await _spawn_runtime(
            name="worker",
            command=[
                sys.executable,
                "-m",
                "scripts.run_operator_worker_loop",
            ],
            cwd=_backend_root(),
            env=env,
            log_dir=log_dir,
            ready_markers=(),
        )
    except Exception:
        if runtimes:
            await _stop_all(runtimes)
        raise
    return runtimes


async def _prove_runtime_ready(
    runtimes: dict[str, AsyncRuntime],
    *,
    settings_version: str,
    settings_environment: str,
) -> dict[str, object]:
    await _await_ready_event(
        runtimes["backend"],
        timeout_seconds=_STARTUP_TIMEOUT_SECONDS,
        code="backend_readiness_event_timeout",
    )
    await _await_ready_event(
        runtimes["frontend"],
        timeout_seconds=_STARTUP_TIMEOUT_SECONDS,
        code="frontend_readiness_event_timeout",
    )
    await _assert_worker_stable(runtimes["worker"])

    http_evidence = await _one_shot_http_readiness(
        settings_version=settings_version,
        settings_environment=settings_environment,
    )

    if not historical._port_listening(8000):
        raise ReleaseLifecycleError("backend_listener_missing")
    if not historical._port_listening(3000):
        raise ReleaseLifecycleError("frontend_listener_missing")

    listeners = {
        "backend": historical._listener_evidence(8000),
        "frontend": historical._listener_evidence(3000),
    }

    return {
        **http_evidence,
        "worker": "RUNNING",
        "listeners": listeners,
    }


async def _stop_runtime(runtime: AsyncRuntime) -> dict[str, object]:
    forced = False
    if runtime.process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(runtime.process.pid, signal.SIGTERM)
        try:
            await asyncio.wait_for(
                runtime.process.wait(),
                timeout=_SHUTDOWN_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            forced = True
            with contextlib.suppress(ProcessLookupError):
                os.killpg(runtime.process.pid, signal.SIGKILL)
            await asyncio.wait_for(runtime.process.wait(), timeout=5.0)

    try:
        await asyncio.wait_for(runtime.log_task, timeout=2.0)
    except TimeoutError:
        runtime.log_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await runtime.log_task

    return {
        "name": runtime.name,
        "exit_code": runtime.process.returncode,
        "forced_kill": forced,
        "log_path": str(runtime.log_path),
    }


async def _stop_all(
    runtimes: dict[str, AsyncRuntime],
) -> tuple[list[dict[str, object]], list[str]]:
    results: list[dict[str, object]] = []
    errors: list[str] = []
    for name in ("worker", "frontend", "backend"):
        runtime = runtimes.get(name)
        if runtime is None:
            continue
        try:
            results.append(await _stop_runtime(runtime))
        except Exception:
            errors.append(f"{name}_shutdown_failed")
    return results, errors


async def _table_fingerprint(
    engine: AsyncEngine,
    *,
    table_name: str,
) -> dict[str, object]:
    if table_name not in _CURRENT_FINGERPRINT_TABLES:
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


async def _durable_snapshot(engine: AsyncEngine) -> dict[str, object]:
    fingerprint = await historical.database_fingerprint(engine)
    tables = {
        table_name: await _table_fingerprint(engine, table_name=table_name)
        for table_name in _CURRENT_FINGERPRINT_TABLES
    }
    return {
        "core": fingerprint.to_dict(),
        "tables": tables,
    }


async def _active_release_rows(
    engine: AsyncEngine,
) -> tuple[list[str], list[dict[str, object]]]:
    async with engine.connect() as connection:
        active_runs = [
            str(value)
            for value in (
                await connection.execute(
                    text(
                        "select id::text from content_runs "
                        "where status in ('pending','running') order by id"
                    )
                )
            ).scalars()
        ]
        rows = list(
            (
                await connection.execute(
                    text(
                        """
                        select
                            s.id::text as step_run_id,
                            s.run_id::text as run_id,
                            s.step_key,
                            s.status as step_status,
                            coalesce(s.error_json->>'class', '') as step_error_class,
                            r.status as run_status,
                            coalesce(r.current_step, '') as current_step,
                            coalesce(r.failure_code, '') as run_failure_code,
                            j.id::text as job_id,
                            j.run_id::text as job_run_id,
                            j.status as job_status,
                            j.lease_owner,
                            j.lease_expires_at
                        from step_runs s
                        join content_runs r on r.id = s.run_id
                        left join lateral (
                            select
                                jobs.id,
                                jobs.run_id,
                                jobs.status,
                                jobs.lease_owner,
                                jobs.lease_expires_at
                            from jobs
                            where jobs.step_run_id = s.id
                            order by jobs.updated_at desc, jobs.id desc
                            limit 1
                        ) j on true
                        where s.status in ('pending','running')
                        order by s.run_id, s.id
                        """
                    )
                )
            ).mappings()
        ]
    return active_runs, [dict(row) for row in rows]


def _classify_paused_operator_retries(
    *,
    active_run_ids: list[str],
    active_steps: list[dict[str, object]],
) -> list[dict[str, str]]:
    step_run_ids = [str(row["run_id"]) for row in active_steps]
    active_run_set = set(active_run_ids)
    step_run_set = set(step_run_ids)

    unmatched_runs = sorted(active_run_set - step_run_set)
    if unmatched_runs:
        raise ReleaseLifecycleError(
            "release_quiescence_active_run_unmatched",
            evidence={"run_ids": unmatched_runs},
        )

    unmatched_steps = sorted(step_run_set - active_run_set)
    if unmatched_steps:
        raise ReleaseLifecycleError(
            "release_quiescence_active_step_unmatched",
            evidence={"run_ids": unmatched_steps},
        )

    if len(step_run_ids) != len(step_run_set):
        raise ReleaseLifecycleError("release_quiescence_multiple_active_steps")

    paused: list[dict[str, str]] = []
    for row in active_steps:
        run_id = str(row["run_id"])
        step_run_id = str(row["step_run_id"])
        job_id = row.get("job_id")
        run_failure = str(row.get("run_failure_code") or "").strip()
        step_failure = str(row.get("step_error_class") or "").strip()
        exact_paused_contract = (
            row.get("run_status") == "running"
            and row.get("current_step") == "start_to_angle"
            and row.get("step_key") == "start_to_angle"
            and row.get("step_status") == "running"
            and isinstance(job_id, str)
            and bool(job_id)
            and row.get("job_run_id") == run_id
            and row.get("job_status") == "failed"
            and row.get("lease_owner") is None
            and row.get("lease_expires_at") is None
            and bool(run_failure)
            and run_failure == step_failure
        )
        if not exact_paused_contract:
            raise ReleaseLifecycleError(
                "release_quiescence_paused_contract_mismatch",
                evidence={
                    "run_id": run_id,
                    "step_run_id": step_run_id,
                },
            )
        paused.append(
            {
                "run_id": run_id,
                "step_run_id": step_run_id,
                "job_id": str(job_id),
                "failure_class": run_failure,
            }
        )
    return paused


async def _assert_release_quiescent_state(
    engine: AsyncEngine,
) -> dict[str, object]:
    job_statuses = await historical._status_counts(engine, table_name="jobs")
    nonterminal_jobs = {
        status: count
        for status, count in job_statuses.items()
        if status not in historical._TERMINAL_JOB_STATUSES and count > 0
    }
    if nonterminal_jobs:
        raise ReleaseLifecycleError(
            "nonterminal_jobs_present",
            evidence={"jobs": nonterminal_jobs},
        )

    model_statuses = await historical._status_counts(engine, table_name="model_calls")
    if model_statuses.get("pending", 0) > 0 or model_statuses.get("running", 0) > 0:
        raise ReleaseLifecycleError("active_model_calls_present")

    tool_statuses = await historical._status_counts(engine, table_name="tool_calls")
    if tool_statuses.get("pending", 0) > 0 or tool_statuses.get("running", 0) > 0:
        raise ReleaseLifecycleError("active_tool_calls_present")

    outbox_statuses = await historical._status_counts(
        engine,
        table_name="outbox_intents",
    )
    active_outbox = {
        status: outbox_statuses.get(status, 0)
        for status in ("pending", "processing", "needs_reconciliation")
        if outbox_statuses.get(status, 0) > 0
    }
    if active_outbox:
        raise ReleaseLifecycleError(
            "active_outbox_intents_present",
            evidence={"outbox_intents": active_outbox},
        )

    active_run_ids, active_steps = await _active_release_rows(engine)
    paused = _classify_paused_operator_retries(
        active_run_ids=active_run_ids,
        active_steps=active_steps,
    )

    run_statuses = await historical._status_counts(engine, table_name="content_runs")
    step_statuses = await historical._status_counts(engine, table_name="step_runs")
    return {
        "content_runs": run_statuses,
        "step_runs": step_statuses,
        "jobs": job_statuses,
        "model_calls": model_statuses,
        "tool_calls": tool_statuses,
        "outbox_intents": outbox_statuses,
        "paused_operator_retries": paused,
    }


def _require_expected_revision(revision: str | None) -> None:
    if revision != _EXPECTED_REVISION:
        raise ReleaseLifecycleError("operational_revision_not_current")


def _require_graceful_shutdown(
    shutdown: list[dict[str, object]],
    *,
    cycle: str,
) -> None:
    if shutdown and any(bool(row["forced_kill"]) for row in shutdown):
        raise ReleaseLifecycleError(f"forced_runtime_kill_{cycle}")


async def _require_release_preflight(*, blocker: str) -> dict[str, object]:
    return await historical._require_release_preflight(blocker=blocker)


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
    await _assert_release_quiescent_state(engine)
    before = await _durable_snapshot(engine)
    historical._require_snapshot_equal(
        baseline,
        before,
        code=f"durable_state_changed_before_{cycle}",
    )

    runtimes: dict[str, AsyncRuntime] = {}
    shutdown: list[dict[str, object]] = []
    primary: ReleaseLifecycleError | None = None
    secondary: list[str] = []
    evidence: dict[str, object] = {
        "cycle": cycle,
        "durable_before": "UNCHANGED",
    }

    try:
        runtimes = await _start_runtime(
            env=env,
            log_dir=log_root / cycle,
            npm=npm,
        )
        evidence["readiness"] = await _prove_runtime_ready(
            runtimes,
            settings_version=settings_version,
            settings_environment=settings_environment,
        )
        during = await _durable_snapshot(engine)
        historical._require_snapshot_equal(
            baseline,
            during,
            code=f"durable_state_changed_during_{cycle}",
        )
        evidence["durable_during"] = "UNCHANGED"
    except ReleaseLifecycleError as exc:
        primary = exc
    except Exception:
        primary = ReleaseLifecycleError(f"runtime_cycle_unexpected_failure_{cycle}")
    finally:
        if runtimes:
            shutdown, cleanup_errors = await _stop_all(runtimes)
            evidence["shutdown"] = shutdown
            secondary.extend(
                f"{code}_{cycle}"
                for code in cleanup_errors
            )

    try:
        stopped = historical._prestart_runtime_guard()
        evidence["stopped"] = stopped
    except ReleaseLifecycleError as exc:
        if primary is None:
            primary = exc
        elif exc.code != primary.code:
            secondary.append(exc.code)

    try:
        _require_graceful_shutdown(shutdown, cycle=cycle)
    except ReleaseLifecycleError as exc:
        if primary is None:
            primary = exc
        elif exc.code != primary.code:
            secondary.append(exc.code)

    try:
        evidence["idle_after"] = await _assert_release_quiescent_state(engine)
    except ReleaseLifecycleError as exc:
        if primary is None:
            primary = exc
        elif exc.code != primary.code:
            secondary.append(exc.code)

    try:
        after = await _durable_snapshot(engine)
        historical._require_snapshot_equal(
            baseline,
            after,
            code=f"durable_state_changed_after_{cycle}",
        )
        evidence["durable_after"] = "UNCHANGED"
    except ReleaseLifecycleError as exc:
        if primary is None:
            primary = exc
        elif exc.code != primary.code:
            secondary.append(exc.code)

    if primary is not None:
        secondary.extend(
            code
            for code in primary.secondary_blockers
            if code != primary.code and code not in secondary
        )
        raise ReleaseLifecycleError(
            primary.code,
            secondary_blockers=secondary,
            evidence=evidence,
        )

    evidence["durable_state"] = "UNCHANGED"
    return evidence


async def _main() -> int:
    args = _parse_args()
    blocker: str | None = None
    secondary_blockers: list[str] = []
    evidence: dict[str, object] = {}
    engine: AsyncEngine | None = None

    try:
        checkout, provenance, frontend_build = _validate_release_inputs(
            authorized_head=args.authorized_head,
            provenance_path=args.provenance,
        )
        runtime_before = historical._prestart_runtime_guard()

        settings = get_settings()
        if settings.app_env.strip().lower() == "test":
            raise ReleaseLifecycleError("test_environment_not_operational")

        source = validate_operational_database_source(settings.database_url)
        if source.database != _EXPECTED_DATABASE:
            raise ReleaseLifecycleError("unexpected_operational_database")

        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        actual_database = await historical._current_database(engine)
        if actual_database != _EXPECTED_DATABASE:
            raise ReleaseLifecycleError("database_identity_mismatch")

        revision = await historical._migration_revision(engine)
        _require_expected_revision(revision)

        evidence = {
            "mode": "controlled_release_lifecycle_0042",
            "checkout": checkout,
            "release_provenance": provenance,
            "frontend_build": frontend_build,
            "database": {
                "configured": source.database,
                "actual": actual_database,
                "revision": revision,
            },
            "runtime_before": runtime_before,
            "cycles": [],
        }

        pre_release_preflight = await _require_release_preflight(
            blocker="pre_release_preflight_blocked"
        )
        evidence["pre_release_preflight"] = pre_release_preflight

        idle_state = await _assert_release_quiescent_state(engine)
        baseline = await _durable_snapshot(engine)
        log_root = Path(
            tempfile.mkdtemp(prefix="contentengine-a4e2-lifecycle-")
        )
        (log_root / "startup").mkdir(parents=True, exist_ok=True)
        (log_root / "restart").mkdir(parents=True, exist_ok=True)
        evidence["idle_state_before"] = idle_state
        evidence["baseline"] = baseline
        evidence["log_root"] = str(log_root)

        env = os.environ.copy()
        cycles = evidence["cycles"]
        assert isinstance(cycles, list)
        cycles.append(
            await _run_cycle(
                cycle="startup",
                engine=engine,
                baseline=baseline,
                env=env,
                log_root=log_root,
                npm=frontend_build["npm"],
                settings_version=settings.app_version,
                settings_environment=settings.app_env,
            )
        )
        cycles.append(
            await _run_cycle(
                cycle="restart",
                engine=engine,
                baseline=baseline,
                env=env,
                log_root=log_root,
                npm=frontend_build["npm"],
                settings_version=settings.app_version,
                settings_environment=settings.app_env,
            )
        )

        evidence["post_release_preflight"] = await _require_release_preflight(
            blocker="post_release_preflight_blocked"
        )

        final_snapshot = await _durable_snapshot(engine)
        historical._require_snapshot_equal(
            baseline,
            final_snapshot,
            code="durable_state_changed_after_lifecycle",
        )
        evidence["final_idle_state"] = await _assert_release_quiescent_state(engine)
        evidence["runtime_final"] = historical._prestart_runtime_guard()
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
        blocker = "release_lifecycle_0042_unexpected_failure"
    finally:
        try:
            historical._prestart_runtime_guard()
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
                historical._final_document(
                    status="BLOCKED",
                    evidence={
                        "mode": "controlled_release_lifecycle_0042",
                        **evidence,
                    },
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
            historical._final_document(
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
