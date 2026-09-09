from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from evidence_set_helpers import create_locked_evidence_set
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.journal.research_handoff import (
    JournalResearchHandoff,
    JournalResearchHandoffError,
    originality_pack_snapshot_hash,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    NeedHypothesis,
    Project,
)
from app.modules.knowledge.models import OriginalityPack
from app.modules.research.contracts import ProductionResearchRequest
from app.modules.research.discovery.service import OpportunityHandoff
from app.modules.research.evidence.contracts import (
    EvidenceResearchRequest,
    EvidenceResearchResult,
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


async def _content_case(
    session: AsyncSession,
) -> tuple[Project, ContentCase, ContentOpportunity, NeedHypothesis]:
    project = Project(slug=f"ce05-handoff-{uuid4().hex[:12]}", name="MOTGU")
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
        missing_evidence_json=["direct buyer evidence"],
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
        motgu_material_refs_json=[],
        material_gaps_json=["direct buyer evidence"],
        existing_content_refs_json=[],
        what_is_actually_new="A bounded research handoff.",
        next_discovery_step="Review the evidence gap.",
        decision="CREATE",
        priority="NOW",
        reasons_json=["test"],
        suggested_content_type="journal",
        selected_by="founder",
        selected_at=datetime.now(UTC),
        selection_reason="Selected for the handoff test.",
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
        originality_statement="MOTGU-owned context remains separate from external evidence.",
        reader_before="Unsure whether an artwork price makes sense.",
        reader_after="Able to ask grounded questions about the work.",
        status="draft",
    )
    session.add(content_case)
    await session.flush()
    return project, content_case, opportunity, need


def _motgu_item() -> dict[str, object]:
    return {
        "type": "motgu_owned_material",
        "source_ref": "motgu:journal:price-context",
        "material": (
            "MOTGU explains price context through the actual work and the buyer's questions."
        ),
        "writer_use": "Give the reader a practical question to ask.",
        "guardrails": "Do not invent scarcity or a pricing formula.",
        "approval_ref": "approval:motgu:journal:price-context",
    }


class FakeDiscoveryWorkflow:
    def __init__(self, result: object) -> None:
        self.result = result
        self.run_calls: list[dict[str, object]] = []
        self.selection_calls: list[dict[str, object]] = []

    async def run(self, session: object, **kwargs: object) -> object:
        self.run_calls.append(kwargs)
        return self.result

    async def select_and_persist(self, session: object, result: object, **kwargs: object) -> object:
        self.selection_calls.append(kwargs)
        return result

    def handoff(self, result: object) -> OpportunityHandoff:
        return OpportunityHandoff(
            opportunity_id="opportunity-2",
            need_hypothesis_id="need-1",
            locale="en",
            signal_refs=("signal:1",),
            experiment_draft_id="experiment-2",
            persisted_content_opportunity_id="db-opportunity-2",
            persisted_need_hypothesis_id="db-need-1",
            persisted_content_experiment_id="db-experiment-2",
        )


class FakeEvidenceWorkflow:
    def __init__(self, result: EvidenceResearchResult) -> None:
        self.result = result
        self.calls = 0

    async def run(self, session: object, **kwargs: object) -> EvidenceResearchResult:
        self.calls += 1
        return self.result


@pytest.mark.asyncio
async def test_discovery_runs_only_for_an_explicit_gap_and_persists_the_plan() -> None:
    result = SimpleNamespace(research_gaps=["missing audience evidence"], artifact_ref="artifact-1")
    fake = FakeDiscoveryWorkflow(result)
    handoff = JournalResearchHandoff(discovery_workflow=fake)

    skipped = await handoff.run_discovery_research(
        None,
        research_gap_required=False,
    )
    assert skipped.result is None
    assert fake.run_calls == []

    request = object()
    ran = await handoff.run_discovery_research(
        None,
        research_gap_required=True,
        request=request,
    )
    assert ran.result is result
    assert ran.research_gaps == ("missing audience evidence",)
    assert fake.run_calls == [
        {
            "request": request,
            "run_id": None,
            "step_run_id": None,
            "persist_plan": True,
        }
    ]


