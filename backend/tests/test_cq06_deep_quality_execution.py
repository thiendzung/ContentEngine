from __future__ import annotations

import copy

import pytest
from test_ce05_outline import isolated_session
from test_cq06_deep_quality_input import (
    _complete_quality_pipeline,
    _loader_kwargs,
)

from app.modules.content_engine.journal.deep_quality_execution import (
    DEEP_QUALITY_ARTIFACT_TYPE,
    DEEP_QUALITY_EVALUATOR_KEY,
    DEEP_QUALITY_EVALUATOR_VERSION,
    deep_quality_task_key,
    ensure_deep_quality_run,
    evaluate_deep_quality,
    load_deep_quality_input_from_handoff,
)
from app.modules.content_engine.journal.deep_quality_input import (
    load_deep_quality_input,
)
from app.modules.content_engine.journal.deep_quality_semantic import (
    DEEP_QUALITY_SEMANTIC_DIMENSIONS,
)
from app.modules.harness.models import StepRun
from app.modules.harness.runtime import ContextInputs, build_context_manifest


def _semantic_output(
    locale: str,
    *,
    warn_key: str | None = None,
) -> dict[str, object]:
    return {
        "locale": locale,
        "dimensions": [
            {
                "key": key,
                "result": "warn" if key == warn_key else "pass",
                "finding": (
                    f"{key} needs one bounded repair."
                    if key == warn_key
                    else f"{key} passes on the exact supplied draft."
                ),
                "remediation": (
                    f"Repair {key} before final review."
                    if key == warn_key
                    else ""
                ),
            }
            for key in DEEP_QUALITY_SEMANTIC_DIMENSIONS
        ],
    }


class _SemanticPort:
    def __init__(self, output: object) -> None:
        self.output = output
        self.calls = 0

    def resolved_model_identity(self) -> tuple[str, str]:
        return "codex_cli", "test-model"

    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object:
        del input_bundle, attempt
        self.calls += 1
        return copy.deepcopy(self.output)


async def _execution_fixture(
    session,
    monkeypatch: pytest.MonkeyPatch,
    *,
    locale: str,
    warn_key: str | None = None,
):
    progress, outline_result = await _complete_quality_pipeline(
        session,
        monkeypatch,
    )
    lane = next(item for item in progress.lanes if item.locale == locale)
    source = await load_deep_quality_input(
        session,
        **_loader_kwargs(lane, outline_result),
    )
    run, handoff, created = await ensure_deep_quality_run(
        session,
        source=source,
    )
    assert created is False
    assert run.status == "pending"
    step = StepRun(
        run_id=run.id,
        step_key=deep_quality_task_key(locale),
        attempt=1,
        status="running",
        input_artifact_refs_json=[
            str(handoff.id),
            str(source.source_artifact.id),
            str(source.search_ai.artifact.id),
        ],
        output_artifact_refs_json=[],
    )
    session.add(step)
    run.status = "running"
    await session.flush()
    manifest = await build_context_manifest(
        session,
        run_id=run.id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version="cq06-deep-quality-test:v1",
            recipe_version="cq06-deep-quality-test-recipe:v1",
            evidence_set_id=source.writer_input.outline_input.bundle.evidence_set_id,
            originality_pack_id=(
                source.writer_input.outline_input.bundle.originality_pack_id
            ),
        ),
    )
    model = _SemanticPort(
        _semantic_output(
            locale,
            warn_key=warn_key,
        )
    )
    return source, run, handoff, step, manifest, model


@pytest.mark.asyncio
async def test_deep_quality_persists_scoreless_exact_assessment_and_reuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        source, run, handoff, step, manifest, model = await _execution_fixture(
            session,
            monkeypatch,
            locale="en",
        )

        first = await evaluate_deep_quality(
            session,
            source=source,
            eval_run_id=run.id,
            step_run_id=step.id,
            handoff_artifact_id=handoff.id,
            model=model,
            provider="codex_cli",
            model_name="test-model",
            context_manifest_id=manifest.id,
            prompt_version="cq06-deep-quality-test:v1",
            recipe_version="cq06-deep-quality-test-recipe:v1",
            max_attempts=1,
        )
        second = await evaluate_deep_quality(
            session,
            source=source,
            eval_run_id=run.id,
            step_run_id=step.id,
            handoff_artifact_id=handoff.id,
            model=model,
            provider="codex_cli",
            model_name="test-model",
            context_manifest_id=manifest.id,
            prompt_version="cq06-deep-quality-test:v1",
            recipe_version="cq06-deep-quality-test-recipe:v1",
            max_attempts=1,
        )

        assert first.reused is False
        assert second.reused is True
        assert first.artifact.id == second.artifact.id
        assert first.artifact.artifact_type == DEEP_QUALITY_ARTIFACT_TYPE
        assert first.assessment.verdict == "pass"
        assert len(first.assessment.dimensions) == 12
        assert model.calls == 1
        assert first.evaluation.score is None
        assert first.evaluation.evaluator_key == DEEP_QUALITY_EVALUATOR_KEY
        assert (
            first.evaluation.evaluator_version
            == DEEP_QUALITY_EVALUATOR_VERSION
        )
        assert first.evaluation.findings_json["numeric_score_used"] is False
        assert str(first.artifact.id) in step.output_artifact_refs_json

        loaded = await load_deep_quality_input_from_handoff(
            session,
            handoff_artifact_id=handoff.id,
        )
        assert loaded.source_artifact.id == source.source_artifact.id
        assert loaded.search_ai.artifact.id == source.search_ai.artifact.id
        assert loaded.human_voice_trace.artifact.id == (
            source.human_voice_trace.artifact.id
        )

        same_run, same_handoff, reused_run = await ensure_deep_quality_run(
            session,
            source=source,
        )
        assert reused_run is True
        assert same_run.id == run.id
        assert same_handoff.id == handoff.id


@pytest.mark.asyncio
async def test_deep_quality_preserves_semantic_warning_without_magic_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        warn_key = "human_voice_motgu_voice"
        source, run, handoff, step, manifest, model = await _execution_fixture(
            session,
            monkeypatch,
            locale="vi-VN",
            warn_key=warn_key,
        )

        result = await evaluate_deep_quality(
            session,
            source=source,
            eval_run_id=run.id,
            step_run_id=step.id,
            handoff_artifact_id=handoff.id,
            model=model,
            provider="codex_cli",
            model_name="test-model",
            context_manifest_id=manifest.id,
            prompt_version="cq06-deep-quality-test:v1",
            recipe_version="cq06-deep-quality-test-recipe:v1",
            max_attempts=1,
        )

        assert result.assessment.verdict == "warn"
        warning = next(
            item
            for item in result.assessment.dimensions
            if item.key == warn_key
        )
        assert warning.result == "warn"
        assert warning.authority == "semantic_model"
        assert warning.remediation
        assert result.evaluation.result == "warn"
        assert result.evaluation.score is None
        assert result.evaluation.findings_json["warn_count"] == 1
        assert result.evaluation.findings_json["fail_count"] == 0
        assert model.calls == 1
