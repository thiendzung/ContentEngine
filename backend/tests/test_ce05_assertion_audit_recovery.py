from __future__ import annotations

import copy
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

from app.modules.content_engine.journal.assertion_audit import (
    ASSERTION_AUDIT_EVALUATOR_VERSION,
    ASSERTION_AUDIT_GENERATOR_VERSION,
    AssertionAuditError,
    AssertionAuditGenerator,
)
from app.modules.content_engine.journal.assertion_audit_agent_bridge import (
    assertion_audit_registry_config,
    create_cli_assertion_audit_model_port,
)
from app.modules.content_engine.journal.assertion_audit_execution import (
    _handoff_payload,
    prepare_assertion_audit_run,
)
from app.modules.content_engine.journal.writer import _canonical_hash
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
