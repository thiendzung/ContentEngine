from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
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
from app.modules.customer_intelligence.models import (
    CustomerInsight,
    CustomerInsightReview,
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
async def test_customer_insight_initial_status_must_be_candidate() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")

        with pytest.raises(
            CustomerInsightError,
            match="customer_insight_initial_status_must_be_candidate",
        ):
            await ensure_customer_insight(
                session,
                project_id=project.id,
                insight_type="pain",
                statement="Cannot silently start as supported.",
                status="SUPPORTED",
            )


@pytest.mark.asyncio
async def test_supported_review_requires_real_support_evidence() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="pain",
            statement="Visible pricing may reduce uncertainty.",
        )

        with pytest.raises(
            CustomerInsightError,
            match="customer_insight_support_evidence_required",
        ):
            await review_customer_insight(
                session,
                customer_insight_id=insight.id,
                status="SUPPORTED",
                reviewed_by="founder",
                reason="No evidence should not be enough.",
            )

        support = await _signal(
            session,
            project_id=project.id,
            text="I could not find the price.",
        )
        await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=support.id,
            relation="supports",
        )

        reviewed = await review_customer_insight(
            session,
            customer_insight_id=insight.id,
            status="SUPPORTED",
            reviewed_by="founder",
            reason="Supported by a linked customer signal.",
        )

        assert reviewed.status == "SUPPORTED"
        assert reviewed.reviewed_at is not None


@pytest.mark.asyncio
async def test_review_lifecycle_preserves_history_and_allows_progression() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="barrier",
            statement="Shipping uncertainty may block a purchase.",
        )

        testing = await review_customer_insight(
            session,
            customer_insight_id=insight.id,
            status="TESTING",
            reviewed_by="founder",
            reason="Need direct customer evidence.",
        )
        assert testing.status == "TESTING"

        support = await _signal(
            session,
            project_id=project.id,
            text="How do I take this painting home safely?",
        )
        await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=support.id,
            relation="supports",
        )

        supported = await review_customer_insight(
            session,
            customer_insight_id=insight.id,
            status="SUPPORTED",
            reviewed_by="founder",
            reason="Direct customer question now supports the insight.",
        )
        replay = await review_customer_insight(
            session,
            customer_insight_id=insight.id,
            status="SUPPORTED",
            reviewed_by="founder",
            reason="Direct customer question now supports the insight.",
        )
        historical_replay = await review_customer_insight(
            session,
            customer_insight_id=insight.id,
            status="TESTING",
            reviewed_by="founder",
            reason="Need direct customer evidence.",
        )

        reviews = list(
            (
                await session.scalars(
                    select(CustomerInsightReview)
                    .where(
                        CustomerInsightReview.customer_insight_id
                        == insight.id
                    )
                    .order_by(CustomerInsightReview.reviewed_at)
                )
            ).all()
        )

        assert supported.status == "SUPPORTED"
        assert replay.id == supported.id
        assert historical_replay.status == "SUPPORTED"
        assert len(reviews) == 2
        assert [review.status for review in reviews] == [
            "TESTING",
            "SUPPORTED",
        ]
        assert reviews[0].reason == "Need direct customer evidence."

        first_review = reviews[0]
        with pytest.raises(
            DBAPIError,
            match="customer_insight_review_must_advance",
        ):
            async with session.begin_nested():
                insight.status = first_review.status
                insight.reviewed_by = first_review.reviewed_by
                insight.reviewed_at = first_review.reviewed_at
                insight.review_reason = first_review.reason
                await session.flush()


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
async def test_customer_insight_signal_relation_and_delete_are_database_immutable() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="question",
            statement="Buyer asks how authenticity is verified.",
        )
        signal = await _signal(
            session,
            project_id=project.id,
            text="How can I know this painting is original?",
        )
        link = await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=signal.id,
            relation="supports",
        )

        with pytest.raises(
            DBAPIError,
            match="customer_insight_signal_is_immutable",
        ):
            async with session.begin_nested():
                link.relation = "contradicts"
                await session.flush()

        await session.refresh(link)
        with pytest.raises(
            DBAPIError,
            match="customer_insight_signal_delete_forbidden",
        ):
            async with session.begin_nested():
                await session.delete(link)
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
async def test_duplicate_chain_validates_parent_even_when_group_is_present() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        other = await _project(session, "other")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="pain",
            statement="Repeated reposts must not fake independent support.",
        )
        foreign_parent = await _signal(
            session,
            project_id=other.id,
            text="Foreign parent.",
        )
        child = await _signal(
            session,
            project_id=project.id,
            text="Grouped child.",
            duplicate_of_id=foreign_parent.id,
            independence_group="same-discussion",
        )
        with pytest.raises(
            CustomerInsightError,
            match="customer_insight_signal_duplicate_parent_invalid",
        ):
            await link_customer_insight_signal(
                session,
                customer_insight_id=insight.id,
                signal_id=child.id,
                relation="supports",
            )

        with pytest.raises(
            DBAPIError,
            match="customer_insight_signal_duplicate_parent_invalid",
        ):
            async with session.begin_nested():
                session.add(
                    CustomerInsightSignal(
                        customer_insight_id=insight.id,
                        signal_id=child.id,
                        relation="supports",
                    )
                )
                await session.flush()


