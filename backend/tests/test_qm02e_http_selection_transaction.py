from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.modules.content_engine.models import (
    ContentOpportunity,
    ContentOpportunitySignal,
    HumanSelection,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)


async def _seed_create_candidate() -> tuple[str, UUID, list[UUID]]:
    settings = get_settings()
    assert settings.app_env == "test"

    project_slug = f"qm02e-http-{uuid4().hex[:10]}"
    signal_ids: list[UUID] = []

    async with SessionLocal() as session:
        project = Project(
            slug=project_slug,
            name="QM-02E HTTP transaction regression",
            default_locale="en",
        )
        session.add(project)
        await session.flush()

        need = NeedHypothesis(
            project_id=project.id,
            type="question",
            statement="Buyer needs confidence setting a first-art budget.",
            audience_scope="first-time art buyer",
            situation="considering a first original painting",
            origin="qm02e_http_test",
            status="SUPPORTED",
            alternative_explanations_json=[],
            missing_evidence_json=[],
            version=1,
        )
        session.add(need)
        await session.flush()

        for observed_text in (
            "How much should I spend on my first painting?",
            "What budget should I set for my first painting?",
        ):
            signal = Signal(
                project_id=project.id,
                source_kind="SEARCH",
                scope="market_web",
                observed_text=observed_text,
                source_url=f"https://fixture.invalid/{uuid4().hex}",
                locale="en",
                context="QM-02E HTTP transaction regression",
                captured_at=datetime.now(UTC),
                fingerprint=uuid4().hex,
                independence_group=uuid4().hex,
                provenance_json={
                    "provider": "fixture",
                    "method": "people_also_ask",
                    "question_eligible": True,
                    "factual_evidence_eligible": False,
                },
            )
            session.add(signal)
            await session.flush()
            signal_ids.append(signal.id)
            session.add(
                NeedHypothesisSignal(
                    need_hypothesis_id=need.id,
                    signal_id=signal.id,
                    relation="supports",
                )
            )

        need_id = need.id
        await session.commit()

    return project_slug, need_id, signal_ids


async def _cleanup_fixture(
    *,
    project_slug: str,
    need_id: UUID,
    signal_ids: list[UUID],
) -> None:
    async with SessionLocal() as session:
        project = await session.scalar(
            select(Project).where(Project.slug == project_slug)
        )
        if project is None:
            return

        opportunity_ids = list(
            (
                await session.scalars(
                    select(ContentOpportunity.id).where(
                        ContentOpportunity.project_id == project.id
                    )
                )
            ).all()
        )
        if opportunity_ids:
            await session.execute(
                delete(HumanSelection).where(
                    HumanSelection.content_opportunity_id.in_(opportunity_ids)
                )
            )
            await session.execute(
                delete(ContentOpportunitySignal).where(
                    ContentOpportunitySignal.content_opportunity_id.in_(
                        opportunity_ids
                    )
                )
            )
            await session.execute(
                delete(ContentOpportunity).where(
                    ContentOpportunity.id.in_(opportunity_ids)
                )
            )

        await session.execute(
            delete(NeedHypothesisSignal).where(
                NeedHypothesisSignal.need_hypothesis_id == need_id
            )
        )
        if signal_ids:
            await session.execute(
                delete(Signal).where(Signal.id.in_(signal_ids))
            )
        await session.execute(
            delete(NeedHypothesis).where(NeedHypothesis.id == need_id)
        )
        await session.delete(project)
        await session.commit()


@pytest.mark.asyncio
async def test_http_selection_commits_before_followup_route_request() -> None:
    project_slug, need_id, signal_ids = await _seed_create_candidate()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            architecture_response = await client.get(
                "/question-map/architecture",
                params={
                    "project_slug": project_slug,
                    "need_id": str(need_id),
                    "locale": "en",
                },
            )
            assert architecture_response.status_code == 200
            architecture = architecture_response.json()
            candidate = next(
                row
                for row in architecture["candidates"]
                if row["role"] == "cluster"
                and row["decision"] == "CREATE"
                and row["selection_readiness"]
                == "READY_FOR_HUMAN_SELECTION"
            )

            selection_response = await client.post(
                "/question-map/opportunities/select",
                json={
                    "project_slug": project_slug,
                    "need_id": str(need_id),
                    "locale": "en",
                    "architecture_candidate_key": candidate["candidate_key"],
                    "expected_architecture_snapshot_hash": architecture[
                        "snapshot_hash"
                    ],
                    "expected_planner_snapshot_hash": architecture[
                        "planner_snapshot_hash"
                    ],
                    "selected_by": "founder",
                    "selection_reason": (
                        "Persist the exact browser-selected CREATE candidate."
                    ),
                    "promise": "Give a practical first-art budget decision path.",
                    "coverage_requirements": [
                        "Explain the budget decision criteria.",
                        "Show what the buyer should verify.",
                    ],
                },
            )
            assert selection_response.status_code == 200
            selected = selection_response.json()
            opportunity_id = UUID(selected["content_opportunity_id"])

            route_response = await client.get(
                f"/question-map/opportunities/{opportunity_id}/route",
                params={"project_slug": project_slug},
            )
            assert route_response.status_code == 200
            route = route_response.json()
            assert route["decision"] == "CREATE"
            assert route["route"] == "CREATE_NEW_CONTENT"

        async with SessionLocal() as session:
            opportunity = await session.get(ContentOpportunity, opportunity_id)
            selection = await session.scalar(
                select(HumanSelection).where(
                    HumanSelection.content_opportunity_id == opportunity_id
                )
            )
            assert opportunity is not None
            assert selection is not None
            assert opportunity.selected_by == "founder"
            assert selection.selected_by == "founder"
    finally:
        await _cleanup_fixture(
            project_slug=project_slug,
            need_id=need_id,
            signal_ids=signal_ids,
        )
