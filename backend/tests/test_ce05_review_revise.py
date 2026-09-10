from __future__ import annotations

import copy
import json
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_writer import (
    FakeWriterModel,
    FakeWriterRunner,
    WriterFixture,
    _draft_payload,
    _generate_draft,
    _writer_fixture,
    isolated_session,
)

from app.modules.content_engine.journal.review_revise import (
    ReviewReviseGenerator,
    ReviewReviseInput,
    load_review_revise_input,
    unresolved_factual_claims,
)
from app.modules.content_engine.journal.review_revise_agent_bridge import (
    REVIEW_REVISE_ROUTE_TASK_KEY,
    create_cli_review_revise_model_port,
    review_revise_registry_config,
)
from app.modules.content_engine.journal.writer import (
    WriterGenerationError,
    WriterGenerationResult,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import Artifact, ContextManifest, ModelCall, StepRun
from app.modules.harness.runtime import ContextInputs, build_context_manifest
from app.modules.system.settings_service import (
    active_prompt_definition,
    active_recipe_definition,
    settings_hash,
)


def _with_unresolved(payload: dict[str, object]) -> dict[str, object]:
    value = copy.deepcopy(payload)
    sections = cast(list[object], value["sections"])
    first = cast(dict[str, object], sections[0])
    first["unresolved_factual_claims"] = [
        "Specific artwork identity, dimensions and material are not supplied."
    ]
    value["unresolved_factual_claims"] = [
        "No specific artwork facts are attached to determine a particular price."
    ]
    return value


async def _source_draft(
    session: AsyncSession,
    *,
    locale: str,
    unresolved: bool,
) -> tuple[WriterFixture, WriterGenerationResult]:
    fixture = await _writer_fixture(session, locale=locale)
    payload = _draft_payload(fixture.writer_input, locale)
    if unresolved:
        payload = _with_unresolved(payload)
    result = await _generate_draft(session, fixture, FakeWriterModel([payload]))
    return fixture, result


async def _review_input(
    session: AsyncSession,
    fixture: WriterFixture,
    source: WriterGenerationResult,
) -> ReviewReviseInput:
    return await load_review_revise_input(
        session,
        writer_run_id=fixture.writer_input.writer_run.id,
        source_draft_artifact_id=source.artifact.id,
        expected_source_draft_version=source.artifact.version,
        expected_source_draft_hash=source.artifact.content_hash,
        outline_artifact_id=fixture.outline_result.artifact.id,
        expected_outline_version=fixture.outline_result.artifact.version,
        expected_outline_hash=fixture.outline_result.artifact.content_hash,
        locale=fixture.writer_input.locale,
    )


async def _review_manifest(
    session: AsyncSession,
    fixture: WriterFixture,
    source: WriterGenerationResult,
) -> tuple[StepRun, ContextManifest, str, str]:
    locale = fixture.writer_input.locale
    step = StepRun(
        run_id=fixture.writer_input.writer_run.id,
        step_key=f"review-test-{locale}",
        attempt=1,
        status="running",
        input_artifact_refs_json=[
            str(source.artifact.id),
            str(fixture.writer_input.handoff_artifact.id),
            str(fixture.outline_result.artifact.id),
        ],
    )
    session.add(step)
    await session.flush()
    prompt_version = f"review-test-{locale}:v1"
    recipe_version = f"review-test-recipe-{locale}:v1"
    manifest = await build_context_manifest(
        session,
        run_id=fixture.writer_input.writer_run.id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version=prompt_version,
            recipe_version=recipe_version,
            evidence_set_id=fixture.outline_fixture.bundle.evidence_set_id,
            originality_pack_id=fixture.outline_fixture.bundle.originality_pack_id,
        ),
    )
    return step, manifest, prompt_version, recipe_version


