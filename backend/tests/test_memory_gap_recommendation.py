from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.memory_gap import MemoryGapError, recommend_memory_gap
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
    NeedHypothesis,
    Project,
)
from app.modules.harness.models import Approval, Artifact, ContentRun

O4_CONTENT_CASE_ID = UUID("9ec6133b-5f14-46d0-9866-e3b049e537b5")


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


@dataclass
class MemoryFixture:
    project: Project
    need: NeedHypothesis
    opportunity: ContentOpportunity


async def make_fixture(
    session: AsyncSession,
    *,
    locale: str = "en",
    intent: str = "evaluate",
    decision: str = "CREATE",
    question: str = "How should a buyer evaluate an artwork price?",
    material_gaps: list[str] | None = None,
) -> MemoryFixture:
    project = Project(slug=f"memory-gap-{uuid4().hex[:12]}", name="MOTGU")
    session.add(project)
    await session.flush()
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement="A buyer wants grounded context before choosing an artwork.",
        audience_scope="first-time art buyer",
        situation="considering an original artwork",
        origin="founder_proposed",
        status="PROPOSED",
        alternative_explanations_json=[],
        missing_evidence_json=[],
    )
    session.add(need)
    await session.flush()
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale=locale,
        reader="first-time art buyer",
        situation="considering a purchase",
        need="evaluate an artwork price",
        question=question,
        intent=intent,
        promise="Make a grounded next decision.",
        motgu_material_refs_json=[],
        material_gaps_json=material_gaps or ["direct buyer evidence"],
        existing_content_refs_json=[],
        what_is_actually_new="Use an explicit memory check before writing.",
        next_discovery_step="Review the matching content manually.",
        decision=decision,
        priority="NOW",
        reasons_json=["memory gap test"],
        suggested_content_type="journal",
    )
    session.add(opportunity)
    await session.flush()
    return MemoryFixture(project, need, opportunity)


async def add_content_item(
    session: AsyncSession,
    *,
    fixture: MemoryFixture,
    locale: str | None = None,
    intent: str | None = None,
    need: NeedHypothesis | None = None,
    project: Project | None = None,
    canonical_key: str | None = None,
    item_status: str = "draft",
) -> tuple[ContentCase, LocaleVariant, ContentItem]:
    item_project = project or fixture.project
    item_need = need or fixture.need
    content_case = ContentCase(
        project_id=item_project.id,
        content_type="journal",
        need_hypothesis_id=item_need.id,
        content_opportunity_id=fixture.opportunity.id,
        desired_action="read a grounded explanation",
        content_hypothesis="A clear explanation helps a buyer decide what to ask next.",
        originality_statement="Use MOTGU context without inventing a pricing formula.",
        reader_before="uncertain about the price",
        reader_after="able to ask grounded questions",
        status="draft",
    )
    session.add(content_case)
    await session.flush()
    locale_variant = LocaleVariant(
        content_case_id=content_case.id,
        locale=locale or fixture.opportunity.locale,
        content_role="cluster",
        primary_question=fixture.opportunity.question,
        primary_intent=intent or fixture.opportunity.intent,
    )
    session.add(locale_variant)
    await session.flush()
    item = ContentItem(
        project_id=item_project.id,
        content_case_id=content_case.id,
        locale_variant_id=locale_variant.id,
        content_type="journal",
        status=item_status,
        canonical_key=canonical_key or f"journal:memory-gap-{uuid4().hex}:en",
    )
    session.add(item)
    await session.flush()
    return content_case, locale_variant, item


async def add_version(
    session: AsyncSession,
    *,
    item: ContentItem,
    version_no: int,
    status: str,
    created_at: datetime,
) -> ContentVersion:
    version = ContentVersion(
        content_item_id=item.id,
        version_no=version_no,
        change_reason=f"memory gap version {version_no}",
        status=status,
        content_json={"title": f"Version {version_no}"},
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(version)
    await session.flush()
    return version


async def set_explicit_target(
    session: AsyncSession,
    *,
    opportunity: ContentOpportunity,
    item_ids: list[UUID],
    decision: str = "UPDATE",
) -> None:
    opportunity.existing_content_refs_json = [str(item_id) for item_id in item_ids]
    opportunity.decision = decision
    await session.flush()


@pytest.mark.asyncio
async def test_no_existing_memory_recommends_create() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
        )

        assert report.recommendation == "CREATE"
        assert report.matched_content_items == ()
        assert report.match_basis == {}
        assert report.unresolved_refs == ()
        assert report.requires_human_review is False
        assert report.stored_opportunity_decision == "CREATE"
        assert report.question == fixture.opportunity.question
        assert report.material_gaps == ("direct buyer evidence",)


