from __future__ import annotations

import copy
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_assertion_audit import (
    FakeAuditModel,
    _passing_output,
    _source,
    isolated_session,
)
from test_ce05_assertion_audit_recovery import _audit, _prepare
from test_ce05_writer import FakeWriterModel, _draft_payload, _generate_draft, _writer_fixture

from app.modules.content_engine.journal.assertion_audit import (
    ASSERTION_AUDIT_EVALUATOR_VERSION,
    AssertionAuditError,
    _source_segments,
)
from app.modules.content_engine.journal.assertion_audit_execution import (
    validate_source_writer_eligibility,
)
from app.modules.content_engine.journal.source_copy import (
    SOURCE_COPY_EVALUATOR_VERSION,
    SOURCE_COPY_GENERATOR_VERSION,
    SOURCE_COPY_TASK_KEYS,
    SourceCopyError,
    SourceCopyInput,
    SourceCopySource,
    _build_sources,
    _handoff_payload,
    check_source_copy,
    classify_source_copy_overlap,
    execute_source_copy,
    load_source_copy_input,
    normalize_source_copy_text,
    normalize_source_copy_tokens,
)
from app.modules.content_engine.journal.writer import WriterInput
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ContextManifest,
    ModelCall,
    QualityEvaluation,
    StepRun,
    ToolCall,
    utc_now,
)
from app.modules.harness.persistence import transition_run
from app.modules.knowledge.models import EvidenceSet, OriginalityPack
from app.modules.knowledge.originality_pack import originality_pack_snapshot_hash


def _segment(text: str) -> object:
    return type(
        "Segment",
        (),
        {"segment_id": "lead:1", "location": "lead", "source_text": text},
    )()


def _words(count: int) -> str:
    return " ".join(f"word{index}" for index in range(count))


def test_source_copy_normalization_preserves_english_and_vietnamese_diacritics() -> None:
    assert normalize_source_copy_text("  Café—Price! ") == "  café—price! "
    assert normalize_source_copy_tokens("Giá  TÁC phẩm nghệ thuật") == (
        "giá",
        "tác",
        "phẩm",
        "nghệ",
        "thuật",
    )
    assert normalize_source_copy_tokens("Café, café") == ("café", "café")


def test_source_copy_normalization_treats_straight_and_curly_apostrophes_as_boundaries() -> None:
    assert normalize_source_copy_tokens("artwork's price") == (
        "artwork",
        "s",
        "price",
    )
    assert normalize_source_copy_tokens("artwork's price") == normalize_source_copy_tokens(
        "artwork’s price"
    )


@pytest.mark.parametrize(
    ("count", "classification"),
    [(7, None), (8, "warn"), (11, "warn"), (12, "fail")],
)
def test_source_copy_apostrophe_typography_cannot_bypass_thresholds(
    count: int, classification: str | None
) -> None:
    prefix = _words(count - 2)
    draft_text = f"{prefix} buyer's"
    source_text = f"{prefix} buyer’s"
    source = SourceCopySource(
        source_kind="evidence_excerpt",
        source_ref="evidence:apostrophe",
        source_field="evidence_excerpt",
        source_text=source_text,
        source_text_hash="e" * 64,
    )
    result = check_source_copy(
        locale="en",
        segments=(_segment(draft_text),),
        sources=(source,),
    )
    assert normalize_source_copy_tokens(draft_text) == normalize_source_copy_tokens(source_text)
    assert result.max_overlap_tokens == count
    if classification is None:
        assert result.result == "pass"
        assert result.findings == ()
    else:
        assert result.result == classification
        assert result.findings[0].overlap_token_count == count


@pytest.mark.parametrize(
    ("count", "classification"),
    [(7, None), (8, "warn"), (11, "warn"), (12, "fail")],
)
def test_source_copy_thresholds(count: int, classification: str | None) -> None:
    assert classify_source_copy_overlap(count) == classification
    source = SourceCopySource(
        source_kind="evidence_excerpt",
        source_ref="evidence:fixture",
        source_field="evidence_excerpt",
        source_text=_words(count),
        source_text_hash="a" * 64,
    )
    result = check_source_copy(
        locale="en",
        segments=(_segment(_words(count)),),
        sources=(source,),
    )
    if classification is None:
        assert result.summary() == {
            "result": "pass",
            "finding_count": 0,
            "warn_count": 0,
            "fail_count": 0,
            "max_overlap_tokens": count,
        }
    else:
        assert result.result == classification
        assert result.findings[0].overlap_token_count == count


