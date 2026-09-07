from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.research.contracts import (
    CommercialBias,
    PageDocument,
    ProductionResearchRequest,
    ProductionResearchResult,
    ProviderDecisionStatus,
    ResearchSpikeResult,
    SourceCandidate,
    utc_now_iso,
)
from app.modules.research.discovery.artifact import persist_discovery_artifact
from app.modules.research.keyword_plan.contracts import (
    ContentOpportunity,
    OpportunityMapResult,
    Signal,
    SignalScope,
    SignalSourceKind,
)
from app.modules.research.keyword_plan.normalize import make_observed_signal
from app.modules.research.keyword_plan.service import (
    OpportunityMapRequest,
    OpportunityMapService,
)


class ProductionResearchRunner(Protocol):
    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> ProductionResearchResult: ...


@dataclass(slots=True, frozen=True)
class MarketObservation:
    source_url: str
    observed_text: str
    locator: str
    external_id: str | None = None


@dataclass(slots=True, frozen=True)
class DiscoverySourceMetadata:
    url: str
    title: str
    provider: str
    source_type: str
    commercial_bias: CommercialBias
    authority_hint: str | None
    metadata_reason: str
    rank_position: int | None
    readable: bool
    relation: str
    parent_url: str | None


@dataclass(slots=True, frozen=True)
class DiscoveryWorkflowRequest:
    research: ProductionResearchRequest
    opportunity: OpportunityMapRequest
    artifact_ref: str | None = None
    market_observations: tuple[MarketObservation, ...] = ()


@dataclass(slots=True, frozen=True)
class OpportunityHandoff:
    opportunity_id: str
    need_hypothesis_id: str
    locale: str
    signal_refs: tuple[str, ...]
    experiment_draft_id: str


@dataclass(slots=True)
class DiscoveryWorkflowResult:
    research: ProductionResearchResult
    source_metadata: list[DiscoverySourceMetadata]
    opportunity_map: OpportunityMapResult
    research_gaps: list[str] = field(default_factory=list)
    artifact_type: str = "discovery_research_report"
    evidence_eligible: bool = False
    artifact_ref: str | None = None


