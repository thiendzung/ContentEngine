"""LL-01B learning assessment and candidate lifecycle.

The service validates and persists learning proposals. It never promotes Customer
Truth, mutates a Need/Insight, or interprets free-text minimum-evidence rules as
numeric thresholds.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import ContentExperiment, NeedHypothesis, Signal
from app.modules.customer_intelligence.models import CustomerInsight
from app.modules.harness.models import Artifact
from app.modules.learning.models import (
    LearningCandidate,
    LearningCandidateAssessment,
    LearningCandidateObservation,
    LearningCandidateSignal,
)
from app.modules.learning.performance_signal import (
    PerformanceSignalError,
    materialize_performance_signal,
)
from app.modules.measurement.models import ContentPerformanceObservation
from app.modules.publishing.models import PublishEvent

AssessmentResult = Literal["SUPPORTS", "CONTRADICTS", "INCONCLUSIVE"]
EvidenceRelation = Literal["supports", "contradicts", "context"]

_ASSESSMENT_ARTIFACT_TYPE = "learning_assessment"
_ASSESSMENT_SCHEMA_VERSION = 1
_CANDIDATE_SCOPE_VERSION = 1
_WS_RE = re.compile(r"\s+")
_INSIGHT_TYPES = {
    "job",
    "pain",
    "desire",
    "question",
    "fear",
    "objection",
    "barrier",
    "trigger",
    "decision_factor",
    "trust_builder",
    "trust_breaker",
    "language",
    "behaviour",
    "expectation",
    "post_purchase_need",
    "referral_trigger",
    "repeat_purchase_trigger",
}


class LearningError(ValueError):
    """Stable fail-closed LL-01B error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class LearningAssessmentResult:
    artifact: Artifact
    replayed: bool


@dataclass(frozen=True, slots=True)
class LearningCandidateResult:
    candidate: LearningCandidate
    replayed: bool


@dataclass(frozen=True, slots=True)
class _AssessmentContext:
    experiment: ContentExperiment
    publish_event: PublishEvent
    publish_package: Artifact
    project_id: UUID
    content_version_id: UUID
    content_item_id: UUID
    content_case_id: UUID
    published_content_id: UUID
    candidate_scope: dict[str, object]


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LearningError(code)
    return {str(key): item for key, item in value.items()}


def _strings(value: object, code: str) -> list[str]:
    if not isinstance(value, list):
        raise LearningError(code)
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise LearningError(code)
        result.append(item.strip())
    return result