def test_source_copy_persists_only_maximal_non_contained_matches() -> None:
    source = SourceCopySource(
        source_kind="originality_material",
        source_ref="originality:fixture",
        source_field="material",
        source_text=_words(14),
        source_text_hash="b" * 64,
    )
    result = check_source_copy(
        locale="en",
        segments=(_segment(f"prefix {_words(14)} suffix"),),
        sources=(source,),
    )
    assert len(result.findings) == 1
    assert result.findings[0].overlap_token_count == 14
    assert set(result.findings[0].to_dict()) == {
        "locale",
        "draft_segment_id",
        "draft_location",
        "draft_text",
        "source_kind",
        "source_ref",
        "source_field",
        "source_text_hash",
        "matched_draft_span",
        "matched_source_span",
        "normalized_match",
        "overlap_token_count",
        "classification",
    }


async def _source_input(session: AsyncSession, *, locale: str = "en") -> SourceCopyInput:
    fixture = await _writer_fixture(session, locale=locale)
    generated = await _generate_draft(
        session,
        fixture,
        FakeWriterModel([_draft_payload(fixture.writer_input, locale)]),
    )


    writer_run = fixture.writer_input.writer_run
    await transition_run(session, run_id=writer_run.id, status="running")
    await transition_run(session, run_id=writer_run.id, status="waiting_approval")

    audit_run = ContentRun(
        project_id=writer_run.project_id,
        content_case_id=writer_run.content_case_id,
            locale_variant_id=fixture.writer_input.locale_variant.id,
        content_item_id=writer_run.content_item_id,
        run_mode="eval",
        status="completed",
        current_step="assertion_audit",
        settings_snapshot_id=writer_run.settings_snapshot_id,
        started_at=utc_now(),
        completed_at=utc_now(),
    )
    session.add(audit_run)
    await session.flush()
    audit_payload = {"artifact_type": "assertion_audit", "locale": locale}
    audit_artifact = Artifact(
        run_id=audit_run.id,
        artifact_type="assertion_audit",
        locale=locale,
        version=1,
        content_json=audit_payload,
        content_hash="c" * 64,
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
        findings_json={},
    )
    session.add(audit_evaluation)
    await session.flush()
    return SourceCopyInput(
        writer_input=cast(WriterInput, fixture.writer_input),
        source_artifact=generated.artifact,
        source_draft=generated.draft,
        assertion_audit_artifact=audit_artifact,
        assertion_audit_evaluation=audit_evaluation,
        sources=(
            SourceCopySource(
                source_kind="evidence_excerpt",
                source_ref="evidence:unrelated",
                source_field="evidence_excerpt",
                source_text="unrelated bounded source text",
                source_text_hash="d" * 64,
            ),
        ),
        segments=_source_segments(generated.draft),
    )


