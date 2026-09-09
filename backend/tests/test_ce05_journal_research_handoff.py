from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from evidence_set_helpers import create_locked_evidence_set
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.journal.research_handoff import (
    EvidenceSetHandoff,
    JournalResearchHandoff,
    JournalResearchHandoffError,
    ResearchDecision,
    originality_pack_snapshot_hash,
    select_research_decision,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    NeedHypothesis,
    Project,
)
from app.modules.harness.models import Artifact, ContentRun, StepRun
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    EvidenceSet,
    EvidenceSetApproval,
    OriginalityPack,
    Source,
    SourceDocument,
)
from app.modules.knowledge.originality_pack import approve_originality_pack
from app.modules.knowledge.persistence import content_hash, evidence_set_hash
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


class HistoricalLockedEvidenceSession:
    def __init__(self, evidence_set: EvidenceSet, evidence_rows: list[Evidence]) -> None:
        self.evidence_set = evidence_set
        self.evidence_rows = evidence_rows

    async def get(self, model: object, object_id: UUID) -> object | None:
        if model is EvidenceSet and object_id == self.evidence_set.id:
            return self.evidence_set
        return None

    async def scalars(self, query: object) -> SimpleNamespace:
        entity = getattr(query, "column_descriptions", [{}])[0].get("entity")
        rows = self.evidence_rows if entity is Evidence else []
        return SimpleNamespace(all=lambda: rows)


async def _evidence_row(session: AsyncSession, *, project_id: UUID, suffix: str = "") -> Evidence:
    source = Source(
        project_id=project_id,
        source_type="web",
        title="Synthetic evidence source",
        canonical_url=f"https://example.test/evidence/{uuid4()}",
        locale="en",
        provenance_json={"fixture": "ce05"},
        captured_at=datetime.now(UTC),
        fingerprint=f"ce05-evidence-source-{uuid4().hex}",
    )
    session.add(source)
    await session.flush()
    evidence_text = f"Synthetic evidence {suffix or uuid4().hex}."
    document = SourceDocument(
        source_id=source.id,
        document_version=1,
        canonical_url=source.canonical_url,
        fetched_at=datetime.now(UTC),
        content_hash=content_hash(evidence_text),
        content_markdown=evidence_text,
        metadata_json={"fixture": "ce05"},
        reader="fixture",
        provider="fixture",
    )
    claim = Claim(
        project_id=project_id,
        statement=f"CE05 synthetic evidence {suffix or uuid4().hex}",
        claim_type="fact",
        entity_refs_json=[],
    )
    session.add_all([document, claim])
    await session.flush()
    evidence = Evidence(
        claim_id=claim.id,
        source_document_id=document.id,
        locator="fixture:1",
        excerpt=evidence_text,
        relation="supports",
        quality_metadata_json={"fixture": True},
        provenance_json={
            "source_id": str(source.id),
            "source_document_id": str(document.id),
        },
    )
    session.add(evidence)
    await session.flush()
    return evidence


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
        evidence = await _evidence_row(session, project_id=project.id)
        evidence_set = await create_locked_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=[str(evidence.id)],
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
        await approve_originality_pack(
            session,
            originality_pack_id=pack.id,
            expected_snapshot_hash=originality_pack_snapshot_hash(pack),
            approved_by="originality reviewer",
            approval_reason="Approved synthetic MOTGU-owned material.",
        )

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
        assert research_handoff.evidence_set.evidence_ids == (evidence.id,)
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
async def test_originality_pack_gate_blocks_draft_and_accepts_exact_approval() -> None:
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
        retired_pack = OriginalityPack(
            content_case_id=content_case.id,
            item_refs_json=[item],
            summary="Retired material.",
            status="retired",
        )
        session.add_all([pack, empty_pack, retired_pack])
        await session.flush()
        handoff = JournalResearchHandoff()

        with pytest.raises(
            JournalResearchHandoffError,
            match="originality_pack_approval_required",
        ):
            await handoff.handoff_originality_pack(
                session,
                content_case_id=content_case.id,
                originality_pack_id=pack.id,
            )
        with pytest.raises(JournalResearchHandoffError, match="originality_pack_retired"):
            await handoff.handoff_originality_pack(
                session,
                content_case_id=content_case.id,
                originality_pack_id=retired_pack.id,
            )

        await approve_originality_pack(
            session,
            originality_pack_id=pack.id,
            expected_snapshot_hash=originality_pack_snapshot_hash(pack),
            approved_by="originality reviewer",
            approval_reason="Approved synthetic MOTGU-owned material.",
        )
        assert pack.approved_by == "originality reviewer"
        assert pack.approval_reason == "Approved synthetic MOTGU-owned material."
        assert pack.snapshot_hash == originality_pack_snapshot_hash(pack)
        valid = await handoff.handoff_originality_pack(
            session,
            content_case_id=content_case.id,
            originality_pack_id=pack.id,
            expected_item_refs=[item],
        )
        assert valid.item_refs == (item,)
        assert valid.snapshot_hash == originality_pack_snapshot_hash(pack)

        with pytest.raises(JournalResearchHandoffError, match="originality_pack_approval_required"):
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


