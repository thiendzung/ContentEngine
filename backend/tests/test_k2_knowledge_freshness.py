from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from evidence_set_helpers import create_locked_evidence_set
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    NeedHypothesis,
    Project,
)
from app.modules.knowledge.admission import admit_knowledge_candidate
from app.modules.knowledge.candidates import extract_knowledge_candidates
from app.modules.knowledge.freshness import (
    FreshnessError,
    ensure_freshness_assignment,
    ensure_freshness_policy,
    evaluate_freshness,
    record_lineage_verification,
    replace_freshness_assignment,
    resolve_effective_freshness_policy,
    retire_freshness_policy,
)
from app.modules.knowledge.freshness_models import (
    FreshnessAssignment,
    SourceDocumentObservation,
)
from app.modules.knowledge.ingest import ingest_source_document, register_source
from app.modules.knowledge.models import Claim, Evidence, KnowledgeCandidate, SourceDocument
from app.modules.knowledge.topic_graph import ensure_knowledge_topic_link, ensure_topic_node

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


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


async def motgu_project(session: AsyncSession) -> Project:
    return (await session.execute(select(Project).where(Project.slug == "motgu"))).scalar_one()


async def _claim_fixture(
    session: AsyncSession,
    *,
    observed_at: datetime = T0,
) -> tuple[Project, Claim, UUID, str]:
    project = await motgu_project(session)
    source_url = f"https://example.test/k2/{uuid4()}"
    source = (
        await register_source(
            session,
            project_id=project.id,
            source_type="web",
            canonical_url=source_url,
            provenance_json={"source_ref": source_url, "method": "k2-test"},
            captured_at=observed_at,
            locale="en",
            authority_hint="high",
            commercial_bias="low",
        )
    ).source
    document_text = "Bat Trang pottery has a long documented craft history."
    ingested = await ingest_source_document(
        session,
        source_id=source.id,
        content_markdown=document_text,
        fetched_at=observed_at,
        canonical_url=source_url,
        reader="k2-test",
        provider="manual",
    )
    claim = Claim(
        project_id=project.id,
        subject_entity_id=None,
        statement=f"Synthetic K2 claim {uuid4()}",
        claim_type="fact",
        importance="normal",
        status="unverified",
        confidence=None,
        entity_refs_json=[],
    )
    session.add(claim)
    await session.flush()
    evidence = Evidence(
        claim_id=claim.id,
        source_document_id=ingested.document.id,
        chunk_id=ingested.chunks[0].id,
        locator="paragraph:1",
        excerpt=document_text,
        relation="supports",
        authority_level="high",
        quality_metadata_json={"source_type": "web"},
        provenance_json={
            "method": "read_excerpt_link",
            "source_id": str(source.id),
            "source_document_id": str(ingested.document.id),
            "source_document_hash": ingested.document.content_hash,
        },
        verified_at=observed_at,
    )
    session.add(evidence)
    await session.flush()
    return project, claim, source.id, document_text


async def _approved_candidate_fixture(
    session: AsyncSession,
) -> tuple[Project, KnowledgeCandidate]:
    project, claim, _source_id, _document_text = await _claim_fixture(session)
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement=f"Synthetic K2 need {uuid4()}",
        audience_scope="test reader",
        situation="testing freshness",
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
        reader="test reader",
        situation="testing freshness",
        need="reuse verified knowledge",
        question="Can verified knowledge be freshness evaluated?",
        intent="learn",
        promise="prove K2 candidate freshness lineage",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="freshness verification",
        next_discovery_step="K2",
        decision="CREATE",
        priority="NOW",
        reasons_json=["K2 test"],
        suggested_content_type="journal",
        selected_by="founder",
        selected_at=T0,
        selection_reason="K2 test",
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="test freshness",
        content_hypothesis="approved knowledge can be evaluated",
        originality_statement="synthetic",
        reader_before="unknown",
        reader_after="known",
        status="draft",
    )
    session.add(content_case)
    await session.flush()
    evidence_ids = list(
        (
            await session.scalars(select(Evidence.id).where(Evidence.claim_id == claim.id))
        ).all()
    )
    evidence_set = await create_locked_evidence_set(
        session,
        project_id=project.id,
        content_case_id=content_case.id,
        version=1,
        evidence_ids=[str(value) for value in evidence_ids],
        locked_by="policy:k2-test",
    )
    candidate = (await extract_knowledge_candidates(session, evidence_set_id=evidence_set.id))[0]
    candidate_hash = cast(str, candidate.provenance_json["candidate_content_hash"])
    approved = await admit_knowledge_candidate(
        session,
        candidate_id=candidate.id,
        decision="approve",
        reviewer="founder",
        review_reason="K2 lineage fixture",
        expected_candidate_content_hash=candidate_hash,
    )
    return project, approved


