from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import NeedHypothesis, Project, Signal
from app.modules.customer_intelligence.intake import (
    CustomerInsightCandidateInput,
    CustomerInsightIntakeError,
    persist_customer_insight_candidate,
)
from app.modules.customer_intelligence.models import (
    CustomerInsightNeedLink,
    CustomerInsightSignal,
)
from app.modules.knowledge.models import Claim, Evidence, SourceDocument
from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    PageDocument,
    ProductionResearchRequest,
    ProductionResearchResult,
    ResearchSignalKind,
    SearchSignal,
    SourceCandidate,
)
from app.modules.research.discovery import (
    DiscoveryResearchWorkflow,
    DiscoveryWorkflowRequest,
)
from app.modules.research.keyword_plan.contracts import NeedType
from app.modules.research.keyword_plan.service import OpportunityMapRequest


@asynccontextmanager
async def isolated_session():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


async def _project(session: AsyncSession, label: str) -> Project:
    project = Project(
        slug=f"{label}-{uuid4().hex[:8]}",
        name=label,
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


async def _signal(
    session: AsyncSession,
    *,
    project_id: UUID,
    text: str,
) -> Signal:
    signal = Signal(
        project_id=project_id,
        source_kind="MARKET",
        scope="market_web",
        observed_text=text,
        source_url=f"https://example.com/{uuid4().hex}",
        locale="en",
        context="E2E-01 intake fixture",
        captured_at=datetime.now(UTC),
        fingerprint=uuid4().hex,
        provenance_json={"provider": "fixture", "method": "reviewed_observation"},
    )
    session.add(signal)
    await session.flush()
    return signal


@pytest.mark.asyncio
async def test_customer_insight_intake_is_explicit_idempotent_and_never_promotes() -> None:
    async with isolated_session() as session:
        project = await _project(session, "e2e-intake")
        signal = await _signal(
            session,
            project_id=project.id,
            text="I want enough context to understand the price before deciding.",
        )
        need = NeedHypothesis(
            project_id=project.id,
            type="question",
            statement="A first-time buyer wants price context before deciding.",
            audience_scope="first-time art buyer",
            situation="considering an original artwork",
            origin="founder_proposed",
            status="PROPOSED",
            alternative_explanations_json=[],
            missing_evidence_json=[],
        )
        session.add(need)
        await session.flush()

        request = CustomerInsightCandidateInput(
            insight_type="question",
            statement=(
                "A first-time buyer may need understandable price context before "
                "deciding on an original artwork."
            ),
            situation="considering an original artwork",
            support_signal_ids=(signal.id,),
            alternative_explanations=(
                "The question may reflect comparison behaviour rather than purchase anxiety.",
            ),
            missing_evidence=("Direct MOTGU customer evidence is still limited.",),
            need_hypothesis_id=need.id,
            need_relation="supports",
            linked_by="founder",
            link_reason="Explicitly link the candidate interpretation to this proposed need.",
        )

        first = await persist_customer_insight_candidate(
            session,
            project_id=project.id,
            request=request,
        )
        replay = await persist_customer_insight_candidate(
            session,
            project_id=project.id,
            request=request,
        )

        assert replay.insight.id == first.insight.id
        assert first.replayed is False
        assert replay.replayed is True
        assert first.insight.status == "CANDIDATE"
        assert first.insight.reviewed_by is None
        assert first.insight.reviewed_at is None

        signal_link = await session.get(
            CustomerInsightSignal,
            (first.insight.id, signal.id),
        )
        need_link = await session.get(
            CustomerInsightNeedLink,
            (first.insight.id, need.id),
        )
        assert signal_link is not None
        assert signal_link.relation == "supports"
        assert need_link is not None
        assert need_link.relation == "supports"


@pytest.mark.asyncio
async def test_customer_insight_intake_fails_closed_on_ambiguous_or_foreign_signals() -> None:
    async with isolated_session() as session:
        project = await _project(session, "e2e-intake")
        other = await _project(session, "e2e-other")
        signal = await _signal(
            session,
            project_id=project.id,
            text="Price context question.",
        )
        foreign = await _signal(
            session,
            project_id=other.id,
            text="Foreign project question.",
        )

        with pytest.raises(
            CustomerInsightIntakeError,
            match="customer_insight_intake_signal_required",
        ):
            await persist_customer_insight_candidate(
                session,
                project_id=project.id,
                request=CustomerInsightCandidateInput(
                    insight_type="question",
                    statement="No evidence must not create an insight candidate.",
                ),
            )

        with pytest.raises(
            CustomerInsightIntakeError,
            match="customer_insight_intake_signal_relation_conflict",
        ):
            await persist_customer_insight_candidate(
                session,
                project_id=project.id,
                request=CustomerInsightCandidateInput(
                    insight_type="question",
                    statement="One signal cannot have conflicting relations.",
                    support_signal_ids=(signal.id,),
                    context_signal_ids=(signal.id,),
                ),
            )

        with pytest.raises(
            CustomerInsightIntakeError,
            match="customer_insight_intake_signal_project_mismatch",
        ):
            await persist_customer_insight_candidate(
                session,
                project_id=project.id,
                request=CustomerInsightCandidateInput(
                    insight_type="question",
                    statement="Foreign evidence must fail closed.",
                    support_signal_ids=(foreign.id,),
                ),
            )


class StubRouter:
    def __init__(self, result: ProductionResearchResult) -> None:
        self.result = result

    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> ProductionResearchResult:
        del session, run_id, step_run_id
        assert request is self.result.request
        return self.result


@pytest.mark.asyncio
async def test_discovery_persists_read_page_as_raw_source_without_creating_evidence() -> None:
    async with isolated_session() as session:
        project = await _project(session, "e2e-discovery")
        suffix = uuid4().hex
        query = f"first artwork price confidence {suffix}"
        source_url = f"https://research.example/{suffix}"
        question = f"How do I understand an original artwork price {suffix}?"

        research_request = ProductionResearchRequest(
            project_id=project.id,
            query=query,
            locale="en",
            max_pages_to_read=1,
        )
        candidate = SourceCandidate(
            provider="serper",
            query=query,
            url=source_url,
            title="First buyer price context",
            snippet=question,
            source_type="editorial",
            commercial_bias=CommercialBias.LOW,
            intended_use=IntendedUse.DISCOVERY,
        )
        production = ProductionResearchResult(
            request=research_request,
            signals=[
                SearchSignal(
                    provider="serper",
                    query=query,
                    kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                    text=question,
                    url=source_url,
                    snippet=question,
                    position=1,
                )
            ],
            source_candidates=[candidate],
            selected_sources=[candidate],
            documents=[
                PageDocument(
                    provider="jina",
                    url=source_url,
                    requested_url=source_url,
                    final_url=source_url,
                    title="First buyer price context",
                    content=f"{question}\nA longer page body for a raw Discovery source.",
                )
            ],
            sufficient=True,
            stop_reason="synthetic_discovery_complete",
        )
        workflow = DiscoveryResearchWorkflow(router=StubRouter(production))
        request = DiscoveryWorkflowRequest(
            research=research_request,
            opportunity=OpportunityMapRequest(
                project_id=project.slug,
                locale="en",
                audience_scope="first-time art buyer",
                situation="considering an original artwork",
                reader="first-time art buyer",
                need_statement=f"Understand original artwork price context {suffix}",
                need_type=NeedType.QUESTION,
            ),
        )

        source_documents_before = int(
            await session.scalar(select(func.count()).select_from(SourceDocument))
        )
        claims_before = int(await session.scalar(select(func.count()).select_from(Claim)))
        evidence_before = int(
            await session.scalar(select(func.count()).select_from(Evidence))
        )

        result = await workflow.run(session, request=request, persist_plan=True)

        assert result.planning_refs is not None
        source_documents_after = int(
            await session.scalar(select(func.count()).select_from(SourceDocument))
        )
        claims_after = int(await session.scalar(select(func.count()).select_from(Claim)))
        evidence_after = int(
            await session.scalar(select(func.count()).select_from(Evidence))
        )
        assert source_documents_after == source_documents_before + 1
        assert claims_after == claims_before
        assert evidence_after == evidence_before

        signal_id = next(iter(result.planning_refs.signal_ids.values()))
        signal = await session.get(Signal, signal_id)
        assert signal is not None
        assert signal.provenance_json["provider"] == "serper"
        assert signal.provenance_json["source_document_id"]
        source_document = await session.get(
            SourceDocument,
            UUID(str(signal.provenance_json["source_document_id"])),
        )
        assert source_document is not None
        assert source_document.canonical_url == source_url
        assert source_document.metadata_json["raw_source_only"] is True
