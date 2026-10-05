from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.research.keyword_plan.classification_v2 import (
    CLASSIFIER_VERSION,
    classify_question_v2,
)
from app.modules.research.keyword_plan.clustering_v2 import (
    CLUSTERING_VERSION,
    QuestionForClustering,
    build_question_clusters_v2,
)
from app.modules.research.keyword_plan.contracts import (
    Confidence,
    Intent,
    QueryQuality,
    QuestionType,
)
from app.modules.research.keyword_plan.question_map import build_question_map


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


def _question(
    *,
    key: str,
    text: str,
    locale: str = "en",
    source_priority: int = 5,
    source_count: int = 1,
    independent_source_count: int | None = None,
) -> QuestionForClustering:
    return QuestionForClustering(
        question_key=key,
        text=text,
        normalized_text=text.casefold(),
        signal_refs=tuple(f"signal-{key}-{i}" for i in range(source_count)),
        source_count=source_count,
        independent_source_count=(
            source_count
            if independent_source_count is None
            else independent_source_count
        ),
        source_priority=source_priority,
        classification=classify_question_v2(text, locale=locale),
    )


def test_classification_v2_recognizes_english_authenticity_job() -> None:
    result = classify_question_v2(
        "How do I know if a painting is original?",
        locale="en",
    )

    assert result.topic_key == "authenticity"
    assert result.answer_job == "verify_authenticity"
    assert result.question_type is QuestionType.TRUST
    assert result.intent is Intent.TRUST
    assert result.query_quality is QueryQuality.USABLE
    assert result.classification_status == "classified"
    assert not result.semantic_fallback_required


def test_classification_v2_recognizes_vietnamese_authenticity_independently() -> None:
    result = classify_question_v2(
        "Làm sao biết tranh này là tranh nguyên bản?",
        locale="vi-VN",
    )

    assert result.topic_key == "authenticity"
    assert result.answer_job == "verify_authenticity"
    assert result.intent is Intent.TRUST
    assert result.confidence is not Confidence.LOW


def test_classification_v2_splits_budget_from_value_answer_jobs() -> None:
    budget = classify_question_v2(
        "How much should I spend on my first painting?",
        locale="en",
    )
    value = classify_question_v2(
        "Why is original art expensive?",
        locale="en",
    )

    assert budget.topic_key == "price"
    assert budget.answer_job == "plan_budget"
    assert budget.intent is Intent.EVALUATE
    assert value.topic_key == "price"
    assert value.answer_job == "understand_value"
    assert value.intent is Intent.UNDERSTAND


def test_classification_v2_keeps_low_confidence_language_unresolved() -> None:
    result = classify_question_v2(
        "beautiful paintings ideas",
        locale="en",
    )

    assert result.topic_key == "general"
    assert result.answer_job == "unresolved"
    assert result.classification_status == "unresolved"
    assert result.semantic_fallback_required
    assert result.confidence is Confidence.LOW


def test_classification_v2_fails_closed_for_unsupported_locale() -> None:
    result = classify_question_v2(
        "How do I know if this painting is original?",
        locale="fr",
    )

    assert result.classification_status == "unresolved"
    assert result.semantic_fallback_required
    assert result.confidence is Confidence.LOW


def test_classification_v2_keeps_vietnamese_art_making_off_scope() -> None:
    result = classify_question_v2(
        "Cách phối màu sơn dầu cho đẹp?",
        locale="vi",
    )

    assert result.topic_key == "painting_technique"
    assert result.answer_job == "learn_art_making"
    assert result.query_quality is QueryQuality.OFF_SCOPE
    assert result.classification_status == "classified"


def test_clustering_v2_uses_intent_and_answer_job_not_topic_only() -> None:
    questions = [
        _question(
            key="budget",
            text="How much should I spend on my first painting?",
        ),
        _question(
            key="value",
            text="Why is original art expensive?",
        ),
    ]

    clusters = build_question_clusters_v2(
        need_id="need-1",
        locale="en",
        questions=questions,
    )

    assert len(clusters) == 2
    assert {cluster.answer_job for cluster in clusters} == {
        "plan_budget",
        "understand_value",
    }


def test_clustering_v2_excludes_unresolved_and_off_scope_questions() -> None:
    questions = [
        _question(key="unknown", text="beautiful paintings ideas"),
        _question(key="technique", text="How do I mix oil paint colors?"),
        _question(
            key="auth",
            text="How can I verify an original painting?",
        ),
    ]

    clusters = build_question_clusters_v2(
        need_id="need-1",
        locale="en",
        questions=questions,
    )

    assert len(clusters) == 1
    assert clusters[0].answer_job == "verify_authenticity"
    assert clusters[0].question_keys == ("auth",)