async def _legacy_source_copy_input(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[object, Artifact, SourceCopyInput]:
    import app.modules.content_engine.journal.assertion_audit_execution as execution_module

    fixture, source, audit_input = await _source(session, locale="vi-VN")
    writer_run = audit_input.writer_input.writer_run
    await transition_run(session, run_id=writer_run.id, status="running")
    await transition_run(session, run_id=writer_run.id, status="failed")
    writer_run.failure_code = "assertion_audit_vi_failed"
    monkeypatch.setattr(execution_module, "LEGACY_FAILED_VI_WRITER_RUN_ID", writer_run.id)
    monkeypatch.setattr(execution_module, "LEGACY_FAILED_VI_DRAFT_ID", source.id)
    monkeypatch.setattr(
        execution_module,
        "LEGACY_FAILED_VI_DRAFT_VERSION",
        source.version,
    )
    monkeypatch.setattr(
        execution_module,
        "LEGACY_FAILED_VI_DRAFT_HASH",
        source.content_hash,
    )
    execution = await _prepare(session, source_input=audit_input)
    audit_result = await _audit(
        session,
        source_input=audit_input,
        execution=execution,
        model=FakeAuditModel([_passing_output(audit_input)]),
    )
    assert audit_result.result == "pass"
    loaded = await load_source_copy_input(
        session,
        writer_run_id=writer_run.id,
        source_draft_artifact_id=source.id,
        expected_source_draft_version=source.version,
        expected_source_draft_hash=source.content_hash,
        assertion_audit_artifact_id=audit_result.artifact.id,
        expected_assertion_audit_version=audit_result.artifact.version,
        expected_assertion_audit_hash=audit_result.artifact.content_hash,
        assertion_audit_quality_evaluation_id=audit_result.evaluation.id,
        outline_artifact_id=audit_input.writer_input.outline_artifact.id,
        expected_outline_version=audit_input.writer_input.outline_artifact.version,
        expected_outline_hash=audit_input.writer_input.outline_artifact.content_hash,
        locale="vi-VN",
    )
    return fixture, source, loaded


@pytest.mark.asyncio(loop_scope="module")
async def test_source_copy_accepts_exact_legacy_vi_failed_writer_as_immutable_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _fixture, source, source_input = await _legacy_source_copy_input(session, monkeypatch)
        writer_run = source_input.writer_input.writer_run
        snapshot = copy.deepcopy(source.content_json)
        assert writer_run.status == "failed"
        assert writer_run.failure_code == "assertion_audit_vi_failed"
        assert source_input.source_artifact.id == source.id
        assert source_input.source_artifact.version == source.version
        assert source_input.source_artifact.content_hash == source.content_hash
        assert source_input.source_artifact.content_json == snapshot
        assert source_input.sources


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize("locale", ["vi-VN", "en"])
async def test_source_copy_keeps_waiting_approval_writer_eligibility(locale: str) -> None:
    async with isolated_session() as session:
        _fixture, source, source_input = await _source(session, locale=locale)
        source_input.writer_input.writer_run.status = "waiting_approval"
        validate_source_writer_eligibility(
            writer_input=source_input.writer_input,
            source_artifact=source,
        )


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize(
    ("locale", "status"),
    [
        ("vi-VN", "failed"),
        ("en", "failed"),
        ("vi-VN", "cancelled"),
        ("vi-VN", "completed"),
    ],
)
async def test_source_copy_rejects_nonlegacy_terminal_writer_states(
    locale: str, status: str
) -> None:
    async with isolated_session() as session:
        _fixture, source, source_input = await _source(session, locale=locale)
        source_input.writer_input.writer_run.status = status
        with pytest.raises(
            AssertionAuditError,
            match="assertion_audit_source_writer_state_invalid",
        ):
            validate_source_writer_eligibility(
                writer_input=source_input.writer_input,
                source_artifact=source,
            )


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize("mismatch", ["id", "version", "hash"])
async def test_source_copy_rejects_legacy_writer_with_wrong_draft_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    import app.modules.content_engine.journal.assertion_audit_execution as execution_module

    async with isolated_session() as session:
        _fixture, source, source_input = await _source(session, locale="vi-VN")
        writer_run = source_input.writer_input.writer_run
        writer_run.status = "failed"
        monkeypatch.setattr(execution_module, "LEGACY_FAILED_VI_WRITER_RUN_ID", writer_run.id)
        monkeypatch.setattr(execution_module, "LEGACY_FAILED_VI_DRAFT_ID", source.id)
        monkeypatch.setattr(
            execution_module,
            "LEGACY_FAILED_VI_DRAFT_VERSION",
            source.version,
        )
        monkeypatch.setattr(
            execution_module,
            "LEGACY_FAILED_VI_DRAFT_HASH",
            source.content_hash,
        )
        wrong_source = Artifact(
            run_id=source.run_id,
            artifact_type="journal_draft",
            locale="vi-VN",
            version=source.version,
            content_json=source.content_json,
            content_hash=source.content_hash,
        )
        if mismatch == "id":
            wrong_source.id = uuid4()
        elif mismatch == "version":
            wrong_source.version = source.version + 1
        else:
            wrong_source.content_hash = "0" * 64
        with pytest.raises(
            AssertionAuditError,
            match="assertion_audit_source_writer_state_invalid",
        ):
            validate_source_writer_eligibility(
                writer_input=source_input.writer_input,
                source_artifact=wrong_source,
            )


def test_source_copy_cli_resolves_from_backend_execution_root() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "scripts.source_copy_real_o4_journal", "--help"],
        cwd=backend_root,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0
    assert "source-copy" in result.stdout


