"""LL-01D post-application validation, human resolution, and rollback."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    ContentExperiment,
    ContentItem,
    NeedHypothesis,
    NeedHypothesisReview,
    NeedHypothesisSignal,
    Project,
    Signal,
    utc_now,
)
from app.modules.customer_intelligence.insights import (
    CustomerInsightError,
    link_customer_insight_signal,
    review_customer_insight,
    signal_independence_key,
)
from app.modules.customer_intelligence.living_map import (
    refresh_customer_map_snapshot_artifact,
)
from app.modules.customer_intelligence.models import (
    CustomerInsight,
    CustomerInsightSignal,
)
from app.modules.harness.models import Artifact
from app.modules.learning.application import (
    LearningApplicationError,
    _ensure_need_signal_link,
)
from app.modules.learning.models import (
    LearningApplication,
    LearningCandidate,
    LearningResolution,
    LearningResolutionApplication,
    LearningValidation,
)
from app.modules.learning.performance_signal import (
    PerformanceSignalError,
    materialize_performance_signal,
)
from app.modules.measurement.models import PerformanceMetric

EvidenceRelation = Literal["supports", "contradicts", "context"]
ValidationStatus = Literal[
    "NEEDS_MORE_EVIDENCE",
    "INCONCLUSIVE",
    "VALIDATED",
    "REGRESSED",
    "CONTESTED",
]
ResolutionDecision = Literal[
    "PROMOTE",
    "KEEP",
    "ROLLBACK",
    "REJECT",
    "REQUEST_MORE_EVIDENCE",
    "ARCHIVE_CANDIDATE",
]


class LearningRegressionError(ValueError):
    """Stable fail-closed LL-01D error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class MetricComparisonInput:
    baseline_metric_id: UUID
    candidate_metric_id: UUID


@dataclass(frozen=True, slots=True)
class LearningValidationResult:
    validation: LearningValidation
    replayed: bool


@dataclass(frozen=True, slots=True)
class LearningResolutionResult:
    resolution: LearningResolution
    replayed: bool


