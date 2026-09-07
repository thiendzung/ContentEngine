from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentOpportunity,
    ContentOpportunitySignal,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.harness.models import ContentRun
from app.modules.research.contracts import (
    ProductionResearchRequest,
    ProductionResearchResult,
    ResearchSignalKind,
    SearchSignal,
    utc_now_iso,
)
from app.modules.research.discovery import DiscoveryResearchWorkflow, DiscoveryWorkflowRequest
from app.modules.research.keyword_plan.contracts import (
    NeedType,
    SignalScope,
    SignalSourceKind,
)
from app.modules.research.keyword_plan.normalize import make_observed_signal
from app.modules.research.keyword_plan.service import OpportunityMapRequest


class PlanningRouter:
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
async def test_pre_content_discovery_persists_planning_spine_without_content_run() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            project = (
                await session.execute(select(Project).where(Project.slug == "motgu"))
            ).scalar_one()
            suffix = uuid4().hex
            query = f"first art purchase confidence {suffix}"
            request = ProductionResearchRequest(
                project_id=project.id,
                query=query,
                locale="en",
                max_pages_to_read=0,
            )
            production = ProductionResearchResult(
                request=request,
                signals=[
                    SearchSignal(
                        provider="serper",
                        query=query,
                        kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                        text=f"How do I choose my first painting {suffix}?",
                    ),
                    SearchSignal(
                        provider="serper",
                        query=query,
                        kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                        text=f"How much should my first painting cost {suffix}?",
                    ),
                    SearchSignal(
                        provider="serper",
                        query=query,
                        kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                        text=f"How do I know original art is right for me {suffix}?",
                    ),
                ],
                sufficient=True,
                stop_reason="serper_sufficient",
            )
            repeated_market_text = f"I worried about choosing the wrong artwork {suffix}."
            captured_at = utc_now_iso()
            market_a = make_observed_signal(
                source_kind=SignalSourceKind.MARKET,
                scope=SignalScope.MARKET_WEB,
                observed_text=repeated_market_text,
                locale="en",
                provider="jina",
                method="read_observation",
                context="community thread A",
                captured_at=captured_at,
                source_url=f"https://community.example/a/{suffix}",
                locator="comment:a",
            )
            market_b = make_observed_signal(
                source_kind=SignalSourceKind.MARKET,
                scope=SignalScope.MARKET_WEB,
                observed_text=repeated_market_text,
                locale="en",
                provider="jina",
                method="read_observation",
                context="repost thread B",
                captured_at=captured_at,
                source_url=f"https://community.example/b/{suffix}",
                locator="comment:b",
            )
            workflow = DiscoveryResearchWorkflow(router=PlanningRouter(production))
            workflow_request = DiscoveryWorkflowRequest(
                research=request,
                opportunity=OpportunityMapRequest(
                    project_id="motgu",
                    locale="en",
                    audience_scope="international first-time art buyer",
                    situation="considering an original artwork",
                    reader="international first-time art buyer",
                    need_statement=f"Choose a first original artwork with confidence {suffix}",
                    need_type=NeedType.QUESTION,
                    extra_signals=(market_a, market_b),
                ),
            )
            runs_before = await session.scalar(select(func.count()).select_from(ContentRun))

            first = await workflow.run(
                session,
                request=workflow_request,
                persist_plan=True,
            )
            second = await workflow.run(
                session,
                request=workflow_request,
                persist_plan=True,
            )

            assert first.planning_refs is not None
            assert second.planning_refs is not None
            assert first.planning_refs.need_hypothesis_id == second.planning_refs.need_hypothesis_id
            assert first.planning_refs.signal_ids == second.planning_refs.signal_ids
            assert first.planning_refs.opportunity_ids == second.planning_refs.opportunity_ids

            hypothesis = await session.get(
                NeedHypothesis,
                first.planning_refs.need_hypothesis_id,
            )
            assert hypothesis is not None
            assert hypothesis.status == "PROPOSED"
            assert hypothesis.reviewed_by is None

            persisted_signal_ids = tuple(first.planning_refs.signal_ids.values())
            persisted_opportunity_ids = tuple(first.planning_refs.opportunity_ids.values())
            persisted_signals = tuple(
                (
                    await session.execute(
                        select(Signal).where(Signal.id.in_(persisted_signal_ids))
                    )
                )
                .scalars()
                .all()
            )
            persisted_opportunities = tuple(
                (
                    await session.execute(
                        select(ContentOpportunity).where(
                            ContentOpportunity.id.in_(persisted_opportunity_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
            support_links = tuple(
                (
                    await session.execute(
                        select(NeedHypothesisSignal).where(
                            NeedHypothesisSignal.need_hypothesis_id == hypothesis.id,
                            NeedHypothesisSignal.relation == "supports",
                        )
                    )
                )
                .scalars()
                .all()
            )
            opportunity_links = tuple(
                (
                    await session.execute(
                        select(ContentOpportunitySignal).where(
                            ContentOpportunitySignal.content_opportunity_id.in_(
                                persisted_opportunity_ids
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
            runs_after = await session.scalar(select(func.count()).select_from(ContentRun))

            market_rows = [
                signal
                for signal in persisted_signals
                if signal.source_kind == SignalSourceKind.MARKET.value
            ]
            assert len(persisted_signals) == len(first.planning_refs.signal_ids)
            assert len(persisted_opportunities) == len(first.planning_refs.opportunity_ids)
            assert all(item.selected_by is None for item in persisted_opportunities)
            assert len(market_rows) == 2
            assert market_rows[0].id != market_rows[1].id
            assert sum(item.duplicate_of_id is not None for item in market_rows) == 1
            assert {item.source_url for item in market_rows} == {
                f"https://community.example/a/{suffix}",
                f"https://community.example/b/{suffix}",
            }
            assert len(support_links) > 0
            assert len(opportunity_links) > 0
            assert runs_after == runs_before
        finally:
            await session.close()
            await transaction.rollback()
