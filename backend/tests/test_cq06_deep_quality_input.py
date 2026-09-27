from __future__ import annotations

import copy
from typing import cast

import pytest
from test_ce05_assertion_audit import _passing_output
from test_ce05_outline import isolated_session
from test_operator_quality import (
    _CapturePort,
    _complete_f3_writers,
    _complete_readiness_lane,
    _dispatch_quality,
)

from app.modules.content_engine.journal import operator_quality_worker
from app.modules.content_engine.journal.assertion_audit import load_assertion_audit_input
from app.modules.content_engine.journal.deep_quality_input import (
    DeepQualityInputError,
    load_deep_quality_input,
)
from app.modules.content_engine.journal.operator_quality import get_quality_progress
from app.modules.harness.agent_runner import AgentRunnerRegistry


async def _complete_quality_pipeline(
    session,
    monkeypatch: pytest.MonkeyPatch,
):
    fixture, writer_outputs, outline_result = await _complete_f3_writers(session)
    case_id = fixture.run.content_case_id
    await _dispatch_quality(session, fixture=fixture)

    review_outputs = copy.deepcopy(writer_outputs)
    cast(dict[str, object], review_outputs["en"])["closing_markdown"] = (
        "Pause, look again, and decide at your own pace."
    )
    cast(dict[str, object], review_outputs["vi-VN"])["closing_markdown"] = (
        "Dừng lại, nhìn thêm một lần rồi tự quyết định theo nhịp của bạn."
    )
    review_ports = {
        locale: _CapturePort(payload)
        for locale, payload in review_outputs.items()
    }

    async def fake_review_port(_session, *, locale: str, **kwargs):
        del _session, kwargs
        return review_ports[locale]

    monkeypatch.setattr(
        operator_quality_worker,
        "create_cli_review_revise_model_port",
        fake_review_port,
    )
    registry = AgentRunnerRegistry()
    for index in range(2):
        job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session,
            worker_id=f"cq06-review-{index}",
        )
        assert job is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=job.id,
            worker_id=f"cq06-review-{index}",
            runner_registry=registry,
        )

    progress = await get_quality_progress(
        session,
        content_case_id=case_id,
        source_run_id=None,
    )
    assert progress is not None
    audit_ports: dict[str, _CapturePort] = {}
    for lane in progress.lanes:
        assert lane.writer.run is not None
        assert lane.revised_draft is not None
        audit_input = await load_assertion_audit_input(
            session,
            writer_run_id=lane.writer.run.id,
            revised_draft_artifact_id=lane.revised_draft.id,
            expected_revised_draft_version=lane.revised_draft.version,
            expected_revised_draft_hash=lane.revised_draft.content_hash,
            outline_artifact_id=outline_result.artifact.id,
            expected_outline_version=outline_result.artifact.version,
            expected_outline_hash=outline_result.artifact.content_hash,
            locale=lane.locale,
        )
        audit_ports[lane.locale] = _CapturePort(_passing_output(audit_input))

    async def fake_audit_port(_session, *, locale: str, **kwargs):
        del _session, kwargs
        return audit_ports[locale]

    monkeypatch.setattr(
        operator_quality_worker,
        "create_cli_assertion_audit_model_port",
        fake_audit_port,
    )
    for index in range(2):
        job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session,
            worker_id=f"cq06-audit-{index}",
        )
        assert job is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=job.id,
            worker_id=f"cq06-audit-{index}",
            runner_registry=registry,
        )

    for index in range(2):
        job = await operator_quality_worker.claim_or_reclaim_quality_job(
            session,
            worker_id=f"cq06-source-{index}",
        )
        assert job is not None
        await operator_quality_worker.execute_quality_job(
            session,
            job_id=job.id,
            worker_id=f"cq06-source-{index}",
            runner_registry=registry,
        )

    await _complete_readiness_lane(
        session,
        case_id=case_id,
        locale="vi-VN",
        monkeypatch=monkeypatch,
        runner_registry=registry,
        worker_prefix="cq06-readiness-vi",
    )
    await _complete_readiness_lane(
        session,
        case_id=case_id,
        locale="en",
        monkeypatch=monkeypatch,
        runner_registry=registry,
        worker_prefix="cq06-readiness-en",
    )

    progress = await get_quality_progress(
        session,
        content_case_id=case_id,
        source_run_id=None,
    )
    assert progress is not None
    return progress, outline_result


