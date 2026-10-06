from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.research.keyword_plan.question_map import (
    QuestionMapError,
    build_question_map,
)
from app.modules.research.keyword_plan.router import get_question_map


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
    row = Project(
        slug=f"{label}-{uuid4().hex[:8]}",
        name=label,
        default_locale="en",
    )
    session.add(row)
    await session.flush()
    return row


async def _need(
    session: AsyncSession,
    *,
    project_id,
    statement: str = "Buyer needs confidence about authenticity.",
) -> NeedHypothesis:
    row = NeedHypothesis(
        project_id=project_id,
        type="question",
        statement=statement,
        audience_scope="first-time buyer",
        situation="considering an artwork",
        origin="customer_intelligence",
        status="SUPPORTED",
        alternative_explanations_json=[],
        missing_evidence_json=[],
        version=2,
    )
    session.add(row)
    await session.flush()
    return row


async def _signal(
    session: AsyncSession,
    *,
    project_id,
    text: str,
    locale: str = "en",
    source_kind: str = "SEARCH",
) -> Signal:
    row = Signal(
        project_id=project_id,
        source_kind=source_kind,
        scope="market_web",
        observed_text=text,
        source_url=f"https://example.com/{uuid4().hex}",
        locale=locale,
        context="QM-01A fixture",
        captured_at=datetime.now(UTC),
        fingerprint=uuid4().hex,
        provenance_json={"provider": "fixture", "method": "test"},
    )
    session.add(row)
    await session.flush()
    return row


async def _link(
    session: AsyncSession,
    *,
    need: NeedHypothesis,
    signal: Signal,
    relation: str = "supports",
) -> None:
    session.add(
        NeedHypothesisSignal(
            need_hypothesis_id=need.id,
            signal_id=signal.id,
            relation=relation,
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_question_map_is_deterministic_and_provenance_bounded() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)
        first = await _signal(
            session,
            project_id=project.id,
            text="How do I know this painting is original?",
        )
        second = await _signal(
            session,
            project_id=project.id,
            text="How do I know this painting is original?",
        )
        await _link(session, need=need, signal=first)
        await _link(session, need=need, signal=second)

        first_map = await build_question_map(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        replay = await build_question_map(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="EN",
        )

        assert replay == first_map
        assert first_map["need"]["id"] == str(need.id)
        assert first_map["need"]["version"] == 2
        assert first_map["counts"] == {
            "questions": 1,
            "search_signals": 2,
        }
        question = first_map["questions"][0]
        assert question["normalized_text"] == (
            "how do i know this painting is original"
        )
        assert question["signal_refs"] == sorted(
            [str(first.id), str(second.id)]
        )
        assert first_map["signal_refs"] == sorted(
            [str(first.id), str(second.id)]
        )
        assert len(first_map["snapshot_hash"]) == 64


@pytest.mark.asyncio
async def test_question_map_excludes_explicit_context_only_search_signal() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)
        question = await _signal(
            session,
            project_id=project.id,
            text="How do I know this painting is original?",
        )
        context = await _signal(
            session,
            project_id=project.id,
            text="Complete guide to buying original art",
        )
        context.provenance_json = {
            "provider": "serper",
            "method": "organic",
            "question_eligible": False,
        }
        await _link(session, need=need, signal=question)
        await _link(session, need=need, signal=context)

        payload = await build_question_map(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )

        assert payload["counts"] == {
            "questions": 1,
            "search_signals": 1,
        }
        assert payload["signal_refs"] == [str(question.id)]
        assert payload["questions"][0]["text"] == question.observed_text


@pytest.mark.asyncio
async def test_question_map_is_locale_specific_and_ignores_noncanonical_evidence() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)
        en = await _signal(
            session,
            project_id=project.id,
            text="How do I carry a painting home?",
            locale="en",
        )
        vi = await _signal(
            session,
            project_id=project.id,
            text="Mang tranh về nhà bằng cách nào?",
            locale="vi",
        )
        market = await _signal(
            session,
            project_id=project.id,
            text="General market observation",
            locale="en",
            source_kind="MARKET",
        )
        contradiction = await _signal(
            session,
            project_id=project.id,
            text="Shipping is not a concern.",
            locale="en",
        )
        for signal in (en, vi, market):
            await _link(session, need=need, signal=signal)
        await _link(
            session,
            need=need,
            signal=contradiction,
            relation="contradicts",
        )

        en_map = await build_question_map(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )
        vi_map = await build_question_map(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="vi",
        )

        assert [row["text"] for row in en_map["questions"]] == [
            "How do I carry a painting home?"
        ]
        assert [row["text"] for row in vi_map["questions"]] == [
            "Mang tranh về nhà bằng cách nào?"
        ]
        assert str(market.id) not in en_map["signal_refs"]
        assert str(contradiction.id) not in en_map["signal_refs"]


@pytest.mark.asyncio
async def test_question_map_empty_view_is_explicit() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)

        result = await build_question_map(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )

        assert result["questions"] == []
        assert result["signal_refs"] == []
        assert result["counts"] == {
            "questions": 0,
            "search_signals": 0,
        }
        assert isinstance(result["snapshot_hash"], str)


@pytest.mark.asyncio
async def test_question_map_fails_closed_for_cross_project_need() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        foreign = await _project(session, "foreign")
        foreign_need = await _need(session, project_id=foreign.id)

        with pytest.raises(
            QuestionMapError,
            match="question_map_need_not_found",
        ):
            await build_question_map(
                session,
                project_id=project.id,
                need_id=foreign_need.id,
                locale="en",
            )


@pytest.mark.asyncio
async def test_question_map_router_is_read_only() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)
        signal = await _signal(
            session,
            project_id=project.id,
            text="What should I ask before buying art?",
        )
        await _link(session, need=need, signal=signal)

        before_needs = await session.scalar(
            select(func.count()).select_from(NeedHypothesis)
        )
        before_signals = await session.scalar(
            select(func.count()).select_from(Signal)
        )
        before_links = await session.scalar(
            select(func.count()).select_from(NeedHypothesisSignal)
        )

        payload = await get_question_map(
            need_id=need.id,
            locale="en",
            project_slug=project.slug,
            session=session,
        )

        assert payload["project"]["id"] == str(project.id)
        assert payload["need"]["id"] == str(need.id)
        assert payload["counts"]["questions"] == 1
        assert await session.scalar(
            select(func.count()).select_from(NeedHypothesis)
        ) == before_needs
        assert await session.scalar(
            select(func.count()).select_from(Signal)
        ) == before_signals
        assert await session.scalar(
            select(func.count()).select_from(NeedHypothesisSignal)
        ) == before_links
