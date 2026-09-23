from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import ContentExperiment as DBContentExperiment
from app.modules.content_engine.models import (
    ContentOpportunity as DBContentOpportunity,
)
from app.modules.content_engine.models import (
    ContentOpportunitySignal,
    NeedHypothesisSignal,
)
from app.modules.content_engine.models import HumanSelection as DBHumanSelection
from app.modules.content_engine.models import (
    NeedHypothesis as DBNeedHypothesis,
)
from app.modules.content_engine.models import Signal as DBSignal
from app.modules.knowledge.ingest import ingest_source_document, register_source
from app.modules.research.contracts import (
    PageDocument,
    ProductionResearchResult,
    SourceCandidate,
)
from app.modules.research.evidence.contracts import PersistedPageRef
from app.modules.research.keyword_plan.contracts import OpportunityMapResult, Signal


@dataclass(slots=True, frozen=True)
class PersistedDiscoveryPlan:
    need_hypothesis_id: UUID
    signal_ids: dict[str, UUID]
    opportunity_ids: dict[str, UUID]


@dataclass(slots=True, frozen=True)
class PersistedDiscoverySelection:
    human_selection_id: UUID
    content_opportunity_id: UUID
    content_experiment_id: UUID


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize_url(url: str) -> str:
    candidate = url.strip()
    parts = urlsplit(candidate)
    if not parts.scheme or not parts.netloc:
        return candidate.rstrip("/").casefold()
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    ).casefold()


def _candidate_for_document(
    production: ProductionResearchResult,
    document: PageDocument,
) -> SourceCandidate | None:
    document_urls = {
        _normalize_url(url)
        for url in (document.url, document.requested_url, document.final_url)
        if url
    }
    for candidate in production.source_candidates:
        if _normalize_url(candidate.url) in document_urls:
            return candidate
    return None


def _authority_hint(candidate: SourceCandidate | None) -> str | None:
    if candidate is None:
        return None
    if candidate.source_type == "institutional":
        return "institutional_candidate"
    if candidate.source_type == "community_or_review":
        return "audience_observation_candidate"
    if candidate.source_type == "editorial":
        return "secondary_editorial_context"
    if candidate.source_type == "commercial":
        return "commercial_context_only"
    return None


async def persist_discovery_read_documents(
    session: AsyncSession,
    *,
    production: ProductionResearchResult,
) -> dict[str, PersistedPageRef]:
    """Persist already-read Discovery pages as raw sources, never factual Evidence."""

    refs: dict[str, PersistedPageRef] = {}
    for document in production.documents:
        candidate = _candidate_for_document(production, document)
        canonical_url = document.final_url or document.url or document.requested_url
        if not canonical_url:
            raise ValueError("discovery_read_document_url_required")

        source_type = candidate.source_type if candidate is not None else "web"
        commercial_bias = (
            candidate.commercial_bias.value if candidate is not None else None
        )
        provenance: dict[str, object] = {
            "method": "discovery_read",
            "provider": document.provider,
            "query": production.request.query,
            "source_ref": canonical_url,
            "raw_source_only": True,
        }
        if candidate is not None:
            provenance.update(
                {
                    "discovered_by": candidate.provider,
                    "found_via": candidate.found_via,
                    "relation": candidate.relation.value,
                    "intended_use": candidate.intended_use.value,
                    "parent_url": candidate.parent_url,
                }
            )

        registered = await register_source(
            session,
            project_id=production.request.project_id,
            source_type=source_type,
            title=document.title or (candidate.title if candidate is not None else None),
            canonical_url=canonical_url,
            locale=production.request.locale,
            commercial_bias=commercial_bias,
            authority_hint=_authority_hint(candidate),
            captured_at=_parse_datetime(document.captured_at),
            provenance_json=provenance,
        )
        ingested = await ingest_source_document(
            session,
            source_id=registered.source.id,
            content_markdown=document.content,
            fetched_at=_parse_datetime(document.captured_at),
            canonical_url=canonical_url,
            reader=document.provider,
            provider=document.provider,
            metadata_json={
                "discovery_research_query": production.request.query,
                "raw_source_only": True,
                "content_truncated": document.content_truncated,
                "links_truncated": document.links_truncated,
            },
        )
        page_ref = PersistedPageRef(
            source_id=registered.source.id,
            source_document_id=ingested.document.id,
            chunk_ids=tuple(chunk.id for chunk in ingested.chunks),
            canonical_url=canonical_url,
        )
        for url in (document.url, document.requested_url, document.final_url, canonical_url):
            if url:
                refs[_normalize_url(url)] = page_ref

    return refs


