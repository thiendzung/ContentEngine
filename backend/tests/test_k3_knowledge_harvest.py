from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from evidence_set_helpers import create_locked_evidence_set
from sqlalchemy import select
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
    ensure_freshness_assignment,
    ensure_freshness_policy,
    record_lineage_verification,
)
from app.modules.knowledge.harvest import (
    harvest_knowledge,
    verify_knowledge_harvest_snapshot,
)
from app.modules.knowledge.ingest import ingest_source_document, register_source
from app.modules.knowledge.models import Claim, Evidence, KnowledgeCandidate, Source
from app.modules.knowledge.topic_graph import (
    ensure_knowledge_topic_link,
    ensure_topic_edge,
    ensure_topic_node,
)
from app.modules.knowledge.topic_models import TopicNode

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


@dataclass(frozen=True)
class ApprovedCandidateFixture:
    candidate: KnowledgeCandidate
    content_case: ContentCase
    source: Source
    source_text: str


async def motgu_project(session: AsyncSession) -> Project:
    return (await session.execute(select(Project).where(Project.slug == "motgu"))).scalar_one()


async def create_content_case(
    session: AsyncSession,
    *,
    project: Project,
    locale: str,
) -> ContentCase:
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement=f"Synthetic K3 need {uuid4()}",
        audience_scope="test reader",
        situation="testing deterministic knowledge harvest",
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
        locale=locale,
        reader="test reader",
        situation="testing deterministic knowledge harvest",
        need="reuse approved knowledge",
        question="What approved knowledge is reusable?",
        intent="learn",
        promise="use only provenance-bound approved knowledge",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new=f"K3 fixture {uuid4()}",
        next_discovery_step="none",
        decision="CREATE",
        priority="NOW",
        reasons_json=["K3 test fixture"],
        suggested_content_type="journal",
        selected_by="founder",
        selected_at=T0,
        selection_reason="K3 test",
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="reuse approved knowledge",
        content_hypothesis="approved knowledge reduces redundant research",
        originality_statement="synthetic K3 fixture",
        reader_before="without reusable context",
        reader_after="with provenance-bound context",
        status="draft",
    )
    session.add(content_case)
    await session.flush()
    return content_case


