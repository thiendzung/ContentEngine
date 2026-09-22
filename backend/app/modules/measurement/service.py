"""PM-01 measurement ingest and traceable publication identity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    AudienceHypothesis,
    ContentCase,
    ContentExperiment,
    ContentItem,
    ContentItemJourneyStage,
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
    NeedHypothesis,
)
from app.modules.harness.models import Artifact
from app.modules.measurement.models import (
    CORE_METRICS,
    ContentPerformanceObservation,
    PerformanceMetric,
    PerformanceSnapshot,
)
from app.modules.publishing.models import PublishedContent, PublishEvent

MeasurementProvider = Literal[
    "search_console",
    "analytics",
    "motgu_conversion",
    "rank_math",
]
DataStatus = Literal[
    "INSUFFICIENT_DATA",
    "EARLY_SIGNAL",
    "REPEATED_PATTERN",
    "LEARNING_CANDIDATE_READY",
]

_PROVIDER_METRICS: dict[str, frozenset[str]] = {
    "search_console": frozenset({"impressions", "clicks"}),
    "analytics": frozenset(
        {
            "sessions",
            "engaged_sessions",
            "artwork_transition",
            "visit_transition",
            "workshop_transition",
        }
    ),
    "motgu_conversion": frozenset({"inquiry"}),
    "rank_math": frozenset(),
}


class MeasurementError(ValueError):
    """Stable fail-closed PM-01 measurement error."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class MetricInput:
    metric_date: datetime
    metric_name: str
    metric_value: Decimal | int | float | str
    dimensions: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class MeasurementIngestResult:
    snapshot: PerformanceSnapshot
    metrics: tuple[PerformanceMetric, ...]
    replayed: bool


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, bool):
        raise MeasurementError("measurement_metric_value_invalid")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MeasurementError("measurement_metric_value_invalid") from exc
    if not parsed.is_finite() or parsed < 0:
        raise MeasurementError("measurement_metric_value_invalid")
    return parsed


def _normalized_metric_inputs(
    *,
    provider: str,
    window_start: datetime,
    window_end: datetime,
    metrics: list[MetricInput],
) -> list[tuple[datetime, str, Decimal, dict[str, object]]]:
    allowed = _PROVIDER_METRICS.get(provider)
    if allowed is None:
        raise MeasurementError("measurement_provider_invalid")
    normalized: list[tuple[datetime, str, Decimal, dict[str, object]]] = []
    identities: set[tuple[datetime, str]] = set()
    for metric in metrics:
        name = metric.metric_name.strip()
        if name not in CORE_METRICS or name not in allowed:
            raise MeasurementError("measurement_metric_provider_mismatch", name)
        if not window_start <= metric.metric_date <= window_end:
            raise MeasurementError("measurement_metric_outside_window", name)
        identity = (metric.metric_date, name)
        if identity in identities:
            raise MeasurementError("measurement_metric_duplicate", name)
        identities.add(identity)
        dimensions = metric.dimensions or {}
        if not isinstance(dimensions, dict):
            raise MeasurementError("measurement_dimensions_invalid", name)
        normalized.append(
            (
                metric.metric_date,
                name,
                _decimal(metric.metric_value),
                json.loads(json.dumps(dimensions, ensure_ascii=False, default=str)),
            )
        )
    normalized.sort(key=lambda row: (row[0], row[1]))
    return normalized


