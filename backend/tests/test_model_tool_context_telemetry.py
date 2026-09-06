from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    LocaleVariant,
    NeedHypothesis,
    Project,
    SettingsSnapshot,
)
from app.modules.harness.models import Artifact, ContentRun, StepRun
from app.modules.harness.persistence import load_budget_usage
from app.modules.harness.runtime import (
    ContextInputs,
    ModelCandidate,
    ModelClientRegistry,
    ModelRequest,
    ModelResponse,
    RuntimeConfigurationError,
    RuntimeStateError,
    SettingsModelRouter,
    ToolRegistry,
    ToolRequest,
    ToolResponse,
    build_context_manifest,
    complete_model_call,
    complete_tool_call,
    fail_model_call,
    fail_tool_call,
    request_fingerprint,
    start_model_call,
    start_tool_call,
)
from app.modules.knowledge.models import EvidenceSet, OriginalityPack
from app.modules.knowledge.persistence import content_hash


class FakeModelClient:
    async def generate(self, request: ModelRequest) -> ModelResponse:
        assert request.context_manifest_id
        return ModelResponse(
            content="synthetic output",
            input_tokens=50,
            output_tokens=80,
            cost=Decimal("0.12"),
            latency_ms=25,
            finish_reason="stop",
        )


class FakeToolAdapter:
    async def execute(self, request: ToolRequest) -> ToolResponse:
        assert request.payload
        return ToolResponse(result_ref="artifact://tool-result", latency_ms=12)


async def create_runtime_run(
    session: AsyncSession,
) -> tuple[ContentRun, StepRun, SettingsSnapshot, EvidenceSet, OriginalityPack]:
    project = (
        await session.execute(select(Project).where(Project.slug == "motgu"))
    ).scalar_one()
    suffix = uuid4().hex[:8]
    hypothesis = NeedHypothesis(
        project_id=project.id,
        type="problem",
        statement=f"CE03 PR-C synthetic {suffix}",
        audience_scope="test reader",
        situation="runtime test",
        origin="FOUNDER",
    )
    session.add(hypothesis)
    await session.flush()
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale="en",
        reader="test reader",
        situation="runtime test",
        need="Traceable model context",
        question="Can runtime be reproduced?",
        intent="learn",
        promise="Keep model context traceable",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Synthetic runtime proof",
        next_discovery_step="None",
        decision="CREATE",
        priority="NOW",
        reasons_json=["test"],
        suggested_content_type="journal",
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=hypothesis.id,
        content_opportunity_id=opportunity.id,
        desired_action="Continue",
        content_hypothesis="Traceable context improves reproducibility",
        originality_statement="Synthetic only",
        reader_before="Uncertain",
        reader_after="Certain",
    )
    session.add(content_case)
    await session.flush()
    locale_variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="primary",
        primary_question="Can runtime be reproduced?",
        primary_intent="learn",
    )
    settings = {
        "models": {"draft": {"route": "writer"}},
        "model_routes": {
            "writer": {
                "provider": "provider-a",
                "model": "writer-v1",
                "fallbacks": [
                    {"provider": "provider-b", "model": "writer-v2"}
                ],
            }
        },
    }
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json=settings,
        source_version_refs_json=["settings:test"],
        content_hash=content_hash(f"settings:{suffix}"),
    )
    session.add_all([locale_variant, snapshot])
    await session.flush()
    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=locale_variant.id,
        run_mode="create",
        status="running",
        current_step="draft",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    step = StepRun(
        run_id=run.id,
        step_key="draft",
        attempt=1,
        status="running",
        started_at=datetime.now(UTC),
    )
    evidence_set = EvidenceSet(
        project_id=project.id,
        content_case_id=content_case.id,
        version=1,
        evidence_ids_json=[],
        content_hash=content_hash(f"evidence:{suffix}"),
        status="draft",
    )
    originality_pack = OriginalityPack(
        content_case_id=content_case.id,
        item_refs_json=[{"kind": "motgu_fact", "ref": "synthetic"}],
        summary="Synthetic originality",
        status="approved",
        approved_at=datetime.now(UTC),
    )
    session.add_all([step, evidence_set, originality_pack])
    await session.flush()
    return run, step, snapshot, evidence_set, originality_pack


def test_model_router_and_registries_are_provider_neutral() -> None:
    snapshot = SettingsSnapshot(
        project_id=uuid4(),
        resolved_settings_json={
            "models": {"draft": {"route": "writer"}},
            "model_routes": {
                "writer": {
                    "provider": "provider-a",
                    "model": "writer-v1",
                    "fallbacks": [
                        {"provider": "provider-b", "model": "writer-v2"}
                    ],
                }
            },
        },
        source_version_refs_json=[],
        content_hash="x" * 64,
    )
    route = SettingsModelRouter().resolve(task_key="draft", settings_snapshot=snapshot)
    assert route.primary == ModelCandidate(provider="provider-a", model="writer-v1")
    assert route.fallbacks == (
        ModelCandidate(provider="provider-b", model="writer-v2"),
    )

    model_registry = ModelClientRegistry()
    client = FakeModelClient()
    model_registry.register("provider-a", client)
    assert model_registry.get("provider-a") is client

    tool_registry = ToolRegistry()
    adapter = FakeToolAdapter()
    tool_registry.register("search", adapter)
    assert tool_registry.get("search") is adapter

    with pytest.raises(RuntimeConfigurationError, match="no model client"):
        model_registry.get("missing")
    with pytest.raises(RuntimeConfigurationError, match="no tool adapter"):
        tool_registry.get("missing")


