from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_assertion_audit import (
    _passing_output,
    isolated_session,
)
from test_ce05_writer import (
    FakeWriterModel,
    FakeWriterRunner,
    _draft_payload,
    _generate_draft,
    _writer_fixture,
)

import app.modules.content_engine.journal.post_audit_revision as revision_module
import app.modules.content_engine.journal.post_audit_revision_agent_bridge as revision_bridge
import scripts.post_audit_revision_real_o4_en as revision_cli
from app.modules.content_engine.journal.assertion_audit import (
    _summary,
    load_assertion_audit_input,
    validate_assertion_audit_output,
)
from app.modules.content_engine.journal.post_audit_revision import (
    POST_AUDIT_REVISION_GENERATOR_VERSION,
    PostAuditRevisionGenerator,
    load_post_audit_revision_input,
    validate_post_audit_revision_output,
)
from app.modules.content_engine.journal.post_audit_revision_agent_bridge import (
    create_cli_post_audit_revision_model_port,
    post_audit_revision_registry_config,
)
from app.modules.content_engine.journal.writer import _canonical_hash, persist_journal_draft
from app.modules.content_engine.models import (
    PromptDefinition,
    RecipeDefinition,
    SettingsSnapshot,
)
from app.modules.harness.agent_runner import AgentRunnerRegistry
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
from app.modules.harness.persistence import RUN_TRANSITIONS, transition_run, transition_step_run
from app.modules.harness.runtime import ContextInputs, build_context_manifest
from app.modules.system.settings_service import settings_hash

TARGET_REPLACEMENTS = {
    "lead:1": (
        "Treat the number as one part of your decision, and examine the work and its "
        "context before deciding."
    ),
    "section:s1:1": (
        "Use the number as a starting point for questions, not as a verdict."
    ),
    "section:s1:3": (
        "Treat that context as background for your questions rather than a verdict."
    ),
    "section:s1:4": (
        "Keep this checklist as guidance for your questions, not a verdict about the work."
    ),
    "section:s2:2": (
        "Use these questions to ask for context rather than to calculate a price."
    ),
}
TARGET_SOURCE_TEXTS = {
    "lead:1": "You cannot tell whether an original artwork is fairly priced from the number alone.",
    "section:s1:1": "Prices are context-dependent.",
    "section:s1:3": "That helps explain why the price alone is not an objective answer.",
    "section:s1:4": (
        "It does not establish that a particular artwork is fairly or unfairly priced, "
        "and price alone "
        "does not prove quality, importance or investment value."
    ),
    "section:s2:2": (
        "These questions invite useful explanation without turning the conversation "
        "into a pricing formula."
    ),
}


def _patch_test_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    types = {
        "lead:1": ("fact", "critical"),
        "section:s1:1": ("fact", "critical"),
        "section:s1:3": ("interpretation", "medium"),
        "section:s1:4": ("fact", "critical"),
        "section:s2:2": ("interpretation", "medium"),
    }
    findings = tuple(
        (
            segment_id,
            TARGET_SOURCE_TEXTS[segment_id],
            assertion_type,
            severity,
        )
        for segment_id, (assertion_type, severity) in types.items()
    )
    monkeypatch.setattr(revision_module, "_TARGET_FINDINGS", findings)
    monkeypatch.setattr(revision_module, "_TARGET_IDS", tuple(item[0] for item in findings))


