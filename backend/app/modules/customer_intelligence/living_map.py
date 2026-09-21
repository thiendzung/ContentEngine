"""Customer Living Map read model, snapshot and incremental change detection."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    AudienceHypothesis,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    SettingsVersion,
    Signal,
)
from app.modules.customer_intelligence.insights import (
    CustomerInsightError,
    customer_insight_evidence_counts,
)
from app.modules.customer_intelligence.models import (
    CustomerInsight,
    CustomerInsightNeedLink,
    CustomerInsightSignal,
)
from app.modules.harness.models import Artifact, ContentRun, StepRun

CUSTOMER_MAP_SCHEMA_VERSION = 1
CUSTOMER_MAP_ARTIFACT_TYPE = "customer_map_snapshot"
JourneyChangeKind = Literal["NEW", "SUPPORT", "CONTRADICT", "DUPLICATE"]
InsightNeedRelation = Literal["supports", "contradicts", "context"]

_DEFAULT_JOURNEY_STAGES: tuple[dict[str, str | None], ...] = (
    {
        "key": "unaware",
        "label": "Unaware",
        "description": "Customer has not yet recognized MOTGU or the relevant need.",
    },
    {
        "key": "aware",
        "label": "Aware",
        "description": "Customer recognizes MOTGU, the category, or the need.",
    },
    {
        "key": "interested",
        "label": "Interested",
        "description": "Customer is actively exploring or comparing.",
    },
    {
        "key": "preference",
        "label": "Preference",
        "description": "Customer is developing preference or affinity.",
    },
    {
        "key": "trust",
        "label": "Trust",
        "description": "Customer has enough confidence to consider action.",
    },
    {
        "key": "purchase",
        "label": "Purchase",
        "description": "Customer is deciding or completing a purchase.",
    },
    {
        "key": "satisfied",
        "label": "Satisfied",
        "description": "Customer evaluates the post-purchase experience.",
    },
    {
        "key": "referral",
        "label": "Referral",
        "description": "Customer may recommend MOTGU to others.",
    },
    {
        "key": "repeat_purchase",
        "label": "Repeat purchase",
        "description": "Customer may return for another purchase or experience.",
    },
)
_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class CustomerMapError(ValueError):
    """Fail-closed Living Map error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class JourneyConfig:
    stages: tuple[dict[str, str | None], ...]
    source_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CustomerMapRefreshResult:
    artifact: Artifact
    change_report: dict[str, object]


async def ensure_customer_insight_need_link(
    session: AsyncSession,
    *,
    customer_insight_id: UUID,
    need_hypothesis_id: UUID,
    relation: InsightNeedRelation,
) -> CustomerInsightNeedLink:
    if relation not in {"supports", "contradicts", "context"}:
        raise CustomerMapError("customer_map_insight_need_relation_invalid")

    insight = await session.get(CustomerInsight, customer_insight_id)
    if insight is None:
        raise CustomerMapError("customer_map_insight_not_found")
    need = await session.get(NeedHypothesis, need_hypothesis_id)
    if need is None:
        raise CustomerMapError("customer_map_need_not_found")
    if insight.project_id != need.project_id:
        raise CustomerMapError("customer_map_insight_need_project_mismatch")
    if (
        insight.audience_hypothesis_id is not None
        and need.audience_hypothesis_id is not None
        and insight.audience_hypothesis_id != need.audience_hypothesis_id
    ):
        raise CustomerMapError("customer_map_insight_need_audience_mismatch")

    existing = await session.get(
        CustomerInsightNeedLink,
        (customer_insight_id, need_hypothesis_id),
    )
    if existing is not None:
        if existing.relation != relation:
            raise CustomerMapError("customer_map_insight_need_replay_conflict")
        return existing

    link = CustomerInsightNeedLink(
        customer_insight_id=customer_insight_id,
        need_hypothesis_id=need_hypothesis_id,
        relation=relation,
    )
    session.add(link)
    await session.flush()
    return link


