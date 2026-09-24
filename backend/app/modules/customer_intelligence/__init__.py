"""Customer intelligence domain primitives."""

from app.modules.customer_intelligence.insights import (
    CustomerInsightError,
    CustomerInsightEvidenceCounts,
    customer_insight_evidence_counts,
    derive_insight_key,
    ensure_customer_insight,
    link_customer_insight_signal,
    review_customer_insight,
)
from app.modules.customer_intelligence.intake import (
    CustomerInsightCandidateInput,
    CustomerInsightCandidateResult,
    CustomerInsightIntakeError,
    persist_customer_insight_candidate,
)

__all__ = [
    "CustomerInsightCandidateInput",
    "CustomerInsightCandidateResult",
    "CustomerInsightIntakeError",
    "CustomerInsightError",
    "CustomerInsightEvidenceCounts",
    "customer_insight_evidence_counts",
    "derive_insight_key",
    "ensure_customer_insight",
    "link_customer_insight_signal",
    "persist_customer_insight_candidate",
    "review_customer_insight",
]
