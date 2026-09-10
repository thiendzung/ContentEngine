from __future__ import annotations

import copy
from typing import Any

import pytest
from sqlalchemy import select

from app.modules.content_engine.journal.angle import (
    AngleGenerator,
    angle_candidate_hash,
    approve_angle_candidate,
)
from app.modules.content_engine.journal.outline import (
    JournalOutline,
    OutlineGenerationError,
    OutlineGenerator,
    OutlineSection,
    load_outline_input,
    outline_model_input_hash,
)
from app.modules.content_engine.journal.outline_agent_bridge import (
    OUTLINE_PROMPT_KEY,
    OUTLINE_RECIPE_KEY,
    OUTLINE_TASK_KEY,
    create_cli_outline_model_port,
)
from app.modules.content_engine.models import PromptDefinition, RecipeDefinition, SettingsSnapshot
from app.modules.harness.agent_runner import (
    AgentCapability,
    AgentRunRequest,
    AgentRunResult,
    AgentRunnerRegistry,
)
from app.modules.harness.models import ContentRun, ModelCall, StepRun
from app.modules.harness.runtime import ContextInputs, build_context_manifest
from app.modules.system.settings_service import settings_hash
from test_ce05_angle_approval import (
    FakeAngleModel,
    _bundle_fixture,
    _candidate_payload,
    isolated_session,
)


class FakeOutlineModel:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = outputs
        self.calls = 0
        self.received: dict[str, object] | None = None

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        del attempt
        self.calls += 1
        self.received = copy.deepcopy(input_bundle)
        return self.outputs[min(self.calls - 1, len(self.outputs) - 1)]


class RoutedOutlineModel(FakeOutlineModel):
    def resolved_model_identity(self) -> tuple[str, str]:
        return "codex_cli", "test-model"


class FakeOutlineRunner:
    def __init__(self, output: object) -> None:
        self.output = output
        self.requests: list[AgentRunRequest] = []

    async def preflight(self) -> AgentCapability:
        return AgentCapability(
            provider="codex_cli",
            executable="codex",
            version="fake-agent-1",
            authenticated=True,
            auth_mode="test",
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.requests.append(request)
        return AgentRunResult(
            provider=request.provider,
            model=request.model,
            runner_version="fake-agent-1",
            structured_output=self.output,
            raw_output_hash="a" * 64,
            exit_code=0,
            usage={"input_tokens": 10, "output_tokens": 20},
            duration_ms=7,
            session_id="outline-test",
        )


async def _approved_fixture(session: Any):
    bundle_artifact, bundle, evidence_set, pack = await _bundle_fixture(session)
    angle_output = [_candidate_payload(bundle, index) for index in range(1, 4)]
    angle_result = await AngleGenerator(max_attempts=1).generate_candidates(
        session,
        journal_input_bundle_id=bundle_artifact.id,
        model=FakeAngleModel([angle_output]),
        provider="fixture-provider",
        model_name="fixture-model",
    )
    selected = angle_result.candidates[0]
    candidate_hash = angle_candidate_hash(selected)
    approval = await approve_angle_candidate(
        session,
        angle_artifact_id=angle_result.artifact.id,
        expected_artifact_version=angle_result.artifact.version,
        expected_artifact_hash=angle_result.artifact.content_hash,
        selected_angle_id=selected.angle_id,
        expected_candidate_hash=candidate_hash,
        approved_by="founder",
        approval_reason="Approved exact Outline test Angle.",
    )
    run = await session.get(ContentRun, bundle_artifact.run_id)
    assert run is not None
    step = StepRun(
        run_id=run.id,
        step_key="outline",
        attempt=1,
        status="running",
    )
    session.add(step)
    await session.flush()
    prompt_version = "journal_outline:v1"
    recipe_version = "journal_outline_v1:v1"
    manifest = await build_context_manifest(
        session,
        run_id=run.id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version=prompt_version,
            recipe_version=recipe_version,
            evidence_set_id=evidence_set.id,
            originality_pack_id=pack.id,
        ),
    )
    return {
        "bundle_artifact": bundle_artifact,
        "bundle": bundle,
        "evidence_set": evidence_set,
        "pack": pack,
        "angle_result": angle_result,
        "selected": selected,
        "candidate_hash": candidate_hash,
        "approval": approval,
        "run": run,
        "step": step,
        "manifest": manifest,
        "prompt_version": prompt_version,
        "recipe_version": recipe_version,
    }


