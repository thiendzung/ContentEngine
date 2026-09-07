"""Evidence research workflow for CE04 PR-E."""

from app.modules.research.evidence.contracts import (
    ClaimCandidate,
    EvidenceRelation,
    EvidenceResearchRequest,
    EvidenceResearchResult,
    OriginalityMaterialInput,
    count_usable_originality_items,
    is_usable_originality_item,
)
from app.modules.research.evidence.service import EvidenceResearchWorkflow

__all__ = [
    "ClaimCandidate",
    "EvidenceRelation",
    "EvidenceResearchRequest",
    "EvidenceResearchResult",
    "OriginalityMaterialInput",
    "count_usable_originality_items",
    "is_usable_originality_item",
    "EvidenceResearchWorkflow",
]
