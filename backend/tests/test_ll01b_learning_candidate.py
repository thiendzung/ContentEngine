from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from test_ll01a_performance_signal import _publish, _record_search_observation
from test_pm01_publish_measurement import isolated_session

from app.modules.content_engine.models import NeedHypothesis, Project, Signal
from app.modules.customer_intelligence.models import CustomerInsight
from app.modules.learning.models import (
    LearningCandidate,
    LearningCandidateAssessment,
    LearningCandidateSignal,
)
from app.modules.learning.performance_signal import materialize_performance_signal
from app.modules.learning.service import (
    LearningError,
    _classify_candidate_evidence_status,
    create_learning_assessment,
    create_learning_candidate,
)
from app.modules.measurement.service import (
    MetricInput,
    ingest_performance_snapshot,
    record_performance_observation,
)


async def _search_signal(session, monkeypatch):
    fixture, mapping = await _publish(
        session,
        monkeypatch,
        worker_id=f"ll01b-search-{uuid4().hex[:8]}",
    )
    observation, _snapshot = await _record_search_observation(
        session,
        fixture=fixture,
        mapping=mapping,
    )
    materialized = await materialize_performance_signal(
        session,
        observation_id=observation.id,
    )
    assert materialized.signal is not None
    return fixture, mapping, observation, materialized.signal


async def _analytics_signal(
    session,
    *,
    fixture,
    mapping,
    data_status: Literal[
        "EARLY_SIGNAL",
        "REPEATED_PATTERN",
        "LEARNING_CANDIDATE_READY",
    ] = "EARLY_SIGNAL",
):
    now = datetime.now(UTC)
    review_start = fixture.experiment.review_window_start
    assert review_start is not None
    snapshot = await ingest_performance_snapshot(
        session,
        published_content_id=mapping.id,
        content_version_id=fixture.version.id,
        provider="analytics",
        window_start=max(review_start, now - timedelta(hours=1)),
        window_end=now,
        raw_metrics={
            "aggregate": "synthetic",
            "raw_session_like_value": "must-not-flow",
        },
        metrics=[
            MetricInput(
                metric_date=now,
                metric_name="sessions",
                metric_value=20,
                dimensions={"channel": "synthetic private dimension"},
            ),
            MetricInput(
                metric_date=now,
                metric_name="engaged_sessions",
                metric_value=11,
                dimensions={"channel": "synthetic private dimension"},
            ),
        ],
    )
    observation = await record_performance_observation(
        session,
        published_content_id=mapping.id,
        content_version_id=fixture.version.id,
        observation_type="engagement",
        statement="Engagement may be meaningful, but causality is not established.",
        data_status=data_status,
        observed_at=now,
        metric_refs=[row.id for row in snapshot.metrics],
    )
    materialized = await materialize_performance_signal(
        session,
        observation_id=observation.id,
    )
    assert materialized.signal is not None
    return observation, materialized.signal


