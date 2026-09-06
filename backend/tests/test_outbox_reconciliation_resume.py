from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, engine
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
    OutboxIntent,
    OutboxStateError,
    ReconciliationRequiredError,
    ReconciliationResult,
    SideEffectExecutionResult,
    SideEffectRequest,
    apply_reconciliation_result,
    complete_outbox_intent,
    create_outbox_intent,
    get_outbox_intent,
    mark_outbox_needs_reconciliation,
    prepare_outbox_dispatch,
    requires_reconciliation,
    side_effect_request,
)
from app.modules.harness.persistence import (
    claim_next_job,
    complete_job,
    enqueue_job,
    reclaim_expired_job,
)
from app.modules.knowledge.persistence import content_hash


class FakeExternalSideEffect:
    def __init__(self) -> None:
        self.records: dict[str, tuple[str, str]] = {}
        self.execute_count = 0
        self.force_unknown = False

    async def execute(self, request: SideEffectRequest) -> SideEffectExecutionResult:
        self.execute_count += 1
        external_ref = f"external://{request.idempotency_key}"
        self.records[request.idempotency_key] = (request.payload_ref, external_ref)
        return SideEffectExecutionResult(external_ref=external_ref)

    async def reconcile(self, request: SideEffectRequest) -> ReconciliationResult:
        if self.force_unknown:
            return ReconciliationResult(outcome="unknown", message="provider timeout")
        record = self.records.get(request.idempotency_key)
        if record is None:
            return ReconciliationResult(outcome="confirmed_absent")
        payload_ref, external_ref = record
        if payload_ref != request.payload_ref:
            return ReconciliationResult(
                outcome="conflict",
                external_ref=external_ref,
                message="same key points to different payload",
            )
        return ReconciliationResult(
            outcome="confirmed_success",
            external_ref=external_ref,
        )


async def _create_run_and_step(session: AsyncSession) -> tuple[ContentRun, StepRun]:
    project = (
        await session.execute(select(Project).where(Project.slug == "motgu"))
    ).scalar_one()
    suffix = uuid4().hex[:8]
    hypothesis = NeedHypothesis(
        project_id=project.id,
        type="problem",
        statement=f"CE03 PR-D synthetic {suffix}",
        audience_scope="test reader",
        situation="outbox test",
        origin="FOUNDER",
    )
    session.add(hypothesis)
    await session.flush()
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale="en",
        reader="test reader",
        situation="outbox test",
        need="Durable side effect",
        question="Can an external action resume safely?",
        intent="test",
        promise="Avoid duplicate side effects",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Synthetic outbox proof",
        next_discovery_step="None",
        decision="CREATE",
        priority="NOW",
        reasons_json=["test"],
        suggested_content_type="journal",
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=hypothesis.id,
        content_opportunity_id=opportunity.id,
        desired_action="Continue",
        content_hypothesis="Durable side effects prevent duplicates",
        originality_statement="Synthetic only",
        reader_before="Uncertain",
        reader_after="Certain",
    )
    session.add(content_case)
    await session.flush()
    locale_variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="primary",
        primary_question="Can an external action resume safely?",
        primary_intent="test",
    )
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={},
        source_version_refs_json=["settings:test"],
        content_hash=content_hash(f"outbox-settings:{suffix}"),
    )
    session.add_all([locale_variant, snapshot])
    await session.flush()
    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=locale_variant.id,
        run_mode="create",
        status="running",
        current_step="publish",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    step = StepRun(
        run_id=run.id,
        step_key="publish",
        attempt=1,
        status="pending",
    )
    session.add(step)
    await session.flush()
    return run, step