def _records(value: object, code: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise LearningError(code)
    return [_dict(item, code) for item in value]


def _uuid(value: object, code: str) -> UUID:
    if not isinstance(value, str):
        raise LearningError(code)
    try:
        return UUID(value)
    except ValueError as exc:
        raise LearningError(code) from exc


def _optional_uuid(value: object, code: str) -> UUID | None:
    if value is None:
        return None
    return _uuid(value, code)


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LearningError(code)
    return value.strip()


def _aware(value: datetime | None, code: str) -> datetime:
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        raise LearningError(code)
    return value


def _clean_strings(values: list[str], code: str) -> list[str]:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise LearningError(code)
    normalized = [value.strip() for value in values]
    result = sorted(set(normalized))
    if len(result) != len(normalized):
        raise LearningError(code)
    return result


def _normalized_statement(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return _WS_RE.sub(" ", normalized)


def _normalize_candidate_proposal(
    *,
    target_type: str,
    proposal: dict[str, object] | None,
) -> dict[str, object]:
    raw = {} if proposal is None else dict(proposal)
    if target_type != "new_customer_insight":
        if raw:
            raise LearningError("learning_candidate_proposal_unexpected")
        return {}
    if set(raw) != {"insight_type", "situation", "need_relation"}:
        raise LearningError("learning_candidate_new_insight_proposal_invalid")
    insight_type = _text(
        raw.get("insight_type"),
        "learning_candidate_new_insight_type_invalid",
    )
    if insight_type not in _INSIGHT_TYPES:
        raise LearningError("learning_candidate_new_insight_type_invalid")
    situation_raw = raw.get("situation")
    if situation_raw is None:
        situation: str | None = None
    elif isinstance(situation_raw, str) and situation_raw.strip():
        situation = situation_raw.strip()
    else:
        raise LearningError("learning_candidate_new_insight_situation_invalid")
    need_relation = _text(
        raw.get("need_relation"),
        "learning_candidate_new_insight_need_relation_invalid",
    )
    if need_relation not in {"supports", "contradicts", "context"}:
        raise LearningError("learning_candidate_new_insight_need_relation_invalid")
    return {
        "insight_type": insight_type,
        "situation": situation,
        "need_relation": need_relation,
    }


def _lens_scope(value: object) -> tuple[str | None, list[str]]:
    if value is None:
        return None, []
    lens = _dict(value, "learning_assessment_lens_invalid")
    primary_raw = lens.get("primary_lens")
    if primary_raw is not None and not isinstance(primary_raw, str):
        raise LearningError("learning_assessment_lens_invalid")
    primary = (
        primary_raw.strip()
        if isinstance(primary_raw, str) and primary_raw.strip()
        else None
    )
    merged = _strings(
        lens.get("merged_lenses", []),
        "learning_assessment_lens_invalid",
    )
    supporting = _strings(
        lens.get("supporting_lenses", []),
        "learning_assessment_lens_invalid",
    )
    if merged and supporting and sorted(set(merged)) != sorted(set(supporting)):
        raise LearningError("learning_assessment_lens_alias_conflict")
    resolved = merged or supporting
    return primary, sorted(set(resolved))


async def _assessment_context(
    session: AsyncSession,
    *,
    experiment_id: UUID,
) -> _AssessmentContext:
    experiment = await session.get(ContentExperiment, experiment_id)
    if experiment is None:
        raise LearningError("learning_assessment_experiment_not_found")
    if (
        experiment.content_item_id is None
        or experiment.content_version_id is None
        or experiment.published_content_id is None
    ):
        raise LearningError("learning_assessment_experiment_not_published")
    review_start = _aware(
        experiment.review_window_start,
        "learning_assessment_review_window_invalid",
    )
    review_end = _aware(
        experiment.review_window_end,
        "learning_assessment_review_window_invalid",
    )
    if review_end <= review_start:
        raise LearningError("learning_assessment_review_window_invalid")
    if (
        not experiment.expected_behaviour.strip()
        or not experiment.measurement_plan_json
        or not experiment.metric_definitions_json
        or not experiment.minimum_evidence_json
    ):
        raise LearningError("learning_assessment_experiment_contract_incomplete")

    events = list(
        (
            await session.scalars(
                select(PublishEvent)
                .where(
                    PublishEvent.published_content_id == experiment.published_content_id,
                    PublishEvent.content_version_id == experiment.content_version_id,
                    PublishEvent.content_experiment_id == experiment.id,
                    PublishEvent.external_status == "publish",
                    PublishEvent.published_at.is_not(None),
                )
                .order_by(PublishEvent.created_at, PublishEvent.id)
            )
        ).all()
    )
    if not events:
        raise LearningError("learning_assessment_publish_event_missing")
    publish_event = events[0]
    package = await session.get(Artifact, publish_event.publish_package_artifact_id)
    if (
        package is None
        or package.artifact_type != "publish_package"
        or not isinstance(package.content_json, dict)
        or package.content_hash != _hash(package.content_json)
    ):
        raise LearningError("learning_assessment_publish_package_invalid")

    identity = _dict(
        package.content_json.get("identity"),
        "learning_assessment_publish_identity_invalid",
    )
    content = _dict(
        package.content_json.get("content"),
        "learning_assessment_publish_content_invalid",
    )
    frozen_project = _uuid(
        identity.get("project_id"),
        "learning_assessment_publish_identity_invalid",
    )
    frozen_experiment = _uuid(
        identity.get("content_experiment_id"),
        "learning_assessment_publish_identity_invalid",
    )
    frozen_version = _uuid(
        identity.get("content_version_id"),
        "learning_assessment_publish_identity_invalid",
    )
    frozen_item = _uuid(
        identity.get("content_item_id"),
        "learning_assessment_publish_identity_invalid",
    )
    frozen_case = _uuid(
        identity.get("content_case_id"),
        "learning_assessment_publish_identity_invalid",
    )
    frozen_need = _uuid(
        identity.get("need_hypothesis_id"),
        "learning_assessment_publish_identity_invalid",
    )
    frozen_need_version = identity.get("need_hypothesis_version")
    if not isinstance(frozen_need_version, int) or frozen_need_version < 1:
        raise LearningError("learning_assessment_need_version_invalid")
    frozen_audience = _optional_uuid(
        identity.get("audience_hypothesis_id"),
        "learning_assessment_audience_invalid",
    )
    journey_stages = sorted(
        set(
            _strings(
                identity.get("journey_stages"),
                "learning_assessment_journey_invalid",
            )
        )
    )
    locale = _text(
        content.get("locale"),
        "learning_assessment_locale_invalid",
    )
    content_type = _text(
        content.get("content_type"),
        "learning_assessment_content_type_invalid",
    )
    primary_lens, supporting_lenses = _lens_scope(
        identity.get("lens_selection")
    )

    if (
        frozen_project != experiment.project_id
        or frozen_experiment != experiment.id
        or frozen_version != experiment.content_version_id
        or frozen_item != experiment.content_item_id
        or frozen_need != experiment.need_hypothesis_id
        or frozen_need_version != experiment.hypothesis_version
    ):
        raise LearningError("learning_assessment_frozen_identity_mismatch")

    candidate_scope: dict[str, object] = {
        "scope_version": _CANDIDATE_SCOPE_VERSION,
        "audience_hypothesis_id": (
            str(frozen_audience) if frozen_audience is not None else None
        ),
        "need_hypothesis_id": str(frozen_need),
        "need_hypothesis_version": frozen_need_version,
        "locale": locale,
        "content_type": content_type,
        "journey_stages": journey_stages,
        "primary_lens": primary_lens,
        "supporting_lenses": supporting_lenses,
        # PM-01 did not freeze LocaleVariant.primary_intent. Using mutable current
        # intent here would silently rewrite history, so LL-01B makes the gap explicit.
        "intent": None,
        "intent_scope_status": "NOT_FROZEN_IN_PM01",
    }
    return _AssessmentContext(
        experiment=experiment,
        publish_event=publish_event,
        publish_package=package,
        project_id=frozen_project,
        content_version_id=frozen_version,
        content_item_id=frozen_item,
        content_case_id=frozen_case,
        published_content_id=experiment.published_content_id,
        candidate_scope=candidate_scope,
    )


def _signal_payload(signal: Signal, relation: EvidenceRelation) -> dict[str, object]:
    return {
        "id": str(signal.id),
        "relation": relation,
        "fingerprint": signal.fingerprint,
        "independence_group": signal.independence_group,
        "observed_text": signal.observed_text,
    }


async def _validate_signal(
    session: AsyncSession,
    *,
    context: _AssessmentContext,
    signal_id: UUID,
    relation: EvidenceRelation,
) -> tuple[Signal, ContentPerformanceObservation]:
    if relation not in {"supports", "contradicts", "context"}:
        raise LearningError("learning_assessment_signal_relation_invalid")
    signal = await session.get(Signal, signal_id)
    if signal is None:
        raise LearningError("learning_assessment_signal_not_found")
    expected_group = f"experiment:{context.experiment.id}"
    if (
        signal.project_id != context.project_id
        or signal.source_kind != "MOTGU"
        or signal.scope != "motgu_site"
        or signal.independence_group != expected_group
    ):
        raise LearningError("learning_assessment_signal_lineage_mismatch")
    provenance = _dict(
        signal.provenance_json,
        "learning_assessment_signal_provenance_invalid",
    )
    if provenance.get("kind") != "content_performance_signal":
        raise LearningError("learning_assessment_signal_kind_invalid")
    if (
        signal.external_id is None
        or signal.fingerprint
        != _hash(
            {
                "external_id": signal.external_id,
                "observed_text": signal.observed_text,
                "provenance": provenance,
            }
        )
    ):
        raise LearningError("learning_assessment_signal_fingerprint_mismatch")
    experiment = _dict(
        provenance.get("experiment"),
        "learning_assessment_signal_provenance_invalid",
    )
    if experiment.get("id") != str(context.experiment.id):
        raise LearningError("learning_assessment_signal_experiment_mismatch")
    content = _dict(
        provenance.get("content"),
        "learning_assessment_signal_provenance_invalid",
    )
    if (
        content.get("content_version_id") != str(context.content_version_id)
        or content.get("content_item_id") != str(context.content_item_id)
        or content.get("content_case_id") != str(context.content_case_id)
        or content.get("locale") != context.candidate_scope.get("locale")
        or signal.locale != context.candidate_scope.get("locale")
    ):
        raise LearningError("learning_assessment_signal_content_mismatch")
    customer = _dict(
        provenance.get("customer"),
        "learning_assessment_signal_provenance_invalid",
    )
    if (
        customer.get("audience_hypothesis_id")
        != context.candidate_scope.get("audience_hypothesis_id")
        or customer.get("need_hypothesis_id")
        != context.candidate_scope.get("need_hypothesis_id")
        or customer.get("need_hypothesis_version")
        != context.candidate_scope.get("need_hypothesis_version")
        or sorted(
            _strings(
                customer.get("journey_stages"),
                "learning_assessment_signal_customer_invalid",
            )
        )
        != context.candidate_scope.get("journey_stages")
        or customer.get("identity_source") != "publish_package"
    ):
        raise LearningError("learning_assessment_signal_customer_mismatch")
    primary_lens, supporting_lenses = _lens_scope(
        provenance.get("lens_selection")
    )
    if (
        primary_lens != context.candidate_scope.get("primary_lens")
        or supporting_lenses != context.candidate_scope.get("supporting_lenses")
    ):
        raise LearningError("learning_assessment_signal_lens_mismatch")
    for metric in _records(
        provenance.get("metrics"),
        "learning_assessment_signal_metrics_invalid",
    ):
        if set(metric) - {
            "id",
            "snapshot_id",
            "provider",
            "metric_date",
            "metric_name",
            "metric_value",
        }:
            raise LearningError("learning_assessment_signal_metric_shape_invalid")
    for window in _records(
        provenance.get("measurement_windows"),
        "learning_assessment_signal_windows_invalid",
    ):
        if set(window) - {
            "snapshot_id",
            "provider",
            "window_start",
            "window_end",
        }:
            raise LearningError("learning_assessment_signal_window_shape_invalid")
    observation_ref = _dict(
        provenance.get("content_performance_observation"),
        "learning_assessment_signal_provenance_invalid",
    )
    observation_id = _uuid(
        observation_ref.get("id"),
        "learning_assessment_observation_ref_invalid",
    )
    observation = await session.get(ContentPerformanceObservation, observation_id)
    if (
        observation is None
        or observation.published_content_id != context.published_content_id
        or observation.content_version_id != context.content_version_id
    ):
        raise LearningError("learning_assessment_observation_lineage_mismatch")
    if observation.data_status == "INSUFFICIENT_DATA":
        raise LearningError("learning_assessment_signal_from_insufficient_data")
    expected_external_id = f"content_performance_observation:{observation.id}"
    if signal.external_id != expected_external_id:
        raise LearningError("learning_assessment_signal_external_id_mismatch")
    try:
        canonical = await materialize_performance_signal(
            session,
            observation_id=observation.id,
        )
    except PerformanceSignalError as exc:
        raise LearningError(
            f"learning_assessment_signal_replay_{exc.code}"
        ) from exc
    if (
        canonical.signal is None
        or canonical.signal.id != signal.id
        or canonical.signal.fingerprint != signal.fingerprint
        or not canonical.replayed
    ):
        raise LearningError("learning_assessment_signal_replay_mismatch")
    return signal, observation


def _assessment_evidence_status(
    *,
    relations: dict[UUID, EvidenceRelation],
    observations: dict[UUID, ContentPerformanceObservation],
) -> str:
    support = any(relation == "supports" for relation in relations.values())
    contradict = any(relation == "contradicts" for relation in relations.values())
    if not support and not contradict:
        return "INSUFFICIENT_DATA"
    if support and contradict:
        return "CONTESTED"
    statuses = {row.data_status for row in observations.values()}
    if "LEARNING_CANDIDATE_READY" in statuses:
        return "CANDIDATE_READY"
    if "REPEATED_PATTERN" in statuses:
        return "REPEATED_PATTERN"
    return "EARLY_SIGNAL"


def _validate_assessment_direction(
    *,
    proposed_result: AssessmentResult,
    relations: dict[UUID, EvidenceRelation],
    alternatives: list[str],
    missing: list[str],
) -> None:
    if proposed_result not in {"SUPPORTS", "CONTRADICTS", "INCONCLUSIVE"}:
        raise LearningError("learning_assessment_result_invalid")
    support = any(relation == "supports" for relation in relations.values())
    contradict = any(relation == "contradicts" for relation in relations.values())
    if support and contradict and proposed_result != "INCONCLUSIVE":
        raise LearningError("learning_assessment_contested_must_be_inconclusive")
    if proposed_result == "SUPPORTS" and (not support or contradict):
        raise LearningError("learning_assessment_support_direction_invalid")
    if proposed_result == "CONTRADICTS" and (not contradict or support):
        raise LearningError("learning_assessment_contradict_direction_invalid")
    if proposed_result in {"SUPPORTS", "CONTRADICTS"} and not alternatives:
        raise LearningError("learning_assessment_alternative_explanation_required")
    if proposed_result == "INCONCLUSIVE" and not missing:
        raise LearningError("learning_assessment_missing_evidence_required")


async def create_learning_assessment(
    session: AsyncSession,
    *,
    experiment_id: UUID,
    proposed_result: AssessmentResult,
    signal_relations: dict[UUID, EvidenceRelation],
    alternative_explanations: list[str],
    missing_evidence: list[str],
) -> LearningAssessmentResult:
    """Persist an immutable, idempotent experiment-level learning proposal."""

    context = await _assessment_context(session, experiment_id=experiment_id)
    alternatives = _clean_strings(
        alternative_explanations,
        "learning_assessment_alternative_duplicate",
    )
    missing = _clean_strings(
        missing_evidence,
        "learning_assessment_missing_duplicate",
    )
    _validate_assessment_direction(
        proposed_result=proposed_result,
        relations=signal_relations,
        alternatives=alternatives,
        missing=missing,
    )

    validated_signals: dict[UUID, Signal] = {}
    observations: dict[UUID, ContentPerformanceObservation] = {}
    observation_relations: dict[UUID, EvidenceRelation] = {}
    for signal_id, relation in sorted(
        signal_relations.items(),
        key=lambda item: str(item[0]),
    ):
        signal, observation = await _validate_signal(
            session,
            context=context,
            signal_id=signal_id,
            relation=relation,
        )
        existing_relation = observation_relations.get(observation.id)
        if existing_relation is not None and existing_relation != relation:
            raise LearningError("learning_assessment_observation_relation_conflict")
        validated_signals[signal.id] = signal
        observations[observation.id] = observation
        observation_relations[observation.id] = relation

    evidence_status = _assessment_evidence_status(
        relations=signal_relations,
        observations=observations,
    )
    review_start = _aware(
        context.experiment.review_window_start,
        "learning_assessment_review_window_invalid",
    )
    review_end = _aware(
        context.experiment.review_window_end,
        "learning_assessment_review_window_invalid",
    )
    signal_rows = [
        _signal_payload(validated_signals[signal_id], signal_relations[signal_id])
        for signal_id in sorted(validated_signals, key=str)
    ]
    observation_rows = [
        {
            "id": str(observation_id),
            "relation": observation_relations[observation_id],
            "data_status": observations[observation_id].data_status,
            "observed_at": observations[observation_id].observed_at.isoformat(),
            "metric_refs": sorted(observations[observation_id].metric_refs_json),
            "statement_excluded": True,
        }
        for observation_id in sorted(observations, key=str)
    ]
    input_fingerprint = _hash(
        {
            "experiment_id": str(context.experiment.id),
            "candidate_scope": context.candidate_scope,
            "signals": signal_rows,
            "observations": observation_rows,
            "proposed_result": proposed_result,
            "alternative_explanations": alternatives,
            "missing_evidence": missing,
            "expected_behaviour": context.experiment.expected_behaviour,
            "measurement_plan": list(context.experiment.measurement_plan_json),
            "metric_definitions": list(context.experiment.metric_definitions_json),
            "minimum_evidence": list(context.experiment.minimum_evidence_json),
            "review_window_start": review_start.isoformat(),
            "review_window_end": review_end.isoformat(),
        }
    )
    payload: dict[str, object] = {
        "schema_version": _ASSESSMENT_SCHEMA_VERSION,
        "artifact_type": _ASSESSMENT_ARTIFACT_TYPE,
        "project_id": str(context.project_id),
        "experiment": {
            "id": str(context.experiment.id),
            "expected_behaviour": context.experiment.expected_behaviour,
            "review_window_start": review_start.isoformat(),
            "review_window_end": review_end.isoformat(),
        },
        "lineage": {
            "published_content_id": str(context.published_content_id),
            "publish_event_id": str(context.publish_event.id),
            "publish_package_artifact_id": str(context.publish_package.id),
            "content_version_id": str(context.content_version_id),
            "content_item_id": str(context.content_item_id),
            "content_case_id": str(context.content_case_id),
        },
        "candidate_scope": context.candidate_scope,
        "assessment": {
            "proposed_result": proposed_result,
            "evidence_status": evidence_status,
            "causal_claim_allowed": False,
            "minimum_evidence_interpreted": False,
        },
        "evidence": {
            "signals": signal_rows,
            "observations": observation_rows,
            "observed_facts": [
                validated_signals[signal_id].observed_text
                for signal_id in sorted(validated_signals, key=str)
            ],
            "alternative_explanations": alternatives,
            "missing_evidence": missing,
        },
        "measurement_contract": {
            "measurement_plan": list(context.experiment.measurement_plan_json),
            "metric_definitions": list(context.experiment.metric_definitions_json),
            "minimum_evidence_verbatim": list(
                context.experiment.minimum_evidence_json
            ),
        },
        "input_fingerprint": input_fingerprint,
    }
    content_hash = _hash(payload)
    existing = await session.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == context.publish_package.run_id,
            Artifact.artifact_type == _ASSESSMENT_ARTIFACT_TYPE,
            Artifact.content_hash == content_hash,
        )
        .order_by(Artifact.version, Artifact.id)
        .limit(1)
    )
    if existing is not None:
        if existing.content_json != payload:
            raise LearningError("learning_assessment_replay_conflict")
        return LearningAssessmentResult(artifact=existing, replayed=True)

    next_version = int(
        await session.scalar(
            select(
                func.coalesce(func.max(Artifact.version), 0) + 1
            ).where(
                Artifact.run_id == context.publish_package.run_id,
                Artifact.artifact_type == _ASSESSMENT_ARTIFACT_TYPE,
            )
        )
        or 1
    )
    artifact = Artifact(
        run_id=context.publish_package.run_id,
        step_run_id=None,
        artifact_type=_ASSESSMENT_ARTIFACT_TYPE,
        locale=_text(
            context.candidate_scope.get("locale"),
            "learning_assessment_locale_invalid",
        ),
        version=next_version,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    return LearningAssessmentResult(artifact=artifact, replayed=False)


def _assessment_payload(artifact: Artifact) -> dict[str, object]:
    if (
        artifact.artifact_type != _ASSESSMENT_ARTIFACT_TYPE
        or not isinstance(artifact.content_json, dict)
        or artifact.content_hash != _hash(artifact.content_json)
    ):
        raise LearningError("learning_candidate_assessment_invalid")
    payload = _dict(
        artifact.content_json,
        "learning_candidate_assessment_invalid",
    )
    if payload.get("artifact_type") != _ASSESSMENT_ARTIFACT_TYPE:
        raise LearningError("learning_candidate_assessment_invalid")
    return payload


async def _validated_assessment_payload(
    session: AsyncSession,
    *,
    artifact: Artifact,
) -> dict[str, object]:
    payload = _assessment_payload(artifact)
    expected_top_level = {
        "schema_version",
        "artifact_type",
        "project_id",
        "experiment",
        "lineage",
        "candidate_scope",
        "assessment",
        "evidence",
        "measurement_contract",
        "input_fingerprint",
    }
    if set(payload) != expected_top_level or payload.get("schema_version") != 1:
        raise LearningError("learning_candidate_assessment_shape_invalid")
    project_id = _uuid(
        payload.get("project_id"),
        "learning_candidate_project_invalid",
    )
    experiment_payload = _dict(
        payload.get("experiment"),
        "learning_candidate_assessment_experiment_invalid",
    )
    experiment_id = _uuid(
        experiment_payload.get("id"),
        "learning_candidate_assessment_experiment_invalid",
    )
    context = await _assessment_context(session, experiment_id=experiment_id)
    if project_id != context.project_id:
        raise LearningError("learning_candidate_assessment_project_mismatch")
    review_start = _aware(
        context.experiment.review_window_start,
        "learning_candidate_assessment_review_window_invalid",
    )
    review_end = _aware(
        context.experiment.review_window_end,
        "learning_candidate_assessment_review_window_invalid",
    )
    expected_experiment_payload = {
        "id": str(context.experiment.id),
        "expected_behaviour": context.experiment.expected_behaviour,
        "review_window_start": review_start.isoformat(),
        "review_window_end": review_end.isoformat(),
    }
    if experiment_payload != expected_experiment_payload:
        raise LearningError("learning_candidate_assessment_experiment_stale")
    scope = _dict(
        payload.get("candidate_scope"),
        "learning_candidate_scope_invalid",
    )
    if scope != context.candidate_scope:
        raise LearningError("learning_candidate_assessment_scope_stale")
    lineage = _dict(
        payload.get("lineage"),
        "learning_candidate_assessment_lineage_invalid",
    )
    expected_lineage = {
        "published_content_id": str(context.published_content_id),
        "publish_event_id": str(context.publish_event.id),
        "publish_package_artifact_id": str(context.publish_package.id),
        "content_version_id": str(context.content_version_id),
        "content_item_id": str(context.content_item_id),
        "content_case_id": str(context.content_case_id),
    }
    if lineage != expected_lineage:
        raise LearningError("learning_candidate_assessment_lineage_mismatch")

    assessment = _dict(
        payload.get("assessment"),
        "learning_candidate_assessment_invalid",
    )
    if set(assessment) != {
        "proposed_result",
        "evidence_status",
        "causal_claim_allowed",
        "minimum_evidence_interpreted",
    }:
        raise LearningError("learning_candidate_assessment_shape_invalid")
    proposed_result = _text(
        assessment.get("proposed_result"),
        "learning_candidate_assessment_result_invalid",
    )
    if proposed_result not in {"SUPPORTS", "CONTRADICTS", "INCONCLUSIVE"}:
        raise LearningError("learning_candidate_assessment_result_invalid")
    if (
        assessment.get("causal_claim_allowed") is not False
        or assessment.get("minimum_evidence_interpreted") is not False
    ):
        raise LearningError("learning_candidate_assessment_guard_invalid")

    evidence = _dict(
        payload.get("evidence"),
        "learning_candidate_assessment_evidence_invalid",
    )
    if set(evidence) != {
        "signals",
        "observations",
        "observed_facts",
        "alternative_explanations",
        "missing_evidence",
    }:
        raise LearningError("learning_candidate_assessment_evidence_shape_invalid")
    signal_relations: dict[UUID, EvidenceRelation] = {}
    observations: dict[UUID, ContentPerformanceObservation] = {}
    observation_relations: dict[UUID, EvidenceRelation] = {}
    observed_facts: list[str] = []
    signal_records: list[dict[str, object]] = []
    seen_signals: set[UUID] = set()
    for record in _records(
        evidence.get("signals", []),
        "learning_candidate_assessment_signal_invalid",
    ):
        if set(record) != {
            "id",
            "relation",
            "fingerprint",
            "independence_group",
            "observed_text",
        }:
            raise LearningError("learning_candidate_assessment_signal_shape_invalid")
        signal_id = _uuid(
            record.get("id"),
            "learning_candidate_assessment_signal_invalid",
        )
        if signal_id in seen_signals:
            raise LearningError("learning_candidate_assessment_signal_duplicate")
        seen_signals.add(signal_id)
        relation_raw = _text(
            record.get("relation"),
            "learning_candidate_assessment_signal_invalid",
        )
        if relation_raw not in {"supports", "contradicts", "context"}:
            raise LearningError("learning_candidate_assessment_signal_invalid")
        relation: EvidenceRelation = relation_raw  # type: ignore[assignment]
        signal, observation = await _validate_signal(
            session,
            context=context,
            signal_id=signal_id,
            relation=relation,
        )
        if (
            record.get("fingerprint") != signal.fingerprint
            or record.get("independence_group") != signal.independence_group
            or record.get("observed_text") != signal.observed_text
        ):
            raise LearningError("learning_candidate_assessment_signal_stale")
        signal_relations[signal_id] = relation
        signal_records.append(record)
        observations[observation.id] = observation
        existing_observation_relation = observation_relations.get(observation.id)
        if (
            existing_observation_relation is not None
            and existing_observation_relation != relation
        ):
            raise LearningError(
                "learning_candidate_assessment_observation_relation_conflict"
            )
        observation_relations[observation.id] = relation
        observed_facts.append(signal.observed_text)

    observation_records = _records(
        evidence.get("observations", []),
        "learning_candidate_assessment_observation_invalid",
    )
    if len(observation_records) != len(observations):
        raise LearningError("learning_candidate_assessment_observation_set_mismatch")
    seen_observations: set[UUID] = set()
    for record in observation_records:
        if set(record) != {
            "id",
            "relation",
            "data_status",
            "observed_at",
            "metric_refs",
            "statement_excluded",
        }:
            raise LearningError(
                "learning_candidate_assessment_observation_shape_invalid"
            )
        observation_id = _uuid(
            record.get("id"),
            "learning_candidate_assessment_observation_invalid",
        )
        if observation_id in seen_observations or observation_id not in observations:
            raise LearningError(
                "learning_candidate_assessment_observation_set_mismatch"
            )
        seen_observations.add(observation_id)
        observation = observations[observation_id]
        relation = observation_relations[observation_id]
        if (
            record.get("relation") != relation
            or record.get("data_status") != observation.data_status
            or record.get("observed_at") != observation.observed_at.isoformat()
            or record.get("metric_refs")
            != sorted(observation.metric_refs_json)
            or record.get("statement_excluded") is not True
        ):
            raise LearningError("learning_candidate_assessment_observation_stale")

    facts = _strings(
        evidence.get("observed_facts", []),
        "learning_candidate_assessment_facts_invalid",
    )
    if facts != observed_facts:
        raise LearningError("learning_candidate_assessment_facts_stale")

    alternatives = _strings(
        evidence.get("alternative_explanations", []),
        "learning_candidate_alternatives_invalid",
    )
    missing = _strings(
        evidence.get("missing_evidence", []),
        "learning_candidate_missing_evidence_invalid",
    )
    _validate_assessment_direction(
        proposed_result=proposed_result,  # type: ignore[arg-type]
        relations=signal_relations,
        alternatives=alternatives,
        missing=missing,
    )
    expected_status = _assessment_evidence_status(
        relations=signal_relations,
        observations=observations,
    )
    if assessment.get("evidence_status") != expected_status:
        raise LearningError("learning_candidate_assessment_status_stale")

    measurement_contract = _dict(
        payload.get("measurement_contract"),
        "learning_candidate_assessment_measurement_contract_invalid",
    )
    expected_measurement_contract = {
        "measurement_plan": list(context.experiment.measurement_plan_json),
        "metric_definitions": list(context.experiment.metric_definitions_json),
        "minimum_evidence_verbatim": list(
            context.experiment.minimum_evidence_json
        ),
    }
    if measurement_contract != expected_measurement_contract:
        raise LearningError("learning_candidate_assessment_measurement_contract_stale")

    signal_rows = sorted(
        signal_records,
        key=lambda record: str(record["id"]),
    )
    observation_rows = [
        {
            "id": str(observation_id),
            "relation": observation_relations[observation_id],
            "data_status": observations[observation_id].data_status,
            "observed_at": observations[observation_id].observed_at.isoformat(),
            "metric_refs": sorted(observations[observation_id].metric_refs_json),
            "statement_excluded": True,
        }
        for observation_id in sorted(observations, key=str)
    ]
    expected_input_fingerprint = _hash(
        {
            "experiment_id": str(context.experiment.id),
            "candidate_scope": context.candidate_scope,
            "signals": signal_rows,
            "observations": observation_rows,
            "proposed_result": proposed_result,
            "alternative_explanations": alternatives,
            "missing_evidence": missing,
            "expected_behaviour": context.experiment.expected_behaviour,
            "measurement_plan": list(context.experiment.measurement_plan_json),
            "metric_definitions": list(context.experiment.metric_definitions_json),
            "minimum_evidence": list(context.experiment.minimum_evidence_json),
            "review_window_start": review_start.isoformat(),
            "review_window_end": review_end.isoformat(),
        }
    )
    if payload.get("input_fingerprint") != expected_input_fingerprint:
        raise LearningError("learning_candidate_assessment_fingerprint_mismatch")
    return payload


def _candidate_key(
    *,
    project_id: UUID,
    target_type: str,
    target_id: UUID | None,
    statement: str,
    proposal: dict[str, object],
    scope: dict[str, object],
) -> str:
    return _hash(
        {
            "project_id": str(project_id),
            "target_type": target_type,
            "target_id": str(target_id) if target_id is not None else None,
            "statement": _normalized_statement(statement),
            "proposal": proposal,
            "scope": scope,
        }
    )


async def _validate_candidate_target(
    session: AsyncSession,
    *,
    project_id: UUID,
    scope: dict[str, object],
    target_type: str,
    target_id: UUID | None,
    relation: str,
) -> None:
    allowed = {
        "customer_insight",
        "need_hypothesis",
        "new_customer_insight",
        "no_map_change",
    }
    if target_type not in allowed:
        raise LearningError("learning_candidate_target_type_invalid")
    if target_type == "need_hypothesis":
        if relation not in {"supports", "contradicts", "context"} or target_id is None:
            raise LearningError("learning_candidate_need_relation_invalid")
        need = await session.get(NeedHypothesis, target_id)
        if need is None or need.project_id != project_id:
            raise LearningError("learning_candidate_need_target_mismatch")
        if scope.get("need_hypothesis_id") != str(need.id):
            raise LearningError("learning_candidate_need_scope_mismatch")
    elif target_type == "customer_insight":
        if relation not in {"supports", "contradicts", "context"} or target_id is None:
            raise LearningError("learning_candidate_insight_relation_invalid")
        insight = await session.get(CustomerInsight, target_id)
        if insight is None or insight.project_id != project_id:
            raise LearningError("learning_candidate_insight_target_mismatch")
        frozen_audience = scope.get("audience_hypothesis_id")
        insight_audience = (
            str(insight.audience_hypothesis_id)
            if insight.audience_hypothesis_id is not None
            else None
        )
        if insight_audience != frozen_audience:
            raise LearningError("learning_candidate_insight_scope_mismatch")
    elif target_type == "new_customer_insight":
        if target_id is not None or relation != "proposes":
            raise LearningError("learning_candidate_new_insight_target_invalid")
    else:
        if target_id is not None or relation != "no_change":
            raise LearningError("learning_candidate_no_change_target_invalid")


async def _candidate_evidence(
    session: AsyncSession,
    *,
    candidate: LearningCandidate | None,
    assessment: Artifact,
) -> tuple[
    dict[UUID, EvidenceRelation],
    dict[UUID, EvidenceRelation],
    set[UUID],
]:
    signal_relations: dict[UUID, EvidenceRelation] = {}
    observation_relations: dict[UUID, EvidenceRelation] = {}
    assessment_ids: set[UUID] = set()

    if candidate is not None:
        for row in (
            await session.scalars(
                select(LearningCandidateAssessment).where(
                    LearningCandidateAssessment.learning_candidate_id == candidate.id
                )
            )
        ).all():
            assessment_ids.add(row.assessment_artifact_id)
        for row in (
            await session.scalars(
                select(LearningCandidateSignal).where(
                    LearningCandidateSignal.learning_candidate_id == candidate.id
                )
            )
        ).all():
            signal_relations[row.signal_id] = row.relation  # type: ignore[assignment]
        for row in (
            await session.scalars(
                select(LearningCandidateObservation).where(
                    LearningCandidateObservation.learning_candidate_id == candidate.id
                )
            )
        ).all():
            observation_relations[row.observation_id] = row.relation  # type: ignore[assignment]

    payload = _assessment_payload(assessment)
    evidence = _dict(
        payload.get("evidence"),
        "learning_candidate_assessment_evidence_invalid",
    )
    for record in _records(
        evidence.get("signals", []),
        "learning_candidate_assessment_signal_invalid",
    ):
        signal_id = _uuid(
            record.get("id"),
            "learning_candidate_assessment_signal_invalid",
        )
        relation = _text(
            record.get("relation"),
            "learning_candidate_assessment_signal_invalid",
        )
        if relation not in {"supports", "contradicts", "context"}:
            raise LearningError("learning_candidate_assessment_signal_invalid")
        existing = signal_relations.get(signal_id)
        if existing is not None and existing != relation:
            raise LearningError("learning_candidate_signal_relation_conflict")
        signal_relations[signal_id] = relation  # type: ignore[assignment]

    for record in _records(
        evidence.get("observations", []),
        "learning_candidate_assessment_observation_invalid",
    ):
        observation_id = _uuid(
            record.get("id"),
            "learning_candidate_assessment_observation_invalid",
        )
        relation = _text(
            record.get("relation"),
            "learning_candidate_assessment_observation_invalid",
        )
        if relation not in {"supports", "contradicts", "context"}:
            raise LearningError("learning_candidate_assessment_observation_invalid")
        existing = observation_relations.get(observation_id)
        if existing is not None and existing != relation:
            raise LearningError("learning_candidate_observation_relation_conflict")
        observation_relations[observation_id] = relation  # type: ignore[assignment]

    assessment_ids.add(assessment.id)
    return signal_relations, observation_relations, assessment_ids


def _classify_candidate_evidence_status(
    *,
    support_groups: set[str],
    contradict_groups: set[str],
    assessment_statuses: list[str],
    assessment_results: list[str],
) -> str:
    if support_groups and contradict_groups:
        return "CONTESTED"
    directional_groups = support_groups or contradict_groups
    if not directional_groups:
        return "NEEDS_EVIDENCE"
    # One experiment is never enough to become a repeated/global learning rule,
    # regardless of an upstream observation maturity label.
    if len(directional_groups) == 1:
        return "EARLY_SIGNAL"

    return _classify_candidate_evidence_status(
        support_groups=support_groups,
        contradict_groups=contradict_groups,
        assessment_statuses=assessment_statuses,
        assessment_results=assessment_results,
    )


async def _candidate_evidence_status(
    session: AsyncSession,
    *,
    signal_relations: dict[UUID, EvidenceRelation],
    assessment_ids: set[UUID],
) -> str:
    support_groups: set[str] = set()
    contradict_groups: set[str] = set()
    for signal_id, relation in signal_relations.items():
        signal = await session.get(Signal, signal_id)
        if signal is None or not signal.independence_group:
            raise LearningError("learning_candidate_signal_lineage_invalid")
        if relation == "supports":
            support_groups.add(signal.independence_group)
        elif relation == "contradicts":
            contradict_groups.add(signal.independence_group)

    assessment_statuses: list[str] = []
    assessment_results: list[str] = []
    for artifact_id in sorted(assessment_ids, key=str):
        artifact = await session.get(Artifact, artifact_id)
        if artifact is None:
            raise LearningError("learning_candidate_assessment_missing")
        payload = await _validated_assessment_payload(
            session,
            artifact=artifact,
        )
        assessment = _dict(
            payload.get("assessment"),
            "learning_candidate_assessment_invalid",
        )
        assessment_statuses.append(
            _text(
                assessment.get("evidence_status"),
                "learning_candidate_assessment_status_invalid",
            )
        )
        assessment_results.append(
            _text(
                assessment.get("proposed_result"),
                "learning_candidate_assessment_result_invalid",
            )
        )

    directional_results = {
        result for result in assessment_results if result != "INCONCLUSIVE"
    }
    if len(directional_results) > 1:
        return "CONTESTED"
    # PM-01 observation maturity is an interpretation, not a deterministic
    # readiness authority. Until minimum-evidence rules are typed and calibrated,
    # LL-01B may auto-promote only to REPEATED_PATTERN.
    del assessment_statuses
    return "REPEATED_PATTERN"


def _validate_candidate_relation_for_evidence(
    *,
    target_type: str,
    relation: str,
    signal_relations: dict[UUID, EvidenceRelation],
) -> None:
    has_support = any(value == "supports" for value in signal_relations.values())
    has_contradiction = any(
        value == "contradicts" for value in signal_relations.values()
    )
    if target_type == "new_customer_insight":
        if not has_support or has_contradiction:
            raise LearningError("learning_candidate_new_insight_evidence_invalid")
        return
    if target_type not in {"need_hypothesis", "customer_insight"}:
        return
    expected_relation = (
        "context"
        if has_support == has_contradiction
        else ("supports" if has_support else "contradicts")
    )
    if relation != expected_relation:
        raise LearningError("learning_candidate_relation_evidence_mismatch")


async def _candidate_context_lists(
    session: AsyncSession,
    *,
    assessment_ids: set[UUID],
) -> tuple[list[str], list[str]]:
    alternatives: set[str] = set()
    missing: set[str] = set()
    for artifact_id in assessment_ids:
        artifact = await session.get(Artifact, artifact_id)
        if artifact is None:
            raise LearningError("learning_candidate_assessment_missing")
        payload = await _validated_assessment_payload(
            session,
            artifact=artifact,
        )
        evidence = _dict(
            payload.get("evidence"),
            "learning_candidate_assessment_evidence_invalid",
        )
        alternatives.update(
            _strings(
                evidence.get("alternative_explanations", []),
                "learning_candidate_alternatives_invalid",
            )
        )
        missing.update(
            _strings(
                evidence.get("missing_evidence", []),
                "learning_candidate_missing_evidence_invalid",
            )
        )
    return sorted(alternatives), sorted(missing)


async def create_learning_candidate(
    session: AsyncSession,
    *,
    assessment_artifact_id: UUID,
    target_type: str,
    target_id: UUID | None,
    statement: str,
    relation: str,
    proposal: dict[str, object] | None = None,
    expected_benefit: str | None = None,
    regression_risk: str | None = None,
) -> LearningCandidateResult:
    """Create/replay one candidate version from a validated assessment Artifact."""

    clean_statement = statement.strip()
    if not clean_statement:
        raise LearningError("learning_candidate_statement_required")
    assessment_artifact = await session.get(Artifact, assessment_artifact_id)
    if assessment_artifact is None:
        raise LearningError("learning_candidate_assessment_missing")
    payload = await _validated_assessment_payload(
        session,
        artifact=assessment_artifact,
    )
    project_id = _uuid(
        payload.get("project_id"),
        "learning_candidate_project_invalid",
    )
    scope = _dict(
        payload.get("candidate_scope"),
        "learning_candidate_scope_invalid",
    )
    normalized_proposal = _normalize_candidate_proposal(
        target_type=target_type,
        proposal=proposal,
    )
    await _validate_candidate_target(
        session,
        project_id=project_id,
        scope=scope,
        target_type=target_type,
        target_id=target_id,
        relation=relation,
    )
    candidate_key = _candidate_key(
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
        statement=clean_statement,
        proposal=normalized_proposal,
        scope=scope,
    )
    latest = await session.scalar(
        select(LearningCandidate)
        .where(
            LearningCandidate.project_id == project_id,
            LearningCandidate.candidate_key == candidate_key,
        )
        .order_by(LearningCandidate.version.desc())
        .limit(1)
    )
    if latest is not None and latest.status != "OPEN":
        raise LearningError("learning_candidate_latest_not_open")

    signal_relations, observation_relations, assessment_ids = await _candidate_evidence(
        session,
        candidate=latest,
        assessment=assessment_artifact,
    )
    evidence_status = await _candidate_evidence_status(
        session,
        signal_relations=signal_relations,
        assessment_ids=assessment_ids,
    )
    _validate_candidate_relation_for_evidence(
        target_type=target_type,
        relation=relation,
        signal_relations=signal_relations,
    )
    alternatives, missing = await _candidate_context_lists(
        session,
        assessment_ids=assessment_ids,
    )
    expected = expected_benefit.strip() if expected_benefit else None
    risk = regression_risk.strip() if regression_risk else None

    if latest is not None:
        assessment_rows = set(
            (
                await session.scalars(
                    select(LearningCandidateAssessment.assessment_artifact_id).where(
                        LearningCandidateAssessment.learning_candidate_id == latest.id
                    )
                )
            ).all()
        )
        if (
            assessment_artifact.id in assessment_rows
            and latest.target_type == target_type
            and latest.target_id == target_id
            and latest.statement == clean_statement
            and latest.relation == relation
            and latest.proposal_json == normalized_proposal
            and latest.scope_json == scope
            and latest.evidence_status == evidence_status
            and latest.alternative_explanations_json == alternatives
            and latest.missing_evidence_json == missing
            and latest.expected_benefit == expected
            and latest.regression_risk == risk
        ):
            return LearningCandidateResult(candidate=latest, replayed=True)

    version = 1 if latest is None else latest.version + 1
    candidate = LearningCandidate(
        project_id=project_id,
        candidate_key=candidate_key,
        version=version,
        target_type=target_type,
        target_id=target_id,
        statement=clean_statement,
        relation=relation,
        proposal_json=normalized_proposal,
        scope_json=scope,
        evidence_status=evidence_status,
        alternative_explanations_json=alternatives,
        missing_evidence_json=missing,
        expected_benefit=expected,
        regression_risk=risk,
        source_assessment_artifact_id=assessment_artifact.id,
        supersedes_id=(latest.id if latest is not None else None),
        status="OPEN",
    )
    session.add(candidate)
    await session.flush()

    for artifact_id in sorted(assessment_ids, key=str):
        session.add(
            LearningCandidateAssessment(
                learning_candidate_id=candidate.id,
                assessment_artifact_id=artifact_id,
            )
        )
    for signal_id in sorted(signal_relations, key=str):
        session.add(
            LearningCandidateSignal(
                learning_candidate_id=candidate.id,
                signal_id=signal_id,
                relation=signal_relations[signal_id],
            )
        )
    for observation_id in sorted(observation_relations, key=str):
        session.add(
            LearningCandidateObservation(
                learning_candidate_id=candidate.id,
                observation_id=observation_id,
                relation=observation_relations[observation_id],
            )
        )
    await session.flush()

    if latest is not None:
        await session.refresh(latest)
        if latest.status != "SUPERSEDED":
            raise LearningError("learning_candidate_prior_not_superseded")

    return LearningCandidateResult(candidate=candidate, replayed=False)


__all__ = [
    "AssessmentResult",
    "EvidenceRelation",
    "LearningAssessmentResult",
    "LearningCandidateResult",
    "LearningError",
    "create_learning_assessment",
    "create_learning_candidate",
]
