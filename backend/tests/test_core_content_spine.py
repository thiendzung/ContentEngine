from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    AudienceHypothesis,
    ContentCase,
    ContentExperiment,
    ContentItem,
    ContentOpportunity,
    ContentOpportunitySignal,
    LocaleVariant,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.content_engine.persistence import (
    create_next_content_version,
    get_content_item_by_canonical_key,
    record_human_selection,
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


@pytest.mark.asyncio
async def test_core_spine_keeps_hypothesis_and_content_identity() -> None:
    async with isolated_session() as session:
        project = Project(slug=f"motgu-{uuid4().hex[:8]}", name="MOTGU")
        session.add(project)
        await session.flush()

        audience = AudienceHypothesis(
            project_id=project.id,
            name="First-time art buyer",
            description="People considering an original artwork for the first time.",
        )
        signal = Signal(
            project_id=project.id,
            source_kind="SEARCH",
            scope="market_web",
            observed_text="How much should I spend on my first painting?",
            source_url="https://example.com/question",
            locale="en",
            context="CE01 regression fixture",
            captured_at=datetime.now(timezone.utc),
            fingerprint=uuid4().hex,
            provenance_json={"provider": "fixture", "method": "test"},
        )
        session.add_all([audience, signal])
        await session.flush()

        hypothesis = NeedHypothesis(
            project_id=project.id,
            audience_hypothesis_id=audience.id,
            type="pain",
            statement="First-time buyers may worry about choosing the wrong painting.",
            audience_scope="first-time art buyers",
            situation="considering an original artwork",
            origin="founder_proposed",
            missing_evidence_json=["direct MOTGU customer signal"],
        )
        session.add(hypothesis)
        await session.flush()
        session.add(
            NeedHypothesisSignal(
                need_hypothesis_id=hypothesis.id,
                signal_id=signal.id,
                relation="supports",
            )
        )

        opportunity = ContentOpportunity(
            project_id=project.id,
            need_hypothesis_id=hypothesis.id,
            locale="en",
            reader="first-time art buyer",
            situation="looking at a displayed artwork price",
            need="understand what the price does and does not mean",
            question="How should I read the price of an artwork?",
            intent="evaluate",
            promise="Evaluate a displayed price without treating it as a score.",
            motgu_material_refs_json=["motgu_artwork_000105"],
            material_gaps_json=[],
            existing_content_refs_json=[],
            what_is_actually_new="Use a real MOTGU artwork as a grounded example.",
            next_discovery_step="Confirm artwork facts from live canonical source.",
            decision="CREATE",
            priority="NOW",
            reasons_json=["founder selected in CE01"],
            suggested_content_type="journal",
            suggested_role="cluster",
        )
        session.add(opportunity)
        await session.flush()
        session.add(
            ContentOpportunitySignal(
                content_opportunity_id=opportunity.id,
                signal_id=signal.id,
            )
        )

        await record_human_selection(
            session,
            opportunity_id=opportunity.id,
            selected_by="founder",
            reason="Test content without promoting the customer hypothesis.",
        )
        assert hypothesis.status == "PROPOSED"

        experiment = ContentExperiment(
            project_id=project.id,
            content_opportunity_id=opportunity.id,
            need_hypothesis_id=hypothesis.id,
            hypothesis_version=hypothesis.version,
            expected_behaviour="Reader moves from price anxiety to informed evaluation.",
            measurement_plan_json=["observe artwork transitions after publish"],
            metric_definitions_json=["artwork_transition"],
            minimum_evidence_json=["sufficient impressions before conclusion"],
        )
        content_case = ContentCase(
            project_id=project.id,
            content_type="journal",
            audience_hypothesis_id=audience.id,
            need_hypothesis_id=hypothesis.id,
            content_opportunity_id=opportunity.id,
            desired_action="Continue to a relevant artwork when useful.",
            content_hypothesis="Clear price framing can reduce uncertainty.",
            originality_statement="Use a real MOTGU artwork without inventing pricing formula.",
            reader_before="Price feels like a quality score.",
            reader_after="Price becomes one input for evaluation.",
        )
        session.add_all([experiment, content_case])
        await session.flush()

        locale_variant = LocaleVariant(
            content_case_id=content_case.id,
            locale="en",
            content_role="cluster",
            primary_question="How should I read the price of an artwork?",
            primary_intent="evaluate",
            primary_query="how to evaluate art price",
            emotion_arc_json=["uncertainty", "clarity", "confidence"],
            must_include_json=["displayed price is not a universal quality score"],
            must_not_claim_json=["MOTGU artist pricing formula"],
        )
        session.add(locale_variant)
        await session.flush()

        item = ContentItem(
            project_id=project.id,
            content_case_id=content_case.id,
            locale_variant_id=locale_variant.id,
            content_type="journal",
            canonical_key="journal:first-artwork-price:en",
        )
        session.add(item)
        await session.flush()

        version_1 = await create_next_content_version(
            session,
            content_item_id=item.id,
            change_reason="Initial CE01 candidate",
            content_json={"title": "How to Read the Price of an Artwork"},
        )
        version_2 = await create_next_content_version(
            session,
            content_item_id=item.id,
            change_reason="Editorial refresh",
            content_json={"title": "How to Read an Artwork Price"},
        )
        found = await get_content_item_by_canonical_key(
            session,
            project_id=project.id,
            canonical_key=item.canonical_key,
        )

        assert found is not None
        assert found.id == item.id
        assert version_1.content_item_id == version_2.content_item_id == item.id
        assert (version_1.version_no, version_2.version_no) == (1, 2)
        assert version_1.content_json != version_2.content_json
        assert hypothesis.status == "PROPOSED"