@pytest.mark.asyncio
async def test_opportunity_handoff_requires_explicit_human_selection() -> None:
    selection = SimpleNamespace(
        selected_by="founder",
        reason="The second opportunity matches the selected question.",
        selected_at="2026-09-09T10:00:00+00:00",
    )
    result = SimpleNamespace(
        planning_refs=object(),
        opportunity_map=SimpleNamespace(human_selection=selection),
    )
    fake = FakeDiscoveryWorkflow(result)
    handoff = JournalResearchHandoff(discovery_workflow=fake)

    selected = await handoff.select_opportunity(
        None,
        result=result,
        opportunity_id="opportunity-2",
        selected_by="founder",
        reason=selection.reason,
    )

    assert selected.opportunity_id == "opportunity-2"
    assert selected.selected_by == "founder"
    assert selected.selection_reason == selection.reason
    assert selected.selected_at == selection.selected_at
    assert fake.selection_calls == [
        {
            "opportunity_id": "opportunity-2",
            "selected_by": "founder",
            "reason": selection.reason,
        }
    ]

    with pytest.raises(JournalResearchHandoffError, match="opportunity_selection_id_required"):
        await handoff.select_opportunity(
            None,
            result=result,
            opportunity_id=" ",
            selected_by="founder",
            reason="reason",
        )


@pytest.mark.asyncio
async def test_evidence_research_handoff_requires_exact_approved_locked_snapshot() -> None:
    async with isolated_session() as session:
        project, content_case, _opportunity, need = await _content_case(session)
        evidence_set = await create_locked_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=[str(uuid4())],
            locked_by="evidence reviewer",
        )
        pack = OriginalityPack(
            content_case_id=content_case.id,
            item_refs_json=[_motgu_item()],
            summary="MOTGU-owned material is available.",
            status="draft",
        )
        session.add(pack)
        await session.flush()

        result = EvidenceResearchResult(
            research=None,  # type: ignore[arg-type]
            content_case_id=content_case.id,
            evidence_set_id=evidence_set.id,
            evidence_set_version=evidence_set.version,
            evidence_set_content_hash=evidence_set.content_hash,
            evidence_set_status="locked",
            originality_pack_id=pack.id,
        )
        fake = FakeEvidenceWorkflow(result)
        handoff = JournalResearchHandoff(evidence_workflow=fake)
        request = EvidenceResearchRequest(
            research=ProductionResearchRequest(
                project_id=project.id,
                query="artwork price context",
            ),
            content_opportunity_id=_opportunity.id,
            need_hypothesis_id=need.id,
            lock_evidence_set=True,
            locked_by="evidence reviewer",
        )

        research_handoff = await handoff.run_evidence_research(session, request=request)
        assert fake.calls == 1
        assert research_handoff.evidence_set.evidence_set_id == evidence_set.id
        assert research_handoff.evidence_set.version == evidence_set.version
        assert research_handoff.evidence_set.content_hash == evidence_set.content_hash
        assert research_handoff.originality_pack.originality_pack_id == pack.id

        with pytest.raises(
            JournalResearchHandoffError,
            match="evidence_set_snapshot_hash_mismatch",
        ):
            await handoff.handoff_evidence_set(
                session,
                project_id=project.id,
                content_case_id=content_case.id,
                evidence_set_id=evidence_set.id,
                expected_version=evidence_set.version,
                expected_content_hash="0" * 64,
            )


@pytest.mark.asyncio
async def test_originality_pack_gate_requires_nonempty_motgu_material_and_exact_refs() -> None:
    async with isolated_session() as session:
        project, content_case, _opportunity, _need = await _content_case(session)
        item = _motgu_item()
        pack = OriginalityPack(
            content_case_id=content_case.id,
            item_refs_json=[item],
            summary="MOTGU-owned material is available.",
            status="draft",
        )
        empty_pack = OriginalityPack(
            content_case_id=content_case.id,
            item_refs_json=[],
            summary="Originality gap.",
            status="draft",
        )
        session.add_all([pack, empty_pack])
        await session.flush()
        handoff = JournalResearchHandoff()

        valid = await handoff.handoff_originality_pack(
            session,
            content_case_id=content_case.id,
            originality_pack_id=pack.id,
            expected_item_refs=[item],
        )
        assert valid.item_refs == (item,)
        assert valid.snapshot_hash == originality_pack_snapshot_hash(pack)

        with pytest.raises(
            JournalResearchHandoffError,
            match="originality_pack_motgu_material_required",
        ):
            await handoff.handoff_originality_pack(
                session,
                content_case_id=content_case.id,
                originality_pack_id=empty_pack.id,
            )

        with pytest.raises(JournalResearchHandoffError, match="originality_pack_refs_mismatch"):
            await handoff.handoff_originality_pack(
                session,
                content_case_id=content_case.id,
                originality_pack_id=pack.id,
                expected_item_refs=[{"type": "reference_only", "source_ref": "motgu:old"}],
            )


@pytest.mark.asyncio
async def test_discovery_gap_without_request_fails_closed() -> None:
    with pytest.raises(
        JournalResearchHandoffError,
        match="discovery_request_required_for_research_gap",
    ):
        await JournalResearchHandoff().run_discovery_research(
            None,
            research_gap_required=True,
        )
