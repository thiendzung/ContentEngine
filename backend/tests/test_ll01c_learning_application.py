from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from test_ll01a_performance_signal import _publish
from test_ll01b_learning_candidate import _analytics_signal, _search_signal
from test_pm01_publish_measurement import isolated_session

from app.modules.content_engine.models import NeedHypothesisSignal
from app.modules.customer_intelligence.insights import ensure_customer_insight
from app.modules.customer_intelligence.models import (
    CustomerInsight,
    CustomerInsightNeedLink,
    CustomerInsightSignal,
)
from app.modules.learning.application import (
    LearningApplicationError,
    apply_learning_candidate,
    review_learning_candidate,
)
from app.modules.harness.models import Artifact
from app.modules.learning.models import (
    LearningApplication,
    LearningCandidateReview,
)
from app.modules.learning.service import (
    create_learning_assessment,
    create_learning_candidate,
)


async def _need_candidate(session, monkeypatch):
    fixture, mapping, _observation, signal = await _search_signal(
        session,
        monkeypatch,
    )
    assessment = await create_learning_assessment(
        session,
        experiment_id=fixture.experiment.id,
        proposed_result="SUPPORTS",
        signal_relations={signal.id: "supports"},
        alternative_explanations=["Distribution can affect the observed metrics."],
        missing_evidence=["Need another independent experiment."],
    )
    candidate = await create_learning_candidate(
        session,
        assessment_artifact_id=assessment.artifact.id,
        target_type="need_hypothesis",
        target_id=fixture.need.id,
        statement="Measured evidence may support this frozen Need.",
        relation="supports",
        expected_benefit="Preserve reviewed factual evidence on the Need.",
        regression_risk="Do not promote the Need status automatically.",
    )
    return fixture, mapping, signal, assessment, candidate.candidate


async def _new_insight_candidate(session, monkeypatch):
    fixture, _mapping, _observation, signal = await _search_signal(
        session,
        monkeypatch,
    )
    assessment = await create_learning_assessment(
        session,
        experiment_id=fixture.experiment.id,
        proposed_result="SUPPORTS",
        signal_relations={signal.id: "supports"},
        alternative_explanations=["Distribution can affect the observed metrics."],
        missing_evidence=["Need another independent experiment."],
    )
    candidate = await create_learning_candidate(
        session,
        assessment_artifact_id=assessment.artifact.id,
        target_type="new_customer_insight",
        target_id=None,
        statement="Readers may need a clearer provenance verification path.",
        relation="proposes",
        proposal={
            "insight_type": "question",
            "situation": "before deciding whether to buy an artwork",
            "need_relation": "supports",
        },
        expected_benefit="Create a reviewable CustomerInsight candidate.",
        regression_risk="Never create a supported insight automatically.",
    )
    return fixture, signal, candidate.candidate


async def _no_map_candidate(session, monkeypatch):
    fixture, _mapping = await _publish(
        session,
        monkeypatch,
        worker_id=f"ll01c-no-map-{uuid4().hex[:8]}",
    )
    assessment = await create_learning_assessment(
        session,
        experiment_id=fixture.experiment.id,
        proposed_result="INCONCLUSIVE",
        signal_relations={},
        alternative_explanations=[],
        missing_evidence=["No normalized evidence exists yet."],
    )
    candidate = await create_learning_candidate(
        session,
        assessment_artifact_id=assessment.artifact.id,
        target_type="no_map_change",
        target_id=None,
        statement="Keep the Customer Map unchanged.",
        relation="no_change",
        expected_benefit="Avoid learning from absence of evidence.",
        regression_risk="None; no Customer Truth mutation is proposed.",
    )
    return fixture, candidate.candidate


