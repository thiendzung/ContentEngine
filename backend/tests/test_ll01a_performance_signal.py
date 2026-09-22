from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_pm01_publish_measurement import (
    FakeWordPress,
    PMFixture,
    _approve_and_claim,
    _fixture,
    isolated_session,
)

from app.modules.content_engine.models import ContentItemJourneyStage, ContentVersion, Signal
from app.modules.customer_intelligence.insights import (
    customer_insight_evidence_counts,
    ensure_customer_insight,
    link_customer_insight_signal,
)
from app.modules.customer_intelligence.models import CustomerInsight
from app.modules.learning.performance_signal import (
    PerformanceSignalError,
    materialize_performance_signal,
)
from app.modules.measurement.models import PerformanceMetric
from app.modules.measurement.service import (
    MetricInput,
    ingest_performance_snapshot,
    record_performance_observation,
)
from app.modules.publishing.service import (
    begin_wordpress_dispatch,
    execute_wordpress_call,
    prepare_publish_package,
    record_wordpress_execution_result,
)


async def _publish(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    *,
    worker_id: str,
) -> tuple[PMFixture, object]:
    fixture = await _fixture(session, monkeypatch)
    package = await prepare_publish_package(
        session,
        content_version_id=fixture.version.id,
        experiment_id=fixture.experiment.id,
        slug=f"ll01a-{uuid4().hex[:8]}",
        action="publish",
    )
    _decision, _dispatch, claimed = await _approve_and_claim(
        session,
        package_run_id=package.run.id,
        package_artifact_id=package.artifact.id,
        worker_id=worker_id,
    )
    gateway = FakeWordPress()
    prepared = await begin_wordpress_dispatch(
        session,
        job_id=claimed.id,
        worker_id=worker_id,
    )
    external = await execute_wordpress_call(
        gateway=gateway,
        request=prepared.request,
    )
    mapping, event = await record_wordpress_execution_result(
        session,
        job_id=claimed.id,
        worker_id=worker_id,
        result=external,
    )
    assert mapping is not None
    assert event is not None
    assert event.external_status == "publish"
    return fixture, mapping


async def _record_search_observation(
    session: AsyncSession,
    *,
    fixture: PMFixture,
    mapping,
    statement: str = "Interpretation text must not become factual Signal content.",
):
    now = datetime.now(UTC)
    review_start = fixture.experiment.review_window_start
    assert review_start is not None
    window_start = max(review_start, now - timedelta(hours=1))
    snapshot = await ingest_performance_snapshot(
        session,
        published_content_id=mapping.id,
        content_version_id=fixture.version.id,
        provider="search_console",
        window_start=window_start,
        window_end=now,
        raw_metrics={
            "page": mapping.canonical_url,
            "raw_secret": "must-not-flow-to-signal",
        },
        metrics=[
            MetricInput(
                metric_date=now,
                metric_name="impressions",
                metric_value=120,
                dimensions={"query": "synthetic private dimension"},
            ),
            MetricInput(
                metric_date=now,
                metric_name="clicks",
                metric_value=9,
                dimensions={"query": "synthetic private dimension"},
            ),
        ],
    )
    observation = await record_performance_observation(
        session,
        published_content_id=mapping.id,
        content_version_id=fixture.version.id,
        observation_type="search_exposure",
        statement=statement,
        data_status="EARLY_SIGNAL",
        observed_at=now,
        metric_refs=[row.id for row in snapshot.metrics],
    )
    return observation, snapshot