@pytest.mark.asyncio
async def test_unchanged_reread_creates_observation_without_new_document_version() -> None:
    async with isolated_session() as session:
        project, claim, source_id, document_text = await _claim_fixture(session)
        del project, claim
        before_documents = await session.scalar(
            select(func.count())
            .select_from(SourceDocument)
            .where(SourceDocument.source_id == source_id)
        )
        first_observations = await session.scalar(
            select(func.count())
            .select_from(SourceDocumentObservation)
            .join(SourceDocument, SourceDocumentObservation.source_document_id == SourceDocument.id)
            .where(SourceDocument.source_id == source_id)
        )

        reread = await ingest_source_document(
            session,
            source_id=source_id,
            content_markdown=document_text,
            fetched_at=T0 + timedelta(days=40),
            reader="k2-test",
            provider="manual",
        )

        after_documents = await session.scalar(
            select(func.count())
            .select_from(SourceDocument)
            .where(SourceDocument.source_id == source_id)
        )
        after_observations = await session.scalar(
            select(func.count())
            .select_from(SourceDocumentObservation)
            .join(SourceDocument, SourceDocumentObservation.source_document_id == SourceDocument.id)
            .where(SourceDocument.source_id == source_id)
        )
        assert reread.document_created is False
        assert before_documents == after_documents == 1
        assert first_observations == 1
        assert after_observations == 2


@pytest.mark.asyncio
async def test_freshness_state_progression_reread_and_source_supersession() -> None:
    async with isolated_session() as session:
        project, claim, source_id, document_text = await _claim_fixture(session)
        unclassified = await evaluate_freshness(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            as_of=T0,
        )
        assert unclassified.state == "UNCLASSIFIED"

        policy = await ensure_freshness_policy(
            session,
            project_id=project.id,
            policy_key="k2-test-fast",
            version=1,
            freshness_class="fast",
            max_age_days=30,
            refresh_lead_days=5,
            created_by="founder",
            rationale="Synthetic K2 TTL for deterministic testing.",
        )
        await ensure_freshness_assignment(
            session,
            project_id=project.id,
            policy_id=policy.id,
            target_type="claim",
            target_id=claim.id,
            assigned_by="founder",
            reason="K2 test",
        )
        unknown = await evaluate_freshness(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            as_of=T0,
        )
        assert unknown.state == "UNKNOWN"

        first = await record_lineage_verification(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            recorded_by="policy:k2-lineage",
            as_of=T0,
        )
        replay = await record_lineage_verification(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            recorded_by="policy:k2-lineage",
            as_of=T0,
        )
        assert first.id == replay.id
        assert first.verified_at == T0

        fresh = await evaluate_freshness(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            as_of=T0 + timedelta(days=10),
        )
        due = await evaluate_freshness(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            as_of=T0 + timedelta(days=26),
        )
        stale = await evaluate_freshness(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            as_of=T0 + timedelta(days=31),
        )
        assert fresh.state == "FRESH"
        assert due.state == "DUE"
        assert stale.state == "STALE"
        assert stale.reasons == ("max_age_exceeded",)

        await ingest_source_document(
            session,
            source_id=source_id,
            content_markdown=document_text,
            fetched_at=T0 + timedelta(days=40),
            reader="k2-test",
            provider="manual",
        )
        refreshed = await record_lineage_verification(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            recorded_by="policy:k2-lineage",
            as_of=T0 + timedelta(days=40),
        )
        assert refreshed.id != first.id
        assert refreshed.basis_hash == first.basis_hash
        assert refreshed.verified_at == T0 + timedelta(days=40)
        assert (
            await evaluate_freshness(
                session,
                project_id=project.id,
                target_type="claim",
                target_id=claim.id,
                as_of=T0 + timedelta(days=41),
            )
        ).state == "FRESH"

        await ingest_source_document(
            session,
            source_id=source_id,
            content_markdown=document_text + " The page changed.",
            fetched_at=T0 + timedelta(days=42),
            reader="k2-test",
            provider="manual",
        )
        historical = await evaluate_freshness(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            as_of=T0 + timedelta(days=41),
        )
        changed = await evaluate_freshness(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
            as_of=T0 + timedelta(days=43),
        )
        assert historical.state == "FRESH"
        assert changed.state == "STALE"
        assert changed.reasons == ("source_superseded",)