async def _revise(
    session: AsyncSession,
    fixture: WriterFixture,
    source: WriterGenerationResult,
    model: FakeWriterModel,
    *,
    max_attempts: int = 2,
) -> WriterGenerationResult:
    _step, manifest, prompt_version, recipe_version = await _review_manifest(
        session,
        fixture,
        source,
    )
    return await ReviewReviseGenerator(max_attempts=max_attempts).revise_draft(
        session,
        writer_run_id=fixture.writer_input.writer_run.id,
        source_draft_artifact_id=source.artifact.id,
        expected_source_draft_version=source.artifact.version,
        expected_source_draft_hash=source.artifact.content_hash,
        outline_artifact_id=fixture.outline_result.artifact.id,
        expected_outline_version=fixture.outline_result.artifact.version,
        expected_outline_hash=fixture.outline_result.artifact.content_hash,
        locale=fixture.writer_input.locale,
        model=model,
        provider="fixture-provider",
        model_name="fixture-model",
        context_manifest_id=manifest.id,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )


@pytest.mark.asyncio
async def test_review_revise_turns_declared_gaps_into_clean_v2_and_reuses_it() -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft(session, locale="en", unresolved=True)
        source_snapshot = copy.deepcopy(source.artifact.content_json)
        review_input = await _review_input(session, fixture, source)
        assert len(unresolved_factual_claims(review_input.source_draft)) == 2
        assert "source_draft" in review_input.model_input
        assert "source_unresolved_factual_claims" in review_input.model_input
        serialized = json.dumps(review_input.model_input, ensure_ascii=False, sort_keys=True)
        assert "other_locale_draft" not in serialized
        assert "translation_source" not in serialized

        revised_payload = _draft_payload(fixture.writer_input, "en")
        model = FakeWriterModel([revised_payload])
        step, manifest, prompt_version, recipe_version = await _review_manifest(
            session,
            fixture,
            source,
        )
        generator = ReviewReviseGenerator(max_attempts=1)
        first = await generator.revise_draft(
            session,
            writer_run_id=fixture.writer_input.writer_run.id,
            source_draft_artifact_id=source.artifact.id,
            expected_source_draft_version=source.artifact.version,
            expected_source_draft_hash=source.artifact.content_hash,
            outline_artifact_id=fixture.outline_result.artifact.id,
            expected_outline_version=fixture.outline_result.artifact.version,
            expected_outline_hash=fixture.outline_result.artifact.content_hash,
            locale="en",
            model=model,
            provider="fixture-provider",
            model_name="fixture-model",
            context_manifest_id=manifest.id,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
        )
        second = await generator.revise_draft(
            session,
            writer_run_id=fixture.writer_input.writer_run.id,
            source_draft_artifact_id=source.artifact.id,
            expected_source_draft_version=source.artifact.version,
            expected_source_draft_hash=source.artifact.content_hash,
            outline_artifact_id=fixture.outline_result.artifact.id,
            expected_outline_version=fixture.outline_result.artifact.version,
            expected_outline_hash=fixture.outline_result.artifact.content_hash,
            locale="en",
            model=model,
            provider="fixture-provider",
            model_name="fixture-model",
            context_manifest_id=manifest.id,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
        )

        assert step.run_id == first.artifact.run_id
        assert first.artifact.id != source.artifact.id
        assert first.artifact.version == source.artifact.version + 1
        assert first.reused is False
        assert second.reused is True
        assert second.model_attempts == 0
        assert second.artifact.id == first.artifact.id
        assert unresolved_factual_claims(first.draft) == ()
        assert model.calls == 1
        assert source.artifact.content_json == source_snapshot


@pytest.mark.asyncio
async def test_review_revise_fails_closed_when_unresolved_remains_after_budget() -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft(session, locale="en", unresolved=True)
        invalid = _with_unresolved(_draft_payload(fixture.writer_input, "en"))
        model = FakeWriterModel([invalid])

        with pytest.raises(
            WriterGenerationError,
            match="review_revise_model_output_invalid",
        ):
            await _revise(session, fixture, source, model, max_attempts=2)

        drafts = list(
            (
                await session.scalars(
                    select(Artifact).where(
                        Artifact.run_id == fixture.writer_input.writer_run.id,
                        Artifact.artifact_type == "journal_draft",
                    )
                )
            ).all()
        )
        assert model.calls == 2
        assert [artifact.id for artifact in drafts] == [source.artifact.id]