@pytest.mark.asyncio
async def test_one_explicit_content_item_recommends_update() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        _case, _variant, item = await add_content_item(
            session,
            fixture=fixture,
            intent="compare",
        )
        await set_explicit_target(session, opportunity=fixture.opportunity, item_ids=[item.id])
        version = await add_version(
            session,
            item=item,
            version_no=1,
            status="draft",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
        )

        assert report.recommendation == "UPDATE"
        assert len(report.matched_content_items) == 1
        matched = report.matched_content_items[0]
        assert matched.content_item_id == item.id
        assert matched.canonical_key == item.canonical_key
        assert matched.content_case_id == item.content_case_id
        assert matched.item_status == "draft"
        assert matched.match_basis == ("explicit_ref",)
        assert matched.latest_content_version is not None
        assert matched.latest_content_version.id == version.id
        assert matched.latest_content_version.version == 1
        assert matched.latest_content_version.status == "draft"
        assert matched.latest_published_version is None


@pytest.mark.asyncio
async def test_exact_structural_match_without_explicit_ref_recommends_update() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        _case, _variant, item = await add_content_item(session, fixture=fixture)

        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
        )

        assert report.recommendation == "UPDATE"
        assert report.matched_content_items[0].content_item_id == item.id
        assert report.match_basis[str(item.id)] == ("structural_match",)


@pytest.mark.asyncio
async def test_existing_content_item_without_version_is_update_not_create() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        _case, _variant, item = await add_content_item(session, fixture=fixture)
        await set_explicit_target(session, opportunity=fixture.opportunity, item_ids=[item.id])

        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
        )

        assert report.recommendation == "UPDATE"
        assert report.matched_content_items[0].latest_content_version is None


@pytest.mark.asyncio
async def test_old_published_version_with_explicit_boundary_recommends_refresh() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        _case, _variant, item = await add_content_item(session, fixture=fixture)
        await set_explicit_target(session, opportunity=fixture.opportunity, item_ids=[item.id])
        published_at = datetime(2025, 1, 1, tzinfo=UTC)
        version = await add_version(
            session,
            item=item,
            version_no=1,
            status="published",
            created_at=published_at,
        )
        refresh_before = datetime(2026, 1, 1, tzinfo=UTC)

        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
            refresh_before=refresh_before,
        )

        assert report.recommendation == "REFRESH"
        assert report.refresh_before == refresh_before
        assert report.freshness_basis == "content_version_created_at"
        assert report.matched_content_items[0].latest_published_version is not None
        assert report.matched_content_items[0].latest_published_version.id == version.id


@pytest.mark.asyncio
async def test_published_version_without_refresh_boundary_is_update() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        _case, _variant, item = await add_content_item(session, fixture=fixture)
        await set_explicit_target(session, opportunity=fixture.opportunity, item_ids=[item.id])
        await add_version(
            session,
            item=item,
            version_no=1,
            status="published",
            created_at=datetime(2020, 1, 1, tzinfo=UTC),
        )

        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
        )

        assert report.recommendation == "UPDATE"
        assert report.refresh_before is None


@pytest.mark.asyncio
async def test_recent_published_version_is_update() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        _case, _variant, item = await add_content_item(session, fixture=fixture)
        await set_explicit_target(session, opportunity=fixture.opportunity, item_ids=[item.id])
        recent = datetime(2026, 8, 1, tzinfo=UTC)
        await add_version(
            session,
            item=item,
            version_no=1,
            status="published",
            created_at=recent,
        )

        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
            refresh_before=datetime(2026, 1, 1, tzinfo=UTC),
        )

        assert report.recommendation == "UPDATE"


