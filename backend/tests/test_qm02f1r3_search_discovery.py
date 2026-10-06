from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    HumanSelection,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.harness.models import ContentRun, Job, StepRun
from app.modules.research.contracts import (
    ProductionResearchRequest,
    ProductionResearchResult,
    ProviderCallArtifact,
    ProviderDecision,
    ProviderDecisionStatus,
    ResearchSignalKind,
    SearchSignal,
)
from app.modules.research.keyword_plan.normalize import (
    normalize_text,
    signal_fingerprint,
)
from app.modules.research.keyword_plan.question_map import build_question_map
from app.modules.research.keyword_plan.search_discovery import (
    SearchDiscoveryRequest,
    capture_hash,
    run_search_discovery,
)


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


async def _project(session: AsyncSession) -> Project:
    row = Project(
        slug=f"qm-f1r3-{uuid4().hex[:8]}",
        name="QM F1R3",
        default_locale="en",
    )
    session.add(row)
    await session.flush()
    return row


async def _need(
    session: AsyncSession,
    *,
    project_id,
) -> NeedHypothesis:
    row = NeedHypothesis(
        project_id=project_id,
        type="question",
        statement="Buy a first original artwork with confidence.",
        audience_scope="international first-time art buyer",
        situation="considering a first original artwork",
        origin="customer_intelligence",
        status="PROPOSED",
        alternative_explanations_json=[],
        missing_evidence_json=["Direct customer evidence remains limited."],
        version=1,
    )
    session.add(row)
    await session.flush()
    return row


class FakeSearchDiscoveryRunner:
    def __init__(self, *, locale_specific: bool = False) -> None:
        self.requests: list[ProductionResearchRequest] = []
        self.locale_specific = locale_specific

    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id=None,
        step_run_id=None,
    ) -> ProductionResearchResult:
        del session, run_id, step_run_id
        self.requests.append(request)

        if self.locale_specific:
            text = (
                "Làm sao biết tranh sơn dầu là tranh gốc?"
                if request.locale == "vi"
                else "How do I know if an oil painting is original?"
            )
            signals = [
                SearchSignal(
                    provider="serper",
                    query=request.query,
                    kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                    text=text,
                )
            ]
        elif normalize_text(request.query) == "buying first original artwork":
            signals = [
                SearchSignal(
                    provider="serper",
                    query=request.query,
                    kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                    text="How do I know if a painting is original?",
                ),
                SearchSignal(
                    provider="serper",
                    query=request.query,
                    kind=ResearchSignalKind.AUTOCOMPLETE,
                    text="How do I know if a painting is original?",
                ),
                SearchSignal(
                    provider="serper",
                    query=request.query,
                    kind=ResearchSignalKind.RELATED_SEARCH,
                    text="How much should I spend on my first painting?",
                ),
                SearchSignal(
                    provider="serper",
                    query=request.query,
                    kind=ResearchSignalKind.AUTOCOMPLETE,
                    text="What size painting fits my wall?",
                ),
                SearchSignal(
                    provider="serper",
                    query=request.query,
                    kind=ResearchSignalKind.AUTOCOMPLETE,
                    text="Can I carry a painting home on a flight?",
                ),
                SearchSignal(
                    provider="serper",
                    query=request.query,
                    kind=ResearchSignalKind.PEOPLE_ALSO_ASK,
                    text="How do I mix oil paint?",
                ),
                SearchSignal(
                    provider="serper",
                    query=request.query,
                    kind=ResearchSignalKind.ORGANIC,
                    text="Complete guide to buying original art",
                    title="Complete guide to buying original art",
                    url="https://example.com/buying-art",
                    snippet="Commercial context for a first-time buyer.",
                    position=1,
                ),
            ]
        else:
            signals = []

        result = ProductionResearchResult(request=request)
        result.signals.extend(signals)
        result.sufficient = True
        result.stop_reason = "serper_sufficient"
        result.decisions.append(
            ProviderDecision(
                provider="serper",
                status=ProviderDecisionStatus.CALLED,
                reason="default_google_discovery",
            )
        )
        result.calls.append(
            ProviderCallArtifact(
                provider="serper",
                operation="search",
                query=request.query,
                purpose="discovery",
                status="ok",
                result_count=len(signals),
                raw_excerpt=f"fixture:{request.query}",
            )
        )
        return result


class CrossNeedEligibilityRunner:
    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id=None,
        step_run_id=None,
    ) -> ProductionResearchResult:
        del session, run_id, step_run_id
        kind = (
            ResearchSignalKind.PEOPLE_ALSO_ASK
            if request.query == "question-seed"
            else ResearchSignalKind.ORGANIC
        )
        result = ProductionResearchResult(request=request)
        result.signals.append(
            SearchSignal(
                provider="serper",
                query=request.query,
                kind=kind,
                text="How do I know if a painting is original?",
                title=(
                    "How do I know if a painting is original?"
                    if kind is ResearchSignalKind.ORGANIC
                    else None
                ),
                url=(
                    "https://example.com/authenticity"
                    if kind is ResearchSignalKind.ORGANIC
                    else None
                ),
            )
        )
        result.sufficient = True
        result.stop_reason = "serper_sufficient"
        return result


