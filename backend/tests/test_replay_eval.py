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
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    QualityEvaluation,
    StepRun,
)
from app.modules.harness.outbox import OutboxStateError, create_outbox_intent
from app.modules.harness.persistence import transition_run, transition_step_run
from app.modules.harness.replay_eval import (
    ReplayEvalError,
    create_eval_report,
    create_eval_run,
    frozen_context_inputs,
)
from app.modules.harness.runtime import (
    ContextInputs,
    ModelResponse,
    SettingsModelRouter,
    build_context_manifest,
    complete_model_call,
    start_model_call,
)
from app.modules.knowledge.models import EvidenceSet, OriginalityPack
from app.modules.knowledge.persistence import content_hash


async def _create_baseline(
    session: AsyncSession,
) -> tuple[
    ContentRun,
    StepRun,
    Artifact,
    SettingsSnapshot,
    SettingsSnapshot,
]:
    project = (
        await session.execute(select(Project).where(Project.slug == "motgu"))
    ).scalar_one()
    suffix = uuid4().hex[:8]
    hypothesis = NeedHypothesis(
        project_id=project.id,
        type="problem",
        statement=f"CE03 PR-E replay baseline {suffix}",
        audience_scope="test reader",
        situation="replay eval",
        origin="FOUNDER",
    )
    session.add(hypothesis)
    await session.flush()

    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale="en",
        reader="test reader",
        situation="replay eval",
        need="Compare a candidate safely",
        question="Can a completed run be replayed without publishing?",
        intent="test",
        promise="Frozen inputs with a comparable report",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Synthetic replay proof",
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
        desired_action="Compare",
        content_hypothesis="Replay makes regressions visible",
        originality_statement="Synthetic only",
        reader_before="Unknown",
        reader_after="Compared",
    )
    session.add(content_case)
    await session.flush()

    locale_variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="primary",
        primary_question="Can a completed run be replayed without publishing?",
        primary_intent="test",
    )
    baseline_snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={
            "models": {"draft": {"route": "writer"}},
            "model_routes": {
                "writer": {"provider": "provider-a", "model": "writer-v1"}
            },
        },
        source_version_refs_json=["settings:baseline"],
        content_hash=content_hash(f"replay-baseline-settings:{suffix}"),
    )
    candidate_snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={
            "models": {"draft": {"route": "writer"}},
            "model_routes": {
                "writer": {"provider": "provider-b", "model": "writer-v2"}
            },
        },
        source_version_refs_json=["settings:candidate"],
        content_hash=content_hash(f"replay-candidate-settings:{suffix}"),
    )
    session.add_all([locale_variant, baseline_snapshot, candidate_snapshot])
    await session.flush()

    baseline = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=locale_variant.id,
        run_mode="create",
        status="running",
        current_step="draft",
        settings_snapshot_id=baseline_snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(baseline)
    await session.flush()

    baseline_step = StepRun(
        run_id=baseline.id,
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
        content_hash=content_hash(f"replay-evidence:{suffix}"),
        status="draft",
    )
    originality_pack = OriginalityPack(
        content_case_id=content_case.id,
        item_refs_json=[{"kind": "motgu_fact", "ref": "replay-synthetic"}],
        summary="Replay synthetic originality",
        status="approved",
        approved_at=datetime.now(UTC),
    )
    session.add_all([baseline_step, evidence_set, originality_pack])
    await session.flush()

    baseline_manifest = await build_context_manifest(
        session,
        run_id=baseline.id,
        step_run_id=baseline_step.id,
        inputs=ContextInputs(
            prompt_version="draft:1",
            recipe_version="journal:1",
            evidence_set_id=evidence_set.id,
            originality_pack_id=originality_pack.id,
            knowledge_chunk_refs=("chunk:baseline",),
            golden_example_refs=("golden:baseline",),
            tool_result_refs=("tool:baseline",),
        ),
    )
    baseline_artifact = Artifact(
        run_id=baseline.id,
        step_run_id=baseline_step.id,
        artifact_type="draft",
        version=1,
        content_json={"text": "baseline output"},
        content_hash=content_hash("replay-baseline-output"),
    )
    session.add(baseline_artifact)
    await session.flush()

    baseline_call = await start_model_call(
        session,
        run_id=baseline.id,
        step_run_id=baseline_step.id,
        context_manifest_id=baseline_manifest.id,
        task_key="draft",
        route=SettingsModelRouter()
        .resolve(task_key="draft", settings_snapshot=baseline_snapshot)
        .primary,
        purpose="baseline",
        prompt_version="draft:1",
    )
    await complete_model_call(
        session,
        call_id=baseline_call.id,
        response=ModelResponse(
            content="baseline output",
            input_tokens=100,
            output_tokens=120,
            cost=Decimal("0.20"),
            latency_ms=50,
            finish_reason="stop",
        ),
        result_artifact_id=baseline_artifact.id,
    )
    session.add(
        QualityEvaluation(
            run_id=baseline.id,
            artifact_id=baseline_artifact.id,
            evaluator_key="synthetic-quality",
            evaluator_version="1",
            evaluator_type="deterministic",
            result="pass",
            score=0.80,
            findings_json={},
        )
    )
    baseline_step.status = "completed"
    baseline_step.completed_at = datetime.now(UTC)
    baseline.status = "completed"
    baseline.completed_at = datetime.now(UTC)
    await session.flush()

    return (
        baseline,
        baseline_step,
        baseline_artifact,
        baseline_snapshot,
        candidate_snapshot,
    )


