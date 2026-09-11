from __future__ import annotations

import copy
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_assertion_audit import (
    FakeAuditModel,
    _passing_output,
    _source,
    isolated_session,
)

from app.core.database import engine
from app.modules.content_engine.journal.assertion_audit import (
    ASSERTION_AUDIT_EVALUATOR_KEY,
    ASSERTION_AUDIT_EVALUATOR_VERSION,
    ASSERTION_AUDIT_GENERATOR_VERSION,
    AssertionAuditError,
    AssertionAuditGenerator,
    _fingerprint,
    _summary,
    validate_assertion_audit_output,
)
from app.modules.content_engine.journal.assertion_audit_agent_bridge import (
    assertion_audit_registry_config,
    create_cli_assertion_audit_model_port,
)
from app.modules.content_engine.journal.assertion_audit_execution import (
    _handoff_payload,
    prepare_assertion_audit_run,
)
from app.modules.content_engine.journal.writer import _canonical_hash, writer_model_input_hash
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ContextManifest,
    ModelCall,
    QualityEvaluation,
    StepRun,
    utc_now,
)
from app.modules.harness.persistence import (
    InvalidStateTransitionError,
    transition_run,
    transition_step_run,
)
from app.modules.harness.runtime import _stable_hash
from app.modules.system.settings_service import (
    active_prompt_definition,
    active_recipe_definition,
    settings_hash,
)


async def _prepare(
    session: AsyncSession,
    *,
    source_input,
    prompt_version: str = "assertion-test:v1",
    recipe_version: str = "assertion-test-recipe:v1",
):
    return await prepare_assertion_audit_run(
        session,
        source_input=source_input,
        task_key=f"assertion_audit_{source_input.writer_input.locale}",
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )


async def _mark_source_waiting(session: AsyncSession, *, source_input) -> None:
    await transition_run(
        session,
        run_id=source_input.writer_input.writer_run.id,
        status="running",
    )
    await transition_run(
        session,
        run_id=source_input.writer_input.writer_run.id,
        status="waiting_approval",
    )


async def _audit(
    session: AsyncSession,
    *,
    source_input,
    execution,
    model,
    provider: str = "fixture-provider",
    model_name: str = "fixture-model",
    prompt_version: str = "assertion-test:v1",
    recipe_version: str = "assertion-test-recipe:v1",
):
    if execution.audit_run.status == "pending":
        await transition_run(session, run_id=execution.audit_run.id, status="running")
    if execution.step_run.status == "pending":
        await transition_step_run(session, step_run_id=execution.step_run.id, status="running")
    result = await AssertionAuditGenerator(max_attempts=1).audit_draft(
        session,
        writer_run_id=source_input.writer_input.writer_run.id,
        revised_draft_artifact_id=source_input.source_artifact.id,
        expected_revised_draft_version=source_input.source_artifact.version,
        expected_revised_draft_hash=source_input.source_artifact.content_hash,
        outline_artifact_id=source_input.writer_input.outline_artifact.id,
        expected_outline_version=source_input.writer_input.outline_artifact.version,
        expected_outline_hash=source_input.writer_input.outline_artifact.content_hash,
        locale=source_input.writer_input.locale,
        model=model,
        provider=provider,
        model_name=model_name,
        context_manifest_id=execution.context_manifest.id,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
        execution_run_id=execution.audit_run.id,
    )
    if execution.step_run.status == "running":
        await transition_step_run(session, step_run_id=execution.step_run.id, status="completed")
    if execution.audit_run.status == "running":
        await transition_run(session, run_id=execution.audit_run.id, status="completed")
    return result