def _signal_provenance(
    signal: Signal,
    page_refs: Mapping[str, PersistedPageRef] | None = None,
) -> dict[str, object]:
    provenance = {
        key: value
        for key, value in asdict(signal.provenance).items()
        if value is not None
    }
    provenance["planning_signal_id"] = signal.id
    if signal.source_url and page_refs:
        page_ref = page_refs.get(_normalize_url(signal.source_url))
        if page_ref is not None:
            provenance.update(
                {
                    "source_id": str(page_ref.source_id),
                    "source_document_id": str(page_ref.source_document_id),
                    "source_document_canonical_url": page_ref.canonical_url,
                }
            )
    return provenance


async def _find_existing_signal(
    session: AsyncSession,
    *,
    project_id: UUID,
    signal: Signal,
    page_refs: Mapping[str, PersistedPageRef] | None = None,
) -> DBSignal | None:
    candidates = tuple(
        (
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
            )
        )
        .scalars()
        .all()
    )
    desired = _signal_provenance(signal, page_refs)
    for row in candidates:
        provenance = row.provenance_json or {}
        if provenance.get("planning_signal_id") == signal.id:
            return row

    # Backward-compatible fallback for an older row created before planning_signal_id
    # existed. Exact source + provider/method/locator identity is required so reposts
    # with the same text remain separate observations.
    for row in candidates:
        provenance = row.provenance_json or {}
        if (
            row.source_url == signal.source_url
            and row.external_id == signal.external_id
            and provenance.get("provider") == desired.get("provider")
            and provenance.get("method") == desired.get("method")
            and provenance.get("source_ref") == desired.get("source_ref")
            and provenance.get("locator") == desired.get("locator")
        ):
            return row
    return None