@pytest.mark.asyncio
async def test_ll01b_assessment_is_factual_idempotent_and_does_not_mutate_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, observation, signal = await _search_signal(
            session,
            monkeypatch,
        )
        insight_count_before = int(
            await session.scalar(select(func.count()).select_from(CustomerInsight)) or 0
        )

        first = await create_learning_assessment(
            session,
            experiment_id=fixture.experiment.id,
            proposed_result="SUPPORTS",
            signal_relations={signal.id: "supports"},
            alternative_explanations=[
                "Distribution, ranking, timing, or execution may also affect the observed metrics."
            ],
            missing_evidence=["No purchase or repeat-purchase evidence is present."],
        )
        assert first.replayed is False
        payload = first.artifact.content_json
        assert isinstance(payload, dict)
        assert payload["artifact_type"] == "learning_assessment"
        assert payload["assessment"]["proposed_result"] == "SUPPORTS"
        assert payload["assessment"]["evidence_status"] == "EARLY_SIGNAL"
        assert payload["assessment"]["causal_claim_allowed"] is False
        assert payload["assessment"]["minimum_evidence_interpreted"] is False
        assert payload["measurement_contract"]["minimum_evidence_verbatim"] == [
            "non-zero exposure",
            "review window reached",
        ]
        assert payload["candidate_scope"]["intent"] is None
        assert payload["candidate_scope"]["intent_scope_status"] == "NOT_FROZEN_IN_PM01"
        assert payload["candidate_scope"]["primary_lens"] == "SIGNALS"
        assert payload["candidate_scope"]["supporting_lenses"] == ["METHOD"]

        serialized = json.dumps(payload, sort_keys=True)
        assert observation.statement not in serialized
        assert "must-not-flow-to-signal" not in serialized
        assert "synthetic private dimension" not in serialized
        assert "raw_secret" not in serialized

        replay = await create_learning_assessment(
            session,
            experiment_id=fixture.experiment.id,
            proposed_result="SUPPORTS",
            signal_relations={signal.id: "supports"},
            alternative_explanations=[
                "Distribution, ranking, timing, or execution may also affect the observed metrics."
            ],
            missing_evidence=["No purchase or repeat-purchase evidence is present."],
        )
        assert replay.replayed is True
        assert replay.artifact.id == first.artifact.id

        await session.refresh(fixture.experiment)
        await session.refresh(fixture.need)
        assert fixture.experiment.result == "PENDING"
        assert fixture.need.status == "TESTING"
        assert int(
            await session.scalar(select(func.count()).select_from(CustomerInsight)) or 0
        ) == insight_count_before

        with pytest.raises(
            DBAPIError,
            match="learning_assessment_artifact_update_forbidden",
        ):
            async with session.begin_nested():
                first.artifact.content_json = {"tampered": True}
                await session.flush()


@pytest.mark.asyncio
async def test_ll01b_contested_assessment_must_be_inconclusive_and_candidate_is_contested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, mapping, _search_observation, search_signal = await _search_signal(
            session,
            monkeypatch,
        )
        _analytics_observation, analytics_signal = await _analytics_signal(
            session,
            fixture=fixture,
            mapping=mapping,
        )

        with pytest.raises(
            LearningError,
            match="learning_assessment_contested_must_be_inconclusive",
        ):
            await create_learning_assessment(
                session,
                experiment_id=fixture.experiment.id,
                proposed_result="SUPPORTS",
                signal_relations={
                    search_signal.id: "supports",
                    analytics_signal.id: "contradicts",
                },
                alternative_explanations=["The metrics point in different directions."],
                missing_evidence=["Need another independent experiment."],
            )

        assessment = await create_learning_assessment(
            session,
            experiment_id=fixture.experiment.id,
            proposed_result="INCONCLUSIVE",
            signal_relations={
                search_signal.id: "supports",
                analytics_signal.id: "contradicts",
            },
            alternative_explanations=["The metrics point in different directions."],
            missing_evidence=["Need another independent experiment."],
        )
        assert assessment.artifact.content_json["assessment"]["evidence_status"] == "CONTESTED"

        candidate = await create_learning_candidate(
            session,
            assessment_artifact_id=assessment.artifact.id,
            target_type="need_hypothesis",
            target_id=fixture.need.id,
            statement=(
                "The current content-performance evidence is mixed for this frozen Need scope."
            ),
            relation="context",
            expected_benefit="Keep contradictory performance evidence visible for review.",
            regression_risk="Do not infer that traffic alone proves or disproves the Need.",
        )
        assert candidate.candidate.version == 1
        assert candidate.candidate.evidence_status == "CONTESTED"
        assert candidate.candidate.relation == "context"
        await session.refresh(fixture.need)
        assert fixture.need.status == "TESTING"


