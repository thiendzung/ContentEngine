from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from test_ll01b_learning_candidate import _analytics_signal
from test_ll01c_learning_application import (
    _need_candidate,
    _new_insight_candidate,
)
from test_pm01_publish_measurement import (
    FakeWordPress,
    _approve_and_claim,
    isolated_session,
)

from app.modules.content_engine.models import (
    ContentExperiment,
    ContentVersion,
    NeedHypothesisReview,
    NeedHypothesisSignal,
)
from app.modules.customer_intelligence.models import (
    CustomerInsight,
    CustomerInsightReview,
    CustomerInsightSignal,
)
from app.modules.learning.application import (
    apply_learning_candidate,
    review_learning_candidate,
)
from app.modules.learning.models import LearningResolutionApplication
from app.modules.learning.performance_signal import materialize_performance_signal
from app.modules.learning.regression import (
    LearningRegressionError,
    MetricComparisonInput,
    apply_learning_resolution,
    create_learning_validation,
    review_learning_validation,
)
from app.modules.publishing.service import (
    begin_wordpress_dispatch,
    execute_wordpress_call,
    prepare_publish_package,
    record_wordpress_execution_result,
)


def _metric_id(signal, metric_name: str) -> UUID:
    for row in signal.provenance_json["metrics"]:
        if row["metric_name"] == metric_name:
            return UUID(row["id"])
    raise AssertionError(metric_name)


async def _applied_need(session, monkeypatch):
    fixture, mapping, signal, _assessment, candidate = await _need_candidate(
        session,
        monkeypatch,
    )
    review = await review_learning_candidate(
        session,
        learning_candidate_id=candidate.id,
        decision="APPROVE",
        reviewed_by="founder",
        reason="Apply reviewed factual evidence.",
    )
    applied = await apply_learning_candidate(
        session,
        review_id=review.review.id,
        applied_by="founder",
    )
    return fixture, mapping, signal, candidate, applied.application


async def _applied_new_insight(session, monkeypatch):
    fixture, signal, candidate = await _new_insight_candidate(
        session,
        monkeypatch,
    )
    review = await review_learning_candidate(
        session,
        learning_candidate_id=candidate.id,
        decision="APPROVE",
        reviewed_by="founder",
        reason="Create candidate Insight for reviewed learning.",
    )
    applied = await apply_learning_candidate(
        session,
        review_id=review.review.id,
        applied_by="founder",
    )
    assert applied.resulting_target_id is not None
    return fixture, signal, candidate, applied.application


