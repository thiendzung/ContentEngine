from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_assertion_audit import _passing_output, isolated_session
from test_ce05_writer import FakeWriterModel, _draft_payload, _generate_draft, _writer_fixture

import app.modules.content_engine.journal.post_audit_cleanup as cleanup_module
import scripts.post_audit_cleanup_real_o4_en as cleanup_cli
from app.modules.content_engine.journal.assertion_audit import (
    _summary,
    load_assertion_audit_input,
    validate_assertion_audit_output,
)
from app.modules.content_engine.journal.post_audit_cleanup import (
    CLOSING_SEGMENT_ID,
    CLOSING_SENTENCE_TO_REMOVE,
    POST_AUDIT_CLEANUP_GENERATOR_VERSION,
    POST_AUDIT_CLEANUP_TASK_KEY,
    PostAuditCleanupGenerator,
    load_post_audit_cleanup_input,
)
from app.modules.content_engine.journal.writer import _canonical_hash, persist_journal_draft
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ModelCall,
    QualityEvaluation,
    StepRun,
    ToolCall,
    utc_now,
)
from app.modules.harness.persistence import RUN_TRANSITIONS, transition_run, transition_step_run

pytestmark = pytest.mark.asyncio(loop_scope="module")


SOURCE_CLOSING = (
    "Take your time. If anything is unclear, ask before deciding. "
    "There is nothing formal about asking for a clearer answer."
)
RESULT_CLOSING = "Take your time. If anything is unclear, ask before deciding."


