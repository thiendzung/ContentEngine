from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_outline import (
    FakeOutlineModel,
    OutlineFixture,
    _approved_fixture,
    _generate as _generate_outline,
    _outline_payload,
    isolated_session,
)

from app.modules.content_engine.journal.outline import OutlineGenerationResult
from app.modules.content_engine.journal.writer import (
    WriterGenerationError,
    WriterGenerationResult,
    WriterGenerator,
    WriterInput,
    WriterModelPort,
    load_writer_input,
)
from app.modules.content_engine.journal.writer_agent_bridge import (
    WRITER_ROUTE_TASK_KEY,
    create_cli_writer_model_port,
    writer_registry_config,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import (
    AgentCapability,
    AgentRunnerRegistry,
    AgentRunRequest,
    AgentRunResult,
)
from app.modules.harness.models import ContextManifest, ModelCall, StepRun
from app.modules.harness.runtime import ContextInputs, build_context_manifest
from app.modules.system.settings_service import active_prompt_definition, active_recipe_definition
from app.modules.system.settings_service import settings_hash


class FakeWriterModel:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = outputs
        self.calls = 0
        self.received: dict[str, object] | None = None

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        del attempt
        self.calls += 1
        self.received = copy.deepcopy(input_bundle)
        return self.outputs[min(self.calls - 1, len(self.outputs) - 1)]


class RoutedWriterModel(FakeWriterModel):
    def resolved_model_identity(self) -> tuple[str, str]:
        return "codex_cli", "test-model"


class FakeWriterRunner:
    def __init__(self, output: object) -> None:
        self.output = output
        self.requests: list[AgentRunRequest] = []

    async def preflight(self) -> AgentCapability:
        return AgentCapability(
            provider="codex_cli",
            executable="codex",
            version="fake-writer-agent-1",
            authenticated=True,
            auth_mode="test",
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.requests.append(request)
        return AgentRunResult(
            provider=request.provider,
            model=request.model,
            runner_version="fake-writer-agent-1",
            structured_output=self.output,
            raw_output_hash="b" * 64,
            exit_code=0,
            usage={"input_tokens": 100, "output_tokens": 200},
            duration_ms=11,
            session_id="writer-test",
        )


@dataclass
class WriterFixture:
    outline_fixture: OutlineFixture
    outline_result: OutlineGenerationResult
    writer_input: WriterInput
    step: StepRun
    manifest: ContextManifest
    prompt_version: str
    recipe_version: str


async def _outline_result(
    session: AsyncSession,
) -> tuple[OutlineFixture, OutlineGenerationResult]:
    fixture = await _approved_fixture(session)
    result = await _generate_outline(
        session,
        fixture,
        FakeOutlineModel([_outline_payload(fixture.bundle)]),
    )
    return fixture, result


async def _writer_fixture(session: AsyncSession, *, locale: str) -> WriterFixture:
    outline_fixture, outline_result = await _outline_result(session)
    writer_input = await load_writer_input(
        session,
        outline_artifact_id=outline_result.artifact.id,
        expected_outline_version=outline_result.artifact.version,
        expected_outline_hash=outline_result.artifact.content_hash,
        locale=locale,
    )
    task_key = f"writer-test-{locale}"
    step = StepRun(
        run_id=outline_result.artifact.run_id,
        step_key=task_key,
        attempt=1,
        status="running",
    )
    session.add(step)
    await session.flush()
    prompt_version = f"writer-test-{locale}:v1"
    recipe_version = f"writer-test-recipe-{locale}:v1"
    manifest = await build_context_manifest(
        session,
        run_id=outline_result.artifact.run_id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version=prompt_version,
            recipe_version=recipe_version,
            evidence_set_id=outline_fixture.bundle.evidence_set_id,
            originality_pack_id=outline_fixture.bundle.originality_pack_id,
        ),
    )
    return WriterFixture(
        outline_fixture=outline_fixture,
        outline_result=outline_result,
        writer_input=writer_input,
        step=step,
        manifest=manifest,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )


def _draft_payload(writer_input: WriterInput, locale: str) -> dict[str, object]:
    outline = writer_input.outline_payload
    raw_sections = outline["sections"]
    assert isinstance(raw_sections, list)
    sections: list[dict[str, object]] = []
    for index, raw_section in enumerate(raw_sections, start=1):
        assert isinstance(raw_section, dict)
        if locale == "vi-VN":
            heading = f"Phần {index}: {raw_section['heading']}"
            body = "Giải thích ngắn gọn, bình tĩnh và bám đúng phần hỗ trợ đã được duyệt."
        else:
            heading = f"Section {index}: {raw_section['heading']}"
            body = "Explain the approved point clearly, calmly and only from the supplied support."
        sections.append(
            {
                "section_id": raw_section["section_id"],
                "heading": heading,
                "body_markdown": body,
                "evidence_refs": list(cast(list[str], raw_section["evidence_refs"])),
                "originality_refs": list(cast(list[str], raw_section["originality_refs"])),
                "unresolved_factual_claims": [],
            }
        )
    if locale == "vi-VN":
        title = "Hiểu giá một tác phẩm nghệ thuật: những điều nên hỏi trước khi quyết định"
        standfirst = "Một hướng dẫn bình tĩnh cho người mua tác phẩm gốc lần đầu."
        lead = "Giá niêm yết không tự nó cho biết một tác phẩm có phù hợp với quyết định của bạn hay không."
        closing = "Hãy dành thời gian nhìn lại những gì bạn đã biết và hỏi thêm khi cần."
    else:
        title = "Understanding an artwork's price: what to ask before you decide"
        standfirst = "A calm guide for a first-time buyer of an original artwork."
        lead = "A listed price alone cannot tell you whether a work fits the decision in front of you."
        closing = "Take your time, review what you know, and ask for context where you still need it."
    return {
        "locale": locale,
        "title": title,
        "standfirst": standfirst,
        "lead_markdown": lead,
        "lead_evidence_refs": list(cast(list[str], outline["primary_answer_evidence_refs"])),
        "lead_originality_refs": list(
            cast(list[str], outline["primary_answer_originality_refs"])
        ),
        "sections": sections,
        "closing_markdown": closing,
        "internal_link_intents": [],
        "unresolved_factual_claims": [],
    }


async def _generate_draft(
    session: AsyncSession,
    fixture: WriterFixture,
    model: WriterModelPort,
) -> WriterGenerationResult:
    return await WriterGenerator(max_attempts=1).generate_draft(
        session,
        outline_artifact_id=fixture.outline_result.artifact.id,
        expected_outline_version=fixture.outline_result.artifact.version,
        expected_outline_hash=fixture.outline_result.artifact.content_hash,
        locale=fixture.writer_input.locale,
        model=model,
        provider="fixture-provider",
        model_name="fixture-model",
        context_manifest_id=fixture.manifest.id,
        prompt_version=fixture.prompt_version,
        recipe_version=fixture.recipe_version,
    )


@pytest.mark.asyncio
async def test_writer_binds_outline_support_and_reuses_exact_locale_artifact() -> None:
    async with isolated_session() as session:
        fixture = await _writer_fixture(session, locale="vi-VN")
        model = FakeWriterModel([_draft_payload(fixture.writer_input, "vi-VN")])
        first = await _generate_draft(session, fixture, model)
        second = await _generate_draft(session, fixture, model)

        assert first.reused is False
        assert second.reused is True
        assert second.model_attempts == 0
        assert first.artifact.id == second.artifact.id
        assert first.artifact.content_hash == second.artifact.content_hash
        assert first.draft.locale == "vi-VN"
        assert model.calls == 1
        assert model.received is not None
        serialized = json.dumps(model.received, ensure_ascii=False, sort_keys=True)
        assert "other_locale_draft" not in serialized
        assert "translation_source" not in serialized
        assert "journal_draft" not in serialized


@pytest.mark.asyncio
async def test_vi_and_en_are_independent_siblings_from_same_outline() -> None:
    async with isolated_session() as session:
        outline_fixture, outline_result = await _outline_result(session)
        inputs: dict[str, WriterInput] = {}
        results: dict[str, WriterGenerationResult] = {}
        models: dict[str, FakeWriterModel] = {}
        for locale in ("vi-VN", "en"):
            writer_input = await load_writer_input(
                session,
                outline_artifact_id=outline_result.artifact.id,
                expected_outline_version=outline_result.artifact.version,
                expected_outline_hash=outline_result.artifact.content_hash,
                locale=locale,
            )
            step = StepRun(
                run_id=outline_result.artifact.run_id,
                step_key=f"sibling-{locale}",
                attempt=1,
                status="running",
            )
            session.add(step)
            await session.flush()
            manifest = await build_context_manifest(
                session,
                run_id=outline_result.artifact.run_id,
                step_run_id=step.id,
                inputs=ContextInputs(
                    prompt_version=f"sibling-{locale}:v1",
                    recipe_version=f"sibling-recipe-{locale}:v1",
                    evidence_set_id=outline_fixture.bundle.evidence_set_id,
                    originality_pack_id=outline_fixture.bundle.originality_pack_id,
                ),
            )
            model = FakeWriterModel([_draft_payload(writer_input, locale)])
            result = await WriterGenerator(max_attempts=1).generate_draft(
                session,
                outline_artifact_id=outline_result.artifact.id,
                expected_outline_version=outline_result.artifact.version,
                expected_outline_hash=outline_result.artifact.content_hash,
                locale=locale,
                model=model,
                provider="fixture-provider",
                model_name="fixture-model",
                context_manifest_id=manifest.id,
                prompt_version=f"sibling-{locale}:v1",
                recipe_version=f"sibling-recipe-{locale}:v1",
            )
            inputs[locale] = writer_input
            results[locale] = result
            models[locale] = model

        assert results["vi-VN"].artifact.id != results["en"].artifact.id
        assert results["vi-VN"].artifact.locale == "vi-VN"
        assert results["en"].artifact.locale == "en"
        assert inputs["vi-VN"].outline_artifact.id == inputs["en"].outline_artifact.id
        assert models["vi-VN"].received is not None
        assert models["en"].received is not None
        assert models["vi-VN"].received["journal_outline_ref"] == models["en"].received[
            "journal_outline_ref"
        ]
        assert models["vi-VN"].received["outline"] == models["en"].received["outline"]
        assert models["vi-VN"].received["evidence_set"] == models["en"].received["evidence_set"]
        assert models["vi-VN"].received["originality_pack"] == models["en"].received[
            "originality_pack"
        ]


@pytest.mark.asyncio
async def test_writer_support_drift_fails_closed() -> None:
    async with isolated_session() as session:
        fixture = await _writer_fixture(session, locale="en")
        invalid = _draft_payload(fixture.writer_input, "en")
        sections = cast(list[object], invalid["sections"])
        first = cast(dict[str, object], sections[0])
        first["evidence_refs"] = [str(fixture.outline_fixture.bundle.evidence_ids[0])]
        model = FakeWriterModel([invalid])

        with pytest.raises(WriterGenerationError, match="writer_model_output_invalid"):
            await _generate_draft(session, fixture, model)
        assert model.calls == 1


@pytest.mark.asyncio
async def test_writer_stale_outline_fails_before_model_call() -> None:
    async with isolated_session() as session:
        fixture = await _writer_fixture(session, locale="en")
        model = FakeWriterModel([_draft_payload(fixture.writer_input, "en")])
        with pytest.raises(WriterGenerationError, match="writer_outline_snapshot_mismatch"):
            await WriterGenerator(max_attempts=1).generate_draft(
                session,
                outline_artifact_id=fixture.outline_result.artifact.id,
                expected_outline_version=fixture.outline_result.artifact.version,
                expected_outline_hash="0" * 64,
                locale="en",
                model=model,
                provider="fixture-provider",
                model_name="fixture-model",
                context_manifest_id=fixture.manifest.id,
                prompt_version=fixture.prompt_version,
                recipe_version=fixture.recipe_version,
            )
        assert model.calls == 0


@pytest.mark.asyncio
async def test_writer_bridge_uses_locale_registry_and_records_modelcall() -> None:
    async with isolated_session() as session:
        outline_fixture, outline_result = await _outline_result(session)
        writer_input = await load_writer_input(
            session,
            outline_artifact_id=outline_result.artifact.id,
            expected_outline_version=outline_result.artifact.version,
            expected_outline_hash=outline_result.artifact.content_hash,
            locale="en",
        )
        config = writer_registry_config("en")
        prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=config.recipe_key,
            content_type="journal",
            locale="en",
            task_key=config.task_key,
        )
        prompt_version = f"{prompt.prompt_key}:v{prompt.version}"
        recipe_version = f"{recipe.recipe_key}:v{recipe.version}"
        step = StepRun(
            run_id=outline_result.artifact.run_id,
            step_key=config.task_key,
            attempt=1,
            status="running",
        )
        session.add(step)
        await session.flush()
        manifest = await build_context_manifest(
            session,
            run_id=outline_result.artifact.run_id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                evidence_set_id=outline_fixture.bundle.evidence_set_id,
                originality_pack_id=outline_fixture.bundle.originality_pack_id,
            ),
        )
        route_settings = {
            "models": {"angle": {"route": "agent_angle"}},
            "model_routes": {
                "agent_angle": {"provider": "codex_cli", "model": "test-model"}
            },
        }
        snapshot = SettingsSnapshot(
            id=outline_fixture.run.settings_snapshot_id,
            project_id=outline_fixture.run.project_id,
            resolved_settings_json=route_settings,
            source_version_refs_json=["writer-test"],
            content_hash=settings_hash(route_settings),
        )
        fake = FakeWriterRunner(_draft_payload(writer_input, "en"))
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", fake)
        port = await create_cli_writer_model_port(
            session,
            run_id=outline_fixture.run.id,
            settings_snapshot=snapshot,
            context_manifest_id=manifest.id,
            runner_registry=registry,
            locale="en",
        )
        result = await port.generate(input_bundle=writer_input.model_input, attempt=1)

        assert result == _draft_payload(writer_input, "en")
        assert len(fake.requests) == 1
        request = fake.requests[0]
        assert request.provider == "codex_cli"
        assert request.model == "test-model"
        assert set(request.working_context) == {"writer_model_input"}
        assert "journal_draft" not in json.dumps(request.working_context, sort_keys=True)
        call = await session.scalar(
            select(ModelCall).where(
                ModelCall.run_id == outline_fixture.run.id,
                ModelCall.task_key == config.task_key,
            )
        )
        assert call is not None
        assert call.status == "completed"
        assert call.runtime_metadata_json is not None
        assert call.runtime_metadata_json["route_reuse"] == WRITER_ROUTE_TASK_KEY
        assert call.runtime_metadata_json["locale"] == "en"
        assert call.runtime_metadata_json["independent_locale_generation"] is True