def _outline_payload(bundle: Any) -> dict[str, object]:
    evidence_ref = str(bundle.evidence_ids[0])
    originality_ref = bundle.originality_refs[0]
    return {
        "primary_answer": (
            "There is no universal formula for an artwork price; start with documented "
            "context around the work, then separate those facts from your personal decision."
        ),
        "primary_answer_support_type": "mixed",
        "primary_answer_evidence_refs": [evidence_ref],
        "primary_answer_originality_refs": [originality_ref],
        "primary_answer_claim_guard": "Do not turn context into a universal valuation formula.",
        "sections": [
            {
                "section_id": "s1",
                "heading": "Start with what is documented",
                "purpose": "Give the reader a factual starting point.",
                "answer_direction": "Explain only factors supported by the locked EvidenceSet.",
                "support_type": "factual",
                "evidence_refs": [evidence_ref],
                "originality_refs": [],
                "claim_guards": ["Do not imply one factor mechanically determines price."],
                "reader_movement": "confusion -> factual orientation",
                "internal_link_targets": [],
            },
            {
                "section_id": "s2",
                "heading": "Bring the question back to the real work",
                "purpose": "Use MOTGU-owned material to make the guidance concrete.",
                "answer_direction": "Use the approved MOTGU material without inventing facts.",
                "support_type": "motgu_original",
                "evidence_refs": [],
                "originality_refs": [originality_ref],
                "claim_guards": ["Do not invent availability, price or artist intent."],
                "reader_movement": "orientation -> concrete evaluation",
                "internal_link_targets": ["related Artwork when verified"],
            },
            {
                "section_id": "s3",
                "heading": "Ask before you decide",
                "purpose": "Turn the article into a practical decision aid.",
                "answer_direction": "Give calm questions the reader can use before buying.",
                "support_type": "editorial",
                "evidence_refs": [],
                "originality_refs": [],
                "claim_guards": ["Keep questions editorial; add no new factual claims."],
                "reader_movement": "concrete evaluation -> confident next question",
                "internal_link_targets": [],
            },
        ],
    }


@pytest.mark.asyncio
async def test_outline_binds_exact_approval_support_and_reuses_exact_artifact() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        bundle = fixture["bundle"]
        model = FakeOutlineModel([_outline_payload(bundle)])
        generator = OutlineGenerator(max_attempts=1)
        kwargs = {
            "angle_artifact_id": fixture["angle_result"].artifact.id,
            "expected_angle_artifact_version": fixture["angle_result"].artifact.version,
            "expected_angle_artifact_hash": fixture["angle_result"].artifact.content_hash,
            "selected_angle_id": fixture["selected"].angle_id,
            "expected_candidate_hash": fixture["candidate_hash"],
            "expected_approval_id": fixture["approval"].id,
            "model": model,
            "provider": "fixture-provider",
            "model_name": "fixture-model",
            "context_manifest_id": fixture["manifest"].id,
            "prompt_version": fixture["prompt_version"],
            "recipe_version": fixture["recipe_version"],
        }
        first = await generator.generate_outline(session, **kwargs)
        second = await generator.generate_outline(session, **kwargs)

        assert isinstance(first.outline, JournalOutline)
        assert all(isinstance(section, OutlineSection) for section in first.outline.sections)
        assert len(first.outline.sections) == 3
        assert first.artifact.id == second.artifact.id
        assert first.reused is False
        assert second.reused is True
        assert second.model_attempts == 0
        assert model.calls == 1
        payload = first.artifact.content_json
        assert isinstance(payload, dict)
        assert payload["approved_angle"]["approval"]["id"] == str(fixture["approval"].id)
        assert payload["approved_angle"]["approval"]["selected_candidate_hash"] == fixture[
            "candidate_hash"
        ]
        assert payload["journal_input_bundle"]["content_hash"] == fixture[
            "bundle_artifact"
        ].content_hash
        assert payload["evidence_set"]["content_hash"] == fixture["evidence_set"].content_hash
        assert payload["originality_pack"]["snapshot_hash"] == fixture["pack"].snapshot_hash
        assert payload["model_input"]["content_hash"] == outline_model_input_hash(
            (await load_outline_input(
                session,
                angle_artifact_id=fixture["angle_result"].artifact.id,
                expected_angle_artifact_version=fixture["angle_result"].artifact.version,
                expected_angle_artifact_hash=fixture["angle_result"].artifact.content_hash,
                selected_angle_id=fixture["selected"].angle_id,
                expected_candidate_hash=fixture["candidate_hash"],
                expected_approval_id=fixture["approval"].id,
            )).model_input
        )
        assert payload["outline"]["must_not_claim"] == list(fixture["selected"].excluded_claims)


