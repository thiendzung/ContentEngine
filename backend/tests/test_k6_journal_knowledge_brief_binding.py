from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_journal_context_memory import make_valid_approved_candidate
from test_ce05_journal_research_handoff import _approved_pack, _content_case, _run_and_step

from app.core.database import engine
from app.modules.content_engine.journal.angle import (
    angle_model_input_hash,
    load_journal_input_bundle,
)
from app.modules.content_engine.journal.context import (
    JournalContextError,
    build_journal_context,
    persist_journal_context,
)
from app.modules.content_engine.journal.operator_angle_bundle import (
    bind_bundle_context_manifest,
)
from app.modules.content_engine.journal.research_handoff import (
    JournalResearchHandoff,
    ResearchDecision,
)
from app.modules.content_engine.models import ContentCase, LocaleVariant, Project
from app.modules.harness.models import Artifact, ContextManifest, ModelCall, ToolCall
from app.modules.harness.runtime import (
    ContextInputs,
    RuntimeStateError,
    build_context_manifest,
)
from app.modules.knowledge.brief import materialize_knowledge_brief
from app.modules.knowledge.brief_models import KnowledgeBrief
from app.modules.knowledge.brief_ref import (
    format_knowledge_brief_ref,
    knowledge_brief_snapshot,
)
from app.modules.knowledge.coverage import plan_knowledge_coverage
from app.modules.knowledge.harvest import harvest_knowledge
from app.modules.knowledge.topic_graph import (
    ensure_knowledge_topic_link,
    ensure_topic_node,
)


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


async def _materialize_case_brief(
    session: AsyncSession,
    *,
    project: Project,
    content_case: ContentCase,
    locale: str,
    with_candidate: bool,
) -> tuple[KnowledgeBrief, object | None]:
    topic = await ensure_topic_node(
        session,
        project_id=project.id,
        canonical_key=f"k6-{locale}-{uuid4().hex}",
        name=f"K6 {locale} topic",
        node_type="topic",
        metadata_json={"fixture": "k6"},
    )
    candidate_fixture = None
    if with_candidate:
        candidate_fixture = await make_valid_approved_candidate(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            statement="Artwork price context should stay evidence-grounded for the buyer.",
        )
        await ensure_knowledge_topic_link(
            session,
            project_id=project.id,
            topic_id=topic.id,
            target_type="knowledge_candidate",
            target_id=candidate_fixture.candidate.id,
            link_method="manual",
            linked_by="founder",
            relevance_score=900,
        )
    harvest = await harvest_knowledge(
        session,
        project_id=project.id,
        root_topic_ids=(topic.id,),
        locale=locale,
        as_of=datetime.now(UTC),
        created_by="policy:k6-harvest",
        content_case_id=content_case.id,
    )
    plan = await plan_knowledge_coverage(
        session,
        knowledge_harvest_id=harvest.id,
        created_by="policy:k6-plan",
    )
    brief = await materialize_knowledge_brief(
        session,
        knowledge_coverage_plan_id=plan.id,
        created_by="policy:k6-brief",
    )
    return brief, candidate_fixture


async def _materialize_unbound_brief(
    session: AsyncSession,
    *,
    project: Project,
    locale: str,
) -> KnowledgeBrief:
    topic = await ensure_topic_node(
        session,
        project_id=project.id,
        canonical_key=f"k6-unbound-{locale}-{uuid4().hex}",
        name=f"K6 unbound {locale}",
        node_type="topic",
        metadata_json={"fixture": "k6"},
    )
    harvest = await harvest_knowledge(
        session,
        project_id=project.id,
        root_topic_ids=(topic.id,),
        locale=locale,
        as_of=datetime.now(UTC),
        created_by="policy:k6-harvest",
    )
    plan = await plan_knowledge_coverage(
        session,
        knowledge_harvest_id=harvest.id,
        created_by="policy:k6-plan",
    )
    return await materialize_knowledge_brief(
        session,
        knowledge_coverage_plan_id=plan.id,
        created_by="policy:k6-brief",
    )


async def _k6_runtime_fixture(
    session: AsyncSession,
) -> tuple[
    Project,
    ContentCase,
    LocaleVariant,
    KnowledgeBrief,
    object,
    object,
    object,
]:
    project, content_case, opportunity, _need = await _content_case(session)
    run, step = await _run_and_step(
        session,
        project=project,
        content_case=content_case,
    )
    variant = await session.get(LocaleVariant, run.locale_variant_id)
    assert variant is not None
    brief, candidate_fixture = await _materialize_case_brief(
        session,
        project=project,
        content_case=content_case,
        locale=variant.locale,
        with_candidate=True,
    )
    assert candidate_fixture is not None
    context = await build_journal_context(
        session,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        knowledge_brief_id=brief.id,
    )
    persisted_context = await persist_journal_context(
        session,
        run_id=run.id,
        step_run_id=step.id,
        context=context,
    )
    return (
        project,
        content_case,
        variant,
        brief,
        candidate_fixture,
        opportunity,
        (run, step, context, persisted_context),
    )


