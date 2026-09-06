from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
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
from app.modules.harness.models import (
    Approval,
    Artifact,
    ContentRun,
    ContextManifest,
    ModelCall,
    QualityEvaluation,
    StepRun,
    ToolCall,
)
from app.modules.knowledge.models import EvidenceSet
from app.modules.knowledge.persistence import content_hash


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


async def create_run(session: AsyncSession) -> tuple[Project, ContentRun, SettingsSnapshot]:
    project = (await session.execute(select(Project).where(Project.slug == "motgu"))).scalar_one()
    suffix = uuid4().hex[:8]
    hypothesis = NeedHypothesis(
        project_id=project.id,
        type="problem",
        statement=f"Reader needs context {suffix}",
        audience_scope="art-curious reader",
        situation="Before visiting an artwork",
        origin="FOUNDER",
    )
    session.add(hypothesis)
    await session.flush()
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale="vi-VN",
        reader="art-curious reader",
        situation="Before visiting an artwork",
        need="Understand the work",
        question="What should I notice?",
        intent="learn",
        promise="Offer grounded context",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="A useful explanation",
        next_discovery_step="Review first-party material",
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
        desired_action="Look closer",
        content_hypothesis="Grounded context helps the reader look closer",
        originality_statement="Use a specific MOTGU detail",
        reader_before="Uncertain",
        reader_after="More attentive",
    )
    session.add(content_case)
    await session.flush()
    locale_variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="vi-VN",
        content_role="primary",
        primary_question="Tôi nên chú ý điều gì?",
        primary_intent="learn",
    )
    session.add(locale_variant)
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={"brand": {"voice": "warm"}},
        source_version_refs_json=["settings-version:test"],
        content_hash=content_hash("settings:test"),
    )
    session.add_all([snapshot])
    await session.flush()
    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=locale_variant.id,
        run_mode="create",
        status="running",
        current_step="outline",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    return project, run, snapshot


def artifact_row(run: ContentRun, version: int, step_run_id: UUID | None = None) -> Artifact:
    return Artifact(
        run_id=run.id,
        step_run_id=step_run_id,
        artifact_type="draft",
        locale="vi-VN",
        version=version,
        content_json={"version": version, "body": f"draft {version}"},
        content_hash=content_hash(f"draft:{version}"),
    )


@pytest.mark.asyncio
async def test_content_run_keeps_case_locale_and_settings_snapshot() -> None:
    async with isolated_session() as session:
        _, run, snapshot = await create_run(session)
        assert run.settings_snapshot_id == snapshot.id
        assert run.content_case_id is not None
        assert run.locale_variant_id is not None


@pytest.mark.asyncio
async def test_step_attempt_is_unique() -> None:
    async with isolated_session() as session:
        _, run, _ = await create_run(session)
        step = StepRun(
            run_id=run.id,
            step_key="outline",
            attempt=1,
            error_json={"class": "temporary"},
        )
        session.add(step)
        await session.flush()
        assert step.error_json == {"class": "temporary"}
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(StepRun(run_id=run.id, step_key="outline", attempt=1))
                await session.flush()


@pytest.mark.asyncio
async def test_artifact_is_append_only_and_v2_does_not_inherit_v1_approval() -> None:
    async with isolated_session() as session:
        _, run, _ = await create_run(session)
        first = artifact_row(run, 1)
        session.add(first)
        await session.flush()
        approval = Approval(
            run_id=run.id,
            step_key="draft",
            artifact_id=first.id,
            decision="approved",
            actor_id="reviewer-1",
        )
        session.add(approval)
        await session.flush()
        with pytest.raises(DBAPIError, match="artifact_is_immutable"):
            async with session.begin_nested():
                await session.execute(
                    update(Artifact)
                    .where(Artifact.id == first.id)
                    .values(content_json={"version": 99})
                )
        with pytest.raises(DBAPIError, match="artifact_is_immutable"):
            async with session.begin_nested():
                await session.delete(first)
                await session.flush()
        second = artifact_row(run, 2)
        session.add(second)
        await session.flush()
        stored_first = (
            await session.execute(select(Artifact).where(Artifact.id == first.id))
        ).scalar_one()
        assert stored_first.content_json == {"version": 1, "body": "draft 1"}
        assert second.version == 2
        assert (
            await session.execute(select(Approval).where(Approval.artifact_id == second.id))
        ).scalars().all() == []


