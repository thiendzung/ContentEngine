"""LL-01A factual performance Signals from PM-01 observations.

This module deliberately stops before interpretation. It materializes a durable
MOTGU Signal from normalized post-publication metrics while preserving exact
publication/experiment lineage and experiment-scoped evidence independence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import ContentExperiment, Signal
from app.modules.harness.models import Artifact
from app.modules.measurement.models import (
    ContentPerformanceObservation,
    PerformanceMetric,
    PerformanceSnapshot,
)
from app.modules.measurement.service import MeasurementError, get_measurement_identity
from app.modules.publishing.models import PublishedContent, PublishEvent

_SIGNAL_SCHEMA_VERSION = 1
_SIGNAL_EXTERNAL_PREFIX = "content_performance_observation"
_SIGNAL_CONTEXT = (
    "Post-publication normalized performance facts; no causal or customer-truth "
    "interpretation."
)


class PerformanceSignalError(ValueError):
    """Stable fail-closed LL-01A error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PerformanceSignalResult:
    signal: Signal | None
    replayed: bool
    skipped_reason: str | None = None


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
        raise PerformanceSignalError(code)
    return {str(key): item for key, item in value.items()}


def _strings(value: object, code: str) -> list[str]:
    if not isinstance(value, list):
        raise PerformanceSignalError(code)
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PerformanceSignalError(code)
        result.append(item.strip())
    return result


def _uuid(value: object, code: str) -> UUID:
    if not isinstance(value, str):
        raise PerformanceSignalError(code)
    try:
        return UUID(value)
    except ValueError as exc:
        raise PerformanceSignalError(code) from exc


def _optional_uuid(value: object, code: str) -> UUID | None:
    if value is None:
        return None
    return _uuid(value, code)


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PerformanceSignalError(code)
    return value.strip()


def _aware(value: datetime | None, code: str) -> datetime:
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        raise PerformanceSignalError(code)
    return value


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


async def _load_metrics(
    session: AsyncSession,
    *,
    observation: ContentPerformanceObservation,
) -> tuple[tuple[PerformanceMetric, ...], tuple[PerformanceSnapshot, ...]]:
    metric_ids: list[UUID] = []
    for raw_ref in observation.metric_refs_json:
        metric_ids.append(_uuid(raw_ref, "performance_signal_metric_ref_invalid"))
    if len(set(metric_ids)) != len(metric_ids):
        raise PerformanceSignalError("performance_signal_metric_ref_duplicate")
    if not metric_ids:
        if observation.data_status != "INSUFFICIENT_DATA":
            raise PerformanceSignalError("performance_signal_metrics_required")
        return (), ()

    metrics: list[PerformanceMetric] = []
    snapshots: dict[UUID, PerformanceSnapshot] = {}
    for metric_id in metric_ids:
        metric = await session.get(PerformanceMetric, metric_id)
        if metric is None:
            raise PerformanceSignalError("performance_signal_metric_not_found")
        if (
            metric.published_content_id != observation.published_content_id
            or metric.content_version_id != observation.content_version_id
        ):
            raise PerformanceSignalError("performance_signal_metric_identity_mismatch")

        snapshot = await session.get(PerformanceSnapshot, metric.snapshot_id)
        if snapshot is None:
            raise PerformanceSignalError("performance_signal_snapshot_not_found")
        if (
            snapshot.published_content_id != observation.published_content_id
            or snapshot.content_version_id != observation.content_version_id
            or snapshot.provider != metric.provider
            or not snapshot.window_start <= metric.metric_date <= snapshot.window_end
        ):
            raise PerformanceSignalError("performance_signal_snapshot_identity_mismatch")
        metrics.append(metric)
        snapshots[snapshot.id] = snapshot

    metrics.sort(
        key=lambda row: (
            row.metric_date,
            row.provider,
            row.metric_name,
            str(row.id),
        )
    )
    ordered_snapshots = sorted(
        snapshots.values(),
        key=lambda row: (
            row.window_start,
            row.window_end,
            row.provider,
            str(row.id),
        ),
    )
    return tuple(metrics), tuple(ordered_snapshots)


def _metric_payload(metric: PerformanceMetric) -> dict[str, object]:
    return {
        "id": str(metric.id),
        "snapshot_id": str(metric.snapshot_id),
        "provider": metric.provider,
        "metric_date": metric.metric_date.isoformat(),
        "metric_name": metric.metric_name,
        "metric_value": _decimal_text(metric.metric_value),
    }


