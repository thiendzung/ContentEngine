from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from dataclasses import replace
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_assertion_audit import isolated_session
from test_ce05_writer import (
    _draft_payload,
    _writer_fixture,
)

import app.modules.content_engine.journal.source_copy_cleanup as cleanup_module
import scripts.source_copy_cleanup_real_o4_en as cleanup_cli
from app.modules.content_engine.journal.assertion_audit import (
    ASSERTION_AUDIT_EVALUATOR_VERSION,
    _source_segments,
)
from app.modules.content_engine.journal.source_copy import (
    SourceCopyCheck,
    SourceCopyFinding,
    SourceCopyInput,
    SourceCopySource,
)
from app.modules.content_engine.journal.source_copy_cleanup import (
    EXPECTED_SOURCE_TEXT_HASH,
    REPLACEMENT_TEXT,
    SOURCE_COPY_CLEANUP_GENERATOR_VERSION,
    SOURCE_COPY_CLEANUP_TASK_KEY,
    TARGET_SEGMENT_ID,
    TARGET_TEXT,
    SourceCopyCleanupGenerator,
    SourceCopyCleanupInput,
)
from app.modules.content_engine.journal.writer import (
    WriterGenerationError,
    _validate_model_output,
    persist_journal_draft,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ModelCall,
    QualityEvaluation,
    StepRun,
    ToolCall,
    utc_now,
)
from app.modules.harness.persistence import transition_run, transition_step_run

SOURCE_EXCERPT = (
    "Prices asked and amounts offered are determined by personal interests of both the seller "
    "and the purchaser and by the trends in the market."
)


def _warning(draft_text: str) -> SourceCopyFinding:
    return SourceCopyFinding(
        locale="en",
        draft_segment_id=TARGET_SEGMENT_ID,
        draft_location="section:understand-price-context",
        draft_text=draft_text,
        source_kind="evidence_excerpt",
        source_ref="evidence:5e97ed0d-8989-47d3-af4e-b2f29a5110cd",
        source_field="evidence_excerpt",
        source_text_hash=EXPECTED_SOURCE_TEXT_HASH,
        matched_draft_span={"start": 0, "end": len(draft_text)},
        matched_source_span={"start": 0, "end": len(SOURCE_EXCERPT)},
        normalized_match=TARGET_TEXT,
        overlap_token_count=9,
        classification="warn",
    )