async def _duplicate_completed_audit(
    session: AsyncSession,
    *,
    source_input,
    source_execution,
    source_result,
    created_at: datetime,
    conflicting_summary: bool = False,
    malformed: str | None = None,
    run_status: str = "completed",
):
    """Create a historical duplicate fixture without changing the source run."""

    source_run = source_input.writer_input.writer_run
    payload = copy.deepcopy(source_execution.handoff.content_json)
    assert isinstance(payload, dict)
    duplicate_run = ContentRun(
        id=uuid4(),
        project_id=source_run.project_id,
        content_case_id=source_run.content_case_id,
        locale_variant_id=source_run.locale_variant_id,
        content_item_id=source_run.content_item_id,
        run_mode="eval",
        status=run_status,
        current_step=source_execution.step_run.step_key,
        settings_snapshot_id=source_run.settings_snapshot_id,
        started_at=created_at,
        completed_at=created_at + timedelta(seconds=1),
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(duplicate_run)
    await session.flush()

    duplicate_handoff = Artifact(
        run_id=duplicate_run.id,
        artifact_type="assertion_audit_handoff",
        locale=source_input.writer_input.locale,
        version=1,
        content_json=payload,
        content_hash=_canonical_hash(payload),
    )
    session.add(duplicate_handoff)
    await session.flush()

    duplicate_step = StepRun(
        run_id=duplicate_run.id,
        step_key=source_execution.step_run.step_key,
        attempt=1,
        status="completed",
        input_artifact_refs_json=[
            str(duplicate_handoff.id),
            str(source_input.source_artifact.id),
            str(source_input.writer_input.outline_artifact.id),
        ],
        output_artifact_refs_json=[],
        started_at=created_at,
        completed_at=created_at + timedelta(seconds=1),
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(duplicate_step)
    await session.flush()

    source_manifest = source_execution.context_manifest
    manifest_payload = {
        "run_id": str(duplicate_run.id),
        "step_run_id": str(duplicate_step.id),
        "settings_snapshot_id": str(duplicate_run.settings_snapshot_id),
        "prompt_version": source_manifest.prompt_version,
        "recipe_version": source_manifest.recipe_version,
        "evidence_set_id": str(source_manifest.evidence_set_id),
        "originality_pack_id": str(source_manifest.originality_pack_id),
        "context_artifact_id": (
            str(source_manifest.context_artifact_id)
            if source_manifest.context_artifact_id is not None
            else None
        ),
        "approved_knowledge_refs": source_manifest.approved_knowledge_refs_json,
        "knowledge_chunk_refs": source_manifest.knowledge_chunk_refs_json,
        "golden_example_refs": source_manifest.golden_example_refs_json,
        "tool_result_refs": source_manifest.tool_result_refs_json,
    }
    duplicate_manifest = ContextManifest(
        run_id=duplicate_run.id,
        step_run_id=duplicate_step.id,
        settings_snapshot_id=duplicate_run.settings_snapshot_id,
        prompt_version=source_manifest.prompt_version,
        recipe_version=source_manifest.recipe_version,
        evidence_set_id=source_manifest.evidence_set_id,
        originality_pack_id=source_manifest.originality_pack_id,
        context_artifact_id=source_manifest.context_artifact_id,
        approved_knowledge_refs_json=copy.deepcopy(source_manifest.approved_knowledge_refs_json),
        knowledge_chunk_refs_json=copy.deepcopy(source_manifest.knowledge_chunk_refs_json),
        golden_example_refs_json=copy.deepcopy(source_manifest.golden_example_refs_json),
        tool_result_refs_json=copy.deepcopy(source_manifest.tool_result_refs_json),
        content_hash=_stable_hash(manifest_payload),
    )
    if malformed != "missing_manifest":
        session.add(duplicate_manifest)
        await session.flush()
        if malformed == "duplicate_manifest":
            session.add(
                ContextManifest(
                    run_id=duplicate_run.id,
                    step_run_id=duplicate_step.id,
                    settings_snapshot_id=duplicate_run.settings_snapshot_id,
                    prompt_version=source_manifest.prompt_version,
                    recipe_version=source_manifest.recipe_version,
                    evidence_set_id=source_manifest.evidence_set_id,
                    originality_pack_id=source_manifest.originality_pack_id,
                    context_artifact_id=source_manifest.context_artifact_id,
                    approved_knowledge_refs_json=copy.deepcopy(
                        source_manifest.approved_knowledge_refs_json
                    ),
                    knowledge_chunk_refs_json=copy.deepcopy(
                        source_manifest.knowledge_chunk_refs_json
                    ),
                    golden_example_refs_json=copy.deepcopy(
                        source_manifest.golden_example_refs_json
                    ),
                    tool_result_refs_json=copy.deepcopy(source_manifest.tool_result_refs_json),
                    content_hash=_stable_hash(manifest_payload),
                )
            )
            await session.flush()
    manifest_for_payload = (
        duplicate_manifest if malformed != "missing_manifest" else source_manifest
    )

    source_payload = source_result.artifact.content_json
    assert isinstance(source_payload, dict)
    audit_payload = copy.deepcopy(source_payload)
    model_payload = audit_payload.get("model")
    assert isinstance(model_payload, dict)
    provider = model_payload["provider"]
    model = model_payload["model"]
    assert isinstance(provider, str)
    assert isinstance(model, str)
    if conflicting_summary:
        segments = audit_payload["segments"]
        assert isinstance(segments, list)
        for segment in segments:
            assert isinstance(segment, dict)
            assertions = segment["assertions"]
            assert isinstance(assertions, list)
            if assertions:
                assertion = assertions[0]
                assert isinstance(assertion, dict)
                assertion["support_status"] = "unsupported"
                assertion["severity"] = "critical"
                break
        validated = validate_assertion_audit_output(
            {"locale": source_input.writer_input.locale, "segments": segments},
            audit_input=source_input,
        )
        audit_payload["summary"] = _summary(validated)
    if malformed == "wrong_source":
        source_draft = audit_payload["source_draft"]
        assert isinstance(source_draft, dict)
        source_draft["id"] = str(uuid4())
    execution_context = audit_payload["execution_context"]
    assert isinstance(execution_context, dict)
    execution_context = audit_payload["execution_context"]
    assert isinstance(execution_context, dict)
    audit_payload["execution_context"] = {
        **execution_context,
        "context_manifest_id": str(manifest_for_payload.id),
        "context_manifest_hash": manifest_for_payload.content_hash,
    }
    audit_payload["generation_fingerprint"] = _fingerprint(
        audit_input=source_input,
        model_input_hash=writer_model_input_hash(source_input.model_input),
        provider=provider,
        model=model,
        prompt_version=source_manifest.prompt_version,
        recipe_version=source_manifest.recipe_version,
        context_manifest_hash=manifest_for_payload.content_hash,
    )
    duplicate_artifact = Artifact(
        run_id=duplicate_run.id,
        step_run_id=duplicate_step.id,
        artifact_type="assertion_audit",
        locale=source_input.writer_input.locale,
        version=1,
        content_json=audit_payload,
        content_hash=(
            "0" * 64
            if malformed == "stale_artifact_hash"
            else _canonical_hash(audit_payload)
        ),
    )
    if malformed != "missing_artifact":
        session.add(duplicate_artifact)
        await session.flush()
        duplicate_step.output_artifact_refs_json = [str(duplicate_artifact.id)]
        if malformed == "duplicate_artifact":
            session.add(
                Artifact(
                    run_id=duplicate_run.id,
                    step_run_id=duplicate_step.id,
                    artifact_type="assertion_audit",
                    locale=source_input.writer_input.locale,
                    version=2,
                    content_json=copy.deepcopy(audit_payload),
                    content_hash=_canonical_hash(audit_payload),
                )
            )
        for _attempt in range(int(model_payload["model_calls"])):
            session.add(
                ModelCall(
                    run_id=duplicate_run.id,
                    step_run_id=duplicate_step.id,
                    context_manifest_id=duplicate_manifest.id,
                    task_key=duplicate_step.step_key,
                    provider=provider,
                    model=model,
                    purpose="Fixture assertion audit",
                    prompt_version=source_manifest.prompt_version,
                    started_at=created_at,
                    completed_at=created_at + timedelta(seconds=1),
                    finish_reason="stop",
                    status="completed",
                )
            )
    summary = audit_payload["summary"]
    assert isinstance(summary, dict)
    if malformed not in {"missing_evaluation", "missing_artifact"}:
        evaluation = QualityEvaluation(
            run_id=duplicate_run.id,
            artifact_id=duplicate_artifact.id,
            evaluator_key=ASSERTION_AUDIT_EVALUATOR_KEY,
            evaluator_version=ASSERTION_AUDIT_EVALUATOR_VERSION,
            evaluator_type="deterministic",
            result=str(summary["result"]),
            score=None,
            severity="critical" if summary["result"] == "fail" else "none",
            findings_json={
                "source_draft_id": str(source_input.source_artifact.id),
                "source_draft_hash": source_input.source_artifact.content_hash,
                "assertion_audit_artifact_id": str(duplicate_artifact.id),
                "assertion_audit_hash": duplicate_artifact.content_hash,
                **summary,
            },
        )
        session.add(evaluation)
        if malformed == "duplicate_evaluation":
            session.add(
                QualityEvaluation(
                    run_id=duplicate_run.id,
                    artifact_id=duplicate_artifact.id,
                    evaluator_key=ASSERTION_AUDIT_EVALUATOR_KEY,
                    evaluator_version=ASSERTION_AUDIT_EVALUATOR_VERSION,
                    evaluator_type="deterministic",
                    result=str(summary["result"]),
                    score=None,
                    severity="critical" if summary["result"] == "fail" else "none",
                    findings_json=copy.deepcopy(evaluation.findings_json),
                )
            )
    if malformed == "duplicate_step":
        session.add(
            StepRun(
                run_id=duplicate_run.id,
                step_key=duplicate_step.step_key,
                attempt=2,
                status="completed",
                input_artifact_refs_json=copy.deepcopy(
                    duplicate_step.input_artifact_refs_json
                ),
                output_artifact_refs_json=[],
                started_at=created_at,
                completed_at=created_at + timedelta(seconds=1),
            )
        )
    await session.flush()
    return duplicate_run, duplicate_handoff, duplicate_step, duplicate_manifest, duplicate_artifact


async def _runtime_counts(session: AsyncSession) -> dict[str, int]:
    models = {
        "content_runs": ContentRun,
        "step_runs": StepRun,
        "context_manifests": ContextManifest,
        "model_calls": ModelCall,
        "artifacts": Artifact,
        "quality_evaluations": QualityEvaluation,
    }
    return {
        table: len((await session.scalars(select(model))).all())
        for table, model in models.items()
    }


async def _add_fixture_model_call(session: AsyncSession, *, execution) -> None:
    session.add(
        ModelCall(
            run_id=execution.audit_run.id,
            step_run_id=execution.step_run.id,
            context_manifest_id=execution.context_manifest.id,
            task_key=execution.step_run.step_key,
            provider="fixture-provider",
            model="fixture-model",
            purpose="Fixture assertion audit",
            prompt_version="assertion-test:v1",
            started_at=utc_now(),
            completed_at=utc_now(),
            finish_reason="stop",
            status="completed",
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_completed_duplicates_recover_canonical_without_side_effects() -> None:
    async with isolated_session() as session:
        fixture, _source_artifact, source_input = await _source(session)
        await _mark_source_waiting(session, source_input=source_input)
        execution = await _prepare(session, source_input=source_input)
        result = await _audit(
            session,
            source_input=source_input,
            execution=execution,
            model=FakeAuditModel([_passing_output(source_input)]),
        )
        await _add_fixture_model_call(session, execution=execution)
        duplicate = await _duplicate_completed_audit(
            session,
            source_input=source_input,
            source_execution=execution,
            source_result=result,
            created_at=execution.audit_run.created_at + timedelta(seconds=1),
        )
        historical = {
            execution.audit_run.id: (
                execution.audit_run.status,
                result.artifact.content_hash,
                result.evaluation.id,
            ),
            duplicate[0].id: (duplicate[0].status, duplicate[4].content_hash, None),
        }
        before = await _runtime_counts(session)

        recovered = await _prepare(session, source_input=source_input)
        assert recovered.audit_run.id == execution.audit_run.id
        assert recovered.handoff.id == execution.handoff.id
        assert recovered.audit_run_reused is True
        assert recovered.reusable_run_count == 2
        assert recovered.duplicate_recovery_used is True
        assert set(recovered.duplicate_run_ids) == {execution.audit_run.id, duplicate[0].id}

        rerun_model = FakeAuditModel([_passing_output(source_input)])
        rerun = await _audit(
            session,
            source_input=source_input,
            execution=recovered,
            model=rerun_model,
        )
        after = await _runtime_counts(session)
        assert after == before
        assert rerun.reused is True
        assert rerun.model_attempts == 0
        assert rerun.artifact.id == result.artifact.id
        assert rerun.evaluation.id == result.evaluation.id
        assert rerun_model.calls == 0
        assert historical[execution.audit_run.id] == (
            execution.audit_run.status,
            result.artifact.content_hash,
            result.evaluation.id,
        )
        assert historical[duplicate[0].id] == (
            duplicate[0].status,
            duplicate[4].content_hash,
            None,
        )


@pytest.mark.asyncio
async def test_conflicting_completed_duplicates_fail_closed() -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, source_input = await _source(session)
        await _mark_source_waiting(session, source_input=source_input)
        execution = await _prepare(session, source_input=source_input)
        result = await _audit(
            session,
            source_input=source_input,
            execution=execution,
            model=FakeAuditModel([_passing_output(source_input)]),
        )
        await _add_fixture_model_call(session, execution=execution)
        await _duplicate_completed_audit(
            session,
            source_input=source_input,
            source_execution=execution,
            source_result=result,
            created_at=execution.audit_run.created_at + timedelta(seconds=1),
            conflicting_summary=True,
        )

        with pytest.raises(AssertionAuditError, match="assertion_audit_duplicate_summary_conflict"):
            await _prepare(session, source_input=source_input)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "malformed",
    [
        "missing_manifest",
        "missing_artifact",
        "missing_evaluation",
        "duplicate_step",
        "duplicate_manifest",
        "duplicate_artifact",
        "duplicate_evaluation",
        "stale_artifact_hash",
        "wrong_source",
    ],
)
async def test_malformed_completed_duplicate_fails_closed(malformed: str) -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, source_input = await _source(session)
        await _mark_source_waiting(session, source_input=source_input)
        execution = await _prepare(session, source_input=source_input)
        result = await _audit(
            session,
            source_input=source_input,
            execution=execution,
            model=FakeAuditModel([_passing_output(source_input)]),
        )
        await _duplicate_completed_audit(
            session,
            source_input=source_input,
            source_execution=execution,
            source_result=result,
            created_at=execution.audit_run.created_at + timedelta(seconds=1),
            malformed=malformed,
        )

        with pytest.raises(AssertionAuditError):
            await _prepare(session, source_input=source_input)


@pytest.mark.asyncio
async def test_active_duplicate_fails_closed_without_mutation() -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, source_input = await _source(session)
        await _mark_source_waiting(session, source_input=source_input)
        first = await _prepare(session, source_input=source_input)
        result = await _audit(
            session,
            source_input=source_input,
            execution=first,
            model=FakeAuditModel([_passing_output(source_input)]),
        )
        await _duplicate_completed_audit(
            session,
            source_input=source_input,
            source_execution=first,
            source_result=result,
            created_at=first.audit_run.created_at + timedelta(seconds=1),
            run_status="running",
        )

        with pytest.raises(AssertionAuditError, match="assertion_audit_active_duplicate"):
            await _prepare(session, source_input=source_input)


def test_postgresql_source_writer_lock_is_the_concurrency_serialization_point() -> None:
    assert engine.dialect.name == "postgresql"
    statement = (
        select(ContentRun)
        .where(ContentRun.id == uuid4())
        .with_for_update()
    )
    compiled = str(statement.compile(dialect=engine.sync_engine.dialect))
    assert "FOR UPDATE" in compiled


@pytest.mark.asyncio
async def test_assertion_audit_recovery_owns_eval_records_and_reuses_completed_run() -> None:
    async with isolated_session() as session:
        fixture, _source_artifact, source_input = await _source(session)
        await _mark_source_waiting(session, source_input=source_input)

        first_execution = await _prepare(session, source_input=source_input)
        first_result = await _audit(
            session,
            source_input=source_input,
            execution=first_execution,
            model=FakeAuditModel([_passing_output(source_input)]),
        )
        second_execution = await _prepare(session, source_input=source_input)
        second_result = await _audit(
            session,
            source_input=source_input,
            execution=second_execution,
            model=FakeAuditModel([_passing_output(source_input)]),
        )

        assert first_execution.audit_run.run_mode == "eval"
        assert first_execution.audit_run.id != fixture.writer_input.writer_run.id
        assert second_execution.audit_run.id == first_execution.audit_run.id
        assert second_execution.handoff.id == first_execution.handoff.id
        assert first_result.artifact.run_id == first_execution.audit_run.id
        assert first_result.evaluation.run_id == first_execution.audit_run.id
        assert (
            first_execution.handoff.content_json["generator"]["version"]
            == ASSERTION_AUDIT_GENERATOR_VERSION
        )
        assert (
            first_result.artifact.content_json["generator"]["version"]
            == ASSERTION_AUDIT_GENERATOR_VERSION
        )
        assert first_result.evaluation.evaluator_version == ASSERTION_AUDIT_EVALUATOR_VERSION
        assert second_result.reused is True
        assert second_result.model_attempts == 0
        assert second_result.artifact.id == first_result.artifact.id
        assert second_result.evaluation.id == first_result.evaluation.id
        assert fixture.writer_input.writer_run.status == "waiting_approval"

        audit_steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == first_execution.audit_run.id,
                        StepRun.step_key == "assertion_audit_en",
                    )
                )
            ).all()
        )
        audit_manifests = list(
            (
                await session.scalars(
                    select(ContextManifest).where(
                        ContextManifest.run_id == first_execution.audit_run.id,
                    )
                )
            ).all()
        )
        audit_artifacts = list(
            (
                await session.scalars(
                    select(Artifact).where(Artifact.run_id == first_execution.audit_run.id)
                )
            ).all()
        )
        audit_evaluations = list(
            (
                await session.scalars(
                    select(QualityEvaluation).where(
                        QualityEvaluation.run_id == first_execution.audit_run.id,
                    )
                )
            ).all()
        )
        audit_model_calls = list(
            (
                await session.scalars(
                    select(ModelCall).where(ModelCall.run_id == first_execution.audit_run.id)
                )
            ).all()
        )
        assert len(audit_steps) == 1
        assert len(audit_manifests) == 1
        assert (
            len([a for a in audit_artifacts if a.artifact_type == "assertion_audit_handoff"])
            == 1
        )
        assert len([a for a in audit_artifacts if a.artifact_type == "assertion_audit"]) == 1
        assert len(audit_evaluations) == 1
        assert audit_model_calls == []
        assert (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == fixture.writer_input.writer_run.id,
                    Artifact.artifact_type == "assertion_audit",
                )
            )
        ).all() == []