async def create_candidate(
    session: AsyncSession,
    *,
    project: Project,
    locale: str,
    label: str,
    approve: bool = True,
) -> ApprovedCandidateFixture:
    content_case = await create_content_case(session, project=project, locale=locale)
    source_url = f"https://example.test/k3/{label}/{uuid4()}"
    source = (
        await register_source(
            session,
            project_id=project.id,
            source_type="web",
            captured_at=T0,
            provenance_json={"source_ref": source_url, "method": "k3-test"},
            title=f"K3 source {label}",
            canonical_url=source_url,
            locale=locale,
            commercial_bias="low",
            authority_hint="high",
        )
    ).source
    source_text = f"Verified synthetic K3 source for {label}."
    ingested = await ingest_source_document(
        session,
        source_id=source.id,
        content_markdown=source_text,
        fetched_at=T0,
        canonical_url=source_url,
        reader="k3-test",
        provider="manual",
    )
    claim = Claim(
        project_id=project.id,
        statement=f"Reusable approved K3 claim for {label}.",
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
        locator=f"k3:{label}",
        excerpt=source_text,
        relation="supports",
        authority_level="high",
        quality_metadata_json={"fixture": "k3"},
        provenance_json={
            "method": "read_excerpt_link",
            "source_id": str(source.id),
            "source_document_id": str(ingested.document.id),
            "source_document_hash": ingested.document.content_hash,
        },
        verified_at=T0,
    )
    session.add(evidence)
    await session.flush()
    evidence_set = await create_locked_evidence_set(
        session,
        project_id=project.id,
        content_case_id=content_case.id,
        evidence_ids=[str(evidence.id)],
        locked_by="policy:k3-test-evidence",
    )
    candidates = await extract_knowledge_candidates(
        session,
        evidence_set_id=evidence_set.id,
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    if approve:
        candidate = await admit_knowledge_candidate(
            session,
            candidate_id=candidate.id,
            decision="approve",
            reviewer="founder",
            review_reason="Synthetic K3 approved candidate fixture.",
            expected_candidate_content_hash=str(
                candidate.provenance_json["candidate_content_hash"]
            ),
        )
    return ApprovedCandidateFixture(
        candidate=candidate,
        content_case=content_case,
        source=source,
        source_text=source_text,
    )


async def create_topic(
    session: AsyncSession,
    *,
    project: Project,
    key: str,
    node_type: str,
) -> TopicNode:
    return await ensure_topic_node(
        session,
        project_id=project.id,
        canonical_key=f"{key}-{uuid4().hex}",
        name=f"K3 {key}",
        node_type=node_type,  # type: ignore[arg-type]
        metadata_json={"fixture": "k3"},
    )


@pytest.mark.asyncio
async def test_harvest_expands_contains_only_and_deduplicates_candidate() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        root = await create_topic(session, project=project, key="root", node_type="pillar")
        child = await create_topic(session, project=project, key="child", node_type="topic")
        subtopic = await create_topic(
            session,
            project=project,
            key="subtopic",
            node_type="subtopic",
        )
        related = await create_topic(
            session,
            project=project,
            key="related",
            node_type="pillar",
        )
        await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=root.id,
            child_topic_id=child.id,
            relation_type="contains",
            created_by="test",
        )
        await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=child.id,
            child_topic_id=subtopic.id,
            relation_type="contains",
            created_by="test",
        )
        await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=root.id,
            child_topic_id=related.id,
            relation_type="related",
            created_by="test",
        )

        reusable = await create_candidate(
            session,
            project=project,
            locale="en",
            label="reusable",
        )
        unrelated = await create_candidate(
            session,
            project=project,
            locale="en",
            label="related-only",
        )
        await create_candidate(
            session,
            project=project,
            locale="en",
            label="unapproved",
            approve=False,
        )
        vi_candidate = await create_candidate(
            session,
            project=project,
            locale="vi",
            label="vi",
        )

        for topic in (child, subtopic):
            await ensure_knowledge_topic_link(
                session,
                project_id=project.id,
                topic_id=topic.id,
                target_type="knowledge_candidate",
                target_id=reusable.candidate.id,
                link_method="manual",
                linked_by="founder",
                relevance_score=900,
            )
        await ensure_knowledge_topic_link(
            session,
            project_id=project.id,
            topic_id=related.id,
            target_type="knowledge_candidate",
            target_id=unrelated.candidate.id,
            link_method="manual",
            linked_by="founder",
        )
        unapproved = await session.scalar(
            select(KnowledgeCandidate).where(
                KnowledgeCandidate.status == "CANDIDATE",
                KnowledgeCandidate.project_id == project.id,
            )
        )
        assert unapproved is not None
        await ensure_knowledge_topic_link(
            session,
            project_id=project.id,
            topic_id=child.id,
            target_type="knowledge_candidate",
            target_id=unapproved.id,
            link_method="manual",
            linked_by="founder",
        )
        await ensure_knowledge_topic_link(
            session,
            project_id=project.id,
            topic_id=child.id,
            target_type="knowledge_candidate",
            target_id=vi_candidate.candidate.id,
            link_method="manual",
            linked_by="founder",
        )

        harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(root.id,),
            locale="en",
            as_of=T0 + timedelta(days=1),
            created_by="policy:k3-harvest",
            content_case_id=reusable.content_case.id,
        )
        assert harvest.requested_topic_ids_json == [str(root.id)]
        assert set(harvest.expanded_topic_ids_json) == {
            str(root.id),
            str(child.id),
            str(subtopic.id),
        }
        assert len(harvest.items_json) == 1
        item = harvest.items_json[0]
        assert isinstance(item, dict)
        assert item["candidate_id"] == str(reusable.candidate.id)
        assert item["freshness"]["state"] == "UNCLASSIFIED"  # type: ignore[index]
        scoped_links = item["scoped_topic_links"]
        assert isinstance(scoped_links, list)
        assert {link["topic_id"] for link in scoped_links} == {  # type: ignore[index]
            str(child.id),
            str(subtopic.id),
        }
        verify_knowledge_harvest_snapshot(harvest)

        replay = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(root.id,),
            locale="en",
            as_of=T0 + timedelta(days=1),
            created_by="policy:k3-harvest",
            content_case_id=reusable.content_case.id,
        )
        assert replay.id == harvest.id
        assert replay.snapshot_hash == harvest.snapshot_hash