@pytest.mark.asyncio
async def test_ll01c_review_is_human_idempotent_and_does_not_mutate_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, _signal, _assessment, candidate = await _need_candidate(
            session,
            monkeypatch,
        )
        need_links_before = int(
            await session.scalar(
                select(func.count()).select_from(NeedHypothesisSignal)
            )
            or 0
        )
        insights_before = int(
            await session.scalar(select(func.count()).select_from(CustomerInsight))
            or 0
        )

        first = await review_learning_candidate(
            session,
            learning_candidate_id=candidate.id,
            decision="APPROVE",
            reviewed_by="founder",
            reason="Approve factual evidence linkage only.",
        )
        assert first.replayed is False
        assert first.review.candidate_version == candidate.version
        assert first.review.candidate_snapshot_hash
        assert fixture.need.status == "TESTING"

        replay = await review_learning_candidate(
            session,
            learning_candidate_id=candidate.id,
            decision="APPROVE",
            reviewed_by="founder",
            reason="Approve factual evidence linkage only.",
        )
        assert replay.replayed is True
        assert replay.review.id == first.review.id

        with pytest.raises(
            LearningApplicationError,
            match="learning_review_replay_conflict",
        ):
            await review_learning_candidate(
                session,
                learning_candidate_id=candidate.id,
                decision="REJECT",
                reviewed_by="founder",
                reason="Conflicting final review.",
            )

        assert int(
            await session.scalar(
                select(func.count()).select_from(NeedHypothesisSignal)
            )
            or 0
        ) == need_links_before
        assert int(
            await session.scalar(select(func.count()).select_from(CustomerInsight))
            or 0
        ) == insights_before


@pytest.mark.asyncio
async def test_ll01c_apply_need_links_signal_without_status_or_version_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, signal, _assessment, candidate = await _need_candidate(
            session,
            monkeypatch,
        )
        status_before = fixture.need.status
        version_before = fixture.need.version
        review = await review_learning_candidate(
            session,
            learning_candidate_id=candidate.id,
            decision="APPROVE",
            reviewed_by="founder",
            reason="Link the reviewed factual evidence.",
        )
        applied = await apply_learning_candidate(
            session,
            review_id=review.review.id,
            applied_by="founder",
        )
        assert applied.replayed is False
        assert applied.application.applied_action == "link_need_signals"
        assert applied.resulting_target_id == fixture.need.id
        assert applied.customer_map_snapshot_artifact_id is not None
        assert applied.change_report is not None
        events = applied.change_report["events"]
        assert any(
            event["entity_type"] == "need"
            and event["entity_ref"] == str(fixture.need.id)
            and event["detail"] == "supports_evidence_added"
            for event in events
        )

        link = await session.get(
            NeedHypothesisSignal,
            (fixture.need.id, signal.id, "supports"),
        )
        assert link is not None
        await session.refresh(fixture.need)
        assert fixture.need.status == status_before
        assert fixture.need.version == version_before

        replay = await apply_learning_candidate(
            session,
            review_id=review.review.id,
            applied_by="another-safe-replayer",
        )
        assert replay.replayed is True
        assert replay.application.id == applied.application.id
        assert (
            int(
                await session.scalar(
                    select(func.count()).select_from(LearningApplication)
                )
                or 0
            )
            == 1
        )


@pytest.mark.asyncio
async def test_ll01c_stale_need_version_blocks_application_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, signal, _assessment, candidate = await _need_candidate(
            session,
            monkeypatch,
        )
        review = await review_learning_candidate(
            session,
            learning_candidate_id=candidate.id,
            decision="APPROVE",
            reviewed_by="founder",
            reason="Approve exact frozen Need version only.",
        )
        fixture.need.version += 1
        await session.flush()

        with pytest.raises(
            LearningApplicationError,
            match="learning_review_stale",
        ):
            await apply_learning_candidate(
                session,
                review_id=review.review.id,
                applied_by="founder",
            )

        assert await session.get(
            NeedHypothesisSignal,
            (fixture.need.id, signal.id, "supports"),
        ) is None
        assert (
            await session.scalar(
                select(func.count()).select_from(LearningApplication)
            )
            or 0
        ) == 0


