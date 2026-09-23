from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import Project, Signal
from app.modules.customer_intelligence.insights import (
    InsightType,
    derive_insight_key,
    ensure_customer_insight,
    link_customer_insight_signal,
)
from app.modules.customer_intelligence.living_map import (
    InsightNeedRelation,
    ensure_customer_insight_need_link,
)
from app.modules.customer_intelligence.models import CustomerInsight


class CustomerInsightIntakeError(ValueError):
    """Raised when a candidate intake request is incomplete or ambiguous."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CustomerInsightCandidateInput:
    insight_type: InsightType
    statement: str
    situation: str | None = None
    audience_hypothesis_id: UUID | None = None
    support_signal_ids: tuple[UUID, ...] = ()
    contradict_signal_ids: tuple[UUID, ...] = ()
    context_signal_ids: tuple[UUID, ...] = ()
    alternative_explanations: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    need_hypothesis_id: UUID | None = None
    need_relation: InsightNeedRelation | None = None
    linked_by: str | None = None
    link_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CustomerInsightCandidateResult:
    insight: CustomerInsight
    replayed: bool
    linked_signal_ids: tuple[UUID, ...]
    need_linked: bool


def _normalized_signal_relations(
    request: CustomerInsightCandidateInput,
) -> tuple[tuple[UUID, str], ...]:
    rows = (
        *((signal_id, "supports") for signal_id in request.support_signal_ids),
        *((signal_id, "contradicts") for signal_id in request.contradict_signal_ids),
        *((signal_id, "context") for signal_id in request.context_signal_ids),
    )
    if not rows:
        raise CustomerInsightIntakeError("customer_insight_intake_signal_required")

    seen: dict[UUID, str] = {}
    normalized: list[tuple[UUID, str]] = []
    for signal_id, relation in rows:
        previous = seen.get(signal_id)
        if previous is not None:
            if previous != relation:
                raise CustomerInsightIntakeError(
                    "customer_insight_intake_signal_relation_conflict"
                )
            continue
        seen[signal_id] = relation
        normalized.append((signal_id, relation))
    return tuple(normalized)


def _validate_need_link(request: CustomerInsightCandidateInput) -> bool:
    values = (
        request.need_hypothesis_id,
        request.need_relation,
        request.linked_by,
        request.link_reason,
    )
    if all(value is None for value in values):
        return False
    if any(value is None for value in values):
        raise CustomerInsightIntakeError(
            "customer_insight_intake_need_link_incomplete"
        )
    if not request.linked_by or not request.linked_by.strip():
        raise CustomerInsightIntakeError(
            "customer_insight_intake_need_link_actor_required"
        )
    if not request.link_reason or not request.link_reason.strip():
        raise CustomerInsightIntakeError(
            "customer_insight_intake_need_link_reason_required"
        )
    return True


async def persist_customer_insight_candidate(
    session: AsyncSession,
    *,
    project_id: UUID,
    request: CustomerInsightCandidateInput,
) -> CustomerInsightCandidateResult:
    """Persist one explicit CustomerInsight candidate from exact durable Signals.

    This bridge performs no research/model/tool work and never reviews or promotes
    the candidate. The caller must supply the interpretation and exact Signal
    relations. Optional Need linkage is explicit and auditable.
    """

    signal_relations = _normalized_signal_relations(request)
    link_need = _validate_need_link(request)

    project = await session.get(Project, project_id)
    if project is None:
        raise CustomerInsightIntakeError("customer_insight_intake_project_not_found")

    statement = request.statement.strip()
    situation = request.situation.strip() if request.situation else None
    if not statement:
        raise CustomerInsightIntakeError(
            "customer_insight_intake_statement_required"
        )

    key = derive_insight_key(
        insight_type=request.insight_type,
        statement=statement,
        audience_hypothesis_id=request.audience_hypothesis_id,
        situation=situation,
    )
    existing = await session.scalar(
        select(CustomerInsight).where(
            CustomerInsight.project_id == project_id,
            CustomerInsight.insight_key == key,
            CustomerInsight.version == 1,
        )
    )

    async with session.begin_nested():
        insight = await ensure_customer_insight(
            session,
            project_id=project_id,
            insight_type=request.insight_type,
            statement=statement,
            audience_hypothesis_id=request.audience_hypothesis_id,
            situation=situation,
            alternative_explanations=request.alternative_explanations,
            missing_evidence=request.missing_evidence,
        )

        linked_ids: list[UUID] = []
        for signal_id, relation in signal_relations:
            signal = await session.get(Signal, signal_id)
            if signal is None:
                raise CustomerInsightIntakeError(
                    "customer_insight_intake_signal_not_found"
                )
            if signal.project_id != project_id:
                raise CustomerInsightIntakeError(
                    "customer_insight_intake_signal_project_mismatch"
                )
            await link_customer_insight_signal(
                session,
                customer_insight_id=insight.id,
                signal_id=signal_id,
                relation=relation,  # type: ignore[arg-type]
            )
            linked_ids.append(signal_id)

        if link_need:
            assert request.need_hypothesis_id is not None
            assert request.need_relation is not None
            assert request.linked_by is not None
            assert request.link_reason is not None
            await ensure_customer_insight_need_link(
                session,
                customer_insight_id=insight.id,
                need_hypothesis_id=request.need_hypothesis_id,
                relation=request.need_relation,
                linked_by=request.linked_by,
                reason=request.link_reason,
            )

    return CustomerInsightCandidateResult(
        insight=insight,
        replayed=existing is not None,
        linked_signal_ids=tuple(linked_ids),
        need_linked=link_need,
    )


__all__ = [
    "CustomerInsightCandidateInput",
    "CustomerInsightCandidateResult",
    "CustomerInsightIntakeError",
    "persist_customer_insight_candidate",
]