@pytest.mark.asyncio
async def test_assertion_audit_failed_eval_is_preserved_and_retry_uses_new_eval_run() -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, source_input = await _source(session)
        await _mark_source_waiting(session, source_input=source_input)
        execution = await _prepare(session, source_input=source_input)
        await transition_run(session, run_id=execution.audit_run.id, status="running")
        await transition_step_run(session, step_run_id=execution.step_run.id, status="running")

        with pytest.raises(AssertionAuditError, match="assertion_audit_model_output_invalid"):
            await AssertionAuditGenerator(max_attempts=1).audit_draft(
                session,
                writer_run_id=source_input.writer_input.writer_run.id,
                revised_draft_artifact_id=source_input.source_artifact.id,
                expected_revised_draft_version=source_input.source_artifact.version,
                expected_revised_draft_hash=source_input.source_artifact.content_hash,
                outline_artifact_id=source_input.writer_input.outline_artifact.id,
                expected_outline_version=source_input.writer_input.outline_artifact.version,
                expected_outline_hash=source_input.writer_input.outline_artifact.content_hash,
                locale=source_input.writer_input.locale,
                model=FakeAuditModel([{}]),
                provider="fixture-provider",
                model_name="fixture-model",
                context_manifest_id=execution.context_manifest.id,
                prompt_version="assertion-test:v1",
                recipe_version="assertion-test-recipe:v1",
                execution_run_id=execution.audit_run.id,
            )
        await transition_step_run(session, step_run_id=execution.step_run.id, status="failed")
        execution.audit_run.failure_code = "assertion_audit_failed"
        await transition_run(session, run_id=execution.audit_run.id, status="failed")

        retry = await _prepare(session, source_input=source_input)
        assert retry.audit_run.id != execution.audit_run.id
        assert retry.audit_run.status == "pending"
        assert execution.audit_run.status == "failed"
        assert retry.audit_run_reused is False
        with pytest.raises(InvalidStateTransitionError):
            await transition_run(session, run_id=execution.audit_run.id, status="running")