@pytest.mark.asyncio
async def test_topic_policy_is_strictest_and_explicit_target_overrides_it() -> None:
    async with isolated_session() as session:
        project, claim, _source_id, _document_text = await _claim_fixture(session)
        broad = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key=f"k2-broad-{uuid4().hex}",
            name="K2 Broad Topic",
            node_type="topic",
        )
        strict = await ensure_topic_node(
            session,
            project_id=project.id,
            canonical_key=f"k2-strict-{uuid4().hex}",
            name="K2 Strict Topic",
            node_type="topic",
        )
        for topic in (broad, strict):
            await ensure_knowledge_topic_link(
                session,
                project_id=project.id,
                topic_id=topic.id,
                target_type="claim",
                target_id=claim.id,
                link_method="manual",
                linked_by="founder",
            )
        broad_policy = await ensure_freshness_policy(
            session,
            project_id=project.id,
            policy_key=f"broad-{uuid4().hex}",
            version=1,
            freshness_class="slow",
            max_age_days=90,
            refresh_lead_days=10,
            created_by="founder",
            rationale="K2 broad topic policy",
        )
        strict_policy = await ensure_freshness_policy(
            session,
            project_id=project.id,
            policy_key=f"strict-{uuid4().hex}",
            version=1,
            freshness_class="medium",
            max_age_days=60,
            refresh_lead_days=10,
            created_by="founder",
            rationale="K2 strict topic policy",
        )
        await ensure_freshness_assignment(
            session,
            project_id=project.id,
            policy_id=broad_policy.id,
            target_type="topic",
            target_id=broad.id,
            assigned_by="founder",
            reason="topic default",
        )
        await ensure_freshness_assignment(
            session,
            project_id=project.id,
            policy_id=strict_policy.id,
            target_type="topic",
            target_id=strict.id,
            assigned_by="founder",
            reason="topic default",
        )
        effective = await resolve_effective_freshness_policy(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
        )
        assert effective is not None
        assert effective.source == "topic"
        assert effective.policy.id == strict_policy.id
        assert effective.topic_id == strict.id

        target_policy = await ensure_freshness_policy(
            session,
            project_id=project.id,
            policy_key=f"target-{uuid4().hex}",
            version=1,
            freshness_class="evergreen",
            max_age_days=365,
            refresh_lead_days=30,
            created_by="founder",
            rationale="Explicit claim policy wins over topics.",
        )
        await ensure_freshness_assignment(
            session,
            project_id=project.id,
            policy_id=target_policy.id,
            target_type="claim",
            target_id=claim.id,
            assigned_by="founder",
            reason="explicit claim override",
        )
        overridden = await resolve_effective_freshness_policy(
            session,
            project_id=project.id,
            target_type="claim",
            target_id=claim.id,
        )
        assert overridden is not None
        assert overridden.source == "target"
        assert overridden.policy.id == target_policy.id
        assert overridden.topic_id is None


