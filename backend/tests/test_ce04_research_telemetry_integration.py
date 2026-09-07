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
from app.modules.harness.models import ContentRun, StepRun, ToolCall
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
from app.modules.research.production import ResearchRouter
from app.modules.research.providers.base import ResearchProviderError


class TelemetryProvider:
    name = "serper"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def estimated_calls(self, request: SearchRequest) -> int:
        del request
        return 1

    async def search(self, request: SearchRequest) -> ProviderResponse:
        if self.fail:
            raise ResearchProviderError(
                self.name,
                "search",
                "http_429",
                failure_class="provider_rate_limit",
            )
        signals = tuple(
            SearchSignal(
                provider=self.name,
                query=request.query,
                kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                text=f"question-{index}",
            )
            for index in range(3)
        )
        sources = tuple(
            SourceCandidate(
                provider=self.name,
                query=request.query,
                url=f"https://example.test/source-{index}",
                title=f"source-{index}",
                commercial_bias=(
                    CommercialBias.LOW if index == 0 else CommercialBias.UNKNOWN
                ),
            )
            for index in range(3)
        )
        return ProviderResponse(signals, sources, ())


async def _create_run(session: AsyncSession, *, suffix: str) -> tuple[Project, ContentRun, StepRun]:
    project = (
        await session.execute(select(Project).where(Project.slug == "motgu"))
    ).scalar_one()
    hypothesis = NeedHypothesis(
        project_id=project.id,
        type="problem",
        statement=f"CE04 research telemetry {suffix}",
        audience_scope="test reader",
        situation="production research test",
        origin="FOUNDER",
    )
    session.add(hypothesis)
    await session.flush()
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale="en",
        reader="test reader",
        situation="production research test",
        need="Traceable research",
        question=f"Unique research telemetry question {suffix}?",
        intent="learn",
        promise="Keep provider calls traceable",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Synthetic CE04 telemetry proof",
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
        content_hypothesis="Provider telemetry keeps research reproducible",
        originality_statement="Synthetic only",
        reader_before="Unknown",
        reader_after="Traceable",
    )
    session.add(content_case)
    await session.flush()
    locale_variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="primary",
        primary_question=f"Unique research telemetry question {suffix}?",
        primary_intent="learn",
    )
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={"research": {"test": True}},
        source_version_refs_json=["research:test"],
        content_hash=content_hash(f"ce04-research-settings:{suffix}"),
    )
    session.add_all([locale_variant, snapshot])
    await session.flush()
    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=locale_variant.id,
        run_mode="create",
        status="running",
        current_step="research",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    step = StepRun(
        run_id=run.id,
        step_key="research",
        attempt=1,
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add(step)
    await session.flush()
    return project, run, step


@pytest.mark.asyncio
async def test_research_router_records_ce03_toolcall_and_budget_usage() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            suffix = uuid4().hex
            project, run, step = await _create_run(session, suffix=suffix)
            router = ResearchRouter(serper=TelemetryProvider())
            result = await router.run(
                session,
                request=ProductionResearchRequest(
                    project_id=project.id,
                    query=f"unique-research-query-{suffix}",
                    max_pages_to_read=0,
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
            usage = await load_budget_usage(
                session,
                run_id=run.id,
                step_run_id=step.id,
            )

            assert result.stop_reason == "serper_sufficient"
            assert len(tool_calls) == 1
            assert tool_calls[0].tool_key == "research.serper.search"
            assert tool_calls[0].status == "completed"
            assert tool_calls[0].result_ref is None
            assert usage.tool_calls == 1
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_research_router_failure_uses_ce03_error_class() -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            suffix = uuid4().hex
            project, run, step = await _create_run(session, suffix=suffix)
            router = ResearchRouter(serper=TelemetryProvider(fail=True))
            await router.run(
                session,
                request=ProductionResearchRequest(
                    project_id=project.id,
                    query=f"unique-failing-research-query-{suffix}",
                    max_pages_to_read=0,
                ),
                run_id=run.id,
                step_run_id=step.id,
            )

            tool_call = (
                await session.execute(select(ToolCall).where(ToolCall.run_id == run.id))
            ).scalar_one()
            assert tool_call.status == "failed"
            assert tool_call.error_class == "provider_rate_limit"
        finally:
            await session.close()
            await transaction.rollback()
