from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.harness.persistence import load_budget_usage
from app.modules.harness.policy import (
    BudgetExceededError,
    BudgetLimits,
    BudgetUsage,
    enforce_budget,
)
from app.modules.harness.runtime import (
    ToolRequest,
    ToolResponse,
    complete_tool_call,
    fail_tool_call,
    start_tool_call,
)
from app.modules.knowledge.retrieval import RetrievalRequest, retrieve_chunks
from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    InternalKnowledgeHit,
    ProductionResearchRequest,
    ProductionResearchResult,
    ProviderCallArtifact,
    ProviderDecision,
    ProviderDecisionStatus,
    ProviderResponse,
    ResearchDepth,
    ResearchSignalKind,
    SearchRequest,
    SourceCandidate,
)
from app.modules.research.providers.base import PageReader, ResearchProviderError, SearchProvider
from app.modules.research.utils import choose_sources, dedupe_sources


@dataclass(frozen=True)
class ProductionSufficiencyPolicy:
    min_internal_hits: int = 3
    min_question_signals: int = 3
    min_source_candidates: int = 3
    min_better_sources: int = 1

    def internal_is_sufficient(self, hits: list[InternalKnowledgeHit]) -> bool:
        if len(hits) < self.min_internal_hits:
            return False
        return any(hit.exact_phrase for hit in hits) or sum(
            len(hit.matched_terms) for hit in hits
        ) >= self.min_internal_hits

    def external_is_sufficient(self, result: ProductionResearchResult) -> bool:
        question_kinds = {
            ResearchSignalKind.PEOPLE_ALSO_ASK,
            ResearchSignalKind.RELATED_SEARCH,
            ResearchSignalKind.AUTOCOMPLETE,
        }
        question_count = sum(1 for signal in result.signals if signal.kind in question_kinds)
        unique_sources = dedupe_sources(result.source_candidates)
        better_sources = sum(
            1
            for source in unique_sources
            if source.commercial_bias is CommercialBias.LOW
            or source.intended_use is IntendedUse.EVIDENCE_CANDIDATE
        )
        return (
            question_count >= self.min_question_signals
            and len(unique_sources) >= self.min_source_candidates
            and better_sources >= self.min_better_sources
        )


@dataclass(slots=True)
class _TransientUsage:
    tool_calls: int = 0