@pytest.mark.asyncio(loop_scope="module")
async def test_source_copy_uses_dedicated_eval_and_exact_completed_rerun_is_side_effect_free(
) -> None:
    async with isolated_session() as session:
        source_input = await _source_input(session)
        writer_snapshot = copy.deepcopy(source_input.source_artifact.content_json)
        first = await execute_source_copy(
            session,
            source_input=source_input,
            task_key=SOURCE_COPY_TASK_KEYS["en"],
        )
        await session.commit()
        counts_before = {
            "runs": await session.scalar(select(func.count()).select_from(ContentRun)),
            "steps": await session.scalar(select(func.count()).select_from(StepRun)),
            "artifacts": await session.scalar(select(func.count()).select_from(Artifact)),
            "evaluations": await session.scalar(
                select(func.count()).select_from(QualityEvaluation)
            ),
            "model_calls": await session.scalar(select(func.count()).select_from(ModelCall)),
            "tool_calls": await session.scalar(select(func.count()).select_from(ToolCall)),
            "manifests": await session.scalar(
                select(func.count()).select_from(ContextManifest)
            ),
        }
        second = await execute_source_copy(
            session,
            source_input=source_input,
            task_key=SOURCE_COPY_TASK_KEYS["en"],
        )
        await session.commit()
        counts_after = {
            "runs": await session.scalar(select(func.count()).select_from(ContentRun)),
            "steps": await session.scalar(select(func.count()).select_from(StepRun)),
            "artifacts": await session.scalar(select(func.count()).select_from(Artifact)),
            "evaluations": await session.scalar(
                select(func.count()).select_from(QualityEvaluation)
            ),
            "model_calls": await session.scalar(select(func.count()).select_from(ModelCall)),
            "tool_calls": await session.scalar(select(func.count()).select_from(ToolCall)),
            "manifests": await session.scalar(
                select(func.count()).select_from(ContextManifest)
            ),
        }
        assert first.reused is False
        assert second.reused is True
        assert second.eval_run.id == first.eval_run.id
        assert second.handoff.id == first.handoff.id
        assert second.step_run.id == first.step_run.id
        assert second.artifact.id == first.artifact.id
        assert second.evaluation.id == first.evaluation.id
        assert counts_after == counts_before
        assert first.eval_run.run_mode == "eval"
        assert first.eval_run.id != source_input.writer_input.writer_run.id
        assert source_input.source_artifact.content_json == writer_snapshot
        assert first.step_run.output_artifact_refs_json == [str(first.artifact.id)]
        assert first.artifact.content_json["model_calls"] == 0
        assert first.artifact.content_json["tool_calls"] == 0
        assert first.artifact.content_json["source_corpus"]
        assert (
            first.artifact.content_json["algorithm"]["generator_version"]
            == SOURCE_COPY_GENERATOR_VERSION
        )
        assert (
            first.artifact.content_json["algorithm"]["evaluator_version"]
            == SOURCE_COPY_EVALUATOR_VERSION
        )
        assert first.evaluation.evaluator_version == SOURCE_COPY_EVALUATOR_VERSION


@pytest.mark.asyncio(loop_scope="module")
async def test_source_copy_failed_eval_is_terminal_and_retry_uses_replacement_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        source_input = await _source_input(session)
        import app.modules.content_engine.journal.source_copy as source_copy_module

        original = source_copy_module.SourceCopyGenerator.check_draft

        async def _failing(self: object, *args: object, **kwargs: object) -> object:
            del self, args, kwargs
            raise SourceCopyError("fixture_source_copy_failure")

        monkeypatch.setattr(source_copy_module.SourceCopyGenerator, "check_draft", _failing)
        with pytest.raises(SourceCopyError, match="fixture_source_copy_failure"):
            await execute_source_copy(
                session,
                source_input=source_input,
                task_key=SOURCE_COPY_TASK_KEYS["en"],
            )
        await session.commit()
        failed_run = await session.scalar(
            select(ContentRun).where(
                ContentRun.run_mode == "eval",
                ContentRun.current_step == SOURCE_COPY_TASK_KEYS["en"],
            )
        )
        assert failed_run is not None
        assert failed_run.status == "failed"
        failed_step = await session.scalar(select(StepRun).where(StepRun.run_id == failed_run.id))
        assert failed_step is not None
        assert failed_step.status == "failed"
        monkeypatch.setattr(source_copy_module.SourceCopyGenerator, "check_draft", original)
        retry = await execute_source_copy(
            session,
            source_input=source_input,
            task_key=SOURCE_COPY_TASK_KEYS["en"],
        )
        await session.commit()
        assert retry.reused is False
        assert retry.eval_run.id != failed_run.id
        assert retry.eval_run.status == "completed"
        assert retry.step_run.status == "completed"
        assert await session.scalar(
            select(func.count())
            .select_from(ContentRun)
            .where(
                ContentRun.run_mode == "eval",
                ContentRun.current_step == SOURCE_COPY_TASK_KEYS["en"],
            )
        ) == 2


