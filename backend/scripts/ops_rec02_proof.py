from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    LocaleVariant,
    NeedHypothesis,
    Project,
    SettingsSnapshot,
)
from app.modules.harness.models import ContentRun, Job, StepRun
from app.modules.harness.outbox import (
    IdempotencyConflictError,
    OutboxStateError,
    ReconciliationRequiredError,
    ReconciliationResult,
    SideEffectExecutionResult,
    SideEffectRequest,
    apply_reconciliation_result,
    create_outbox_intent,
    prepare_outbox_dispatch,
    side_effect_request,
)
from app.modules.harness.persistence import (
    LeaseOwnershipError,
    claim_next_job,
    complete_job,
    enqueue_job,
    reclaim_expired_job,
)
from app.modules.knowledge.persistence import content_hash
from app.modules.system.recovery import (
    RecoverySafetyError,
    validate_operational_database_source,
    validate_restore_target,
)
from scripts import ops_data02_rehearsal as data02
from scripts import ops_release_lifecycle as historical

_SOURCE_REVISION = "20260915_0034"
_TARGET_REVISION = "20260926_0044"
_CRASH_EXIT_CODE = 17
_SHORT_LEASE_SECONDS = 1
_REPLACEMENT_LEASE_SECONDS = 30


class Rec02Error(RuntimeError):
    def __init__(self, code: str, *, evidence: dict[str, object] | None = None) -> None:
        self.code = code
        self.evidence = dict(evidence or {})
        super().__init__(code)


class _FakeSideEffect:
    def __init__(self) -> None:
        self.records: dict[str, tuple[str, str]] = {}
        self.execute_count = 0

    async def execute(self, request: SideEffectRequest) -> SideEffectExecutionResult:
        self.execute_count += 1
        external_ref = f"synthetic://{request.idempotency_key}"
        self.records[request.idempotency_key] = (request.payload_ref, external_ref)
        return SideEffectExecutionResult(external_ref=external_ref)

    async def reconcile(self, request: SideEffectRequest) -> ReconciliationResult:
        record = self.records.get(request.idempotency_key)
        if record is None:
            return ReconciliationResult(outcome="confirmed_absent")
        payload_ref, external_ref = record
        if payload_ref != request.payload_ref:
            return ReconciliationResult(
                outcome="conflict",
                external_ref=external_ref,
                message="synthetic payload conflict",
            )
        return ReconciliationResult(
            outcome="confirmed_success",
            external_ref=external_ref,
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P1 REC-02 crash/restart and reconciliation proof"
    )
    parser.add_argument("backup", type=Path, nargs="?")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--authorized-head")
    parser.add_argument("--child-claim", action="store_true")
    return parser.parse_args()


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


async def _callback_delay(seconds: float) -> None:
    loop = asyncio.get_running_loop()
    event = asyncio.Event()
    handle = loop.call_later(seconds, event.set)
    try:
        await event.wait()
    finally:
        handle.cancel()


async def _status_counts(engine: AsyncEngine, *, table_name: str) -> dict[str, int]:
    if table_name not in {"jobs", "outbox_intents"}:
        raise Rec02Error("unsupported_status_table")
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


async def _require_quiescent(engine: AsyncEngine) -> dict[str, object]:
    jobs = await _status_counts(engine, table_name="jobs")
    active_jobs = {
        status: jobs.get(status, 0)
        for status in ("queued", "leased")
        if jobs.get(status, 0) > 0
    }
    if active_jobs:
        raise Rec02Error("rec02_existing_active_jobs", evidence={"jobs": active_jobs})

    outbox = await _status_counts(engine, table_name="outbox_intents")
    active_outbox = {
        status: outbox.get(status, 0)
        for status in ("pending", "processing", "needs_reconciliation")
        if outbox.get(status, 0) > 0
    }
    if active_outbox:
        raise Rec02Error(
            "rec02_existing_active_outbox",
            evidence={"outbox_intents": active_outbox},
        )
    return {"jobs": jobs, "outbox_intents": outbox}