async def _counts(
    session: AsyncSession,
    *,
    project_id,
) -> dict[str, int]:
    return {
        "signals": int(
            await session.scalar(
                select(func.count())
                .select_from(Signal)
                .where(
                    Signal.project_id == project_id,
                    Signal.source_kind == "SEARCH",
                )
            )
            or 0
        ),
        "need_links": int(
            await session.scalar(
                select(func.count())
                .select_from(NeedHypothesisSignal)
            )
            or 0
        ),
        "opportunities": int(
            await session.scalar(
                select(func.count())
                .select_from(ContentOpportunity)
                .where(ContentOpportunity.project_id == project_id)
            )
            or 0
        ),
        "selections": int(
            await session.scalar(
                select(func.count())
                .select_from(HumanSelection)
                .join(
                    ContentOpportunity,
                    ContentOpportunity.id
                    == HumanSelection.content_opportunity_id,
                )
                .where(ContentOpportunity.project_id == project_id)
            )
            or 0
        ),
        "cases": int(
            await session.scalar(
                select(func.count())
                .select_from(ContentCase)
                .where(ContentCase.project_id == project_id)
            )
            or 0
        ),
        "runs": int(
            await session.scalar(
                select(func.count())
                .select_from(ContentRun)
                .where(ContentRun.project_id == project_id)
            )
            or 0
        ),
        "steps": int(
            await session.scalar(
                select(func.count())
                .select_from(StepRun)
                .join(ContentRun, ContentRun.id == StepRun.run_id)
                .where(ContentRun.project_id == project_id)
            )
            or 0
        ),
        "jobs": int(
            await session.scalar(
                select(func.count())
                .select_from(Job)
                .join(ContentRun, ContentRun.id == Job.run_id)
                .where(ContentRun.project_id == project_id)
            )
            or 0
        ),
    }