@pytest.mark.asyncio
async def test_context_manifest_is_reproducible_and_tracks_originality() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run, step, _, evidence_set, originality_pack = await create_runtime_run(
                session
            )
            inputs = ContextInputs(
                prompt_version="draft:1",
                recipe_version="journal:1",
                evidence_set_id=evidence_set.id,
                originality_pack_id=originality_pack.id,
                knowledge_chunk_refs=("chunk:1", "chunk:2"),
                golden_example_refs=("golden:1",),
                tool_result_refs=("tool:1",),
            )
            first = await build_context_manifest(
                session,
                run_id=run.id,
                step_run_id=step.id,
                inputs=inputs,
            )
            second = await build_context_manifest(
                session,
                run_id=run.id,
                step_run_id=step.id,
                inputs=inputs,
            )
            assert first.id != second.id
            assert first.content_hash == second.content_hash
            assert first.settings_snapshot_id == run.settings_snapshot_id
            assert first.evidence_set_id == evidence_set.id
            assert first.originality_pack_id == originality_pack.id
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_context_manifest_rejects_cross_case_originality_pack() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run, step, _, evidence_set, _ = await create_runtime_run(session)
            other_run, _, _, _, other_pack = await create_runtime_run(session)
            assert other_run.content_case_id != run.content_case_id
            with pytest.raises(RuntimeStateError, match="different ContentCase"):
                await build_context_manifest(
                    session,
                    run_id=run.id,
                    step_run_id=step.id,
                    inputs=ContextInputs(
                        prompt_version="draft:1",
                        recipe_version="journal:1",
                        evidence_set_id=evidence_set.id,
                        originality_pack_id=other_pack.id,
                    ),
                )
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_model_and_tool_telemetry_feed_existing_budget_ledger() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run, step, snapshot, evidence_set, originality_pack = await create_runtime_run(
                session
            )
            route = SettingsModelRouter().resolve(
                task_key="draft",
                settings_snapshot=snapshot,
            )
            manifest = await build_context_manifest(
                session,
                run_id=run.id,
                step_run_id=step.id,
                inputs=ContextInputs(
                    prompt_version="draft:1",
                    recipe_version="journal:1",
                    evidence_set_id=evidence_set.id,
                    originality_pack_id=originality_pack.id,
                ),
            )
            model_call = await start_model_call(
                session,
                run_id=run.id,
                step_run_id=step.id,
                context_manifest_id=manifest.id,
                task_key="draft",
                route=route.primary,
                purpose="synthetic draft",
                prompt_version="draft:1",
            )
            client = FakeModelClient()
            response = await client.generate(
                ModelRequest(
                    task_key="draft",
                    prompt="Synthetic prompt",
                    context_manifest_id=manifest.id,
                    output_schema={"type": "string"},
                )
            )
            artifact = Artifact(
                run_id=run.id,
                step_run_id=step.id,
                artifact_type="draft",
                locale="en",
                version=1,
                content_json={"text": response.content},
                content_hash=content_hash(response.content),
            )
            session.add(artifact)
            await session.flush()
            await complete_model_call(
                session,
                call_id=model_call.id,
                response=response,
                result_artifact_id=artifact.id,
            )

            tool_request = ToolRequest(
                tool_key="search",
                payload={"query": "synthetic query", "locale": "en"},
            )
            assert request_fingerprint(tool_request) == request_fingerprint(
                tool_request
            )
            tool_call = await start_tool_call(
                session,
                run_id=run.id,
                step_run_id=step.id,
                request=tool_request,
            )
            adapter = FakeToolAdapter()
            tool_response = await adapter.execute(tool_request)
            await complete_tool_call(
                session,
                call_id=tool_call.id,
                response=tool_response,
            )

            usage = await load_budget_usage(
                session,
                run_id=run.id,
                step_run_id=step.id,
            )
            assert usage.model_calls == 1
            assert usage.tool_calls == 1
            assert usage.output_tokens == 80
            assert usage.estimated_cost == Decimal("0.12")
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_failed_model_and_tool_calls_preserve_error_class() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            run, step, snapshot, evidence_set, originality_pack = await create_runtime_run(
                session
            )
            route = SettingsModelRouter().resolve(
                task_key="draft",
                settings_snapshot=snapshot,
            )
            manifest = await build_context_manifest(
                session,
                run_id=run.id,
                step_run_id=step.id,
                inputs=ContextInputs(
                    prompt_version="draft:1",
                    recipe_version="journal:1",
                    evidence_set_id=evidence_set.id,
                    originality_pack_id=originality_pack.id,
                ),
            )
            model_call = await start_model_call(
                session,
                run_id=run.id,
                step_run_id=step.id,
                context_manifest_id=manifest.id,
                task_key="draft",
                route=route.primary,
                purpose="synthetic failure",
                prompt_version="draft:1",
            )
            failed_model = await fail_model_call(
                session,
                call_id=model_call.id,
                error_class="provider_transient",
                latency_ms=9,
            )
            assert failed_model.status == "failed"
            assert failed_model.error_class == "provider_transient"

            tool_call = await start_tool_call(
                session,
                run_id=run.id,
                step_run_id=step.id,
                request=ToolRequest(tool_key="reader", payload={"url": "test"}),
                retry_count=1,
            )
            failed_tool = await fail_tool_call(
                session,
                call_id=tool_call.id,
                error_class="tool_invalid_response",
                latency_ms=6,
            )
            assert failed_tool.status == "failed"
            assert failed_tool.retry_count == 1
            assert failed_tool.error_class == "tool_invalid_response"
        finally:
            await session.close()
            await transaction.rollback()