async def _fixture_with_exact_targets(
    session: AsyncSession,
) -> tuple[object, Artifact, Artifact]:
    fixture = await _writer_fixture(session, locale="en")
    outline = fixture.outline_result.artifact
    draft_payload = _draft_payload(fixture.writer_input, "en")
    draft_payload["lead_markdown"] = (
        "You cannot tell whether an original artwork is fairly priced from the number alone. "
        "Before deciding, check the specific work and the available context."
    )
    sections = cast(list[object], draft_payload["sections"])
    section_bodies = {
        "s1": (
            "Prices are context-dependent. Asked prices and amounts offered can reflect "
            "the personal "
            "interests of both the seller and the purchaser, as well as market trends. "
            "That helps explain why the price alone is not an objective answer. "
            "It does not establish that a particular artwork is fairly or unfairly priced, "
            "and price alone "
            "does not prove quality, importance or investment value."
        ),
        "s2": (
            "Ask what special conditions or circumstances may apply to the work. "
            "These questions invite useful explanation without turning the conversation "
            "into a pricing formula."
        ),
        "s3": "Take your time and ask before deciding.",
    }
    for raw_section in sections:
        section = cast(dict[str, object], raw_section)
        section["body_markdown"] = section_bodies[cast(str, section["section_id"])]
    draft_v1 = await _generate_draft(
        session,
        fixture,
        FakeWriterModel([draft_payload]),
    )
    draft_v2 = await persist_journal_draft(
        session,
        writer_input=fixture.writer_input,
        draft=draft_v1.draft,
        provider="fixture-provider",
        model="fixture-model",
        model_calls=1,
        prompt_version=fixture.prompt_version,
        recipe_version=fixture.recipe_version,
        context_manifest=fixture.manifest,
        generator_version="fixture.journal_review_revise.v1",
    )
    await transition_run(
        session,
        run_id=fixture.writer_input.writer_run.id,
        status="running",
    )
    await transition_run(
        session,
        run_id=fixture.writer_input.writer_run.id,
        status="waiting_approval",
    )
    await session.flush()
    return fixture, draft_v2, outline


async def _failed_audit_fixture(
    session: AsyncSession,
) -> tuple[object, Artifact, Artifact, QualityEvaluation]:
    fixture, source, outline = await _fixture_with_exact_targets(session)
    audit_input = await load_assertion_audit_input(
        session,
        writer_run_id=fixture.writer_input.writer_run.id,
        revised_draft_artifact_id=source.id,
        expected_revised_draft_version=source.version,
        expected_revised_draft_hash=source.content_hash,
        outline_artifact_id=outline.id,
        expected_outline_version=outline.version,
        expected_outline_hash=outline.content_hash,
        locale="en",
    )
    output = _passing_output(audit_input)
    target_types = {
        "lead:1": ("fact", "critical"),
        "section:s1:1": ("fact", "critical"),
        "section:s1:3": ("interpretation", "medium"),
        "section:s1:4": ("fact", "critical"),
        "section:s2:2": ("interpretation", "medium"),
    }
    for raw_segment in cast(list[object], output["segments"]):
        segment = cast(dict[str, object], raw_segment)
        if segment["segment_id"] not in target_types:
            continue
        assertion_type, severity = target_types[cast(str, segment["segment_id"])]
        segment["assertions"] = [
            {
                "assertion_text": segment["source_text"],
                "assertion_type": assertion_type,
                "support_status": "unsupported",
                "severity": severity,
                "evidence_refs": [],
                "originality_refs": [],
                "rationale": "Persisted failed audit fixture.",
            }
        ]
    # Use the audit validator once to obtain the canonical persisted segment shape/summary.
    audited = validate_assertion_audit_output(output, audit_input=audit_input)
    summary = _summary(audited)
    settings = await session.get(
        SettingsSnapshot,
        fixture.writer_input.writer_run.settings_snapshot_id,
    )
    assert settings is not None
    eval_run = ContentRun(
        project_id=fixture.writer_input.writer_run.project_id,
        content_case_id=fixture.writer_input.writer_run.content_case_id,
        locale_variant_id=fixture.writer_input.locale_variant.id,
        content_item_id=None,
        run_mode="eval",
        status="completed",
        current_step="assertion_audit_en",
        settings_snapshot_id=settings.id,
        started_at=utc_now(),
        completed_at=utc_now(),
    )
    session.add(eval_run)
    await session.flush()
    audit_payload: dict[str, object] = {
        "schema_version": 1,
        "artifact_type": "assertion_audit",
        "locale": "en",
        "generation_fingerprint": "fixture-failed-audit",
        "source_draft": {
            "id": str(source.id),
            "version": source.version,
            "content_hash": source.content_hash,
        },
        "source_writer_run_id": str(fixture.writer_input.writer_run.id),
        "journal_outline": {
            "id": str(outline.id),
            "version": outline.version,
            "content_hash": outline.content_hash,
        },
        "evidence_set": {
            "id": str(fixture.outline_fixture.bundle.evidence_set_id),
            "version": fixture.outline_fixture.bundle.evidence_set_version,
            "content_hash": fixture.outline_fixture.bundle.evidence_set_hash,
        },
        "originality_pack": {
            "id": str(fixture.outline_fixture.bundle.originality_pack_id),
            "snapshot_hash": fixture.outline_fixture.bundle.originality_pack_hash,
        },
        "model_input": {"content_hash": "a" * 64},
        "execution_context": {"context_manifest_id": str(fixture.manifest.id)},
        "generator": {"version": "ce05.journal_assertion_audit.v3", "schema_version": 1},
        "model": {"provider": "fixture-provider", "model": "fixture-model", "model_calls": 1},
        "segments": [segment.to_dict() for segment in audited],
        "summary": summary,
    }
    audit_artifact = Artifact(
        run_id=eval_run.id,
        artifact_type="assertion_audit",
        locale="en",
        version=1,
        content_json=audit_payload,
        content_hash=_canonical_hash(audit_payload),
    )
    session.add(audit_artifact)
    await session.flush()
    quality = QualityEvaluation(
        run_id=eval_run.id,
        artifact_id=audit_artifact.id,
        evaluator_key="assertion_audit_hard_gate",
        evaluator_version="ce05.assertion_audit.hard_gate.v3",
        evaluator_type="deterministic",
        result="fail",
        severity="critical",
        findings_json={
            "source_draft_id": str(source.id),
            "source_draft_hash": source.content_hash,
            "assertion_audit_artifact_id": str(audit_artifact.id),
            "assertion_audit_hash": audit_artifact.content_hash,
            **summary,
        },
    )
    session.add(quality)
    await session.flush()
    return fixture, source, audit_artifact, quality


