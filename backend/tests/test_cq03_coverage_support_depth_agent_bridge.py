from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.modules.content_engine.journal.coverage_support_depth_agent_bridge as bridge
from app.modules.content_engine.journal.coverage_support_depth_agent_bridge import (
    COVERAGE_SUPPORT_DEPTH_ROUTE_TASK_KEY,
    CliCoverageSupportDepthModelPort,
    CoverageSupportDepthRegistryConfig,
    _bind_output_schema,
)
from app.modules.content_engine.journal.coverage_support_depth_eval import (
    build_coverage_support_depth_model_input,
)
from app.modules.harness.agent_runner import (
    AgentRunnerRegistry,
    AgentRunRequest,
    AgentRunResult,
)
from app.modules.harness.models import ContentRun, ContextManifest


def _base_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "integer"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "requirement_id": {"type": "string"},
                        "status": {"type": "string"},
                        "evidence_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "caveat_evidence_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "originality_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "rationale": {"type": "string"},
                        "gaps": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            },
        },
    }


def test_output_schema_binds_exact_allowed_refs() -> None:
    model_input = build_coverage_support_depth_model_input(
        coverage_requirements=["One", "Two"],
        evidence_items=[
            {"evidence_id": "ev-support", "relation": "supports"},
            {"evidence_id": "ev-context", "relation": "context_only"},
        ],
        originality_items=[
            {
                "type": "motgu_owned_material",
                "source_ref": "motgu:one",
                "material": "Owned material",
                "writer_use": "Use as first-party context",
                "guardrails": "Do not call it external proof",
                "approval_ref": "approval:one",
            }
        ],
        evidence_set_ref={"id": "es", "version": 1, "content_hash": "a" * 64},
        originality_pack_ref={"id": "op", "snapshot_hash": "b" * 64},
    )

    schema = _bind_output_schema(_base_schema(), model_input=model_input)
    items = schema["properties"]["items"]  # type: ignore[index]
    assert items["minItems"] == 2  # type: ignore[index]
    assert items["maxItems"] == 2  # type: ignore[index]
    props = items["items"]["properties"]  # type: ignore[index]
    assert props["requirement_id"]["enum"] == ["coverage-1", "coverage-2"]
    assert props["evidence_refs"]["items"]["enum"] == ["ev-support"]
    assert props["caveat_evidence_refs"]["items"]["enum"] == ["ev-context"]
    assert props["originality_refs"]["items"]["enum"] == ["motgu:one"]


class _FakeSession:
    def __init__(self, *, run: object, manifest: object) -> None:
        self.run = run
        self.manifest = manifest

    async def get(self, model: object, key: object) -> object | None:
        if model is ContentRun and key == self.run.id:  # type: ignore[attr-defined]
            return self.run
        if model is ContextManifest and key == self.manifest.id:  # type: ignore[attr-defined]
            return self.manifest
        return None


class _Runner:
    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        return AgentRunResult(
            provider=request.provider,
            model=request.model,
            runner_version="fixture-codex",
            structured_output={"schema_version": 1, "items": []},
            raw_output_hash="c" * 64,
            exit_code=0,
            usage={"input_tokens": 1, "output_tokens": 1},
            duration_ms=1,
        )


@pytest.mark.asyncio
async def test_model_call_uses_exact_angle_route_key_for_policy_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = uuid4()
    step_run_id = uuid4()
    settings_id = uuid4()
    manifest_id = uuid4()
    settings_snapshot = SimpleNamespace(
        id=settings_id,
        resolved_settings_json={
            "models": {
                "angle": {
                    "provider": "codex_cli",
                    "model": "fixture-model",
                }
            }
        },
    )
    prompt = SimpleNamespace(
        prompt_key="journal_coverage_support_depth_en",
        version=1,
        body="Return JSON only.",
        output_schema_json=_base_schema(),
    )
    recipe = SimpleNamespace(
        recipe_key="journal_coverage_support_depth_en_v1",
        version=1,
        recipe_json={"strategy": "cq03"},
    )
    run = SimpleNamespace(
        id=run_id,
        settings_snapshot_id=settings_id,
    )
    manifest = SimpleNamespace(
        id=manifest_id,
        run_id=run_id,
        step_run_id=step_run_id,
        prompt_version="journal_coverage_support_depth_en:v1",
        recipe_version="journal_coverage_support_depth_en_v1:v1",
    )
    session = _FakeSession(run=run, manifest=manifest)
    registry = AgentRunnerRegistry()
    registry.register("codex_cli", _Runner())

    captured: dict[str, object] = {}

    async def _start_model_call(*_args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(id=uuid4())

    async def _complete_model_call(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(bridge, "start_model_call", _start_model_call)
    monkeypatch.setattr(bridge, "complete_model_call", _complete_model_call)

    port = CliCoverageSupportDepthModelPort(
        session,  # type: ignore[arg-type]
        run_id=run_id,
        settings_snapshot=settings_snapshot,  # type: ignore[arg-type]
        context_manifest_id=manifest_id,
        prompt=prompt,  # type: ignore[arg-type]
        recipe=recipe,  # type: ignore[arg-type]
        config=CoverageSupportDepthRegistryConfig(
            locale="en",
            prompt_key=prompt.prompt_key,
            recipe_key=recipe.recipe_key,
        ),
        runner_registry=registry,
        timeout=1.0,
    )

    await port.generate(
        input_bundle=build_coverage_support_depth_model_input(
            coverage_requirements=[],
            evidence_items=[],
            originality_items=[],
            evidence_set_ref={
                "id": "es-1",
                "version": 1,
                "content_hash": "a" * 64,
            },
            originality_pack_ref={
                "id": "op-1",
                "snapshot_hash": "b" * 64,
            },
        ),
        attempt=1,
    )

    assert captured["task_key"] == COVERAGE_SUPPORT_DEPTH_ROUTE_TASK_KEY
    assert captured["task_key"] == "angle"
