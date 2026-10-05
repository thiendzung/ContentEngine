"""Canonical Question Map derived read model with QM-01B semantics."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    cluster_eligible,
)
from app.modules.research.keyword_plan.contracts import QueryQuality
from app.modules.research.keyword_plan.normalize import normalize_text

QUESTION_MAP_SCHEMA_VERSION = 2


class QuestionMapError(ValueError):
    """Fail-closed Question Map error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _signal_method(signal: Signal) -> str:
    value = signal.provenance_json.get("method")
    return value.strip().casefold() if isinstance(value, str) else ""


def _signal_priority(signal: Signal) -> int:
    if signal.scope == "motgu_direct":
        return 0
    method = _signal_method(signal)
    ranks = {
        "search_console": 1,
        "google_search_console": 1,
        "people_also_ask": 2,
        "related_search": 3,
        "autocomplete": 4,
    }
    return ranks.get(method, 5)


def _representative(signals: list[Signal]) -> Signal:
    return sorted(
        signals,
        key=lambda row: (
            _signal_priority(row),
            row.observed_text.casefold(),
            row.observed_text,
            str(row.id),
        ),
    )[0]


def _classification_payload(question: QuestionForClustering) -> dict[str, object]:
    classification = question.classification
    return {
        "version": CLASSIFIER_VERSION,
        "status": classification.classification_status,
        "question_type": str(classification.question_type),
        "intent": str(classification.intent),
        "audience_stage": str(classification.audience_stage),
        "topic_key": classification.topic_key,
        "answer_job": classification.answer_job,
        "confidence": str(classification.confidence),
        "query_quality": str(classification.query_quality),
        "semantic_fallback_required": classification.semantic_fallback_required,
    }


def _question_payload(question: QuestionForClustering) -> dict[str, object]:
    return {
        "question_key": question.question_key,
        "text": question.text,
        "normalized_text": question.normalized_text,
        "signal_refs": list(question.signal_refs),
        "source_count": question.source_count,
        "independent_source_count": question.independent_source_count,
        "source_priority": question.source_priority,
        "classification": _classification_payload(question),
        "cluster_eligible": cluster_eligible(question),
    }


async def build_question_map(
    session: AsyncSession,
    *,
    project_id: UUID,
    need_id: UUID,
    locale: str,
) -> dict[str, object]:
    """Build a deterministic locale-specific projection from canonical state."""

    normalized_locale = locale.strip().casefold()
    if not normalized_locale:
        raise QuestionMapError("question_map_locale_required")

    project = await session.get(Project, project_id)
    if project is None:
        raise QuestionMapError("question_map_project_not_found")

    need = await session.get(NeedHypothesis, need_id)
    if need is None or need.project_id != project.id:
        raise QuestionMapError("question_map_need_not_found")

    rows = (
        await session.execute(
            select(NeedHypothesisSignal, Signal)
            .join(Signal, Signal.id == NeedHypothesisSignal.signal_id)
            .where(
                NeedHypothesisSignal.need_hypothesis_id == need.id,
                NeedHypothesisSignal.relation == "supports",
                Signal.project_id == project.id,
                Signal.source_kind == "SEARCH",
            )
            .order_by(Signal.id)
        )
    ).all()

    grouped: dict[str, list[Signal]] = defaultdict(list)
    for _link, signal in rows:
        if signal.locale.strip().casefold() != normalized_locale:
            continue
        normalized = normalize_text(signal.observed_text)
        if not normalized:
            continue
        grouped[normalized].append(signal)

    derived_questions: list[QuestionForClustering] = []
    all_signal_refs: list[str] = []
    for normalized in sorted(grouped):
        signals = grouped[normalized]
        representative = _representative(signals)
        refs = tuple(sorted(str(row.id) for row in signals))
        all_signal_refs.extend(refs)
        classification = classify_question_v2(
            representative.observed_text,
            locale=normalized_locale,
        )
        derived_questions.append(
            QuestionForClustering(
                question_key=hashlib.sha256(
                    (
                        f"{need.id}\x1f{normalized_locale}\x1f{normalized}"
                    ).encode()
                ).hexdigest()[:24],
                text=representative.observed_text.strip(),
                normalized_text=normalized,
                signal_refs=refs,
                source_count=len(refs),
                independent_source_count=len(
                    {
                        row.independence_group or row.fingerprint
                        for row in signals
                    }
                ),
                source_priority=min(_signal_priority(row) for row in signals),
                classification=classification,
            )
        )

    clusters = build_question_clusters_v2(
        need_id=str(need.id),
        locale=normalized_locale,
        questions=derived_questions,
    )
    questions = [_question_payload(question) for question in derived_questions]
    cluster_payloads: list[dict[str, object]] = [
        {
            "cluster_key": cluster.cluster_key,
            "intent": cluster.intent,
            "answer_job": cluster.answer_job,
            "primary_question_key": cluster.primary_question_key,
            "primary_question": cluster.primary_question,
            "question_keys": list(cluster.question_keys),
            "signal_refs": list(cluster.signal_refs),
            "topic_keys": list(cluster.topic_keys),
            "question_count": cluster.question_count,
        }
        for cluster in clusters
    ]

    unresolved_count = sum(
        question.classification.classification_status == "unresolved"
        for question in derived_questions
    )
    off_scope_count = sum(
        question.classification.query_quality is QueryQuality.OFF_SCOPE
        for question in derived_questions
    )
    classified_count = len(derived_questions) - unresolved_count

    snapshot: dict[str, object] = {
        "schema_version": QUESTION_MAP_SCHEMA_VERSION,
        "project": {
            "id": str(project.id),
            "slug": project.slug,
        },
        "need": {
            "id": str(need.id),
            "version": need.version,
            "status": need.status,
            "type": need.type,
            "statement": need.statement,
            "audience_hypothesis_id": (
                str(need.audience_hypothesis_id)
                if need.audience_hypothesis_id is not None
                else None
            ),
        },
        "locale": normalized_locale,
        "source_policy": {
            "signal_source_kind": "SEARCH",
            "need_relation": "supports",
            "canonical_need": True,
            "classifier_version": CLASSIFIER_VERSION,
            "clustering_version": CLUSTERING_VERSION,
            "model_call": False,
        },
        "counts": {
            "questions": len(questions),
            "search_signals": len(all_signal_refs),
        },
        "classification_summary": {
            "classified_questions": classified_count,
            "unresolved_questions": unresolved_count,
            "off_scope_questions": off_scope_count,
        },
        "cluster_summary": {
            "clusters": len(cluster_payloads),
        },
        "questions": questions,
        "clusters": cluster_payloads,
        "signal_refs": sorted(all_signal_refs),
    }

    return {
        **snapshot,
        "snapshot_hash": _stable_hash(snapshot),
    }


__all__ = [
    "QUESTION_MAP_SCHEMA_VERSION",
    "QuestionMapError",
    "build_question_map",
]