@pytest.mark.asyncio
async def test_review_revise_support_drift_fails_closed() -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft(session, locale="en", unresolved=True)
        invalid = _draft_payload(fixture.writer_input, "en")
        sections = cast(list[object], invalid["sections"])
        first = cast(dict[str, object], sections[0])
        first["evidence_refs"] = ["00000000-0000-0000-0000-000000000000"]
        model = FakeWriterModel([invalid])

        with pytest.raises(
            WriterGenerationError,
            match="review_revise_model_output_invalid",
        ):
            await _revise(session, fixture, source, model, max_attempts=1)
        assert model.calls == 1


@pytest.mark.asyncio
async def test_review_revise_bridge_uses_locale_registry_and_review_task_key() -> None:
    async with isolated_session() as session:
        fixture, source = await _source_draft(session, locale="en", unresolved=True)
        review_input = await _review_input(session, fixture, source)
        config = review_revise_registry_config("en")
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
            run_id=fixture.writer_input.writer_run.id,
            step_key=config.task_key,
            attempt=1,
            status="running",
            input_artifact_refs_json=[
                str(source.artifact.id),
                str(fixture.writer_input.handoff_artifact.id),
                str(fixture.outline_result.artifact.id),
            ],
        )
        session.add(step)
        await session.flush()
        manifest = await build_context_manifest(
            session,
            run_id=fixture.writer_input.writer_run.id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                evidence_set_id=fixture.outline_fixture.bundle.evidence_set_id,
                originality_pack_id=fixture.outline_fixture.bundle.originality_pack_id,
            ),
        )
        route_settings = {
            "models": {"angle": {"route": "agent_angle"}},
            "model_routes": {
                "agent_angle": {"provider": "codex_cli", "model": "test-model"}
            },
        }
        snapshot = SettingsSnapshot(
            id=fixture.writer_input.writer_run.settings_snapshot_id,
            project_id=fixture.writer_input.writer_run.project_id,
            resolved_settings_json=route_settings,
            source_version_refs_json=["review-revise-test"],
            content_hash=settings_hash(route_settings),
        )
        revised_payload = _draft_payload(fixture.writer_input, "en")
        fake = FakeWriterRunner(revised_payload)
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", fake)
        port = await create_cli_review_revise_model_port(
            session,
            run_id=fixture.writer_input.writer_run.id,
            settings_snapshot=snapshot,
            context_manifest_id=manifest.id,
            runner_registry=registry,
            locale="en",
        )
        result = await port.generate(input_bundle=review_input.model_input, attempt=1)

        assert result == revised_payload
        assert len(fake.requests) == 1
        request = fake.requests[0]
        assert request.provider == "codex_cli"
        assert request.model == "test-model"
        assert set(request.working_context) == {"review_revise_model_input"}
        context = cast(
            dict[str, object],
            request.working_context["review_revise_model_input"],
        )
        assert cast(dict[str, object], context["source_draft"])["locale"] == "en"
        serialized = json.dumps(context, ensure_ascii=False, sort_keys=True)
        assert "other_locale_draft" not in serialized
        assert "translation_source" not in serialized

        call = await session.scalar(
            select(ModelCall).where(
                ModelCall.run_id == fixture.writer_input.writer_run.id,
                ModelCall.task_key == config.task_key,
            )
        )
        assert call is not None
        assert call.status == "completed"
        assert call.runtime_metadata_json is not None
        assert call.runtime_metadata_json["route_reuse"] == REVIEW_REVISE_ROUTE_TASK_KEY
        assert call.runtime_metadata_json["stage"] == "review_revise"
        assert call.runtime_metadata_json["independent_locale_revision"] is True