async def _second_experiment_search_signal(
    session,
    *,
    fixture,
    worker_id: str,
    impressions: int,
):
    version2 = ContentVersion(
        content_item_id=fixture.item.id,
        version_no=2,
        final_artifact_id=fixture.final_artifact.id,
        change_reason="LL-01D independent validation cycle.",
        status="approved",
        content_json=fixture.version.content_json,
        created_by_run_id=fixture.source_run.id,
    )
    session.add(version2)
    now = datetime.now(UTC)
    experiment2 = ContentExperiment(
        project_id=fixture.project.id,
        content_opportunity_id=fixture.opportunity.id,
        need_hypothesis_id=fixture.need.id,
        hypothesis_version=fixture.need.version,
        expected_behaviour=fixture.experiment.expected_behaviour,
        measurement_plan_json=list(fixture.experiment.measurement_plan_json),
        metric_definitions_json=list(fixture.experiment.metric_definitions_json),
        minimum_evidence_json=list(fixture.experiment.minimum_evidence_json),
        review_window_start=now,
        review_window_end=now + timedelta(days=30),
        status="PLANNED",
    )
    session.add(experiment2)
    await session.flush()

    package = await prepare_publish_package(
        session,
        content_version_id=version2.id,
        experiment_id=experiment2.id,
        slug=f"ll01d-{uuid4().hex[:8]}",
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
    assert event.content_experiment_id == experiment2.id

    snapshot_time = datetime.now(UTC)
    from app.modules.measurement.service import (
        MetricInput,
        ingest_performance_snapshot,
        record_performance_observation,
    )

    snapshot = await ingest_performance_snapshot(
        session,
        published_content_id=mapping.id,
        content_version_id=version2.id,
        provider="search_console",
        window_start=max(now, snapshot_time - timedelta(hours=1)),
        window_end=snapshot_time,
        raw_metrics={"cycle": "ll01d-independent"},
        metrics=[
            MetricInput(
                metric_date=snapshot_time,
                metric_name="impressions",
                metric_value=impressions,
                dimensions={"query": "synthetic private dimension"},
            ),
            MetricInput(
                metric_date=snapshot_time,
                metric_name="clicks",
                metric_value=max(1, impressions // 10),
                dimensions={"query": "synthetic private dimension"},
            ),
        ],
    )
    observation = await record_performance_observation(
        session,
        published_content_id=mapping.id,
        content_version_id=version2.id,
        observation_type="search_exposure",
        statement="Later independent cycle; interpretation stays outside Signal.",
        data_status="EARLY_SIGNAL",
        observed_at=snapshot_time,
        metric_refs=[row.id for row in snapshot.metrics],
    )
    materialized = await materialize_performance_signal(
        session,
        observation_id=observation.id,
    )
    assert materialized.signal is not None
    assert materialized.signal.independence_group == f"experiment:{experiment2.id}"
    assert materialized.signal.independence_group != f"experiment:{fixture.experiment.id}"
    return materialized.signal


@pytest.mark.asyncio
async def test_ll01d_validated_need_requires_independent_evidence_and_human_promote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, baseline_signal, _candidate, application = await _applied_need(
            session,
            monkeypatch,
        )
        later_signal = await _second_experiment_search_signal(
            session,
            fixture=fixture,
            worker_id="ll01d-validated",
            impressions=180,
        )

        validation = await create_learning_validation(
            session,
            learning_application_id=application.id,
            validation_status="VALIDATED",
            signal_relations={later_signal.id: "supports"},
            metric_comparisons=[
                MetricComparisonInput(
                    baseline_metric_id=_metric_id(baseline_signal, "impressions"),
                    candidate_metric_id=_metric_id(later_signal, "impressions"),
                )
            ],
            alternative_explanations=["Distribution may still affect exposure."],
            missing_evidence=[],
        )
        assert validation.replayed is False
        assert validation.validation.validation_status == "VALIDATED"
        comparison = validation.validation.metric_comparisons_json[0]
        assert comparison["metric_name"] == "impressions"
        assert comparison["baseline_value"] == "120"
        assert comparison["candidate_value"] == "180"
        assert comparison["delta"] == "60"
        assert comparison["direction"] == "INCREASE"
        assert comparison["causal_claim_allowed"] is False

        replay = await create_learning_validation(
            session,
            learning_application_id=application.id,
            validation_status="VALIDATED",
            signal_relations={later_signal.id: "supports"},
            metric_comparisons=[
                MetricComparisonInput(
                    baseline_metric_id=_metric_id(baseline_signal, "impressions"),
                    candidate_metric_id=_metric_id(later_signal, "impressions"),
                )
            ],
            alternative_explanations=["Distribution may still affect exposure."],
            missing_evidence=[],
        )
        assert replay.replayed is True
        assert replay.validation.id == validation.validation.id

        need_version_before = fixture.need.version
        resolution = await review_learning_validation(
            session,
            learning_validation_id=validation.validation.id,
            decision="PROMOTE",
            target_status="SUPPORTED",
            reviewed_by="founder",
            reason="Independent later evidence supports promotion.",
        )
        await session.refresh(fixture.need)
        assert fixture.need.status == "TESTING"
        assert fixture.need.version == need_version_before

        applied = await apply_learning_resolution(
            session,
            learning_resolution_id=resolution.resolution.id,
            applied_by="founder",
        )
        await session.refresh(fixture.need)
        assert fixture.need.status == "SUPPORTED"
        assert fixture.need.version == need_version_before + 1
        assert applied.application.applied_action == "review_need"
        assert applied.customer_map_snapshot_artifact_id is not None
        assert (
            await session.scalar(
                select(func.count()).select_from(NeedHypothesisReview).where(
                    NeedHypothesisReview.need_hypothesis_id == fixture.need.id
                )
            )
            or 0
        ) == 1
        assert (
            await session.scalar(
                select(func.count()).select_from(NeedHypothesisSignal).where(
                    NeedHypothesisSignal.need_hypothesis_id == fixture.need.id
                )
            )
            or 0
        ) >= 1


@pytest.mark.asyncio
async def test_ll01d_same_experiment_provider_signal_is_not_independent_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, mapping, _baseline_signal, _candidate, application = await _applied_need(
            session,
            monkeypatch,
        )
        _observation, same_group_signal = await _analytics_signal(
            session,
            fixture=fixture,
            mapping=mapping,
        )
        with pytest.raises(
            LearningRegressionError,
            match="learning_validation_validated_evidence_invalid",
        ):
            await create_learning_validation(
                session,
                learning_application_id=application.id,
                validation_status="VALIDATED",
                signal_relations={same_group_signal.id: "supports"},
                metric_comparisons=[],
                alternative_explanations=[],
                missing_evidence=[],
            )


@pytest.mark.asyncio
async def test_ll01d_metric_comparison_requires_exact_metric_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, baseline_signal, _candidate, application = await _applied_need(
            session,
            monkeypatch,
        )
        later_signal = await _second_experiment_search_signal(
            session,
            fixture=fixture,
            worker_id="ll01d-metric-mismatch",
            impressions=150,
        )
        with pytest.raises(
            LearningRegressionError,
            match="learning_validation_metric_definition_mismatch",
        ):
            await create_learning_validation(
                session,
                learning_application_id=application.id,
                validation_status="VALIDATED",
                signal_relations={later_signal.id: "supports"},
                metric_comparisons=[
                    MetricComparisonInput(
                        baseline_metric_id=_metric_id(baseline_signal, "clicks"),
                        candidate_metric_id=_metric_id(later_signal, "impressions"),
                    )
                ],
                alternative_explanations=[],
                missing_evidence=[],
            )


@pytest.mark.asyncio
async def test_ll01d_regressed_new_insight_uses_compensating_review_not_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, baseline_signal, _candidate, application = await _applied_new_insight(
            session,
            monkeypatch,
        )
        insight = await session.get(CustomerInsight, application.resulting_target_id)
        assert insight is not None
        signal_links_before = int(
            await session.scalar(
                select(func.count()).select_from(CustomerInsightSignal).where(
                    CustomerInsightSignal.customer_insight_id == insight.id
                )
            )
            or 0
        )
        later_signal = await _second_experiment_search_signal(
            session,
            fixture=fixture,
            worker_id="ll01d-regressed",
            impressions=60,
        )
        validation = await create_learning_validation(
            session,
            learning_application_id=application.id,
            validation_status="REGRESSED",
            signal_relations={later_signal.id: "contradicts"},
            metric_comparisons=[
                MetricComparisonInput(
                    baseline_metric_id=_metric_id(baseline_signal, "impressions"),
                    candidate_metric_id=_metric_id(later_signal, "impressions"),
                )
            ],
            alternative_explanations=["Search demand or distribution may have changed."],
            missing_evidence=[],
        )
        resolution = await review_learning_validation(
            session,
            learning_validation_id=validation.validation.id,
            decision="ROLLBACK",
            target_status="REJECTED",
            reviewed_by="founder",
            reason="Independent contradictory evidence justifies compensating rejection.",
        )
        await session.refresh(insight)
        assert insight.status == "CANDIDATE"

        applied = await apply_learning_resolution(
            session,
            learning_resolution_id=resolution.resolution.id,
            applied_by="founder",
        )
        await session.refresh(insight)
        assert insight.status == "REJECTED"
        assert applied.application.applied_action == "review_insight"
        assert applied.application.before_state_hash != applied.application.after_state_hash
        assert (
            await session.scalar(
                select(func.count()).select_from(CustomerInsightReview).where(
                    CustomerInsightReview.customer_insight_id == insight.id,
                    CustomerInsightReview.status == "REJECTED",
                )
            )
            or 0
        ) == 1
        assert (
            await session.scalar(
                select(func.count()).select_from(CustomerInsightSignal).where(
                    CustomerInsightSignal.customer_insight_id == insight.id
                )
            )
            or 0
        ) == signal_links_before

        replay = await apply_learning_resolution(
            session,
            learning_resolution_id=resolution.resolution.id,
            applied_by="safe-replayer",
        )
        assert replay.replayed is True
        assert replay.application.id == applied.application.id


@pytest.mark.asyncio
async def test_ll01d_review_is_separate_and_stale_target_blocks_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, _baseline_signal, _candidate, application = await _applied_need(
            session,
            monkeypatch,
        )
        later_signal = await _second_experiment_search_signal(
            session,
            fixture=fixture,
            worker_id="ll01d-stale",
            impressions=170,
        )
        validation = await create_learning_validation(
            session,
            learning_application_id=application.id,
            validation_status="VALIDATED",
            signal_relations={later_signal.id: "supports"},
            metric_comparisons=[],
            alternative_explanations=[],
            missing_evidence=[],
        )
        resolution = await review_learning_validation(
            session,
            learning_validation_id=validation.validation.id,
            decision="PROMOTE",
            target_status="SUPPORTED",
            reviewed_by="founder",
            reason="Review exact target state only.",
        )
        assert fixture.need.status == "TESTING"

        fixture.need.status = "INSUFFICIENT_EVIDENCE"
        await session.flush()

        with pytest.raises(
            LearningRegressionError,
            match="learning_resolution_target_stale",
        ):
            await apply_learning_resolution(
                session,
                learning_resolution_id=resolution.resolution.id,
                applied_by="founder",
            )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(LearningResolutionApplication)
                .where(
                    LearningResolutionApplication.learning_resolution_id
                    == resolution.resolution.id
                )
            )
            or 0
        ) == 0