async def _persist_signals(
    session: AsyncSession,
    *,
    project_id: UUID,
    result: OpportunityMapResult,
    page_refs: Mapping[str, PersistedPageRef] | None = None,
) -> dict[str, UUID]:
    signal_ids: dict[str, UUID] = {}
    rows_by_planning_id: dict[str, DBSignal] = {}

    for signal in result.signals:
        existing = await _find_existing_signal(
            session,
            project_id=project_id,
            signal=signal,
            page_refs=page_refs,
        )
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
                provenance_json=_signal_provenance(signal, page_refs),
            )
            session.add(existing)
            await session.flush()
        elif existing.provenance_json.get("planning_signal_id") is None:
            provenance = dict(existing.provenance_json)
            provenance["planning_signal_id"] = signal.id
            existing.provenance_json = provenance

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
    page_refs: Mapping[str, PersistedPageRef] | None = None,
) -> PersistedDiscoveryPlan:
    """Persist pre-ContentCase planning objects without creating a ContentRun."""

    signal_ids = await _persist_signals(
        session,
        project_id=project_id,
        result=result,
        page_refs=page_refs,
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


async def persist_discovery_selection(
    session: AsyncSession,
    *,
    result: OpportunityMapResult,
    planning_refs: PersistedDiscoveryPlan,
) -> PersistedDiscoverySelection:
    """Persist the explicit human selection and its experiment draft, not a ContentCase."""

    selection = result.human_selection
    experiment = result.experiment_draft
    if selection is None or experiment is None:
        raise ValueError("human_selection_required_before_persisting_handoff")

    opportunity_id = planning_refs.opportunity_ids.get(selection.opportunity_id)
    if opportunity_id is None:
        raise ValueError("selected_opportunity_missing_from_persisted_plan")

    existing_selected = tuple(
        (
            await session.execute(
                select(DBContentOpportunity).where(
                    DBContentOpportunity.id.in_(planning_refs.opportunity_ids.values()),
                    DBContentOpportunity.selected_by.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if len(existing_selected) > 1:
        raise ValueError("discovery_plan_has_multiple_persisted_selections")
    if existing_selected:
        existing = existing_selected[0]
        if (
            existing.id != opportunity_id
            or existing.selected_by != selection.selected_by
            or existing.selection_reason != selection.reason
        ):
            raise ValueError("discovery_plan_already_has_different_selection")

    opportunity = await session.get(DBContentOpportunity, opportunity_id)
    if opportunity is None:
        raise ValueError("persisted_selected_opportunity_not_found")

    if opportunity.selected_by is not None and (
        opportunity.selected_by != selection.selected_by
        or opportunity.selection_reason != selection.reason
    ):
        raise ValueError("opportunity_already_selected_with_different_decision")

    selected_at = _parse_datetime(selection.selected_at)
    opportunity.selected_by = selection.selected_by
    opportunity.selected_at = selected_at
    opportunity.selection_reason = selection.reason

    human_selection = (
        await session.execute(
            select(DBHumanSelection)
            .where(
                DBHumanSelection.content_opportunity_id == opportunity.id,
                DBHumanSelection.selected_by == selection.selected_by,
                DBHumanSelection.reason == selection.reason,
            )
            .order_by(DBHumanSelection.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if human_selection is None:
        human_selection = DBHumanSelection(
            content_opportunity_id=opportunity.id,
            selected_by=selection.selected_by,
            reason=selection.reason,
            selected_at=selected_at,
        )
        session.add(human_selection)
        await session.flush()

    experiment_candidates = tuple(
        (
            await session.scalars(
                select(DBContentExperiment)
                .where(
                    DBContentExperiment.content_opportunity_id == opportunity.id,
                    DBContentExperiment.need_hypothesis_id
                    == planning_refs.need_hypothesis_id,
                    DBContentExperiment.hypothesis_version
                    == experiment.hypothesis_version,
                    DBContentExperiment.expected_behaviour
                    == experiment.expected_behaviour,
                )
                .order_by(DBContentExperiment.created_at.asc())
            )
        ).all()
    )
    desired_measurement_plan = list(experiment.measurement_plan)
    desired_metric_definitions = list(experiment.metric_definitions)
    desired_minimum_evidence = list(experiment.minimum_evidence)
    exact_experiments = [
        row
        for row in experiment_candidates
        if row.content_item_id is None
        and row.content_version_id is None
        and row.published_content_id is None
        and row.status == "PLANNED"
        and row.result == "PENDING"
        and list(row.measurement_plan_json) == desired_measurement_plan
        and list(row.metric_definitions_json) == desired_metric_definitions
        and list(row.minimum_evidence_json) == desired_minimum_evidence
    ]
    if len(exact_experiments) > 1:
        raise ValueError("discovery_experiment_exact_duplicate")
    content_experiment = exact_experiments[0] if exact_experiments else None
    if content_experiment is None:
        content_experiment = DBContentExperiment(
            project_id=opportunity.project_id,
            content_opportunity_id=opportunity.id,
            need_hypothesis_id=planning_refs.need_hypothesis_id,
            hypothesis_version=experiment.hypothesis_version,
            expected_behaviour=experiment.expected_behaviour,
            measurement_plan_json=list(experiment.measurement_plan),
            metric_definitions_json=list(experiment.metric_definitions),
            minimum_evidence_json=list(experiment.minimum_evidence),
            status=experiment.status.value,
            result=experiment.result.value,
            observation_refs_json=[],
            alternative_explanations_json=list(
                result.need_hypothesis.alternative_explanations
            ),
        )
        session.add(content_experiment)
        await session.flush()

    return PersistedDiscoverySelection(
        human_selection_id=human_selection.id,
        content_opportunity_id=opportunity.id,
        content_experiment_id=content_experiment.id,
    )