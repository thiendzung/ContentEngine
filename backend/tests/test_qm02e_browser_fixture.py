from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.models import (
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    HumanSelection,
    NeedHypothesis,
)
from app.modules.harness.models import ContentRun
from scripts.seed_qm02e_browser_fixture import (
    Qm02eBrowserFixtureError,
    drift_target,
    seed_browser_fixture,
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
async def test_seed_browser_fixture_creates_supported_decision_scenarios() -> None:
    async with isolated_session() as session:
        result = await seed_browser_fixture(session)

        assert result["fixture_version"] == "qm02e-browser-v1"
        scenarios = result["scenarios"]
        assert isinstance(scenarios, list)

        by_name = {
            str(row["scenario"]): row
            for row in scenarios
            if isinstance(row, dict)
        }
        assert set(by_name) == {"create", "update", "refresh", "merge"}
        assert by_name["create"]["expected_decision"] == "CREATE"
        assert by_name["update"]["expected_decision"] == "UPDATE"
        assert by_name["refresh"]["expected_decision"] == "REFRESH"
        assert by_name["merge"]["expected_decision"] == "MERGE"

        assert by_name["create"]["target_content_item_ids"] == []
        assert len(by_name["update"]["target_content_item_ids"]) == 1
        assert len(by_name["refresh"]["target_content_item_ids"]) == 1
        assert len(by_name["merge"]["target_content_item_ids"]) == 2

        assert (
            await session.scalar(
                select(func.count()).select_from(NeedHypothesis)
            )
        ) == 4
        assert (
            await session.scalar(
                select(func.count()).select_from(ContentOpportunity)
            )
        ) == 4
        assert (
            await session.scalar(select(func.count()).select_from(ContentItem))
        ) == 4
        assert (
            await session.scalar(
                select(func.count()).select_from(ContentVersion)
            )
        ) == 5
        assert (
            await session.scalar(
                select(func.count()).select_from(HumanSelection)
            )
        ) == 0
        assert (
            await session.scalar(select(func.count()).select_from(ContentRun))
        ) == 0
        assert (
            await session.scalar(
                select(func.count()).select_from(OperatorCommand)
            )
        ) == 0


@pytest.mark.asyncio
async def test_seed_browser_fixture_requires_reset_test_state() -> None:
    async with isolated_session() as session:
        await seed_browser_fixture(session)

        with pytest.raises(
            Qm02eBrowserFixtureError,
            match="qm02e_fixture_requires_reset_test_database",
        ):
            await seed_browser_fixture(session)


@pytest.mark.asyncio
async def test_drift_target_uses_canonical_content_version_append() -> None:
    async with isolated_session() as session:
        seeded = await seed_browser_fixture(session)
        scenarios = seeded["scenarios"]
        assert isinstance(scenarios, list)
        update = next(
            row
            for row in scenarios
            if isinstance(row, dict) and row["scenario"] == "update"
        )
        target_id = str(update["target_content_item_ids"][0])

        before = int(
            await session.scalar(
                select(func.count())
                .select_from(ContentVersion)
                .join(
                    ContentItem,
                    ContentItem.id == ContentVersion.content_item_id,
                )
                .where(ContentItem.id == UUID(target_id))
            )
            or 0
        )
        result = await drift_target(session, scenario="update")
        after = int(
            await session.scalar(
                select(func.count())
                .select_from(ContentVersion)
                .join(
                    ContentItem,
                    ContentItem.id == ContentVersion.content_item_id,
                )
                .where(ContentItem.id == target_id)
            )
            or 0
        )

        assert result["content_item_id"] == target_id
        assert result["content_version_no"] == 2
        assert before == 1
        assert after == 2