@pytest.mark.asyncio
async def test_artifact_versions_are_append_only_and_approval_targets_artifact() -> None:
    async with isolated_session() as session:
        _, run, _ = await create_run(session)
        first = artifact_row(run, 1)
        second = artifact_row(run, 2)
        session.add_all([first, second])
        await session.flush()
        approval = Approval(
            run_id=run.id,
            step_key="draft",
            artifact_id=first.id,
            decision="approved",
            actor_id="reviewer",
        )
        session.add(approval)
        await session.flush()
        stored = (
            await session.execute(select(Artifact).where(Artifact.id == first.id))
        ).scalar_one()
        assert stored.content_json == {"version": 1, "body": "draft 1"}
        assert approval.artifact_id == first.id
        assert approval.step_key == "draft"
        assert approval.decision == "approved"
        assert second.id != first.id
        assert (
            await session.execute(select(Approval).where(Approval.artifact_id == second.id))
        ).scalars().all() == []


@pytest.mark.asyncio
async def test_context_manifest_is_immutable_and_keeps_context_refs() -> None:
    async with isolated_session() as session:
        project, run, snapshot = await create_run(session)
        evidence_set = EvidenceSet(
            project_id=project.id,
            content_case_id=run.content_case_id,
            version=1,
            evidence_ids_json=["evidence:1"],
            content_hash=content_hash("evidence-set:1"),
            status="locked",
            locked_at=datetime.now(UTC),
            locked_by="reviewer",
        )
        session.add(evidence_set)
        await session.flush()
        manifest = ContextManifest(
            run_id=run.id,
            settings_snapshot_id=snapshot.id,
            prompt_version="journal_draft:1",
            recipe_version="journal_direct_answer_story:1",
            evidence_set_id=evidence_set.id,
            knowledge_chunk_refs_json=["chunk:1"],
            golden_example_refs_json=["example:1"],
            tool_result_refs_json=["tool-result:1"],
            content_hash=content_hash("manifest:1"),
        )
        session.add(manifest)
        await session.flush()
        assert manifest.evidence_set_id == evidence_set.id
        assert manifest.settings_snapshot_id == snapshot.id
        with pytest.raises(DBAPIError, match="context_manifest_is_immutable"):
            async with session.begin_nested():
                await session.execute(
                    update(ContextManifest)
                    .where(ContextManifest.id == manifest.id)
                    .values(prompt_version="journal_draft:2")
                )
        with pytest.raises(DBAPIError, match="context_manifest_is_immutable"):
            async with session.begin_nested():
                await session.delete(manifest)
                await session.flush()


@pytest.mark.asyncio
async def test_model_tool_and_quality_ledgers_reference_the_run_context_and_artifact() -> None:
    async with isolated_session() as session:
        _, run, snapshot = await create_run(session)
        step = StepRun(run_id=run.id, step_key="draft", attempt=1)
        session.add(step)
        await session.flush()
        manifest = ContextManifest(
            run_id=run.id,
            step_run_id=step.id,
            settings_snapshot_id=snapshot.id,
            prompt_version="prompt:1",
            recipe_version="recipe:1",
            knowledge_chunk_refs_json=[],
            golden_example_refs_json=[],
            tool_result_refs_json=[],
            content_hash=content_hash("manifest:ledger"),
        )
        artifact = artifact_row(run, 1, step.id)
        session.add_all([manifest, artifact])
        await session.flush()
        model_call = ModelCall(
            run_id=run.id,
            step_run_id=step.id,
            context_manifest_id=manifest.id,
            task_key="draft",
            provider="test-provider",
            model="test-model",
            purpose="draft generation",
            prompt_version="prompt:1",
            status="completed",
            input_tokens=10,
            output_tokens=20,
            cost=Decimal("0.012300"),
            latency_ms=30,
            finish_reason="stop",
            error_class=None,
            result_artifact_id=artifact.id,
        )
        tool_call = ToolCall(
            run_id=run.id,
            step_run_id=step.id,
            tool_key="reader",
            request_fingerprint="request:1",
            result_ref="result:1",
            latency_ms=12,
            status="failed",
            retry_count=1,
            error_class="timeout",
        )
        evaluation = QualityEvaluation(
            run_id=run.id,
            artifact_id=artifact.id,
            evaluator_key="assertion-audit",
            evaluator_version="1",
            evaluator_type="deterministic",
            result="pass",
            score=1.0,
            severity="none",
            findings_json={"checked": 3},
        )
        session.add_all([model_call, tool_call, evaluation])
        await session.flush()
        assert model_call.context_manifest_id == manifest.id
        assert model_call.result_artifact_id == artifact.id
        assert model_call.status == "completed"
        assert model_call.cost == Decimal("0.012300")
        assert model_call.error_class is None
        assert tool_call.result_ref == "result:1"
        assert tool_call.status == "failed"
        assert tool_call.error_class == "timeout"
        assert evaluation.artifact_id == artifact.id
        assert evaluation.findings_json == {"checked": 3}

        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    QualityEvaluation(
                        run_id=run.id,
                        artifact_id=artifact.id,
                        evaluator_key="assertion-audit",
                        evaluator_version="1",
                        evaluator_type="deterministic",
                        result="unknown",
                        findings_json={},
                    )
                )
                await session.flush()