@pytest.mark.asyncio
async def test_ll01d_request_more_evidence_is_noop_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _fixture, _mapping, _signal, _candidate, application = await _applied_need(
            session,
            monkeypatch,
        )
        validation = await create_learning_validation(
            session,
            learning_application_id=application.id,
            validation_status="NEEDS_MORE_EVIDENCE",
            signal_relations={},
            metric_comparisons=[],
            alternative_explanations=[],
            missing_evidence=["Need a later independent experiment."],
        )
        resolution = await review_learning_validation(
            session,
            learning_validation_id=validation.validation.id,
            decision="REQUEST_MORE_EVIDENCE",
            target_status=None,
            reviewed_by="founder",
            reason="Do not change Customer Truth yet.",
        )
        applied = await apply_learning_resolution(
            session,
            learning_resolution_id=resolution.resolution.id,
            applied_by="founder",
        )
        assert applied.application.applied_action == "no_map_change"
        assert applied.application.customer_map_snapshot_artifact_id is None
        assert applied.application.change_report_json is None


@pytest.mark.asyncio
async def test_ll01d_validation_resolution_and_receipt_are_immutable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _fixture, _mapping, _signal, _candidate, application = await _applied_need(
            session,
            monkeypatch,
        )
        validation = await create_learning_validation(
            session,
            learning_application_id=application.id,
            validation_status="NEEDS_MORE_EVIDENCE",
            signal_relations={},
            metric_comparisons=[],
            alternative_explanations=[],
            missing_evidence=["Need independent evidence."],
        )
        resolution = await review_learning_validation(
            session,
            learning_validation_id=validation.validation.id,
            decision="KEEP",
            target_status=None,
            reviewed_by="founder",
            reason="Keep current state while gathering evidence.",
        )
        applied = await apply_learning_resolution(
            session,
            learning_resolution_id=resolution.resolution.id,
            applied_by="founder",
        )

        with pytest.raises(DBAPIError, match="learning_validation_update_forbidden"):
            async with session.begin_nested():
                validation.validation.validation_status = "VALIDATED"
                await session.flush()

        await session.refresh(resolution.resolution)
        with pytest.raises(DBAPIError, match="learning_resolution_update_forbidden"):
            async with session.begin_nested():
                resolution.resolution.reason = "rewrite forbidden"
                await session.flush()

        await session.refresh(applied.application)
        with pytest.raises(
            DBAPIError,
            match="learning_resolution_application_update_forbidden",
        ):
            async with session.begin_nested():
                applied.application.applied_by = "rewrite forbidden"
                await session.flush()


