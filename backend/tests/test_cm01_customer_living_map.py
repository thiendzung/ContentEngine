from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_review_console import _approved_fixture

from app.core.database import engine
from app.main import app
from app.modules.content_engine.models import (
    AudienceHypothesis,
    NeedHypothesis,
    Project,
    SettingsVersion,
    Signal,
)
from app.modules.customer_intelligence.insights import (
    ensure_customer_insight,
    link_customer_insight_signal,
)
from app.modules.customer_intelligence.living_map import (
    CustomerMapError,
    build_customer_map_snapshot,
    compare_customer_map_snapshots,
    customer_map_audience_detail,
    customer_map_changes,
    customer_map_summary,
    ensure_customer_insight_need_link,
    refresh_customer_map_snapshot_artifact,
    resolve_journey_config,
)
from app.modules.customer_intelligence.models import CustomerInsightNeedLink
from app.modules.harness.models import Artifact, ModelCall, ToolCall


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


async def _audience(
    session: AsyncSession,
    *,
    project_id,
    name: str,
) -> AudienceHypothesis:
    audience = AudienceHypothesis(
        project_id=project_id,
        name=name,
        description=f"{name} description",
        status="PROPOSED",
    )
    session.add(audience)
    await session.flush()
    return audience


async def _need(
    session: AsyncSession,
    *,
    project_id,
    audience_hypothesis_id=None,
    statement: str = "Customer needs a reliable answer.",
) -> NeedHypothesis:
    need = NeedHypothesis(
        project_id=project_id,
        audience_hypothesis_id=audience_hypothesis_id,
        type="question",
        statement=statement,
        audience_scope="first-time buyer",
        situation="considering an artwork",
        origin="research",
        status="PROPOSED",
        alternative_explanations_json=[],
        missing_evidence_json=[],
        version=1,
    )
    session.add(need)
    await session.flush()
    return need


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
        context="CM-01 fixture",
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
async def test_insight_need_link_is_exact_scoped_and_immutable() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        other = await _project(session, "other")
        audience = await _audience(
            session,
            project_id=project.id,
            name="First-time buyer",
        )
        other_audience = await _audience(
            session,
            project_id=project.id,
            name="Different audience",
        )
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="fear",
            statement="Buyer worries about authenticity.",
            audience_hypothesis_id=audience.id,
        )
        need = await _need(
            session,
            project_id=project.id,
            audience_hypothesis_id=audience.id,
        )

        first = await ensure_customer_insight_need_link(
            session,
            customer_insight_id=insight.id,
            need_hypothesis_id=need.id,
            relation="supports",
        )
        replay = await ensure_customer_insight_need_link(
            session,
            customer_insight_id=insight.id,
            need_hypothesis_id=need.id,
            relation="supports",
        )
        assert replay.customer_insight_id == first.customer_insight_id

        with pytest.raises(
            CustomerMapError,
            match="customer_map_insight_need_replay_conflict",
        ):
            await ensure_customer_insight_need_link(
                session,
                customer_insight_id=insight.id,
                need_hypothesis_id=need.id,
                relation="contradicts",
            )

        cross_project_need = await _need(
            session,
            project_id=other.id,
        )
        with pytest.raises(
            CustomerMapError,
            match="customer_map_insight_need_project_mismatch",
        ):
            await ensure_customer_insight_need_link(
                session,
                customer_insight_id=insight.id,
                need_hypothesis_id=cross_project_need.id,
                relation="supports",
            )

        wrong_audience_need = await _need(
            session,
            project_id=project.id,
            audience_hypothesis_id=other_audience.id,
        )
        with pytest.raises(
            CustomerMapError,
            match="customer_map_insight_need_audience_mismatch",
        ):
            await ensure_customer_insight_need_link(
                session,
                customer_insight_id=insight.id,
                need_hypothesis_id=wrong_audience_need.id,
                relation="supports",
            )

        with pytest.raises(
            DBAPIError,
            match="customer_insight_need_link_is_immutable",
        ):
            async with session.begin_nested():
                first.relation = "context"
                await session.flush()

        await session.refresh(first)
        with pytest.raises(
            DBAPIError,
            match="customer_insight_need_link_delete_forbidden",
        ):
            async with session.begin_nested():
                await session.delete(first)
                await session.flush()