async def _cleanup_fixture(
    session: AsyncSession,
) -> tuple[object, Artifact, Artifact, QualityEvaluation]:
    fixture = await _writer_fixture(session, locale="en")
    draft_payload = _draft_payload(fixture.writer_input, "en")
    draft_payload["closing_markdown"] = SOURCE_CLOSING
    generated = await _generate_draft(
        session,
        fixture,
        FakeWriterModel([draft_payload]),
    )
    source_v2 = await persist_journal_draft(
        session,
        writer_input=fixture.writer_input,
        draft=generated.draft,
        provider="fixture-provider",
        model="fixture-model",
        model_calls=1,
        prompt_version=fixture.prompt_version,
        recipe_version=fixture.recipe_version,
        context_manifest=fixture.manifest,
        generator_version="fixture.journal_review_revise.v1",
    )
    source_v3 = await persist_journal_draft(
        session,
        writer_input=fixture.writer_input,
        draft=generated.draft,
        provider="fixture-provider",
        model="fixture-model",
        model_calls=1,
        prompt_version=fixture.prompt_version,
        recipe_version=fixture.recipe_version,
        context_manifest=fixture.manifest,
        generator_version="fixture.journal_post_audit_revision.v1",
    )
    assert source_v2.version == 2
    assert source_v3.version == 3
    await transition_run(
        session,
        run_id=fixture.writer_input.writer_run.id,
        status="running",
    )
    await transition_run(
        session,
        run_id=fixture.writer_input.writer_run.id,
        status="waiting_approval",
    )

    audit_input = await load_assertion_audit_input(
        session,
        writer_run_id=fixture.writer_input.writer_run.id,
        revised_draft_artifact_id=source_v3.id,
        expected_revised_draft_version=3,
        expected_revised_draft_hash=source_v3.content_hash,
        outline_artifact_id=fixture.outline_result.artifact.id,
        expected_outline_version=fixture.outline_result.artifact.version,
        expected_outline_hash=fixture.outline_result.artifact.content_hash,
        locale="en",
    )
    output = _passing_output(audit_input)
    for raw_segment in cast(list[object], output["segments"]):
        segment = cast(dict[str, object], raw_segment)
        if segment["segment_id"] == CLOSING_SEGMENT_ID:
            segment["assertions"] = [
                {
                    "assertion_text": CLOSING_SENTENCE_TO_REMOVE,
                    "assertion_type": "brand_statement",
                    "support_status": "unsupported",
                    "severity": "critical",
                    "evidence_refs": [],
                    "originality_refs": [],
                    "rationale": "Exact failed audit fixture.",
                }
            ]
    audited = validate_assertion_audit_output(output, audit_input=audit_input)
    summary = _summary(audited)
    eval_run = ContentRun(
        project_id=fixture.writer_input.writer_run.project_id,
        content_case_id=fixture.writer_input.writer_run.content_case_id,
        locale_variant_id=fixture.writer_input.locale_variant.id,
        content_item_id=None,
        run_mode="eval",
        status="completed",
        current_step="assertion_audit_en",
        settings_snapshot_id=fixture.writer_input.writer_run.settings_snapshot_id,
        started_at=utc_now(),
        completed_at=utc_now(),
    )
    session.add(eval_run)
    await session.flush()
    audit_payload: dict[str, object] = {
        "schema_version": 1,
        "artifact_type": "assertion_audit",
        "locale": "en",
        "generation_fingerprint": "fixture-post-audit-cleanup",
        "source_draft": {
            "id": str(source_v3.id),
            "version": source_v3.version,
            "content_hash": source_v3.content_hash,
        },
        "source_writer_run_id": str(fixture.writer_input.writer_run.id),
        "journal_outline": {
            "id": str(fixture.outline_result.artifact.id),
            "version": fixture.outline_result.artifact.version,
            "content_hash": fixture.outline_result.artifact.content_hash,
        },
        "evidence_set": {
            "id": str(fixture.outline_fixture.bundle.evidence_set_id),
            "version": fixture.outline_fixture.bundle.evidence_set_version,
            "content_hash": fixture.outline_fixture.bundle.evidence_set_hash,
        },
        "originality_pack": {
            "id": str(fixture.outline_fixture.bundle.originality_pack_id),
            "snapshot_hash": fixture.outline_fixture.bundle.originality_pack_hash,
        },
        "model_input": {"content_hash": "a" * 64},
        "execution_context": {"context_manifest_id": "fixture"},
        "generator": {"version": "ce05.journal_assertion_audit.v3", "schema_version": 1},
        "model": {"provider": "fixture-provider", "model": "fixture-model", "model_calls": 1},
        "segments": [segment.to_dict() for segment in audited],
        "summary": summary,
    }
    audit_artifact = Artifact(
        run_id=eval_run.id,
        artifact_type="assertion_audit",
        locale="en",
        version=1,
        content_json=audit_payload,
        content_hash=_canonical_hash(audit_payload),
    )
    session.add(audit_artifact)
    await session.flush()
    quality = QualityEvaluation(
        run_id=eval_run.id,
        artifact_id=audit_artifact.id,
        evaluator_key="assertion_audit_hard_gate",
        evaluator_version="ce05.assertion_audit.hard_gate.v3",
        evaluator_type="deterministic",
        result="fail",
        severity="critical",
        findings_json={
            "source_draft_id": str(source_v3.id),
            "source_draft_hash": source_v3.content_hash,
            "assertion_audit_artifact_id": str(audit_artifact.id),
            "assertion_audit_hash": audit_artifact.content_hash,
            **summary,
        },
    )
    session.add(quality)
    await session.flush()
    return fixture, source_v3, audit_artifact, quality


def _args(
    fixture: object,
    source: Artifact,
    audit: Artifact,
    quality: QualityEvaluation,
) -> SimpleNamespace:
    writer_input = cast(object, fixture).writer_input
    outline = writer_input.outline_artifact
    return SimpleNamespace(
        writer_run_id=writer_input.writer_run.id,
        source_draft_artifact_id=source.id,
        source_draft_version=source.version,
        source_draft_hash=source.content_hash,
        failed_audit_artifact_id=audit.id,
        failed_audit_version=audit.version,
        failed_audit_hash=audit.content_hash,
        failed_quality_evaluation_id=quality.id,
        outline_artifact_id=outline.id,
        outline_artifact_version=outline.version,
        outline_artifact_hash=outline.content_hash,
    )