@pytest.mark.asyncio
async def test_assignment_replacement_and_policy_retirement_are_audited() -> None:
    async with isolated_session() as session:
        project, claim, _source_id, _document_text = await _claim_fixture(session)
        first_policy = await ensure_freshness_policy(
            session,
            project_id=project.id,
            policy_key=f"replace-a-{uuid4().hex}",
            version=1,
            freshness_class="slow",
            max_age_days=90,
            refresh_lead_days=10,
            created_by="founder",
            rationale="Initial K2 policy",
        )
        second_policy = await ensure_freshness_policy(
            session,
            project_id=project.id,
            policy_key=f"replace-b-{uuid4().hex}",
            version=1,
            freshness_class="medium",
            max_age_days=60,
            refresh_lead_days=10,
            created_by="founder",
            rationale="Replacement K2 policy",
        )
        first_assignment = await ensure_freshness_assignment(
            session,
            project_id=project.id,
            policy_id=first_policy.id,
            target_type="claim",
            target_id=claim.id,
            assigned_by="founder",
            reason="initial",
        )
        with pytest.raises(FreshnessError) as active_info:
            await retire_freshness_policy(
                session,
                policy_id=first_policy.id,
                retired_by="founder",
                reason="replace policy",
            )
        assert active_info.value.code == "freshness_policy_has_active_assignments"

        replacement = await replace_freshness_assignment(
            session,
            expected_assignment_id=first_assignment.id,
            new_policy_id=second_policy.id,
            assigned_by="founder",
            reason="replace policy",
        )
        await session.refresh(first_assignment)
        assert first_assignment.status == "retired"
        assert first_assignment.retired_by == "founder"
        assert replacement.supersedes_id == first_assignment.id
        assert replacement.status == "active"

        retired = await retire_freshness_policy(
            session,
            policy_id=first_policy.id,
            retired_by="founder",
            reason="replace policy",
        )
        assert retired.status == "retired"
        assert retired.retired_by == "founder"


@pytest.mark.asyncio
async def test_approved_candidate_is_verifiable_and_unapproved_candidate_is_rejected() -> None:
    async with isolated_session() as session:
        project, approved = await _approved_candidate_fixture(session)
        policy = await ensure_freshness_policy(
            session,
            project_id=project.id,
            policy_key=f"candidate-{uuid4().hex}",
            version=1,
            freshness_class="medium",
            max_age_days=60,
            refresh_lead_days=10,
            created_by="founder",
            rationale="Candidate policy",
        )
        await ensure_freshness_assignment(
            session,
            project_id=project.id,
            policy_id=policy.id,
            target_type="knowledge_candidate",
            target_id=approved.id,
            assigned_by="founder",
            reason="approved candidate",
        )
        verification = await record_lineage_verification(
            session,
            project_id=project.id,
            target_type="knowledge_candidate",
            target_id=approved.id,
            recorded_by="policy:k2-lineage",
            as_of=T0,
        )
        assert verification.knowledge_candidate_id == approved.id
        assert verification.evidence_ids_json
        assert (
            await evaluate_freshness(
                session,
                project_id=project.id,
                target_type="knowledge_candidate",
                target_id=approved.id,
                as_of=T0 + timedelta(days=1),
            )
        ).state == "FRESH"

        raw = KnowledgeCandidate(
            project_id=project.id,
            locale="en",
            statement=f"Unapproved K2 candidate {uuid4()}",
            summary="Must not receive freshness authority.",
            source_refs_json=[],
            provenance_json={},
            entity_refs_json=[],
            status="CANDIDATE",
            reviewer=None,
            review_reason=None,
        )
        session.add(raw)
        await session.flush()
        with pytest.raises(FreshnessError) as info:
            await ensure_freshness_assignment(
                session,
                project_id=project.id,
                policy_id=policy.id,
                target_type="knowledge_candidate",
                target_id=raw.id,
                assigned_by="founder",
                reason="should fail",
            )
        assert info.value.code == "freshness_assignment_candidate_not_approved"

        active_count = await session.scalar(
            select(func.count())
            .select_from(FreshnessAssignment)
            .where(FreshnessAssignment.knowledge_candidate_id == raw.id)
        )
        assert active_count == 0