@pytest.mark.asyncio
async def test_multiple_existing_targets_require_human_review_without_merge() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        _case_one, _variant_one, item_one = await add_content_item(session, fixture=fixture)
        _case_two, _variant_two, item_two = await add_content_item(session, fixture=fixture)
        await set_explicit_target(
            session,
            opportunity=fixture.opportunity,
            item_ids=[item_one.id, item_two.id],
        )

        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
        )

        assert report.recommendation is None
        assert report.requires_human_review is True
        assert "multiple_existing_targets" in report.reasons
        assert "MERGE" not in report.reasons
        assert len(report.matched_content_items) == 2


@pytest.mark.asyncio
async def test_unresolved_explicit_ref_is_visible_and_requires_human_review() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        missing_ref = str(uuid4())
        fixture.opportunity.existing_content_refs_json = ["not-a-content-item", missing_ref]
        await session.flush()

        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
        )

        assert report.recommendation == "CREATE"
        assert report.unresolved_refs == ("not-a-content-item", missing_ref)
        assert report.requires_human_review is True
        assert "unresolved_explicit_refs" in report.reasons


@pytest.mark.asyncio
async def test_project_mismatch_explicit_ref_is_rejected() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        foreign_project = Project(slug=f"foreign-{uuid4().hex[:12]}", name="Foreign")
        session.add(foreign_project)
        await session.flush()
        foreign_need = NeedHypothesis(
            project_id=foreign_project.id,
            type="question",
            statement="Foreign hypothesis",
            audience_scope="reader",
            situation="situation",
            origin="founder_proposed",
            status="PROPOSED",
        )
        session.add(foreign_need)
        await session.flush()
        foreign_fixture = MemoryFixture(foreign_project, foreign_need, fixture.opportunity)
        _case, _variant, item = await add_content_item(
            session,
            fixture=foreign_fixture,
            project=foreign_project,
            need=foreign_need,
        )
        await set_explicit_target(session, opportunity=fixture.opportunity, item_ids=[item.id])

        with pytest.raises(MemoryGapError, match="memory_gap_explicit_ref_project_mismatch"):
            await recommend_memory_gap(
                session,
                content_opportunity_id=fixture.opportunity.id,
            )


@pytest.mark.asyncio
async def test_locale_mismatch_explicit_ref_is_rejected() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session, locale="en")
        _case, _variant, item = await add_content_item(session, fixture=fixture, locale="vi")
        await set_explicit_target(session, opportunity=fixture.opportunity, item_ids=[item.id])

        with pytest.raises(MemoryGapError, match="memory_gap_explicit_ref_locale_mismatch"):
            await recommend_memory_gap(
                session,
                content_opportunity_id=fixture.opportunity.id,
            )


@pytest.mark.asyncio
async def test_stored_decision_mismatch_is_reported_without_mutation() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session, decision="CREATE")
        _case, _variant, item = await add_content_item(session, fixture=fixture)
        await set_explicit_target(
            session,
            opportunity=fixture.opportunity,
            item_ids=[item.id],
            decision="CREATE",
        )
        original_decision = fixture.opportunity.decision

        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
        )

        assert report.recommendation == "UPDATE"
        assert report.stored_opportunity_decision == "CREATE"
        assert report.planning_decision_mismatch is True
        assert "planning_decision_mismatch" in report.reasons
        assert fixture.opportunity.decision == original_decision == "CREATE"


@pytest.mark.asyncio
async def test_repeated_same_input_returns_identical_report() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        _case, _variant, item = await add_content_item(session, fixture=fixture)
        await set_explicit_target(session, opportunity=fixture.opportunity, item_ids=[item.id])
        created_at = datetime(2026, 2, 1, tzinfo=UTC)
        await add_version(
            session,
            item=item,
            version_no=1,
            status="published",
            created_at=created_at,
        )
        refresh_before = datetime(2026, 3, 1, tzinfo=UTC)

        first = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
            refresh_before=refresh_before,
        )
        second = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
            refresh_before=refresh_before,
        )

        assert first.to_dict() == second.to_dict()


@pytest.mark.asyncio
async def test_content_item_count_is_unchanged() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        before = await session.scalar(select(func.count()).select_from(ContentItem))
        await recommend_memory_gap(session, content_opportunity_id=fixture.opportunity.id)
        after = await session.scalar(select(func.count()).select_from(ContentItem))
        assert before == after