async def _measurement_mapping(
    session: AsyncSession,
    *,
    published_content_id: UUID,
    content_version_id: UUID,
    provider: str,
) -> tuple[PublishedContent, ContentVersion, ContentItem]:
    mapping = await session.get(PublishedContent, published_content_id)
    version = await session.get(ContentVersion, content_version_id)
    if mapping is None or version is None:
        raise MeasurementError("measurement_identity_missing")
    item = await session.get(ContentItem, mapping.content_item_id)
    if (
        item is None
        or version.content_item_id != item.id
        or mapping.current_content_version_id != version.id
    ):
        raise MeasurementError("measurement_identity_mismatch")
    if provider != "rank_math" and (
        mapping.external_status != "publish" or mapping.published_at is None
    ):
        raise MeasurementError("measurement_content_not_published")
    event = await session.scalar(
        select(PublishEvent)
        .where(
            PublishEvent.published_content_id == mapping.id,
            PublishEvent.content_version_id == version.id,
            PublishEvent.external_status == mapping.external_status,
        )
        .order_by(PublishEvent.created_at.desc(), PublishEvent.id.desc())
        .limit(1)
    )
    if event is None:
        raise MeasurementError("measurement_publish_event_missing")
    if provider != "rank_math" and event.external_status != "publish":
        raise MeasurementError("measurement_publish_event_not_public")
    return mapping, version, item