@pytest.mark.asyncio
async def test_ll01a_materializes_factual_idempotent_signal_without_truth_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, mapping = await _publish(
            session,
            monkeypatch,
            worker_id="ll01a-factual-worker",
        )
        observation, _snapshot = await _record_search_observation(
            session,
            fixture=fixture,
            mapping=mapping,
        )
        insight_count_before = int(
            await session.scalar(select(func.count()).select_from(CustomerInsight)) or 0
        )

        first = await materialize_performance_signal(
            session,
            observation_id=observation.id,
        )
        assert first.replayed is False
        signal = first.signal
        assert signal.source_kind == "MOTGU"
        assert signal.scope == "motgu_site"
        assert signal.locale == "en"
        assert signal.source_url == mapping.canonical_url
        assert signal.external_id == f"content_performance_observation:{observation.id}"
        assert signal.independence_group == f"experiment:{fixture.experiment.id}"
        assert "Interpretation text" not in signal.observed_text
        assert "impressions=120.000000" in signal.observed_text
        assert "clicks=9.000000" in signal.observed_text

        serialized = json.dumps(signal.provenance_json, sort_keys=True)
        assert "must-not-flow-to-signal" not in serialized
        assert "synthetic private dimension" not in serialized
        assert observation.statement not in serialized
        assert signal.provenance_json["content_performance_observation"][
            "interpretation_fields_excluded"
        ] == ["statement", "observation_type", "data_status"]
        assert signal.provenance_json["customer"]["need_hypothesis_id"] == str(
            fixture.need.id
        )
        assert signal.provenance_json["customer"]["journey_stages"] == ["trust"]
        assert signal.provenance_json["lens_selection"]["primary_lens"] == "SIGNALS"
        assert signal.provenance_json["experiment"]["id"] == str(
            fixture.experiment.id
        )

        replay = await materialize_performance_signal(
            session,
            observation_id=observation.id,
        )
        assert replay.replayed is True
        assert replay.signal.id == signal.id
        assert replay.signal.fingerprint == signal.fingerprint
        assert int(
            await session.scalar(
                select(func.count()).select_from(Signal).where(
                    Signal.external_id == signal.external_id
                )
            )
            or 0
        ) == 1

        await session.refresh(fixture.need)
        await session.refresh(fixture.experiment)
        assert fixture.need.status == "TESTING"
        assert fixture.experiment.result == "PENDING"
        assert int(
            await session.scalar(select(func.count()).select_from(CustomerInsight)) or 0
        ) == insight_count_before


@pytest.mark.asyncio
async def test_ll01a_collapses_multiple_provider_observations_by_experiment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, mapping = await _publish(
            session,
            monkeypatch,
            worker_id="ll01a-independence-worker",
        )
        search_observation, _search_snapshot = await _record_search_observation(
            session,
            fixture=fixture,
            mapping=mapping,
        )

        now = datetime.now(UTC)
        review_start = fixture.experiment.review_window_start
        assert review_start is not None
        analytics = await ingest_performance_snapshot(
            session,
            published_content_id=mapping.id,
            content_version_id=fixture.version.id,
            provider="analytics",
            window_start=max(review_start, now - timedelta(hours=1)),
            window_end=now,
            raw_metrics={"aggregate": "synthetic"},
            metrics=[
                MetricInput(
                    metric_date=now,
                    metric_name="sessions",
                    metric_value=20,
                ),
                MetricInput(
                    metric_date=now,
                    metric_name="engaged_sessions",
                    metric_value=11,
                ),
            ],
        )
        analytics_observation = await record_performance_observation(
            session,
            published_content_id=mapping.id,
            content_version_id=fixture.version.id,
            observation_type="engagement",
            statement="Engagement is visible; causality remains unknown.",
            data_status="EARLY_SIGNAL",
            observed_at=now,
            metric_refs=[row.id for row in analytics.metrics],
        )

        first = await materialize_performance_signal(
            session,
            observation_id=search_observation.id,
        )
        second = await materialize_performance_signal(
            session,
            observation_id=analytics_observation.id,
        )
        assert first.signal.id != second.signal.id
        assert first.signal.independence_group == second.signal.independence_group
        assert first.signal.independence_group == f"experiment:{fixture.experiment.id}"

        insight = await ensure_customer_insight(
            session,
            project_id=fixture.project.id,
            insight_type="behaviour",
            statement="Readers may continue from this guide to a deeper evaluation step.",
            audience_hypothesis_id=fixture.content_case.audience_hypothesis_id,
            situation="after reading the published guide",
        )
        await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=first.signal.id,
            relation="supports",
        )
        await link_customer_insight_signal(
            session,
            customer_insight_id=insight.id,
            signal_id=second.signal.id,
            relation="supports",
        )
        counts = await customer_insight_evidence_counts(
            session,
            customer_insight_id=insight.id,
        )
        assert counts.supports == 2
        assert counts.independent_supports == 1