@pytest.mark.asyncio
async def test_ll01d_resolution_replay_conflict_and_latest_validation_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _fixture, _mapping, _signal, _candidate, application = await _applied_need(
            session,
            monkeypatch,
        )
        v1 = await create_learning_validation(
            session,
            learning_application_id=application.id,
            validation_status="NEEDS_MORE_EVIDENCE",
            signal_relations={},
            metric_comparisons=[],
            alternative_explanations=[],
            missing_evidence=["Need independent evidence."],
        )
        first_resolution = await review_learning_validation(
            session,
            learning_validation_id=v1.validation.id,
            decision="KEEP",
            target_status=None,
            reviewed_by="founder",
            reason="Keep while evidence is weak.",
        )
        replay = await review_learning_validation(
            session,
            learning_validation_id=v1.validation.id,
            decision="KEEP",
            target_status=None,
            reviewed_by="founder",
            reason="Keep while evidence is weak.",
        )
        assert replay.replayed is True
        assert replay.resolution.id == first_resolution.resolution.id

        with pytest.raises(
            LearningRegressionError,
            match="learning_resolution_replay_conflict",
        ):
            await review_learning_validation(
                session,
                learning_validation_id=v1.validation.id,
                decision="REQUEST_MORE_EVIDENCE",
                target_status=None,
                reviewed_by="founder",
                reason="Different decision.",
            )

        v2 = await create_learning_validation(
            session,
            learning_application_id=application.id,
            validation_status="INCONCLUSIVE",
            signal_relations={},
            metric_comparisons=[],
            alternative_explanations=[],
            missing_evidence=["Evidence remains inconclusive."],
        )
        assert v2.validation.version == 2
        with pytest.raises(
            LearningRegressionError,
            match="learning_resolution_validation_stale",
        ):
            await apply_learning_resolution(
                session,
                learning_resolution_id=first_resolution.resolution.id,
                applied_by="founder",
            )
