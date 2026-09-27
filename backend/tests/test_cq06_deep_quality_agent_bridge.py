from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from test_ce05_outline import isolated_session
from test_cq06_deep_quality_input import (
    _complete_quality_pipeline,
    _loader_kwargs,
)

from app.modules.content_engine.journal.deep_quality_agent_bridge import (
    DEEP_QUALITY_PROMPT_VERSION,
    DEEP_QUALITY_RECIPE_VERSION,
    DEEP_QUALITY_ROUTE_TASK_KEY,
    create_cli_deep_quality_model_port,
)
from app.modules.content_engine.journal.deep_quality_execution import (
    deep_quality_task_key,
    ensure_deep_quality_run,
    evaluate_deep_quality,
)
from app.modules.content_engine.journal.deep_quality_input import (
    load_deep_quality_input,
)
from app.modules.content_engine.journal.deep_quality_semantic import (
    DEEP_QUALITY_SEMANTIC_DIMENSIONS,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import (
    AgentCapability,
    AgentRunnerRegistry,
    AgentRunRequest,
    AgentRunResult,
)
from app.modules.harness.models import ModelCall
from app.modules.harness.runtime import ContextInputs, build_context_manifest


def _semantic_output(locale: str) -> dict[str, object]:
    return {
        "locale": locale,
        "dimensions": [
            {
                "key": key,
                "result": "pass",
                "finding": f"{key} passes.",
                "remediation": "",
            }
            for key in DEEP_QUALITY_SEMANTIC_DIMENSIONS
        ],
    }


class _Runner:
    def __init__(self, output: object) -> None:
        self.output = output
        self.requests: list[AgentRunRequest] = []

    async def preflight(self) -> AgentCapability:
        return AgentCapability(
            provider="codex_cli",
            executable="codex",
            version="fixture-cq06",
            authenticated=True,
            auth_mode="test",
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.requests.append(request)
        return AgentRunResult(
            provider=request.provider,
            model=request.model,
            runner_version="fixture-cq06",
            runner_executable=(
                "/Applications/ChatGPT.app/Contents/Resources/codex"
            ),
            structured_output=self.output,
            raw_output_hash="c" * 64,
            exit_code=0,
            usage={
                "input_tokens": 120,
                "output_tokens": 80,
                "cost": "0.001",
            },
            duration_ms=9,
            session_id="cq06-test-session",
        )


@pytest.mark.asyncio
async def test_deep_quality_agent_bridge_is_bounded_and_records_truthful_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        progress, outline_result = await _complete_quality_pipeline(
            session,
            monkeypatch,
        )
        lane = next(item for item in progress.lanes if item.locale == "en")
        source = await load_deep_quality_input(
            session,
            **_loader_kwargs(lane, outline_result),
        )
        assert lane.deep_quality.run is not None
        assert lane.deep_quality.handoff is not None
        assert lane.deep_quality.step is not None
        run = lane.deep_quality.run
        handoff = lane.deep_quality.handoff
        step = lane.deep_quality.step
        assert run.status == "pending"
        assert step.status == "pending"
        assert step.input_artifact_refs_json == [
            str(handoff.id),
            str(source.source_artifact.id),
            str(source.search_ai.artifact.id),
        ]

        same_run, same_handoff, reused = await ensure_deep_quality_run(
            session,
            source=source,
        )
        assert reused is True
        assert same_run.id == run.id
        assert same_handoff.id == handoff.id

        run.status = "running"
        step.status = "running"
        await session.flush()

        manifest = await build_context_manifest(
            session,
            run_id=run.id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version=DEEP_QUALITY_PROMPT_VERSION,
                recipe_version=DEEP_QUALITY_RECIPE_VERSION,
                evidence_set_id=(
                    source.writer_input.outline_input.bundle.evidence_set_id
                ),
                originality_pack_id=(
                    source.writer_input.outline_input.bundle.originality_pack_id
                ),
            ),
        )
        snapshot = await session.get(
            SettingsSnapshot,
            run.settings_snapshot_id,
        )
        assert snapshot is not None

        runner = _Runner(_semantic_output("en"))
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", runner)
        port = await create_cli_deep_quality_model_port(
            session,
            run_id=run.id,
            settings_snapshot=snapshot,
            context_manifest_id=manifest.id,
            runner_registry=registry,
            locale="en",
        )

        result = await evaluate_deep_quality(
            session,
            source=source,
            eval_run_id=run.id,
            step_run_id=step.id,
            handoff_artifact_id=handoff.id,
            model=port,
            provider="codex_cli",
            model_name="test-model",
            context_manifest_id=manifest.id,
            prompt_version=DEEP_QUALITY_PROMPT_VERSION,
            recipe_version=DEEP_QUALITY_RECIPE_VERSION,
            max_attempts=1,
        )

        assert result.assessment.verdict == "pass"
        assert len(runner.requests) == 1
        request = runner.requests[0]
        assert request.provider == "codex_cli"
        assert request.model == "test-model"
        assert request.timeout > 0
        assert "Do not research" in request.prompt
        assert "declare an overall verdict" in request.prompt
        serialized_context = json.dumps(
            request.working_context,
            ensure_ascii=False,
            sort_keys=True,
        )
        assert "evidence_set" not in serialized_context
        assert "originality_pack" not in serialized_context
        assert "other_locale_draft" not in serialized_context
        assert "translation_source" not in serialized_context
        schema = request.structured_output_schema
        assert "score" not in json.dumps(schema, sort_keys=True)

        call = await session.scalar(
            select(ModelCall).where(
                ModelCall.run_id == run.id,
                ModelCall.task_key == deep_quality_task_key("en"),
            )
        )
        assert call is not None
        assert call.status == "completed"
        assert call.provider == "codex_cli"
        assert call.model == "test-model"
        assert call.prompt_version == DEEP_QUALITY_PROMPT_VERSION
        assert call.runtime_metadata_json is not None
        assert call.runtime_metadata_json["route_reuse"] == (
            DEEP_QUALITY_ROUTE_TASK_KEY
        )
        assert call.runtime_metadata_json["stage"] == (
            "deep_quality_semantic"
        )
        assert call.runtime_metadata_json["tools_allowed"] is False
        assert call.runtime_metadata_json["numeric_score_used"] is False
        assert call.runtime_metadata_json["overall_verdict_authority"] is False
        assert call.runtime_metadata_json["runner_executable"] == (
            "/Applications/ChatGPT.app/Contents/Resources/codex"
        )