async def _approved_pack(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    item_refs: list[object] | None = None,
) -> OriginalityPack:
    pack = OriginalityPack(
        content_case_id=content_case_id,
        item_refs_json=[_motgu_item()] if item_refs is None else item_refs,
        summary="MOTGU-owned material is available.",
        status="draft",
    )
    session.add(pack)
    await session.flush()
    await approve_originality_pack(
        session,
        originality_pack_id=pack.id,
        expected_snapshot_hash=originality_pack_snapshot_hash(pack),
        approved_by="originality reviewer",
        approval_reason="Approved synthetic MOTGU-owned material.",
    )
    return pack


async def _run_and_step(
    session: AsyncSession,
    *,
    project: Project,
    content_case: ContentCase,
) -> tuple[ContentRun, StepRun]:
    from app.modules.content_engine.models import LocaleVariant, SettingsSnapshot

    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="primary",
        primary_question="How should a buyer evaluate an artwork price?",
        primary_intent="evaluate",
    )
    settings = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={"test": True},
        source_version_refs_json=["test:ce05"],
        content_hash=content_hash("ce05-journal-input-settings"),
    )
    session.add_all([variant, settings])
    await session.flush()
    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        run_mode="create",
        status="running",
        current_step="journal_input_bundle",
        settings_snapshot_id=settings.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    step = StepRun(
        run_id=run.id,
        step_key="journal_input_bundle",
        attempt=1,
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add(step)
    await session.flush()
    return run, step


@pytest.mark.asyncio
async def test_historical_locked_evidence_set_without_retrofit_approval_passes() -> None:
    project_id = uuid4()
    content_case_id = uuid4()
    evidence_ids = [str(uuid4())]
    evidence_set = EvidenceSet(
        id=uuid4(),
        project_id=project_id,
        content_case_id=content_case_id,
        version=1,
        evidence_ids_json=evidence_ids,
        content_hash=evidence_set_hash(evidence_ids),
        status="locked",
        locked_at=datetime.now(UTC),
        locked_by=None,
    )
    evidence = Evidence(id=UUID(evidence_ids[0]))
    handoff = await JournalResearchHandoff().handoff_evidence_set(
        HistoricalLockedEvidenceSession(evidence_set, [evidence]),
        project_id=project_id,
        content_case_id=content_case_id,
        evidence_set_id=evidence_set.id,
        expected_version=evidence_set.version,
        expected_content_hash=evidence_set.content_hash,
    )
    assert handoff.approval_id is None
    assert handoff.approved_by is None


@pytest.mark.asyncio
async def test_evidence_set_gate_rejects_draft_and_stale_snapshot() -> None:
    async with isolated_session() as session:
        project, content_case, _opportunity, _need = await _content_case(session)
        evidence = await _evidence_row(session, project_id=project.id)
        evidence_ids = [str(uuid4())]
        evidence_set = EvidenceSet(
            project_id=project.id,
            content_case_id=content_case.id,
            version=1,
            evidence_ids_json=evidence_ids,
            content_hash=evidence_set_hash(evidence_ids),
            status="draft",
        )
        session.add(evidence_set)
        await session.flush()
        handoff = JournalResearchHandoff()
        with pytest.raises(JournalResearchHandoffError, match="evidence_set_must_be_locked"):
            await handoff.handoff_evidence_set(
                session,
                project_id=project.id,
                content_case_id=content_case.id,
                evidence_set_id=evidence_set.id,
                expected_version=evidence_set.version,
                expected_content_hash=evidence_set.content_hash,
            )

        evidence_set = await create_locked_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=[str(evidence.id)],
            version=2,
        )
        original_hash = evidence_set.content_hash
        evidence_set.evidence_ids_json = [str(uuid4())]
        with pytest.raises(JournalResearchHandoffError, match="evidence_set_snapshot_stale"):
            with session.no_autoflush:
                await handoff.handoff_evidence_set(
                    session,
                    project_id=project.id,
                    content_case_id=content_case.id,
                    evidence_set_id=evidence_set.id,
                    expected_version=evidence_set.version,
                    expected_content_hash=original_hash,
                )