async def ingest_performance_snapshot(
    session: AsyncSession,
    *,
    published_content_id: UUID,
    content_version_id: UUID,
    provider: MeasurementProvider,
    window_start: datetime,
    window_end: datetime,
    raw_metrics: dict[str, object],
    metrics: list[MetricInput],
    imported_at: datetime | None = None,
) -> MeasurementIngestResult:
    """Persist one idempotent provider window plus normalized core metrics."""

    if window_end < window_start:
        raise MeasurementError("measurement_window_invalid")
    if not isinstance(raw_metrics, dict):
        raise MeasurementError("measurement_raw_payload_invalid")
    mapping, version, _item = await _measurement_mapping(
        session,
        published_content_id=published_content_id,
        content_version_id=content_version_id,
        provider=provider,
    )
    normalized = _normalized_metric_inputs(
        provider=provider,
        window_start=window_start,
        window_end=window_end,
        metrics=metrics,
    )
    raw_copy = json.loads(json.dumps(raw_metrics, ensure_ascii=False, default=str))
    fingerprint = _hash(
        {
            "provider": provider,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "raw_metrics": raw_copy,
            "metrics": [
                {
                    "metric_date": date.isoformat(),
                    "metric_name": name,
                    "metric_value": str(value),
                    "dimensions": dimensions,
                }
                for date, name, value, dimensions in normalized
            ],
        }
    )

    existing = await session.scalar(
        select(PerformanceSnapshot).where(
            PerformanceSnapshot.published_content_id == mapping.id,
            PerformanceSnapshot.provider == provider,
            PerformanceSnapshot.window_start == window_start,
            PerformanceSnapshot.window_end == window_end,
            PerformanceSnapshot.payload_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        if (
            existing.content_version_id != version.id
            or existing.raw_metrics_json != raw_copy
        ):
            raise MeasurementError("measurement_snapshot_replay_conflict")
        rows = tuple(
            (
                await session.scalars(
                    select(PerformanceMetric)
                    .where(PerformanceMetric.snapshot_id == existing.id)
                    .order_by(
                        PerformanceMetric.metric_date,
                        PerformanceMetric.metric_name,
                    )
                )
            ).all()
        )
        expected = [
            (date, name, value, dimensions)
            for date, name, value, dimensions in normalized
        ]
        actual = [
            (
                row.metric_date,
                row.metric_name,
                row.metric_value,
                row.dimensions_json,
            )
            for row in rows
        ]
        if actual != expected:
            raise MeasurementError("measurement_snapshot_metric_conflict")
        return MeasurementIngestResult(
            snapshot=existing,
            metrics=rows,
            replayed=True,
        )

    snapshot = PerformanceSnapshot(
        published_content_id=mapping.id,
        content_version_id=version.id,
        provider=provider,
        window_start=window_start,
        window_end=window_end,
        payload_fingerprint=fingerprint,
        raw_metrics_json=raw_copy,
        imported_at=imported_at or datetime.now(UTC),
    )
    session.add(snapshot)
    await session.flush()

    rows: list[PerformanceMetric] = []
    for metric_date, name, value, dimensions in normalized:
        row = PerformanceMetric(
            snapshot_id=snapshot.id,
            published_content_id=mapping.id,
            content_version_id=version.id,
            provider=provider,
            metric_date=metric_date,
            metric_name=name,
            metric_value=value,
            dimensions_json=dimensions,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return MeasurementIngestResult(
        snapshot=snapshot,
        metrics=tuple(rows),
        replayed=False,
    )


async def record_performance_observation(
    session: AsyncSession,
    *,
    published_content_id: UUID,
    content_version_id: UUID,
    observation_type: str,
    statement: str,
    data_status: DataStatus,
    observed_at: datetime,
    metric_refs: list[UUID] | None = None,
) -> ContentPerformanceObservation:
    """Persist one explicit interpretation without promoting it to a learning rule."""

    if not observation_type.strip() or not statement.strip():
        raise MeasurementError("measurement_observation_text_required")
    if data_status not in {
        "INSUFFICIENT_DATA",
        "EARLY_SIGNAL",
        "REPEATED_PATTERN",
        "LEARNING_CANDIDATE_READY",
    }:
        raise MeasurementError("measurement_observation_status_invalid")
    refs = metric_refs or []
    if data_status != "INSUFFICIENT_DATA" and not refs:
        raise MeasurementError("measurement_observation_metric_refs_required")
    rows: list[PerformanceMetric] = []
    for metric_id in refs:
        metric = await session.get(PerformanceMetric, metric_id)
        if (
            metric is None
            or metric.published_content_id != published_content_id
            or metric.content_version_id != content_version_id
        ):
            raise MeasurementError("measurement_observation_metric_mismatch")
        rows.append(metric)
    if len({row.id for row in rows}) != len(rows):
        raise MeasurementError("measurement_observation_metric_duplicate")

    await _measurement_mapping(
        session,
        published_content_id=published_content_id,
        content_version_id=content_version_id,
        provider=(rows[0].provider if rows else "analytics"),
    )
    observation = ContentPerformanceObservation(
        published_content_id=published_content_id,
        content_version_id=content_version_id,
        observation_type=observation_type.strip(),
        statement=statement.strip(),
        metric_refs_json=[str(row.id) for row in rows],
        data_status=data_status,
        observed_at=observed_at,
    )
    session.add(observation)
    await session.flush()
    return observation


async def get_measurement_identity(
    session: AsyncSession,
    *,
    published_content_id: UUID,
) -> dict[str, object]:
    """Return the exact customer/content identity used by PM-01 and later LL-01."""

    mapping = await session.get(PublishedContent, published_content_id)
    if mapping is None:
        raise MeasurementError("measurement_identity_missing")
    version = await session.get(ContentVersion, mapping.current_content_version_id)
    item = await session.get(ContentItem, mapping.content_item_id)
    if version is None or item is None or version.content_item_id != item.id:
        raise MeasurementError("measurement_identity_mismatch")
    case = await session.get(ContentCase, item.content_case_id)
    variant = await session.get(LocaleVariant, item.locale_variant_id)
    if (
        case is None
        or variant is None
        or case.project_id != mapping.project_id
        or variant.content_case_id != case.id
    ):
        raise MeasurementError("measurement_content_lineage_invalid")
    opportunity = await session.get(ContentOpportunity, case.content_opportunity_id)
    need = await session.get(NeedHypothesis, case.need_hypothesis_id)
    audience = (
        await session.get(AudienceHypothesis, case.audience_hypothesis_id)
        if case.audience_hypothesis_id is not None
        else None
    )
    if (
        opportunity is None
        or need is None
        or opportunity.need_hypothesis_id != need.id
        or opportunity.project_id != mapping.project_id
        or need.project_id != mapping.project_id
        or (audience is not None and audience.project_id != mapping.project_id)
    ):
        raise MeasurementError("measurement_customer_lineage_invalid")

    event = await session.scalar(
        select(PublishEvent)
        .where(
            PublishEvent.published_content_id == mapping.id,
            PublishEvent.content_version_id == version.id,
        )
        .order_by(PublishEvent.created_at.desc(), PublishEvent.id.desc())
        .limit(1)
    )
    if event is None:
        raise MeasurementError("measurement_publish_event_missing")
    package = await session.get(Artifact, event.publish_package_artifact_id)
    if (
        package is None
        or package.artifact_type != "publish_package"
        or not isinstance(package.content_json, dict)
        or package.content_hash != _hash(package.content_json)
    ):
        raise MeasurementError("measurement_publish_package_invalid")
    package_identity = package.content_json.get("identity")
    if not isinstance(package_identity, dict):
        raise MeasurementError("measurement_publish_package_invalid")
    expected = {
        "project_id": str(mapping.project_id),
        "content_case_id": str(case.id),
        "locale_variant_id": str(variant.id),
        "content_item_id": str(item.id),
        "content_version_id": str(version.id),
        "content_opportunity_id": str(opportunity.id),
        "need_hypothesis_id": str(need.id),
    }
    for key, value in expected.items():
        if package_identity.get(key) != value:
            raise MeasurementError("measurement_package_identity_mismatch", key)

    raw_experiment_id = package_identity.get("content_experiment_id")
    if not isinstance(raw_experiment_id, str):
        raise MeasurementError("measurement_experiment_identity_missing")
    try:
        experiment_id = UUID(raw_experiment_id)
    except ValueError as exc:
        raise MeasurementError("measurement_experiment_identity_invalid") from exc
    experiment = await session.get(ContentExperiment, experiment_id)
    if (
        experiment is None
        or experiment.published_content_id != mapping.id
        or experiment.content_version_id != version.id
        or experiment.content_item_id != item.id
        or experiment.content_opportunity_id != opportunity.id
        or experiment.need_hypothesis_id != need.id
    ):
        raise MeasurementError("measurement_experiment_identity_mismatch")
    journey = list(
        (
            await session.scalars(
                select(ContentItemJourneyStage.stage_key)
                .where(ContentItemJourneyStage.content_item_id == item.id)
                .order_by(ContentItemJourneyStage.stage_key)
            )
        ).all()
    )
    lens = package_identity.get("lens_selection")
    return {
        "published_content": {
            "id": str(mapping.id),
            "target": mapping.target,
            "external_id": mapping.external_id,
            "canonical_url": mapping.canonical_url,
            "external_revision_id": mapping.external_revision_id,
            "external_status": mapping.external_status,
            "published_at": (
                mapping.published_at.isoformat()
                if mapping.published_at is not None
                else None
            ),
        },
        "content": {
            "content_version_id": str(version.id),
            "content_version_no": version.version_no,
            "content_item_id": str(item.id),
            "content_case_id": str(case.id),
            "locale_variant_id": str(variant.id),
            "locale": variant.locale,
            "content_type": item.content_type,
            "content_hypothesis": case.content_hypothesis,
            "intent": variant.primary_intent,
        },
        "customer": {
            "audience_hypothesis_id": (
                str(audience.id) if audience is not None else None
            ),
            "need_hypothesis_id": str(need.id),
            "need_hypothesis_version": need.version,
            "need_statement": need.statement,
            "journey_stages": journey,
        },
        "opportunity": {
            "id": str(opportunity.id),
            "version": opportunity.version,
            "decision": opportunity.decision,
            "question": opportunity.question,
            "intent": opportunity.intent,
        },
        "lens_selection": lens,
        "experiment": {
            "id": str(experiment.id),
            "expected_behaviour": experiment.expected_behaviour,
            "measurement_plan": list(experiment.measurement_plan_json),
            "metric_definitions": list(experiment.metric_definitions_json),
            "minimum_evidence": list(experiment.minimum_evidence_json),
            "status": experiment.status,
            "result": experiment.result,
        },
        "publish_event": {
            "id": str(event.id),
            "idempotency_key": event.idempotency_key,
            "action": event.action,
            "external_status": event.external_status,
        },
    }


__all__ = [
    "CORE_METRICS",
    "DataStatus",
    "MeasurementError",
    "MeasurementIngestResult",
    "MeasurementProvider",
    "MetricInput",
    "get_measurement_identity",
    "ingest_performance_snapshot",
    "record_performance_observation",
]