@pytest.mark.asyncio
async def test_bounded_search_discovery_reaches_question_and_architecture_maps() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        runner = FakeSearchDiscoveryRunner()
        request = SearchDiscoveryRequest(
            project_id=project.id,
            need_id=need.id,
            locale="en",
            country="us",
            seed_queries=("buying first original artwork",),
            artifact_ref="artifact-file:research/f1r3-fixture.json",
            max_hops=1,
            max_expansions_per_hop=2,
            max_total_queries=3,
        )
        before = await _counts(session, project_id=project.id)

        first = await run_search_discovery(
            session,
            runner=runner,
            request=request,
        )
        after_first = await _counts(session, project_id=project.id)

        assert len(first.executed_queries) == 3
        assert len(runner.requests) == 3
        assert first.provider_calls
        assert all(
            isinstance(row.get("raw_excerpt"), str)
            and row["raw_excerpt"]
            and isinstance(row.get("raw_excerpt_hash"), str)
            and len(row["raw_excerpt_hash"]) == 64
            for row in first.provider_calls
        )
        assert all(
            item.force_external_discovery
            and item.max_pages_to_read == 0
            for item in runner.requests
        )
        assert first.question_count == 5
        assert first.cluster_count == 4
        assert first.pillar_candidate_count == 1
        assert len(first.breadth) == 4
        assert {
            row["answer_job"]
            for row in first.breadth
        } == {
            "carry_home",
            "choose_size",
            "plan_budget",
            "verify_authenticity",
        }

        assert after_first["signals"] == before["signals"] + 6
        assert after_first["need_links"] == before["need_links"] + 5
        assert after_first["opportunities"] == before["opportunities"]
        assert after_first["selections"] == before["selections"]
        assert after_first["cases"] == before["cases"]
        assert after_first["runs"] == before["runs"]
        assert after_first["steps"] == before["steps"]
        assert after_first["jobs"] == before["jobs"]

        await session.refresh(need)
        assert need.status == "PROPOSED"
        assert need.version == 1

        authenticity_fp = signal_fingerprint(
            locale="en",
            observed_text="How do I know if a painting is original?",
        )
        authenticity = await session.scalar(
            select(Signal).where(
                Signal.project_id == project.id,
                Signal.fingerprint == authenticity_fp,
            )
        )
        assert authenticity is not None
        assert authenticity.independence_group == authenticity_fp
        assert authenticity.duplicate_of_id is None
        assert authenticity.provenance_json["observation_count"] == 2
        assert authenticity.provenance_json["customer_truth_eligible"] is False
        assert authenticity.provenance_json["factual_evidence_eligible"] is False
        assert {
            row["method"]
            for row in authenticity.provenance_json["observations"]
        } == {"people_also_ask", "autocomplete"}

        organic = await session.scalar(
            select(Signal).where(
                Signal.project_id == project.id,
                Signal.source_url == "https://example.com/buying-art",
            )
        )
        assert organic is not None
        assert organic.provenance_json["question_eligible"] is False
        assert organic.provenance_json["planning_need_refs"] == [
            str(need.id)
        ]
        assert await session.get(
            NeedHypothesisSignal,
            (need.id, organic.id, "supports"),
        ) is None

        question_map = await build_question_map(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        question_texts = {
            row["text"]
            for row in question_map["questions"]
            if isinstance(row, dict)
        }
        assert "Complete guide to buying original art" not in question_texts
        assert str(organic.id) not in question_map["signal_refs"]

        off_scope = next(
            row
            for row in question_map["questions"]
            if isinstance(row, dict)
            and row["text"] == "How do I mix oil paint?"
        )
        assert off_scope["cluster_eligible"] is False

        hash_first = capture_hash(first)
        second = await run_search_discovery(
            session,
            runner=FakeSearchDiscoveryRunner(),
            request=request,
        )
        after_second = await _counts(session, project_id=project.id)

        assert second.created_signal_ids == []
        assert set(second.reused_signal_ids) == set(first.persisted_signal_ids)
        assert after_second == after_first
        assert second.question_map_snapshot_hash == first.question_map_snapshot_hash
        assert second.architecture_snapshot_hash == first.architecture_snapshot_hash
        assert capture_hash(second) == hash_first


@pytest.mark.asyncio
async def test_context_only_reuse_does_not_leak_question_link_across_needs() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        question_need = await _need(session, project_id=project.id)
        context_need = await _need(session, project_id=project.id)
        runner = CrossNeedEligibilityRunner()

        question_result = await run_search_discovery(
            session,
            runner=runner,
            request=SearchDiscoveryRequest(
                project_id=project.id,
                need_id=question_need.id,
                locale="en",
                country="us",
                seed_queries=("question-seed",),
                max_hops=0,
                max_total_queries=1,
            ),
        )
        context_result = await run_search_discovery(
            session,
            runner=runner,
            request=SearchDiscoveryRequest(
                project_id=project.id,
                need_id=context_need.id,
                locale="en",
                country="us",
                seed_queries=("context-seed",),
                max_hops=0,
                max_total_queries=1,
            ),
        )

        assert question_result.persisted_signal_ids == (
            context_result.persisted_signal_ids
        )
        signal_id = question_result.persisted_signal_ids[0]
        signal = await session.get(Signal, signal_id)
        assert signal is not None
        assert signal.provenance_json["question_eligible"] is True
        assert signal.provenance_json["planning_need_refs"] == sorted(
            [str(question_need.id), str(context_need.id)]
        )
        assert await session.get(
            NeedHypothesisSignal,
            (question_need.id, signal_id, "supports"),
        ) is not None
        assert await session.get(
            NeedHypothesisSignal,
            (context_need.id, signal_id, "supports"),
        ) is None

        context_map = await build_question_map(
            session,
            project_id=project.id,
            need_id=context_need.id,
            locale="en",
        )
        assert context_map["counts"]["questions"] == 0
        assert context_map["signal_refs"] == []


@pytest.mark.asyncio
async def test_search_discovery_keeps_locale_signal_identity_separate() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project_id=project.id)
        runner = FakeSearchDiscoveryRunner(locale_specific=True)

        english = await run_search_discovery(
            session,
            runner=runner,
            request=SearchDiscoveryRequest(
                project_id=project.id,
                need_id=need.id,
                locale="en",
                country="us",
                seed_queries=("original painting",),
                max_hops=0,
                max_total_queries=1,
            ),
        )
        vietnamese = await run_search_discovery(
            session,
            runner=runner,
            request=SearchDiscoveryRequest(
                project_id=project.id,
                need_id=need.id,
                locale="vi",
                country="vn",
                seed_queries=("tranh sơn dầu gốc",),
                max_hops=0,
                max_total_queries=1,
            ),
        )

        assert set(english.persisted_signal_ids).isdisjoint(
            set(vietnamese.persisted_signal_ids)
        )
        assert english.question_map_snapshot_hash != vietnamese.question_map_snapshot_hash
        rows = list(
            (
                await session.scalars(
                    select(Signal)
                    .where(Signal.project_id == project.id)
                    .order_by(Signal.locale, Signal.id)
                )
            ).all()
        )
        assert {row.locale for row in rows} == {"en", "vi"}
        assert all(
            row.provenance_json["customer_truth_eligible"] is False
            and row.provenance_json["factual_evidence_eligible"] is False
            for row in rows
        )