async def resolve_journey_config(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> JourneyConfig:
    project = await session.get(Project, project_id)
    if project is None:
        raise CustomerMapError("customer_map_project_not_found")

    rows = list(
        (
            await session.scalars(
                select(SettingsVersion)
                .where(
                    SettingsVersion.status == "active",
                    or_(
                        and_(
                            SettingsVersion.scope_type == "system",
                            SettingsVersion.project_id.is_(None),
                        ),
                        and_(
                            SettingsVersion.scope_type == "project",
                            SettingsVersion.project_id == project.id,
                            SettingsVersion.scope_key == project.slug,
                        ),
                    ),
                )
                .order_by(
                    SettingsVersion.scope_type,
                    SettingsVersion.scope_key,
                    SettingsVersion.version,
                    SettingsVersion.id,
                )
            )
        ).all()
    )

    configs: list[tuple[tuple[dict[str, str | None], ...], str]] = []
    for row in rows:
        root = row.settings_json.get("customer_living_map")
        if root is None:
            continue
        if not isinstance(root, dict):
            raise CustomerMapError("customer_map_settings_invalid")
        journey = root.get("journey")
        if journey is None:
            continue
        if not isinstance(journey, dict) or set(journey) != {"stages"}:
            raise CustomerMapError("customer_map_journey_settings_invalid")
        stages = _parse_journey_stages(journey.get("stages"))
        configs.append(
            (
                stages,
                f"settings_version:{row.id}:v{row.version}",
            )
        )

    if not configs:
        return JourneyConfig(
            stages=_DEFAULT_JOURNEY_STAGES,
            source_refs=("builtin:customer-journey:v1",),
        )

    canonical = configs[0][0]
    if any(stages != canonical for stages, _ in configs[1:]):
        raise CustomerMapError("customer_map_journey_config_conflict")
    return JourneyConfig(
        stages=canonical,
        source_refs=tuple(ref for _, ref in configs),
    )


async def build_customer_map_snapshot(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> dict[str, object]:
    project = await session.get(Project, project_id)
    if project is None:
        raise CustomerMapError("customer_map_project_not_found")

    journey = await resolve_journey_config(session, project_id=project.id)
    audiences = list(
        (
            await session.scalars(
                select(AudienceHypothesis)
                .where(AudienceHypothesis.project_id == project.id)
                .order_by(AudienceHypothesis.name, AudienceHypothesis.id)
            )
        ).all()
    )
    needs = list(
        (
            await session.scalars(
                select(NeedHypothesis)
                .where(NeedHypothesis.project_id == project.id)
                .order_by(NeedHypothesis.id)
            )
        ).all()
    )
    all_insights = list(
        (
            await session.scalars(
                select(CustomerInsight)
                .where(CustomerInsight.project_id == project.id)
                .order_by(
                    CustomerInsight.insight_key,
                    CustomerInsight.version,
                    CustomerInsight.id,
                )
            )
        ).all()
    )
    current_insights: dict[str, CustomerInsight] = {}
    for insight in all_insights:
        previous = current_insights.get(insight.insight_key)
        if previous is None or insight.version > previous.version:
            current_insights[insight.insight_key] = insight
    insights = sorted(
        current_insights.values(),
        key=lambda row: (row.insight_key, row.version, str(row.id)),
    )

    insight_ids = [row.id for row in insights]
    need_ids = [row.id for row in needs]

    insight_signal_rows = []
    if insight_ids:
        insight_signal_rows = list(
            (
                await session.execute(
                    select(CustomerInsightSignal)
                    .where(
                        CustomerInsightSignal.customer_insight_id.in_(insight_ids)
                    )
                    .order_by(
                        CustomerInsightSignal.customer_insight_id,
                        CustomerInsightSignal.relation,
                        CustomerInsightSignal.signal_id,
                    )
                )
            ).scalars()
        )
    insight_need_rows = []
    if insight_ids:
        insight_need_rows = list(
            (
                await session.execute(
                    select(CustomerInsightNeedLink)
                    .where(
                        CustomerInsightNeedLink.customer_insight_id.in_(insight_ids)
                    )
                    .order_by(
                        CustomerInsightNeedLink.customer_insight_id,
                        CustomerInsightNeedLink.need_hypothesis_id,
                    )
                )
            ).scalars()
        )
    need_signal_rows = []
    if need_ids:
        need_signal_rows = list(
            (
                await session.execute(
                    select(NeedHypothesisSignal)
                    .where(NeedHypothesisSignal.need_hypothesis_id.in_(need_ids))
                    .order_by(
                        NeedHypothesisSignal.need_hypothesis_id,
                        NeedHypothesisSignal.relation,
                        NeedHypothesisSignal.signal_id,
                    )
                )
            ).scalars()
        )

    insight_signal_map: dict[UUID, dict[str, list[str]]] = {}
    for link in insight_signal_rows:
        refs = insight_signal_map.setdefault(
            link.customer_insight_id,
            {"supports": [], "contradicts": [], "context": []},
        )
        refs[link.relation].append(str(link.signal_id))

    insight_need_map: dict[UUID, list[dict[str, str]]] = {}
    need_insight_map: dict[UUID, list[dict[str, str]]] = {}
    for link in insight_need_rows:
        insight_need_map.setdefault(link.customer_insight_id, []).append(
            {
                "need_hypothesis_id": str(link.need_hypothesis_id),
                "relation": link.relation,
            }
        )
        need_insight_map.setdefault(link.need_hypothesis_id, []).append(
            {
                "customer_insight_id": str(link.customer_insight_id),
                "relation": link.relation,
            }
        )

    need_signal_map: dict[UUID, dict[str, list[str]]] = {}
    for link in need_signal_rows:
        refs = need_signal_map.setdefault(
            link.need_hypothesis_id,
            {"supports": [], "contradicts": []},
        )
        refs[link.relation].append(str(link.signal_id))

    insight_payloads: list[dict[str, object]] = []
    for insight in insights:
        refs = insight_signal_map.get(
            insight.id,
            {"supports": [], "contradicts": [], "context": []},
        )
        try:
            evidence = await customer_insight_evidence_counts(
                session,
                customer_insight_id=insight.id,
            )
        except CustomerInsightError as exc:
            raise CustomerMapError(exc.code) from exc
        insight_payloads.append(
            {
                "id": str(insight.id),
                "insight_key": insight.insight_key,
                "version": insight.version,
                "audience_hypothesis_id": (
                    str(insight.audience_hypothesis_id)
                    if insight.audience_hypothesis_id is not None
                    else None
                ),
                "insight_type": insight.insight_type,
                "statement": insight.statement,
                "situation": insight.situation,
                "status": insight.status,
                "alternative_explanations": list(
                    insight.alternative_explanations_json
                ),
                "missing_evidence": list(insight.missing_evidence_json),
                "reviewed_by": insight.reviewed_by,
                "review_reason": insight.review_reason,
                "signal_refs": {
                    "supports": sorted(refs["supports"]),
                    "contradicts": sorted(refs["contradicts"]),
                    "context": sorted(refs["context"]),
                },
                "evidence_counts": {
                    "supports": evidence.supports,
                    "contradicts": evidence.contradicts,
                    "context": evidence.context,
                    "independent_supports": evidence.independent_supports,
                    "independent_contradicts": evidence.independent_contradicts,
                    "independent_context": evidence.independent_context,
                },
                "need_links": sorted(
                    insight_need_map.get(insight.id, []),
                    key=lambda item: (
                        item["need_hypothesis_id"],
                        item["relation"],
                    ),
                ),
            }
        )

    need_payloads: list[dict[str, object]] = []
    for need in needs:
        refs = need_signal_map.get(
            need.id,
            {"supports": [], "contradicts": []},
        )
        need_payloads.append(
            {
                "id": str(need.id),
                "audience_hypothesis_id": (
                    str(need.audience_hypothesis_id)
                    if need.audience_hypothesis_id is not None
                    else None
                ),
                "type": need.type,
                "statement": need.statement,
                "audience_scope": need.audience_scope,
                "situation": need.situation,
                "origin": need.origin,
                "status": need.status,
                "version": need.version,
                "alternative_explanations": list(
                    need.alternative_explanations_json
                ),
                "missing_evidence": list(need.missing_evidence_json),
                "reviewed_by": need.reviewed_by,
                "review_reason": need.review_reason,
                "signal_refs": {
                    "supports": sorted(refs["supports"]),
                    "contradicts": sorted(refs["contradicts"]),
                },
                "insight_links": sorted(
                    need_insight_map.get(need.id, []),
                    key=lambda item: (
                        item["customer_insight_id"],
                        item["relation"],
                    ),
                ),
            }
        )

    insight_ref_by_audience: dict[str, list[dict[str, object]]] = {}
    unassigned_insights: list[dict[str, object]] = []
    for insight in insight_payloads:
        ref = {
            "id": insight["id"],
            "insight_key": insight["insight_key"],
            "version": insight["version"],
            "status": insight["status"],
            "insight_type": insight["insight_type"],
        }
        audience_id = insight["audience_hypothesis_id"]
        if isinstance(audience_id, str):
            insight_ref_by_audience.setdefault(audience_id, []).append(ref)
        else:
            unassigned_insights.append(ref)

    need_ref_by_audience: dict[str, list[dict[str, object]]] = {}
    unassigned_needs: list[dict[str, object]] = []
    for need in need_payloads:
        ref = {
            "id": need["id"],
            "version": need["version"],
            "status": need["status"],
            "type": need["type"],
            "statement": need["statement"],
        }
        audience_id = need["audience_hypothesis_id"]
        if isinstance(audience_id, str):
            need_ref_by_audience.setdefault(audience_id, []).append(ref)
        else:
            unassigned_needs.append(ref)

    audience_payloads = [
        {
            "id": str(audience.id),
            "name": audience.name,
            "description": audience.description,
            "status": audience.status,
            "evidence_summary": audience.evidence_summary,
            "confidence": audience.confidence,
            "insights": sorted(
                insight_ref_by_audience.get(str(audience.id), []),
                key=lambda item: (
                    str(item["insight_key"]),
                    int(item["version"]),
                ),
            ),
            "needs": sorted(
                need_ref_by_audience.get(str(audience.id), []),
                key=lambda item: str(item["id"]),
            ),
        }
        for audience in audiences
    ]

    return {
        "schema_version": CUSTOMER_MAP_SCHEMA_VERSION,
        "project": {
            "id": str(project.id),
            "slug": project.slug,
            "name": project.name,
        },
        "journey": {
            "stages": [dict(stage) for stage in journey.stages],
            "source_refs": list(journey.source_refs),
        },
        "audiences": audience_payloads,
        "insights": insight_payloads,
        "needs": need_payloads,
        "unassigned": {
            "insights": sorted(
                unassigned_insights,
                key=lambda item: (
                    str(item["insight_key"]),
                    int(item["version"]),
                ),
            ),
            "needs": sorted(
                unassigned_needs,
                key=lambda item: str(item["id"]),
            ),
        },
    }


async def latest_customer_map_snapshot_artifact(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> Artifact | None:
    return await session.scalar(
        select(Artifact)
        .join(ContentRun, ContentRun.id == Artifact.run_id)
        .where(
            ContentRun.project_id == project_id,
            Artifact.artifact_type == CUSTOMER_MAP_ARTIFACT_TYPE,
        )
        .order_by(Artifact.created_at.desc(), Artifact.id.desc())
        .limit(1)
    )


async def refresh_customer_map_snapshot_artifact(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
) -> CustomerMapRefreshResult:
    run = await session.get(ContentRun, run_id)
    if run is None:
        raise CustomerMapError("customer_map_run_not_found")
    if step_run_id is not None:
        step = await session.get(StepRun, step_run_id)
        if step is None or step.run_id != run.id:
            raise CustomerMapError("customer_map_step_mismatch")

    previous = await latest_customer_map_snapshot_artifact(
        session,
        project_id=run.project_id,
    )
    current = await build_customer_map_snapshot(
        session,
        project_id=run.project_id,
    )
    report = compare_customer_map_snapshots(
        previous.content_json if previous is not None else None,
        current,
    )
    content_hash = _stable_hash(current)

    latest_in_run = await session.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == run.id,
            Artifact.artifact_type == CUSTOMER_MAP_ARTIFACT_TYPE,
        )
        .order_by(Artifact.version.desc())
        .limit(1)
    )
    if (
        latest_in_run is not None
        and latest_in_run.content_hash == content_hash
        and latest_in_run.content_json == current
        and latest_in_run.step_run_id == step_run_id
    ):
        return CustomerMapRefreshResult(
            artifact=latest_in_run,
            change_report=report,
        )

    artifact = Artifact(
        run_id=run.id,
        step_run_id=step_run_id,
        artifact_type=CUSTOMER_MAP_ARTIFACT_TYPE,
        locale=None,
        version=(latest_in_run.version + 1 if latest_in_run is not None else 1),
        content_json=current,
        external_ref=None,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    return CustomerMapRefreshResult(
        artifact=artifact,
        change_report=report,
    )


def compare_customer_map_snapshots(
    previous: object,
    current: object,
) -> dict[str, object]:
    current_map = _validate_snapshot(current)
    previous_map = _validate_snapshot(previous) if previous is not None else None

    current_project = current_map["project"]
    if not isinstance(current_project, dict):
        raise CustomerMapError("customer_map_snapshot_project_invalid")
    project_id = current_project.get("id")
    if not isinstance(project_id, str):
        raise CustomerMapError("customer_map_snapshot_project_invalid")

    if previous_map is not None:
        previous_project = previous_map["project"]
        if (
            not isinstance(previous_project, dict)
            or previous_project.get("id") != project_id
        ):
            raise CustomerMapError("customer_map_snapshot_project_mismatch")

    events: list[dict[str, object]] = []
    if previous_map is None:
        for audience in _records(current_map, "audiences"):
            events.append(
                _event(
                    "NEW",
                    "audience",
                    _string_field(audience, "id"),
                    "audience_added",
                )
            )
        for need in _records(current_map, "needs"):
            events.append(
                _event(
                    "NEW",
                    "need",
                    _string_field(need, "id"),
                    "need_added",
                )
            )
        for insight in _records(current_map, "insights"):
            events.append(
                _event(
                    "NEW",
                    "insight",
                    _string_field(insight, "insight_key"),
                    "insight_added",
                )
            )
        for stage in _journey_stages(current_map):
            events.append(
                _event(
                    "NEW",
                    "journey_stage",
                    _string_field(stage, "key"),
                    "journey_stage_added",
                )
            )
        return _change_report(
            baseline=True,
            previous_hash=None,
            current_hash=_stable_hash(current_map),
            events=events,
        )

    previous_audiences = _by_id(_records(previous_map, "audiences"), "id")
    current_audiences = _by_id(_records(current_map, "audiences"), "id")
    for audience_id in sorted(set(current_audiences) - set(previous_audiences)):
        events.append(
            _event("NEW", "audience", audience_id, "audience_added")
        )

    previous_needs = _by_id(_records(previous_map, "needs"), "id")
    current_needs = _by_id(_records(current_map, "needs"), "id")
    for need_id in sorted(set(current_needs) - set(previous_needs)):
        events.append(_event("NEW", "need", need_id, "need_added"))

    previous_insights = _by_id(
        _records(previous_map, "insights"),
        "insight_key",
    )
    current_insights = _by_id(
        _records(current_map, "insights"),
        "insight_key",
    )
    for insight_key in sorted(set(current_insights) - set(previous_insights)):
        events.append(
            _event("NEW", "insight", insight_key, "insight_added")
        )

    for insight_key in sorted(set(current_insights) & set(previous_insights)):
        before = previous_insights[insight_key]
        after = current_insights[insight_key]
        before_version = before.get("version")
        after_version = after.get("version")
        if before_version != after_version:
            events.append(
                _event(
                    "NEW",
                    "insight",
                    insight_key,
                    "insight_version_changed",
                    before=before_version,
                    after=after_version,
                )
            )
        events.extend(
            _insight_evidence_events(
                insight_key=insight_key,
                previous=before,
                current=after,
            )
        )

    previous_stages = _by_id(_journey_stages(previous_map), "key")
    current_stages = _by_id(_journey_stages(current_map), "key")
    for stage_key in sorted(set(current_stages) - set(previous_stages)):
        events.append(
            _event(
                "NEW",
                "journey_stage",
                stage_key,
                "journey_stage_added",
            )
        )

    return _change_report(
        baseline=False,
        previous_hash=_stable_hash(previous_map),
        current_hash=_stable_hash(current_map),
        events=events,
    )


async def customer_map_summary(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> dict[str, object]:
    snapshot = await build_customer_map_snapshot(session, project_id=project_id)
    audiences = _records(snapshot, "audiences")
    needs = _records(snapshot, "needs")
    insights = _records(snapshot, "insights")
    return {
        "project": snapshot["project"],
        "snapshot_hash": _stable_hash(snapshot),
        "journey": snapshot["journey"],
        "counts": {
            "audiences": len(audiences),
            "needs": len(needs),
            "insights": len(insights),
            "supported_needs": sum(
                1 for row in needs if row.get("status") == "SUPPORTED"
            ),
            "supported_insights": sum(
                1 for row in insights if row.get("status") == "SUPPORTED"
            ),
            "unassigned_needs": len(
                _records(
                    _dict_field(snapshot, "unassigned"),
                    "needs",
                )
            ),
            "unassigned_insights": len(
                _records(
                    _dict_field(snapshot, "unassigned"),
                    "insights",
                )
            ),
        },
        "audiences": [
            {
                "id": audience["id"],
                "name": audience["name"],
                "status": audience["status"],
                "need_count": len(_records(audience, "needs")),
                "insight_count": len(_records(audience, "insights")),
            }
            for audience in audiences
        ],
    }


async def customer_map_audience_detail(
    session: AsyncSession,
    *,
    project_id: UUID,
    audience_id: UUID,
) -> dict[str, object]:
    snapshot = await build_customer_map_snapshot(session, project_id=project_id)
    audience = next(
        (
            row
            for row in _records(snapshot, "audiences")
            if row.get("id") == str(audience_id)
        ),
        None,
    )
    if audience is None:
        raise CustomerMapError("customer_map_audience_not_found")

    need_ids = {
        str(item["id"])
        for item in _records(audience, "needs")
        if isinstance(item.get("id"), str)
    }
    insight_ids = {
        str(item["id"])
        for item in _records(audience, "insights")
        if isinstance(item.get("id"), str)
    }
    return {
        "project": snapshot["project"],
        "snapshot_hash": _stable_hash(snapshot),
        "journey": snapshot["journey"],
        "audience": audience,
        "needs": [
            row
            for row in _records(snapshot, "needs")
            if row.get("id") in need_ids
        ],
        "insights": [
            row
            for row in _records(snapshot, "insights")
            if row.get("id") in insight_ids
        ],
    }


async def customer_map_changes(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> dict[str, object]:
    current = await build_customer_map_snapshot(session, project_id=project_id)
    previous = await latest_customer_map_snapshot_artifact(
        session,
        project_id=project_id,
    )
    return compare_customer_map_snapshots(
        previous.content_json if previous is not None else None,
        current,
    )


def _parse_journey_stages(value: object) -> tuple[dict[str, str | None], ...]:
    if not isinstance(value, list) or not value:
        raise CustomerMapError("customer_map_journey_stages_invalid")
    stages: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            raise CustomerMapError("customer_map_journey_stage_invalid")
        if not set(raw).issubset({"key", "label", "description"}):
            raise CustomerMapError("customer_map_journey_stage_invalid")
        if "key" not in raw or "label" not in raw:
            raise CustomerMapError("customer_map_journey_stage_invalid")
        key = raw["key"]
        label = raw["label"]
        description = raw.get("description")
        if (
            not isinstance(key, str)
            or not _KEY_RE.fullmatch(key)
            or key in seen
            or not isinstance(label, str)
            or not label.strip()
            or (
                description is not None
                and (not isinstance(description, str) or not description.strip())
            )
        ):
            raise CustomerMapError("customer_map_journey_stage_invalid")
        seen.add(key)
        stages.append(
            {
                "key": key,
                "label": label.strip(),
                "description": (
                    description.strip()
                    if isinstance(description, str)
                    else None
                ),
            }
        )
    return tuple(stages)


def _insight_evidence_events(
    *,
    insight_key: str,
    previous: dict[str, object],
    current: dict[str, object],
) -> list[dict[str, object]]:
    previous_refs = _dict_field(previous, "signal_refs")
    current_refs = _dict_field(current, "signal_refs")
    previous_counts = _dict_field(previous, "evidence_counts")
    current_counts = _dict_field(current, "evidence_counts")
    events: list[dict[str, object]] = []

    for relation, kind, count_key in (
        ("supports", "SUPPORT", "independent_supports"),
        ("contradicts", "CONTRADICT", "independent_contradicts"),
    ):
        before = set(_string_list_field(previous_refs, relation))
        after = set(_string_list_field(current_refs, relation))
        added = sorted(after - before)
        if not added:
            continue
        before_independent = _int_field(previous_counts, count_key)
        after_independent = _int_field(current_counts, count_key)
        event_kind: JourneyChangeKind
        detail: str
        if after_independent > before_independent:
            event_kind = kind  # type: ignore[assignment]
            detail = f"{relation}_evidence_added"
        else:
            event_kind = "DUPLICATE"
            detail = f"{relation}_duplicate_evidence_added"
        events.append(
            _event(
                event_kind,
                "insight",
                insight_key,
                detail,
                signal_refs=added,
                independent_before=before_independent,
                independent_after=after_independent,
            )
        )
    return events


def _change_report(
    *,
    baseline: bool,
    previous_hash: str | None,
    current_hash: str,
    events: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "baseline": baseline,
        "previous_snapshot_hash": previous_hash,
        "current_snapshot_hash": current_hash,
        "counts": {
            "NEW": sum(1 for event in events if event["kind"] == "NEW"),
            "SUPPORT": sum(
                1 for event in events if event["kind"] == "SUPPORT"
            ),
            "CONTRADICT": sum(
                1 for event in events if event["kind"] == "CONTRADICT"
            ),
            "DUPLICATE": sum(
                1 for event in events if event["kind"] == "DUPLICATE"
            ),
        },
        "events": events,
    }


def _event(
    kind: JourneyChangeKind,
    entity_type: str,
    entity_ref: str,
    detail: str,
    **extra: object,
) -> dict[str, object]:
    return {
        "kind": kind,
        "entity_type": entity_type,
        "entity_ref": entity_ref,
        "detail": detail,
        **extra,
    }


def _validate_snapshot(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CustomerMapError("customer_map_snapshot_invalid")
    snapshot = {str(key): item for key, item in value.items()}
    if snapshot.get("schema_version") != CUSTOMER_MAP_SCHEMA_VERSION:
        raise CustomerMapError("customer_map_snapshot_schema_invalid")
    for key in (
        "project",
        "journey",
        "audiences",
        "insights",
        "needs",
        "unassigned",
    ):
        if key not in snapshot:
            raise CustomerMapError("customer_map_snapshot_invalid")
    return snapshot


def _records(container: dict[str, object], key: str) -> list[dict[str, object]]:
    value = container.get(key)
    if not isinstance(value, list):
        raise CustomerMapError("customer_map_snapshot_invalid")
    output: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise CustomerMapError("customer_map_snapshot_invalid")
        output.append({str(k): v for k, v in item.items()})
    return output


def _journey_stages(snapshot: dict[str, object]) -> list[dict[str, object]]:
    journey = _dict_field(snapshot, "journey")
    return _records(journey, "stages")


def _dict_field(container: dict[str, object], key: str) -> dict[str, object]:
    value = container.get(key)
    if not isinstance(value, dict):
        raise CustomerMapError("customer_map_snapshot_invalid")
    return {str(k): v for k, v in value.items()}


def _string_field(container: dict[str, object], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str):
        raise CustomerMapError("customer_map_snapshot_invalid")
    return value


def _string_list_field(container: dict[str, object], key: str) -> list[str]:
    value = container.get(key)
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in value
    ):
        raise CustomerMapError("customer_map_snapshot_invalid")
    return list(value)


def _int_field(container: dict[str, object], key: str) -> int:
    value = container.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CustomerMapError("customer_map_snapshot_invalid")
    return value


def _by_id(
    rows: list[dict[str, object]],
    key: str,
) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for row in rows:
        identifier = _string_field(row, key)
        if identifier in output:
            raise CustomerMapError("customer_map_snapshot_duplicate_identity")
        output[identifier] = row
    return output


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "CUSTOMER_MAP_ARTIFACT_TYPE",
    "CUSTOMER_MAP_SCHEMA_VERSION",
    "CustomerMapError",
    "CustomerMapRefreshResult",
    "JourneyConfig",
    "build_customer_map_snapshot",
    "compare_customer_map_snapshots",
    "customer_map_audience_detail",
    "customer_map_changes",
    "customer_map_summary",
    "ensure_customer_insight_need_link",
    "latest_customer_map_snapshot_artifact",
    "refresh_customer_map_snapshot_artifact",
    "resolve_journey_config",
]