@pytest.mark.asyncio
async def test_v2_failed_eval_diagnostic_is_not_reused_by_v3() -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, source_input = await _source(session)
        await _mark_source_waiting(session, source_input=source_input)
        source_run = source_input.writer_input.writer_run
        settings_snapshot = await session.get(SettingsSnapshot, source_run.settings_snapshot_id)
        assert settings_snapshot is not None
        task_key = f"assertion_audit_{source_input.writer_input.locale}"
        legacy_payload = copy.deepcopy(
            _handoff_payload(
                source_input=source_input,
                settings_snapshot=settings_snapshot,
                task_key=task_key,
            )
        )
        generator = legacy_payload["generator"]
        assert isinstance(generator, dict)
        generator["version"] = "ce05.journal_assertion_audit.v2"
        legacy_run = ContentRun(
            id=uuid4(),
            project_id=source_run.project_id,
            content_case_id=source_run.content_case_id,
            locale_variant_id=source_input.writer_input.locale_variant.id,
            content_item_id=source_run.content_item_id,
            run_mode="eval",
            status="failed",
            current_step=task_key,
            settings_snapshot_id=source_run.settings_snapshot_id,
            started_at=utc_now(),
            failure_code="legacy_assertion_audit_failed",
        )
        session.add(legacy_run)
        await session.flush()
        legacy_handoff = Artifact(
            run_id=legacy_run.id,
            artifact_type="assertion_audit_handoff",
            locale=source_input.writer_input.locale,
            version=1,
            content_json=legacy_payload,
            content_hash=_canonical_hash(legacy_payload),
        )
        session.add(legacy_handoff)
        await session.flush()

        execution = await _prepare(session, source_input=source_input)

        assert execution.audit_run.id != legacy_run.id
        assert execution.audit_run.status == "pending"
        assert execution.handoff.id != legacy_handoff.id
        assert (
            execution.handoff.content_json["generator"]["version"]
            == ASSERTION_AUDIT_GENERATOR_VERSION
        )
        assert execution.audit_run_reused is False