@dataclass(frozen=True, slots=True)
class LearningResolutionApplicationResult:
    application: LearningResolutionApplication
    replayed: bool
    customer_map_snapshot_artifact_id: UUID | None
    change_report: dict[str, object] | None


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text(value: str, code: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise LearningRegressionError(code)
    return normalized


def _clean_strings(values: list[str], code: str) -> list[str]:
    normalized = [_text(value, code) for value in values]
    result = sorted(set(normalized))
    if len(result) != len(normalized):
        raise LearningRegressionError(code)
    return result


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LearningRegressionError(code)
    return {str(key): item for key, item in value.items()}


def _strings(value: object, code: str) -> list[str]:
    if not isinstance(value, list):
        raise LearningRegressionError(code)
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise LearningRegressionError(code)
        result.append(item.strip())
    return result


def _uuid(value: object, code: str) -> UUID:
    if not isinstance(value, str):
        raise LearningRegressionError(code)
    try:
        return UUID(value)
    except ValueError as exc:
        raise LearningRegressionError(code) from exc


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return format(normalized.quantize(Decimal(1)), "f")
    return format(normalized, "f")


def _lens_scope(value: object) -> tuple[str | None, list[str]]:
    if value is None:
        return None, []
    lens = _dict(value, "learning_validation_signal_lens_invalid")
    primary_raw = lens.get("primary_lens")
    if primary_raw is not None and not isinstance(primary_raw, str):
        raise LearningRegressionError("learning_validation_signal_lens_invalid")
    primary = (
        primary_raw.strip()
        if isinstance(primary_raw, str) and primary_raw.strip()
        else None
    )
    merged_raw = lens.get("merged_lenses", lens.get("supporting_lenses", []))
    supporting = sorted(
        set(_strings(merged_raw, "learning_validation_signal_lens_invalid"))
    )
    return primary, supporting


async def _canonical_independence_key(
    session: AsyncSession,
    signal: Signal,
    cache: dict[UUID, str],
) -> str:
    try:
        return await signal_independence_key(session, signal, cache)
    except CustomerInsightError as exc:
        raise LearningRegressionError(
            f"learning_validation_{exc.code}"
        ) from exc


async def _target_evidence_snapshot(
    session: AsyncSession,
    *,
    project_id: UUID,
    target_type: str,
    target_id: UUID,
) -> list[dict[str, object]]:
    evidence_rows: list[tuple[UUID, str]]
    if target_type == "need_hypothesis":
        need_rows = list(
            (
                await session.scalars(
                    select(NeedHypothesisSignal)
                    .where(
                        NeedHypothesisSignal.need_hypothesis_id == target_id
                    )
                    .order_by(
                        NeedHypothesisSignal.relation,
                        NeedHypothesisSignal.signal_id,
                    )
                )
            ).all()
        )
        evidence_rows = [
            (row.signal_id, row.relation) for row in need_rows
        ]
    elif target_type in {"customer_insight", "new_customer_insight"}:
        insight_rows = list(
            (
                await session.scalars(
                    select(CustomerInsightSignal)
                    .where(
                        CustomerInsightSignal.customer_insight_id == target_id
                    )
                    .order_by(
                        CustomerInsightSignal.relation,
                        CustomerInsightSignal.signal_id,
                    )
                )
            ).all()
        )
        evidence_rows = [
            (row.signal_id, row.relation) for row in insight_rows
        ]
    else:
        raise LearningRegressionError(
            "learning_validation_target_type_invalid"
        )

    cache: dict[UUID, str] = {}
    result: list[dict[str, object]] = []
    for signal_id, relation in evidence_rows:
        signal = await session.get(Signal, signal_id)
        if signal is None or signal.project_id != project_id:
            raise LearningRegressionError(
                "learning_validation_target_evidence_stale"
            )
        result.append(
            {
                "signal_id": str(signal.id),
                "relation": relation,
                "fingerprint": signal.fingerprint,
                "independence_key": await _canonical_independence_key(
                    session,
                    signal,
                    cache,
                ),
            }
        )
    return result


async def _target_snapshot(
    session: AsyncSession,
    *,
    application: LearningApplication,
    lock: bool,
) -> dict[str, object]:
    if application.target_type == "no_map_change":
        if application.resulting_target_id is not None:
            raise LearningRegressionError("learning_validation_no_map_target_invalid")
        return {"target_type": "no_map_change", "current_target": None}

    if application.resulting_target_id is None:
        raise LearningRegressionError("learning_validation_target_missing")

    if application.target_type == "need_hypothesis":
        need_stmt = (
            select(NeedHypothesis)
            .where(NeedHypothesis.id == application.resulting_target_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            need_stmt = need_stmt.with_for_update()
        need = await session.scalar(need_stmt)
        if need is None or need.project_id != application.project_id:
            raise LearningRegressionError("learning_validation_need_target_stale")
        return {
            "target_type": application.target_type,
            "current_target": {
                "id": str(need.id),
                "version": need.version,
                "status": need.status,
                "audience_hypothesis_id": (
                    str(need.audience_hypothesis_id)
                    if need.audience_hypothesis_id is not None
                    else None
                ),
                "evidence": await _target_evidence_snapshot(
                    session,
                    project_id=application.project_id,
                    target_type=application.target_type,
                    target_id=need.id,
                ),
            },
        }

    if application.target_type in {"customer_insight", "new_customer_insight"}:
        insight_stmt = (
            select(CustomerInsight)
            .where(CustomerInsight.id == application.resulting_target_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            insight_stmt = insight_stmt.with_for_update()
        insight = await session.scalar(insight_stmt)
        if insight is None or insight.project_id != application.project_id:
            raise LearningRegressionError("learning_validation_insight_target_stale")
        latest_version = await session.scalar(
            select(func.max(CustomerInsight.version)).where(
                CustomerInsight.project_id == insight.project_id,
                CustomerInsight.insight_key == insight.insight_key,
            )
        )
        if latest_version != insight.version:
            raise LearningRegressionError("learning_validation_insight_version_stale")
        return {
            "target_type": application.target_type,
            "current_target": {
                "id": str(insight.id),
                "insight_key": insight.insight_key,
                "version": insight.version,
                "status": insight.status,
                "audience_hypothesis_id": (
                    str(insight.audience_hypothesis_id)
                    if insight.audience_hypothesis_id is not None
                    else None
                ),
                "evidence": await _target_evidence_snapshot(
                    session,
                    project_id=application.project_id,
                    target_type=application.target_type,
                    target_id=insight.id,
                ),
            },
        }

    raise LearningRegressionError("learning_validation_target_type_invalid")


async def _application_context(
    session: AsyncSession,
    *,
    application_id: UUID,
) -> tuple[LearningApplication, LearningCandidate]:
    application = await session.get(LearningApplication, application_id)
    if application is None:
        raise LearningRegressionError("learning_application_not_found")
    candidate = await session.get(LearningCandidate, application.learning_candidate_id)
    if (
        candidate is None
        or candidate.project_id != application.project_id
        or candidate.version != application.candidate_version
        or candidate.scope_json != application.frozen_scope_json
        or candidate.target_type != application.target_type
        or application.candidate_snapshot_hash == ""
    ):
        raise LearningRegressionError("learning_validation_application_identity_invalid")
    latest_candidate_version = await session.scalar(
        select(func.max(LearningCandidate.version)).where(
            LearningCandidate.project_id == candidate.project_id,
            LearningCandidate.candidate_key == candidate.candidate_key,
        )
    )
    if (
        latest_candidate_version != candidate.version
        or candidate.status != "OPEN"
    ):
        raise LearningRegressionError("learning_validation_candidate_stale")
    return application, candidate


def _expected_scope(application: LearningApplication) -> dict[str, object]:
    scope = dict(application.frozen_scope_json)
    expected_keys = {
        "scope_version",
        "audience_hypothesis_id",
        "need_hypothesis_id",
        "need_hypothesis_version",
        "locale",
        "content_type",
        "journey_stages",
        "primary_lens",
        "supporting_lenses",
        "intent",
        "intent_scope_status",
    }
    if set(scope) != expected_keys:
        raise LearningRegressionError("learning_validation_scope_invalid")
    return scope


async def _signal_metric_records(
    session: AsyncSession,
    signal: Signal,
    *,
    scope: dict[str, object],
    not_before: datetime | None = None,
) -> list[dict[str, object]]:
    if (
        signal.source_kind != "MOTGU"
        or signal.scope != "motgu_site"
        or signal.external_id is None
    ):
        raise LearningRegressionError("learning_validation_signal_kind_invalid")
    provenance = _dict(
        signal.provenance_json,
        "learning_validation_signal_provenance_invalid",
    )
    if provenance.get("kind") != "content_performance_signal":
        raise LearningRegressionError("learning_validation_signal_kind_invalid")
    observation_payload = _dict(
        provenance.get("content_performance_observation"),
        "learning_validation_signal_provenance_invalid",
    )
    observation_id = _uuid(
        observation_payload.get("id"),
        "learning_validation_signal_observation_invalid",
    )
    try:
        rematerialized = await materialize_performance_signal(
            session,
            observation_id=observation_id,
        )
    except PerformanceSignalError as exc:
        raise LearningRegressionError(
            f"learning_validation_{exc.code}"
        ) from exc
    if rematerialized.signal is None or rematerialized.signal.id != signal.id:
        raise LearningRegressionError("learning_validation_signal_replay_mismatch")
    if signal.fingerprint != _hash(
        {
            "external_id": signal.external_id,
            "observed_text": signal.observed_text,
            "provenance": provenance,
        }
    ):
        raise LearningRegressionError("learning_validation_signal_fingerprint_mismatch")

    content = _dict(
        provenance.get("content"),
        "learning_validation_signal_provenance_invalid",
    )
    content_item_id = _uuid(
        content.get("content_item_id"),
        "learning_validation_signal_content_item_invalid",
    )
    content_item = await session.get(ContentItem, content_item_id)
    if (
        content_item is None
        or content_item.project_id != signal.project_id
        or content_item.content_type != scope.get("content_type")
    ):
        raise LearningRegressionError(
            "learning_validation_signal_content_type_mismatch"
        )
    experiment_payload = _dict(
        provenance.get("experiment"),
        "learning_validation_signal_provenance_invalid",
    )
    experiment_id = _uuid(
        experiment_payload.get("id"),
        "learning_validation_signal_experiment_invalid",
    )
    experiment = await session.get(ContentExperiment, experiment_id)
    if (
        experiment is None
        or experiment.project_id != signal.project_id
        or experiment.content_item_id != content_item.id
        or experiment_payload.get("review_window_start")
            != (
                experiment.review_window_start.isoformat()
                if experiment.review_window_start is not None
                else None
            )
        or experiment_payload.get("review_window_end")
            != (
                experiment.review_window_end.isoformat()
                if experiment.review_window_end is not None
                else None
            )
    ):
        raise LearningRegressionError(
            "learning_validation_signal_experiment_mismatch"
        )
    if not_before is not None:
        if signal.observed_at is None or signal.observed_at <= not_before:
            raise LearningRegressionError(
                "learning_validation_signal_not_later"
            )
        if (
            experiment.review_window_start is None
            or experiment.review_window_start < not_before
        ):
            raise LearningRegressionError(
                "learning_validation_experiment_not_later"
            )
    customer = _dict(
        provenance.get("customer"),
        "learning_validation_signal_provenance_invalid",
    )
    if (
        content.get("locale") != scope.get("locale")
        or signal.locale != scope.get("locale")
        or customer.get("audience_hypothesis_id")
        != scope.get("audience_hypothesis_id")
        or customer.get("need_hypothesis_id")
        != scope.get("need_hypothesis_id")
        or customer.get("need_hypothesis_version")
        != scope.get("need_hypothesis_version")
        or sorted(
            _strings(
                customer.get("journey_stages"),
                "learning_validation_signal_scope_invalid",
            )
        )
        != scope.get("journey_stages")
    ):
        raise LearningRegressionError("learning_validation_signal_scope_mismatch")

    primary_lens, supporting_lenses = _lens_scope(provenance.get("lens_selection"))
    if (
        primary_lens != scope.get("primary_lens")
        or supporting_lenses != scope.get("supporting_lenses")
    ):
        raise LearningRegressionError("learning_validation_signal_scope_mismatch")

    metrics = provenance.get("metrics")
    if not isinstance(metrics, list):
        raise LearningRegressionError("learning_validation_signal_metrics_invalid")
    contract = {
        "experiment_id": str(experiment.id),
        "review_window_start": experiment_payload.get("review_window_start"),
        "review_window_end": experiment_payload.get("review_window_end"),
        "metric_definitions": list(experiment.metric_definitions_json),
    }
    result: list[dict[str, object]] = []
    for row in metrics:
        metric = _dict(row, "learning_validation_signal_metrics_invalid")
        metric["_experiment_contract"] = contract
        result.append(metric)
    return result


async def _load_signal_set(
    session: AsyncSession,
    *,
    application: LearningApplication,
    signal_relations: dict[UUID, EvidenceRelation],
    not_before: datetime | None = None,
) -> tuple[
    list[dict[str, object]],
    set[str],
    dict[UUID, dict[str, object]],
]:
    scope = _expected_scope(application)
    cache: dict[UUID, str] = {}
    rows: list[dict[str, object]] = []
    groups: set[str] = set()
    metrics: dict[UUID, dict[str, object]] = {}
    for signal_id, relation in sorted(signal_relations.items(), key=lambda item: str(item[0])):
        if relation not in {"supports", "contradicts", "context"}:
            raise LearningRegressionError("learning_validation_signal_relation_invalid")
        signal = await session.get(Signal, signal_id)
        if signal is None or signal.project_id != application.project_id:
            raise LearningRegressionError("learning_validation_signal_not_found")
        metric_rows = await _signal_metric_records(
            session,
            signal,
            scope=scope,
            not_before=not_before,
        )
        independence_key = await _canonical_independence_key(
            session,
            signal,
            cache,
        )
        groups.add(independence_key)
        rows.append(
            {
                "signal_id": str(signal.id),
                "relation": relation,
                "fingerprint": signal.fingerprint,
                "independence_key": independence_key,
            }
        )
        for metric_row in metric_rows:
            metric_id = _uuid(
                metric_row.get("id"),
                "learning_validation_signal_metric_id_invalid",
            )
            existing = metrics.get(metric_id)
            if existing is not None and existing != metric_row:
                raise LearningRegressionError("learning_validation_metric_ref_conflict")
            metrics[metric_id] = metric_row
    return rows, groups, metrics


def _baseline_relations(application: LearningApplication) -> dict[UUID, EvidenceRelation]:
    result: dict[UUID, EvidenceRelation] = {}
    for raw in application.applied_signal_refs_json:
        row = _dict(raw, "learning_validation_baseline_signal_invalid")
        signal_id = _uuid(
            row.get("signal_id"),
            "learning_validation_baseline_signal_invalid",
        )
        relation = row.get("relation")
        if relation not in {"supports", "contradicts", "context"}:
            raise LearningRegressionError("learning_validation_baseline_signal_invalid")
        result[signal_id] = cast(EvidenceRelation, relation)
    return result


async def _metric_comparisons(
    session: AsyncSession,
    *,
    inputs: list[MetricComparisonInput],
    baseline_metrics: dict[UUID, dict[str, object]],
    candidate_metrics: dict[UUID, dict[str, object]],
) -> list[dict[str, object]]:
    seen: set[tuple[UUID, UUID]] = set()
    result: list[dict[str, object]] = []
    for comparison in inputs:
        key = (comparison.baseline_metric_id, comparison.candidate_metric_id)
        if key in seen:
            raise LearningRegressionError("learning_validation_metric_comparison_duplicate")
        seen.add(key)
        if comparison.baseline_metric_id not in baseline_metrics:
            raise LearningRegressionError("learning_validation_baseline_metric_unbound")
        if comparison.candidate_metric_id not in candidate_metrics:
            raise LearningRegressionError("learning_validation_candidate_metric_unbound")
        baseline = await session.get(PerformanceMetric, comparison.baseline_metric_id)
        candidate = await session.get(PerformanceMetric, comparison.candidate_metric_id)
        if baseline is None or candidate is None:
            raise LearningRegressionError("learning_validation_metric_missing")
        if (
            baseline.metric_name != candidate.metric_name
            or baseline.provider != candidate.provider
            or baseline.dimensions_json != candidate.dimensions_json
        ):
            raise LearningRegressionError("learning_validation_metric_definition_mismatch")
        baseline_payload = baseline_metrics[baseline.id]
        candidate_payload = candidate_metrics[candidate.id]
        baseline_contract = _dict(
            baseline_payload.get("_experiment_contract"),
            "learning_validation_metric_contract_invalid",
        )
        candidate_contract = _dict(
            candidate_payload.get("_experiment_contract"),
            "learning_validation_metric_contract_invalid",
        )
        if (
            baseline_contract.get("metric_definitions")
            != candidate_contract.get("metric_definitions")
        ):
            raise LearningRegressionError(
                "learning_validation_metric_contract_mismatch"
            )
        if (
            baseline_payload.get("metric_name") != baseline.metric_name
            or baseline_payload.get("provider") != baseline.provider
            or baseline_payload.get("metric_value") != _decimal_text(baseline.metric_value)
            or candidate_payload.get("metric_name") != candidate.metric_name
            or candidate_payload.get("provider") != candidate.provider
            or candidate_payload.get("metric_value") != _decimal_text(candidate.metric_value)
        ):
            raise LearningRegressionError("learning_validation_metric_provenance_mismatch")
        delta = candidate.metric_value - baseline.metric_value
        direction = (
            "INCREASE"
            if delta > 0
            else "DECREASE"
            if delta < 0
            else "UNCHANGED"
        )
        result.append(
            {
                "metric_name": baseline.metric_name,
                "provider": baseline.provider,
                "baseline_metric_id": str(baseline.id),
                "candidate_metric_id": str(candidate.id),
                "baseline_value": _decimal_text(baseline.metric_value),
                "candidate_value": _decimal_text(candidate.metric_value),
                "delta": _decimal_text(delta),
                "direction": direction,
                "baseline_experiment_id": baseline_contract["experiment_id"],
                "candidate_experiment_id": candidate_contract["experiment_id"],
                "baseline_review_window": {
                    "start": baseline_contract["review_window_start"],
                    "end": baseline_contract["review_window_end"],
                },
                "candidate_review_window": {
                    "start": candidate_contract["review_window_start"],
                    "end": candidate_contract["review_window_end"],
                },
                "metric_definitions_verbatim": baseline_contract[
                    "metric_definitions"
                ],
                "causal_claim_allowed": False,
            }
        )
    return result


def _validate_status(
    *,
    status: ValidationStatus,
    validation_rows: list[dict[str, object]],
    baseline_groups: set[str],
    missing_evidence: list[str],
) -> list[str]:
    if status not in {
        "NEEDS_MORE_EVIDENCE",
        "INCONCLUSIVE",
        "VALIDATED",
        "REGRESSED",
        "CONTESTED",
    }:
        raise LearningRegressionError("learning_validation_status_invalid")
    relations_by_group: dict[str, set[str]] = {}
    for row in validation_rows:
        key = cast(str, row["independence_key"])
        relation = cast(str, row["relation"])
        if relation in {"supports", "contradicts"}:
            relations_by_group.setdefault(key, set()).add(relation)
    new_groups = {
        key: relations
        for key, relations in relations_by_group.items()
        if key not in baseline_groups
    }
    support = any("supports" in relations for relations in new_groups.values())
    contradict = any("contradicts" in relations for relations in new_groups.values())

    if status == "VALIDATED" and (not support or contradict):
        raise LearningRegressionError("learning_validation_validated_evidence_invalid")
    if status == "REGRESSED" and (not contradict or support):
        raise LearningRegressionError("learning_validation_regressed_evidence_invalid")
    if status == "CONTESTED" and not (support and contradict):
        raise LearningRegressionError("learning_validation_contested_evidence_invalid")
    if status == "NEEDS_MORE_EVIDENCE" and (support or contradict):
        raise LearningRegressionError("learning_validation_more_evidence_status_invalid")
    if status in {"NEEDS_MORE_EVIDENCE", "INCONCLUSIVE"} and not missing_evidence:
        raise LearningRegressionError("learning_validation_missing_evidence_required")
    return sorted(new_groups)


async def create_learning_validation(
    session: AsyncSession,
    *,
    learning_application_id: UUID,
    validation_status: ValidationStatus,
    signal_relations: dict[UUID, EvidenceRelation],
    metric_comparisons: list[MetricComparisonInput],
    alternative_explanations: list[str],
    missing_evidence: list[str],
) -> LearningValidationResult:
    """Create one immutable validation version; never mutate Customer Truth."""

    seed_application = await session.get(
        LearningApplication,
        learning_application_id,
    )
    if seed_application is None:
        raise LearningRegressionError("learning_application_not_found")
    project = await session.scalar(
        select(Project)
        .where(Project.id == seed_application.project_id)
        .with_for_update()
    )
    if project is None:
        raise LearningRegressionError("learning_validation_project_not_found")
    application, candidate = await _application_context(
        session,
        application_id=learning_application_id,
    )

    baseline_relations = _baseline_relations(application)
    baseline_rows, baseline_groups, baseline_metrics = await _load_signal_set(
        session,
        application=application,
        signal_relations=baseline_relations,
    )
    validation_rows, _validation_groups, validation_metrics = await _load_signal_set(
        session,
        application=application,
        signal_relations=signal_relations,
        not_before=application.applied_at,
    )
    alternatives = _clean_strings(
        alternative_explanations,
        "learning_validation_alternative_duplicate",
    )
    missing = _clean_strings(
        missing_evidence,
        "learning_validation_missing_duplicate",
    )
    independent_groups = _validate_status(
        status=validation_status,
        validation_rows=validation_rows,
        baseline_groups=baseline_groups,
        missing_evidence=missing,
    )
    comparisons = await _metric_comparisons(
        session,
        inputs=metric_comparisons,
        baseline_metrics=baseline_metrics,
        candidate_metrics=validation_metrics,
    )
    if (
        validation_status in {"VALIDATED", "REGRESSED"}
        and not alternatives
    ):
        raise LearningRegressionError(
            "learning_validation_alternative_explanation_required"
        )
    target_snapshot = await _target_snapshot(
        session,
        application=application,
        lock=True,
    )
    fingerprint_payload: dict[str, object] = {
        "application_id": str(application.id),
        "candidate_id": str(candidate.id),
        "candidate_version": candidate.version,
        "target_type": application.target_type,
        "resulting_target_id": (
            str(application.resulting_target_id)
            if application.resulting_target_id is not None
            else None
        ),
        "target_snapshot": target_snapshot,
        "baseline_signals": baseline_rows,
        "validation_signals": validation_rows,
        "independent_evidence_groups": independent_groups,
        "metric_comparisons": comparisons,
        "frozen_scope": application.frozen_scope_json,
        "validation_status": validation_status,
        "alternative_explanations": alternatives,
        "missing_evidence": missing,
        "minimum_evidence_interpreted": False,
        "causal_claim_allowed": False,
    }
    fingerprint = _hash(fingerprint_payload)
    existing = await session.scalar(
        select(LearningValidation).where(
            LearningValidation.learning_application_id == application.id,
            LearningValidation.validation_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return LearningValidationResult(validation=existing, replayed=True)

    next_version = int(
        await session.scalar(
            select(func.coalesce(func.max(LearningValidation.version), 0) + 1)
            .where(LearningValidation.learning_application_id == application.id)
        )
        or 1
    )
    validation = LearningValidation(
        project_id=application.project_id,
        learning_application_id=application.id,
        learning_candidate_id=candidate.id,
        candidate_version=candidate.version,
        version=next_version,
        validation_fingerprint=fingerprint,
        validation_status=validation_status,
        target_type=application.target_type,
        resulting_target_id=application.resulting_target_id,
        target_snapshot_json=target_snapshot,
        baseline_signal_refs_json=baseline_rows,
        validation_signal_refs_json=validation_rows,
        independent_evidence_groups_json=independent_groups,
        metric_comparisons_json=comparisons,
        frozen_scope_json=dict(application.frozen_scope_json),
        alternative_explanations_json=alternatives,
        missing_evidence_json=missing,
        evaluated_at=utc_now(),
    )
    session.add(validation)
    await session.flush()
    return LearningValidationResult(validation=validation, replayed=False)


async def _validation_snapshot_hash(
    session: AsyncSession,
    validation: LearningValidation,
) -> str:
    snapshot_hash = await session.scalar(
        select(func.learning_validation_snapshot_hash(validation.id))
    )
    if not isinstance(snapshot_hash, str) or len(snapshot_hash) != 64:
        raise LearningRegressionError(
            "learning_validation_snapshot_hash_invalid"
        )
    return snapshot_hash


def _reviewed_target_status(
    validation: LearningValidation,
) -> str | None:
    snapshot = _dict(
        validation.target_snapshot_json,
        "learning_resolution_target_snapshot_invalid",
    )
    current = snapshot.get("current_target")
    if current is None:
        return None
    current_target = _dict(
        current,
        "learning_resolution_target_snapshot_invalid",
    )
    status = current_target.get("status")
    if not isinstance(status, str) or not status.strip():
        raise LearningRegressionError(
            "learning_resolution_target_snapshot_invalid"
        )
    return status.strip()


def _validate_resolution_decision(
    validation: LearningValidation,
    decision: ResolutionDecision,
    target_status: str | None,
) -> None:
    if decision not in {
        "PROMOTE",
        "KEEP",
        "ROLLBACK",
        "REJECT",
        "REQUEST_MORE_EVIDENCE",
        "ARCHIVE_CANDIDATE",
    }:
        raise LearningRegressionError("learning_resolution_decision_invalid")
    if (
        validation.target_type == "no_map_change"
        and decision in {"PROMOTE", "ROLLBACK", "REJECT"}
    ):
        raise LearningRegressionError(
            "learning_resolution_no_map_mutation_invalid"
        )

    current_status = _reviewed_target_status(validation)

    if decision == "PROMOTE":
        if validation.validation_status != "VALIDATED":
            raise LearningRegressionError(
                "learning_resolution_promote_validation_invalid"
            )
        if target_status not in {"TESTING", "SUPPORTED"}:
            raise LearningRegressionError(
                "learning_resolution_promote_status_invalid"
            )
        if current_status == target_status:
            raise LearningRegressionError(
                "learning_resolution_target_status_noop"
            )
        if validation.target_type == "need_hypothesis":
            allowed = {
                ("PROPOSED", "TESTING"),
                ("TESTING", "SUPPORTED"),
            }
            if (current_status, target_status) not in allowed:
                raise LearningRegressionError(
                    "learning_resolution_need_transition_invalid"
                )
        elif target_status == "TESTING" and current_status == "SUPPORTED":
            raise LearningRegressionError(
                "learning_resolution_insight_transition_invalid"
            )
        return

    if decision in {"ROLLBACK", "REJECT"}:
        if validation.validation_status != "REGRESSED":
            raise LearningRegressionError(
                "learning_resolution_rollback_validation_invalid"
            )
        if target_status not in {"REJECTED", "INSUFFICIENT_EVIDENCE"}:
            raise LearningRegressionError(
                "learning_resolution_rollback_status_invalid"
            )
        if current_status == target_status:
            raise LearningRegressionError(
                "learning_resolution_target_status_noop"
            )
        if (
            validation.target_type == "need_hypothesis"
            and target_status == "REJECTED"
            and current_status != "TESTING"
        ):
            raise LearningRegressionError(
                "learning_resolution_need_transition_invalid"
            )
        return

    if target_status is not None:
        raise LearningRegressionError("learning_resolution_target_status_unexpected")


async def review_learning_validation(
    session: AsyncSession,
    *,
    learning_validation_id: UUID,
    decision: ResolutionDecision,
    target_status: str | None,
    reviewed_by: str,
    reason: str,
) -> LearningResolutionResult:
    """Record human resolution only; Customer Truth remains unchanged."""

    actor = _text(reviewed_by, "learning_resolution_reviewer_required")
    rationale = _text(reason, "learning_resolution_reason_required")
    seed_validation = await session.get(
        LearningValidation,
        learning_validation_id,
    )
    if seed_validation is None:
        raise LearningRegressionError("learning_validation_not_found")

    # Exact retries must remain replayable even after the reviewed resolution
    # has already changed target/candidate state.
    existing = await session.scalar(
        select(LearningResolution).where(
            LearningResolution.learning_validation_id == seed_validation.id
        )
    )
    if existing is not None:
        snapshot_hash = await _validation_snapshot_hash(
            session,
            seed_validation,
        )
        if (
            existing.project_id != seed_validation.project_id
            or existing.learning_application_id
            != seed_validation.learning_application_id
            or existing.validation_version != seed_validation.version
            or existing.decision != decision
            or existing.target_status != target_status
            or existing.reviewed_by != actor
            or existing.reason != rationale
            or existing.validation_snapshot_hash != snapshot_hash
            or existing.target_snapshot_json
            != seed_validation.target_snapshot_json
        ):
            raise LearningRegressionError("learning_resolution_replay_conflict")
        return LearningResolutionResult(
            resolution=existing,
            replayed=True,
        )

    project = await session.scalar(
        select(Project)
        .where(Project.id == seed_validation.project_id)
        .with_for_update()
    )
    if project is None:
        raise LearningRegressionError("learning_resolution_project_not_found")
    validation = await session.scalar(
        select(LearningValidation)
        .where(LearningValidation.id == learning_validation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if validation is None:
        raise LearningRegressionError("learning_validation_not_found")
    latest_version = await session.scalar(
        select(func.max(LearningValidation.version)).where(
            LearningValidation.learning_application_id
            == validation.learning_application_id
        )
    )
    if latest_version != validation.version:
        raise LearningRegressionError("learning_validation_stale")
    _validate_resolution_decision(validation, decision, target_status)

    application, _candidate = await _application_context(
        session,
        application_id=validation.learning_application_id,
    )
    current_target = await _target_snapshot(
        session,
        application=application,
        lock=True,
    )
    if current_target != validation.target_snapshot_json:
        raise LearningRegressionError("learning_resolution_target_stale")

    existing = await session.scalar(
        select(LearningResolution).where(
            LearningResolution.learning_validation_id == validation.id
        )
    )
    snapshot_hash = await _validation_snapshot_hash(session, validation)
    if existing is not None:
        if (
            existing.project_id != validation.project_id
            or existing.learning_application_id
            != validation.learning_application_id
            or existing.validation_version != validation.version
            or existing.decision != decision
            or existing.target_status != target_status
            or existing.reviewed_by != actor
            or existing.reason != rationale
            or existing.validation_snapshot_hash != snapshot_hash
            or existing.target_snapshot_json != current_target
        ):
            raise LearningRegressionError("learning_resolution_replay_conflict")
        return LearningResolutionResult(
            resolution=existing,
            replayed=True,
        )

    resolution = LearningResolution(
        project_id=validation.project_id,
        learning_validation_id=validation.id,
        learning_application_id=validation.learning_application_id,
        validation_version=validation.version,
        decision=decision,
        target_status=target_status,
        reviewed_by=actor,
        reason=rationale,
        validation_snapshot_hash=snapshot_hash,
        target_snapshot_json=current_target,
        reviewed_at=utc_now(),
    )
    session.add(resolution)
    await session.flush()
    return LearningResolutionResult(resolution=resolution, replayed=False)


def _validation_signal_relations(
    validation: LearningValidation,
) -> dict[UUID, EvidenceRelation]:
    result: dict[UUID, EvidenceRelation] = {}
    for raw in validation.validation_signal_refs_json:
        row = _dict(raw, "learning_resolution_validation_signal_invalid")
        signal_id = _uuid(
            row.get("signal_id"),
            "learning_resolution_validation_signal_invalid",
        )
        relation = row.get("relation")
        if relation not in {"supports", "contradicts", "context"}:
            raise LearningRegressionError(
                "learning_resolution_validation_signal_invalid"
            )
        typed_relation = cast(EvidenceRelation, relation)
        previous = result.get(signal_id)
        if previous is not None and previous != typed_relation:
            raise LearningRegressionError(
                "learning_resolution_validation_signal_conflict"
            )
        result[signal_id] = typed_relation
    return result


async def _need_evidence_refs(
    session: AsyncSession,
    *,
    need_id: UUID,
) -> tuple[list[str], list[str]]:
    rows = list(
        (
            await session.scalars(
                select(NeedHypothesisSignal)
                .where(NeedHypothesisSignal.need_hypothesis_id == need_id)
                .order_by(
                    NeedHypothesisSignal.relation,
                    NeedHypothesisSignal.signal_id,
                )
            )
        ).all()
    )
    supports = [
        str(row.signal_id) for row in rows if row.relation == "supports"
    ]
    contradicts = [
        str(row.signal_id) for row in rows if row.relation == "contradicts"
    ]
    return supports, contradicts


async def _review_need_hypothesis(
    session: AsyncSession,
    *,
    need_id: UUID,
    status: str,
    reviewed_by: str,
    reason: str,
) -> NeedHypothesis:
    if status not in {
        "TESTING",
        "SUPPORTED",
        "REJECTED",
        "INSUFFICIENT_EVIDENCE",
    }:
        raise LearningRegressionError("learning_resolution_need_status_invalid")
    need = await session.scalar(
        select(NeedHypothesis)
        .where(NeedHypothesis.id == need_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if need is None:
        raise LearningRegressionError("learning_resolution_need_not_found")

    existing = await session.scalar(
        select(NeedHypothesisReview)
        .where(
            NeedHypothesisReview.need_hypothesis_id == need.id,
            NeedHypothesisReview.version == need.version - 1,
            NeedHypothesisReview.status == status,
            NeedHypothesisReview.reviewed_by == reviewed_by,
            NeedHypothesisReview.reason == reason,
        )
        .order_by(NeedHypothesisReview.reviewed_at.desc())
        .limit(1)
    )
    if existing is not None and need.status == status:
        return need

    supports, contradicts = await _need_evidence_refs(session, need_id=need.id)
    cache: dict[UUID, str] = {}
    support_groups: set[str] = set()
    contradict_groups: set[str] = set()
    for raw_id in supports:
        signal = await session.get(Signal, UUID(raw_id))
        if signal is None or signal.project_id != need.project_id:
            raise LearningRegressionError("learning_resolution_need_signal_stale")
        support_groups.add(await signal_independence_key(session, signal, cache))
    for raw_id in contradicts:
        signal = await session.get(Signal, UUID(raw_id))
        if signal is None or signal.project_id != need.project_id:
            raise LearningRegressionError("learning_resolution_need_signal_stale")
        contradict_groups.add(await signal_independence_key(session, signal, cache))

    if status == "SUPPORTED" and not support_groups:
        raise LearningRegressionError("learning_resolution_need_support_required")
    if status == "SUPPORTED" and contradict_groups:
        raise LearningRegressionError("learning_resolution_need_contested")
    if status == "REJECTED" and not contradict_groups:
        raise LearningRegressionError("learning_resolution_need_contradiction_required")

    reviewed_version = need.version
    session.add(
        NeedHypothesisReview(
            need_hypothesis_id=need.id,
            version=reviewed_version,
            status=status,
            reviewed_by=reviewed_by,
            reason=reason,
            support_signal_refs_json=supports,
            contradict_signal_refs_json=contradicts,
            reviewed_at=utc_now(),
        )
    )
    need.status = status
    need.reviewed_by = reviewed_by
    need.reviewed_at = utc_now()
    need.review_reason = reason
    need.version = reviewed_version + 1
    await session.flush()
    return need


async def apply_learning_resolution(
    session: AsyncSession,
    *,
    learning_resolution_id: UUID,
    applied_by: str,
) -> LearningResolutionApplicationResult:
    """Apply one reviewed resolution using compensating state, never deletion."""

    actor = _text(applied_by, "learning_resolution_apply_actor_required")
    resolution = await session.get(LearningResolution, learning_resolution_id)
    if resolution is None:
        raise LearningRegressionError("learning_resolution_not_found")
    existing = await session.scalar(
        select(LearningResolutionApplication).where(
            LearningResolutionApplication.learning_resolution_id == resolution.id
        )
    )
    if existing is not None:
        return LearningResolutionApplicationResult(
            application=existing,
            replayed=True,
            customer_map_snapshot_artifact_id=(
                existing.customer_map_snapshot_artifact_id
            ),
            change_report=existing.change_report_json,
        )

    project = await session.scalar(
        select(Project)
        .where(Project.id == resolution.project_id)
        .with_for_update()
    )
    if project is None:
        raise LearningRegressionError("learning_resolution_project_not_found")

    validation = await session.scalar(
        select(LearningValidation)
        .where(LearningValidation.id == resolution.learning_validation_id)
        .with_for_update()
    )
    if validation is None:
        raise LearningRegressionError("learning_validation_not_found")
    latest_version = await session.scalar(
        select(func.max(LearningValidation.version)).where(
            LearningValidation.learning_application_id
            == validation.learning_application_id
        )
    )
    if latest_version != validation.version:
        raise LearningRegressionError("learning_resolution_validation_stale")
    if (
        resolution.validation_version != validation.version
        or resolution.validation_snapshot_hash
        != await _validation_snapshot_hash(session, validation)
    ):
        raise LearningRegressionError("learning_resolution_snapshot_stale")

    application, candidate = await _application_context(
        session,
        application_id=validation.learning_application_id,
    )
    current_target = await _target_snapshot(
        session,
        application=application,
        lock=True,
    )
    if (
        current_target != validation.target_snapshot_json
        or current_target != resolution.target_snapshot_json
    ):
        raise LearningRegressionError("learning_resolution_target_stale")

    # Re-check after project/validation/target locks for concurrent exact replay.
    existing = await session.scalar(
        select(LearningResolutionApplication).where(
            LearningResolutionApplication.learning_resolution_id == resolution.id
        )
    )
    if existing is not None:
        return LearningResolutionApplicationResult(
            application=existing,
            replayed=True,
            customer_map_snapshot_artifact_id=(
                existing.customer_map_snapshot_artifact_id
            ),
            change_report=existing.change_report_json,
        )

    if resolution.decision in {"KEEP", "REQUEST_MORE_EVIDENCE"}:
        receipt = LearningResolutionApplication(
            project_id=resolution.project_id,
            learning_resolution_id=resolution.id,
            learning_validation_id=validation.id,
            learning_application_id=application.id,
            decision=resolution.decision,
            target_type=application.target_type,
            resulting_target_id=application.resulting_target_id,
            resulting_status=None,
            applied_action="no_map_change",
            before_target_snapshot_json=current_target,
            after_target_snapshot_json=current_target,
            before_state_hash=None,
            after_state_hash=None,
            customer_map_snapshot_artifact_id=None,
            change_report_json=None,
            applied_by=actor,
            applied_at=utc_now(),
        )
        session.add(receipt)
        await session.flush()
        return LearningResolutionApplicationResult(
            application=receipt,
            replayed=False,
            customer_map_snapshot_artifact_id=None,
            change_report=None,
        )

    if resolution.decision == "ARCHIVE_CANDIDATE":
        locked_candidate = await session.scalar(
            select(LearningCandidate)
            .where(LearningCandidate.id == candidate.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if locked_candidate is None or locked_candidate.status != "OPEN":
            raise LearningRegressionError("learning_resolution_candidate_not_open")
        locked_candidate.status = "ARCHIVED"
        await session.flush()
        receipt = LearningResolutionApplication(
            project_id=resolution.project_id,
            learning_resolution_id=resolution.id,
            learning_validation_id=validation.id,
            learning_application_id=application.id,
            decision=resolution.decision,
            target_type=application.target_type,
            resulting_target_id=application.resulting_target_id,
            resulting_status="ARCHIVED",
            applied_action="archive_candidate",
            before_target_snapshot_json=current_target,
            after_target_snapshot_json=current_target,
            before_state_hash=None,
            after_state_hash=None,
            customer_map_snapshot_artifact_id=None,
            change_report_json=None,
            applied_by=actor,
            applied_at=utc_now(),
        )
        session.add(receipt)
        await session.flush()
        return LearningResolutionApplicationResult(
            application=receipt,
            replayed=False,
            customer_map_snapshot_artifact_id=None,
            change_report=None,
        )

    if resolution.target_status is None:
        raise LearningRegressionError("learning_resolution_target_status_required")
    if application.customer_map_snapshot_artifact_id is None:
        raise LearningRegressionError("learning_resolution_map_lineage_missing")
    prior_map = await session.get(
        Artifact,
        application.customer_map_snapshot_artifact_id,
    )
    if prior_map is None or prior_map.artifact_type != "customer_map_snapshot":
        raise LearningRegressionError("learning_resolution_map_lineage_invalid")

    before_refresh = await refresh_customer_map_snapshot_artifact(
        session,
        run_id=prior_map.run_id,
        step_run_id=None,
    )
    before_target = current_target

    validation_relations = _validation_signal_relations(validation)

    if application.target_type == "need_hypothesis":
        if application.resulting_target_id is None:
            raise LearningRegressionError("learning_resolution_need_target_missing")
        need_target = await session.get(
            NeedHypothesis,
            application.resulting_target_id,
        )
        if (
            need_target is None
            or need_target.project_id != application.project_id
        ):
            raise LearningRegressionError("learning_resolution_need_not_found")
        for signal_id, relation in validation_relations.items():
            if relation not in {"supports", "contradicts"}:
                continue
            try:
                await _ensure_need_signal_link(
                    session,
                    need=need_target,
                    signal_id=signal_id,
                    relation=relation,
                )
            except LearningApplicationError as exc:
                raise LearningRegressionError(
                    f"learning_resolution_{exc.code}"
                ) from exc
        need = await _review_need_hypothesis(
            session,
            need_id=application.resulting_target_id,
            status=resolution.target_status,
            reviewed_by=resolution.reviewed_by,
            reason=resolution.reason,
        )
        resulting_target_id = need.id
        action = "review_need"
    elif application.target_type in {"customer_insight", "new_customer_insight"}:
        if application.resulting_target_id is None:
            raise LearningRegressionError("learning_resolution_insight_target_missing")
        try:
            for signal_id, relation in validation_relations.items():
                await link_customer_insight_signal(
                    session,
                    customer_insight_id=application.resulting_target_id,
                    signal_id=signal_id,
                    relation=relation,
                )
            insight = await review_customer_insight(
                session,
                customer_insight_id=application.resulting_target_id,
                status=cast(
                    Literal[
                        "SUPPORTED",
                        "REJECTED",
                        "INSUFFICIENT_EVIDENCE",
                        "TESTING",
                    ],
                    resolution.target_status,
                ),
                reviewed_by=resolution.reviewed_by,
                reason=resolution.reason,
            )
        except CustomerInsightError as exc:
            raise LearningRegressionError(
                f"learning_resolution_{exc.code}"
            ) from exc
        resulting_target_id = insight.id
        action = "review_insight"
    else:
        raise LearningRegressionError("learning_resolution_truth_target_invalid")

    after_target = await _target_snapshot(
        session,
        application=application,
        lock=False,
    )
    after_refresh = await refresh_customer_map_snapshot_artifact(
        session,
        run_id=prior_map.run_id,
        step_run_id=None,
    )
    receipt = LearningResolutionApplication(
        project_id=resolution.project_id,
        learning_resolution_id=resolution.id,
        learning_validation_id=validation.id,
        learning_application_id=application.id,
        decision=resolution.decision,
        target_type=application.target_type,
        resulting_target_id=resulting_target_id,
        resulting_status=resolution.target_status,
        applied_action=action,
        before_target_snapshot_json=before_target,
        after_target_snapshot_json=after_target,
        before_state_hash=before_refresh.artifact.content_hash,
        after_state_hash=after_refresh.artifact.content_hash,
        customer_map_snapshot_artifact_id=after_refresh.artifact.id,
        change_report_json=after_refresh.change_report,
        applied_by=actor,
        applied_at=utc_now(),
    )
    session.add(receipt)
    await session.flush()
    return LearningResolutionApplicationResult(
        application=receipt,
        replayed=False,
        customer_map_snapshot_artifact_id=after_refresh.artifact.id,
        change_report=after_refresh.change_report,
    )


__all__ = [
    "LearningRegressionError",
    "LearningResolutionApplicationResult",
    "LearningResolutionResult",
    "LearningValidationResult",
    "MetricComparisonInput",
    "apply_learning_resolution",
    "create_learning_validation",
    "review_learning_validation",
]