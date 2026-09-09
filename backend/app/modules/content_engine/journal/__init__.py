"""Journal vertical slice for CE05."""

from app.modules.content_engine.journal.context import (
    MAX_APPROVED_KNOWLEDGE,
    ApprovedKnowledge,
    JournalContext,
    JournalContextError,
    MemoryOverlap,
    PersistedJournalContext,
    build_journal_context,
    persist_journal_context,
)
from app.modules.content_engine.journal.research_handoff import (
    DiscoveryResearchHandoff,
    EvidenceResearchHandoff,
    EvidenceSetHandoff,
    JournalResearchHandoff,
    JournalResearchHandoffError,
    OpportunitySelectionHandoff,
    OriginalityPackHandoff,
    ResearchDecision,
    originality_pack_snapshot_hash,
    select_research_decision,
)

__all__ = [
    "ApprovedKnowledge",
    "JournalContext",
    "JournalContextError",
    "MAX_APPROVED_KNOWLEDGE",
    "MemoryOverlap",
    "PersistedJournalContext",
    "build_journal_context",
    "persist_journal_context",
    "DiscoveryResearchHandoff",
    "EvidenceResearchHandoff",
    "EvidenceSetHandoff",
    "JournalResearchHandoff",
    "JournalResearchHandoffError",
    "OpportunitySelectionHandoff",
    "OriginalityPackHandoff",
    "ResearchDecision",
    "originality_pack_snapshot_hash",
    "select_research_decision",
]