@pytest.mark.asyncio
async def test_ll01b_candidate_replay_and_versioning_do_not_inflate_same_experiment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, mapping, _search_observation, search_signal = await _search_signal(
            session,
            monkeypatch,
        )
        assessment_v1 = await create_learning_assessment(
            session,
            experiment_id=fixture.experiment.id,
            proposed_result="SUPPORTS",
            signal_relations={search_signal.id: "supports"},
            alternative_explanations=["Distribution remains an alternative explanation."],
            missing_evidence=["Need repeated evidence from another experiment."],
        )
        candidate_v1 = await create_learning_candidate(
            session,
            assessment_artifact_id=assessment_v1.artifact.id,
            target_type="need_hypothesis",
            target_id=fixture.need.id,
            statement="Performance evidence may support this Need in the frozen scope.",
            relation="supports",
            expected_benefit="Prioritize evidence collection without changing Customer Truth.",
            regression_risk="Do not generalize one article to all buyers.",
        )
        assert candidate_v1.replayed is False
        assert candidate_v1.candidate.version == 1
        assert candidate_v1.candidate.evidence_status == "EARLY_SIGNAL"

        replay = await create_learning_candidate(
            session,
            assessment_artifact_id=assessment_v1.artifact.id,
            target_type="need_hypothesis",
            target_id=fixture.need.id,
            statement="Performance evidence may support this Need in the frozen scope.",
            relation="supports",
            expected_benefit="Prioritize evidence collection without changing Customer Truth.",
            regression_risk="Do not generalize one article to all buyers.",
        )
        assert replay.replayed is True
        assert replay.candidate.id == candidate_v1.candidate.id

        _analytics_observation, analytics_signal = await _analytics_signal(
            session,
            fixture=fixture,
            mapping=mapping,
            data_status="LEARNING_CANDIDATE_READY",
        )
        assessment_v2 = await create_learning_assessment(
            session,
            experiment_id=fixture.experiment.id,
            proposed_result="SUPPORTS",
            signal_relations={
                search_signal.id: "supports",
                analytics_signal.id: "supports",
            },
            alternative_explanations=["Distribution remains an alternative explanation."],
            missing_evidence=["Need an independent experiment, not another provider window."],
        )
        assert (
            assessment_v2.artifact.content_json["assessment"]["evidence_status"]
            == "CANDIDATE_READY"
        )

        candidate_v2 = await create_learning_candidate(
            session,
            assessment_artifact_id=assessment_v2.artifact.id,
            target_type="need_hypothesis",
            target_id=fixture.need.id,
            statement="Performance evidence may support this Need in the frozen scope.",
            relation="supports",
            expected_benefit="Prioritize evidence collection without changing Customer Truth.",
            regression_risk="Do not generalize one article to all buyers.",
        )
        assert candidate_v2.replayed is False
        assert candidate_v2.candidate.version == 2
        assert candidate_v2.candidate.supersedes_id == candidate_v1.candidate.id
        # Two providers/windows from the same experiment remain one independent group.
        assert candidate_v2.candidate.evidence_status == "EARLY_SIGNAL"

        await session.refresh(candidate_v1.candidate)
        assert candidate_v1.candidate.status == "SUPERSEDED"
        assert candidate_v2.candidate.status == "OPEN"

        versions = list(
            (
                await session.scalars(
                    select(LearningCandidate)
                    .where(
                        LearningCandidate.project_id == fixture.project.id,
                        LearningCandidate.candidate_key == candidate_v2.candidate.candidate_key,
                    )
                    .order_by(LearningCandidate.version)
                )
            ).all()
        )
        assert [row.version for row in versions] == [1, 2]

        linked_signals = list(
            (
                await session.scalars(
                    select(LearningCandidateSignal).where(
                        LearningCandidateSignal.learning_candidate_id
                        == candidate_v2.candidate.id
                    )
                )
            ).all()
        )
        assert len(linked_signals) == 2
        assert {
            (await session.get(Signal, row.signal_id)).independence_group
            for row in linked_signals
        } == {f"experiment:{fixture.experiment.id}"}

        linked_assessments = list(
            (
                await session.scalars(
                    select(LearningCandidateAssessment).where(
                        LearningCandidateAssessment.learning_candidate_id
                        == candidate_v2.candidate.id
                    )
                )
            ).all()
        )
        assert len(linked_assessments) == 2

        with pytest.raises(
            DBAPIError,
            match="learning_candidate_version_content_immutable",
        ):
            async with session.begin_nested():
                candidate_v1.candidate.statement = "Rewrite old candidate."
                await session.flush()

        await session.refresh(fixture.need)
        assert fixture.need.status == "TESTING"


