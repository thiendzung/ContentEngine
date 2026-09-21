from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import AudienceHypothesis, Project, Signal
from app.modules.customer_intelligence.insights import (
    CustomerInsightError,
    customer_insight_evidence_counts,
    ensure_customer_insight,
    link_customer_insight_signal,
    review_customer_insight,
)
from app.modules.customer_intelligence.models import CustomerInsight, CustomerInsightSignal


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
    project_id,
    text: str,
    duplicate_of_id=None,
    independence_group: str | None = None,
) -> Signal:
    signal = Signal(
        project_id=project_id,
        source_kind="MARKET",
        scope="market_web",
        observed_text=text,
        source_url=f"https://example.com/{uuid4().hex}",
        locale="en",
        context="CT-01 test fixture",
        captured_at=datetime.now(UTC),
        fingerprint=uuid4().hex,
        duplicate_of_id=duplicate_of_id,
        independence_group=independence_group,
        provenance_json={"provider": "fixture", "method": "test"},
    )
    session.add(signal)
    await session.flush()
    return signal


@pytest.mark.asyncio
async def test_customer_insight_exact_replay_and_revision_are_durable() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        audience = AudienceHypothesis(
            project_id=project.id,
            name="First-time buyer",
            description="International first-time art buyer.",
        )
        session.add(audience)
        await session.flush()

        first = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="fear",
            statement="Buyer worries that the work may not be original.",
            audience_hypothesis_id=audience.id,
            situation="considering an artwork purchase",
            alternative_explanations=["general distrust of tourist retail"],
            missing_evidence=["direct MOTGU inquiry evidence"],
        )
        replay = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="fear",
            statement="Buyer worries that the work may not be original.",
            audience_hypothesis_id=audience.id,
            situation="considering an artwork purchase",
            alternative_explanations=["general distrust of tourist retail"],
            missing_evidence=["direct MOTGU inquiry evidence"],
        )

        assert replay.id == first.id
        assert replay.insight_key == first.insight_key
        assert replay.status == "CANDIDATE"

        revised = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="fear",
            statement="Buyer needs confidence that the specific work is original.",
            audience_hypothesis_id=audience.id,
            situation="considering an artwork purchase",
            alternative_explanations=["general distrust of tourist retail"],
            missing_evidence=["direct MOTGU inquiry evidence"],
            insight_key=first.insight_key,
            version=2,
        )

        assert revised.id != first.id
        assert revised.insight_key == first.insight_key
        assert revised.version == 2

        with pytest.raises(
            CustomerInsightError,
            match="customer_insight_previous_version_required",
        ):
            await ensure_customer_insight(
                session,
                project_id=project.id,
                insight_type="fear",
                statement="Skipped revision.",
                insight_key=first.insight_key,
                version=4,
            )


@pytest.mark.asyncio
async def test_customer_insight_requires_explicit_review_for_truth_promotion() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")

        with pytest.raises(
            CustomerInsightError,
            match="customer_insight_review_required",
        ):
            await ensure_customer_insight(
                session,
                project_id=project.id,
                insight_type="pain",
                statement="Cannot silently start as supported.",
                status="SUPPORTED",
            )

        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="pain",
            statement="Visible pricing may reduce uncertainty.",
        )
        reviewed = await review_customer_insight(
            session,
            customer_insight_id=insight.id,
            status="SUPPORTED",
            reviewed_by="founder",
            reason="Reviewed against independent customer evidence.",
        )
        replay = await review_customer_insight(
            session,
            customer_insight_id=insight.id,
            status="SUPPORTED",
            reviewed_by="founder",
            reason="Reviewed against independent customer evidence.",
        )

        assert reviewed.status == "SUPPORTED"
        assert reviewed.reviewed_at is not None
        assert replay.id == reviewed.id

        with pytest.raises(
            CustomerInsightError,
            match="customer_insight_already_reviewed",
        ):
            await review_customer_insight(
                session,
                customer_insight_id=insight.id,
                status="REJECTED",
                reviewed_by="founder",
                reason="Conflicting second review.",
            )