@pytest.mark.asyncio(loop_scope="module")
async def test_source_copy_corpus_is_exact_locked_evidence_and_approved_pack_fields() -> None:
    async with isolated_session() as session:
        source_input = await _source_input(session)
        sources = await _build_sources(session, source_input=source_input)
        assert {source.source_kind for source in sources} == {
            "evidence_excerpt",
            "originality_material",
            "originality_writer_use",
            "originality_guardrail",
        }
        assert all(
            source.source_text_hash and len(source.source_text_hash) == 64 for source in sources
        )
        assert all("claim" not in source.to_dict() for source in sources)


@pytest.mark.asyncio(loop_scope="module")
async def test_source_copy_rejects_unlocked_evidence_and_unapproved_originality() -> None:
    async with isolated_session() as session:
        source_input = await _source_input(session)
        evidence_set_row = await session.get(
            EvidenceSet, source_input.writer_input.outline_input.bundle.evidence_set_id
        )
        assert evidence_set_row is not None
        evidence_set_row.status = "draft"
        with pytest.raises(SourceCopyError, match="source_copy_evidence_set_snapshot_mismatch"):
            await _build_sources(session, source_input=source_input)


@pytest.mark.asyncio(loop_scope="module")
async def test_source_copy_rejects_unapproved_originality_pack_fail_closed() -> None:
    async with isolated_session() as session:
        source_input = await _source_input(session)
        approved_pack = await session.get(
            OriginalityPack,
            source_input.writer_input.outline_input.bundle.originality_pack_id,
        )
        assert approved_pack is not None
        draft_pack = OriginalityPack(
            content_case_id=approved_pack.content_case_id,
            item_refs_json=copy.deepcopy(approved_pack.item_refs_json),
            summary=approved_pack.summary,
            status="draft",
        )
        session.add(draft_pack)
        await session.flush()
        draft_bundle = replace(
            source_input.writer_input.outline_input.bundle,
            originality_pack_id=draft_pack.id,
            originality_pack_hash=originality_pack_snapshot_hash(draft_pack),
        )
        draft_outline_input = replace(
            source_input.writer_input.outline_input,
            bundle=draft_bundle,
        )
        draft_writer_input = replace(
            source_input.writer_input,
            outline_input=draft_outline_input,
        )
        draft_source_input = replace(source_input, writer_input=draft_writer_input)
        with pytest.raises(
            SourceCopyError,
            match="source_copy_originality_pack_snapshot_mismatch",
        ):
            await _build_sources(session, source_input=draft_source_input)


@pytest.mark.asyncio(loop_scope="module")
async def test_source_copy_fails_closed_on_multiple_reusable_eval_matches() -> None:
    async with isolated_session() as session:
        source_input = await _source_input(session)
        first = await execute_source_copy(
            session,
            source_input=source_input,
            task_key=SOURCE_COPY_TASK_KEYS["en"],
        )
        await session.commit()
        settings_snapshot = await session.get(
            SettingsSnapshot, source_input.writer_input.writer_run.settings_snapshot_id
        )
        assert settings_snapshot is not None
        payload = _handoff_payload(
            source_input=source_input,
            settings_snapshot=settings_snapshot,
            task_key=SOURCE_COPY_TASK_KEYS["en"],
        )
        duplicate_run = ContentRun(
            project_id=source_input.writer_input.writer_run.project_id,
            content_case_id=source_input.writer_input.writer_run.content_case_id,
            locale_variant_id=source_input.writer_input.locale_variant.id,
            content_item_id=source_input.writer_input.writer_run.content_item_id,
            run_mode="eval",
            status="pending",
            current_step=SOURCE_COPY_TASK_KEYS["en"],
            settings_snapshot_id=source_input.writer_input.writer_run.settings_snapshot_id,
            started_at=utc_now(),
        )
        session.add(duplicate_run)
        await session.flush()
        session.add(
            Artifact(
                run_id=duplicate_run.id,
                artifact_type="source_copy_handoff",
                locale="en",
                version=1,
                content_json=payload,
                content_hash=first.handoff.content_hash,
            )
        )
        await session.flush()
        with pytest.raises(SourceCopyError, match="source_copy_reusable_run_duplicate"):
            await execute_source_copy(
                session,
                source_input=source_input,
                task_key=SOURCE_COPY_TASK_KEYS["en"],
            )