@pytest.mark.asyncio(loop_scope="module")
async def test_cleanup_binds_exact_inputs_deletes_only_sentence_and_reuses() -> None:
    async with isolated_session() as session:
        fixture, source, audit, quality = await _cleanup_fixture(session)
        cleanup_input = await load_post_audit_cleanup_input(
            session,
            writer_run_id=fixture.writer_input.writer_run.id,
            source_draft_artifact_id=source.id,
            expected_source_draft_version=3,
            expected_source_draft_hash=source.content_hash,
            failed_audit_artifact_id=audit.id,
            expected_failed_audit_version=1,
            expected_failed_audit_hash=audit.content_hash,
            failed_quality_evaluation_id=quality.id,
            outline_artifact_id=fixture.outline_result.artifact.id,
            expected_outline_version=fixture.outline_result.artifact.version,
            expected_outline_hash=fixture.outline_result.artifact.content_hash,
        )
        source_snapshot = copy.deepcopy(source.content_json)
        audit_snapshot = copy.deepcopy(audit.content_json)
        quality_snapshot = copy.deepcopy(quality.findings_json)
        step = StepRun(
            run_id=fixture.writer_input.writer_run.id,
            step_key=POST_AUDIT_CLEANUP_TASK_KEY,
            attempt=1,
            status="pending",
            input_artifact_refs_json=[str(source.id), str(audit.id)],
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
        await transition_run(
            session,
            run_id=fixture.writer_input.writer_run.id,
            status="running",
        )
        await transition_step_run(session, step_run_id=step.id, status="running")
        first = await PostAuditCleanupGenerator().cleanup_draft(
            session,
            cleanup_input=cleanup_input,
            step_run_id=step.id,
        )
        await transition_step_run(session, step_run_id=step.id, status="completed")
        await transition_run(
            session,
            run_id=fixture.writer_input.writer_run.id,
            status="waiting_approval",
        )
        second = await PostAuditCleanupGenerator().cleanup_draft(
            session,
            cleanup_input=cleanup_input,
            step_run_id=step.id,
        )

        assert first.reused is False
        assert first.model_attempts == 0
        assert second.reused is True
        assert second.model_attempts == 0
        assert first.artifact.id == second.artifact.id
        assert first.artifact.version == 4
        assert first.draft.closing_markdown == RESULT_CLOSING
        source_draft = cast(dict[str, object], source.content_json)["draft"]
        result_draft = cast(dict[str, object], first.artifact.content_json)["draft"]
        assert isinstance(source_draft, dict)
        assert isinstance(result_draft, dict)
        for key, value in source_draft.items():
            if key != "closing_markdown":
                assert result_draft[key] == value
        assert source.content_json == source_snapshot
        assert audit.content_json == audit_snapshot
        assert quality.findings_json == quality_snapshot
        payload = cast(dict[str, object], first.artifact.content_json)
        assert payload["generator"] == {
            "version": POST_AUDIT_CLEANUP_GENERATOR_VERSION,
            "schema_version": 1,
        }
        assert payload["model_calls"] == 0
        assert payload["provider_calls"] == 0
        assert payload["tool_calls"] == 0
        assert "prompt_version" not in payload
        assert "recipe_version" not in payload
        assert "context_manifest_id" not in payload
        assert step.output_artifact_refs_json == [str(first.artifact.id)]
        assert await session.scalar(
            select(func.count()).select_from(ModelCall).where(ModelCall.run_id == step.run_id)
        ) == 0
        assert await session.scalar(
            select(func.count()).select_from(ToolCall).where(ToolCall.run_id == step.run_id)
        ) == 0


@pytest.mark.asyncio(loop_scope="module")
async def test_cleanup_cli_failure_preserves_writer_and_retry_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async with isolated_session() as session:
        fixture, source, audit, quality = await _cleanup_fixture(session)
        args = _args(fixture, source, audit, quality)

        class _SessionContext:
            async def __aenter__(self) -> AsyncSession:
                return session

            async def __aexit__(self, *args: object) -> None:
                return None

        async def _no_commit() -> None:
            return None

        monkeypatch.setattr(session, "commit", _no_commit)
        monkeypatch.setattr(cleanup_cli, "SessionLocal", lambda: _SessionContext())

        class _FailingCleanup:
            async def cleanup_draft(self, *args: object, **kwargs: object) -> object:
                del args, kwargs
                raise cleanup_module.WriterGenerationError("fixture_cleanup_failure")

        monkeypatch.setattr(cleanup_cli, "PostAuditCleanupGenerator", _FailingCleanup)
        with pytest.raises(Exception, match="fixture_cleanup_failure"):
            await cleanup_cli._run(args)
        capsys.readouterr()
        run = await session.get(ContentRun, fixture.writer_input.writer_run.id)
        assert run is not None
        assert run.status == "waiting_approval"
        failed_steps = list(
            (
                await session.scalars(
                    select(StepRun)
                    .where(
                        StepRun.run_id == run.id,
                        StepRun.step_key == POST_AUDIT_CLEANUP_TASK_KEY,
                    )
                    .order_by(StepRun.attempt)
                )
            ).all()
        )
        assert [(step.attempt, step.status) for step in failed_steps] == [(1, "failed")]
        assert failed_steps[0].error_json == {"code": "fixture_cleanup_failure"}

        monkeypatch.setattr(cleanup_cli, "PostAuditCleanupGenerator", PostAuditCleanupGenerator)
        await cleanup_cli._run(args)
        first_output = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert first_output["step_attempt"] == 2
        assert first_output["step_status"] == "completed"
        assert first_output["writer_run_status"] == "waiting_approval"
        assert first_output["cleanup_artifact_version"] == 4
        assert first_output["model_calls"] == 0
        assert first_output["reused"] is False

        counts_before = {
            "steps": await session.scalar(
                select(func.count()).select_from(StepRun).where(StepRun.run_id == run.id)
            ),
            "artifacts": await session.scalar(
                select(func.count()).select_from(Artifact).where(Artifact.run_id == run.id)
            ),
            "model_calls": await session.scalar(
                select(func.count()).select_from(ModelCall).where(ModelCall.run_id == run.id)
            ),
            "tool_calls": await session.scalar(
                select(func.count()).select_from(ToolCall).where(ToolCall.run_id == run.id)
            ),
        }
        await cleanup_cli._run(args)
        second_output = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert second_output["step_attempt"] == 2
        assert second_output["step_run_id"] == first_output["step_run_id"]
        assert second_output["cleanup_artifact_id"] == first_output["cleanup_artifact_id"]
        assert second_output["cleanup_artifact_hash"] == first_output["cleanup_artifact_hash"]
        assert second_output["reused"] is True
        assert second_output["model_attempts"] == 0
        counts_after = {
            "steps": await session.scalar(
                select(func.count()).select_from(StepRun).where(StepRun.run_id == run.id)
            ),
            "artifacts": await session.scalar(
                select(func.count()).select_from(Artifact).where(Artifact.run_id == run.id)
            ),
            "model_calls": await session.scalar(
                select(func.count()).select_from(ModelCall).where(ModelCall.run_id == run.id)
            ),
            "tool_calls": await session.scalar(
                select(func.count()).select_from(ToolCall).where(ToolCall.run_id == run.id)
            ),
        }
        assert counts_after == counts_before
        failed_steps = list(
            (
                await session.scalars(
                    select(StepRun)
                    .where(
                        StepRun.run_id == run.id,
                        StepRun.step_key == POST_AUDIT_CLEANUP_TASK_KEY,
                    )
                    .order_by(StepRun.attempt)
                )
            ).all()
        )
        assert [(step.attempt, step.status) for step in failed_steps] == [
            (1, "failed"),
            (2, "completed"),
        ]


@pytest.mark.asyncio(loop_scope="module")
async def test_cleanup_fails_closed_on_audit_hash_and_preserves_terminal_semantics() -> None:
    async with isolated_session() as session:
        fixture, source, audit, quality = await _cleanup_fixture(session)
        with pytest.raises(Exception, match="post_audit_cleanup_failed_audit_snapshot_mismatch"):
            await load_post_audit_cleanup_input(
                session,
                writer_run_id=fixture.writer_input.writer_run.id,
                source_draft_artifact_id=source.id,
                expected_source_draft_version=3,
                expected_source_draft_hash=source.content_hash,
                failed_audit_artifact_id=audit.id,
                expected_failed_audit_version=1,
                expected_failed_audit_hash="0" * 64,
                failed_quality_evaluation_id=quality.id,
                outline_artifact_id=fixture.outline_result.artifact.id,
                expected_outline_version=fixture.outline_result.artifact.version,
                expected_outline_hash=fixture.outline_result.artifact.content_hash,
            )
        assert RUN_TRANSITIONS["failed"] == set()
        assert RUN_TRANSITIONS["completed"] == set()