@pytest.mark.asyncio
async def test_wrong_approval_or_model_route_fails_before_model_call() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        model = RoutedOutlineModel([_outline_payload(fixture["bundle"])])
        with pytest.raises(OutlineGenerationError, match="outline_angle_approval_mismatch"):
            await OutlineGenerator(max_attempts=1).generate_outline(
                session,
                angle_artifact_id=fixture["angle_result"].artifact.id,
                expected_angle_artifact_version=fixture["angle_result"].artifact.version,
                expected_angle_artifact_hash=fixture["angle_result"].artifact.content_hash,
                selected_angle_id=fixture["selected"].angle_id,
                expected_candidate_hash=fixture["candidate_hash"],
                expected_approval_id=fixture["run"].id,
                model=model,
                provider="codex_cli",
                model_name="test-model",
                context_manifest_id=fixture["manifest"].id,
                prompt_version=fixture["prompt_version"],
                recipe_version=fixture["recipe_version"],
            )
        assert model.calls == 0

        with pytest.raises(OutlineGenerationError, match="outline_model_route_mismatch"):
            await OutlineGenerator(max_attempts=1).generate_outline(
                session,
                angle_artifact_id=fixture["angle_result"].artifact.id,
                expected_angle_artifact_version=fixture["angle_result"].artifact.version,
                expected_angle_artifact_hash=fixture["angle_result"].artifact.content_hash,
                selected_angle_id=fixture["selected"].angle_id,
                expected_candidate_hash=fixture["candidate_hash"],
                expected_approval_id=fixture["approval"].id,
                model=model,
                provider="codex_cli",
                model_name="wrong-model",
                context_manifest_id=fixture["manifest"].id,
                prompt_version=fixture["prompt_version"],
                recipe_version=fixture["recipe_version"],
            )
        assert model.calls == 0