@pytest.mark.asyncio
async def test_k5_bound_context_is_v2_and_skips_legacy_live_candidate_recall() -> None:
    async with isolated_session() as session:
        (
            project,
            content_case,
            variant,
            brief,
            _candidate_fixture,
            _opportunity,
            runtime,
        ) = await _k6_runtime_fixture(session)
        run, step, context, persisted = runtime

        # This second approved candidate deliberately matches the old keyword recall path,
        # but it is not in K3/K4/K5 and therefore must never leak into K6 context.
        leaked_if_live_recall = await make_valid_approved_candidate(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            statement="A buyer should evaluate artwork price context before deciding.",
        )
        rebuilt = await build_journal_context(
            session,
            content_case_id=content_case.id,
            locale_variant_id=variant.id,
            knowledge_brief_id=brief.id,
        )

        assert context.schema_version == 2
        assert rebuilt.schema_version == 2
        assert context.approved_knowledge == ()
        assert rebuilt.approved_knowledge == ()
        assert context.to_dict()["approved_knowledge_refs"] == []
        assert rebuilt.to_dict()["approved_knowledge_refs"] == []
        assert context.knowledge_brief == knowledge_brief_snapshot(brief)
        assert rebuilt.knowledge_brief == knowledge_brief_snapshot(brief)
        assert str(leaked_if_live_recall.candidate.id) not in str(rebuilt.to_dict())
        assert context.provider_calls == 0

        manifest = await session.get(ContextManifest, persisted.context_manifest_id)
        assert manifest is not None
        assert manifest.run_id == run.id
        assert manifest.step_run_id == step.id
        assert manifest.approved_knowledge_refs_json == []
        assert manifest.knowledge_chunk_refs_json == [format_knowledge_brief_ref(brief)]
        assert manifest.context_artifact_id == persisted.journal_context_artifact.id
        assert await session.scalar(select(func.count()).select_from(ModelCall)) == 0
        assert await session.scalar(select(func.count()).select_from(ToolCall)) == 0

        replay = await persist_journal_context(
            session,
            run_id=run.id,
            step_run_id=step.id,
            context=rebuilt,
        )
        replay_manifest = await session.get(ContextManifest, replay.context_manifest_id)
        assert replay_manifest is not None
        assert replay.journal_context_artifact.id == persisted.journal_context_artifact.id
        assert replay.memory_overlap_artifact.id == persisted.memory_overlap_artifact.id
        assert replay_manifest.content_hash == manifest.content_hash
        assert replay_manifest.knowledge_chunk_refs_json == manifest.knowledge_chunk_refs_json


@pytest.mark.asyncio
async def test_runtime_rejects_malformed_forged_and_multiple_knowledge_brief_refs() -> None:
    async with isolated_session() as session:
        (
            _project,
            _content_case_row,
            _variant,
            brief,
            _candidate_fixture,
            _opportunity,
            runtime,
        ) = await _k6_runtime_fixture(session)
        run, step, _context, persisted = runtime
        valid_ref = format_knowledge_brief_ref(brief)

        invalid_refs = [
            ("knowledge_brief:not-a-uuid:" + "0" * 64,),
            (f"knowledge_brief:{brief.id}:" + "0" * 64,),
            (valid_ref, valid_ref),
        ]
        expected = [
            "knowledge_brief_ref_invalid",
            "knowledge_brief_ref_snapshot_mismatch",
            "knowledge_brief_ref_multiple",
        ]
        for refs, error in zip(invalid_refs, expected, strict=True):
            with pytest.raises(RuntimeStateError, match=error):
                await build_context_manifest(
                    session,
                    run_id=run.id,
                    step_run_id=step.id,
                    inputs=ContextInputs(
                        prompt_version="k6:test",
                        recipe_version="k6:test",
                        context_artifact_id=persisted.journal_context_artifact.id,
                        knowledge_chunk_refs=refs,
                    ),
                )


@pytest.mark.asyncio
async def test_context_rejects_wrong_project_case_and_locale_briefs() -> None:
    async with isolated_session() as session:
        project, content_case, _opportunity, _need = await _content_case(session)
        run, _step = await _run_and_step(
            session,
            project=project,
            content_case=content_case,
        )
        variant = await session.get(LocaleVariant, run.locale_variant_id)
        assert variant is not None

        unbound = await _materialize_unbound_brief(
            session,
            project=project,
            locale=variant.locale,
        )
        with pytest.raises(JournalContextError, match="knowledge_brief_ref_case_mismatch"):
            await build_journal_context(
                session,
                content_case_id=content_case.id,
                locale_variant_id=variant.id,
                knowledge_brief_id=unbound.id,
            )

        wrong_locale, _ = await _materialize_case_brief(
            session,
            project=project,
            content_case=content_case,
            locale="vi",
            with_candidate=False,
        )
        with pytest.raises(JournalContextError, match="knowledge_brief_ref_locale_mismatch"):
            await build_journal_context(
                session,
                content_case_id=content_case.id,
                locale_variant_id=variant.id,
                knowledge_brief_id=wrong_locale.id,
            )

        other_project, other_case, _other_opportunity, _other_need = await _content_case(session)
        wrong_project, _ = await _materialize_case_brief(
            session,
            project=other_project,
            content_case=other_case,
            locale=variant.locale,
            with_candidate=False,
        )
        with pytest.raises(JournalContextError, match="knowledge_brief_ref_project_mismatch"):
            await build_journal_context(
                session,
                content_case_id=content_case.id,
                locale_variant_id=variant.id,
                knowledge_brief_id=wrong_project.id,
            )