async def _cleanup_fixture(session: AsyncSession) -> SourceCopyCleanupInput:
    fixture = await _writer_fixture(session, locale="en")
    raw = _draft_payload(fixture.writer_input, "en")
    sections = cast(list[object], raw["sections"])
    target = cast(dict[str, object], sections[0])
    outline_sections = cast(list[object], fixture.writer_input.outline_payload["sections"])
    outline_target = cast(dict[str, object], outline_sections[0])
    target["section_id"] = "understand-price-context"
    outline_target["section_id"] = "understand-price-context"
    target["body_markdown"] = (
        "Prices asked and amounts offered are determined by "
        f"{TARGET_TEXT} and by market trends."
    )
    generated_draft = _validate_model_output(raw, writer_input=fixture.writer_input)
    source = await persist_journal_draft(
        session,
        writer_input=fixture.writer_input,
        draft=generated_draft,
        provider="fixture-provider",
        model="fixture-model",
        model_calls=1,
        prompt_version=fixture.prompt_version,
        recipe_version=fixture.recipe_version,
        context_manifest=fixture.manifest,
        generator_version="fixture.journal_source_copy_cleanup.v1",
    )
    source_versions = [
        (2, "fixture.journal_source_copy_cleanup.v2"),
        (3, "fixture.journal_source_copy_cleanup.v3"),
        (4, "fixture.journal_source_copy_cleanup.v4"),
    ]
    for expected_version, generator_version in source_versions:
        source = await persist_journal_draft(
            session,
            writer_input=fixture.writer_input,
            draft=generated_draft,
            provider="fixture-provider",
            model="fixture-model",
            model_calls=1,
            prompt_version=fixture.prompt_version,
            recipe_version=fixture.recipe_version,
            context_manifest=fixture.manifest,
            generator_version=generator_version,
        )
        assert source.version == expected_version
    await transition_run(session, run_id=fixture.writer_input.writer_run.id, status="running")
    await transition_run(
        session,
        run_id=fixture.writer_input.writer_run.id,
        status="waiting_approval",
    )

    audit_run = ContentRun(
        project_id=fixture.writer_input.writer_run.project_id,
        content_case_id=fixture.writer_input.writer_run.content_case_id,
        locale_variant_id=fixture.writer_input.locale_variant.id,
        content_item_id=fixture.writer_input.writer_run.content_item_id,
        run_mode="eval",
        status="completed",
        current_step="assertion_audit_en",
        settings_snapshot_id=fixture.writer_input.writer_run.settings_snapshot_id,
        started_at=utc_now(),
        completed_at=utc_now(),
    )
    copy_run = ContentRun(
        project_id=fixture.writer_input.writer_run.project_id,
        content_case_id=fixture.writer_input.writer_run.content_case_id,
        locale_variant_id=fixture.writer_input.locale_variant.id,
        content_item_id=fixture.writer_input.writer_run.content_item_id,
        run_mode="eval",
        status="completed",
        current_step="source_copy_check_en",
        settings_snapshot_id=fixture.writer_input.writer_run.settings_snapshot_id,
        started_at=utc_now(),
        completed_at=utc_now(),
    )
    session.add_all([audit_run, copy_run])
    await session.flush()
    audit_artifact = Artifact(
        run_id=audit_run.id,
        artifact_type="assertion_audit",
        locale="en",
        version=1,
        content_json={"fixture": "passing-audit"},
        content_hash="a" * 64,
    )
    session.add(audit_artifact)
    await session.flush()
    audit_evaluation = QualityEvaluation(
        run_id=audit_run.id,
        artifact_id=audit_artifact.id,
        evaluator_key="assertion_audit_hard_gate",
        evaluator_version=ASSERTION_AUDIT_EVALUATOR_VERSION,
        evaluator_type="deterministic",
        result="pass",
        severity="none",
        findings_json={"result": "pass"},
    )
    handoff = Artifact(
        run_id=copy_run.id,
        artifact_type="source_copy_handoff",
        locale="en",
        version=1,
        content_json={"fixture": "source-copy-handoff"},
        content_hash="b" * 64,
    )
    session.add(handoff)
    await session.flush()
    copy_step = StepRun(
        run_id=copy_run.id,
        step_key="source_copy_check_en",
        attempt=1,
        status="completed",
        input_artifact_refs_json=[str(handoff.id), str(source.id), str(audit_artifact.id)],
        output_artifact_refs_json=[],
    )
    copy_artifact = Artifact(
        run_id=copy_run.id,
        artifact_type="source_copy_check",
        locale="en",
        version=1,
        content_json={"fixture": "source-copy-warning"},
        content_hash="c" * 64,
    )
    session.add_all([copy_step, copy_artifact])
    await session.flush()
    copy_evaluation = QualityEvaluation(
        run_id=copy_run.id,
        artifact_id=copy_artifact.id,
        evaluator_key="source_copy_basic_gate",
        evaluator_version="ce05.source_copy.basic_gate.v2",
        evaluator_type="deterministic",
        result="warn",
        severity="medium",
        findings_json={"result": "warn", "warn_count": 1, "fail_count": 0},
    )
    session.add_all([audit_evaluation, copy_evaluation])
    await session.flush()
    settings_snapshot = await session.get(
        SettingsSnapshot,
        fixture.writer_input.writer_run.settings_snapshot_id,
    )
    assert settings_snapshot is not None
    source_copy_input = SourceCopyInput(
        writer_input=fixture.writer_input,
        source_artifact=source,
        source_draft=generated_draft,
        assertion_audit_artifact=audit_artifact,
        assertion_audit_evaluation=audit_evaluation,
        sources=(
            SourceCopySource(
                source_kind="evidence_excerpt",
                source_ref="evidence:5e97ed0d-8989-47d3-af4e-b2f29a5110cd",
                source_field="evidence_excerpt",
                source_text=SOURCE_EXCERPT,
                source_text_hash=EXPECTED_SOURCE_TEXT_HASH,
            ),
        ),
        segments=_source_segments(generated_draft),
        settings_snapshot_hash=settings_snapshot.content_hash,
    )
    return SourceCopyCleanupInput(
        writer_input=fixture.writer_input,
        source_artifact=source,
        source_draft=generated_draft,
        assertion_audit_artifact=audit_artifact,
        assertion_audit_evaluation=audit_evaluation,
        source_copy_input=source_copy_input,
        source_copy_eval_run=copy_run,
        source_copy_handoff=handoff,
        source_copy_step=copy_step,
        source_copy_artifact=copy_artifact,
        source_copy_evaluation=copy_evaluation,
        warning=_warning(cast(str, target["body_markdown"])),
    )