class DiscoveryResearchWorkflow:
    """Bridge production research into the existing Opportunity Map planning contract."""

    def __init__(
        self,
        *,
        router: ProductionResearchRunner,
        opportunity_service: OpportunityMapService | None = None,
    ) -> None:
        self._router = router
        self._opportunity_service = opportunity_service or OpportunityMapService()

    async def run(
        self,
        session: AsyncSession,
        *,
        request: DiscoveryWorkflowRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> DiscoveryWorkflowResult:
        self._validate_request(request, run_id=run_id, step_run_id=step_run_id)

        production = await self._router.run(
            session,
            request=request.research,
            run_id=run_id,
            step_run_id=step_run_id,
        )
        source_metadata = self._source_metadata(production)
        market_signals, observation_gaps = self._market_signals(
            production,
            request.market_observations,
            artifact_ref=request.artifact_ref,
        )
        gaps = [*observation_gaps, *self._production_gaps(production, market_signals)]

        spike = ResearchSpikeResult(
            seed=production.request.query,
            seed_origin=request.opportunity.seed_origin,
            hypothesis_status="PROPOSED",
            calls=list(production.calls),
            signals=list(production.signals),
            source_candidates=list(production.source_candidates),
            selected_sources=list(production.selected_sources),
            documents=list(production.documents),
        )
        opportunity_request = replace(
            request.opportunity,
            artifact_ref=request.artifact_ref,
            extra_signals=(*request.opportunity.extra_signals, *market_signals),
            missing_evidence=tuple(
                dict.fromkeys((*request.opportunity.missing_evidence, *gaps))
            ),
        )
        opportunity_map = self._opportunity_service.build(spike, opportunity_request)
        combined_gaps = list(dict.fromkeys((*gaps, *opportunity_map.research_gaps)))
        opportunity_map.research_gaps = combined_gaps

        result = DiscoveryWorkflowResult(
            research=production,
            source_metadata=source_metadata,
            opportunity_map=opportunity_map,
            research_gaps=combined_gaps,
        )
        if run_id is not None and step_run_id is not None:
            artifact = await persist_discovery_artifact(
                session,
                run_id=run_id,
                step_run_id=step_run_id,
                result=result,
            )
            result.artifact_ref = str(artifact.id)
        return result

    def select(
        self,
        result: DiscoveryWorkflowResult,
        *,
        opportunity_id: str,
        selected_by: str,
        reason: str,
    ) -> DiscoveryWorkflowResult:
        result.opportunity_map = self._opportunity_service.select(
            result.opportunity_map,
            opportunity_id=opportunity_id,
            selected_by=selected_by,
            reason=reason,
        )
        return result

    def handoff(self, result: DiscoveryWorkflowResult) -> OpportunityHandoff:
        selection = result.opportunity_map.human_selection
        experiment = result.opportunity_map.experiment_draft
        if selection is None or experiment is None:
            raise ValueError("human_selection_required_before_opportunity_handoff")

        selected = self._selected_opportunity(result.opportunity_map, selection.opportunity_id)
        return OpportunityHandoff(
            opportunity_id=selected.id,
            need_hypothesis_id=selected.need_hypothesis_id,
            locale=selected.locale,
            signal_refs=selected.signal_refs,
            experiment_draft_id=experiment.id,
        )

    def _validate_request(
        self,
        request: DiscoveryWorkflowRequest,
        *,
        run_id: UUID | None,
        step_run_id: UUID | None,
    ) -> None:
        if request.research.locale != request.opportunity.locale:
            raise ValueError("discovery_locale_mismatch")
        if (run_id is None) != (step_run_id is None):
            raise ValueError("run_id_and_step_run_id_must_be_provided_together")

    def _market_signals(
        self,
        production: ProductionResearchResult,
        observations: tuple[MarketObservation, ...],
        *,
        artifact_ref: str | None,
    ) -> tuple[list[Signal], list[str]]:
        readable = self._readable_document_urls(production)
        captured_at = utc_now_iso()
        signals: list[Signal] = []
        gaps: list[str] = []

        for observation in observations:
            source_url = observation.source_url.strip()
            observed_text = observation.observed_text.strip()
            locator = observation.locator.strip()
            if not source_url:
                raise ValueError("market_observation_source_url_required")
            if not observed_text:
                raise ValueError("market_observation_text_required")
            if not locator:
                raise ValueError("market_observation_locator_required")

            document = readable.get(self._url_key(source_url))
            if document is None:
                gaps.append(
                    "MARKET observation skipped because its source was not read successfully: "
                    f"{source_url}"
                )
                continue
            if not self._observation_is_present(observed_text, document.content):
                gaps.append(
                    "MARKET observation skipped because its text was not found in the "
                    f"read source: {source_url}"
                )
                continue

            signals.append(
                make_observed_signal(
                    source_kind=SignalSourceKind.MARKET,
                    scope=SignalScope.MARKET_WEB,
                    observed_text=observed_text,
                    locale=production.request.locale,
                    provider=document.provider,
                    method="read_observation",
                    context=f"readable_market_observation:{production.request.query}",
                    captured_at=captured_at,
                    source_url=source_url,
                    external_id=observation.external_id,
                    artifact_ref=artifact_ref,
                    locator=locator,
                )
            )
        return signals, gaps

    def _production_gaps(
        self,
        production: ProductionResearchResult,
        market_signals: list[Signal],
    ) -> list[str]:
        gaps: list[str] = []
        if not production.sufficient:
            gaps.append(
                "Production discovery ended without meeting the bounded sufficiency policy: "
                f"{production.stop_reason}."
            )
        failures = [
            decision
            for decision in production.decisions
            if decision.status is ProviderDecisionStatus.FAILED
        ]
        for decision in failures:
            failure = decision.failure_class or "unknown_failure"
            gaps.append(f"Provider {decision.provider} failed during discovery: {failure}.")
        if production.internal_hits and not production.signals:
            gaps.append(
                "Internal knowledge may provide context but does not automatically prove "
                "external audience demand or customer truth."
            )
        if not market_signals:
            gaps.append("No readable MARKET observation was normalized in this discovery run.")
        return gaps

    def _source_metadata(
        self,
        production: ProductionResearchResult,
    ) -> list[DiscoverySourceMetadata]:
        positions: dict[str, int] = {}
        for signal in production.signals:
            if signal.url is None or signal.position is None:
                continue
            key = self._url_key(signal.url)
            current = positions.get(key)
            if current is None or signal.position < current:
                positions[key] = signal.position

        readable_urls = self._readable_document_urls(production)
        output: list[DiscoverySourceMetadata] = []
        for source in production.source_candidates:
            authority_hint = self._authority_hint(source)
            reason = source.why_selected.strip() or "Source metadata derived conservatively."
            reason = f"{reason} Search rank/provider score is excluded from authority."
            output.append(
                DiscoverySourceMetadata(
                    url=source.url,
                    title=source.title,
                    provider=source.provider,
                    source_type=source.source_type,
                    commercial_bias=source.commercial_bias,
                    authority_hint=authority_hint,
                    metadata_reason=reason,
                    rank_position=positions.get(self._url_key(source.url)),
                    readable=self._url_key(source.url) in readable_urls,
                    relation=source.relation.value,
                    parent_url=source.parent_url,
                )
            )
        return output

    def _authority_hint(self, source: SourceCandidate) -> str | None:
        if source.source_type == "institutional":
            return "institutional_candidate"
        if source.source_type == "community_or_review":
            return "audience_observation_candidate"
        if source.source_type == "editorial":
            return "secondary_editorial_context"
        if source.source_type == "commercial":
            return "commercial_context_only"
        return None

    def _readable_document_urls(
        self,
        production: ProductionResearchResult,
    ) -> dict[str, PageDocument]:
        readable: dict[str, PageDocument] = {}
        for document in production.documents:
            for url in (document.url, document.requested_url, document.final_url):
                if url:
                    readable[self._url_key(url)] = document
        return readable

    def _selected_opportunity(
        self,
        result: OpportunityMapResult,
        opportunity_id: str,
    ) -> ContentOpportunity:
        for opportunity in result.opportunities:
            if opportunity.id == opportunity_id:
                return opportunity
        raise ValueError("selected_opportunity_missing")

    def _observation_is_present(self, observed_text: str, document_content: str) -> bool:
        observed = re.sub(r"\s+", " ", observed_text).strip().casefold()
        document = re.sub(r"\s+", " ", document_content).strip().casefold()
        return bool(observed) and observed in document

    def _url_key(self, url: str) -> str:
        return url.strip().rstrip("/").casefold()