async def _create_synthetic_run(
    session: AsyncSession,
) -> tuple[ContentRun, StepRun]:
    project = await session.scalar(
        select(Project).where(Project.slug == "motgu").limit(1)
    )
    if project is None:
        raise Rec02Error("rec02_project_missing")

    suffix = uuid4().hex[:12]
    hypothesis = NeedHypothesis(
        project_id=project.id,
        type="problem",
        statement=f"REC-02 synthetic recovery proof {suffix}",
        audience_scope="synthetic recovery verifier",
        situation="local crash/restart proof",
        origin="FOUNDER",
    )
    session.add(hypothesis)
    await session.flush()

    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale="en",
        reader="synthetic recovery verifier",
        situation="local crash/restart proof",
        need="Prove durable recovery without duplicate effects.",
        question="Can a claimed job resume safely after worker exit?",
        intent="test",
        promise="Recovery reuses durable state and reconciles ambiguity.",
        coverage_requirements_json=[],
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="REC-02 synthetic local proof only.",
        next_discovery_step="None.",
        decision="CREATE",
        priority="NOW",
        reasons_json=["rec02"],
        suggested_content_type="journal",
        suggested_role="cluster",
    )
    session.add(opportunity)
    await session.flush()

    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=hypothesis.id,
        content_opportunity_id=opportunity.id,
        desired_action="Verify recovery.",
        content_hypothesis="Durable leases prevent stale worker completion.",
        originality_statement="Synthetic REC-02 proof only.",
        reader_before="Unverified",
        reader_after="Recovery semantics verified",
    )
    session.add(content_case)
    await session.flush()

    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="cluster",
        primary_question="Can a claimed job resume safely after worker exit?",
        primary_intent="test",
    )
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={"rec02": True},
        source_version_refs_json=["rec02:synthetic"],
        content_hash=content_hash(f"rec02:{suffix}"),
    )
    session.add_all([variant, snapshot])
    await session.flush()

    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        run_mode="create",
        status="running",
        current_step="rec02_crash",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()

    step = StepRun(
        run_id=run.id,
        step_key="rec02_crash",
        attempt=1,
        status="pending",
        input_artifact_refs_json=[],
        output_artifact_refs_json=[],
    )
    session.add(step)
    await session.flush()
    return run, step


async def _child_claim() -> int:
    worker_id = os.environ.get("REC02_WORKER_ID", "").strip()
    if not worker_id:
        print(json.dumps({"status": "BLOCKED", "blocker": "child_worker_id_missing"}))
        return 2

    from app.core.database import SessionLocal

    async with SessionLocal() as session:
        async with session.begin():
            job = await claim_next_job(
                session,
                worker_id=worker_id,
                lease_duration=timedelta(seconds=_SHORT_LEASE_SECONDS),
            )
            if job is None:
                print(json.dumps({"status": "BLOCKED", "blocker": "child_job_missing"}))
                return 2
            receipt = {
                "status": "CLAIMED_THEN_EXITING",
                "job_id": str(job.id),
                "attempt": job.attempt,
                "lease_owner": job.lease_owner,
            }

    print(json.dumps(receipt, sort_keys=True), flush=True)
    return _CRASH_EXIT_CODE