def _args(cleanup_input: SourceCopyCleanupInput) -> SimpleNamespace:
    return SimpleNamespace(
        writer_run_id=cleanup_input.writer_input.writer_run.id,
        source_draft_artifact_id=cleanup_input.source_artifact.id,
        source_draft_version=4,
        source_draft_hash=cleanup_input.source_artifact.content_hash,
        assertion_audit_artifact_id=cleanup_input.assertion_audit_artifact.id,
        assertion_audit_version=1,
        assertion_audit_hash=cleanup_input.assertion_audit_artifact.content_hash,
        assertion_audit_quality_evaluation_id=cleanup_input.assertion_audit_evaluation.id,
        source_copy_eval_run_id=cleanup_input.source_copy_eval_run.id,
        source_copy_handoff_id=cleanup_input.source_copy_handoff.id,
        source_copy_handoff_hash=cleanup_input.source_copy_handoff.content_hash,
        source_copy_step_run_id=cleanup_input.source_copy_step.id,
        source_copy_artifact_id=cleanup_input.source_copy_artifact.id,
        source_copy_artifact_version=1,
        source_copy_artifact_hash=cleanup_input.source_copy_artifact.content_hash,
        source_copy_quality_evaluation_id=cleanup_input.source_copy_evaluation.id,
        outline_artifact_id=cleanup_input.writer_input.outline_artifact.id,
        outline_artifact_version=cleanup_input.writer_input.outline_artifact.version,
        outline_artifact_hash=cleanup_input.writer_input.outline_artifact.content_hash,
    )


def test_source_copy_cleanup_cli_resolves_from_backend_execution_root() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.source_copy_cleanup_real_o4_en", "--help"],
        cwd=".",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "replace the locked EN source-copy warning" in result.stdout


def test_source_copy_cleanup_rejects_any_warning_other_than_the_locked_one() -> None:
    check = SourceCopyCheck(
        result="warn",
        findings=(_warning("target"),),
        finding_count=1,
        warn_count=1,
        fail_count=0,
        max_overlap_tokens=9,
    )
    assert cleanup_module._expected_warning(check).source_ref.startswith("evidence:")
    invalid = replace(_warning("target"), source_ref="evidence:other")
    invalid_check = SourceCopyCheck(
        result="warn",
        findings=(invalid,),
        finding_count=1,
        warn_count=1,
        fail_count=0,
        max_overlap_tokens=9,
    )
    with pytest.raises(Exception, match="source_copy_cleanup_warning_finding_mismatch"):
        cleanup_module._expected_warning(invalid_check)

    multiple = SourceCopyCheck(
        result="warn",
        findings=(_warning("target"), _warning("target")),
        finding_count=2,
        warn_count=2,
        fail_count=0,
        max_overlap_tokens=9,
    )
    with pytest.raises(Exception, match="source_copy_cleanup_warning_summary_mismatch"):
        cleanup_module._expected_warning(multiple)


