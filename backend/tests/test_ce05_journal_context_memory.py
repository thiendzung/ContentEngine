from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.journal.context import (
    JournalContextError,
    build_journal_context,
    persist_journal_context,
)
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
    ContextManifest,
    ModelCall,
    StepRun,
    ToolCall,
)
from app.modules.knowledge.models import KnowledgeCandidate
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


async def make_fixture(
    session: AsyncSession,
    *,
    selected: bool = True,
    decision: str = "CREATE",
) -> tuple[Project, ContentCase, LocaleVariant, ContentOpportunity]:
    project = Project(slug=f"ce05-{uuid4().hex[:12]}", name="MOTGU")
    session.add(project)
    await session.flush()
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement="A first-time buyer wants grounded artwork price context.",
        audience_scope="first-time art buyer",
        situation="considering an original artwork",
        origin="founder_proposed",
        status="PROPOSED",
        alternative_explanations_json=[],
        missing_evidence_json=[],
    )
    session.add(need)
    await session.flush()
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader="first-time art buyer",
        situation="considering an original artwork",
        need="understand artwork price context",
        question="How should a buyer evaluate an artwork price?",
        intent="evaluate",
        promise="Ask grounded questions before deciding.",
        motgu_material_refs_json=["motgu:artwork:price-context"],
        material_gaps_json=["direct buyer evidence"],
        existing_content_refs_json=[],
        what_is_actually_new="A bounded internal memory check before writing.",
        next_discovery_step="Review the evidence gap.",
        decision=decision,
        priority="NOW",
        reasons_json=["CE05 test"],
        suggested_content_type="journal",
        selected_by="MG CONTENT ENGINE" if selected else None,
        selected_at=datetime.now(UTC) if selected else None,
        selection_reason="Test selection" if selected else None,
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="Ask a grounded next question.",
        content_hypothesis="A clear explanation helps a buyer decide what to ask next.",
        originality_statement="Use MOTGU-owned context without inventing a pricing formula.",
        reader_before="Unsure whether an artwork price makes sense.",
        reader_after="Able to ask grounded questions about the work.",
        status="draft",
    )
    session.add(content_case)
    await session.flush()
    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="cluster",
        primary_question=opportunity.question,
        primary_intent=opportunity.intent,
    )
    session.add(variant)
    await session.flush()
    return project, content_case, variant, opportunity


def candidate(
    *,
    project_id: UUID,
    statement: str,
    status: str,
    locale: str | None = "en",
    provenance: dict[str, object] | None = None,
) -> KnowledgeCandidate:
    return KnowledgeCandidate(
        project_id=project_id,
        locale=locale,
        statement=statement,
        summary=f"Context for: {statement}",
        source_refs_json=["source:approved-source"],
        provenance_json=provenance
        or {"source_id": "approved-source", "method": "human_review"},
        entity_refs_json=[],
        status=status,
    )


@pytest.mark.asyncio
async def test_context_recalls_only_bounded_approved_knowledge_without_provider_calls() -> None:
    async with isolated_session() as session:
        project, content_case, variant, _opportunity = await make_fixture(session)
        approved = candidate(
            project_id=project.id,
            statement="Artwork prices are shaped by context and market conditions.",
            status="APPROVED",
        )
        candidate_row = candidate(
            project_id=project.id,
            statement="Artwork price candidate should never enter the writer context.",
            status="CANDIDATE",
        )
        rejected = candidate(
            project_id=project.id,
            statement="Rejected artwork price context.",
            status="REJECTED",
        )
        session.add_all([approved, candidate_row, rejected])
        await session.flush()

        context = await build_journal_context(
            session,
            content_case_id=content_case.id,
            locale_variant_id=variant.id,
        )

        assert [item.id for item in context.approved_knowledge] == [approved.id]
        assert context.provider_calls == 0
        assert context.memory_overlap.effective_decision == "CREATE"
        assert context.to_dict()["approved_knowledge_refs"] == [
            f"knowledge_candidate:{approved.id}"
        ]
        assert await session.scalar(select(func.count()).select_from(ModelCall)) == 0
        assert await session.scalar(select(func.count()).select_from(ToolCall)) == 0


@pytest.mark.asyncio
async def test_upstream_do_not_write_decision_is_not_replaced_by_memory_recommendation() -> None:
    async with isolated_session() as session:
        _project, content_case, variant, _opportunity = await make_fixture(
            session,
            decision="DO_NOT_WRITE",
        )
        context = await build_journal_context(
            session,
            content_case_id=content_case.id,
            locale_variant_id=variant.id,
        )

        assert context.memory_overlap.effective_decision == "DO_NOT_WRITE"
        assert context.memory_overlap.to_dict()["upstream_decision_is_authoritative"] is True


@pytest.mark.asyncio
async def test_unselected_opportunity_cannot_build_journal_context() -> None:
    async with isolated_session() as session:
        _project, content_case, variant, _opportunity = await make_fixture(session, selected=False)
        with pytest.raises(JournalContextError, match="journal_context_opportunity_not_selected"):
            await build_journal_context(
                session,
                content_case_id=content_case.id,
                locale_variant_id=variant.id,
            )


@pytest.mark.asyncio
async def test_persisted_context_and_memory_artifacts_are_idempotent_and_manifest_is_exact(
) -> None:
    async with isolated_session() as session:
        project, content_case, variant, _opportunity = await make_fixture(session)
        approved = candidate(
            project_id=project.id,
            statement="Artwork prices are shaped by context and market conditions.",
            status="APPROVED",
        )
        session.add(approved)
        snapshot = SettingsSnapshot(
            project_id=project.id,
            resolved_settings_json={"models": {}, "recipes": {}},
            source_version_refs_json=["settings:ce05-test"],
            content_hash=content_hash("settings:ce05-test"),
        )
        session.add(snapshot)
        await session.flush()
        run = ContentRun(
            project_id=project.id,
            content_case_id=content_case.id,
            locale_variant_id=variant.id,
            run_mode="create",
            status="running",
            current_step="journal_context",
            settings_snapshot_id=snapshot.id,
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()
        step = StepRun(
            run_id=run.id,
            step_key="journal_context",
            attempt=1,
            status="running",
            started_at=datetime.now(UTC),
        )
        session.add(step)
        await session.flush()
        context = await build_journal_context(
            session,
            content_case_id=content_case.id,
            locale_variant_id=variant.id,
        )

        first = await persist_journal_context(
            session,
            run_id=run.id,
            step_run_id=step.id,
            context=context,
        )
        second = await persist_journal_context(
            session,
            run_id=run.id,
            step_run_id=step.id,
            context=context,
        )
        manifest = await session.get(ContextManifest, first.context_manifest_id)
        assert manifest is not None
        assert first.journal_context_artifact.id == second.journal_context_artifact.id
        assert first.memory_overlap_artifact.id == second.memory_overlap_artifact.id
        assert manifest.context_artifact_id == first.journal_context_artifact.id
        assert manifest.approved_knowledge_refs_json == [f"knowledge_candidate:{approved.id}"]
        second_manifest = await session.get(ContextManifest, second.context_manifest_id)
        assert second_manifest is not None
        assert manifest.content_hash == second_manifest.content_hash
        assert manifest.context_artifact_id == second_manifest.context_artifact_id
        assert await session.scalar(
            select(func.count()).select_from(Artifact).where(Artifact.run_id == run.id)
        ) == 2