class FakeRevisionModel:
    def __init__(self, output: object) -> None:
        self.output = output
        self.calls = 0

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        del input_bundle, attempt
        self.calls += 1
        return self.output


async def _ensure_revision_registry(session: AsyncSession) -> None:
    config = post_audit_revision_registry_config("en")
    prompt = await session.scalar(
        select(PromptDefinition).where(
            PromptDefinition.prompt_key == config.prompt_key,
            PromptDefinition.version == 1,
        )
    )
    if prompt is None:
        session.add(
            PromptDefinition(
                prompt_key=config.prompt_key,
                version=1,
                purpose="Test bounded English post-audit replacements.",
                body="Return exactly the bounded replacement payload.",
                input_contract_json={"required": []},
                output_schema_json={"type": "object"},
                status="active",
                change_reason="Focused bridge test.",
                approved_by="founder",
            )
        )
    recipe = await session.scalar(
        select(RecipeDefinition).where(
            RecipeDefinition.recipe_key == config.recipe_key,
            RecipeDefinition.version == 1,
        )
    )
    if recipe is None:
        session.add(
            RecipeDefinition(
                recipe_key=config.recipe_key,
                version=1,
                selector_json={
                    "content_type": "journal",
                    "locale": "en",
                    "task": config.task_key,
                },
                recipe_json={"strategy": "bounded_exact_five_sentence_replacements"},
                status="active",
                approved_by="founder",
            )
        )
    await session.flush()