@pytest.mark.asyncio
async def test_duplicate_cycle_fails_closed_even_with_independence_group() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="pain",
            statement="Cyclic duplicate lineage is invalid.",
        )
        first = await _signal(
            session,
            project_id=project.id,
            text="First.",
            independence_group="same-discussion",
        )
        second = await _signal(
            session,
            project_id=project.id,
            text="Second.",
            duplicate_of_id=first.id,
            independence_group="same-discussion",
        )
        first.duplicate_of_id = second.id
        await session.flush()
        with pytest.raises(
            CustomerInsightError,
            match="customer_insight_signal_duplicate_cycle",
        ):
            await link_customer_insight_signal(
                session,
                customer_insight_id=insight.id,
                signal_id=second.id,
                relation="supports",
            )

        with pytest.raises(
            DBAPIError,
            match="customer_insight_signal_duplicate_cycle",
        ):
            async with session.begin_nested():
                session.add(
                    CustomerInsightSignal(
                        customer_insight_id=insight.id,
                        signal_id=second.id,
                        relation="supports",
                    )
                )
                await session.flush()


@pytest.mark.asyncio
async def test_linked_signal_and_ancestor_project_scope_cannot_drift() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        other = await _project(session, "other")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="question",
            statement="Buyer asks whether a source is trustworthy.",
        )

        direct = await _signal(
            session,
            project_id=project.id,
            text="Direct signal.",
        )
        await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=direct.id,
            relation="supports",
        )

        with pytest.raises(
            DBAPIError,
            match="customer_insight_signal_lineage_immutable",
        ):
            async with session.begin_nested():
                direct.project_id = other.id
                await session.flush()

        await session.refresh(direct)

        root = await _signal(
            session,
            project_id=project.id,
            text="Root signal.",
        )
        child = await _signal(
            session,
            project_id=project.id,
            text="Child signal.",
            duplicate_of_id=root.id,
        )
        await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=child.id,
            relation="context",
        )

        with pytest.raises(
            DBAPIError,
            match="customer_insight_signal_lineage_immutable",
        ):
            async with session.begin_nested():
                root.project_id = other.id
                await session.flush()


@pytest.mark.asyncio
async def test_referenced_audience_project_scope_cannot_drift() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        other = await _project(session, "other")
        audience = AudienceHypothesis(
            project_id=project.id,
            name="First-time buyer",
            description="Audience linked to CT-01 insight.",
        )
        session.add(audience)
        await session.flush()

        await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="fear",
            statement="Buyer fears choosing the wrong artwork.",
            audience_hypothesis_id=audience.id,
        )

        with pytest.raises(
            DBAPIError,
            match="customer_insight_audience_project_change_forbidden",
        ):
            async with session.begin_nested():
                audience.project_id = other.id
                await session.flush()


@pytest.mark.asyncio
async def test_customer_insight_version_content_and_delete_are_database_immutable() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="desire",
            statement="Buyer wants a meaningful connection to the work.",
        )

        with pytest.raises(
            DBAPIError,
            match="customer_insight_version_content_immutable",
        ):
            async with session.begin_nested():
                insight.statement = "Silently rewritten interpretation."
                await session.flush()

        await session.refresh(insight)
        with pytest.raises(
            DBAPIError,
            match="customer_insight_delete_forbidden",
        ):
            async with session.begin_nested():
                await session.delete(insight)
                await session.flush()


@pytest.mark.asyncio
async def test_database_requires_audited_review_and_support_for_promotion() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="pain",
            statement="Promotion must be evidence-backed and audited.",
        )

        now = datetime.now(UTC)
        with pytest.raises(
            DBAPIError,
            match="customer_insight_review_record_required",
        ):
            async with session.begin_nested():
                insight.status = "SUPPORTED"
                insight.reviewed_by = "founder"
                insight.reviewed_at = now
                insight.review_reason = "Direct update without audit."
                await session.flush()

        await session.refresh(insight)
        now = datetime.now(UTC)
        session.add(
            CustomerInsightReview(
                customer_insight_id=insight.id,
                status="SUPPORTED",
                reviewed_by="founder",
                reason="Audited but unsupported.",
                support_signal_refs_json=[],
                contradict_signal_refs_json=[],
                context_signal_refs_json=[],
                reviewed_at=now,
            )
        )
        await session.flush()

        with pytest.raises(
            DBAPIError,
            match="customer_insight_support_evidence_required",
        ):
            async with session.begin_nested():
                insight.status = "SUPPORTED"
                insight.reviewed_by = "founder"
                insight.reviewed_at = now
                insight.review_reason = "Audited but unsupported."
                await session.flush()


@pytest.mark.asyncio
async def test_database_rejects_invalid_type_and_non_candidate_insert() -> None:
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

        non_candidate = CustomerInsight(
            project_id=project.id,
            insight_key="b" * 64,
            version=1,
            insight_type="pain",
            statement="Cannot insert directly as supported.",
            status="SUPPORTED",
            alternative_explanations_json=[],
            missing_evidence_json=[],
        )
        with pytest.raises(
            DBAPIError,
            match="customer_insight_initial_status_must_be_candidate",
        ):
            async with session.begin_nested():
                session.add(non_candidate)
                await session.flush()