def _window_payload(snapshot: PerformanceSnapshot) -> dict[str, object]:
    return {
        "snapshot_id": str(snapshot.id),
        "provider": snapshot.provider,
        "window_start": snapshot.window_start.isoformat(),
        "window_end": snapshot.window_end.isoformat(),
    }


def _observed_text(
    *,
    observation_id: UUID,
    metrics: tuple[PerformanceMetric, ...],
) -> str:
    if not metrics:
        return (
            "Observed no normalized metric rows attached to performance observation "
            f"{observation_id}."
        )
    facts = "; ".join(
        (
            f"{metric.provider}:{metric.metric_name}="
            f"{_decimal_text(metric.metric_value)}@{metric.metric_date.isoformat()}"
        )
        for metric in metrics
    )
    return f"Observed normalized post-publication metrics: {facts}."


def _replay_matches(
    existing: Signal,
    *,
    project_id: UUID,
    observed_text: str,
    source_url: str,
    external_id: str,
    locale: str,
    captured_at: datetime,
    observed_at: datetime,
    fingerprint: str,
    independence_group: str,
    provenance: dict[str, object],
) -> bool:
    return (
        existing.project_id == project_id
        and existing.source_kind == "MOTGU"
        and existing.scope == "motgu_site"
        and existing.observed_text == observed_text
        and existing.source_url == source_url
        and existing.external_id == external_id
        and existing.locale == locale
        and existing.context == _SIGNAL_CONTEXT
        and existing.captured_at == captured_at
        and existing.observed_at == observed_at
        and existing.fingerprint == fingerprint
        and existing.duplicate_of_id is None
        and existing.independence_group == independence_group
        and existing.provenance_json == provenance
    )