@pytest.mark.asyncio
async def test_customer_insight_relation_replay_is_exact_and_project_scoped() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        other = await _project(session, "other")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="barrier",
            statement="Shipping uncertainty can block a purchase decision.",
        )
        support = await _signal(
            session,
            project_id=project.id,
            text="How do I take a painting home?",
        )
        foreign = await _signal(
            session,
            project_id=other.id,
            text="Unrelated project observation.",
        )

        first = await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=support.id,
            relation="supports",
        )
        replay = await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=support.id,
            relation="supports",
        )
        assert replay.customer_insight_id == first.customer_insight_id

        with pytest.raises(
            CustomerInsightError,
            match="customer_insight_signal_relation_conflict",
        ):
            await link_customer_insight_signal(
                session,
                customer_insight_id=insight.id,
                signal_id=support.id,
                relation="contradicts",
            )

        with pytest.raises(
            CustomerInsightError,
            match="customer_insight_signal_project_mismatch",
        ):
            await link_customer_insight_signal(
                session,
                customer_insight_id=insight.id,
                signal_id=foreign.id,
                relation="supports",
            )

        with pytest.raises(
            DBAPIError,
            match="customer_insight_signal_project_mismatch",
        ):
            async with session.begin_nested():
                session.add(
                    CustomerInsightSignal(
                        customer_insight_id=insight.id,
                        signal_id=foreign.id,
                        relation="context",
                    )
                )
                await session.flush()


@pytest.mark.asyncio
async def test_duplicate_signals_do_not_inflate_independent_evidence() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="pain",
            statement="Missing visible pricing can create uncertainty.",
        )
        original = await _signal(
            session,
            project_id=project.id,
            text="I could not find the price.",
        )
        repost = await _signal(
            session,
            project_id=project.id,
            text="I could not find the price.",
            duplicate_of_id=original.id,
        )
        independent = await _signal(
            session,
            project_id=project.id,
            text="Why is the price not shown?",
        )
        contradiction = await _signal(
            session,
            project_id=project.id,
            text="The visible price was clear enough for me.",
        )

        for signal in (original, repost, independent):
            await link_customer_insight_signal(
                session,
                customer_insight_id=insight.id,
                signal_id=signal.id,
                relation="supports",
            )
        await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=contradiction.id,
            relation="contradicts",
        )

        counts = await customer_insight_evidence_counts(
            session,
            customer_insight_id=insight.id,
        )

        assert counts.supports == 3
        assert counts.independent_supports == 2
        assert counts.contradicts == 1
        assert counts.independent_contradicts == 1


@pytest.mark.asyncio
async def test_customer_insight_version_content_is_database_immutable() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="desire",
            statement="Buyer wants a meaningful connection to the work.",
        )

        insight.statement = "Silently rewritten interpretation."
        with pytest.raises(
            DBAPIError,
            match="customer_insight_version_content_immutable",
        ):
            async with session.begin_nested():
                await session.flush()


@pytest.mark.asyncio
async def test_customer_insight_database_rejects_invalid_type_and_unreviewed_support() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")

        invalid = CustomerInsight(
            project_id=project.id,
            insight_key="a" * 64,
            version=1,
            insight_type="persona_guess",
            statement="Invalid taxonomy entry.",
            status="CANDIDATE",
            alternative_explanations_json=[],
            missing_evidence_json=[],
        )
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(invalid)
                await session.flush()

        unreviewed = CustomerInsight(
            project_id=project.id,
            insight_key="b" * 64,
            version=1,
            insight_type="pain",
            statement="Unreviewed promotion.",
            status="SUPPORTED",
            alternative_explanations_json=[],
            missing_evidence_json=[],
        )
        with pytest.raises(
            DBAPIError,
            match="customer_insight_review_required",
        ):
            async with session.begin_nested():
                session.add(unreviewed)
                await session.flush()