@pytest.mark.asyncio
async def test_evidence_set_gate_accepts_exact_approval_and_rejects_wrong_lineage() -> None:
    async with isolated_session() as session:
        project, content_case, _opportunity, _need = await _content_case(session)
        evidence = await _evidence_row(session, project_id=project.id)
        evidence_set = await create_locked_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=[str(evidence.id)],
        )
        handoff = JournalResearchHandoff()
        valid = await handoff.handoff_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_set_id=evidence_set.id,
            expected_version=evidence_set.version,
            expected_content_hash=evidence_set.content_hash,
        )
        assert valid.approval_id is not None

        wrong_approval = EvidenceSetApproval(
            evidence_set_id=evidence_set.id,
            evidence_set_version=evidence_set.version + 1,
            evidence_set_content_hash="f" * 64,
            approved_by="wrong reviewer",
            approval_reason="Wrong historical snapshot.",
            approved_at=datetime.now(UTC),
        )
        session.add(wrong_approval)
        await session.flush()
        with pytest.raises(
            JournalResearchHandoffError,
            match="evidence_set_approval_snapshot_mismatch",
        ):
            await handoff.handoff_evidence_set(
                session,
                project_id=project.id,
                content_case_id=content_case.id,
                evidence_set_id=evidence_set.id,
                expected_version=evidence_set.version,
                expected_content_hash=evidence_set.content_hash,
            )


@pytest.mark.asyncio
async def test_evidence_set_gate_rejects_missing_member() -> None:
    async with isolated_session() as session:
        project, content_case, _opportunity, _need = await _content_case(session)
        evidence = await _evidence_row(session, project_id=project.id, suffix="present")
        evidence_ids = [str(evidence.id), str(uuid4())]
        evidence_set = await create_locked_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=evidence_ids,
        )

        with pytest.raises(JournalResearchHandoffError, match="evidence_set_member_missing"):
            await JournalResearchHandoff().handoff_evidence_set(
                session,
                project_id=project.id,
                content_case_id=content_case.id,
                evidence_set_id=evidence_set.id,
                expected_version=evidence_set.version,
                expected_content_hash=evidence_set.content_hash,
            )


@pytest.mark.asyncio
async def test_evidence_set_gate_rejects_malformed_member_id() -> None:
    async with isolated_session() as session:
        project, content_case, _opportunity, _need = await _content_case(session)
        evidence_ids = ["not-a-uuid"]
        evidence_set = await create_locked_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=evidence_ids,
        )

        with pytest.raises(JournalResearchHandoffError, match="evidence_set_snapshot_invalid"):
            await JournalResearchHandoff().handoff_evidence_set(
                session,
                project_id=project.id,
                content_case_id=content_case.id,
                evidence_set_id=evidence_set.id,
                expected_version=evidence_set.version,
                expected_content_hash=evidence_set.content_hash,
            )


