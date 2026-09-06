from dataclasses import dataclass, field
from enum import StrEnum

from app.modules.research.contracts import utc_now_iso


class SignalSourceKind(StrEnum):
    MARKET = "MARKET"
    SEARCH = "SEARCH"
    MOTGU = "MOTGU"


class SignalScope(StrEnum):
    MARKET_WEB = "market_web"
    MOTGU_SITE = "motgu_site"
    MOTGU_DIRECT = "motgu_direct"


class NeedType(StrEnum):
    PAIN = "pain"
    DESIRE = "desire"
    QUESTION = "question"
    CURIOSITY = "curiosity"
    OBJECTION = "objection"


class HypothesisStatus(StrEnum):
    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class QuestionType(StrEnum):
    WHAT = "what"
    WHY = "why"
    HOW = "how"
    WHERE = "where"
    COMPARE = "compare"
    TRUST = "trust"
    PRICE = "price"
    LOGISTICS = "logistics"
    FIT = "fit"
    VISIT = "visit"
    CARE = "care"
    CULTURE = "culture"
    OTHER = "other"


class Intent(StrEnum):
    LEARN = "learn"
    UNDERSTAND = "understand"
    COMPARE = "compare"
    EVALUATE = "evaluate"
    TRUST = "trust"
    PLAN_VISIT = "plan_visit"
    CONSIDER_PURCHASE = "consider_purchase"
    POST_PURCHASE = "post_purchase"


class AudienceStage(StrEnum):
    CURIOUS = "curious"
    EXPLORING = "exploring"
    FIRST_TIME_BUYER = "first_time_buyer"
    EVALUATING = "evaluating"
    READY_TO_VISIT = "ready_to_visit"
    READY_TO_INQUIRE = "ready_to_inquire"
    OWNER = "owner"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContentDecision(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    REFRESH = "REFRESH"
    MERGE = "MERGE"
    LINK_ONLY = "LINK_ONLY"
    DO_NOT_WRITE = "DO_NOT_WRITE"


class OpportunityPriority(StrEnum):
    NOW = "NOW"
    NEXT = "NEXT"
    LATER = "LATER"
    NO = "NO"


class SuggestedContentType(StrEnum):
    JOURNAL = "journal"
    ARTWORK = "artwork"


class JournalRole(StrEnum):
    PILLAR = "pillar"
    CLUSTER = "cluster"


class ExperimentStatus(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    REVIEWED = "REVIEWED"


class ExperimentResult(StrEnum):
    PENDING = "PENDING"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(slots=True, frozen=True)
class SignalProvenance:
    provider: str
    method: str
    artifact_ref: str | None = None
    source_ref: str | None = None
    locator: str | None = None
    version_or_hash: str | None = None


@dataclass(slots=True, frozen=True)
class Signal:
    id: str
    source_kind: SignalSourceKind
    scope: SignalScope
    observed_text: str
    locale: str
    context: str
    captured_at: str
    provenance: SignalProvenance
    fingerprint: str
    source_url: str | None = None
    external_id: str | None = None
    observed_at: str | None = None
    duplicate_of: str | None = None
    independence_group: str | None = None


@dataclass(slots=True, frozen=True)
class QuestionRecord:
    id: str
    query: str
    locale: str
    seed_query: str
    signal_refs: tuple[str, ...]
    question_type: QuestionType
    intent: Intent
    audience_stage: AudienceStage
    need_type: NeedType
    topic_key: str
    confidence: Confidence


@dataclass(slots=True, frozen=True)
class QuestionCluster:
    id: str
    topic_key: str
    intent: Intent
    audience_stage: AudienceStage
    need_type: NeedType
    primary_question: str
    question_ids: tuple[str, ...]
    signal_refs: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class NeedHypothesis:
    id: str
    statement: str
    audience_scope: str
    situation: str
    need_type: NeedType
    origin: str = "founder_proposed"
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    support_signal_refs: tuple[str, ...] = ()
    contradict_signal_refs: tuple[str, ...] = ()
    alternative_explanations: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    version: int = 1


@dataclass(slots=True, frozen=True)
class MotguMaterial:
    ref: str
    kind: str
    description: str


@dataclass(slots=True, frozen=True)
class ExistingContentRef:
    id: str
    primary_question: str
    intent: Intent
    topic_key: str
    stale: bool = False
    covers_answer: bool = False


@dataclass(slots=True, frozen=True)
class ContentOpportunity:
    id: str
    need_hypothesis_id: str
    locale: str
    reader: str
    situation: str
    need: str
    question: str
    intent: Intent
    promise: str
    topic_key: str
    signal_refs: tuple[str, ...]
    motgu_material_refs: tuple[str, ...]
    material_gaps: tuple[str, ...]
    existing_content_refs: tuple[str, ...]
    what_is_actually_new: str
    next_discovery_step: str
    decision: ContentDecision
    priority: OpportunityPriority
    reasons: tuple[str, ...]
    suggested_content_type: SuggestedContentType
    suggested_role: JournalRole | None = None
    version: int = 1
    selected_by: str | None = None
    selected_at: str | None = None
    selection_reason: str | None = None


@dataclass(slots=True, frozen=True)
class NicheCandidate:
    id: str
    audience: str
    need: str
    topic_key: str
    question_pattern: str
    content_gap: str
    motgu_right_to_win: tuple[str, ...]
    suggested_content_refs: tuple[str, ...]
    business_path: str
    signal_refs: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class HumanSelection:
    opportunity_id: str
    selected_by: str
    reason: str
    selected_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True, frozen=True)
class ContentExperimentDraft:
    id: str
    content_opportunity_id: str
    need_hypothesis_id: str
    hypothesis_version: int
    expected_behaviour: str
    measurement_plan: tuple[str, ...]
    metric_definitions: tuple[str, ...]
    minimum_evidence: tuple[str, ...]
    status: ExperimentStatus = ExperimentStatus.PLANNED
    result: ExperimentResult = ExperimentResult.PENDING


@dataclass(slots=True)
class OpportunityMapResult:
    project_id: str
    locale: str
    seed: str
    version: int
    need_hypothesis: NeedHypothesis
    signals: list[Signal] = field(default_factory=list)
    questions: list[QuestionRecord] = field(default_factory=list)
    clusters: list[QuestionCluster] = field(default_factory=list)
    opportunities: list[ContentOpportunity] = field(default_factory=list)
    niche_candidates: list[NicheCandidate] = field(default_factory=list)
    research_gaps: list[str] = field(default_factory=list)
    human_selection: HumanSelection | None = None
    experiment_draft: ContentExperimentDraft | None = None
    created_at: str = field(default_factory=utc_now_iso)
