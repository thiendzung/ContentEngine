from dataclasses import replace

from app.modules.research.budget import BudgetLedger, ResearchBudget, ResearchBudgetExceeded
from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    ManualDeepResearchImport,
    ProviderCallArtifact,
    ResearchBudgetUsage,
    ResearchSignalKind,
    ResearchSpikeResult,
    SearchRequest,
    SourceCandidate,
)
from app.modules.research.providers.base import PageReader, ResearchProviderError, SearchProvider
from app.modules.research.utils import (
    choose_sources,
    dedupe_sources,
    extract_second_hop_candidates,
    validate_public_http_url,
)


class SufficiencyPolicy:
    def __init__(
        self,
        min_question_signals: int = 4,
        min_source_candidates: int = 5,
        min_low_bias_or_evidence_candidates: int = 1,
    ) -> None:
        self.min_question_signals = min_question_signals
        self.min_source_candidates = min_source_candidates
        self.min_low_bias_or_evidence_candidates = min_low_bias_or_evidence_candidates

    def is_sufficient(self, result: ResearchSpikeResult) -> bool:
        question_kinds = {
            ResearchSignalKind.PEOPLE_ALSO_ASK,
            ResearchSignalKind.RELATED_SEARCH,
            ResearchSignalKind.AUTOCOMPLETE,
        }
        question_count = sum(1 for signal in result.signals if signal.kind in question_kinds)
        unique_sources = dedupe_sources(result.source_candidates)
        better_source_count = sum(
            1
            for source in unique_sources
            if source.commercial_bias is CommercialBias.LOW
            or source.intended_use is IntendedUse.EVIDENCE_CANDIDATE
        )
        return (
            question_count >= self.min_question_signals
            and len(unique_sources) >= self.min_source_candidates
            and better_source_count >= self.min_low_bias_or_evidence_candidates
        )


class ResearchSpikeService:
    def __init__(
        self,
        *,
        serper: SearchProvider,
        tavily: SearchProvider | None = None,
        exa: SearchProvider | None = None,
        reader: PageReader | None = None,
        budget: ResearchBudget | None = None,
        sufficiency: SufficiencyPolicy | None = None,
    ) -> None:
        self._serper = serper
        self._tavily = tavily
        self._exa = exa
        self._reader = reader
        self._budget = budget or ResearchBudget()
        self._sufficiency = sufficiency or SufficiencyPolicy()

    async def run(
        self,
        seed: str,
        *,
        locale: str = "en",
        country: str = "us",
        manual_deep_research: ManualDeepResearchImport | None = None,
    ) -> ResearchSpikeResult:
        request = SearchRequest(query=seed.strip(), locale=locale, country=country)
        if not request.query:
            raise ValueError("seed_query_required")

        result = ResearchSpikeResult(seed=request.query, manual_deep_research=manual_deep_research)
        ledger = BudgetLedger(self._budget)

        await self._run_provider(
            self._serper,
            request,
            result,
            ledger,
            reason="default_google_discovery",
        )

        if not self._sufficiency.is_sufficient(result) and self._tavily is not None:
            await self._run_provider(
                self._tavily,
                request,
                result,
                ledger,
                reason="serper_insufficient_or_sales_heavy",
            )

        if not self._sufficiency.is_sufficient(result) and self._exa is not None:
            await self._run_provider(
                self._exa,
                request,
                result,
                ledger,
                reason="deeper_sources_still_needed",
            )

        result.source_candidates = dedupe_sources(result.source_candidates)
        result.selected_sources = choose_sources(
            result.source_candidates,
            self._budget.max_selected_urls,
        )

        if self._reader is not None:
            for source in result.selected_sources:
                if ledger.pages_read >= self._budget.max_pages_read:
                    break
                try:
                    ledger.consume_provider_calls(1, self._reader.name)
                    ledger.consume_page_read()
                    page = await self._reader.read(source.url, query=request.query)
                except (ResearchProviderError, ResearchBudgetExceeded, ValueError) as exc:
                    result.calls.append(
                        ProviderCallArtifact(
                            provider=self._reader.name,
                            operation=(
                                exc.operation if isinstance(exc, ResearchProviderError) else "read"
                            ),
                            query=request.query,
                            purpose="selected_url_read",
                            status="error",
                            result_count=0,
                            raw_excerpt="",
                            reason=str(exc),
                        )
                    )
                    continue
                result.calls.append(
                    replace(
                        page.call,
                        reason=f"selected_source:{source.found_via}:{source.source_type}",
                    )
                )
                result.documents.append(page.document)

        second_hop: list[SourceCandidate] = []
        for document in result.documents:
            second_hop.extend(
                extract_second_hop_candidates(
                    document.content,
                    parent_url=document.url,
                    query=request.query,
                    limit=self._budget.max_second_hop_candidates,
                    linked_urls=(link.url for link in document.links),
                )
            )
        result.second_hop_candidates = choose_sources(
            second_hop,
            self._budget.max_second_hop_candidates,
        )
        result.budget_usage = ResearchBudgetUsage(
            max_provider_calls=self._budget.max_provider_calls,
            provider_calls_used=ledger.provider_calls_used,
            max_pages_read=self._budget.max_pages_read,
            pages_read=ledger.pages_read,
        )
        return result

    async def _run_provider(
        self,
        provider: SearchProvider,
        request: SearchRequest,
        result: ResearchSpikeResult,
        ledger: BudgetLedger,
        *,
        reason: str,
    ) -> None:
        try:
            ledger.consume_provider_calls(provider.estimated_calls(request), provider.name)
            response = await provider.search(request)
        except (ResearchProviderError, ResearchBudgetExceeded) as exc:
            result.calls.append(
                ProviderCallArtifact(
                    provider=provider.name,
                    operation=(
                        exc.operation if isinstance(exc, ResearchProviderError) else "search"
                    ),
                    query=request.query,
                    purpose="discovery_or_source_discovery",
                    status="error",
                    result_count=0,
                    raw_excerpt="",
                    reason=f"{reason}:{exc}",
                )
            )
            return

        result.calls.extend(replace(call, reason=reason) for call in response.calls)
        result.signals.extend(response.signals)
        result.source_candidates.extend(response.sources)


def import_manual_deep_research(report: str, source_urls: list[str]) -> ManualDeepResearchImport:
    cleaned_urls: list[str] = []
    for raw_url in source_urls:
        url = raw_url.strip()
        if not url:
            continue
        cleaned_urls.append(validate_public_http_url(url))
    return ManualDeepResearchImport(report=report.strip(), source_urls=tuple(cleaned_urls))


def mark_source_selected(source: SourceCandidate, reason: str) -> SourceCandidate:
    return replace(source, why_selected=reason.strip() or source.why_selected)