def test_cluster_primary_question_prefers_stronger_source_before_repetition() -> None:
    questions = [
        _question(
            key="autocomplete",
            text="How much should I spend on art?",
            source_priority=4,
            source_count=3,
        ),
        _question(
            key="paa",
            text="What budget should I set for my first painting?",
            source_priority=2,
            source_count=1,
        ),
    ]

    clusters = build_question_clusters_v2(
        need_id="need-1",
        locale="en",
        questions=questions,
    )

    assert len(clusters) == 1
    assert clusters[0].primary_question_key == "paa"


@pytest.mark.asyncio
async def test_question_map_v2_exposes_classification_clusters_and_versions() -> None:
    async with isolated_session() as session:
        project = Project(
            slug=f"qm01b-{uuid4().hex[:8]}",
            name="QM-01B",
            default_locale="en",
        )
        session.add(project)
        await session.flush()

        need = NeedHypothesis(
            project_id=project.id,
            type="question",
            statement="Buyer needs confidence before choosing art.",
            audience_scope="first-time buyer",
            situation="evaluating an artwork",
            origin="customer_intelligence",
            status="SUPPORTED",
            alternative_explanations_json=[],
            missing_evidence_json=[],
            version=1,
        )
        session.add(need)
        await session.flush()

        signals = [
            Signal(
                project_id=project.id,
                source_kind="SEARCH",
                scope="market_web",
                observed_text="How much should I spend on my first painting?",
                source_url="https://example.com/paa",
                locale="en",
                context="qm01b",
                captured_at=datetime.now(UTC),
                fingerprint=uuid4().hex,
                provenance_json={
                    "provider": "serper",
                    "method": "people_also_ask",
                },
            ),
            Signal(
                project_id=project.id,
                source_kind="SEARCH",
                scope="market_web",
                observed_text="What budget should I set for my first painting?",
                source_url="https://example.com/autocomplete",
                locale="en",
                context="qm01b",
                captured_at=datetime.now(UTC),
                fingerprint=uuid4().hex,
                provenance_json={
                    "provider": "serper",
                    "method": "autocomplete",
                },
            ),
            Signal(
                project_id=project.id,
                source_kind="SEARCH",
                scope="market_web",
                observed_text="beautiful paintings ideas",
                source_url="https://example.com/unresolved",
                locale="en",
                context="qm01b",
                captured_at=datetime.now(UTC),
                fingerprint=uuid4().hex,
                provenance_json={
                    "provider": "serper",
                    "method": "related_search",
                },
            ),
        ]
        session.add_all(signals)
        await session.flush()
        session.add_all(
            [
                NeedHypothesisSignal(
                    need_hypothesis_id=need.id,
                    signal_id=signal.id,
                    relation="supports",
                )
                for signal in signals
            ]
        )
        await session.flush()

        payload = await build_question_map(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )

        assert payload["schema_version"] == 2
        source_policy = payload["source_policy"]
        assert isinstance(source_policy, dict)
        assert source_policy["classifier_version"] == CLASSIFIER_VERSION
        assert source_policy["clustering_version"] == CLUSTERING_VERSION
        assert source_policy["model_call"] is False

        questions = payload["questions"]
        assert isinstance(questions, list)
        assert len(questions) == 3

        unresolved = next(
            row
            for row in questions
            if isinstance(row, dict)
            and row["normalized_text"] == "beautiful paintings ideas"
        )
        classification = unresolved["classification"]
        assert isinstance(classification, dict)
        assert classification["status"] == "unresolved"
        assert unresolved["cluster_eligible"] is False

        clusters = payload["clusters"]
        assert isinstance(clusters, list)
        assert len(clusters) == 1
        assert clusters[0]["answer_job"] == "plan_budget"
        assert (
            clusters[0]["primary_question"]
            == "How much should I spend on my first painting?"
        )

        first_question = next(
            row
            for row in questions
            if isinstance(row, dict)
            and row["normalized_text"]
            == "how much should i spend on my first painting"
        )
        first_classification = first_question["classification"]
        assert isinstance(first_classification, dict)
        assert "need_type" not in first_classification

        summary = payload["classification_summary"]
        assert isinstance(summary, dict)
        assert summary["classified_questions"] == 2
        assert summary["unresolved_questions"] == 1
