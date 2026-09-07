from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ResearchSignalKind(StrEnum):
    PEOPLE_ALSO_ASK = "people_also_ask"
    RELATED_SEARCH = "related_search"
    AUTOCOMPLETE = "autocomplete"
    ORGANIC = "organic"
    SOURCE_DISCOVERY = "source_discovery"


class CommercialBias(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class SourceRelation(StrEnum):
    DIRECT = "direct"
    SECOND_HOP = "second_hop"
    INTERMEDIATE = "intermediate"


class IntendedUse(StrEnum):
    DISCOVERY = "discovery"
    EVIDENCE_CANDIDATE = "evidence_candidate"
    CONTEXT_ONLY = "context_only"


class ResearchDepth(StrEnum):
    STANDARD = "standard"
    DEEP = "deep"


class ProviderDecisionStatus(StrEnum):
    CALLED = "called"
    SKIPPED = "skipped"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class SearchRequest:
    query: str
    locale: str = "en"
    country: str = "us"
    limit: int = 10
    parent_url: str | None = None


@dataclass(slots=True, frozen=True)
class SearchSignal:
    """Provider observation; not a normalized Signal or a validated customer need."""

    provider: str
    query: str
    kind: ResearchSignalKind
    text: str
    title: str | None = None
    url: str | None = None
    snippet: str | None = None
    position: int | None = None


@dataclass(slots=True, frozen=True)
class SourceCandidate:
    provider: str
    query: str
    url: str
    title: str
    snippet: str = ""
    source_type: str = "unknown"
    commercial_bias: CommercialBias = CommercialBias.UNKNOWN
    found_via: str = "search"
    relation: SourceRelation = SourceRelation.DIRECT
    intended_use: IntendedUse = IntendedUse.DISCOVERY
    why_selected: str = ""
    parent_url: str | None = None


@dataclass(slots=True, frozen=True)
class ProviderCallArtifact:
    provider: str
    operation: str
    query: str
    purpose: str
    status: str
    result_count: int
    raw_excerpt: str
    reason: str = ""
    captured_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True, frozen=True)
class ProviderResponse:
    signals: tuple[SearchSignal, ...]
    sources: tuple[SourceCandidate, ...]
    calls: tuple[ProviderCallArtifact, ...]


@dataclass(slots=True, frozen=True)
class PageLink:
    url: str
    text: str = ""


@dataclass(slots=True, frozen=True)
class PageDocument:
    provider: str
    url: str
    content: str
    title: str | None = None
    requested_url: str | None = None
    final_url: str | None = None
    provider_timestamp: str | int | float | None = None
    captured_at: str = field(default_factory=utc_now_iso)
    links: tuple[PageLink, ...] = ()
    content_truncated: bool = False
    links_truncated: bool = False


@dataclass(slots=True, frozen=True)
class PageReadResponse:
    document: PageDocument
    call: ProviderCallArtifact


@dataclass(slots=True, frozen=True)
class ManualDeepResearchImport:
    report: str
    source_urls: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class ResearchBudgetUsage:
    max_provider_calls: int
    provider_calls_used: int
    max_pages_read: int
    pages_read: int


@dataclass(slots=True)
class ResearchSpikeResult:
    seed: str
    seed_origin: str = "founder_proposed"
    hypothesis_status: str = "PROPOSED"
    created_at: str = field(default_factory=utc_now_iso)
    calls: list[ProviderCallArtifact] = field(default_factory=list)
    signals: list[SearchSignal] = field(default_factory=list)
    source_candidates: list[SourceCandidate] = field(default_factory=list)
    selected_sources: list[SourceCandidate] = field(default_factory=list)
    documents: list[PageDocument] = field(default_factory=list)
    second_hop_candidates: list[SourceCandidate] = field(default_factory=list)
    manual_deep_research: ManualDeepResearchImport | None = None
    budget_usage: ResearchBudgetUsage | None = None


@dataclass(slots=True, frozen=True)
class ProductionResearchRequest:
    project_id: UUID
    query: str
    locale: str = "en"
    country: str = "us"
    limit: int = 10
    depth: ResearchDepth = ResearchDepth.STANDARD
    max_pages_to_read: int = 1
    preferred_source_types: tuple[str, ...] = ()
    parent_url: str | None = None


@dataclass(slots=True, frozen=True)
class InternalKnowledgeHit:
    chunk_ref: str
    source_ref: str
    text: str
    source_type: str
    authority_hint: str | None
    commercial_bias: str | None
    exact_phrase: bool
    matched_terms: tuple[str, ...]
    ranking_reasons: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class ProviderDecision:
    provider: str
    status: ProviderDecisionStatus
    reason: str
    failure_class: str | None = None


@dataclass(slots=True)
class ProductionResearchResult:
    request: ProductionResearchRequest
    internal_hits: list[InternalKnowledgeHit] = field(default_factory=list)
    decisions: list[ProviderDecision] = field(default_factory=list)
    calls: list[ProviderCallArtifact] = field(default_factory=list)
    signals: list[SearchSignal] = field(default_factory=list)
    source_candidates: list[SourceCandidate] = field(default_factory=list)
    selected_sources: list[SourceCandidate] = field(default_factory=list)
    documents: list[PageDocument] = field(default_factory=list)
    stop_reason: str = "not_started"
    sufficient: bool = False

    @property
    def external_provider_calls(self) -> int:
        return sum(
            1
            for decision in self.decisions
            if decision.status in {ProviderDecisionStatus.CALLED, ProviderDecisionStatus.FAILED}
            and decision.provider != "internal_knowledge"
        )
