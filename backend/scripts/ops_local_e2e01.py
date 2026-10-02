from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.recovery import (
    RecoverySafetyError,
    validate_operational_database_source,
    validate_restore_target,
)
from scripts import ops_data02_rehearsal as data02
from scripts import ops_run02_min as run02
from scripts import ops_release_lifecycle_0042 as event_runtime

_SOURCE_REVISION = "20260915_0034"
_TARGET_REVISION = "20260926_0044"
_RUNTIME_DB_SUFFIX = "_local_e2e01_test"
_API_BASE = "http://127.0.0.1:8000"
_STATE_FORMAT = 1
_MAX_WORKER_TRANSITIONS = 32


class LocalE2E01Error(RuntimeError):
    def __init__(self, code: str, *, evidence: dict[str, object] | None = None) -> None:
        self.code = code
        self.evidence = dict(evidence or {})
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "P1 LOCAL-E2E-01: one fresh real Journal case on a disposable 0044 DB "
            "with explicit human gates and one controlled runtime restart"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("backup", type=Path)
    start.add_argument("--manifest", type=Path)
    start.add_argument("--intake", type=Path, required=True)
    start.add_argument("--authorized-head", required=True)
    start.add_argument("--state-file", type=Path, required=True)

    for name in ("status", "approve-angle", "approve-outline", "approve-final", "finish", "cleanup"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--authorized-head", required=True)
        cmd.add_argument("--state-file", type=Path, required=True)
        if name == "approve-angle":
            cmd.add_argument("--angle-id", required=True)
        if name == "approve-final":
            cmd.add_argument("--locale", required=True)
            cmd.add_argument(
                "--decision",
                choices=("approved", "changes_requested", "rejected"),
                default="approved",
            )
            cmd.add_argument("--comment")
    return parser.parse_args()


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _json_sha256(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_intake(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalE2E01Error("local_e2e01_intake_invalid") from exc
    if not isinstance(payload, dict):
        raise LocalE2E01Error("local_e2e01_intake_invalid")
    required = {
        "project_slug", "source_locale", "research_country", "required_locales",
        "content_role", "reader", "situation", "need", "question", "intent",
        "promise", "coverage_requirements", "selection_reason",
        "originality_material", "originality_writer_use",
        "originality_guardrails", "idempotency_key",
    }
    if set(payload) != required:
        raise LocalE2E01Error(
            "local_e2e01_intake_shape_invalid",
            evidence={
                "missing": sorted(required - set(payload)),
                "extra": sorted(set(payload) - required),
            },
        )
    locales = payload.get("required_locales")
    coverage = payload.get("coverage_requirements")
    if sorted(locales if isinstance(locales, list) else []) != ["en", "vi-VN"]:
        raise LocalE2E01Error("local_e2e01_bilingual_intake_required")
    if not isinstance(coverage, list) or not coverage:
        raise LocalE2E01Error("local_e2e01_coverage_required")
    if payload.get("content_role") not in {"pillar", "cluster"}:
        raise LocalE2E01Error("local_e2e01_role_invalid")
    return payload


def _load_state(path: Path) -> dict[str, object]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalE2E01Error("local_e2e01_state_invalid") from exc
    if not isinstance(state, dict) or state.get("format_version") != _STATE_FORMAT:
        raise LocalE2E01Error("local_e2e01_state_invalid")
    return state


def _write_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _target_from_state(state: dict[str, object]) -> URL:
    settings = get_settings()
    source = validate_operational_database_source(settings.database_url)
    name = state.get("runtime_database")
    if (
        not isinstance(name, str)
        or source.database is None
        or name != f"{source.database}{_RUNTIME_DB_SUFFIX}"
    ):
        raise LocalE2E01Error("local_e2e01_runtime_database_invalid")
    target = source.set(database=name)
    validate_restore_target(
        source_url=settings.database_url,
        restore_url=target.render_as_string(hide_password=False),
    )
    return target


async def _count(engine: AsyncEngine, table_name: str) -> int:
    allowed = {
        "model_calls", "tool_calls", "artifacts", "jobs",
        "operator_commands", "content_versions", "publish_events",
    }
    if table_name not in allowed:
        raise LocalE2E01Error("local_e2e01_count_table_invalid")
    async with engine.connect() as connection:
        return int(
            (await connection.execute(text(f'SELECT count(*)::int FROM "{table_name}"'))).scalar_one()
        )


async def _runtime_counts(engine: AsyncEngine) -> dict[str, int]:
    return {
        name: await _count(engine, name)
        for name in (
            "model_calls", "tool_calls", "artifacts", "jobs",
            "operator_commands", "content_versions", "publish_events",
        )
    }


async def _source_snapshot(source_url: str) -> dict[str, object]:
    engine = create_async_engine(source_url, poolclass=NullPool)
    try:
        revision, core = await data02._database_state(engine)
        docs = await data02._source_documents_fingerprint(engine)
        full = await data02._full_data_fingerprint(engine)
        return {
            "revision": revision,
            "core": core.to_dict(),
            "documents": docs,
            "full": {
                "table_count": full["table_count"],
                "row_count": full["row_count"],
                "sha256": full["sha256"],
            },
        }
    finally:
        await engine.dispose()


async def _prepare_database(backup: Path, manifest_path: Path) -> tuple[URL, dict[str, object]]:
    settings = get_settings()
    source = validate_operational_database_source(settings.database_url)
    manifest = data02._load_manifest(backup, manifest_path)
    source_revision = data02._manifest_source_revision(manifest, source)
    if source_revision != _SOURCE_REVISION:
        raise LocalE2E01Error("local_e2e01_source_revision_manifest_mismatch")
    chain = data02._upgrade_chain(data02._alembic_script(), source_revision)
    if not chain or chain[-1] != _TARGET_REVISION:
        raise LocalE2E01Error("local_e2e01_upgrade_chain_invalid")
    if source.database is None:
        raise LocalE2E01Error("local_e2e01_source_database_missing")
    target = source.set(database=f"{source.database}{_RUNTIME_DB_SUFFIX}")
    validate_restore_target(
        source_url=settings.database_url,
        restore_url=target.render_as_string(hide_password=False),
    )
    source_before = await _source_snapshot(settings.database_url)
    if source_before["revision"] != _SOURCE_REVISION:
        raise LocalE2E01Error("local_e2e01_source_revision_drift")
    await data02._recreate_database(target)
    try:
        data02._restore_backup(backup, target)
        engine = create_async_engine(target, poolclass=NullPool)
        try:
            if await data02._migration_revision(engine) != _SOURCE_REVISION:
                raise LocalE2E01Error("local_e2e01_restored_revision_mismatch")
            data02._run_alembic_upgrade(target)
            if await data02._migration_revision(engine) != _TARGET_REVISION:
                raise LocalE2E01Error("local_e2e01_target_revision_mismatch")
        finally:
            await engine.dispose()
    except Exception:
        await data02._drop_database(target)
        raise
    return target, {
        "source_before": source_before,
        "upgrade_chain": list(chain),
        "runtime_revision": _TARGET_REVISION,
    }


async def _stop_services(runtimes: dict[str, event_runtime.AsyncRuntime]) -> list[dict[str, object]]:
    rows, errors = await event_runtime._stop_all(runtimes)
    run02._require_graceful_shutdown(rows, errors)
    run02._require_port_free(run02._BACKEND_HOST, run02._BACKEND_PORT)
    run02._require_port_free(run02._FRONTEND_HOST, run02._FRONTEND_PORT)
    return rows


async def _api(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> dict[str, Any]:
    response = await client.request(method, path, json=payload)
    if response.status_code >= 400:
        code: object = None
        try:
            body = response.json()
            detail = body.get("detail") if isinstance(body, dict) else None
            code = detail.get("code") if isinstance(detail, dict) else detail
        except Exception:
            pass
        raise LocalE2E01Error(
            "local_e2e01_api_rejected",
            evidence={"status": response.status_code, "code": code, "path": path},
        )
    body = response.json()
    if not isinstance(body, dict):
        raise LocalE2E01Error("local_e2e01_api_shape_invalid", evidence={"path": path})
    return body


async def _view(client: httpx.AsyncClient, case_id: str) -> dict[str, Any]:
    return await _api(client, "GET", f"/journal/operator/cases/{case_id}/view")


async def _run_worker(env: dict[str, str]) -> dict[str, Any]:
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
        raise LocalE2E01Error(
            "local_e2e01_worker_failed",
            evidence={
                "exit_code": process.returncode,
                "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            },
        )
    lines = [line.strip() for line in stdout.decode("utf-8", errors="replace").splitlines() if line.strip()]
    if not lines:
        raise LocalE2E01Error("local_e2e01_worker_output_missing")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise LocalE2E01Error("local_e2e01_worker_output_invalid") from exc
    if not isinstance(payload, dict):
        raise LocalE2E01Error("local_e2e01_worker_output_invalid")
    return payload


async def _submit_next(client: httpx.AsyncClient, case_id: str, state: dict[str, Any]) -> dict[str, Any]:
    intent = state.get("primary_intent")
    if intent not in {"start", "continue", "resume"}:
        raise LocalE2E01Error(
            "local_e2e01_unapproved_auto_intent",
            evidence={"intent": intent, "status": state.get("status")},
        )
    version = state.get("state_version")
    if not isinstance(version, str):
        raise LocalE2E01Error("local_e2e01_state_version_missing")
    return await _api(
        client,
        "POST",
        f"/journal/operator/cases/{case_id}/commands",
        {
            "intent": intent,
            "expected_state_version": version,
            "idempotency_key": f"local-e2e01:{case_id}:{intent}:{version}",
            "knowledge_brief_id": None,
        },
    )


async def _drive_to_gate(
    client: httpx.AsyncClient,
    case_id: str,
    env: dict[str, str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipts: list[dict[str, Any]] = []
    for _ in range(_MAX_WORKER_TRANSITIONS):
        view = await _view(client, case_id)
        state = view.get("state")
        if not isinstance(state, dict):
            raise LocalE2E01Error("local_e2e01_state_missing")
        status = state.get("status")
        if status in {"AWAITING_APPROVAL", "BLOCKED", "COMPLETE"}:
            return view, receipts
        if status == "READY":
            receipts.append(await _submit_next(client, case_id, state))
            view = await _view(client, case_id)
            state = view.get("state")
            if not isinstance(state, dict):
                raise LocalE2E01Error("local_e2e01_state_missing")
            status = state.get("status")
        if status not in {"QUEUED", "RUNNING"}:
            raise LocalE2E01Error(
                "local_e2e01_unexpected_runtime_state",
                evidence={"status": status, "phase": state.get("phase")},
            )
        receipt = await _run_worker(env)
        if receipt.get("status") != "completed":
            raise LocalE2E01Error(
                "local_e2e01_worker_unexpected_idle",
                evidence={"worker": receipt},
            )
        receipts.append(receipt)
    raise LocalE2E01Error("local_e2e01_transition_budget_exhausted")


def _gate(view: dict[str, Any], expected: str) -> dict[str, Any]:
    state = view.get("state")
    gate = view.get("pending_gate")
    if (
        not isinstance(state, dict)
        or state.get("status") != "AWAITING_APPROVAL"
        or state.get("human_gate") != expected
        or not isinstance(gate, dict)
        or gate.get("type") != expected
    ):
        raise LocalE2E01Error(
            "local_e2e01_expected_gate_missing",
            evidence={
                "expected": expected,
                "status": state.get("status") if isinstance(state, dict) else None,
                "human_gate": state.get("human_gate") if isinstance(state, dict) else None,
            },
        )
    return gate


async def _with_runtime(target: URL, authorized_head: str, operation: Any) -> Any:
    checkout, frontend = run02._validate_frontend_and_checkout(authorized_head)
    run02._require_port_free(run02._BACKEND_HOST, run02._BACKEND_PORT)
    run02._require_port_free(run02._FRONTEND_HOST, run02._FRONTEND_PORT)
    env = run02._runtime_env(target)
    with tempfile.TemporaryDirectory(prefix="contentengine-local-e2e01-") as raw:
        runtimes = await run02._start_services(
            env=env,
            npm=frontend["npm"],
            log_dir=Path(raw),
        )
        try:
            settings = get_settings()
            readiness = await run02._await_services_ready(
                runtimes,
                settings_version=settings.app_version,
                settings_environment="development",
            )
            async with httpx.AsyncClient(
                base_url=_API_BASE,
                timeout=httpx.Timeout(30.0),
                follow_redirects=False,
            ) as client:
                preflight = await _api(client, "GET", "/journal/operator/preflight")
                if preflight.get("status") != "READY":
                    raise LocalE2E01Error(
                        "local_e2e01_operator_preflight_blocked",
                        evidence={"preflight": preflight},
                    )
                return await operation(client, env, checkout, readiness)
        finally:
            await _stop_services(runtimes)


async def _start(args: argparse.Namespace) -> dict[str, object]:
    state_file = args.state_file.expanduser().resolve()
    if state_file.exists():
        raise LocalE2E01Error("local_e2e01_state_file_exists")
    backup = args.backup.expanduser().resolve()
    manifest = args.manifest.expanduser().resolve() if args.manifest else backup.with_suffix(".json")
    intake = _load_intake(args.intake.expanduser().resolve())
    run02._validate_frontend_and_checkout(args.authorized_head)
    target, database = await _prepare_database(backup, manifest)
    engine = create_async_engine(target, poolclass=NullPool)
    state: dict[str, object] = {
        "format_version": _STATE_FORMAT,
        "authorized_head": args.authorized_head,
        "runtime_database": target.database,
        "intake_sha256": _json_sha256(intake),
        "phase": "database_ready",
        "restart_verified": False,
        "source_before": database["source_before"],
    }
    _write_state(state_file, state)
    try:
        before = await _runtime_counts(engine)

        async def first(client: httpx.AsyncClient, env: dict[str, str], checkout: dict[str, object], readiness: dict[str, object]) -> dict[str, object]:
            created = await _api(client, "POST", "/journal/operator/intakes", intake)
            case_id = created.get("content_case_id")
            if not isinstance(case_id, str):
                raise LocalE2E01Error("local_e2e01_case_id_missing")
            view, receipts = await _drive_to_gate(client, case_id, env)
            return {
                "checkout": checkout,
                "readiness": readiness,
                "created": created,
                "view": view,
                "gate": _gate(view, "angle"),
                "receipts": receipts,
            }

        first_result = await _with_runtime(target, args.authorized_head, first)
        created = first_result["created"]
        angle_gate = first_result["gate"]
        assert isinstance(created, dict) and isinstance(angle_gate, dict)
        case_id = created.get("content_case_id")
        assert isinstance(case_id, str)
        at_gate = await _runtime_counts(engine)

        async def restart(client: httpx.AsyncClient, _env: dict[str, str], checkout: dict[str, object], readiness: dict[str, object]) -> dict[str, object]:
            view = await _view(client, case_id)
            return {
                "checkout": checkout,
                "readiness": readiness,
                "view": view,
                "gate": _gate(view, "angle"),
            }

        restarted = await _with_runtime(target, args.authorized_head, restart)
        restarted_gate = restarted["gate"]
        assert isinstance(restarted_gate, dict)
        if restarted_gate.get("artifact") != angle_gate.get("artifact"):
            raise LocalE2E01Error("local_e2e01_restart_angle_binding_changed")
        after_restart = await _runtime_counts(engine)
        if after_restart != at_gate:
            raise LocalE2E01Error(
                "local_e2e01_restart_created_duplicate_work",
                evidence={"before_restart": at_gate, "after_restart": after_restart},
            )
        state.update(
            {
                "phase": "angle_gate",
                "restart_verified": True,
                "content_case_id": case_id,
                "bootstrap_run_id": created.get("bootstrap_run_id"),
                "originality_pack_id": created.get("originality_pack_id"),
                "angle_artifact": angle_gate.get("artifact"),
                "counts_before": before,
                "counts_at_angle_gate": at_gate,
            }
        )
        _write_state(state_file, state)
        return {
            "status": "AWAITING_FOUNDER_ANGLE",
            "state_file": str(state_file),
            "content_case_id": case_id,
            "restart_verified": True,
            "angle_gate": angle_gate,
            "receipts": first_result["receipts"],
            "runtime_database": target.database,
        }
    except Exception:
        state["phase"] = "blocked"
        _write_state(state_file, state)
        raise
    finally:
        await engine.dispose()


async def _status(args: argparse.Namespace) -> dict[str, object]:
    state = _load_state(args.state_file.expanduser().resolve())
    if state.get("authorized_head") != args.authorized_head:
        raise LocalE2E01Error("local_e2e01_authorized_head_mismatch")
    target = _target_from_state(state)
    case_id = state.get("content_case_id")
    if not isinstance(case_id, str):
        raise LocalE2E01Error("local_e2e01_case_not_created")

    async def operation(client: httpx.AsyncClient, _env: dict[str, str], checkout: dict[str, object], readiness: dict[str, object]) -> dict[str, object]:
        return {"checkout": checkout, "readiness": readiness, "view": await _view(client, case_id)}

    proof = await _with_runtime(target, args.authorized_head, operation)
    return {"status": "OK", "proof": proof, "session": state}


async def _approve_angle(args: argparse.Namespace) -> dict[str, object]:
    state_file = args.state_file.expanduser().resolve()
    state = _load_state(state_file)
    if state.get("authorized_head") != args.authorized_head or state.get("restart_verified") is not True:
        raise LocalE2E01Error("local_e2e01_angle_authorization_state_invalid")
    target = _target_from_state(state)
    case_id = state.get("content_case_id")
    if not isinstance(case_id, str):
        raise LocalE2E01Error("local_e2e01_case_not_created")

    async def operation(client: httpx.AsyncClient, env: dict[str, str], _checkout: dict[str, object], _readiness: dict[str, object]) -> dict[str, object]:
        view = await _view(client, case_id)
        gate = _gate(view, "angle")
        candidates = gate.get("candidates")
        if not isinstance(candidates, list):
            raise LocalE2E01Error("local_e2e01_angle_candidates_missing")
        selected = next((x for x in candidates if isinstance(x, dict) and x.get("angle_id") == args.angle_id), None)
        if selected is None:
            raise LocalE2E01Error("local_e2e01_angle_candidate_not_found")
        artifact = gate.get("artifact")
        state_row = view.get("state")
        if not isinstance(artifact, dict) or not isinstance(state_row, dict):
            raise LocalE2E01Error("local_e2e01_angle_binding_missing")
        decision = await _api(
            client,
            "POST",
            f"/journal/operator/cases/{case_id}/decisions",
            {
                "scope": "angle",
                "decision": "approved",
                "expected_state_version": state_row["state_version"],
                "idempotency_key": f"local-e2e01:{case_id}:angle:{args.angle_id}",
                "artifact_id": artifact["id"],
                "artifact_version": artifact["version"],
                "artifact_hash": artifact["content_hash"],
                "selected_angle_id": selected["angle_id"],
                "selected_candidate_hash": selected["candidate_hash"],
                "locale_variant_id": None,
                "comment": "Founder approved LOCAL-E2E-01 Angle.",
            },
        )
        next_view, receipts = await _drive_to_gate(client, case_id, env)
        return {
            "decision": decision,
            "selected_angle": selected,
            "outline_gate": _gate(next_view, "outline"),
            "receipts": receipts,
        }

    result = await _with_runtime(target, args.authorized_head, operation)
    state["phase"] = "outline_gate"
    state["selected_angle_id"] = args.angle_id
    outline_gate = result["outline_gate"]
    assert isinstance(outline_gate, dict)
    state["outline_artifact"] = outline_gate.get("artifact")
    _write_state(state_file, state)
    return {"status": "AWAITING_FOUNDER_OUTLINE", **result}


async def _approve_outline(args: argparse.Namespace) -> dict[str, object]:
    state_file = args.state_file.expanduser().resolve()
    state = _load_state(state_file)
    if state.get("authorized_head") != args.authorized_head:
        raise LocalE2E01Error("local_e2e01_authorized_head_mismatch")
    target = _target_from_state(state)
    case_id = state.get("content_case_id")
    if not isinstance(case_id, str):
        raise LocalE2E01Error("local_e2e01_case_not_created")

    async def operation(client: httpx.AsyncClient, env: dict[str, str], _checkout: dict[str, object], _readiness: dict[str, object]) -> dict[str, object]:
        view = await _view(client, case_id)
        gate = _gate(view, "outline")
        artifact = gate.get("artifact")
        state_row = view.get("state")
        if not isinstance(artifact, dict) or not isinstance(state_row, dict):
            raise LocalE2E01Error("local_e2e01_outline_binding_missing")
        decision = await _api(
            client,
            "POST",
            f"/journal/operator/cases/{case_id}/decisions",
            {
                "scope": "outline",
                "decision": "approved",
                "expected_state_version": state_row["state_version"],
                "idempotency_key": f"local-e2e01:{case_id}:outline:{artifact['content_hash']}",
                "artifact_id": artifact["id"],
                "artifact_version": artifact["version"],
                "artifact_hash": artifact["content_hash"],
                "selected_angle_id": None,
                "selected_candidate_hash": None,
                "locale_variant_id": None,
                "comment": "Founder approved LOCAL-E2E-01 Outline.",
            },
        )
        next_view, receipts = await _drive_to_gate(client, case_id, env)
        next_state = next_view.get("state")
        if not isinstance(next_state, dict):
            raise LocalE2E01Error("local_e2e01_state_missing")
        if next_state.get("status") == "BLOCKED":
            return {"decision": decision, "view": next_view, "receipts": receipts, "blocked": True}
        if next_state.get("human_gate") != "final_review":
            raise LocalE2E01Error("local_e2e01_final_gate_not_reached", evidence={"state": next_state})
        review = await _api(client, "GET", f"/journal/review-cases/{case_id}")
        return {"decision": decision, "view": next_view, "review": review, "receipts": receipts, "blocked": False}

    result = await _with_runtime(target, args.authorized_head, operation)
    if result.get("blocked") is True:
        state["phase"] = "blocked"
        _write_state(state_file, state)
        return {"status": "BLOCKED", **result}
    state["phase"] = "final_review"
    _write_state(state_file, state)
    return {"status": "AWAITING_FOUNDER_FINAL", **result}


async def _approve_final(args: argparse.Namespace) -> dict[str, object]:
    state_file = args.state_file.expanduser().resolve()
    state = _load_state(state_file)
    if state.get("authorized_head") != args.authorized_head:
        raise LocalE2E01Error("local_e2e01_authorized_head_mismatch")
    target = _target_from_state(state)
    case_id = state.get("content_case_id")
    if not isinstance(case_id, str):
        raise LocalE2E01Error("local_e2e01_case_not_created")

    async def operation(client: httpx.AsyncClient, _env: dict[str, str], _checkout: dict[str, object], _readiness: dict[str, object]) -> dict[str, object]:
        view = await _view(client, case_id)
        state_row = view.get("state")
        lanes = view.get("quality_lanes")
        if not isinstance(state_row, dict) or state_row.get("human_gate") != "final_review" or not isinstance(lanes, list):
            raise LocalE2E01Error("local_e2e01_final_gate_missing")
        lane = next((x for x in lanes if isinstance(x, dict) and x.get("locale") == args.locale), None)
        if lane is None or not isinstance(lane.get("locale_variant_id"), str):
            raise LocalE2E01Error("local_e2e01_final_locale_not_found")
        decision = await _api(
            client,
            "POST",
            f"/journal/operator/cases/{case_id}/decisions",
            {
                "scope": "final",
                "decision": args.decision,
                "expected_state_version": state_row["state_version"],
                "idempotency_key": f"local-e2e01:{case_id}:final:{args.locale}:{args.decision}",
                "artifact_id": None,
                "artifact_version": None,
                "artifact_hash": None,
                "selected_angle_id": None,
                "selected_candidate_hash": None,
                "locale_variant_id": lane["locale_variant_id"],
                "comment": args.comment,
            },
        )
        return {
            "decision": decision,
            "view": await _view(client, case_id),
            "review": await _api(client, "GET", f"/journal/review-cases/{case_id}"),
        }

    result = await _with_runtime(target, args.authorized_head, operation)
    view = result["view"]
    assert isinstance(view, dict)
    current = view.get("state")
    complete = isinstance(current, dict) and current.get("status") == "COMPLETE"
    state["phase"] = "complete" if complete else "final_review"
    _write_state(state_file, state)
    return {"status": "COMPLETE" if complete else "AWAITING_FOUNDER_FINAL", **result}


async def _finish(args: argparse.Namespace) -> dict[str, object]:
    state_file = args.state_file.expanduser().resolve()
    state = _load_state(state_file)
    if state.get("authorized_head") != args.authorized_head:
        raise LocalE2E01Error("local_e2e01_authorized_head_mismatch")
    target = _target_from_state(state)
    case_id = state.get("content_case_id")
    if not isinstance(case_id, str):
        raise LocalE2E01Error("local_e2e01_case_not_created")
    engine = create_async_engine(target, poolclass=NullPool)
    settings = get_settings()
    try:
        async def operation(client: httpx.AsyncClient, _env: dict[str, str], _checkout: dict[str, object], _readiness: dict[str, object]) -> dict[str, object]:
            return {
                "view": await _view(client, case_id),
                "review": await _api(client, "GET", f"/journal/review-cases/{case_id}"),
            }

        result = await _with_runtime(target, args.authorized_head, operation)
        view = result["view"]
        review = result["review"]
        assert isinstance(view, dict) and isinstance(review, dict)
        state_row = view.get("state")
        if not isinstance(state_row, dict) or state_row.get("status") != "COMPLETE":
            raise LocalE2E01Error("local_e2e01_case_not_complete")
        if review.get("publication_state") != "NOT_PUBLISHED":
            raise LocalE2E01Error("local_e2e01_publication_lock_failed")
        counts = await _runtime_counts(engine)
        baseline = state.get("counts_before")
        if not isinstance(baseline, dict):
            raise LocalE2E01Error("local_e2e01_baseline_counts_missing")
        publish_delta = counts["publish_events"] - int(baseline.get("publish_events", 0))
        version_delta = counts["content_versions"] - int(
            baseline.get("content_versions", 0)
        )
        if publish_delta != 0:
            raise LocalE2E01Error(
                "local_e2e01_publication_event_present",
                evidence={"publish_event_delta": publish_delta},
            )
        if version_delta != 2:
            raise LocalE2E01Error(
                "local_e2e01_bilingual_versions_missing",
                evidence={"content_version_delta": version_delta},
            )
        if await _source_snapshot(settings.database_url) != state.get("source_before"):
            raise LocalE2E01Error("local_e2e01_operational_source_changed")
        state["phase"] = "verified_complete"
        state["final_counts"] = counts
        _write_state(state_file, state)
        return {
            "status": "PASS_LOCAL_CONTENT_PRODUCTION_READY",
            "content_case_id": case_id,
            "restart_verified": state.get("restart_verified"),
            "review": review,
            "counts": counts,
            "deltas": {
                "content_versions": version_delta,
                "publish_events": publish_delta,
            },
            "operational_source_unchanged": True,
            "runtime_database": target.database,
            "cleanup_required": True,
        }
    finally:
        await engine.dispose()


async def _cleanup(args: argparse.Namespace) -> dict[str, object]:
    state_file = args.state_file.expanduser().resolve()
    state = _load_state(state_file)
    if state.get("authorized_head") != args.authorized_head:
        raise LocalE2E01Error("local_e2e01_authorized_head_mismatch")
    if state.get("phase") not in {"verified_complete", "blocked"}:
        raise LocalE2E01Error("local_e2e01_cleanup_not_authorized", evidence={"phase": state.get("phase")})
    target = _target_from_state(state)
    await data02._drop_database(target)
    state["runtime_database_dropped"] = True
    _write_state(state_file, state)
    return {"status": "CLEANED", "runtime_database": target.database, "state_file": str(state_file)}


async def _main() -> int:
    args = _parse_args()
    try:
        if args.command == "start":
            result = await _start(args)
        elif args.command == "status":
            result = await _status(args)
        elif args.command == "approve-angle":
            result = await _approve_angle(args)
        elif args.command == "approve-outline":
            result = await _approve_outline(args)
        elif args.command == "approve-final":
            result = await _approve_final(args)
        elif args.command == "finish":
            result = await _finish(args)
        elif args.command == "cleanup":
            result = await _cleanup(args)
        else:
            raise LocalE2E01Error("local_e2e01_command_invalid")
    except (LocalE2E01Error, data02.Data02RehearsalError, RecoverySafetyError, run02.Run02Error) as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "mode": "local_e2e01",
            "blocker": getattr(exc, "code", type(exc).__name__),
            "evidence": getattr(exc, "evidence", {}),
        }, sort_keys=True, indent=2))
        return 2
    except Exception as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "mode": "local_e2e01",
            "blocker": "local_e2e01_unexpected_failure",
            "evidence": {"error_class": type(exc).__name__},
        }, sort_keys=True, indent=2))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