@pytest.mark.asyncio(loop_scope="module")
async def test_post_audit_revision_binds_exact_findings_and_reuses_v3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _patch_test_targets(monkeypatch)
        fixture, source, audit, quality = await _failed_audit_fixture(session)
        revision_input = await load_post_audit_revision_input(
            session,
            writer_run_id=fixture.writer_input.writer_run.id,
            source_draft_artifact_id=source.id,
            expected_source_draft_version=2,
            expected_source_draft_hash=source.content_hash,
            failed_audit_artifact_id=audit.id,
            expected_failed_audit_version=1,
            expected_failed_audit_hash=audit.content_hash,
            failed_quality_evaluation_id=quality.id,
            outline_artifact_id=fixture.outline_result.artifact.id,
            expected_outline_version=fixture.outline_result.artifact.version,
            expected_outline_hash=fixture.outline_result.artifact.content_hash,
        )
        assert [finding.segment_id for finding in revision_input.findings] == list(
            TARGET_REPLACEMENTS
        )
        assert revision_input.model_input["target_findings_hash"] == revision_input.findings_hash
        source_snapshot = copy.deepcopy(source.content_json)
        model = FakeRevisionModel(
            {
                "locale": "en",
                "revisions": [
                    {
                        "segment_id": segment_id,
                        "source_text": next(
                            finding.assertion_text
                            for finding in revision_input.findings
                            if finding.segment_id == segment_id
                        ),
                        "replacement_text": replacement,
                    }
                    for segment_id, replacement in TARGET_REPLACEMENTS.items()
                ],
            }
        )
        revision_step = StepRun(
            run_id=fixture.writer_input.writer_run.id,
            step_key="post_audit_revise_en",
            attempt=1,
            status="pending",
            input_artifact_refs_json=[str(source.id), str(audit.id)],
        )
        session.add(revision_step)
        await session.flush()
        manifest = await build_context_manifest(
            session,
            run_id=fixture.writer_input.writer_run.id,
            step_run_id=revision_step.id,
            inputs=ContextInputs(
                prompt_version=fixture.prompt_version,
                recipe_version=fixture.recipe_version,
                evidence_set_id=fixture.outline_fixture.bundle.evidence_set_id,
                originality_pack_id=fixture.outline_fixture.bundle.originality_pack_id,
                tool_result_refs=(),
            ),
        )
        await transition_run(
            session,
            run_id=fixture.writer_input.writer_run.id,
            status="running",
        )
        await transition_step_run(session, step_run_id=revision_step.id, status="running")
        first = await PostAuditRevisionGenerator(max_attempts=1).revise_draft(
            session,
            revision_input=revision_input,
            model=model,
            provider="fixture-provider",
            model_name="fixture-model",
            context_manifest=manifest,
            prompt_version=fixture.prompt_version,
            recipe_version=fixture.recipe_version,
        )
        await transition_step_run(session, step_run_id=revision_step.id, status="completed")
        await transition_run(
            session,
            run_id=fixture.writer_input.writer_run.id,
            status="waiting_approval",
        )
        second = await PostAuditRevisionGenerator(max_attempts=1).revise_draft(
            session,
            revision_input=revision_input,
            model=model,
            provider="fixture-provider",
            model_name="fixture-model",
            context_manifest=manifest,
            prompt_version=fixture.prompt_version,
            recipe_version=fixture.recipe_version,
        )
        assert first.reused is False
        assert first.model_attempts == 1
        assert second.reused is True
        assert second.model_attempts == 0
        assert second.artifact.id == first.artifact.id
        assert first.artifact.version == 3
        assert (
            first.artifact.content_json["generator"]["version"]
            == POST_AUDIT_REVISION_GENERATOR_VERSION
        )
        assert (
            first.artifact.content_json["post_audit_revision"]["failed_assertion_audit"]["id"]
            == str(audit.id)
        )
        assert (
            first.artifact.content_json["post_audit_revision"]["failed_quality_evaluation"]["id"]
            == str(quality.id)
        )
        assert source.content_json == source_snapshot
        assert model.calls == 1
        assert first.draft.lead_markdown.startswith(TARGET_REPLACEMENTS["lead:1"])
        assert first.draft.sections[0].section_id == "s1"
        assert (
            list(first.draft.sections[0].evidence_refs)
            == source.content_json["draft"]["sections"][0]["evidence_refs"]
        )