@pytest.mark.asyncio
async def test_evidence_set_gate_rejects_duplicate_member_id() -> None:
    async with isolated_session() as session:
        project, content_case, _opportunity, _need = await _content_case(session)
        evidence = await _evidence_row(session, project_id=project.id)
        evidence_ids = [str(evidence.id), str(evidence.id)]
        evidence_set = await create_locked_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=evidence_ids,
        )

        with pytest.raises(JournalResearchHandoffError, match="evidence_set_member_duplicate"):
            await JournalResearchHandoff().handoff_evidence_set(
                session,
                project_id=project.id,
                content_case_id=content_case.id,
                evidence_set_id=evidence_set.id,
                expected_version=evidence_set.version,
                expected_content_hash=evidence_set.content_hash,
            )


@pytest.mark.asyncio
async def test_approved_originality_pack_mutation_fails_closed() -> None:
    async with isolated_session() as session:
        _project, content_case, _opportunity, _need = await _content_case(session)
        pack = await _approved_pack(session, content_case_id=content_case.id)
        tampered_item = _motgu_item()
        tampered_item["material"] = "Tampered material snapshot."
        pack.item_refs_json = [tampered_item]
        with pytest.raises(JournalResearchHandoffError, match="originality_pack_snapshot_stale"):
            await JournalResearchHandoff().handoff_originality_pack(
                session,
                content_case_id=content_case.id,
                originality_pack_id=pack.id,
            )


@pytest.mark.asyncio
async def test_database_rejects_mutation_of_approved_originality_pack() -> None:
    async with isolated_session() as session:
        _project, content_case, _opportunity, _need = await _content_case(session)
        pack = await _approved_pack(session, content_case_id=content_case.id)
        with pytest.raises(DBAPIError, match="approved_originality_pack_is_immutable"):
            async with session.begin_nested():
                await session.execute(
                    update(OriginalityPack)
                    .where(OriginalityPack.id == pack.id)
                    .values(summary="Tampered in SQL")
                )


@pytest.mark.asyncio
async def test_research_decision_is_bounded() -> None:
    assert select_research_decision(
        research_gap_required=False,
        opportunity_selected=True,
        evidence_set_ready=True,
        originality_pack_ready=True,
    ) is ResearchDecision.REUSE_EXISTING
    assert select_research_decision(
        research_gap_required=True,
        opportunity_selected=True,
        evidence_set_ready=True,
        originality_pack_ready=True,
    ) is ResearchDecision.RESEARCH_REQUIRED
    assert select_research_decision(
        research_gap_required=False,
        opportunity_selected=False,
        evidence_set_ready=True,
        originality_pack_ready=True,
    ) is ResearchDecision.BLOCKED


@pytest.mark.asyncio
async def test_journal_input_bundle_is_idempotent_and_reuse_has_zero_calls() -> None:
    async with isolated_session() as session:
        project, content_case, opportunity, _need = await _content_case(session)
        evidence = await _evidence_row(session, project_id=project.id)
        evidence_set = await create_locked_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=[str(evidence.id)],
        )
        pack = await _approved_pack(session, content_case_id=content_case.id)
        run, step = await _run_and_step(session, project=project, content_case=content_case)
        handoff = JournalResearchHandoff()
        evidence_handoff = await handoff.handoff_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_set_id=evidence_set.id,
            expected_version=evidence_set.version,
            expected_content_hash=evidence_set.content_hash,
        )
        pack_handoff = await handoff.handoff_originality_pack(
            session,
            content_case_id=content_case.id,
            originality_pack_id=pack.id,
        )
        first = await handoff.persist_journal_input_bundle(
            session,
            run_id=run.id,
            step_run_id=step.id,
            research_decision=ResearchDecision.REUSE_EXISTING,
            opportunity_id=opportunity.id,
            evidence_set=evidence_handoff,
            originality_pack=pack_handoff,
            provider_calls=0,
            model_calls=0,
        )
        second = await handoff.persist_journal_input_bundle(
            session,
            run_id=run.id,
            step_run_id=step.id,
            research_decision="REUSE_EXISTING",
            opportunity_id=opportunity.id,
            evidence_set=evidence_handoff,
            originality_pack=pack_handoff,
            provider_calls=0,
            model_calls=0,
        )
        assert first.id == second.id
        assert first.content_hash == second.content_hash
        assert first.content_json["research_decision"] == "REUSE_EXISTING"
        assert first.content_json["provider_calls"] == 0
        assert first.content_json["model_calls"] == 0
        assert len(
            (
                await session.scalars(
                    select(Artifact).where(
                        Artifact.run_id == run.id,
                        Artifact.artifact_type == "journal_input_bundle",
                    )
                )
            ).all()
        ) == 1
        assert step.output_artifact_refs_json == [str(first.id)]