@pytest.mark.asyncio(loop_scope="module")
async def test_cleanup_rejects_ambiguous_target_copy() -> None:
    async with isolated_session() as session:
        cleanup_input = await _cleanup_fixture(session)
        target_index = next(
            index
            for index, section in enumerate(cleanup_input.source_draft.sections)
            if section.section_id == "understand-price-context"
        )
        target_section = cleanup_input.source_draft.sections[target_index]
        ambiguous_section = replace(
            target_section,
            body_markdown=f"{target_section.body_markdown} {TARGET_TEXT}",
        )
        ambiguous_draft = replace(
            cleanup_input.source_draft,
            sections=(
                *cleanup_input.source_draft.sections[:target_index],
                ambiguous_section,
                *cleanup_input.source_draft.sections[target_index + 1 :],
            ),
        )
        invalid_input = replace(cleanup_input, source_draft=ambiguous_draft)
        with pytest.raises(Exception, match="source_copy_cleanup_target_occurrence_mismatch"):
            cleanup_module._cleanup_draft(invalid_input)


@pytest.mark.asyncio(loop_scope="module")
async def test_cleanup_replaces_only_target_and_exact_rerun_is_side_effect_free() -> None:
    async with isolated_session() as session:
        cleanup_input = await _cleanup_fixture(session)
        source_snapshot = copy.deepcopy(cleanup_input.source_artifact.content_json)
        step = StepRun(
            run_id=cleanup_input.writer_input.writer_run.id,
            step_key=SOURCE_COPY_CLEANUP_TASK_KEY,
            attempt=1,
            status="pending",
            input_artifact_refs_json=[
                str(cleanup_input.source_artifact.id),
                str(cleanup_input.source_copy_artifact.id),
            ],
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
        await transition_run(
            session,
            run_id=cleanup_input.writer_input.writer_run.id,
            status="running",
        )
        await transition_step_run(session, step_run_id=step.id, status="running")
        first = await SourceCopyCleanupGenerator().cleanup_draft(
            session,
            cleanup_input=cleanup_input,
            step_run_id=step.id,
        )
        await transition_step_run(session, step_run_id=step.id, status="completed")
        await transition_run(
            session,
            run_id=cleanup_input.writer_input.writer_run.id,
            status="waiting_approval",
        )
        counts_before = {
            "artifacts": await session.scalar(
                select(func.count()).select_from(Artifact).where(
                    Artifact.run_id == cleanup_input.writer_input.writer_run.id
                )
            ),
            "steps": await session.scalar(
                select(func.count()).select_from(StepRun).where(
                    StepRun.run_id == cleanup_input.writer_input.writer_run.id
                )
            ),
            "models": await session.scalar(
                select(func.count()).select_from(ModelCall).where(
                    ModelCall.run_id == cleanup_input.writer_input.writer_run.id
                )
            ),
            "tools": await session.scalar(
                select(func.count()).select_from(ToolCall).where(
                    ToolCall.run_id == cleanup_input.writer_input.writer_run.id
                )
            ),
        }
        second = await SourceCopyCleanupGenerator().cleanup_draft(
            session,
            cleanup_input=cleanup_input,
            step_run_id=step.id,
        )
        counts_after = {
            "artifacts": await session.scalar(
                select(func.count()).select_from(Artifact).where(
                    Artifact.run_id == cleanup_input.writer_input.writer_run.id
                )
            ),
            "steps": await session.scalar(
                select(func.count()).select_from(StepRun).where(
                    StepRun.run_id == cleanup_input.writer_input.writer_run.id
                )
            ),
            "models": await session.scalar(
                select(func.count()).select_from(ModelCall).where(
                    ModelCall.run_id == cleanup_input.writer_input.writer_run.id
                )
            ),
            "tools": await session.scalar(
                select(func.count()).select_from(ToolCall).where(
                    ToolCall.run_id == cleanup_input.writer_input.writer_run.id
                )
            ),
        }
        assert first.reused is False
        assert second.reused is True
        assert second.model_attempts == 0
        assert second.artifact.id == first.artifact.id
        assert second.artifact.version == 5
        assert counts_after == counts_before
        assert cleanup_input.writer_input.writer_run.status == "waiting_approval"
        assert cleanup_input.source_artifact.content_json == source_snapshot
        target_index = next(
            index
            for index, section in enumerate(second.draft.sections)
            if section.section_id == "understand-price-context"
        )
        assert TARGET_TEXT not in second.draft.sections[target_index].body_markdown
        assert REPLACEMENT_TEXT in second.draft.sections[target_index].body_markdown
        payload = cast(dict[str, object], first.artifact.content_json)
        assert payload["generator"] == {
            "version": SOURCE_COPY_CLEANUP_GENERATOR_VERSION,
            "schema_version": 1,
        }
        assert payload["model_calls"] == 0
        assert payload["provider_calls"] == 0
        assert payload["tool_calls"] == 0
        assert "prompt_version" not in payload
        assert "recipe_version" not in payload


@pytest.mark.asyncio(loop_scope="module")
async def test_cleanup_cli_failure_preserves_writer_and_retry_is_safe(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async with isolated_session() as session:
        cleanup_input = await _cleanup_fixture(session)

        class _SessionContext:
            async def __aenter__(self) -> AsyncSession:
                return session

            async def __aexit__(self, *args: object) -> None:
                del args

        async def _no_commit() -> None:
            return None

        monkeypatch.setattr(cleanup_cli, "SessionLocal", lambda: _SessionContext())
        monkeypatch.setattr(session, "commit", _no_commit)

        async def _load(*args: object, **kwargs: object) -> SourceCopyCleanupInput:
            del args, kwargs
            return cleanup_input

        monkeypatch.setattr(
            cleanup_cli,
            "load_source_copy_cleanup_input",
            _load,
        )

        class _FailingGenerator:
            async def cleanup_draft(self, *args: object, **kwargs: object) -> object:
                del args, kwargs
                raise WriterGenerationError("fixture_cleanup_failure")

        monkeypatch.setattr(cleanup_cli, "SourceCopyCleanupGenerator", _FailingGenerator)
        with pytest.raises(Exception, match="fixture_cleanup_failure"):
            await cleanup_cli._run(cast(argparse.Namespace, _args(cleanup_input)))
        capsys.readouterr()
        run = cleanup_input.writer_input.writer_run
        assert run.status == "waiting_approval"
        failed = list(
            (
                await session.scalars(
                    select(StepRun)
                    .where(
                        StepRun.run_id == run.id,
                        StepRun.step_key == SOURCE_COPY_CLEANUP_TASK_KEY,
                    )
                    .order_by(StepRun.attempt)
                )
            ).all()
        )
        assert [(step.attempt, step.status) for step in failed] == [(1, "failed")]
        monkeypatch.setattr(cleanup_cli, "SourceCopyCleanupGenerator", SourceCopyCleanupGenerator)
        await cleanup_cli._run(cast(argparse.Namespace, _args(cleanup_input)))
        first_output = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert first_output["step_attempt"] == 2
        assert first_output["reused"] is False
        assert first_output["cleanup_artifact_version"] == 5
        await cleanup_cli._run(cast(argparse.Namespace, _args(cleanup_input)))
        second_output = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert second_output["step_run_id"] == first_output["step_run_id"]
        assert second_output["cleanup_artifact_id"] == first_output["cleanup_artifact_id"]
        assert second_output["cleanup_artifact_hash"] == first_output["cleanup_artifact_hash"]
        assert second_output["reused"] is True
        assert second_output["model_attempts"] == 0
        assert run.status == "waiting_approval"