@pytest.mark.asyncio
async def test_replay_eval_uses_frozen_context_reports_delta_and_never_publishes() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            (
                baseline,
                baseline_step,
                baseline_artifact,
                baseline_snapshot,
                candidate_snapshot,
            ) = await _create_baseline(session)
            baseline_manifest = (
                await session.execute(
                    select(__import__(
                        "app.modules.harness.models",
                        fromlist=["ContextManifest"],
                    ).ContextManifest).where(
                        __import__(
                            "app.modules.harness.models",
                            fromlist=["ContextManifest"],
                        ).ContextManifest.run_id
                        == baseline.id
                    )
                )
            ).scalar_one()

            fixture = await create_eval_run(
                session,
                baseline_run_id=baseline.id,
                candidate_settings_snapshot_id=candidate_snapshot.id,
                baseline_artifact_id=baseline_artifact.id,
                baseline_context_manifest_id=baseline_manifest.id,
            )
            assert fixture.run.run_mode == "eval"
            assert fixture.fixture.content_json is not None
            assert fixture.fixture.content_json["frozen"] is True
            assert fixture.fixture.content_json["baseline_artifact_hash"] == baseline_artifact.content_hash

            await transition_run(session, run_id=fixture.run.id, status="running")
            eval_step = StepRun(
                run_id=fixture.run.id,
                step_key="eval",
                attempt=1,
                status="pending",
            )
            session.add(eval_step)
            await session.flush()
            await transition_step_run(session, step_run_id=eval_step.id, status="running")

            frozen_inputs = await frozen_context_inputs(
                session,
                eval_run_id=fixture.run.id,
                prompt_version="draft:2",
                recipe_version="journal:1",
            )
            assert frozen_inputs.evidence_set_id == baseline_manifest.evidence_set_id
            assert frozen_inputs.originality_pack_id == baseline_manifest.originality_pack_id
            assert frozen_inputs.knowledge_chunk_refs == ("chunk:baseline",)
            assert frozen_inputs.golden_example_refs == ("golden:baseline",)
            assert frozen_inputs.tool_result_refs == ("tool:baseline",)

            candidate_manifest = await build_context_manifest(
                session,
                run_id=fixture.run.id,
                step_run_id=eval_step.id,
                inputs=frozen_inputs,
            )
            assert candidate_manifest.settings_snapshot_id == candidate_snapshot.id
            assert candidate_manifest.prompt_version == "draft:2"

            route = SettingsModelRouter().resolve(
                task_key="draft",
                settings_snapshot=candidate_snapshot,
            )
            assert route.primary.provider == "provider-b"
            assert route.primary.model == "writer-v2"

            candidate_artifact = Artifact(
                run_id=fixture.run.id,
                step_run_id=eval_step.id,
                artifact_type="draft",
                version=1,
                content_json={"text": "candidate output"},
                content_hash=content_hash("replay-candidate-output"),
            )
            session.add(candidate_artifact)
            await session.flush()
            candidate_call = await start_model_call(
                session,
                run_id=fixture.run.id,
                step_run_id=eval_step.id,
                context_manifest_id=candidate_manifest.id,
                task_key="draft",
                route=route.primary,
                purpose="eval_candidate",
                prompt_version="draft:2",
            )
            await complete_model_call(
                session,
                call_id=candidate_call.id,
                response=ModelResponse(
                    content="candidate output",
                    input_tokens=100,
                    output_tokens=100,
                    cost=Decimal("0.15"),
                    latency_ms=40,
                    finish_reason="stop",
                ),
                result_artifact_id=candidate_artifact.id,
            )
            session.add(
                QualityEvaluation(
                    run_id=fixture.run.id,
                    artifact_id=candidate_artifact.id,
                    evaluator_key="synthetic-quality",
                    evaluator_version="1",
                    evaluator_type="deterministic",
                    result="pass",
                    score=0.90,
                    findings_json={},
                )
            )
            await session.flush()

            with pytest.raises(OutboxStateError, match="eval ContentRun"):
                await create_outbox_intent(
                    session,
                    run_id=fixture.run.id,
                    intent_type="publish",
                    idempotency_key=f"eval-publish:{fixture.run.id}",
                    payload_ref="artifact://candidate",
                )

            report = await create_eval_report(
                session,
                eval_run_id=fixture.run.id,
                candidate_artifact_id=candidate_artifact.id,
            )
            assert report.content_json is not None
            assert report.content_json["baseline"]["settings_snapshot_id"] == str(
                baseline_snapshot.id
            )
            assert report.content_json["candidate"]["settings_snapshot_id"] == str(
                candidate_snapshot.id
            )
            assert report.content_json["comparison"]["content_changed"] is True
            assert report.content_json["comparison"]["average_score_delta"] == pytest.approx(0.1)
            assert report.content_json["comparison"]["output_tokens_delta"] == -20
            assert report.content_json["comparison"]["cost_delta"] == "-0.050000"
            assert report.content_json["promotion"] == {
                "mode": "manual_only",
                "auto_promoted": False,
            }

            await transition_step_run(session, step_run_id=eval_step.id, status="completed")
            await transition_run(session, run_id=fixture.run.id, status="completed")
            assert fixture.run.status == "completed"
            assert baseline_step.status == "completed"
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_replay_eval_rejects_unfinished_baseline() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            baseline, _, artifact, _, candidate_snapshot = await _create_baseline(session)
            baseline.status = "running"
            baseline.completed_at = None
            await session.flush()
            manifest_id = (
                await session.execute(
                    select(__import__(
                        "app.modules.harness.models",
                        fromlist=["ContextManifest"],
                    ).ContextManifest.id).where(
                        __import__(
                            "app.modules.harness.models",
                            fromlist=["ContextManifest"],
                        ).ContextManifest.run_id
                        == baseline.id
                    )
                )
            ).scalar_one()
            with pytest.raises(ReplayEvalError, match="must be completed"):
                await create_eval_run(
                    session,
                    baseline_run_id=baseline.id,
                    candidate_settings_snapshot_id=candidate_snapshot.id,
                    baseline_artifact_id=artifact.id,
                    baseline_context_manifest_id=manifest_id,
                )
        finally:
            await session.close()
            await transaction.rollback()
