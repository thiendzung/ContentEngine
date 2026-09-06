from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
    NeedHypothesis,
    Project,
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
async def test_locale_variant_and_version_numbers_are_unique() -> None:
    async with isolated_session() as session:
        project = Project(slug=f"motgu-{uuid4().hex[:8]}", name="MOTGU")
        session.add(project)
        await session.flush()

        hypothesis = NeedHypothesis(
            project_id=project.id,
            type="question",
            statement="A test hypothesis",
            audience_scope="test audience",
            situation="test situation",
            origin="founder_proposed",
        )
        session.add(hypothesis)
        await session.flush()

        opportunity = ContentOpportunity(
            project_id=project.id,
            need_hypothesis_id=hypothesis.id,
            locale="en",
            reader="reader",
            situation="situation",
            need="need",
            question="question",
            intent="learn",
            promise="promise",
            motgu_material_refs_json=[],
            material_gaps_json=[],
            existing_content_refs_json=[],
            what_is_actually_new="new",
            next_discovery_step="next",
            decision="CREATE",
            priority="NEXT",
            reasons_json=[],
            suggested_content_type="journal",
        )
        session.add(opportunity)
        await session.flush()

        content_case = ContentCase(
            project_id=project.id,
            content_type="journal",
            need_hypothesis_id=hypothesis.id,
            content_opportunity_id=opportunity.id,
            desired_action="read",
            content_hypothesis="test",
            originality_statement="test",
            reader_before="before",
            reader_after="after",
        )
        session.add(content_case)
        await session.flush()

        locale_variant = LocaleVariant(
            content_case_id=content_case.id,
            locale="en",
            content_role="cluster",
            primary_question="question",
            primary_intent="learn",
        )
        session.add(locale_variant)
        await session.flush()

        duplicate_locale = LocaleVariant(
            content_case_id=content_case.id,
            locale="en",
            content_role="pillar",
            primary_question="another",
            primary_intent="learn",
        )
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(duplicate_locale)
                await session.flush()

        item = ContentItem(
            project_id=project.id,
            content_case_id=content_case.id,
            locale_variant_id=locale_variant.id,
            content_type="journal",
            canonical_key=f"journal:{uuid4().hex}:en",
        )
        session.add(item)
        await session.flush()
        session.add(
            ContentVersion(
                content_item_id=item.id,
                version_no=1,
                change_reason="v1",
                content_json={},
            )
        )
        await session.flush()

        duplicate_version = ContentVersion(
            content_item_id=item.id,
            version_no=1,
            change_reason="duplicate",
            content_json={},
        )
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(duplicate_version)
                await session.flush()