@pytest.mark.asyncio
async def test_need_and_audience_scope_cannot_drift_after_map_binding() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        other = await _project(session, "other")
        audience = await _audience(
            session,
            project_id=project.id,
            name="First-time buyer",
        )
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="question",
            statement="Buyer asks how authenticity is verified.",
            audience_hypothesis_id=audience.id,
        )
        need = await _need(
            session,
            project_id=project.id,
            audience_hypothesis_id=audience.id,
        )
        await ensure_customer_insight_need_link(
            session,
            customer_insight_id=insight.id,
            need_hypothesis_id=need.id,
            relation="supports",
        )

        with pytest.raises(
            DBAPIError,
            match="customer_map_linked_need_scope_immutable",
        ):
            async with session.begin_nested():
                need.project_id = other.id
                await session.flush()

        await session.refresh(need)
        with pytest.raises(
            DBAPIError,
            match="customer_map_audience_project_change_forbidden",
        ):
            async with session.begin_nested():
                audience.project_id = other.id
                await session.flush()


@pytest.mark.asyncio
async def test_journey_config_has_builtin_default_and_approved_override() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        default = await resolve_journey_config(
            session,
            project_id=project.id,
        )
        assert default.source_refs == ("builtin:customer-journey:v1",)
        assert [stage["key"] for stage in default.stages] == [
            "unaware",
            "aware",
            "interested",
            "preference",
            "trust",
            "purchase",
            "satisfied",
            "referral",
            "repeat_purchase",
        ]

        version = SettingsVersion(
            project_id=project.id,
            scope_type="project",
            scope_key=project.slug,
            version=1,
            settings_json={
                "customer_living_map": {
                    "journey": {
                        "stages": [
                            {
                                "key": "discover",
                                "label": "Discover",
                                "description": None,
                            },
                            {
                                "key": "buy",
                                "label": "Buy",
                                "description": "Purchase stage",
                            },
                        ]
                    }
                }
            },
            status="active",
            change_reason="CM-01 journey fixture",
            approved_by="founder",
        )
        session.add(version)
        await session.flush()

        configured = await resolve_journey_config(
            session,
            project_id=project.id,
        )
        assert [stage["key"] for stage in configured.stages] == [
            "discover",
            "buy",
        ]
        assert configured.source_refs == (
            f"settings_version:{version.id}:v1",
        )


@pytest.mark.asyncio
async def test_journey_config_conflict_fails_closed() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        for index, stages in enumerate(
            (
                [{"key": "discover", "label": "Discover"}],
                [{"key": "aware", "label": "Aware"}],
            ),
            start=1,
        ):
            row = SettingsVersion(
                project_id=None if index == 1 else project.id,
                scope_type="system" if index == 1 else "project",
                scope_key=f"system-cm01-{uuid4().hex[:6]}"
                if index == 1
                else project.slug,
                version=1,
                settings_json={
                    "customer_living_map": {
                        "journey": {"stages": stages}
                    }
                },
                status="active",
                change_reason="CM-01 conflict fixture",
                approved_by="founder",
            )
            session.add(row)
        await session.flush()

        with pytest.raises(
            CustomerMapError,
            match="customer_map_journey_config_conflict",
        ):
            await resolve_journey_config(
                session,
                project_id=project.id,
            )


@pytest.mark.asyncio
async def test_customer_map_uses_latest_insight_version_and_explicit_need_link() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        audience = await _audience(
            session,
            project_id=project.id,
            name="First-time buyer",
        )
        need = await _need(
            session,
            project_id=project.id,
            audience_hypothesis_id=audience.id,
            statement="Customer needs confidence about authenticity.",
        )
        first = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="fear",
            statement="Buyer worries the painting may not be original.",
            audience_hypothesis_id=audience.id,
        )
        revised = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="fear",
            statement="Buyer needs confidence about the specific artwork.",
            audience_hypothesis_id=audience.id,
            insight_key=first.insight_key,
            version=2,
        )
        support = await _signal(
            session,
            project_id=project.id,
            text="How can I know this painting is original?",
        )
        await link_customer_insight_signal(
            session,
            customer_insight_id=revised.id,
            signal_id=support.id,
            relation="supports",
        )
        await ensure_customer_insight_need_link(
            session,
            customer_insight_id=revised.id,
            need_hypothesis_id=need.id,
            relation="supports",
        )

        snapshot = await build_customer_map_snapshot(
            session,
            project_id=project.id,
        )

        assert len(snapshot["insights"]) == 1
        insight_payload = snapshot["insights"][0]
        assert insight_payload["id"] == str(revised.id)
        assert insight_payload["version"] == 2
        assert insight_payload["need_links"] == [
            {
                "need_hypothesis_id": str(need.id),
                "relation": "supports",
            }
        ]

        detail = await customer_map_audience_detail(
            session,
            project_id=project.id,
            audience_id=audience.id,
        )
        assert detail["audience"]["id"] == str(audience.id)
        assert [row["id"] for row in detail["needs"]] == [str(need.id)]
        assert [row["id"] for row in detail["insights"]] == [
            str(revised.id)
        ]

        summary = await customer_map_summary(
            session,
            project_id=project.id,
        )
        assert summary["counts"]["audiences"] == 1
        assert summary["counts"]["needs"] == 1
        assert summary["counts"]["insights"] == 1