@pytest.mark.asyncio
async def test_assertion_audit_model_call_is_owned_by_eval_run() -> None:
    from test_ce05_writer import FakeWriterRunner

    async with isolated_session() as session:
        fixture, _source_artifact, source_input = await _source(session)
        await _mark_source_waiting(session, source_input=source_input)
        config = assertion_audit_registry_config("en")
        prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=config.recipe_key,
            content_type="journal",
            locale="en",
            task_key=config.task_key,
        )
        execution = await prepare_assertion_audit_run(
            session,
            source_input=source_input,
            task_key=config.task_key,
            prompt_version=f"{prompt.prompt_key}:v{prompt.version}",
            recipe_version=f"{recipe.recipe_key}:v{recipe.version}",
        )
        snapshot = SettingsSnapshot(
            id=source_input.writer_input.writer_run.settings_snapshot_id,
            project_id=source_input.writer_input.writer_run.project_id,
            resolved_settings_json={
                "models": {"angle": {"route": "audit-test"}},
                "model_routes": {
                    "audit-test": {"provider": "codex_cli", "model": "test-model"}
                },
            },
            source_version_refs_json=["recovery-test"],
            content_hash=settings_hash(
                {
                    "models": {"angle": {"route": "audit-test"}},
                    "model_routes": {
                        "audit-test": {"provider": "codex_cli", "model": "test-model"}
                    },
                }
            ),
        )
        registry = AgentRunnerRegistry()
        runner = FakeWriterRunner(_passing_output(source_input))
        registry.register("codex_cli", runner)
        port = await create_cli_assertion_audit_model_port(
            session,
            run_id=execution.audit_run.id,
            settings_snapshot=snapshot,
            context_manifest_id=execution.context_manifest.id,
            runner_registry=registry,
            locale="en",
        )
        first = await _audit(
            session,
            source_input=source_input,
            execution=execution,
            model=port,
            provider="codex_cli",
            model_name="test-model",
            prompt_version=f"{prompt.prompt_key}:v{prompt.version}",
            recipe_version=f"{recipe.recipe_key}:v{recipe.version}",
        )
        second_execution = await _prepare(
            session,
            source_input=source_input,
            prompt_version=f"{prompt.prompt_key}:v{prompt.version}",
            recipe_version=f"{recipe.recipe_key}:v{recipe.version}",
        )
        second = await AssertionAuditGenerator(max_attempts=1).audit_draft(
            session,
            writer_run_id=source_input.writer_input.writer_run.id,
            revised_draft_artifact_id=source_input.source_artifact.id,
            expected_revised_draft_version=source_input.source_artifact.version,
            expected_revised_draft_hash=source_input.source_artifact.content_hash,
            outline_artifact_id=source_input.writer_input.outline_artifact.id,
            expected_outline_version=source_input.writer_input.outline_artifact.version,
            expected_outline_hash=source_input.writer_input.outline_artifact.content_hash,
            locale=source_input.writer_input.locale,
            model=port,
            provider="codex_cli",
            model_name="test-model",
            context_manifest_id=second_execution.context_manifest.id,
            prompt_version=f"{prompt.prompt_key}:v{prompt.version}",
            recipe_version=f"{recipe.recipe_key}:v{recipe.version}",
            execution_run_id=second_execution.audit_run.id,
        )

        assert first.artifact.run_id == execution.audit_run.id
        assert first.evaluation.run_id == execution.audit_run.id
        assert second.reused is True
        assert second.artifact.id == first.artifact.id
        assert len(runner.requests) == 1
        calls = list(
            (
                await session.scalars(
                    select(ModelCall).where(ModelCall.task_key == config.task_key)
                )
            ).all()
        )
        assert len(calls) == 1
        assert calls[0].run_id == execution.audit_run.id
        assert calls[0].context_manifest_id == execution.context_manifest.id
        assert (
            await session.scalars(
                select(ModelCall).where(
                    ModelCall.run_id == fixture.writer_input.writer_run.id,
                    ModelCall.task_key == config.task_key,
                )
            )
        ).all() == []


