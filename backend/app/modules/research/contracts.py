from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


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


@dataclass(slots=True, frozen=True)
class SearchRequest:
    query: str
    locale: str = "en"
    country: str = "us"
    limit: int = 10


@dataclass(slots=True, frozen=True)
class SearchSignal:
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
class PageDocument:
    provider: str
    url: str
    content: str
    title: str | None = None


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
    created_at: str = field(default_factory=utc_now_iso)
    calls: list[ProviderCallArtifact] = field(default_factory=list)
    signals: list[SearchSignal] = field(default_factory=list)
    source_candidates: list[SourceCandidate] = field(default_factory=list)
    selected_sources: list[SourceCandidate] = field(default_factory=list)
    documents: list[PageDocument] = field(default_factory=list)
    second_hop_candidates: list[SourceCandidate] = field(default_factory=list)
    manual_deep_research: ManualDeepResearchImport | None = None
    budget_usage: ResearchBudgetUsage | None = None