@pytest.mark.asyncio
async def test_source_supersession_changes_same_as_of_harvest_to_stale() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await create_topic(session, project=project, key="fresh", node_type="topic")
        fixture = await create_candidate(
            session,
            project=project,
            locale="en",
            label="freshness",
        )
        await ensure_knowledge_topic_link(
            session,
            project_id=project.id,
            topic_id=topic.id,
            target_type="knowledge_candidate",
            target_id=fixture.candidate.id,
            link_method="manual",
            linked_by="founder",
        )
        policy = await ensure_freshness_policy(
            session,
            project_id=project.id,
            policy_key=f"k3-fast-{uuid4().hex}",
            version=1,
            freshness_class="fast",
            max_age_days=30,
            refresh_lead_days=5,
            created_by="founder",
            rationale="K3 freshness fixture",
        )
        await ensure_freshness_assignment(
            session,
            project_id=project.id,
            policy_id=policy.id,
            target_type="knowledge_candidate",
            target_id=fixture.candidate.id,
            assigned_by="founder",
            reason="K3 freshness fixture",
        )
        verification = await record_lineage_verification(
            session,
            project_id=project.id,
            target_type="knowledge_candidate",
            target_id=fixture.candidate.id,
            recorded_by="policy:k3-lineage",
            as_of=T0,
        )
        fixed_as_of = T0 + timedelta(days=3)
        before = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=fixed_as_of,
            created_by="policy:k3-harvest",
        )
        before_item = before.items_json[0]
        assert isinstance(before_item, dict)
        before_freshness = before_item["freshness"]
        assert isinstance(before_freshness, dict)
        assert before_freshness["state"] == "FRESH"
        assert before_freshness["verification_id"] == str(verification.id)

        await ingest_source_document(
            session,
            source_id=fixture.source.id,
            content_markdown=fixture.source_text + " Updated source version.",
            fetched_at=T0 + timedelta(days=2),
            reader="k3-test",
            provider="manual",
        )
        after = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=fixed_as_of,
            created_by="policy:k3-harvest",
        )
        after_item = after.items_json[0]
        assert isinstance(after_item, dict)
        after_freshness = after_item["freshness"]
        assert isinstance(after_freshness, dict)
        assert after_freshness["state"] == "STALE"
        assert after_freshness["reasons"] == ["source_superseded"]
        assert after.id != before.id
        assert after.snapshot_hash != before.snapshot_hash
        assert before_freshness["state"] == "FRESH"


@pytest.mark.asyncio
async def test_retired_intermediate_topic_stops_harvest_scope_traversal() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        root = await create_topic(session, project=project, key="root", node_type="pillar")
        middle = await create_topic(
            session,
            project=project,
            key="middle",
            node_type="cluster",
        )
        leaf = await create_topic(session, project=project, key="leaf", node_type="topic")
        await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=root.id,
            child_topic_id=middle.id,
            relation_type="contains",
            created_by="test",
        )
        await ensure_topic_edge(
            session,
            project_id=project.id,
            parent_topic_id=middle.id,
            child_topic_id=leaf.id,
            relation_type="contains",
            created_by="test",
        )
        fixture = await create_candidate(
            session,
            project=project,
            locale="en",
            label="retired-intermediate",
        )
        await ensure_knowledge_topic_link(
            session,
            project_id=project.id,
            topic_id=leaf.id,
            target_type="knowledge_candidate",
            target_id=fixture.candidate.id,
            link_method="manual",
            linked_by="founder",
        )
        middle.status = "retired"
        await session.flush()

        harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(root.id,),
            locale="en",
            as_of=T0 + timedelta(days=1),
            created_by="policy:k3-harvest",
        )
        assert harvest.expanded_topic_ids_json == [str(root.id)]
        assert harvest.items_json == []


@pytest.mark.asyncio
async def test_snapshot_verifier_detects_in_memory_hash_corruption() -> None:
    async with isolated_session() as session:
        project = await motgu_project(session)
        topic = await create_topic(session, project=project, key="hash", node_type="topic")
        harvest = await harvest_knowledge(
            session,
            project_id=project.id,
            root_topic_ids=(topic.id,),
            locale="en",
            as_of=T0,
            created_by="policy:k3-harvest",
        )
        original_hash = harvest.snapshot_hash
        harvest.snapshot_hash = "0" * 64
        with pytest.raises(ValueError, match="knowledge_harvest_snapshot_hash_mismatch"):
            verify_knowledge_harvest_snapshot(harvest)
        harvest.snapshot_hash = original_hash