def _loader_kwargs(lane, outline_result) -> dict[str, object]:
    assert lane.writer.run is not None
    assert lane.revised_draft is not None
    assert lane.audit.artifact is not None
    assert lane.audit.evaluation is not None
    assert lane.source_copy.artifact is not None
    assert lane.source_copy.evaluation is not None
    assert lane.reader_value.artifact is not None
    assert lane.reader_value.evaluation is not None
    assert lane.search_ai.artifact is not None
    assert lane.search_ai.evaluation is not None

    return {
        "writer_run_id": lane.writer.run.id,
        "source_draft_artifact_id": lane.revised_draft.id,
        "expected_source_draft_version": lane.revised_draft.version,
        "expected_source_draft_hash": lane.revised_draft.content_hash,
        "outline_artifact_id": outline_result.artifact.id,
        "expected_outline_version": outline_result.artifact.version,
        "expected_outline_hash": outline_result.artifact.content_hash,
        "assertion_audit_artifact_id": lane.audit.artifact.id,
        "expected_assertion_audit_version": lane.audit.artifact.version,
        "expected_assertion_audit_hash": lane.audit.artifact.content_hash,
        "assertion_audit_quality_evaluation_id": lane.audit.evaluation.id,
        "source_copy_artifact_id": lane.source_copy.artifact.id,
        "expected_source_copy_version": lane.source_copy.artifact.version,
        "expected_source_copy_hash": lane.source_copy.artifact.content_hash,
        "source_copy_quality_evaluation_id": lane.source_copy.evaluation.id,
        "reader_value_artifact_id": lane.reader_value.artifact.id,
        "expected_reader_value_version": lane.reader_value.artifact.version,
        "expected_reader_value_hash": lane.reader_value.artifact.content_hash,
        "reader_value_quality_evaluation_id": lane.reader_value.evaluation.id,
        "search_ai_artifact_id": lane.search_ai.artifact.id,
        "expected_search_ai_version": lane.search_ai.artifact.version,
        "expected_search_ai_hash": lane.search_ai.artifact.content_hash,
        "search_ai_quality_evaluation_id": lane.search_ai.evaluation.id,
        "locale": lane.locale,
    }


@pytest.mark.asyncio
async def test_deep_quality_input_revalidates_exact_f4_lineage_for_vi_and_en(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        progress, outline_result = await _complete_quality_pipeline(
            session,
            monkeypatch,
        )

        assert {lane.locale for lane in progress.lanes} == {"vi-VN", "en"}
        for lane in progress.lanes:
            loaded = await load_deep_quality_input(
                session,
                **_loader_kwargs(lane, outline_result),
            )
            assert loaded.writer_input.locale == lane.locale
            assert loaded.source_artifact.id == lane.revised_draft.id
            assert loaded.source_copy.artifact.id == lane.source_copy.artifact.id
            assert loaded.reader_value.artifact.id == lane.reader_value.artifact.id
            assert loaded.search_ai.artifact.id == lane.search_ai.artifact.id
            assert loaded.angle_semantic.artifact.id is not None
            assert loaded.outline_semantic.artifact.id is not None
            assert loaded.human_voice_trace.artifact.id is not None
            assert loaded.reader_value.result == "pass"
            assert loaded.search_ai.result == "pass"


@pytest.mark.asyncio
async def test_deep_quality_input_rejects_cross_locale_search_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        progress, outline_result = await _complete_quality_pipeline(
            session,
            monkeypatch,
        )
        en_lane = next(lane for lane in progress.lanes if lane.locale == "en")
        vi_lane = next(lane for lane in progress.lanes if lane.locale == "vi-VN")
        assert vi_lane.search_ai.artifact is not None
        assert vi_lane.search_ai.evaluation is not None

        kwargs = _loader_kwargs(en_lane, outline_result)
        kwargs["search_ai_artifact_id"] = vi_lane.search_ai.artifact.id
        kwargs["expected_search_ai_version"] = vi_lane.search_ai.artifact.version
        kwargs["expected_search_ai_hash"] = vi_lane.search_ai.artifact.content_hash
        kwargs["search_ai_quality_evaluation_id"] = vi_lane.search_ai.evaluation.id

        with pytest.raises(
            DeepQualityInputError,
            match="deep_quality_search_ai_invalid",
        ):
            await load_deep_quality_input(session, **kwargs)


@pytest.mark.asyncio
async def test_deep_quality_input_rejects_expected_snapshot_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        progress, outline_result = await _complete_quality_pipeline(
            session,
            monkeypatch,
        )
        lane = next(lane for lane in progress.lanes if lane.locale == "en")
        kwargs = _loader_kwargs(lane, outline_result)
        kwargs["expected_reader_value_hash"] = "f" * 64

        with pytest.raises(
            DeepQualityInputError,
            match="deep_quality_reader_value_snapshot_mismatch",
        ):
            await load_deep_quality_input(session, **kwargs)