async def _spawn_crashing_worker(
    *,
    target: URL,
    worker_id: str,
) -> dict[str, object]:
    env = os.environ.copy()
    env["APP_ENV"] = "development"
    env["DATABASE_URL"] = target.render_as_string(hide_password=False)
    env["REC02_WORKER_ID"] = worker_id
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "scripts.ops_rec02_proof",
        "--child-claim",
        cwd=str(_backend_root()),
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != _CRASH_EXIT_CODE:
        raise Rec02Error(
            "rec02_crash_child_unexpected_exit",
            evidence={
                "exit_code": process.returncode,
                "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            },
        )
    lines = [
        line.strip()
        for line in stdout.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    if not lines:
        raise Rec02Error("rec02_crash_child_receipt_missing")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise Rec02Error("rec02_crash_child_receipt_invalid") from exc
    if not isinstance(payload, dict) or payload.get("status") != "CLAIMED_THEN_EXITING":
        raise Rec02Error("rec02_crash_child_receipt_invalid")
    return {
        "exit_code": process.returncode,
        "job_id": payload.get("job_id"),
        "attempt": payload.get("attempt"),
        "lease_owner": payload.get("lease_owner"),
    }


async def _prove_crash_recovery(
    engine: AsyncEngine,
    *,
    target: URL,
) -> dict[str, object]:
    dead_worker = f"rec02-dead:{uuid4().hex}"
    replacement_worker = f"rec02-replacement:{uuid4().hex}"

    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            run, step = await _create_synthetic_run(session)
            job = await enqueue_job(
                session,
                run_id=run.id,
                step_run_id=step.id,
                dedupe_key=f"rec02-crash:{run.id}",
            )
            job_id = job.id

    child = await _spawn_crashing_worker(target=target, worker_id=dead_worker)
    if child.get("job_id") != str(job_id):
        raise Rec02Error("rec02_crash_child_claimed_wrong_job")

    await _callback_delay(_SHORT_LEASE_SECONDS + 0.25)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            reclaimed = await reclaim_expired_job(
                session,
                worker_id=replacement_worker,
                lease_duration=timedelta(seconds=_REPLACEMENT_LEASE_SECONDS),
            )
            if reclaimed is None or reclaimed.id != job_id:
                raise Rec02Error("rec02_expired_job_not_reclaimed")
            if reclaimed.lease_owner != replacement_worker or reclaimed.attempt != 2:
                raise Rec02Error("rec02_reclaim_receipt_invalid")

            stale_blocked = False
            try:
                await complete_job(
                    session,
                    job_id=job_id,
                    worker_id=dead_worker,
                )
            except LeaseOwnershipError:
                stale_blocked = True
            if not stale_blocked:
                raise Rec02Error("rec02_stale_worker_completed_job")

            completed = await complete_job(
                session,
                job_id=job_id,
                worker_id=replacement_worker,
            )
            if completed.status != "completed":
                raise Rec02Error("rec02_replacement_completion_failed")

    return {
        "job_id": str(job_id),
        "dead_worker_exit_code": child["exit_code"],
        "initial_attempt": child["attempt"],
        "reclaimed_attempt": 2,
        "stale_worker_completion": "BLOCKED",
        "replacement_completion": "COMPLETED",
        "lease_wait": "event_callback",
    }


async def _claim_specific_next(
    session: AsyncSession,
    *,
    expected_job_id: UUID,
    worker_id: str,
    lease_seconds: int = _REPLACEMENT_LEASE_SECONDS,
) -> Job:
    job = await claim_next_job(
        session,
        worker_id=worker_id,
        lease_duration=timedelta(seconds=lease_seconds),
    )
    if job is None or job.id != expected_job_id:
        raise Rec02Error("rec02_outbox_job_claim_mismatch")
    return job


async def _prove_idempotency_and_reconciliation(
    engine: AsyncEngine,
) -> dict[str, object]:
    worker_a = f"rec02-outbox-a:{uuid4().hex}"
    worker_b = f"rec02-outbox-b:{uuid4().hex}"
    fake = _FakeSideEffect()

    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            run = await session.scalar(
                select(ContentRun)
                .where(ContentRun.current_step == "rec02_crash")
                .order_by(ContentRun.created_at.desc())
                .limit(1)
            )
            if run is None:
                raise Rec02Error("rec02_synthetic_run_missing")

            step = StepRun(
                run_id=run.id,
                step_key="rec02_outbox",
                attempt=1,
                status="pending",
                input_artifact_refs_json=[],
                output_artifact_refs_json=[],
            )
            session.add(step)
            await session.flush()
            run.current_step = "rec02_outbox"

            job = await enqueue_job(
                session,
                run_id=run.id,
                step_run_id=step.id,
                dedupe_key=f"rec02-outbox:{run.id}",
            )
            same_job = await enqueue_job(
                session,
                run_id=run.id,
                step_run_id=step.id,
                dedupe_key=f"rec02-outbox:{run.id}",
            )
            if same_job.id != job.id:
                raise Rec02Error("rec02_job_dedupe_failed")

            intent = await create_outbox_intent(
                session,
                run_id=run.id,
                intent_type="synthetic_rec02",
                idempotency_key=f"rec02-intent:{run.id}",
                payload_ref="synthetic://payload-v1",
            )
            replay = await create_outbox_intent(
                session,
                run_id=run.id,
                intent_type="synthetic_rec02",
                idempotency_key=intent.idempotency_key,
                payload_ref=intent.payload_ref,
            )
            if replay.id != intent.id:
                raise Rec02Error("rec02_outbox_replay_failed")

            conflict_blocked = False
            try:
                await create_outbox_intent(
                    session,
                    run_id=run.id,
                    intent_type="synthetic_rec02",
                    idempotency_key=intent.idempotency_key,
                    payload_ref="synthetic://payload-changed",
                )
            except IdempotencyConflictError:
                conflict_blocked = True
            if not conflict_blocked:
                raise Rec02Error("rec02_idempotency_conflict_not_blocked")

            await _claim_specific_next(
                session,
                expected_job_id=job.id,
                worker_id=worker_a,
                lease_seconds=_SHORT_LEASE_SECONDS,
            )
            processing = await prepare_outbox_dispatch(
                session,
                intent_id=intent.id,
                job_id=job.id,
                worker_id=worker_a,
            )
            request = side_effect_request(processing)
            accepted = await fake.execute(request)
            if fake.execute_count != 1:
                raise Rec02Error("rec02_external_execute_count_invalid")

    await _callback_delay(_SHORT_LEASE_SECONDS + 0.25)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            reclaimed = await reclaim_expired_job(
                session,
                worker_id=worker_b,
                lease_duration=timedelta(seconds=_REPLACEMENT_LEASE_SECONDS),
            )
            if reclaimed is None or reclaimed.id != job.id:
                raise Rec02Error("rec02_outbox_job_not_reclaimed")

            blind_retry_blocked = False
            try:
                await prepare_outbox_dispatch(
                    session,
                    intent_id=intent.id,
                    job_id=job.id,
                    worker_id=worker_b,
                )
            except ReconciliationRequiredError:
                blind_retry_blocked = True
            if not blind_retry_blocked:
                raise Rec02Error("rec02_blind_retry_not_blocked")

            current = await session.get(type(intent), intent.id)
            if current is None:
                raise Rec02Error("rec02_outbox_intent_missing")
            result = await fake.reconcile(side_effect_request(current))
            reconciled = await apply_reconciliation_result(
                session,
                intent_id=intent.id,
                job_id=job.id,
                worker_id=worker_b,
                result=result,
            )
            if (
                reconciled.status != "completed"
                or reconciled.external_ref != accepted.external_ref
                or fake.execute_count != 1
            ):
                raise Rec02Error("rec02_reconciliation_success_invalid")

            completed_blocked = False
            try:
                await prepare_outbox_dispatch(
                    session,
                    intent_id=intent.id,
                    job_id=job.id,
                    worker_id=worker_b,
                )
            except OutboxStateError:
                completed_blocked = True
            if not completed_blocked:
                raise Rec02Error("rec02_completed_intent_redispatched")

            await complete_job(
                session,
                job_id=job.id,
                worker_id=worker_b,
            )

    return {
        "job_id": str(job.id),
        "intent_id": str(intent.id),
        "job_dedupe": "REUSED",
        "intent_replay": "REUSED",
        "changed_payload": "CONFLICT_BLOCKED",
        "blind_retry_after_restart": "BLOCKED_PENDING_RECONCILIATION",
        "reconciliation": "CONFIRMED_SUCCESS",
        "external_execute_count": fake.execute_count,
    }


async def _prepare_rec02_database(
    *,
    backup: Path,
    manifest_path: Path,
    source_url: str,
) -> tuple[URL, dict[str, object]]:
    manifest = data02._load_manifest(backup, manifest_path)
    source = validate_operational_database_source(source_url)
    source_revision = data02._manifest_source_revision(manifest, source)
    if source_revision != _SOURCE_REVISION:
        raise Rec02Error("rec02_source_revision_manifest_mismatch")
    chain = data02._upgrade_chain(data02._alembic_script(), source_revision)
    expected_fingerprint = data02._expected_fingerprint(manifest)
    target_url = source.set(database=f"{source.database}_rec02_restore_test")
    target = validate_restore_target(
        source_url=source_url,
        restore_url=target_url.render_as_string(hide_password=False),
    )

    source_engine = create_async_engine(source_url, poolclass=NullPool)
    target_created = False
    try:
        source_revision_live, source_core = await data02._database_state(source_engine)
        source_full = await data02._full_data_fingerprint(source_engine)
        if source_revision_live != _SOURCE_REVISION:
            raise Rec02Error("rec02_operational_revision_drift")
        if source_core.to_dict() != expected_fingerprint:
            raise Rec02Error("rec02_operational_fingerprint_drift")

        target_created = True
        await data02._recreate_database(target)
        data02._restore_backup(backup, target)
        target_engine = create_async_engine(target, poolclass=NullPool)
        try:
            restored_revision, restored_core = await data02._database_state(target_engine)
            restored_full = await data02._full_data_fingerprint(target_engine)
            if restored_revision != _SOURCE_REVISION:
                raise Rec02Error("rec02_restored_revision_mismatch")
            if restored_core.to_dict() != expected_fingerprint:
                raise Rec02Error("rec02_restored_core_mismatch")
            if restored_full != source_full:
                raise Rec02Error("rec02_restored_full_data_mismatch")
            data02._run_alembic_upgrade(target)
            migrated_revision = await data02._migration_revision(target_engine)
            if migrated_revision != _TARGET_REVISION:
                raise Rec02Error("rec02_target_revision_mismatch")
        finally:
            await target_engine.dispose()

        return target, {
            "source_revision": source_revision_live,
            "runtime_revision": _TARGET_REVISION,
            "upgrade_chain": list(chain),
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
        full = await data02._full_data_fingerprint(engine)
        return {
            "revision": revision,
            "core": core.to_dict(),
            "full": full,
        }
    finally:
        await engine.dispose()


async def _main() -> int:
    args = _parse_args()
    if args.child_claim:
        return await _child_claim()

    if args.backup is None or not args.authorized_head:
        print(
            json.dumps(
                {"status": "BLOCKED", "blocker": "backup_and_authorized_head_required"},
                sort_keys=True,
            )
        )
        return 2

    backup = args.backup.expanduser().resolve()
    manifest_path = (
        args.manifest.expanduser().resolve()
        if args.manifest
        else backup.with_suffix(".json")
    )
    target: URL | None = None
    target_created = False
    blocker: Rec02Error | None = None
    evidence: dict[str, object] = {}

    try:
        try:
            checkout = historical._validate_checkout(args.authorized_head)
        except historical.ReleaseLifecycleError as exc:
            raise Rec02Error(exc.code, evidence=exc.evidence) from exc

        from app.core.config import get_settings

        settings = get_settings()
        validate_operational_database_source(settings.database_url)
        source_before = await _source_snapshot(settings.database_url)
        if source_before["revision"] != _SOURCE_REVISION:
            raise Rec02Error("rec02_operational_revision_drift")

        target, database = await _prepare_rec02_database(
            backup=backup,
            manifest_path=manifest_path,
            source_url=settings.database_url,
        )
        target_created = True
        engine = create_async_engine(target, poolclass=NullPool)
        try:
            quiescent_before = await _require_quiescent(engine)
            crash_recovery = await _prove_crash_recovery(engine, target=target)
            reconciliation = await _prove_idempotency_and_reconciliation(engine)
        finally:
            await engine.dispose()

        source_after = await _source_snapshot(settings.database_url)
        if source_after != source_before:
            raise Rec02Error("rec02_operational_source_changed")

        evidence = {
            "status": "READY",
            "mode": "rec02_crash_restart_reconciliation",
            "checkout": checkout,
            "database": database,
            "quiescent_before": quiescent_before,
            "crash_recovery": crash_recovery,
            "idempotency_reconciliation": reconciliation,
            "coordination": "event_exit_callback",
            "external_calls": 0,
            "operational_source": {
                "revision_before": source_before["revision"],
                "revision_after": source_after["revision"],
                "unchanged": True,
            },
        }
    except Rec02Error as exc:
        blocker = exc
    except (data02.Data02RehearsalError, RecoverySafetyError) as exc:
        blocker = Rec02Error(exc.code)
    except Exception as exc:
        blocker = Rec02Error(
            "rec02_unexpected_failure",
            evidence={"error_class": type(exc).__name__},
        )
    finally:
        if target_created and target is not None:
            try:
                await data02._drop_database(target)
            except Exception:
                if blocker is None:
                    blocker = Rec02Error("rec02_database_cleanup_failed")

    if blocker is not None:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "rec02_crash_restart_reconciliation",
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