@pytest.mark.asyncio
async def test_restart_reconciles_accepted_side_effect_without_duplicate() -> None:
    fake = FakeExternalSideEffect()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run, step = await _create_run_and_step(session)
            intent = await create_outbox_intent(
                session,
                run_id=run.id,
                intent_type="publish",
                idempotency_key=f"publish:{run.id}",
                payload_ref="artifact://final-v1",
            )
            same = await create_outbox_intent(
                session,
                run_id=run.id,
                intent_type="publish",
                idempotency_key=intent.idempotency_key,
                payload_ref=intent.payload_ref,
            )
            assert same.id == intent.id
            with pytest.raises(IdempotencyConflictError):
                await create_outbox_intent(
                    session,
                    run_id=run.id,
                    intent_type="publish",
                    idempotency_key=intent.idempotency_key,
                    payload_ref="artifact://different",
                )

            job = await enqueue_job(
                session,
                run_id=run.id,
                step_run_id=step.id,
                dedupe_key=f"outbox:{intent.idempotency_key}",
            )
            claimed = await claim_next_job(
                session,
                worker_id="worker-1",
                lease_duration=timedelta(seconds=30),
            )
            assert claimed is not None and claimed.id == job.id
            processing = await prepare_outbox_dispatch(
                session,
                intent_id=intent.id,
                job_id=job.id,
                worker_id="worker-1",
            )
            assert processing.status == "processing"
            request = side_effect_request(processing)

            accepted = await fake.execute(request)
            assert accepted.external_ref
            assert fake.execute_count == 1
            # Simulate crash after external accept but before local success persistence.
            await session.execute(
                update(Job)
                .where(Job.id == job.id)
                .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await session.flush()

            reclaimed = await reclaim_expired_job(
                session,
                worker_id="worker-2",
                lease_duration=timedelta(seconds=30),
            )
            assert reclaimed is not None and reclaimed.id == job.id
            after_restart = await get_outbox_intent(session, intent_id=intent.id)
            assert requires_reconciliation(after_restart)
            with pytest.raises(ReconciliationRequiredError):
                await prepare_outbox_dispatch(
                    session,
                    intent_id=intent.id,
                    job_id=job.id,
                    worker_id="worker-2",
                )

            reconciliation = await fake.reconcile(side_effect_request(after_restart))
            with pytest.raises(OutboxStateError, match="valid job lease"):
                await apply_reconciliation_result(
                    session,
                    intent_id=intent.id,
                    job_id=job.id,
                    worker_id="worker-1",
                    result=reconciliation,
                )

            completed = await apply_reconciliation_result(
                session,
                intent_id=intent.id,
                job_id=job.id,
                worker_id="worker-2",
                result=reconciliation,
            )
            assert completed.status == "completed"
            assert completed.external_ref == accepted.external_ref

            # Even while worker-2 still owns the lease, completed intent blocks resend.
            with pytest.raises(OutboxStateError, match="completed"):
                await prepare_outbox_dispatch(
                    session,
                    intent_id=intent.id,
                    job_id=job.id,
                    worker_id="worker-2",
                )
            assert fake.execute_count == 1

            await complete_job(session, job_id=job.id, worker_id="worker-2")
            assert fake.execute_count == 1

            # Once the job is complete, lack of a valid lease independently blocks resend.
            with pytest.raises(OutboxStateError, match="valid job lease"):
                await prepare_outbox_dispatch(
                    session,
                    intent_id=intent.id,
                    job_id=job.id,
                    worker_id="worker-2",
                )
            assert fake.execute_count == 1
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_confirmed_absent_can_retry_but_unknown_cannot_blind_retry() -> None:
    fake = FakeExternalSideEffect()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run, step = await _create_run_and_step(session)
            intent = await create_outbox_intent(
                session,
                run_id=run.id,
                intent_type="publish",
                idempotency_key=f"publish:{run.id}",
                payload_ref="artifact://final-v1",
            )
            job = await enqueue_job(
                session,
                run_id=run.id,
                step_run_id=step.id,
                dedupe_key=f"outbox:{intent.idempotency_key}",
            )
            claimed = await claim_next_job(
                session,
                worker_id="worker-a",
                lease_duration=timedelta(seconds=30),
            )
            assert claimed is not None
            processing = await prepare_outbox_dispatch(
                session,
                intent_id=intent.id,
                job_id=job.id,
                worker_id="worker-a",
            )
            absent = await fake.reconcile(side_effect_request(processing))
            assert absent.outcome == "confirmed_absent"
            pending = await apply_reconciliation_result(
                session,
                intent_id=intent.id,
                job_id=job.id,
                worker_id="worker-a",
                result=absent,
            )
            assert pending.status == "pending"
            processing = await prepare_outbox_dispatch(
                session,
                intent_id=intent.id,
                job_id=job.id,
                worker_id="worker-a",
            )
            result = await fake.execute(side_effect_request(processing))
            completed = await complete_outbox_intent(
                session,
                intent_id=intent.id,
                job_id=job.id,
                worker_id="worker-a",
                result=result,
            )
            assert completed.status == "completed"
            assert fake.execute_count == 1

            run2, step2 = await _create_run_and_step(session)
            intent2 = await create_outbox_intent(
                session,
                run_id=run2.id,
                intent_type="publish",
                idempotency_key=f"publish:{run2.id}",
                payload_ref="artifact://final-v1",
            )
            job2 = await enqueue_job(
                session,
                run_id=run2.id,
                step_run_id=step2.id,
                dedupe_key=f"outbox:{intent2.idempotency_key}",
            )
            claimed2 = await claim_next_job(
                session,
                worker_id="worker-b",
                lease_duration=timedelta(seconds=30),
            )
            assert claimed2 is not None
            processing2 = await prepare_outbox_dispatch(
                session,
                intent_id=intent2.id,
                job_id=job2.id,
                worker_id="worker-b",
            )
            ambiguous = await mark_outbox_needs_reconciliation(
                session,
                intent_id=intent2.id,
                job_id=job2.id,
                worker_id="worker-b",
                error_class="tool_transient",
                message="provider timeout after send",
            )
            assert ambiguous.status == "needs_reconciliation"
            fake.force_unknown = True
            unknown = await fake.reconcile(side_effect_request(processing2))
            unresolved = await apply_reconciliation_result(
                session,
                intent_id=intent2.id,
                job_id=job2.id,
                worker_id="worker-b",
                result=unknown,
            )
            assert unresolved.status == "needs_reconciliation"
            with pytest.raises(ReconciliationRequiredError):
                await prepare_outbox_dispatch(
                    session,
                    intent_id=intent2.id,
                    job_id=job2.id,
                    worker_id="worker-b",
                )
            assert fake.execute_count == 1
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_reconciliation_conflict_stops_side_effect_explicitly() -> None:
    fake = FakeExternalSideEffect()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run, step = await _create_run_and_step(session)
            intent = await create_outbox_intent(
                session,
                run_id=run.id,
                intent_type="publish",
                idempotency_key=f"publish:{run.id}",
                payload_ref="artifact://final-v1",
            )
            job = await enqueue_job(
                session,
                run_id=run.id,
                step_run_id=step.id,
                dedupe_key=f"outbox:{intent.idempotency_key}",
            )
            claimed = await claim_next_job(
                session,
                worker_id="worker-conflict",
                lease_duration=timedelta(seconds=30),
            )
            assert claimed is not None
            await prepare_outbox_dispatch(
                session,
                intent_id=intent.id,
                job_id=job.id,
                worker_id="worker-conflict",
            )
            failed = await apply_reconciliation_result(
                session,
                intent_id=intent.id,
                job_id=job.id,
                worker_id="worker-conflict",
                result=ReconciliationResult(
                    outcome="conflict",
                    external_ref="external://different-record",
                    message="external payload does not match durable intent",
                ),
            )
            assert failed.status == "failed"
            assert failed.error_json is not None
            assert failed.error_json["class"] == "publish_conflict"
            with pytest.raises(OutboxStateError, match="status: failed"):
                await prepare_outbox_dispatch(
                    session,
                    intent_id=intent.id,
                    job_id=job.id,
                    worker_id="worker-conflict",
                )
            assert fake.execute_count == 0
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_processing_state_is_committed_before_external_call_and_survives_restart() -> None:
    fake = FakeExternalSideEffect()
    cleanup_ids: dict[str, UUID] = {}
    request: SideEffectRequest | None = None
    external_ref: str | None = None
    try:
        async with SessionLocal() as session:
            run, step = await _create_run_and_step(session)
            content_case = await session.get(ContentCase, run.content_case_id)
            assert content_case is not None
            intent = await create_outbox_intent(
                session,
                run_id=run.id,
                intent_type="publish",
                idempotency_key=f"publish:{run.id}",
                payload_ref="artifact://committed-final-v1",
            )
            job = await enqueue_job(
                session,
                run_id=run.id,
                step_run_id=step.id,
                dedupe_key=f"outbox:{intent.idempotency_key}",
            )
            cleanup_ids = {
                "intent": intent.id,
                "job": job.id,
                "step": step.id,
                "run": run.id,
                "locale_variant": run.locale_variant_id,
                "settings_snapshot": run.settings_snapshot_id,
                "content_case": run.content_case_id,
                "opportunity": content_case.content_opportunity_id,
                "hypothesis": content_case.need_hypothesis_id,
            }
            await session.commit()

        async with SessionLocal() as session:
            claimed = await claim_next_job(
                session,
                worker_id="commit-worker-1",
                lease_duration=timedelta(seconds=30),
            )
            assert claimed is not None and claimed.id == cleanup_ids["job"]
            processing = await prepare_outbox_dispatch(
                session,
                intent_id=cleanup_ids["intent"],
                job_id=cleanup_ids["job"],
                worker_id="commit-worker-1",
            )
            request = side_effect_request(processing)
            await session.commit()

        # The external call happens only after `processing` is durably committed.
        assert request is not None
        accepted = await fake.execute(request)
        external_ref = accepted.external_ref
        assert fake.execute_count == 1

        async with SessionLocal() as session:
            persisted = await get_outbox_intent(
                session,
                intent_id=cleanup_ids["intent"],
            )
            assert persisted.status == "processing"
            job = await session.get(Job, cleanup_ids["job"])
            assert job is not None
            job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()

        async with SessionLocal() as session:
            reclaimed = await reclaim_expired_job(
                session,
                worker_id="commit-worker-2",
                lease_duration=timedelta(seconds=30),
            )
            assert reclaimed is not None and reclaimed.id == cleanup_ids["job"]
            persisted = await get_outbox_intent(
                session,
                intent_id=cleanup_ids["intent"],
            )
            assert requires_reconciliation(persisted)
            reconciliation = await fake.reconcile(side_effect_request(persisted))
            completed = await apply_reconciliation_result(
                session,
                intent_id=cleanup_ids["intent"],
                job_id=cleanup_ids["job"],
                worker_id="commit-worker-2",
                result=reconciliation,
            )
            assert completed.status == "completed"
            await complete_job(
                session,
                job_id=cleanup_ids["job"],
                worker_id="commit-worker-2",
            )
            await session.commit()

        async with SessionLocal() as session:
            final_intent = await get_outbox_intent(
                session,
                intent_id=cleanup_ids["intent"],
            )
            assert final_intent.status == "completed"
            assert final_intent.external_ref == external_ref
            assert fake.execute_count == 1
    finally:
        if cleanup_ids:
            async with SessionLocal() as session:
                await session.execute(
                    delete(OutboxIntent).where(OutboxIntent.id == cleanup_ids["intent"])
                )
                await session.execute(delete(Job).where(Job.id == cleanup_ids["job"]))
                await session.execute(
                    delete(StepRun).where(StepRun.id == cleanup_ids["step"])
                )
                await session.execute(
                    delete(ContentRun).where(ContentRun.id == cleanup_ids["run"])
                )
                await session.execute(
                    delete(LocaleVariant).where(
                        LocaleVariant.id == cleanup_ids["locale_variant"]
                    )
                )
                await session.execute(
                    delete(ContentCase).where(
                        ContentCase.id == cleanup_ids["content_case"]
                    )
                )
                await session.execute(
                    delete(ContentOpportunity).where(
                        ContentOpportunity.id == cleanup_ids["opportunity"]
                    )
                )
                await session.execute(
                    delete(NeedHypothesis).where(
                        NeedHypothesis.id == cleanup_ids["hypothesis"]
                    )
                )
                await session.execute(
                    delete(SettingsSnapshot).where(
                        SettingsSnapshot.id == cleanup_ids["settings_snapshot"]
                    )
                )
                await session.commit()