@pytest.mark.asyncio
async def test_unsupported_factual_section_and_outside_refs_fail_closed() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        invalid = _outline_payload(fixture["bundle"])
        sections = invalid["sections"]
        assert isinstance(sections, list)
        first = sections[0]
        assert isinstance(first, dict)
        first["evidence_refs"] = []
        model = FakeOutlineModel([invalid])
        with pytest.raises(OutlineGenerationError, match="outline_model_output_invalid"):
            await OutlineGenerator(max_attempts=1).generate_outline(
                session,
                angle_artifact_id=fixture["angle_result"].artifact.id,
                expected_angle_artifact_version=fixture["angle_result"].artifact.version,
                expected_angle_artifact_hash=fixture["angle_result"].artifact.content_hash,
                selected_angle_id=fixture["selected"].angle_id,
                expected_candidate_hash=fixture["candidate_hash"],
                expected_approval_id=fixture["approval"].id,
                model=model,
                provider="fixture-provider",
                model_name="fixture-model",
                context_manifest_id=fixture["manifest"].id,
                prompt_version=fixture["prompt_version"],
                recipe_version=fixture["recipe_version"],
            )
        assert model.calls == 1

    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        invalid = _outline_payload(fixture["bundle"])
        invalid["primary_answer_evidence_refs"] = ["00000000-0000-0000-0000-000000000000"]
        model = FakeOutlineModel([invalid])
        with pytest.raises(OutlineGenerationError, match="outline_model_output_invalid"):
            await OutlineGenerator(max_attempts=1).generate_outline(
                session,
                angle_artifact_id=fixture["angle_result"].artifact.id,
                expected_angle_artifact_version=fixture["angle_result"].artifact.version,
                expected_angle_artifact_hash=fixture["angle_result"].artifact.content_hash,
                selected_angle_id=fixture["selected"].angle_id,
                expected_candidate_hash=fixture["candidate_hash"],
                expected_approval_id=fixture["approval"].id,
                model=model,
                provider="fixture-provider",
                model_name="fixture-model",
                context_manifest_id=fixture["manifest"].id,
                prompt_version=fixture["prompt_version"],
                recipe_version=fixture["recipe_version"],
            )


@pytest.mark.asyncio
async def test_outline_cli_bridge_reuses_run_route_and_records_outline_modelcall() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        run = fixture["run"]
        route_settings = {
            "models": {"angle": {"route": "agent_angle"}},
            "model_routes": {
                "agent_angle": {"provider": "codex_cli", "model": "test-model"}
            },
        }
        snapshot = SettingsSnapshot(
            project_id=run.project_id,
            resolved_settings_json=route_settings,
            source_version_refs_json=["outline-test"],
            content_hash=settings_hash(route_settings),
        )
        session.add(snapshot)
        await session.flush()
        run.settings_snapshot_id = snapshot.id
        fixture["manifest"].settings_snapshot_id = snapshot.id
        await session.flush()

        prompt = await session.scalar(
            select(PromptDefinition).where(PromptDefinition.prompt_key == OUTLINE_PROMPT_KEY)
        )
        recipe = await session.scalar(
            select(RecipeDefinition).where(RecipeDefinition.recipe_key == OUTLINE_RECIPE_KEY)
        )
        assert prompt is not None and recipe is not None
        assert prompt.status == "active"
        assert recipe.status == "active"

        output = _outline_payload(fixture["bundle"])
        fake = FakeOutlineRunner(output)
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", fake)
        port = await create_cli_outline_model_port(
            session,
            run_id=run.id,
            settings_snapshot=snapshot,
            context_manifest_id=fixture["manifest"].id,
            runner_registry=registry,
            locale=fixture["selected"].locale,
        )
        result = await port.generate(
            input_bundle=(await load_outline_input(
                session,
                angle_artifact_id=fixture["angle_result"].artifact.id,
                expected_angle_artifact_version=fixture["angle_result"].artifact.version,
                expected_angle_artifact_hash=fixture["angle_result"].artifact.content_hash,
                selected_angle_id=fixture["selected"].angle_id,
                expected_candidate_hash=fixture["candidate_hash"],
                expected_approval_id=fixture["approval"].id,
            )).model_input,
            attempt=1,
        )
        assert result == output
        assert len(fake.requests) == 1
        request = fake.requests[0]
        assert request.provider == "codex_cli"
        assert request.model == "test-model"
        assert set(request.working_context) == {"outline_model_input"}
        call = await session.scalar(
            select(ModelCall).where(
                ModelCall.run_id == run.id,
                ModelCall.task_key == OUTLINE_TASK_KEY,
            )
        )
        assert call is not None
        assert call.status == "completed"
        assert call.provider == "codex_cli"
        assert call.model == "test-model"
        assert call.runtime_metadata_json is not None
        assert call.runtime_metadata_json["route_reuse"] == "angle"
