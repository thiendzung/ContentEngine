"""Customer intelligence domain primitives."""

from app.modules.customer_intelligence.insights import (
    CustomerInsightError,
    CustomerInsightEvidenceCounts,
    customer_insight_evidence_counts,
    derive_insight_key,
    ensure_customer_insight,
    link_customer_insight_signal,
)

__all__ = [
    "CustomerInsightError",
    "CustomerInsightEvidenceCounts",
    "customer_insight_evidence_counts",
    "derive_insight_key",
    "ensure_customer_insight",
    "link_customer_insight_signal",
]