@pytest.mark.asyncio
async def test_ll01c_apply_existing_insight_reuses_canonical_signal_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, _mapping, _observation, signal = await _search_signal(
            session,
            monkeypatch,
        )
        insight = await ensure_customer_insight(
            session,
            project_id=fixture.project.id,
            insight_type="question",
            statement="How can I verify an artwork before buying?",
            audience_hypothesis_id=fixture.need.audience_hypothesis_id,
            situation="before purchase",
        )
        assessment = await create_learning_assessment(
            session,
            experiment_id=fixture.experiment.id,
            proposed_result="SUPPORTS",
            signal_relations={signal.id: "supports"},
            alternative_explanations=["Distribution can affect the metric."],
            missing_evidence=["Need another independent experiment."],
        )
        candidate = await create_learning_candidate(
            session,
            assessment_artifact_id=assessment.artifact.id,
            target_type="customer_insight",
            target_id=insight.id,
            statement="Measured evidence may support this exact insight.",
            relation="supports",
        )
        review = await review_learning_candidate(
            session,
            learning_candidate_id=candidate.candidate.id,
            decision="APPROVE",
            reviewed_by="founder",
            reason="Attach factual evidence without changing insight status.",
        )
        applied = await apply_learning_candidate(
            session,
            review_id=review.review.id,
            applied_by="founder",
        )
        assert applied.application.applied_action == "link_insight_signals"
        link = await session.get(CustomerInsightSignal, (insight.id, signal.id))
        assert link is not None
        assert link.relation == "supports"
        await session.refresh(insight)
        assert insight.status == "CANDIDATE"
        assert any(
            event["entity_type"] == "insight"
            and event["detail"] == "supports_evidence_added"
            for event in applied.change_report["events"]
        )


@pytest.mark.asyncio
async def test_ll01c_apply_new_insight_creates_candidate_and_need_link_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, signal, candidate = await _new_insight_candidate(
            session,
            monkeypatch,
        )
        count_before = int(
            await session.scalar(select(func.count()).select_from(CustomerInsight))
            or 0
        )
        review = await review_learning_candidate(
            session,
            learning_candidate_id=candidate.id,
            decision="APPROVE",
            reviewed_by="founder",
            reason="Create a candidate insight for later truth review.",
        )
        applied = await apply_learning_candidate(
            session,
            review_id=review.review.id,
            applied_by="founder",
        )
        assert applied.application.applied_action == "create_candidate_insight"
        assert applied.resulting_target_id is not None

        insight = await session.get(CustomerInsight, applied.resulting_target_id)
        assert insight is not None
        assert insight.status == "CANDIDATE"
        assert insight.insight_type == "question"
        assert insight.audience_hypothesis_id == fixture.need.audience_hypothesis_id
        assert (
            int(
                await session.scalar(
                    select(func.count()).select_from(CustomerInsight)
                )
                or 0
            )
            == count_before + 1
        )
        signal_link = await session.get(
            CustomerInsightSignal,
            (insight.id, signal.id),
        )
        assert signal_link is not None
        need_link = await session.get(
            CustomerInsightNeedLink,
            (insight.id, fixture.need.id),
        )
        assert need_link is not None
        assert need_link.relation == "supports"

        replay = await apply_learning_candidate(
            session,
            review_id=review.review.id,
            applied_by="founder",
        )
        assert replay.replayed is True
        assert replay.resulting_target_id == insight.id
        assert (
            int(
                await session.scalar(
                    select(func.count()).select_from(CustomerInsight)
                )
                or 0
            )
            == count_before + 1
        )