@pytest.mark.asyncio
async def test_ll01a_historical_version_signal_remains_stable_after_current_version_moves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, mapping = await _publish(
            session,
            monkeypatch,
            worker_id="ll01a-history-worker",
        )
        newer_payload = json.loads(json.dumps(fixture.version.content_json))
        newer_payload["ll01a_revision"] = "newer"
        newer = ContentVersion(
            content_item_id=fixture.item.id,
            version_no=fixture.version.version_no + 1,
            final_artifact_id=fixture.final_artifact.id,
            change_reason="Create a later approved version for historical identity proof.",
            status="approved",
            content_json=newer_payload,
            created_by_run_id=fixture.source_run.id,
        )
        session.add(newer)
        await session.flush()
        mapping.current_content_version_id = newer.id
        await session.flush()

        observation, _snapshot = await _record_search_observation(
            session,
            fixture=fixture,
            mapping=mapping,
            statement="Historical metrics stay historical.",
        )
        result = await materialize_performance_signal(
            session,
            observation_id=observation.id,
        )
        assert result.signal.provenance_json["content"]["content_version_id"] == str(
            fixture.version.id
        )

        replay = await materialize_performance_signal(
            session,
            observation_id=observation.id,
        )
        assert replay.replayed is True
        assert replay.signal.id == result.signal.id
        assert replay.signal.fingerprint == result.signal.fingerprint


@pytest.mark.asyncio
async def test_ll01a_uses_frozen_publish_package_customer_identity_after_map_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, mapping = await _publish(
            session,
            monkeypatch,
            worker_id="ll01a-frozen-customer-identity",
        )
        frozen_need_version = fixture.need.version

        trust_stage = await session.get(
            ContentItemJourneyStage,
            (fixture.item.id, "trust"),
        )
        assert trust_stage is not None
        await session.delete(trust_stage)
        session.add(
            ContentItemJourneyStage(
                content_item_id=fixture.item.id,
                stage_key="interest",
                linked_by="founder",
                reason="Simulate a later Customer Map planning change.",
            )
        )
        fixture.need.version = frozen_need_version + 1
        await session.flush()

        observation, _snapshot = await _record_search_observation(
            session,
            fixture=fixture,
            mapping=mapping,
            statement="Current map state must not rewrite frozen publish identity.",
        )
        result = await materialize_performance_signal(
            session,
            observation_id=observation.id,
        )
        customer = result.signal.provenance_json["customer"]
        assert customer["need_hypothesis_version"] == frozen_need_version
        assert customer["journey_stages"] == ["trust"]
        assert customer["identity_source"] == "publish_package"


@pytest.mark.asyncio
async def test_ll01a_fails_closed_on_cross_content_metric_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture_a, mapping_a = await _publish(
            session,
            monkeypatch,
            worker_id="ll01a-mismatch-a",
        )
        observation_a, _snapshot_a = await _record_search_observation(
            session,
            fixture=fixture_a,
            mapping=mapping_a,
        )

        fixture_b, mapping_b = await _publish(
            session,
            monkeypatch,
            worker_id="ll01a-mismatch-b",
        )
        _observation_b, snapshot_b = await _record_search_observation(
            session,
            fixture=fixture_b,
            mapping=mapping_b,
        )
        wrong_metric: PerformanceMetric = snapshot_b.metrics[0]

        observation_a.metric_refs_json = [str(wrong_metric.id)]
        await session.flush()
        with pytest.raises(
            PerformanceSignalError,
            match="performance_signal_metric_identity_mismatch",
        ):
            await materialize_performance_signal(
                session,
                observation_id=observation_a.id,
            )


@pytest.mark.asyncio
async def test_ll01a_replay_conflict_fails_closed_if_source_observation_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, mapping = await _publish(
            session,
            monkeypatch,
            worker_id="ll01a-replay-conflict",
        )
        observation, _snapshot = await _record_search_observation(
            session,
            fixture=fixture,
            mapping=mapping,
        )
        first = await materialize_performance_signal(
            session,
            observation_id=observation.id,
        )
        assert first.replayed is False

        observation.observed_at = observation.observed_at + timedelta(minutes=1)
        await session.flush()
        with pytest.raises(
            PerformanceSignalError,
            match="performance_signal_replay_conflict",
        ):
            await materialize_performance_signal(
                session,
                observation_id=observation.id,
            )


@pytest.mark.asyncio
async def test_ll01a_can_materialize_insufficient_data_without_inventing_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, mapping = await _publish(
            session,
            monkeypatch,
            worker_id="ll01a-insufficient",
        )
        observation = await record_performance_observation(
            session,
            published_content_id=mapping.id,
            content_version_id=fixture.version.id,
            observation_type="review_window_check",
            statement="There is not enough normalized data yet.",
            data_status="INSUFFICIENT_DATA",
            observed_at=datetime.now(UTC),
            metric_refs=[],
        )
        result = await materialize_performance_signal(
            session,
            observation_id=observation.id,
        )
        assert result.signal.provenance_json["metrics"] == []
        assert result.signal.provenance_json["measurement_windows"] == []
        assert "no normalized metric rows" in result.signal.observed_text.lower()
        assert observation.statement not in result.signal.observed_text