async def materialize_performance_signal(
    session: AsyncSession,
    *,
    observation_id: UUID,
) -> PerformanceSignalResult:
    """Materialize one idempotent factual Signal from a PM-01 observation.

    The source observation statement is intentionally not copied into the Signal:
    it is an interpretation layer. Only normalized metric facts and exact lineage
    are carried forward.
    """

    observation = await session.get(ContentPerformanceObservation, observation_id)
    if observation is None:
        raise PerformanceSignalError("performance_signal_observation_not_found")

    observed_at = _aware(
        observation.observed_at,
        "performance_signal_observed_at_invalid",
    )
    captured_at = _aware(
        observation.created_at,
        "performance_signal_captured_at_invalid",
    )

    try:
        identity = await get_measurement_identity(
            session,
            published_content_id=observation.published_content_id,
            content_version_id=observation.content_version_id,
        )
    except MeasurementError as exc:
        raise PerformanceSignalError(
            f"performance_signal_{exc.code}"
        ) from exc

    published = _dict(
        identity.get("published_content"),
        "performance_signal_published_identity_invalid",
    )
    content = _dict(
        identity.get("content"),
        "performance_signal_content_identity_invalid",
    )
    customer = _dict(
        identity.get("customer"),
        "performance_signal_customer_identity_invalid",
    )
    opportunity = _dict(
        identity.get("opportunity"),
        "performance_signal_opportunity_identity_invalid",
    )
    experiment_identity = _dict(
        identity.get("experiment"),
        "performance_signal_experiment_identity_invalid",
    )
    event_identity = _dict(
        identity.get("publish_event"),
        "performance_signal_publish_event_identity_invalid",
    )

    mapping = await session.get(PublishedContent, observation.published_content_id)
    if mapping is None:
        raise PerformanceSignalError("performance_signal_published_content_missing")
    if _uuid(published.get("id"), "performance_signal_published_identity_invalid") != mapping.id:
        raise PerformanceSignalError("performance_signal_published_identity_mismatch")

    content_version_id = _uuid(
        content.get("content_version_id"),
        "performance_signal_content_version_invalid",
    )
    if content_version_id != observation.content_version_id:
        raise PerformanceSignalError("performance_signal_content_version_mismatch")

    content_item_id = _uuid(
        content.get("content_item_id"),
        "performance_signal_content_item_invalid",
    )
    content_case_id = _uuid(
        content.get("content_case_id"),
        "performance_signal_content_case_invalid",
    )
    locale_variant_id = _uuid(
        content.get("locale_variant_id"),
        "performance_signal_locale_variant_invalid",
    )
    _text(content.get("locale"), "performance_signal_locale_invalid")

    need_id = _uuid(
        customer.get("need_hypothesis_id"),
        "performance_signal_need_invalid",
    )
    opportunity_id = _uuid(
        opportunity.get("id"),
        "performance_signal_opportunity_invalid",
    )
    experiment_id = _uuid(
        experiment_identity.get("id"),
        "performance_signal_experiment_invalid",
    )
    experiment = await session.get(ContentExperiment, experiment_id)
    if experiment is None:
        raise PerformanceSignalError("performance_signal_experiment_not_found")
    if (
        experiment.project_id != mapping.project_id
        or experiment.published_content_id != mapping.id
        or experiment.content_item_id != content_item_id
        or experiment.content_version_id != content_version_id
        or experiment.content_opportunity_id != opportunity_id
        or experiment.need_hypothesis_id != need_id
    ):
        raise PerformanceSignalError("performance_signal_experiment_lineage_mismatch")
    review_start = _aware(
        experiment.review_window_start,
        "performance_signal_review_window_invalid",
    )
    review_end = _aware(
        experiment.review_window_end,
        "performance_signal_review_window_invalid",
    )
    if review_end <= review_start:
        raise PerformanceSignalError("performance_signal_review_window_invalid")

    publish_event_id = _uuid(
        event_identity.get("id"),
        "performance_signal_publish_event_invalid",
    )
    event = await session.get(PublishEvent, publish_event_id)
    if event is None:
        raise PerformanceSignalError("performance_signal_publish_event_not_found")
    if (
        event.published_content_id != mapping.id
        or event.content_version_id != content_version_id
        or event.content_experiment_id != experiment.id
        or event.external_status != "publish"
        or event.published_at is None
    ):
        raise PerformanceSignalError("performance_signal_publish_event_mismatch")
    source_url = _text(
        event.canonical_url,
        "performance_signal_canonical_url_required",
    )

    package = await session.get(Artifact, event.publish_package_artifact_id)
    if (
        package is None
        or package.artifact_type != "publish_package"
        or not isinstance(package.content_json, dict)
    ):
        raise PerformanceSignalError("performance_signal_publish_package_invalid")
    package_identity = _dict(
        package.content_json.get("identity"),
        "performance_signal_publish_package_identity_invalid",
    )
    package_content = _dict(
        package.content_json.get("content"),
        "performance_signal_publish_package_content_invalid",
    )
    frozen_locale = _text(
        package_content.get("locale"),
        "performance_signal_publish_package_locale_invalid",
    )
    frozen_expected = {
        "project_id": str(mapping.project_id),
        "content_case_id": str(content_case_id),
        "locale_variant_id": str(locale_variant_id),
        "content_item_id": str(content_item_id),
        "content_opportunity_id": str(opportunity_id),
        "need_hypothesis_id": str(need_id),
        "content_experiment_id": str(experiment.id),
    }
    for key, value in frozen_expected.items():
        if package_identity.get(key) != value:
            raise PerformanceSignalError(
                "performance_signal_publish_package_identity_mismatch"
            )

    frozen_need_version = package_identity.get("need_hypothesis_version")
    if not isinstance(frozen_need_version, int) or frozen_need_version < 1:
        raise PerformanceSignalError(
            "performance_signal_publish_package_need_version_invalid"
        )
    if experiment.hypothesis_version != frozen_need_version:
        raise PerformanceSignalError(
            "performance_signal_experiment_hypothesis_version_mismatch"
        )
    frozen_audience_id = _optional_uuid(
        package_identity.get("audience_hypothesis_id"),
        "performance_signal_publish_package_audience_invalid",
    )
    frozen_journey_stages = _strings(
        package_identity.get("journey_stages"),
        "performance_signal_publish_package_journey_invalid",
    )
    frozen_lens = package_identity.get("lens_selection")
    if frozen_lens is not None and not isinstance(frozen_lens, dict):
        raise PerformanceSignalError(
            "performance_signal_publish_package_lens_invalid"
        )
    frozen_lens_payload: dict[str, object] | None = (
        json.loads(json.dumps(frozen_lens, ensure_ascii=False, default=str))
        if isinstance(frozen_lens, dict)
        else None
    )

    metrics, snapshots = await _load_metrics(
        session,
        observation=observation,
    )

    if not metrics:
        return PerformanceSignalResult(
            signal=None,
            replayed=False,
            skipped_reason="no_normalized_metrics",
        )

    metric_payloads = [_metric_payload(metric) for metric in metrics]
    window_payloads = [_window_payload(snapshot) for snapshot in snapshots]
    observed_text = _observed_text(
        observation_id=observation.id,
        metrics=metrics,
    )
    external_id = f"{_SIGNAL_EXTERNAL_PREFIX}:{observation.id}"
    independence_group = f"experiment:{experiment.id}"

    provenance: dict[str, object] = {
        "schema_version": _SIGNAL_SCHEMA_VERSION,
        "kind": "content_performance_signal",
        "project_id": str(mapping.project_id),
        "content_performance_observation": {
            "id": str(observation.id),
            "observed_at": observed_at.isoformat(),
            "interpretation_fields_excluded": [
                "statement",
                "observation_type",
                "data_status",
            ],
        },
        "publication": {
            "published_content_id": str(mapping.id),
            "publish_event_id": str(event.id),
            "target": mapping.target,
            "canonical_url": source_url,
            "published_at": event.published_at.isoformat(),
        },
        "content": {
            "content_version_id": str(content_version_id),
            "content_item_id": str(content_item_id),
            "content_case_id": str(content_case_id),
            "locale_variant_id": str(locale_variant_id),
            "locale": frozen_locale,
        },
        "customer": {
            "audience_hypothesis_id": (
                str(frozen_audience_id)
                if frozen_audience_id is not None
                else None
            ),
            "need_hypothesis_id": str(need_id),
            "need_hypothesis_version": frozen_need_version,
            "journey_stages": frozen_journey_stages,
            "identity_source": "publish_package",
        },
        "opportunity": {
            "id": str(opportunity_id),
        },
        "lens_selection": frozen_lens_payload,
        "experiment": {
            "id": str(experiment.id),
            "review_window_start": review_start.isoformat(),
            "review_window_end": review_end.isoformat(),
            "independence_group": independence_group,
        },
        "measurement_windows": window_payloads,
        "metrics": metric_payloads,
    }
    fingerprint = _hash(
        {
            "external_id": external_id,
            "observed_text": observed_text,
            "provenance": provenance,
        }
    )
    signal_id = uuid5(
        NAMESPACE_URL,
        f"contentengine:{_SIGNAL_EXTERNAL_PREFIX}:{observation.id}",
    )

    existing_by_id = await session.get(Signal, signal_id)
    existing_by_external = tuple(
        (
            await session.scalars(
                select(Signal)
                .where(
                    Signal.project_id == mapping.project_id,
                    Signal.external_id == external_id,
                )
                .order_by(Signal.id)
            )
        ).all()
    )
    if len(existing_by_external) > 1:
        raise PerformanceSignalError("performance_signal_replay_ambiguous")
    existing = existing_by_id or (
        existing_by_external[0] if existing_by_external else None
    )
    if existing is not None:
        if existing.id != signal_id or not _replay_matches(
            existing,
            project_id=mapping.project_id,
            observed_text=observed_text,
            source_url=source_url,
            external_id=external_id,
            locale=frozen_locale,
            captured_at=captured_at,
            observed_at=observed_at,
            fingerprint=fingerprint,
            independence_group=independence_group,
            provenance=provenance,
        ):
            raise PerformanceSignalError("performance_signal_replay_conflict")
        return PerformanceSignalResult(signal=existing, replayed=True)

    signal = Signal(
        id=signal_id,
        project_id=mapping.project_id,
        source_kind="MOTGU",
        scope="motgu_site",
        observed_text=observed_text,
        source_url=source_url,
        external_id=external_id,
        locale=frozen_locale,
        context=_SIGNAL_CONTEXT,
        captured_at=captured_at,
        observed_at=observed_at,
        fingerprint=fingerprint,
        duplicate_of_id=None,
        independence_group=independence_group,
        provenance_json=provenance,
    )
    session.add(signal)
    await session.flush()
    return PerformanceSignalResult(signal=signal, replayed=False)


__all__ = [
    "PerformanceSignalError",
    "PerformanceSignalResult",
    "materialize_performance_signal",
]