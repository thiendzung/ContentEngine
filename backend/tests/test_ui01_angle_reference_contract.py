from __future__ import annotations

from sqlalchemy import select

import pytest
from test_ce05_agent_runtime import FakeAngleRunner, isolated_session
from test_ce05_angle_approval import _bundle_fixture, _candidate_payload

from app.modules.content_engine.journal.agent_bridge import (
    ANGLE_RENDER_PROTOCOL_VERSION,
    create_cli_angle_model_port,
    render_angle_prompt,
)
from app.modules.content_engine.journal.angle import AngleGenerationError, AngleGenerator
from app.modules.content_engine.models import PromptDefinition, RecipeDefinition, SettingsSnapshot
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import ContentRun, ModelCall
from app.modules.harness.runtime import ContextInputs, build_context_manifest
from app.modules.system.settings_service import settings_hash


async def _runtime_fixture(session, bundle_artifact, bundle):
    run = await session.get(ContentRun, bundle_artifact.run_id)
    assert run is not None
    resolved = {
        "models": {"angle": {"route": "agent_angle"}},
        "model_routes": {
            "agent_angle": {"provider": "codex_cli", "model": "test-model"}
        },
    }
    snapshot = SettingsSnapshot(
        project_id=run.project_id,
        resolved_settings_json=resolved,
        source_version_refs_json=["ui01-angle-reference-contract"],
        content_hash=settings_hash(resolved),
    )
    prompt = await session.scalar(
        select(PromptDefinition).where(
            PromptDefinition.prompt_key == "journal_angle_candidates"
        )
    )
    recipe = await session.scalar(
        select(RecipeDefinition).where(RecipeDefinition.recipe_key == "journal_angle_v1")
    )
    assert prompt is not None and recipe is not None
    prompt.status = "active"
    prompt.approved_by = "founder"
    recipe.status = "active"
    recipe.approved_by = "founder"
    session.add(snapshot)
    await session.flush()
    run.settings_snapshot_id = snapshot.id
    manifest = await build_context_manifest(
        session,
        run_id=run.id,
        step_run_id=None,
        inputs=ContextInputs(
            prompt_version=f"{prompt.prompt_key}:v{prompt.version}",
            recipe_version=f"{recipe.recipe_key}:v{recipe.version}",
            evidence_set_id=bundle.evidence_set_id,
            originality_pack_id=bundle.originality_pack_id,
        ),
    )
    return run, snapshot, prompt, recipe, manifest


@pytest.mark.asyncio
async def test_render_angle_prompt_exposes_exact_reference_allow_list_and_retry_note() -> None:
    async with isolated_session() as session:
        bundle_artifact, bundle, _evidence_set, _pack = await _bundle_fixture(session)
        _run, _snapshot, prompt, recipe, _manifest = await _runtime_fixture(
            session, bundle_artifact, bundle
        )

        first = render_angle_prompt(
            prompt,
            recipe,
            angle_model_input=bundle.angle_model_input,
            attempt=1,
        )
        retry = render_angle_prompt(
            prompt,
            recipe,
            angle_model_input=bundle.angle_model_input,
            attempt=2,
        )

        assert f"ANGLE_RENDER_PROTOCOL_VERSION:\n{ANGLE_RENDER_PROTOCOL_VERSION}" in first
        assert "REFERENCE_CONTRACT_JSON:" in first
        assert (
            '"source_path":"ANGLE_INPUT_JSON.evidence_set.evidence[*].evidence_id"'
            in first
        )
        assert (
            '"source_path":"ANGLE_INPUT_JSON.originality_pack.items[*].source_ref"'
            in first
        )
        assert str(bundle.evidence_ids[0]) in first
        assert bundle.originality_refs[0] in first
        assert '"forbidden_source_fields":["approval_ref","id","snapshot_hash"]' in first
        assert "BOUNDED_RETRY_NOTE:" not in first
        assert "BOUNDED_RETRY_NOTE:" in retry
        assert "copy every reference only from REFERENCE_CONTRACT_JSON allowed_values" in retry


@pytest.mark.asyncio
async def test_approval_ref_is_rejected_and_bad_ref_diagnostics_are_durable() -> None:
    async with isolated_session() as session:
        bundle_artifact, bundle, _evidence_set, _pack = await _bundle_fixture(session)
        run, snapshot, _prompt, _recipe, manifest = await _runtime_fixture(
            session, bundle_artifact, bundle
        )
        originality_pack = bundle.angle_model_input["originality_pack"]
        assert isinstance(originality_pack, dict)
        originality_items = originality_pack["items"]
        assert isinstance(originality_items, list) and originality_items
        first_item = originality_items[0]
        assert isinstance(first_item, dict)
        approval_ref = first_item["approval_ref"]
        assert isinstance(approval_ref, str)
        assert approval_ref != first_item["source_ref"]

        output = [_candidate_payload(bundle, index) for index in range(1, 4)]
        output[0]["originality_refs"] = [approval_ref]
        fake = FakeAngleRunner({"candidates": output})
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", fake)
        port = await create_cli_angle_model_port(
            session,
            run_id=run.id,
            settings_snapshot=snapshot,
            context_manifest_id=manifest.id,
            runner_registry=registry,
        )

        with pytest.raises(AngleGenerationError, match="angle_model_output_invalid") as exc_info:
            await AngleGenerator(max_attempts=1).generate_candidates(
                session,
                journal_input_bundle_id=bundle_artifact.id,
                model=port,
                provider="codex_cli",
                model_name="test-model",
            )
        assert isinstance(exc_info.value.__cause__, AngleGenerationError)
        assert exc_info.value.__cause__.code == "angle_originality_ref_outside_pack"

        call = await session.scalar(
            select(ModelCall).where(ModelCall.run_id == run.id, ModelCall.task_key == "angle")
        )
        assert call is not None and call.status == "completed"
        metadata = call.runtime_metadata_json
        assert isinstance(metadata, dict)
        diagnostics = metadata.get("angle_output_reference_diagnostics")
        assert isinstance(diagnostics, dict)
        assert diagnostics["candidate_count"] == 3
        candidates = diagnostics["candidates"]
        assert isinstance(candidates, list) and len(candidates) == 3
        first_candidate = candidates[0]
        assert isinstance(first_candidate, dict)
        assert first_candidate["originality_refs"] == [approval_ref]
