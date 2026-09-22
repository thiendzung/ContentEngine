from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import AudienceHypothesis, Signal, utc_now
from app.modules.customer_intelligence.models import (
    CustomerInsight,
    CustomerInsightReview,
    CustomerInsightSignal,
)

InsightType = Literal[
    "job",
    "pain",
    "desire",
    "question",
    "fear",
    "objection",
    "barrier",
    "trigger",
    "decision_factor",
    "trust_builder",
    "trust_breaker",
    "language",
    "behaviour",
    "expectation",
    "post_purchase_need",
    "referral_trigger",
    "repeat_purchase_trigger",
]
InsightStatus = Literal[
    "CANDIDATE",
    "TESTING",
    "SUPPORTED",
    "REJECTED",
    "INSUFFICIENT_EVIDENCE",
]
InsightSignalRelation = Literal["supports", "contradicts", "context"]

_INSIGHT_TYPES = {
    "job",
    "pain",
    "desire",
    "question",
    "fear",
    "objection",
    "barrier",
    "trigger",
    "decision_factor",
    "trust_builder",
    "trust_breaker",
    "language",
    "behaviour",
    "expectation",
    "post_purchase_need",
    "referral_trigger",
    "repeat_purchase_trigger",
}
_INSIGHT_STATUSES = {
    "CANDIDATE",
    "TESTING",
    "SUPPORTED",
    "REJECTED",
    "INSUFFICIENT_EVIDENCE",
}
_RELATIONS = {"supports", "contradicts", "context"}