@pytest.mark.asyncio
async def test_exact_failed_vi_writer_source_is_allowed_without_resurrection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.modules.content_engine.journal.assertion_audit_execution as execution_module

    async with isolated_session() as session:
        _fixture, _source_artifact, source_input = await _source(session, locale="vi-VN")
        await transition_run(
            session,
            run_id=source_input.writer_input.writer_run.id,
            status="running",
        )
        await transition_run(
            session,
            run_id=source_input.writer_input.writer_run.id,
            status="failed",
        )
        monkeypatch.setattr(
            execution_module,
            "LEGACY_FAILED_VI_WRITER_RUN_ID",
            source_input.writer_input.writer_run.id,
        )
        monkeypatch.setattr(
            execution_module,
            "LEGACY_FAILED_VI_DRAFT_ID",
            source_input.source_artifact.id,
        )
        monkeypatch.setattr(
            execution_module,
            "LEGACY_FAILED_VI_DRAFT_HASH",
            source_input.source_artifact.content_hash,
        )
        monkeypatch.setattr(
            execution_module,
            "LEGACY_FAILED_VI_DRAFT_VERSION",
            source_input.source_artifact.version,
        )
        execution = await _prepare(session, source_input=source_input)
        assert execution.audit_run.run_mode == "eval"
        assert execution.source_input.writer_input.writer_run.status == "failed"
