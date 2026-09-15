"""Knowledge storage, ingest, provenance, retrieval, admission, and topic graph boundary."""

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
from app.modules.knowledge.originality_pack import (
    OriginalityPackApprovalError,
    approve_originality_pack,
    originality_pack_snapshot_hash,
)
from app.modules.knowledge.topic_graph import (
    KnowledgeTargetType,
    TopicGraphError,
    TopicLinkMethod,
    TopicNodeType,
    TopicRelationType,
    descendant_topic_ids,
    ensure_knowledge_topic_link,
    ensure_topic_edge,
    ensure_topic_node,
    normalize_topic_key,
)
from app.modules.knowledge.topic_models import KnowledgeTopicLink, TopicEdge, TopicNode

__all__ = [
    "EXTRACTION_METHOD",
    "KnowledgeCandidateAdmissionError",
    "KnowledgeTargetType",
    "KnowledgeTopicLink",
    "OriginalityPackApprovalError",
    "TopicEdge",
    "TopicGraphError",
    "TopicLinkMethod",
    "TopicNode",
    "TopicNodeType",
    "TopicRelationType",
    "admit_knowledge_candidate",
    "approve_originality_pack",
    "descendant_topic_ids",
    "deterministic_candidate_summary",
    "ensure_knowledge_topic_link",
    "ensure_topic_edge",
    "ensure_topic_node",
    "extract_knowledge_candidates",
    "normalize_topic_key",
    "originality_pack_snapshot_hash",
    "rebuild_candidate_snapshot",
    "stable_knowledge_candidate_id",
    "verify_candidate_snapshot_lineage",
]
