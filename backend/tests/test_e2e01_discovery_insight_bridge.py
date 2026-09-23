from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
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
        provenance_json={
            "provider": "fixture",
            "method": "reviewed_observation",
            "artifact_ref": f"artifact-file:research/{uuid4().hex}.json",
        },
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
        assert signal.provenance_json["artifact_ref"].startswith("artifact-file:")

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


@pytest.mark.asyncio
async def test_customer_insight_intake_requires_complete_need_link_contract() -> None:
    async with isolated_session() as session:
        project = await _project(session, "e2e-intake")
        signal = await _signal(
            session,
            project_id=project.id,
            text="A first-time buyer asks about originality.",
        )
        need = NeedHypothesis(
            project_id=project.id,
            type="question",
            statement="A first-time buyer wants originality context.",
            audience_scope="first-time art buyer",
            situation="considering an original artwork",
            origin="founder_proposed",
            status="PROPOSED",
            alternative_explanations_json=[],
            missing_evidence_json=[],
        )
        session.add(need)
        await session.flush()

        with pytest.raises(
            CustomerInsightIntakeError,
            match="customer_insight_intake_need_link_incomplete",
        ):
            await persist_customer_insight_candidate(
                session,
                project_id=project.id,
                request=CustomerInsightCandidateInput(
                    insight_type="question",
                    statement="Originality context may matter before purchase.",
                    support_signal_ids=(signal.id,),
                    need_hypothesis_id=need.id,
                ),
            )
