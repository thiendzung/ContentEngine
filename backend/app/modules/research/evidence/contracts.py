from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from app.modules.research.contracts import ProductionResearchRequest, ProductionResearchResult


class EvidenceRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    CONTEXT_ONLY = "context_only"


@dataclass(slots=True, frozen=True)
class ClaimCandidate:
    statement: str
    source_url: str
    locator: str
    excerpt: str
    relation: EvidenceRelation = EvidenceRelation.SUPPORTS
    claim_type: str = "fact"
    importance: str = "normal"


@dataclass(slots=True, frozen=True)
class PersistedPageRef:
    source_id: UUID
    source_document_id: UUID
    chunk_ids: tuple[UUID, ...]
    canonical_url: str


@dataclass(slots=True, frozen=True)
class PersistedEvidenceLink:
    claim_id: UUID
    evidence_id: UUID
    relation: EvidenceRelation


@dataclass(slots=True, frozen=True)
class EvidenceResearchRequest:
    research: ProductionResearchRequest
    content_opportunity_id: UUID
    need_hypothesis_id: UUID
    max_claims: int = 8
    explicit_candidates: tuple[ClaimCandidate, ...] = ()
    lock_evidence_set: bool = False
    locked_by: str | None = None


@dataclass(slots=True)
class EvidenceResearchResult:
    research: ProductionResearchResult
    content_case_id: UUID
    source_document_ids: list[UUID] = field(default_factory=list)
    claim_ids: list[UUID] = field(default_factory=list)
    evidence_ids: list[UUID] = field(default_factory=list)
    relation_counts: dict[str, int] = field(default_factory=dict)
    evidence_set_id: UUID | None = None
    evidence_set_version: int | None = None
    evidence_set_status: str | None = None
    originality_pack_id: UUID | None = None
    originality_item_count: int = 0
    research_gaps: list[str] = field(default_factory=list)
    artifact_type: str = "evidence_research_report"
    evidence_eligible: bool = False
    artifact_ref: str | None = None
