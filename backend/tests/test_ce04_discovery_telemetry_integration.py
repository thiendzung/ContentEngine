from __future__ import annotations

from datetime import UTC, datetime
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
from app.modules.harness.models import Artifact, ContentRun, StepRun, ToolCall
from app.modules.harness.persistence import load_budget_usage
from app.modules.knowledge.persistence import content_hash
from app.modules.research.contracts import (
    CommercialBias,
    ProductionResearchRequest,
    ProviderResponse,
    ResearchSignalKind,
    SearchRequest,
    SearchSignal,
    SourceCandidate,
)
from app.modules.research.discovery import (
    DiscoveryResearchWorkflow,
    DiscoveryWorkflowRequest,
)
from app.modules.research.keyword_plan.contracts import NeedType, SignalSourceKind
from app.modules.research.keyword_plan.service import OpportunityMapRequest
from app.modules.research.production import ResearchRouter


class DiscoveryTelemetryProvider:
    name = "serper"

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return 1

    async def search(self, request: SearchRequest) -> ProviderResponse:
        question_signals = tuple(
            SearchSignal(
                provider=self.name,
                query=request.query,
                kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                text=f"How should a first-time art buyer decide factor {index}?",
            )
            for index in range(3)
        )
        sources = tuple(
            SourceCandidate(
                provider=self.name,
                query=request.query,
                url=f"https://example.test/discovery-{index}",
                title=f"Discovery source {index}",
                source_type="editorial" if index < 2 else "commercial",
                commercial_bias=(
                    CommercialBias.LOW if index < 2 else CommercialBias.HIGH
                ),
                why_selected="Synthetic discovery source for durable integration proof.",
            )
            for index in range(3)
        )
        organic_signals = tuple(
            SearchSignal(
                provider=self.name,
                query=request.query,
                kind=ResearchSignalKind.ORGANIC,
                text=source.title,
                title=source.title,
                url=source.url,
                position=index + 1,
            )
            for index, source in enumerate(sources)
        )
        return ProviderResponse(question_signals + organic_signals, sources, ())


async def _create_run(
    session: AsyncSession,
    *,
    suffix: str,
) -> tuple[Project, ContentRun, StepRun]:
    project = (
        await session.execute(select(Project).where(Project.slug == "motgu"))
    ).scalar_one()
    hypothesis = NeedHypothesis(
        project_id=project.id,
        type="problem",
        statement=f"CE04 discovery durable proof {suffix}",
        audience_scope="international first-time art buyer",
        situation="considering an original artwork",
        origin="FOUNDER",
    )
    session.add(hypothesis)
    await session.flush()

    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale="en",
        reader="international first-time art buyer",
        situation="considering an original artwork",
        need="Choose with confidence",
        question=f"Unique discovery durable question {suffix}?",
        intent="learn",
        promise="Understand the decision before buying",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Synthetic CE04 discovery durable proof",
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
        desired_action="Continue",
        content_hypothesis="Discovery planning remains traceable",
        originality_statement="Synthetic only",
        reader_before="Uncertain",
        reader_after="Better informed",
    )
    session.add(content_case)
    await session.flush()

    locale_variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="primary",
        primary_question=f"Unique discovery durable question {suffix}?",
        primary_intent="learn",
    )
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={"research": {"discovery_test": True}},
        source_version_refs_json=["research:discovery-test"],
        content_hash=content_hash(f"ce04-discovery-settings:{suffix}"),
    )
    session.add_all([locale_variant, snapshot])
    await session.flush()

    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=locale_variant.id,
        run_mode="create",
        status="running",
        current_step="discovery_research",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    step = StepRun(
        run_id=run.id,
        step_key="discovery_research",
        attempt=1,
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add(step)
    await session.flush()
    return project, run, step


@pytest.mark.asyncio
async def test_discovery_workflow_reuses_ce03_ledger_and_persists_non_evidence_artifact() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            suffix = uuid4().hex
            project, run, step = await _create_run(session, suffix=suffix)
            query = f"unique-discovery-query-{suffix}"
            workflow = DiscoveryResearchWorkflow(
                router=ResearchRouter(serper=DiscoveryTelemetryProvider())
            )

            result = await workflow.run(
                session,
                request=DiscoveryWorkflowRequest(
                    research=ProductionResearchRequest(
                        project_id=project.id,
                        query=query,
                        locale="en",
                        max_pages_to_read=0,
                    ),
                    opportunity=OpportunityMapRequest(
                        project_id="motgu",
                        locale="en",
                        audience_scope="international first-time art buyer",
                        situation="considering an original artwork",
                        reader="international first-time art buyer",
                        need_statement="I want to choose my first artwork with confidence.",
                        need_type=NeedType.PAIN,
                    ),
                ),
                run_id=run.id,
                step_run_id=step.id,
            )

            tool_calls = tuple(
                (
                    await session.execute(
                        select(ToolCall)
                        .where(ToolCall.run_id == run.id)
                        .order_by(ToolCall.started_at, ToolCall.id)
                    )
                )
                .scalars()
                .all()
            )
            artifact = (
                await session.execute(
                    select(Artifact).where(
                        Artifact.run_id == run.id,
                        Artifact.artifact_type == "discovery_research_report",
                    )
                )
            ).scalar_one()
            usage = await load_budget_usage(
                session,
                run_id=run.id,
                step_run_id=step.id,
            )
            await session.refresh(step)

            assert result.artifact_ref == str(artifact.id)
            assert artifact.step_run_id == step.id
            assert artifact.content_json is not None
            assert artifact.content_json["evidence_eligible"] is False
            assert artifact.content_json["artifact_type"] == "discovery_research_report"
            assert str(artifact.id) in step.output_artifact_refs_json
            assert len(tool_calls) == 1
            assert tool_calls[0].tool_key == "research.serper.search"
            assert tool_calls[0].status == "completed"
            assert usage.tool_calls == 1
            assert result.opportunity_map.need_hypothesis.status.value == "PROPOSED"
            assert any(
                signal.source_kind is SignalSourceKind.SEARCH
                for signal in result.opportunity_map.signals
            )
            assert not any(
                signal.source_kind is SignalSourceKind.MARKET
                for signal in result.opportunity_map.signals
            )
        finally:
            await session.close()
            await transaction.rollback()