@pytest.mark.asyncio
async def test_invalid_evidence_set_member_does_not_create_input_bundle() -> None:
    async with isolated_session() as session:
        project, content_case, opportunity, _need = await _content_case(session)
        evidence = await _evidence_row(session, project_id=project.id, suffix="present")
        evidence_ids = [str(evidence.id), str(uuid4())]
        evidence_set = await create_locked_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=evidence_ids,
        )
        pack = await _approved_pack(session, content_case_id=content_case.id)
        run, step = await _run_and_step(session, project=project, content_case=content_case)
        handoff = JournalResearchHandoff()
        pack_handoff = await handoff.handoff_originality_pack(
            session,
            content_case_id=content_case.id,
            originality_pack_id=pack.id,
        )
        evidence_handoff = EvidenceSetHandoff(
            evidence_set_id=evidence_set.id,
            project_id=project.id,
            content_case_id=content_case.id,
            version=evidence_set.version,
            content_hash=evidence_set.content_hash,
            evidence_ids=(evidence.id, UUID(evidence_ids[1])),
            approval_id=None,
            approved_by=None,
        )

        with pytest.raises(JournalResearchHandoffError, match="evidence_set_member_missing"):
            await handoff.persist_journal_input_bundle(
                session,
                run_id=run.id,
                step_run_id=step.id,
                research_decision=ResearchDecision.REUSE_EXISTING,
                opportunity_id=opportunity.id,
                evidence_set=evidence_handoff,
                originality_pack=pack_handoff,
                provider_calls=0,
                model_calls=0,
            )

        assert (
            await session.scalar(
                select(func.count(Artifact.id)).where(
                    Artifact.run_id == run.id,
                    Artifact.artifact_type == "journal_input_bundle",
                )
            )
            == 0
        )
        assert step.output_artifact_refs_json == []


@pytest.mark.asyncio
async def test_journal_input_bundle_rejects_blocked_and_mutated_approved_pack() -> None:
    async with isolated_session() as session:
        project, content_case, opportunity, _need = await _content_case(session)
        evidence = await _evidence_row(session, project_id=project.id)
        evidence_set = await create_locked_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_ids=[str(evidence.id)],
        )
        pack = await _approved_pack(session, content_case_id=content_case.id)
        run, step = await _run_and_step(session, project=project, content_case=content_case)
        handoff = JournalResearchHandoff()
        evidence_handoff = await handoff.handoff_evidence_set(
            session,
            project_id=project.id,
            content_case_id=content_case.id,
            evidence_set_id=evidence_set.id,
            expected_version=evidence_set.version,
            expected_content_hash=evidence_set.content_hash,
        )
        pack_handoff = await handoff.handoff_originality_pack(
            session,
            content_case_id=content_case.id,
            originality_pack_id=pack.id,
        )
        with pytest.raises(JournalResearchHandoffError, match="journal_input_bundle_blocked"):
            await handoff.persist_journal_input_bundle(
                session,
                run_id=run.id,
                step_run_id=step.id,
                research_decision=ResearchDecision.BLOCKED,
                opportunity_id=opportunity.id,
                evidence_set=evidence_handoff,
                originality_pack=pack_handoff,
                provider_calls=0,
                model_calls=0,
            )
        tampered_item = _motgu_item()
        tampered_item["material"] = "Tampered material snapshot."
        pack.item_refs_json = [tampered_item]
        with pytest.raises(JournalResearchHandoffError, match="originality_pack_snapshot_stale"):
            with session.no_autoflush:
                await handoff.persist_journal_input_bundle(
                    session,
                    run_id=run.id,
                    step_run_id=step.id,
                    research_decision=ResearchDecision.REUSE_EXISTING,
                    opportunity_id=opportunity.id,
                    evidence_set=evidence_handoff,
                    originality_pack=pack_handoff,
                    provider_calls=0,
                    model_calls=0,
                )