class ResearchRouter:
    """Bounded production provider routing on top of CE03 telemetry/budget primitives."""

    def __init__(
        self,
        *,
        serper: SearchProvider,
        tavily: SearchProvider | None = None,
        exa: SearchProvider | None = None,
        reader: PageReader | None = None,
        budget_limits: BudgetLimits | None = None,
        sufficiency: ProductionSufficiencyPolicy | None = None,
    ) -> None:
        self._serper = serper
        self._tavily = tavily
        self._exa = exa
        self._reader = reader
        self._budget_limits = budget_limits or BudgetLimits(max_tool_calls=4)
        self._sufficiency = sufficiency or ProductionSufficiencyPolicy()

    async def run(
        self,
        session: AsyncSession,
        *,
        request: ProductionResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> ProductionResearchResult:
        query = request.query.strip()
        if not query:
            raise ValueError("research_query_required")
        if request.limit < 1 or request.limit > 50:
            raise ValueError("research_limit_must_be_between_1_and_50")
        if request.max_pages_to_read < 0:
            raise ValueError("max_pages_to_read_must_be_non_negative")

        normalized_request = replace(request, query=query)
        result = ProductionResearchResult(request=normalized_request)
        transient_usage = _TransientUsage()

        await self._load_internal_knowledge(session, result)
        if self._sufficiency.internal_is_sufficient(result.internal_hits):
            result.sufficient = True
            result.stop_reason = "internal_knowledge_sufficient"
            result.decisions.append(
                ProviderDecision(
                    provider="internal_knowledge",
                    status=ProviderDecisionStatus.STOPPED,
                    reason="sufficient_without_external_search",
                )
            )
            self._mark_external_skipped(result, "internal_knowledge_sufficient")
            return result

        result.decisions.append(
            ProviderDecision(
                provider="internal_knowledge",
                status=ProviderDecisionStatus.CALLED,
                reason="insufficient_for_request_external_search_required",
            )
        )

        search_request = SearchRequest(
            query=normalized_request.query,
            locale=normalized_request.locale,
            country=normalized_request.country,
            limit=normalized_request.limit,
        )

        try:
            await self._search_provider(
                session,
                provider=self._serper,
                request=search_request,
                result=result,
                reason="default_google_discovery",
                run_id=run_id,
                step_run_id=step_run_id,
                transient_usage=transient_usage,
            )
        except BudgetExceededError as exc:
            result.stop_reason = "budget_exceeded_before_serper"
            result.decisions.append(
                ProviderDecision(
                    provider=self._serper.name,
                    status=ProviderDecisionStatus.STOPPED,
                    reason=str(exc),
                    failure_class="budget_exceeded",
                )
            )
            self._mark_external_skipped(result, "budget_exceeded")
            return result

        result.source_candidates = dedupe_sources(result.source_candidates)
        if self._sufficiency.external_is_sufficient(result):
            search_stop_reason = "serper_sufficient"
            self._mark_search_fallbacks_skipped(result, search_stop_reason)
        else:
            search_stop_reason = await self._run_single_fallback(
                session,
                search_request=search_request,
                result=result,
                run_id=run_id,
                step_run_id=step_run_id,
                transient_usage=transient_usage,
            )

        result.source_candidates = dedupe_sources(result.source_candidates)
        result.selected_sources = choose_sources(
            result.source_candidates,
            self._selected_source_limit(normalized_request),
        )

        if self._reader is not None and normalized_request.max_pages_to_read > 0:
            await self._read_selected_pages(
                session,
                result=result,
                run_id=run_id,
                step_run_id=step_run_id,
                transient_usage=transient_usage,
            )
        elif self._reader is None:
            result.decisions.append(
                ProviderDecision(
                    provider="jina",
                    status=ProviderDecisionStatus.SKIPPED,
                    reason="reader_not_configured",
                )
            )
        else:
            result.decisions.append(
                ProviderDecision(
                    provider=self._reader.name,
                    status=ProviderDecisionStatus.SKIPPED,
                    reason="page_read_limit_zero",
                )
            )

        result.sufficient = self._sufficiency.external_is_sufficient(result)
        if result.sufficient:
            result.stop_reason = search_stop_reason
        elif search_stop_reason.startswith("budget_exceeded"):
            result.stop_reason = search_stop_reason
        else:
            result.stop_reason = "bounded_search_exhausted"
        return result

    async def _load_internal_knowledge(
        self,
        session: AsyncSession,
        result: ProductionResearchResult,
    ) -> None:
        request = result.request
        hits = await retrieve_chunks(
            session,
            request=RetrievalRequest(
                project_id=request.project_id,
                query=request.query,
                locale=request.locale,
                limit=min(request.limit, 10),
                preferred_source_types=request.preferred_source_types,
            ),
        )
        result.internal_hits.extend(
            InternalKnowledgeHit(
                chunk_ref=str(hit.chunk_id),
                source_ref=str(hit.source_id),
                text=hit.text,
                source_type=hit.source_type,
                authority_hint=hit.authority_hint,
                commercial_bias=hit.commercial_bias,
                exact_phrase=hit.exact_phrase,
                matched_terms=hit.matched_terms,
                ranking_reasons=hit.ranking_reasons,
            )
            for hit in hits
        )

    async def _run_single_fallback(
        self,
        session: AsyncSession,
        *,
        search_request: SearchRequest,
        result: ProductionResearchResult,
        run_id: UUID | None,
        step_run_id: UUID | None,
        transient_usage: _TransientUsage,
    ) -> str:
        provider, reason = self._fallback_for(result.request.depth)
        if provider is None:
            self._mark_search_fallbacks_skipped(result, "no_fallback_configured")
            return "no_fallback_configured"

        other = self._exa if provider is self._tavily else self._tavily
        if other is not None:
            result.decisions.append(
                ProviderDecision(
                    provider=other.name,
                    status=ProviderDecisionStatus.SKIPPED,
                    reason=f"bounded_single_fallback_selected:{provider.name}",
                )
            )

        try:
            await self._search_provider(
                session,
                provider=provider,
                request=search_request,
                result=result,
                reason=reason,
                run_id=run_id,
                step_run_id=step_run_id,
                transient_usage=transient_usage,
            )
        except BudgetExceededError as exc:
            result.decisions.append(
                ProviderDecision(
                    provider=provider.name,
                    status=ProviderDecisionStatus.STOPPED,
                    reason=str(exc),
                    failure_class="budget_exceeded",
                )
            )
            return f"budget_exceeded_before_{provider.name}"

        result.source_candidates = dedupe_sources(result.source_candidates)
        if self._sufficiency.external_is_sufficient(result):
            return f"{provider.name}_sufficient"
        return f"{provider.name}_insufficient_bounded_stop"

    def _fallback_for(self, depth: ResearchDepth) -> tuple[SearchProvider | None, str]:
        if depth is ResearchDepth.DEEP:
            if self._exa is not None:
                return self._exa, "deep_or_second_hop_sources_required"
            if self._tavily is not None:
                return self._tavily, "exa_unavailable_use_tavily_once"
            return None, "no_deep_fallback_configured"
        if self._tavily is not None:
            return self._tavily, "serper_insufficient_or_sales_heavy"
        if self._exa is not None:
            return self._exa, "tavily_unavailable_use_exa_once"
        return None, "no_standard_fallback_configured"

    async def _search_provider(
        self,
        session: AsyncSession,
        *,
        provider: SearchProvider,
        request: SearchRequest,
        result: ProductionResearchResult,
        reason: str,
        run_id: UUID | None,
        step_run_id: UUID | None,
        transient_usage: _TransientUsage,
    ) -> None:
        await self._enforce_next_tool_budget(
            session,
            run_id=run_id,
            step_run_id=step_run_id,
            transient_usage=transient_usage,
        )
        tool_call_id = await self._start_telemetry(
            session,
            run_id=run_id,
            step_run_id=step_run_id,
            provider=provider.name,
            operation="search",
            payload={
                "query": request.query,
                "locale": request.locale,
                "country": request.country,
                "limit": request.limit,
                "reason": reason,
            },
        )
        transient_usage.tool_calls += 1
        try:
            response = await provider.search(request)
        except ResearchProviderError as exc:
            await self._fail_telemetry(
                session,
                call_id=tool_call_id,
                failure_class=exc.failure_class,
            )
            result.decisions.append(
                ProviderDecision(
                    provider=provider.name,
                    status=ProviderDecisionStatus.FAILED,
                    reason=f"{reason}:{exc}",
                    failure_class=exc.failure_class,
                )
            )
            return

        await self._complete_telemetry(session, call_id=tool_call_id)
        result.decisions.append(
            ProviderDecision(
                provider=provider.name,
                status=ProviderDecisionStatus.CALLED,
                reason=reason,
            )
        )
        self._merge_provider_response(result, response, reason=reason)

    async def _read_selected_pages(
        self,
        session: AsyncSession,
        *,
        result: ProductionResearchResult,
        run_id: UUID | None,
        step_run_id: UUID | None,
        transient_usage: _TransientUsage,
    ) -> None:
        assert self._reader is not None
        limit = min(result.request.max_pages_to_read, len(result.selected_sources))
        for source in result.selected_sources[:limit]:
            try:
                await self._enforce_next_tool_budget(
                    session,
                    run_id=run_id,
                    step_run_id=step_run_id,
                    transient_usage=transient_usage,
                )
            except BudgetExceededError as exc:
                result.decisions.append(
                    ProviderDecision(
                        provider=self._reader.name,
                        status=ProviderDecisionStatus.STOPPED,
                        reason=str(exc),
                        failure_class="budget_exceeded",
                    )
                )
                return

            tool_call_id = await self._start_telemetry(
                session,
                run_id=run_id,
                step_run_id=step_run_id,
                provider=self._reader.name,
                operation="read",
                payload={
                    "url": source.url,
                    "query": result.request.query,
                    "reason": f"selected_source:{source.found_via}",
                },
            )
            transient_usage.tool_calls += 1
            try:
                page = await self._reader.read(source.url, query=result.request.query)
            except ResearchProviderError as exc:
                await self._fail_telemetry(
                    session,
                    call_id=tool_call_id,
                    failure_class=exc.failure_class,
                )
                result.decisions.append(
                    ProviderDecision(
                        provider=self._reader.name,
                        status=ProviderDecisionStatus.FAILED,
                        reason=f"selected_url_read:{exc}",
                        failure_class=exc.failure_class,
                    )
                )
                continue

            await self._complete_telemetry(session, call_id=tool_call_id)
            result.calls.append(
                replace(
                    page.call,
                    reason=f"selected_source:{source.found_via}:{source.source_type}",
                )
            )
            result.documents.append(page.document)
            result.decisions.append(
                ProviderDecision(
                    provider=self._reader.name,
                    status=ProviderDecisionStatus.CALLED,
                    reason=f"selected_url:{source.url}",
                )
            )

    async def _enforce_next_tool_budget(
        self,
        session: AsyncSession,
        *,
        run_id: UUID | None,
        step_run_id: UUID | None,
        transient_usage: _TransientUsage,
    ) -> None:
        if run_id is not None:
            usage = await load_budget_usage(
                session,
                run_id=run_id,
                step_run_id=step_run_id,
            )
            prospective = replace(usage, tool_calls=usage.tool_calls + 1)
        else:
            prospective = BudgetUsage(tool_calls=transient_usage.tool_calls + 1)
        enforce_budget(self._budget_limits, prospective)

    async def _start_telemetry(
        self,
        session: AsyncSession,
        *,
        run_id: UUID | None,
        step_run_id: UUID | None,
        provider: str,
        operation: str,
        payload: dict[str, object],
    ) -> UUID | None:
        if run_id is None:
            return None
        call = await start_tool_call(
            session,
            run_id=run_id,
            step_run_id=step_run_id,
            request=ToolRequest(
                tool_key=f"research.{provider}.{operation}",
                payload=payload,
            ),
        )
        return call.id

    async def _complete_telemetry(
        self,
        session: AsyncSession,
        *,
        call_id: UUID | None,
    ) -> None:
        if call_id is None:
            return
        await complete_tool_call(
            session,
            call_id=call_id,
            response=ToolResponse(result_ref=f"tool_call:{call_id}"),
        )

    async def _fail_telemetry(
        self,
        session: AsyncSession,
        *,
        call_id: UUID | None,
        failure_class: str,
    ) -> None:
        if call_id is None:
            return
        await fail_tool_call(
            session,
            call_id=call_id,
            error_class=failure_class,
        )

    @staticmethod
    def _merge_provider_response(
        result: ProductionResearchResult,
        response: ProviderResponse,
        *,
        reason: str,
    ) -> None:
        result.signals.extend(response.signals)
        result.source_candidates.extend(response.sources)
        result.calls.extend(replace(call, reason=reason) for call in response.calls)

    def _selected_source_limit(self, request: ProductionResearchRequest) -> int:
        max_sources = self._budget_limits.max_research_sources
        if max_sources is None:
            return max(request.max_pages_to_read, 1)
        return max(1, min(max_sources, max(request.max_pages_to_read, 1)))

    def _mark_search_fallbacks_skipped(
        self,
        result: ProductionResearchResult,
        reason: str,
    ) -> None:
        called = {decision.provider for decision in result.decisions}
        for provider in (self._tavily, self._exa):
            if provider is None or provider.name in called:
                continue
            result.decisions.append(
                ProviderDecision(
                    provider=provider.name,
                    status=ProviderDecisionStatus.SKIPPED,
                    reason=reason,
                )
            )

    def _mark_external_skipped(
        self,
        result: ProductionResearchResult,
        reason: str,
    ) -> None:
        providers: list[str] = [self._serper.name]
        providers.extend(
            provider.name
            for provider in (self._tavily, self._exa, self._reader)
            if provider is not None
        )
        for provider in dict.fromkeys(providers):
            result.decisions.append(
                ProviderDecision(
                    provider=provider,
                    status=ProviderDecisionStatus.SKIPPED,
                    reason=reason,
                )
            )