@pytest.mark.asyncio
async def test_angle_model_input_contains_exact_verified_k5_snapshot_without_model_call() -> None:
    async with isolated_session() as session:
        (
            project,
            content_case,
            _variant,
            brief,
            candidate_fixture,
            opportunity,
            runtime,
        ) = await _k6_runtime_fixture(session)
        run, step, context, persisted = runtime

        pack = await _approved_pack(session, content_case_id=content_case.id)
        handoff = JournalResearchHandoff()
        evidence_handoff = await handoff.handoff_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_set_id=candidate_fixture.evidence_set.id,
            expected_version=candidate_fixture.evidence_set.version,
            expected_content_hash=candidate_fixture.evidence_set.content_hash,
        )
        originality_handoff = await handoff.handoff_originality_pack(
            session,
            content_case_id=content_case.id,
            originality_pack_id=pack.id,
        )
        manifest = await build_context_manifest(
            session,
            run_id=run.id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version="journal_angle_candidates:v1",
                recipe_version="journal_angle_v1:v1",
                evidence_set_id=evidence_handoff.evidence_set_id,
                originality_pack_id=originality_handoff.originality_pack_id,
                context_artifact_id=persisted.journal_context_artifact.id,
                approved_knowledge_refs=context.approved_knowledge_refs,
                knowledge_chunk_refs=(format_knowledge_brief_ref(brief),),
            ),
        )
        base_bundle = await handoff.persist_journal_input_bundle(
            session,
            run_id=run.id,
            step_run_id=step.id,
            research_decision=ResearchDecision.REUSE_EXISTING,
            opportunity_id=opportunity.id,
            evidence_set=evidence_handoff,
            originality_pack=originality_handoff,
            provider_calls=0,
            model_calls=0,
        )
        bound_bundle = await bind_bundle_context_manifest(
            session,
            base_bundle_artifact_id=base_bundle.id,
            context_manifest_id=manifest.id,
        )
        loaded = await load_journal_input_bundle(
            session,
            journal_input_bundle_id=bound_bundle.id,
            expected_content_hash=bound_bundle.content_hash,
        )

        expected = knowledge_brief_snapshot(brief)
        assert loaded.context_manifest is not None
        assert loaded.context_manifest.id == manifest.id
        assert loaded.context_manifest.knowledge_chunk_refs_json == [
            format_knowledge_brief_ref(brief)
        ]
        assert loaded.angle_model_input["knowledge_brief"] == expected
        assert loaded.angle_model_input["evidence_set"]["id"] == str(
            candidate_fixture.evidence_set.id
        )
        assert loaded.angle_model_input["originality_pack"]["id"] == str(pack.id)
        assert len(angle_model_input_hash(loaded.angle_model_input)) == 64

        brief_payload = expected["payload"]
        assert isinstance(brief_payload, dict)
        # No K2 policy exists in this fixture, so the approved candidate is
        # UNCLASSIFIED: K5 must expose the policy action but never mark it reusable.
        assert brief_payload["reusable_knowledge"] == []
        assert brief_payload["policy_required_targets"]
        assert await session.scalar(select(func.count()).select_from(ModelCall)) == 0
        assert await session.scalar(select(func.count()).select_from(ToolCall)) == 0


@pytest.mark.asyncio
async def test_runtime_rejects_context_artifact_that_does_not_match_typed_brief() -> None:
    async with isolated_session() as session:
        (
            _project,
            _content_case_row,
            _variant,
            brief,
            _candidate_fixture,
            _opportunity,
            runtime,
        ) = await _k6_runtime_fixture(session)
        run, step, _context, persisted = runtime
        forged_payload = dict(persisted.journal_context_artifact.content_json or {})
        forged_payload["knowledge_brief"] = {
            **knowledge_brief_snapshot(brief),
            "snapshot_hash": "0" * 64,
        }
        forged_artifact = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="journal_context",
            locale="en",
            version=99,
            content_json=forged_payload,
            content_hash="0" * 64,
        )
        session.add(forged_artifact)
        await session.flush()

        with pytest.raises(
            RuntimeStateError,
            match="knowledge_brief_context_snapshot_mismatch",
        ):
            await build_context_manifest(
                session,
                run_id=run.id,
                step_run_id=step.id,
                inputs=ContextInputs(
                    prompt_version="k6:test",
                    recipe_version="k6:test",
                    context_artifact_id=forged_artifact.id,
                    knowledge_chunk_refs=(format_knowledge_brief_ref(brief),),
                ),
            )
