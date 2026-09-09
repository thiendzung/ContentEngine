"""Knowledge storage, ingest, provenance, retrieval, and admission boundary."""

from app.modules.knowledge.admission import (
    KnowledgeCandidateAdmissionError,
    admit_knowledge_candidate,
    verify_candidate_snapshot_lineage,
)
from app.modules.knowledge.candidates import (
    EXTRACTION_METHOD,
    deterministic_candidate_summary,
    extract_knowledge_candidates,
    rebuild_candidate_snapshot,
    stable_knowledge_candidate_id,
)

__all__ = [
    "EXTRACTION_METHOD",
    "KnowledgeCandidateAdmissionError",
    "admit_knowledge_candidate",
    "verify_candidate_snapshot_lineage",
    "deterministic_candidate_summary",
    "extract_knowledge_candidates",
    "rebuild_candidate_snapshot",
    "stable_knowledge_candidate_id",
]
