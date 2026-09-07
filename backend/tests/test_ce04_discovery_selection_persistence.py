from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentExperiment,
    ContentOpportunity,
    HumanSelection,
    NeedHypothesis,
    Project,
)
from app.modules.research.contracts import (
    ProductionResearchRequest,
    ProductionResearchResult,
    ResearchSignalKind,
    SearchSignal,
)
from app.modules.research.discovery import DiscoveryResearchWorkflow, DiscoveryWorkflowRequest
from app.modules.research.keyword_plan.contracts import ContentDecision, NeedType
from app.modules.research.keyword_plan.service import OpportunityMapRequest


class SelectionRouter:
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
async def test_persisted_human_selection_is_single_idempotent_and_pre_contentcase() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            project = (
                await session.execute(select(Project).where(Project.slug == "motgu"))
            ).scalar_one()
            suffix = uuid4().hex
            query = f"first original art decision {suffix}"
            research_request = ProductionResearchRequest(
                project_id=project.id,
                query=query,
                locale="en",
                max_pages_to_read=0,
            )
            production = ProductionResearchResult(
                request=research_request,
                signals=[
                    SearchSignal(
                        provider="serper",
                        query=query,
                        kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                        text=f"How much should I spend on my first painting {suffix}?",
                    ),
                    SearchSignal(
                        provider="serper",
                        query=query,
                        kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                        text=f"How do I know which original artwork fits me {suffix}?",
                    ),
                    SearchSignal(
                        provider="serper",
                        query=query,
                        kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                        text=f"What should a first-time art buyer check {suffix}?",
                    ),
                ],
                sufficient=True,
                stop_reason="serper_sufficient",
            )
            workflow = DiscoveryResearchWorkflow(router=SelectionRouter(production))
            request = DiscoveryWorkflowRequest(
                research=research_request,
                opportunity=OpportunityMapRequest(
                    project_id="motgu",
                    locale="en",
                    audience_scope="international first-time art buyer",
                    situation="considering an original artwork",
                    reader="international first-time art buyer",
                    need_statement=f"Choose a first original artwork with confidence {suffix}",
                    need_type=NeedType.QUESTION,
                ),
            )
            content_cases_before = await session.scalar(
                select(func.count()).select_from(ContentCase)
            )

            result = await workflow.run(session, request=request, persist_plan=True)
            assert result.planning_refs is not None
            selected = next(
                opportunity
                for opportunity in result.opportunity_map.opportunities
                if opportunity.decision is not ContentDecision.DO_NOT_WRITE
            )
            selection_reason = "Founder chose this opportunity for the next content experiment."

            workflow.select(
                result,
                opportunity_id=selected.id,
                selected_by="founder",
                reason=selection_reason,
            )
            with pytest.raises(
                ValueError,
                match="persisted_human_selection_required_before_opportunity_handoff",
            ):
                workflow.handoff(result)

            await workflow.select_and_persist(
                session,
                result,
                opportunity_id=selected.id,
                selected_by="founder",
                reason=selection_reason,
            )
            assert result.selection_refs is not None
            first_refs = result.selection_refs
            handoff = workflow.handoff(result)

            db_selection = await session.get(HumanSelection, first_refs.human_selection_id)
            db_opportunity = await session.get(
                ContentOpportunity,
                first_refs.content_opportunity_id,
            )
            db_experiment = await session.get(
                ContentExperiment,
                first_refs.content_experiment_id,
            )
            db_hypothesis = await session.get(
                NeedHypothesis,
                result.planning_refs.need_hypothesis_id,
            )
            content_cases_after = await session.scalar(
                select(func.count()).select_from(ContentCase)
            )

            assert db_selection is not None
            assert db_opportunity is not None
            assert db_experiment is not None
            assert db_hypothesis is not None
            assert db_selection.selected_by == "founder"
            assert db_selection.reason == selection_reason
            assert db_opportunity.selected_by == "founder"
            assert db_opportunity.selection_reason == selection_reason
            assert db_experiment.status == "PLANNED"
            assert db_experiment.result == "PENDING"
            assert db_hypothesis.status == "PROPOSED"
            assert db_hypothesis.reviewed_by is None
            assert content_cases_after == content_cases_before
            assert handoff.persisted_content_opportunity_id == str(db_opportunity.id)
            assert handoff.persisted_need_hypothesis_id == str(db_hypothesis.id)
            assert handoff.persisted_content_experiment_id == str(db_experiment.id)

            await workflow.select_and_persist(
                session,
                result,
                opportunity_id=selected.id,
                selected_by="founder",
                reason=selection_reason,
            )
            assert result.selection_refs == first_refs

            with pytest.raises(
                ValueError,
                match="discovery_plan_already_has_different_selection",
            ):
                await workflow.select_and_persist(
                    session,
                    result,
                    opportunity_id=selected.id,
                    selected_by="founder",
                    reason="A conflicting replacement decision.",
                )

            selection_count = await session.scalar(
                select(func.count()).select_from(HumanSelection).where(
                    HumanSelection.content_opportunity_id == db_opportunity.id
                )
            )
            experiment_count = await session.scalar(
                select(func.count()).select_from(ContentExperiment).where(
                    ContentExperiment.content_opportunity_id == db_opportunity.id
                )
            )
            assert selection_count == 1
            assert experiment_count == 1
        finally:
            await session.close()
            await transaction.rollback()