@pytest.mark.asyncio
async def test_ll01c_no_map_change_creates_receipt_without_snapshot_or_truth_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _fixture, candidate = await _no_map_candidate(session, monkeypatch)
        review = await review_learning_candidate(
            session,
            learning_candidate_id=candidate.id,
            decision="NO_MAP_CHANGE",
            reviewed_by="founder",
            reason="Evidence is insufficient; keep the map unchanged.",
        )
        insight_count = int(
            await session.scalar(select(func.count()).select_from(CustomerInsight))
            or 0
        )
        need_link_count = int(
            await session.scalar(
                select(func.count()).select_from(NeedHypothesisSignal)
            )
            or 0
        )
        snapshot_count = int(
            await session.scalar(
                select(func.count())
                .select_from(Artifact)
                .where(Artifact.artifact_type == "customer_map_snapshot")
            )
            or 0
        )
        applied = await apply_learning_candidate(
            session,
            review_id=review.review.id,
            applied_by="founder",
        )
        assert applied.application.applied_action == "no_map_change"
        assert applied.customer_map_snapshot_artifact_id is None
        assert applied.change_report is None
        assert applied.application.before_state_hash is None
        assert applied.application.after_state_hash is None
        assert int(
            await session.scalar(select(func.count()).select_from(CustomerInsight))
            or 0
        ) == insight_count
        assert int(
            await session.scalar(
                select(func.count()).select_from(NeedHypothesisSignal)
            )
            or 0
        ) == need_link_count
        assert int(
            await session.scalar(
                select(func.count())
                .select_from(Artifact)
                .where(Artifact.artifact_type == "customer_map_snapshot")
            )
            or 0
        ) == snapshot_count


@pytest.mark.asyncio
async def test_ll01c_superseded_candidate_cannot_apply_old_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture, mapping, signal, _assessment, candidate_v1 = await _need_candidate(
            session,
            monkeypatch,
        )
        review = await review_learning_candidate(
            session,
            learning_candidate_id=candidate_v1.id,
            decision="APPROVE",
            reviewed_by="founder",
            reason="Approval is valid only while this candidate is current.",
        )

        _analytics_observation, analytics_signal = await _analytics_signal(
            session,
            fixture=fixture,
            mapping=mapping,
        )
        assessment_v2 = await create_learning_assessment(
            session,
            experiment_id=fixture.experiment.id,
            proposed_result="SUPPORTS",
            signal_relations={
                signal.id: "supports",
                analytics_signal.id: "supports",
            },
            alternative_explanations=["Distribution can affect the metric."],
            missing_evidence=["Need an independent experiment."],
        )
        candidate_v2 = await create_learning_candidate(
            session,
            assessment_artifact_id=assessment_v2.artifact.id,
            target_type="need_hypothesis",
            target_id=fixture.need.id,
            statement="Measured evidence may support this frozen Need.",
            relation="supports",
            expected_benefit="Preserve reviewed factual evidence on the Need.",
            regression_risk="Do not promote the Need status automatically.",
        )
        assert candidate_v2.candidate.version == candidate_v1.version + 1

        with pytest.raises(
            LearningApplicationError,
            match="learning_candidate_not_open",
        ):
            await apply_learning_candidate(
                session,
                review_id=review.review.id,
                applied_by="founder",
            )


@pytest.mark.asyncio
async def test_ll01c_review_and_application_receipts_are_immutable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _fixture, candidate = await _no_map_candidate(session, monkeypatch)
        review = await review_learning_candidate(
            session,
            learning_candidate_id=candidate.id,
            decision="NO_MAP_CHANGE",
            reviewed_by="founder",
            reason="Keep map unchanged.",
        )
        applied = await apply_learning_candidate(
            session,
            review_id=review.review.id,
            applied_by="founder",
        )

        with pytest.raises(
            DBAPIError,
            match="learning_candidate_review_update_forbidden",
        ):
            async with session.begin_nested():
                review.review.reason = "rewrite forbidden"
                await session.flush()

        await session.refresh(applied.application)
        with pytest.raises(
            DBAPIError,
            match="learning_application_update_forbidden",
        ):
            async with session.begin_nested():
                applied.application.applied_by = "rewrite forbidden"
                await session.flush()

        assert (
            await session.scalar(
                select(func.count()).select_from(LearningCandidateReview)
            )
            or 0
        ) == 1
