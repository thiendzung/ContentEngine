from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    ContentOpportunity as DBContentOpportunity,
)
from app.modules.content_engine.models import (
    ContentOpportunitySignal,
    NeedHypothesis as DBNeedHypothesis,
    NeedHypothesisSignal,
    Signal as DBSignal,
)
from app.modules.research.keyword_plan.contracts import OpportunityMapResult, Signal


@dataclass(slots=True, frozen=True)
class PersistedDiscoveryPlan:
    need_hypothesis_id: UUID
    signal_ids: dict[str, UUID]
    opportunity_ids: dict[str, UUID]


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _signal_provenance(signal: Signal) -> dict[str, object]:
    provenance = {
        key: value
        for key, value in asdict(signal.provenance).items()
        if value is not None
    }
    provenance["planning_signal_id"] = signal.id
    return provenance


async def _persist_signals(
    session: AsyncSession,
    *,
    project_id: UUID,
    result: OpportunityMapResult,
) -> dict[str, UUID]:
    signal_ids: dict[str, UUID] = {}
    rows_by_planning_id: dict[str, DBSignal] = {}

    for signal in result.signals:
        existing = (
            await session.execute(
                select(DBSignal)
                .where(
                    DBSignal.project_id == project_id,
                    DBSignal.fingerprint == signal.fingerprint,
                    DBSignal.source_kind == signal.source_kind.value,
                    DBSignal.scope == signal.scope.value,
                    DBSignal.locale == signal.locale,
                    DBSignal.observed_text == signal.observed_text,
                )
                .order_by(DBSignal.created_at.asc(), DBSignal.id.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = DBSignal(
                project_id=project_id,
                source_kind=signal.source_kind.value,
                scope=signal.scope.value,
                observed_text=signal.observed_text,
                source_url=signal.source_url,
                external_id=signal.external_id,
                locale=signal.locale,
                context=signal.context,
                captured_at=_parse_datetime(signal.captured_at),
                observed_at=(
                    _parse_datetime(signal.observed_at)
                    if signal.observed_at is not None
                    else None
                ),
                fingerprint=signal.fingerprint,
                independence_group=signal.independence_group,
                provenance_json=_signal_provenance(signal),
            )
            session.add(existing)
            await session.flush()
        signal_ids[signal.id] = existing.id
        rows_by_planning_id[signal.id] = existing

    for signal in result.signals:
        if signal.duplicate_of is None:
            continue
        row = rows_by_planning_id[signal.id]
        duplicate_of_id = signal_ids.get(signal.duplicate_of)
        if duplicate_of_id is not None and row.duplicate_of_id is None:
            row.duplicate_of_id = duplicate_of_id

    await session.flush()
    return signal_ids


async def _persist_hypothesis(
    session: AsyncSession,
    *,
    project_id: UUID,
    result: OpportunityMapResult,
    signal_ids: dict[str, UUID],
) -> DBNeedHypothesis:
    hypothesis = result.need_hypothesis
    row = (
        await session.execute(
            select(DBNeedHypothesis)
            .where(
                DBNeedHypothesis.project_id == project_id,
                DBNeedHypothesis.type == hypothesis.need_type.value,
                DBNeedHypothesis.statement == hypothesis.statement,
                DBNeedHypothesis.audience_scope == hypothesis.audience_scope,
                DBNeedHypothesis.situation == hypothesis.situation,
                DBNeedHypothesis.origin == hypothesis.origin,
            )
            .order_by(DBNeedHypothesis.version.desc(), DBNeedHypothesis.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        row = DBNeedHypothesis(
            project_id=project_id,
            type=hypothesis.need_type.value,
            statement=hypothesis.statement,
            audience_scope=hypothesis.audience_scope,
            situation=hypothesis.situation,
            origin=hypothesis.origin,
            status=hypothesis.status.value,
            alternative_explanations_json=list(hypothesis.alternative_explanations),
            missing_evidence_json=list(hypothesis.missing_evidence),
            version=hypothesis.version,
        )
        session.add(row)
        await session.flush()
    elif row.status == "PROPOSED":
        row.alternative_explanations_json = list(
            dict.fromkeys(
                (*row.alternative_explanations_json, *hypothesis.alternative_explanations)
            )
        )
        row.missing_evidence_json = list(
            dict.fromkeys((*row.missing_evidence_json, *hypothesis.missing_evidence))
        )

    for planning_id, relation in (
        *((ref, "supports") for ref in hypothesis.support_signal_refs),
        *((ref, "contradicts") for ref in hypothesis.contradict_signal_refs),
    ):
        signal_id = signal_ids.get(planning_id)
        if signal_id is None:
            continue
        existing_link = await session.get(
            NeedHypothesisSignal,
            (row.id, signal_id, relation),
        )
        if existing_link is None:
            session.add(
                NeedHypothesisSignal(
                    need_hypothesis_id=row.id,
                    signal_id=signal_id,
                    relation=relation,
                )
            )

    await session.flush()
    return row


async def _persist_opportunities(
    session: AsyncSession,
    *,
    project_id: UUID,
    result: OpportunityMapResult,
    hypothesis_id: UUID,
    signal_ids: dict[str, UUID],
) -> dict[str, UUID]:
    opportunity_ids: dict[str, UUID] = {}

    for opportunity in result.opportunities:
        row = (
            await session.execute(
                select(DBContentOpportunity)
                .where(
                    DBContentOpportunity.project_id == project_id,
                    DBContentOpportunity.need_hypothesis_id == hypothesis_id,
                    DBContentOpportunity.locale == opportunity.locale,
                    DBContentOpportunity.question == opportunity.question,
                    DBContentOpportunity.decision == opportunity.decision.value,
                    DBContentOpportunity.version == opportunity.version,
                )
                .order_by(DBContentOpportunity.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            row = DBContentOpportunity(
                project_id=project_id,
                need_hypothesis_id=hypothesis_id,
                locale=opportunity.locale,
                reader=opportunity.reader,
                situation=opportunity.situation,
                need=opportunity.need,
                question=opportunity.question,
                intent=opportunity.intent.value,
                promise=opportunity.promise,
                motgu_material_refs_json=list(opportunity.motgu_material_refs),
                material_gaps_json=list(opportunity.material_gaps),
                existing_content_refs_json=list(opportunity.existing_content_refs),
                what_is_actually_new=opportunity.what_is_actually_new,
                next_discovery_step=opportunity.next_discovery_step,
                decision=opportunity.decision.value,
                priority=opportunity.priority.value,
                reasons_json=list(opportunity.reasons),
                suggested_content_type=opportunity.suggested_content_type.value,
                suggested_role=(
                    opportunity.suggested_role.value
                    if opportunity.suggested_role is not None
                    else None
                ),
                version=opportunity.version,
            )
            session.add(row)
            await session.flush()
        elif row.selected_by is None:
            # An unselected planning proposal may absorb more traceable context on rerun.
            row.reader = opportunity.reader
            row.situation = opportunity.situation
            row.need = opportunity.need
            row.intent = opportunity.intent.value
            row.promise = opportunity.promise
            row.motgu_material_refs_json = list(opportunity.motgu_material_refs)
            row.material_gaps_json = list(opportunity.material_gaps)
            row.existing_content_refs_json = list(opportunity.existing_content_refs)
            row.what_is_actually_new = opportunity.what_is_actually_new
            row.next_discovery_step = opportunity.next_discovery_step
            row.priority = opportunity.priority.value
            row.reasons_json = list(opportunity.reasons)
            row.suggested_content_type = opportunity.suggested_content_type.value
            row.suggested_role = (
                opportunity.suggested_role.value
                if opportunity.suggested_role is not None
                else None
            )

        opportunity_ids[opportunity.id] = row.id
        for planning_signal_id in opportunity.signal_refs:
            signal_id = signal_ids.get(planning_signal_id)
            if signal_id is None:
                continue
            existing_link = await session.get(
                ContentOpportunitySignal,
                (row.id, signal_id),
            )
            if existing_link is None:
                session.add(
                    ContentOpportunitySignal(
                        content_opportunity_id=row.id,
                        signal_id=signal_id,
                    )
                )

    await session.flush()
    return opportunity_ids


async def persist_discovery_plan(
    session: AsyncSession,
    *,
    project_id: UUID,
    result: OpportunityMapResult,
) -> PersistedDiscoveryPlan:
    """Persist pre-ContentCase planning objects without creating a ContentRun."""

    signal_ids = await _persist_signals(
        session,
        project_id=project_id,
        result=result,
    )
    hypothesis = await _persist_hypothesis(
        session,
        project_id=project_id,
        result=result,
        signal_ids=signal_ids,
    )
    opportunity_ids = await _persist_opportunities(
        session,
        project_id=project_id,
        result=result,
        hypothesis_id=hypothesis.id,
        signal_ids=signal_ids,
    )
    return PersistedDiscoveryPlan(
        need_hypothesis_id=hypothesis.id,
        signal_ids=signal_ids,
        opportunity_ids=opportunity_ids,
    )