@pytest.mark.asyncio
async def test_ll01b_insufficient_assessment_can_exist_without_creating_customer_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping = await _publish(
            session,
            monkeypatch,
            worker_id="ll01b-insufficient",
        )
        insight_count_before = int(
            await session.scalar(select(func.count()).select_from(CustomerInsight)) or 0
        )
        assessment = await create_learning_assessment(
            session,
            experiment_id=fixture.experiment.id,
            proposed_result="INCONCLUSIVE",
            signal_relations={},
            alternative_explanations=[],
            missing_evidence=["No normalized performance Signal exists yet."],
        )
        assert (
            assessment.artifact.content_json["assessment"]["evidence_status"]
            == "INSUFFICIENT_DATA"
        )
        candidate = await create_learning_candidate(
            session,
            assessment_artifact_id=assessment.artifact.id,
            target_type="no_map_change",
            target_id=None,
            statement="Keep the Customer Map unchanged until measured evidence exists.",
            relation="no_change",
            expected_benefit="Avoid learning from absence of data.",
            regression_risk="None; this proposal explicitly requests no map mutation.",
        )
        assert candidate.candidate.evidence_status == "NEEDS_EVIDENCE"
        assert int(
            await session.scalar(select(func.count()).select_from(CustomerInsight)) or 0
        ) == insight_count_before
        await session.refresh(fixture.need)
        assert fixture.need.status == "TESTING"


@pytest.mark.asyncio
async def test_ll01b_tampered_factual_signal_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, _observation, signal = await _search_signal(
            session,
            monkeypatch,
        )
        signal.provenance_json = {
            **signal.provenance_json,
            "raw_provider_payload": {"secret": "should-never-be-trusted"},
        }
        with pytest.raises(
            LearningError,
            match="learning_assessment_signal_fingerprint_mismatch",
        ):
            await create_learning_assessment(
                session,
                experiment_id=fixture.experiment.id,
                proposed_result="SUPPORTS",
                signal_relations={signal.id: "supports"},
                alternative_explanations=["Distribution can affect the metric."],
                missing_evidence=["Need another experiment."],
            )


@pytest.mark.asyncio
async def test_ll01b_foreign_need_target_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, _observation, signal = await _search_signal(
            session,
            monkeypatch,
        )
        assessment = await create_learning_assessment(
            session,
            experiment_id=fixture.experiment.id,
            proposed_result="SUPPORTS",
            signal_relations={signal.id: "supports"},
            alternative_explanations=["Distribution can affect the metric."],
            missing_evidence=["Need another experiment."],
        )
        foreign_project = Project(
            slug=f"foreign-{uuid4().hex[:8]}",
            name="Foreign project",
            default_locale="en",
        )
        session.add(foreign_project)
        await session.flush()
        foreign_need = NeedHypothesis(
            project_id=foreign_project.id,
            type="question",
            statement="Foreign need",
            audience_scope="foreign",
            situation="foreign",
            origin="founder_proposed",
            status="TESTING",
            version=1,
        )
        session.add(foreign_need)
        await session.flush()

        with pytest.raises(
            LearningError,
            match="learning_candidate_need_target_mismatch",
        ):
            await create_learning_candidate(
                session,
                assessment_artifact_id=assessment.artifact.id,
                target_type="need_hypothesis",
                target_id=foreign_need.id,
                statement="Do not cross project boundaries.",
                relation="supports",
            )


def test_ll01b_candidate_maturity_requires_independent_experiments() -> None:
    assert (
        _classify_candidate_evidence_status(
            support_groups={"experiment:a"},
            contradict_groups=set(),
            assessment_statuses=["CANDIDATE_READY"],
            assessment_results=["SUPPORTS"],
        )
        == "EARLY_SIGNAL"
    )
    assert (
        _classify_candidate_evidence_status(
            support_groups={"experiment:a", "experiment:b"},
            contradict_groups=set(),
            assessment_statuses=["REPEATED_PATTERN", "CANDIDATE_READY"],
            assessment_results=["SUPPORTS", "SUPPORTS"],
        )
        == "REPEATED_PATTERN"
    )
    assert (
        _classify_candidate_evidence_status(
            support_groups={"experiment:a", "experiment:b"},
            contradict_groups=set(),
            assessment_statuses=["CANDIDATE_READY", "CANDIDATE_READY"],
            assessment_results=["SUPPORTS", "SUPPORTS"],
        )
        == "READY_FOR_REVIEW"
    )
    assert (
        _classify_candidate_evidence_status(
            support_groups={"experiment:a"},
            contradict_groups={"experiment:b"},
            assessment_statuses=["CANDIDATE_READY", "CANDIDATE_READY"],
            assessment_results=["SUPPORTS", "CONTRADICTS"],
        )
        == "CONTESTED"
    )
