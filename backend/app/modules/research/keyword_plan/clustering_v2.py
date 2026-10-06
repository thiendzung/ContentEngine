"""Answer-job clustering for Question Map v2."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

CLUSTERING_VERSION = "question-map-clustering-v2.1"


class QuestionClassificationLike(Protocol):
    @property
    def classification_status(self) -> str: ...

    @property
    def question_type(self) -> str: ...

    @property
    def intent(self) -> str: ...

    @property
    def audience_stage(self) -> str: ...

    @property
    def topic_key(self) -> str: ...

    @property
    def answer_job(self) -> str: ...

    @property
    def confidence(self) -> str: ...

    @property
    def query_quality(self) -> str: ...

    @property
    def semantic_fallback_required(self) -> bool: ...


@dataclass(slots=True, frozen=True)
class QuestionForClustering:
    question_key: str
    text: str
    normalized_text: str
    signal_refs: tuple[str, ...]
    source_count: int
    independent_source_count: int
    source_priority: int
    classification: QuestionClassificationLike


@dataclass(slots=True, frozen=True)
class QuestionClusterV2:
    cluster_key: str
    intent: str
    audience_stage: str
    answer_job: str
    primary_question_key: str
    primary_question: str
    question_keys: tuple[str, ...]
    signal_refs: tuple[str, ...]
    topic_keys: tuple[str, ...]
    question_count: int


def cluster_eligible(question: QuestionForClustering) -> bool:
    classification = question.classification
    return (
        classification.classification_status == "classified"
        and classification.query_quality == "usable"
        and not classification.semantic_fallback_required
        and classification.answer_job != "unresolved"
    )


def _cluster_key(
    *,
    need_id: str,
    locale: str,
    intent: str,
    audience_stage: str,
    answer_job: str,
) -> str:
    payload = (
        f"{need_id}\x1f{locale}\x1f{intent}\x1f"
        f"{audience_stage}\x1f{answer_job}"
    ).encode()
    return hashlib.sha256(payload).hexdigest()[:24]


def _primary(group: list[QuestionForClustering]) -> QuestionForClustering:
    return sorted(
        group,
        key=lambda item: (
            item.source_priority,
            -item.independent_source_count,
            -item.source_count,
            item.normalized_text,
            item.question_key,
        ),
    )[0]


def build_question_clusters_v2(
    *,
    need_id: str,
    locale: str,
    questions: list[QuestionForClustering],
) -> list[QuestionClusterV2]:
    grouped: dict[tuple[str, str, str], list[QuestionForClustering]] = {}
    for question in questions:
        if not cluster_eligible(question):
            continue
        key = (
            str(question.classification.intent),
            str(question.classification.audience_stage),
            question.classification.answer_job,
        )
        grouped.setdefault(key, []).append(question)

    clusters: list[QuestionClusterV2] = []
    for (intent, audience_stage, answer_job), group in sorted(
        grouped.items()
    ):
        primary = _primary(group)
        question_keys = tuple(sorted(item.question_key for item in group))
        signal_refs = tuple(
            sorted(
                {
                    signal_ref
                    for item in group
                    for signal_ref in item.signal_refs
                }
            )
        )
        topic_keys = tuple(
            sorted({item.classification.topic_key for item in group})
        )
        clusters.append(
            QuestionClusterV2(
                cluster_key=_cluster_key(
                    need_id=need_id,
                    locale=locale,
                    intent=intent,
                    audience_stage=audience_stage,
                    answer_job=answer_job,
                ),
                intent=intent,
                audience_stage=audience_stage,
                answer_job=answer_job,
                primary_question_key=primary.question_key,
                primary_question=primary.text,
                question_keys=question_keys,
                signal_refs=signal_refs,
                topic_keys=topic_keys,
                question_count=len(group),
            )
        )
    return clusters


__all__ = [
    "CLUSTERING_VERSION",
    "QuestionClassificationLike",
    "QuestionClusterV2",
    "QuestionForClustering",
    "build_question_clusters_v2",
    "cluster_eligible",
]