@pytest.mark.asyncio
async def test_content_version_count_is_unchanged() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        before = await session.scalar(select(func.count()).select_from(ContentVersion))
        await recommend_memory_gap(session, content_opportunity_id=fixture.opportunity.id)
        after = await session.scalar(select(func.count()).select_from(ContentVersion))
        assert before == after


@pytest.mark.asyncio
async def test_content_opportunity_is_unchanged() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session, material_gaps=["one", "two"])
        before = (
            fixture.opportunity.decision,
            list(fixture.opportunity.existing_content_refs_json),
            fixture.opportunity.updated_at,
        )
        await recommend_memory_gap(session, content_opportunity_id=fixture.opportunity.id)
        after = (
            fixture.opportunity.decision,
            list(fixture.opportunity.existing_content_refs_json),
            fixture.opportunity.updated_at,
        )
        assert before == after


@pytest.mark.asyncio
async def test_content_case_count_is_unchanged() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        before = await session.scalar(select(func.count()).select_from(ContentCase))
        await recommend_memory_gap(session, content_opportunity_id=fixture.opportunity.id)
        after = await session.scalar(select(func.count()).select_from(ContentCase))
        assert before == after


@pytest.mark.asyncio
async def test_o4_content_run_count_is_unchanged() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        before = await session.scalar(
            select(func.count())
            .select_from(ContentRun)
            .where(ContentRun.content_case_id == O4_CONTENT_CASE_ID)
        )
        await recommend_memory_gap(session, content_opportunity_id=fixture.opportunity.id)
        after = await session.scalar(
            select(func.count())
            .select_from(ContentRun)
            .where(ContentRun.content_case_id == O4_CONTENT_CASE_ID)
        )
        assert before == after


@pytest.mark.asyncio
async def test_artifact_and_approval_counts_are_unchanged() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        before = (
            await session.scalar(select(func.count()).select_from(Artifact)),
            await session.scalar(select(func.count()).select_from(Approval)),
        )
        await recommend_memory_gap(session, content_opportunity_id=fixture.opportunity.id)
        after = (
            await session.scalar(select(func.count()).select_from(Artifact)),
            await session.scalar(select(func.count()).select_from(Approval)),
        )
        assert before == after


@pytest.mark.asyncio
async def test_no_provider_or_model_vector_dependency_is_exposed() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
        )

        assert report.provider_calls == 0
        serialized = report.to_dict()
        assert "embedding" not in serialized
        assert "vector" not in serialized
        assert "similarity_score" not in serialized


@pytest.mark.asyncio
async def test_same_wording_without_structural_match_is_not_existing_memory() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        other_need = NeedHypothesis(
            project_id=fixture.project.id,
            type="question",
            statement="A different hypothesis has a similar question.",
            audience_scope="first-time art buyer",
            situation="considering an original artwork",
            origin="founder_proposed",
            status="PROPOSED",
        )
        session.add(other_need)
        await session.flush()
        other_fixture = MemoryFixture(fixture.project, other_need, fixture.opportunity)
        _case, _variant, item = await add_content_item(
            session,
            fixture=other_fixture,
            need=other_need,
            canonical_key=f"journal:similar-wording-{uuid4().hex}:en",
        )
        assert item is not None

        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
        )

        assert report.recommendation == "CREATE"
        assert report.matched_content_items == ()


@pytest.mark.asyncio
async def test_report_serialization_is_json_safe_and_contains_required_fields() -> None:
    async with isolated_session() as session:
        fixture = await make_fixture(session)
        report = await recommend_memory_gap(
            session,
            content_opportunity_id=fixture.opportunity.id,
        )
        payload = report.to_dict()

        assert set(
            (
                "opportunity_id",
                "project_id",
                "locale",
                "question",
                "intent",
                "stored_opportunity_decision",
                "matched_content_items",
                "match_basis",
                "unresolved_refs",
                "recommendation",
                "reasons",
                "material_gaps",
                "what_is_actually_new",
                "refresh_before",
                "freshness_basis",
                "requires_human_review",
                "planning_decision_mismatch",
                "provider_calls",
            )
        ).issubset(payload)