@pytest.mark.asyncio(loop_scope="module")
async def test_post_audit_revision_bridge_owns_call_by_new_step_without_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _patch_test_targets(monkeypatch)
        fixture, source, audit, quality = await _failed_audit_fixture(session)
        revision_input = await load_post_audit_revision_input(
            session,
            writer_run_id=fixture.writer_input.writer_run.id,
            source_draft_artifact_id=source.id,
            expected_source_draft_version=2,
            expected_source_draft_hash=source.content_hash,
            failed_audit_artifact_id=audit.id,
            expected_failed_audit_version=1,
            expected_failed_audit_hash=audit.content_hash,
            failed_quality_evaluation_id=quality.id,
            outline_artifact_id=fixture.outline_result.artifact.id,
            expected_outline_version=fixture.outline_result.artifact.version,
            expected_outline_hash=fixture.outline_result.artifact.content_hash,
        )
        await _ensure_revision_registry(session)
        config = post_audit_revision_registry_config("en")
        step = StepRun(
            run_id=fixture.writer_input.writer_run.id,
            step_key=config.task_key,
            attempt=1,
            status="running",
            input_artifact_refs_json=[
                str(source.id),
                str(audit.id),
                str(fixture.writer_input.handoff_artifact.id),
                str(fixture.outline_result.artifact.id),
            ],
        )
        session.add(step)
        await session.flush()
        prompt_version = f"{config.prompt_key}:v1"
        recipe_version = f"{config.recipe_key}:v1"
        manifest = await build_context_manifest(
            session,
            run_id=fixture.writer_input.writer_run.id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                evidence_set_id=fixture.outline_fixture.bundle.evidence_set_id,
                originality_pack_id=fixture.outline_fixture.bundle.originality_pack_id,
                tool_result_refs=(),
            ),
        )
        route_settings = {
            "models": {"angle": {"route": "agent_angle"}},
            "model_routes": {
                "agent_angle": {"provider": "codex_cli", "model": "test-model"}
            },
        }
        settings = SettingsSnapshot(
            id=fixture.writer_input.writer_run.settings_snapshot_id,
            project_id=fixture.writer_input.writer_run.project_id,
            resolved_settings_json=route_settings,
            source_version_refs_json=["post-audit-revision-test"],
            content_hash=settings_hash(route_settings),
        )
        runner = FakeWriterRunner({"locale": "en", "revisions": []})
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", runner)
        port = await create_cli_post_audit_revision_model_port(
            session,
            run_id=fixture.writer_input.writer_run.id,
            settings_snapshot=settings,
            context_manifest_id=manifest.id,
            runner_registry=registry,
        )
        with pytest.raises(Exception, match="post_audit_revision_model_input_not_sanitized"):
            await port.generate(
                input_bundle={**revision_input.model_input, "sibling_draft": {"locale": "vi"}},
                attempt=1,
            )
        assert runner.requests == []
        result = await port.generate(input_bundle=revision_input.model_input, attempt=1)

        assert result == {"locale": "en", "revisions": []}
        assert len(runner.requests) == 1
        request = runner.requests[0]
        assert request.provider == "codex_cli"
        assert request.model == "test-model"
        assert set(request.working_context) == {"post_audit_revision_model_input"}
        call = await session.scalar(
            select(ModelCall).where(
                ModelCall.run_id == fixture.writer_input.writer_run.id,
                ModelCall.task_key == config.task_key,
            )
        )
        assert call is not None
        assert call.step_run_id == step.id
        assert call.context_manifest_id == manifest.id
        assert call.status == "completed"
        assert await session.scalar(
            select(ToolCall).where(ToolCall.run_id == fixture.writer_input.writer_run.id)
        ) is None


@pytest.mark.asyncio(loop_scope="module")
async def test_post_audit_revision_requires_exact_model_target_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _patch_test_targets(monkeypatch)
        fixture, source, audit, quality = await _failed_audit_fixture(session)
        revision_input = await load_post_audit_revision_input(
            session,
            writer_run_id=fixture.writer_input.writer_run.id,
            source_draft_artifact_id=source.id,
            expected_source_draft_version=2,
            expected_source_draft_hash=source.content_hash,
            failed_audit_artifact_id=audit.id,
            expected_failed_audit_version=1,
            expected_failed_audit_hash=audit.content_hash,
            failed_quality_evaluation_id=quality.id,
            outline_artifact_id=fixture.outline_result.artifact.id,
            expected_outline_version=fixture.outline_result.artifact.version,
            expected_outline_hash=fixture.outline_result.artifact.content_hash,
        )
        valid = [
            {
                "segment_id": segment_id,
                "source_text": next(
                    finding.assertion_text
                    for finding in revision_input.findings
                    if finding.segment_id == segment_id
                ),
                "replacement_text": replacement,
            }
            for segment_id, replacement in TARGET_REPLACEMENTS.items()
        ]
        with pytest.raises(Exception, match="post_audit_revision_target_count_invalid"):
            validate_post_audit_revision_output(
                {"locale": "en", "revisions": valid[:-1]},
                revision_input=revision_input,
            )
        with pytest.raises(Exception, match="post_audit_revision_target_ids_invalid"):
            validate_post_audit_revision_output(
                {
                    "locale": "en",
                    "revisions": [*valid[:-1], {**valid[0], "segment_id": "section:extra:1"}],
                },
                revision_input=revision_input,
            )