class CustomerInsightError(ValueError):
    """Raised when a CustomerInsight mutation would violate a durable invariant."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(slots=True, frozen=True)
class CustomerInsightEvidenceCounts:
    supports: int
    contradicts: int
    context: int
    independent_supports: int
    independent_contradicts: int
    independent_context: int


def _required_text(value: str, code: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise CustomerInsightError(code)
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _string_list(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def _key_text(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    return re.sub(r"\s+", " ", normalized)


def derive_insight_key(
    *,
    insight_type: str,
    statement: str,
    audience_hypothesis_id: UUID | None,
    situation: str | None,
) -> str:
    """Derive a deterministic v1 logical key from the initial insight identity."""

    payload = "\x1f".join(
        (
            insight_type,
            _key_text(statement),
            str(audience_hypothesis_id or ""),
            _key_text(situation),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _load_audience(
    session: AsyncSession,
    *,
    audience_hypothesis_id: UUID,
    project_id: UUID,
) -> AudienceHypothesis:
    audience = await session.get(AudienceHypothesis, audience_hypothesis_id)
    if audience is None:
        raise CustomerInsightError("customer_insight_audience_not_found")
    if audience.project_id != project_id:
        raise CustomerInsightError("customer_insight_audience_project_mismatch")
    return audience


async def ensure_customer_insight(
    session: AsyncSession,
    *,
    project_id: UUID,
    insight_type: InsightType,
    statement: str,
    audience_hypothesis_id: UUID | None = None,
    situation: str | None = None,
    status: InsightStatus = "CANDIDATE",
    alternative_explanations: Iterable[str] = (),
    missing_evidence: Iterable[str] = (),
    insight_key: str | None = None,
    version: int = 1,
) -> CustomerInsight:
    """Create or exactly replay one immutable CustomerInsight version.

    A later wording/evidence revision must use the same explicit insight_key
    and the next contiguous version. Lifecycle status/review metadata may evolve
    without rewriting the versioned insight content.
    """

    if insight_type not in _INSIGHT_TYPES:
        raise CustomerInsightError("customer_insight_type_invalid")
    if status not in _INSIGHT_STATUSES:
        raise CustomerInsightError("customer_insight_status_invalid")
    if status != "CANDIDATE":
        raise CustomerInsightError("customer_insight_initial_status_must_be_candidate")
    if version < 1:
        raise CustomerInsightError("customer_insight_version_invalid")

    normalized_statement = _required_text(
        statement, "customer_insight_statement_required"
    )
    normalized_situation = _optional_text(situation)
    alternatives = _string_list(alternative_explanations)
    missing = _string_list(missing_evidence)

    if audience_hypothesis_id is not None:
        await _load_audience(
            session,
            audience_hypothesis_id=audience_hypothesis_id,
            project_id=project_id,
        )

    if version > 1 and insight_key is None:
        raise CustomerInsightError("customer_insight_key_required_for_revision")

    key = insight_key or derive_insight_key(
        insight_type=insight_type,
        statement=normalized_statement,
        audience_hypothesis_id=audience_hypothesis_id,
        situation=normalized_situation,
    )
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        raise CustomerInsightError("customer_insight_key_invalid")

    if version > 1:
        previous = await session.scalar(
            select(CustomerInsight).where(
                CustomerInsight.project_id == project_id,
                CustomerInsight.insight_key == key,
                CustomerInsight.version == version - 1,
            )
        )
        if previous is None:
            raise CustomerInsightError("customer_insight_previous_version_required")

    existing = await session.scalar(
        select(CustomerInsight).where(
            CustomerInsight.project_id == project_id,
            CustomerInsight.insight_key == key,
            CustomerInsight.version == version,
        )
    )
    if existing is not None:
        if (
            existing.insight_type != insight_type
            or existing.statement != normalized_statement
            or existing.audience_hypothesis_id != audience_hypothesis_id
            or existing.situation != normalized_situation
            or existing.alternative_explanations_json != alternatives
            or existing.missing_evidence_json != missing
        ):
            raise CustomerInsightError("customer_insight_replay_conflict")
        return existing

    insight = CustomerInsight(
        project_id=project_id,
        insight_key=key,
        version=version,
        audience_hypothesis_id=audience_hypothesis_id,
        insight_type=insight_type,
        statement=normalized_statement,
        situation=normalized_situation,
        status=status,
        alternative_explanations_json=alternatives,
        missing_evidence_json=missing,
    )
    session.add(insight)
    await session.flush()
    return insight


async def _customer_insight_evidence_refs(
    session: AsyncSession,
    *,
    customer_insight_id: UUID,
) -> dict[str, list[str]]:
    rows = (
        await session.execute(
            select(
                CustomerInsightSignal.signal_id,
                CustomerInsightSignal.relation,
            )
            .where(
                CustomerInsightSignal.customer_insight_id
                == customer_insight_id
            )
            .order_by(
                CustomerInsightSignal.relation,
                CustomerInsightSignal.signal_id,
            )
        )
    ).all()
    refs: dict[str, list[str]] = {
        "supports": [],
        "contradicts": [],
        "context": [],
    }
    for signal_id, relation in rows:
        refs[relation].append(str(signal_id))
    return refs


async def review_customer_insight(
    session: AsyncSession,
    *,
    customer_insight_id: UUID,
    status: Literal["SUPPORTED", "REJECTED", "INSUFFICIENT_EVIDENCE", "TESTING"],
    reviewed_by: str,
    reason: str,
) -> CustomerInsight:
    """Record an auditable review without rewriting versioned insight content."""

    if status not in {
        "SUPPORTED",
        "REJECTED",
        "INSUFFICIENT_EVIDENCE",
        "TESTING",
    }:
        raise CustomerInsightError("customer_insight_review_status_invalid")
    actor = _required_text(reviewed_by, "customer_insight_reviewer_required")
    review_reason = _required_text(reason, "customer_insight_review_reason_required")

    insight = await session.get(CustomerInsight, customer_insight_id)
    if insight is None:
        raise CustomerInsightError("customer_insight_not_found")

    existing_review = await session.scalar(
        select(CustomerInsightReview)
        .where(
            CustomerInsightReview.customer_insight_id == customer_insight_id,
            CustomerInsightReview.status == status,
            CustomerInsightReview.reviewed_by == actor,
            CustomerInsightReview.reason == review_reason,
        )
        .order_by(CustomerInsightReview.reviewed_at.asc())
        .limit(1)
    )
    if existing_review is not None:
        return insight

    if status == "SUPPORTED":
        counts = await customer_insight_evidence_counts(
            session,
            customer_insight_id=customer_insight_id,
        )
        if counts.independent_supports < 1:
            raise CustomerInsightError(
                "customer_insight_support_evidence_required"
            )

    refs = await _customer_insight_evidence_refs(
        session,
        customer_insight_id=customer_insight_id,
    )
    reviewed_at = utc_now()
    session.add(
        CustomerInsightReview(
            customer_insight_id=customer_insight_id,
            status=status,
            reviewed_by=actor,
            reason=review_reason,
            support_signal_refs_json=refs["supports"],
            contradict_signal_refs_json=refs["contradicts"],
            context_signal_refs_json=refs["context"],
            reviewed_at=reviewed_at,
        )
    )
    await session.flush()

    insight.status = status
    insight.reviewed_by = actor
    insight.reviewed_at = reviewed_at
    insight.review_reason = review_reason
    await session.flush()
    return insight


async def link_customer_insight_signal(
    session: AsyncSession,
    *,
    customer_insight_id: UUID,
    signal_id: UUID,
    relation: InsightSignalRelation,
) -> CustomerInsightSignal:
    """Create or exactly replay one project-scoped Insight to Signal relation."""

    if relation not in _RELATIONS:
        raise CustomerInsightError("customer_insight_signal_relation_invalid")

    insight = await session.get(CustomerInsight, customer_insight_id)
    if insight is None:
        raise CustomerInsightError("customer_insight_not_found")
    signal = await session.get(Signal, signal_id)
    if signal is None:
        raise CustomerInsightError("customer_insight_signal_not_found")
    if signal.project_id != insight.project_id:
        raise CustomerInsightError("customer_insight_signal_project_mismatch")

    # Validate the whole duplicate ancestry before accepting durable evidence.
    # DB triggers enforce the same rule for direct writes.
    await signal_independence_key(session, signal, {})

    existing = await session.get(
        CustomerInsightSignal, (customer_insight_id, signal_id)
    )
    if existing is not None:
        if existing.relation != relation:
            raise CustomerInsightError("customer_insight_signal_relation_conflict")
        return existing

    link = CustomerInsightSignal(
        customer_insight_id=customer_insight_id,
        signal_id=signal_id,
        relation=relation,
    )
    session.add(link)
    await session.flush()
    return link


async def signal_independence_key(
    session: AsyncSession,
    signal: Signal,
    cache: dict[UUID, str],
) -> str:
    cached = cache.get(signal.id)
    if cached is not None:
        return cached

    current = signal
    visited: set[UUID] = set()
    independence_groups: set[str] = set()
    root_signal_id: UUID | None = None
    while True:
        if current.id in visited:
            raise CustomerInsightError("customer_insight_signal_duplicate_cycle")
        if current.project_id != signal.project_id:
            raise CustomerInsightError(
                "customer_insight_signal_duplicate_parent_invalid"
            )
        visited.add(current.id)

        if current.independence_group:
            independence_groups.add(current.independence_group)

        if current.duplicate_of_id is None:
            root_signal_id = current.id
            break

        parent = await session.get(Signal, current.duplicate_of_id)
        if parent is None or parent.project_id != signal.project_id:
            raise CustomerInsightError(
                "customer_insight_signal_duplicate_parent_invalid"
            )
        current = parent

    if len(independence_groups) > 1:
        raise CustomerInsightError(
            "customer_insight_signal_independence_group_conflict"
        )
    if independence_groups:
        key = f"group:{next(iter(independence_groups))}"
    elif root_signal_id is not None:
        key = f"signal:{root_signal_id}"
    else:
        raise CustomerInsightError(
            "customer_insight_signal_duplicate_parent_invalid"
        )

    for signal_id in visited:
        cache[signal_id] = key
    return key


async def customer_insight_evidence_counts(
    session: AsyncSession,
    *,
    customer_insight_id: UUID,
) -> CustomerInsightEvidenceCounts:
    """Count linked observations while collapsing repost/duplicate independence."""

    insight = await session.get(CustomerInsight, customer_insight_id)
    if insight is None:
        raise CustomerInsightError("customer_insight_not_found")

    rows = tuple(
        (
            await session.execute(
                select(CustomerInsightSignal, Signal)
                .join(Signal, Signal.id == CustomerInsightSignal.signal_id)
                .where(
                    CustomerInsightSignal.customer_insight_id
                    == customer_insight_id
                )
            )
        ).all()
    )
    counts = {"supports": 0, "contradicts": 0, "context": 0}
    independent: dict[str, set[str]] = {
        "supports": set(),
        "contradicts": set(),
        "context": set(),
    }
    cache: dict[UUID, str] = {}
    for link, signal in rows:
        counts[link.relation] += 1
        independent[link.relation].add(
            await signal_independence_key(session, signal, cache)
        )

    return CustomerInsightEvidenceCounts(
        supports=counts["supports"],
        contradicts=counts["contradicts"],
        context=counts["context"],
        independent_supports=len(independent["supports"]),
        independent_contradicts=len(independent["contradicts"]),
        independent_context=len(independent["context"]),
    )


__all__ = [
    "CustomerInsightError",
    "CustomerInsightEvidenceCounts",
    "InsightSignalRelation",
    "InsightStatus",
    "InsightType",
    "customer_insight_evidence_counts",
    "derive_insight_key",
    "ensure_customer_insight",
    "link_customer_insight_signal",
    "review_customer_insight",
    "signal_independence_key",
]