@pytest.mark.asyncio
async def test_change_report_distinguishes_duplicate_support_and_contradiction() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        insight = await ensure_customer_insight(
            session,
            project_id=project.id,
            insight_type="pain",
            statement="Pricing uncertainty can slow a purchase.",
        )
        original = await _signal(
            session,
            project_id=project.id,
            text="I could not find the price.",
        )
        await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=original.id,
            relation="supports",
        )
        baseline = await build_customer_map_snapshot(
            session,
            project_id=project.id,
        )

        repost = await _signal(
            session,
            project_id=project.id,
            text="I could not find the price.",
            duplicate_of_id=original.id,
        )
        await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=repost.id,
            relation="supports",
        )
        after_duplicate = await build_customer_map_snapshot(
            session,
            project_id=project.id,
        )
        duplicate_report = compare_customer_map_snapshots(
            baseline,
            after_duplicate,
        )
        assert duplicate_report["counts"]["DUPLICATE"] == 1
        assert duplicate_report["counts"]["SUPPORT"] == 0

        independent = await _signal(
            session,
            project_id=project.id,
            text="I am unsure whether this price is fair.",
        )
        contradiction = await _signal(
            session,
            project_id=project.id,
            text="The displayed price was clear enough.",
        )
        await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=independent.id,
            relation="supports",
        )
        await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=contradiction.id,
            relation="contradicts",
        )
        after_new_evidence = await build_customer_map_snapshot(
            session,
            project_id=project.id,
        )
        report = compare_customer_map_snapshots(
            after_duplicate,
            after_new_evidence,
        )
        assert report["counts"]["SUPPORT"] == 1
        assert report["counts"]["CONTRADICT"] == 1


@pytest.mark.asyncio
async def test_snapshot_refresh_is_incremental_and_does_not_run_models_or_tools() -> None:
    async with isolated_session() as session:
        base = await _approved_fixture(session)
        run = base.writer_runs["en"]

        model_calls_before = await session.scalar(
            select(func.count()).select_from(ModelCall)
        )
        tool_calls_before = await session.scalar(
            select(func.count()).select_from(ToolCall)
        )

        first = await refresh_customer_map_snapshot_artifact(
            session,
            run_id=run.id,
            step_run_id=None,
        )
        replay = await refresh_customer_map_snapshot_artifact(
            session,
            run_id=run.id,
            step_run_id=None,
        )
        assert replay.artifact.id == first.artifact.id
        assert replay.change_report["counts"] == {
            "NEW": 0,
            "SUPPORT": 0,
            "CONTRADICT": 0,
            "DUPLICATE": 0,
        }

        insight = await ensure_customer_insight(
            session,
            project_id=run.project_id,
            insight_type="question",
            statement=f"CM-01 incremental {uuid4().hex}",
        )
        changed = await refresh_customer_map_snapshot_artifact(
            session,
            run_id=run.id,
            step_run_id=None,
        )
        assert changed.artifact.id != first.artifact.id
        assert changed.artifact.version == first.artifact.version + 1
        assert changed.change_report["counts"]["NEW"] >= 1

        model_calls_after = await session.scalar(
            select(func.count()).select_from(ModelCall)
        )
        tool_calls_after = await session.scalar(
            select(func.count()).select_from(ToolCall)
        )
        assert model_calls_after == model_calls_before
        assert tool_calls_after == tool_calls_before
        assert insight.id is not None


@pytest.mark.asyncio
async def test_changes_api_model_is_read_only_against_latest_snapshot() -> None:
    async with isolated_session() as session:
        base = await _approved_fixture(session)
        run = base.writer_runs["en"]
        persisted = await refresh_customer_map_snapshot_artifact(
            session,
            run_id=run.id,
            step_run_id=None,
        )
        count_before = await session.scalar(
            select(func.count()).select_from(Artifact)
        )
        changes = await customer_map_changes(
            session,
            project_id=run.project_id,
        )
        count_after = await session.scalar(
            select(func.count()).select_from(Artifact)
        )

        assert changes["baseline"] is False
        assert changes["previous_snapshot_hash"] == persisted.artifact.content_hash
        assert count_after == count_before


def test_customer_map_routes_are_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/customer-map/summary" in paths
    assert "/customer-map/audiences/{audience_id}" in paths
    assert "/customer-map/changes" in paths