@pytest.mark.asyncio(loop_scope="module")
async def test_post_audit_revision_requires_exact_persisted_audit_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _patch_test_targets(monkeypatch)
        fixture, source, audit, quality = await _failed_audit_fixture(session)
        with pytest.raises(Exception, match="post_audit_failed_audit_snapshot_mismatch"):
            await load_post_audit_revision_input(
                session,
                writer_run_id=fixture.writer_input.writer_run.id,
                source_draft_artifact_id=source.id,
                expected_source_draft_version=2,
                expected_source_draft_hash=source.content_hash,
                failed_audit_artifact_id=audit.id,
                expected_failed_audit_version=1,
                expected_failed_audit_hash="0" * 64,
                failed_quality_evaluation_id=quality.id,
                outline_artifact_id=fixture.outline_result.artifact.id,
                expected_outline_version=fixture.outline_result.artifact.version,
                expected_outline_hash=fixture.outline_result.artifact.content_hash,
            )


def test_post_audit_revision_rejects_missing_or_extra_target_ids() -> None:
    payload = {"locale": "en", "revisions": []}
    with pytest.raises(Exception, match="post_audit_revision_target_count_invalid"):
        validate_post_audit_revision_output(payload, revision_input=cast(object, None))


@pytest.mark.asyncio(loop_scope="module")
async def test_post_audit_revision_cli_failure_retry_and_exact_reuse(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async with isolated_session() as session:
        _patch_test_targets(monkeypatch)
        fixture, source, audit, quality = await _failed_audit_fixture(session)
        await _ensure_revision_registry(session)
        valid_output = {
            "locale": "en",
            "revisions": [
                {
                    "segment_id": segment_id,
                    "source_text": TARGET_SOURCE_TEXTS[segment_id],
                    "replacement_text": replacement,
                }
                for segment_id, replacement in TARGET_REPLACEMENTS.items()
            ],
        }
        invalid_runner = FakeWriterRunner({"locale": "en", "revisions": []})
        valid_runner = FakeWriterRunner(valid_output)

        class _SessionContext:
            async def __aenter__(self) -> AsyncSession:
                return session

            async def __aexit__(self, *args: object) -> None:
                return None

        async def _no_commit() -> None:
            return None

        monkeypatch.setattr(session, "commit", _no_commit)
        monkeypatch.setattr(revision_cli, "SessionLocal", lambda: _SessionContext())

        class _FakeRouter:
            def resolve(self, *, task_key: str, settings_snapshot: SettingsSnapshot) -> object:
                del task_key, settings_snapshot
                return SimpleNamespace(
                    primary=SimpleNamespace(provider="codex_cli", model="test-model")
                )

        monkeypatch.setattr(revision_cli, "SettingsModelRouter", _FakeRouter)
        monkeypatch.setattr(revision_bridge, "SettingsModelRouter", _FakeRouter)

        args = SimpleNamespace(
            writer_run_id=fixture.writer_input.writer_run.id,
            source_draft_artifact_id=source.id,
            source_draft_version=2,
            source_draft_hash=source.content_hash,
            failed_audit_artifact_id=audit.id,
            failed_audit_version=1,
            failed_audit_hash=audit.content_hash,
            failed_quality_evaluation_id=quality.id,
            outline_artifact_id=fixture.outline_result.artifact.id,
            outline_artifact_version=fixture.outline_result.artifact.version,
            outline_artifact_hash=fixture.outline_result.artifact.content_hash,
            expected_provider="codex_cli",
            expected_model="test-model",
        )
        monkeypatch.setattr(revision_cli, "_runner", lambda provider: invalid_runner)
        with pytest.raises(Exception, match="post_audit_revision_model_output_invalid"):
            await revision_cli._run(args)
        capsys.readouterr()

        run = await session.get(ContentRun, fixture.writer_input.writer_run.id)
        assert run is not None
        assert run.status == "waiting_approval"
        assert run.status != "failed"
        steps = list(
            (
                await session.scalars(
                    select(StepRun)
                    .where(
                        StepRun.run_id == run.id,
                        StepRun.step_key == "post_audit_revise_en",
                    )
                    .order_by(StepRun.attempt)
                )
            ).all()
        )
        assert len(steps) == 1
        assert steps[0].attempt == 1
        assert steps[0].status == "failed"
        assert await session.scalar(
            select(func.count())
            .select_from(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.artifact_type == "journal_draft",
                Artifact.version == 3,
            )
        ) == 0

        monkeypatch.setattr(revision_cli, "_runner", lambda provider: valid_runner)
        await revision_cli._run(args)
        retry_output = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert retry_output["step_attempt"] == 2
        assert retry_output["step_status"] == "completed"
        assert retry_output["writer_run_status"] == "waiting_approval"
        assert retry_output["reused"] is False
        assert retry_output["model_attempts"] == 1

        run = await session.get(ContentRun, run.id)
        assert run is not None
        assert run.status == "waiting_approval"
        steps = list(
            (
                await session.scalars(
                    select(StepRun)
                    .where(
                        StepRun.run_id == run.id,
                        StepRun.step_key == "post_audit_revise_en",
                    )
                    .order_by(StepRun.attempt)
                )
            ).all()
        )
        assert [(step.attempt, step.status) for step in steps] == [(1, "failed"), (2, "completed")]
        v3 = await session.scalar(
            select(Artifact).where(
                Artifact.run_id == run.id,
                Artifact.artifact_type == "journal_draft",
                Artifact.version == 3,
            )
        )
        assert v3 is not None
        assert v3.step_run_id == steps[1].id
        assert len(valid_runner.requests) == 1

        counts_before = {
            "steps": await session.scalar(
                select(func.count()).select_from(StepRun).where(StepRun.run_id == run.id)
            ),
            "manifests": await session.scalar(
                select(func.count())
                .select_from(ContextManifest)
                .where(ContextManifest.run_id == run.id)
            ),
            "model_calls": await session.scalar(
                select(func.count()).select_from(ModelCall).where(ModelCall.run_id == run.id)
            ),
            "drafts": await session.scalar(
                select(func.count()).select_from(Artifact).where(
                    Artifact.run_id == run.id,
                    Artifact.artifact_type == "journal_draft",
                )
            ),
            "tool_calls": await session.scalar(
                select(func.count()).select_from(ToolCall).where(ToolCall.run_id == run.id)
            ),
        }
        await revision_cli._run(args)
        reuse_output = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert reuse_output["step_attempt"] == 2
        assert reuse_output["step_run_id"] == str(steps[1].id)
        assert reuse_output["reused"] is True
        assert reuse_output["model_attempts"] == 0
        assert reuse_output["revised_draft_artifact_id"] == str(v3.id)
        assert len(valid_runner.requests) == 1
        counts_after = {
            "steps": await session.scalar(
                select(func.count()).select_from(StepRun).where(StepRun.run_id == run.id)
            ),
            "manifests": await session.scalar(
                select(func.count())
                .select_from(ContextManifest)
                .where(ContextManifest.run_id == run.id)
            ),
            "model_calls": await session.scalar(
                select(func.count()).select_from(ModelCall).where(ModelCall.run_id == run.id)
            ),
            "drafts": await session.scalar(
                select(func.count()).select_from(Artifact).where(
                    Artifact.run_id == run.id,
                    Artifact.artifact_type == "journal_draft",
                )
            ),
            "tool_calls": await session.scalar(
                select(func.count()).select_from(ToolCall).where(ToolCall.run_id == run.id)
            ),
        }
        assert counts_after == counts_before


def test_post_audit_revision_preserves_terminal_failed_run_transition() -> None:
    assert RUN_TRANSITIONS["failed"] == set()
    assert RUN_TRANSITIONS["completed"] == set()
