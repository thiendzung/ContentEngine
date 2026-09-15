from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import utc_now
from app.modules.knowledge.admission import verify_candidate_snapshot_lineage
from app.modules.knowledge.freshness_models import (
    FreshnessAssignment,
    FreshnessPolicy,
    FreshnessVerification,
    SourceDocumentObservation,
)
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    KnowledgeCandidate,
    Source,
    SourceDocument,
)
from app.modules.knowledge.topic_models import KnowledgeTopicLink, TopicNode

FreshnessClass = Literal["evergreen", "slow", "medium", "fast"]
FreshnessState = Literal["UNCLASSIFIED", "UNKNOWN", "FRESH", "DUE", "STALE"]
FreshnessTargetType = Literal["claim", "knowledge_candidate"]
FreshnessAssignmentTargetType = Literal["topic", "claim", "knowledge_candidate"]
FreshnessPolicySource = Literal["target", "topic"]

_FRESHNESS_CLASSES = {"evergreen", "slow", "medium", "fast"}


class FreshnessError(ValueError):
    """Raised when freshness metadata cannot be created or evaluated safely."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EffectiveFreshnessPolicy:
    policy: FreshnessPolicy
    source: FreshnessPolicySource
    topic_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class FreshnessEvaluation:
    project_id: UUID
    target_type: FreshnessTargetType
    target_id: UUID
    state: FreshnessState
    policy_id: UUID | None
    policy_key: str | None
    policy_version: int | None
    freshness_class: str | None
    policy_source: FreshnessPolicySource | None
    policy_topic_id: UUID | None
    verification_id: UUID | None
    verified_at: datetime | None
    due_at: datetime | None
    stale_at: datetime | None
    reasons: tuple[str, ...]


def _text(value: str, code: str, *, max_length: int | None = None) -> str:
    normalized = value.strip()
    if not normalized or (max_length is not None and len(normalized) > max_length):
        raise FreshnessError(code)
    return normalized


def normalize_freshness_policy_key(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"[^a-z0-9._-]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-._")
    if not normalized or len(normalized) > 255:
        raise FreshnessError("freshness_policy_key_invalid")
    return normalized


def _aware(value: datetime, code: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FreshnessError(code)
    return value.astimezone(UTC)


async def ensure_source_document_observation(
    session: AsyncSession,
    *,
    source_document_id: UUID,
    observed_at: datetime,
    content_hash: str,
    provider: str | None,
    reader: str | None,
    observation_method: Literal["document_ingest", "migration_backfill"] = "document_ingest",
) -> SourceDocumentObservation:
    """Persist one successful observation even when document content dedupes."""

    document = await session.get(SourceDocument, source_document_id)
    if document is None:
        raise FreshnessError("freshness_observation_document_not_found")
    if document.content_hash != content_hash:
        raise FreshnessError("freshness_observation_content_hash_mismatch")
    observed = _aware(observed_at, "freshness_observation_time_invalid")
    if observation_method not in {"document_ingest", "migration_backfill"}:
        raise FreshnessError("freshness_observation_method_invalid")

    existing = await session.scalar(
        select(SourceDocumentObservation).where(
            SourceDocumentObservation.source_document_id == document.id,
            SourceDocumentObservation.observed_at == observed,
            SourceDocumentObservation.observation_method == observation_method,
        )
    )
    if existing is not None:
        if (
            existing.content_hash != document.content_hash
            or existing.provider != provider
            or existing.reader != reader
        ):
            raise FreshnessError("freshness_observation_replay_conflict")
        return existing

    observation = SourceDocumentObservation(
        source_document_id=document.id,
        observed_at=observed,
        content_hash=document.content_hash,
        provider=provider,
        reader=reader,
        observation_method=observation_method,
    )
    session.add(observation)
    await session.flush()
    return observation


async def ensure_freshness_policy(
    session: AsyncSession,
    *,
    project_id: UUID,
    policy_key: str,
    version: int,
    freshness_class: FreshnessClass,
    max_age_days: int,
    refresh_lead_days: int,
    created_by: str,
    rationale: str,
) -> FreshnessPolicy:
    """Create or exactly replay one versioned policy; no hidden TTL defaults."""

    key = normalize_freshness_policy_key(policy_key)
    actor = _text(created_by, "freshness_policy_actor_required", max_length=200)
    reason = _text(rationale, "freshness_policy_rationale_required")
    if version < 1:
        raise FreshnessError("freshness_policy_version_invalid")
    if freshness_class not in _FRESHNESS_CLASSES:
        raise FreshnessError("freshness_policy_class_invalid")
    if max_age_days < 1 or max_age_days > 3650:
        raise FreshnessError("freshness_policy_max_age_invalid")
    if refresh_lead_days < 0 or refresh_lead_days >= max_age_days:
        raise FreshnessError("freshness_policy_refresh_lead_invalid")

    existing = await session.scalar(
        select(FreshnessPolicy).where(
            FreshnessPolicy.project_id == project_id,
            FreshnessPolicy.policy_key == key,
            FreshnessPolicy.version == version,
        )
    )
    if existing is not None:
        if (
            existing.freshness_class != freshness_class
            or existing.max_age_days != max_age_days
            or existing.refresh_lead_days != refresh_lead_days
            or existing.created_by != actor
            or existing.rationale != reason
            or existing.status != "active"
        ):
            raise FreshnessError("freshness_policy_replay_conflict")
        return existing

    policy = FreshnessPolicy(
        project_id=project_id,
        policy_key=key,
        version=version,
        freshness_class=freshness_class,
        max_age_days=max_age_days,
        refresh_lead_days=refresh_lead_days,
        status="active",
        created_by=actor,
        rationale=reason,
        retired_at=None,
        retired_by=None,
        retirement_reason=None,
    )
    session.add(policy)
    await session.flush()
    return policy


async def retire_freshness_policy(
    session: AsyncSession,
    *,
    policy_id: UUID,
    retired_by: str,
    reason: str,
) -> FreshnessPolicy:
    actor = _text(retired_by, "freshness_policy_retired_by_required", max_length=200)
    retirement_reason = _text(reason, "freshness_policy_retirement_reason_required")
    policy = await session.scalar(
        select(FreshnessPolicy).where(FreshnessPolicy.id == policy_id).with_for_update()
    )
    if policy is None:
        raise FreshnessError("freshness_policy_not_found")
    if policy.status == "retired":
        if policy.retired_by == actor and policy.retirement_reason == retirement_reason:
            return policy
        raise FreshnessError("freshness_policy_retirement_conflict")

    active_assignment = await session.scalar(
        select(FreshnessAssignment.id).where(
            FreshnessAssignment.policy_id == policy.id,
            FreshnessAssignment.status == "active",
        )
    )
    if active_assignment is not None:
        raise FreshnessError("freshness_policy_has_active_assignments")

    policy.status = "retired"
    policy.retired_at = utc_now()
    policy.retired_by = actor
    policy.retirement_reason = retirement_reason
    await session.flush()
    return policy


async def _assignment_target_project_id(
    session: AsyncSession,
    *,
    target_type: FreshnessAssignmentTargetType,
    target_id: UUID,
) -> UUID:
    if target_type == "topic":
        topic = await session.get(TopicNode, target_id)
        if topic is None:
            raise FreshnessError("freshness_assignment_topic_not_found")
        if topic.status != "active":
            raise FreshnessError("freshness_assignment_topic_not_active")
        return topic.project_id
    if target_type == "claim":
        claim = await session.get(Claim, target_id)
        if claim is None:
            raise FreshnessError("freshness_assignment_claim_not_found")
        return claim.project_id
    if target_type == "knowledge_candidate":
        candidate = await session.get(KnowledgeCandidate, target_id)
        if candidate is None:
            raise FreshnessError("freshness_assignment_candidate_not_found")
        if candidate.status != "APPROVED":
            raise FreshnessError("freshness_assignment_candidate_not_approved")
        return candidate.project_id
    raise FreshnessError("freshness_assignment_target_type_invalid")


def _assignment_column(target_type: FreshnessAssignmentTargetType) -> Any:
    return {
        "topic": FreshnessAssignment.topic_id,
        "claim": FreshnessAssignment.claim_id,
        "knowledge_candidate": FreshnessAssignment.knowledge_candidate_id,
    }[target_type]


async def ensure_freshness_assignment(
    session: AsyncSession,
    *,
    project_id: UUID,
    policy_id: UUID,
    target_type: FreshnessAssignmentTargetType,
    target_id: UUID,
    assigned_by: str,
    reason: str,
    supersedes_id: UUID | None = None,
) -> FreshnessAssignment:
    actor = _text(assigned_by, "freshness_assignment_actor_required", max_length=200)
    assignment_reason = _text(reason, "freshness_assignment_reason_required")
    policy = await session.get(FreshnessPolicy, policy_id)
    if policy is None:
        raise FreshnessError("freshness_assignment_policy_not_found")
    if policy.project_id != project_id:
        raise FreshnessError("freshness_assignment_policy_project_mismatch")
    if policy.status != "active":
        raise FreshnessError("freshness_assignment_policy_not_active")
    if await _assignment_target_project_id(
        session,
        target_type=target_type,
        target_id=target_id,
    ) != project_id:
        raise FreshnessError("freshness_assignment_target_project_mismatch")

    target_column = _assignment_column(target_type)
    existing = await session.scalar(
        select(FreshnessAssignment).where(
            FreshnessAssignment.project_id == project_id,
            FreshnessAssignment.status == "active",
            target_column == target_id,
        )
    )
    if existing is not None:
        if (
            existing.policy_id != policy.id
            or existing.assigned_by != actor
            or existing.reason != assignment_reason
            or existing.supersedes_id != supersedes_id
        ):
            raise FreshnessError("freshness_assignment_replay_conflict")
        return existing

    assignment = FreshnessAssignment(
        project_id=project_id,
        policy_id=policy.id,
        topic_id=target_id if target_type == "topic" else None,
        claim_id=target_id if target_type == "claim" else None,
        knowledge_candidate_id=(
            target_id if target_type == "knowledge_candidate" else None
        ),
        status="active",
        assigned_by=actor,
        reason=assignment_reason,
        supersedes_id=supersedes_id,
        retired_at=None,
        retired_by=None,
        retirement_reason=None,
    )
    session.add(assignment)
    await session.flush()
    return assignment


async def replace_freshness_assignment(
    session: AsyncSession,
    *,
    expected_assignment_id: UUID,
    new_policy_id: UUID,
    assigned_by: str,
    reason: str,
) -> FreshnessAssignment:
    actor = _text(assigned_by, "freshness_assignment_actor_required", max_length=200)
    replacement_reason = _text(reason, "freshness_assignment_reason_required")
    current = await session.scalar(
        select(FreshnessAssignment)
        .where(FreshnessAssignment.id == expected_assignment_id)
        .with_for_update()
    )
    if current is None:
        raise FreshnessError("freshness_assignment_not_found")
    if current.status != "active":
        raise FreshnessError("freshness_assignment_not_active")

    target_values = (
        ("topic", current.topic_id),
        ("claim", current.claim_id),
        ("knowledge_candidate", current.knowledge_candidate_id),
    )
    target = next((item for item in target_values if item[1] is not None), None)
    if target is None:
        raise FreshnessError("freshness_assignment_target_missing")
    target_type = cast(FreshnessAssignmentTargetType, target[0])
    target_id = target[1]
    assert target_id is not None

    current.status = "retired"
    current.retired_at = utc_now()
    current.retired_by = actor
    current.retirement_reason = replacement_reason
    await session.flush()

    return await ensure_freshness_assignment(
        session,
        project_id=current.project_id,
        policy_id=new_policy_id,
        target_type=target_type,
        target_id=target_id,
        assigned_by=actor,
        reason=replacement_reason,
        supersedes_id=current.id,
    )


async def _evidence_rows_for_target(
    session: AsyncSession,
    *,
    project_id: UUID,
    target_type: FreshnessTargetType,
    target_id: UUID,
) -> tuple[tuple[Evidence, ...], str | None]:
    if target_type == "claim":
        claim = await session.get(Claim, target_id)
        if claim is None:
            raise FreshnessError("freshness_claim_not_found")
        if claim.project_id != project_id:
            raise FreshnessError("freshness_target_project_mismatch")
        rows = tuple(
            (
                await session.scalars(
                    select(Evidence)
                    .where(Evidence.claim_id == claim.id)
                    .order_by(Evidence.id)
                )
            ).all()
        )
        return rows, None

    candidate = await session.get(KnowledgeCandidate, target_id)
    if candidate is None:
        raise FreshnessError("freshness_candidate_not_found")
    if candidate.project_id != project_id:
        raise FreshnessError("freshness_target_project_mismatch")
    if candidate.status != "APPROVED":
        raise FreshnessError("freshness_candidate_not_approved")
    snapshot, candidate_hash = await verify_candidate_snapshot_lineage(
        session,
        candidate=candidate,
    )
    raw_evidence_ids = snapshot.get("evidence_ids")
    if not isinstance(raw_evidence_ids, list) or not raw_evidence_ids:
        raise FreshnessError("freshness_candidate_evidence_missing")
    try:
        evidence_ids = [UUID(str(value)) for value in raw_evidence_ids]
    except ValueError as exc:
        raise FreshnessError("freshness_candidate_evidence_invalid") from exc
    rows = tuple(
        (
            await session.scalars(
                select(Evidence).where(Evidence.id.in_(evidence_ids)).order_by(Evidence.id)
            )
        ).all()
    )
    if len(rows) != len(set(evidence_ids)):
        raise FreshnessError("freshness_candidate_evidence_missing")
    return rows, candidate_hash


async def _latest_observation_at(
    session: AsyncSession,
    *,
    source_document_id: UUID,
    as_of: datetime,
) -> SourceDocumentObservation:
    observation = await session.scalar(
        select(SourceDocumentObservation)
        .where(
            SourceDocumentObservation.source_document_id == source_document_id,
            SourceDocumentObservation.observed_at <= as_of,
        )
        .order_by(
            SourceDocumentObservation.observed_at.desc(),
            SourceDocumentObservation.id.desc(),
        )
        .limit(1)
    )
    if observation is None:
        raise FreshnessError("freshness_source_observation_missing")
    return observation


async def record_lineage_verification(
    session: AsyncSession,
    *,
    project_id: UUID,
    target_type: FreshnessTargetType,
    target_id: UUID,
    recorded_by: str,
    as_of: datetime | None = None,
) -> FreshnessVerification:
    """Record a snapshot only from current verified evidence and observed source docs."""

    actor = _text(recorded_by, "freshness_verification_actor_required", max_length=200)
    cutoff = _aware(as_of or utc_now(), "freshness_verification_as_of_invalid")
    evidence_rows, candidate_hash = await _evidence_rows_for_target(
        session,
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
    )
    usable = tuple(
        evidence
        for evidence in evidence_rows
        if evidence.source_document_id is not None and evidence.verified_at is not None
    )
    if not usable or len(usable) != len(evidence_rows):
        raise FreshnessError("freshness_requires_verified_source_document_evidence")

    evidence_payload: list[dict[str, object]] = []
    source_payload_by_id: dict[UUID, dict[str, object]] = {}
    observation_ids: list[str] = []
    observation_times: list[datetime] = []

    for evidence in usable:
        assert evidence.source_document_id is not None
        document = await session.get(SourceDocument, evidence.source_document_id)
        if document is None:
            raise FreshnessError("freshness_source_document_missing")
        source = await session.get(Source, document.source_id)
        if source is None or source.project_id != project_id:
            raise FreshnessError("freshness_source_project_mismatch")
        observation = await _latest_observation_at(
            session,
            source_document_id=document.id,
            as_of=cutoff,
        )
        if observation.content_hash != document.content_hash:
            raise FreshnessError("freshness_observation_content_hash_mismatch")

        evidence_payload.append(
            {
                "evidence_id": str(evidence.id),
                "relation": evidence.relation,
                "source_document_id": str(document.id),
                "source_document_hash": document.content_hash,
            }
        )
        source_payload_by_id[document.id] = {
            "source_id": str(source.id),
            "source_document_id": str(document.id),
            "document_version": document.document_version,
            "content_hash": document.content_hash,
        }
        observation_ids.append(str(observation.id))
        observation_times.append(
            _aware(observation.observed_at, "freshness_observation_time_invalid")
        )

    source_payload = sorted(
        source_payload_by_id.values(),
        key=lambda item: str(item["source_document_id"]),
    )
    evidence_payload.sort(key=lambda item: str(item["evidence_id"]))
    basis = {
        "target_type": target_type,
        "target_id": str(target_id),
        "candidate_content_hash": candidate_hash,
        "evidence": evidence_payload,
        "source_documents": source_payload,
    }
    basis_hash = hashlib.sha256(
        json.dumps(basis, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    verified_at = min(observation_times)
    normalized_observation_ids = sorted(set(observation_ids))
    evidence_ids = [str(item["evidence_id"]) for item in evidence_payload]

    target_column = (
        FreshnessVerification.claim_id
        if target_type == "claim"
        else FreshnessVerification.knowledge_candidate_id
    )
    existing = await session.scalar(
        select(FreshnessVerification).where(
            FreshnessVerification.project_id == project_id,
            target_column == target_id,
            FreshnessVerification.basis_hash == basis_hash,
            FreshnessVerification.verified_at == verified_at,
        )
    )
    if existing is not None:
        if (
            existing.evidence_ids_json != evidence_ids
            or existing.source_documents_json != source_payload
            or existing.observation_ids_json != normalized_observation_ids
            or existing.recorded_by != actor
        ):
            raise FreshnessError("freshness_verification_replay_conflict")
        return existing

    verification = FreshnessVerification(
        project_id=project_id,
        claim_id=target_id if target_type == "claim" else None,
        knowledge_candidate_id=(target_id if target_type == "knowledge_candidate" else None),
        basis_hash=basis_hash,
        verified_at=verified_at,
        evidence_ids_json=evidence_ids,
        source_documents_json=source_payload,
        observation_ids_json=normalized_observation_ids,
        verification_method="lineage_snapshot",
        recorded_by=actor,
    )
    session.add(verification)
    await session.flush()
    return verification


async def _explicit_assignment(
    session: AsyncSession,
    *,
    project_id: UUID,
    target_type: FreshnessTargetType,
    target_id: UUID,
) -> FreshnessAssignment | None:
    target_column = (
        FreshnessAssignment.claim_id
        if target_type == "claim"
        else FreshnessAssignment.knowledge_candidate_id
    )
    return await session.scalar(
        select(FreshnessAssignment).where(
            FreshnessAssignment.project_id == project_id,
            FreshnessAssignment.status == "active",
            target_column == target_id,
        )
    )


async def resolve_effective_freshness_policy(
    session: AsyncSession,
    *,
    project_id: UUID,
    target_type: FreshnessTargetType,
    target_id: UUID,
) -> EffectiveFreshnessPolicy | None:
    """Resolve explicit target policy, then strictest directly-linked Topic policy."""

    await _evidence_rows_for_target(
        session,
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
    )
    direct = await _explicit_assignment(
        session,
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
    )
    if direct is not None:
        policy = await session.get(FreshnessPolicy, direct.policy_id)
        if policy is None or policy.project_id != project_id:
            raise FreshnessError("freshness_assignment_policy_invalid")
        if policy.status != "active":
            raise FreshnessError("freshness_assignment_policy_not_active")
        return EffectiveFreshnessPolicy(policy=policy, source="target")

    target_column = (
        KnowledgeTopicLink.claim_id
        if target_type == "claim"
        else KnowledgeTopicLink.knowledge_candidate_id
    )
    topic_ids = tuple(
        (
            await session.scalars(
                select(KnowledgeTopicLink.topic_id).where(
                    KnowledgeTopicLink.project_id == project_id,
                    target_column == target_id,
                )
            )
        ).all()
    )
    if not topic_ids:
        return None

    assignments = tuple(
        (
            await session.scalars(
                select(FreshnessAssignment).where(
                    FreshnessAssignment.project_id == project_id,
                    FreshnessAssignment.status == "active",
                    FreshnessAssignment.topic_id.in_(topic_ids),
                )
            )
        ).all()
    )
    candidates: list[tuple[FreshnessPolicy, UUID]] = []
    for assignment in assignments:
        assert assignment.topic_id is not None
        policy = await session.get(FreshnessPolicy, assignment.policy_id)
        if policy is None or policy.project_id != project_id:
            raise FreshnessError("freshness_assignment_policy_invalid")
        if policy.status != "active":
            raise FreshnessError("freshness_assignment_policy_not_active")
        candidates.append((policy, assignment.topic_id))
    if not candidates:
        return None

    policy, topic_id = min(
        candidates,
        key=lambda item: (
            item[0].max_age_days,
            -item[0].refresh_lead_days,
            item[0].policy_key,
            item[0].version,
            str(item[0].id),
            str(item[1]),
        ),
    )
    return EffectiveFreshnessPolicy(policy=policy, source="topic", topic_id=topic_id)


async def _latest_verification(
    session: AsyncSession,
    *,
    project_id: UUID,
    target_type: FreshnessTargetType,
    target_id: UUID,
    as_of: datetime,
) -> FreshnessVerification | None:
    target_column = (
        FreshnessVerification.claim_id
        if target_type == "claim"
        else FreshnessVerification.knowledge_candidate_id
    )
    return await session.scalar(
        select(FreshnessVerification)
        .where(
            FreshnessVerification.project_id == project_id,
            target_column == target_id,
            FreshnessVerification.verified_at <= as_of,
        )
        .order_by(FreshnessVerification.verified_at.desc(), FreshnessVerification.id.desc())
        .limit(1)
    )


async def _basis_source_superseded(
    session: AsyncSession,
    *,
    verification: FreshnessVerification,
    as_of: datetime,
) -> bool:
    for raw in verification.source_documents_json:
        if not isinstance(raw, dict):
            raise FreshnessError("freshness_verification_source_payload_invalid")
        try:
            source_id = UUID(str(raw["source_id"]))
            document_id = UUID(str(raw["source_document_id"]))
        except (KeyError, ValueError) as exc:
            raise FreshnessError("freshness_verification_source_payload_invalid") from exc
        latest = await session.scalar(
            select(SourceDocument)
            .where(
                SourceDocument.source_id == source_id,
                SourceDocument.fetched_at <= as_of,
            )
            .order_by(SourceDocument.document_version.desc(), SourceDocument.id.desc())
            .limit(1)
        )
        if latest is None or latest.id != document_id:
            return True
    return False


async def evaluate_freshness(
    session: AsyncSession,
    *,
    project_id: UUID,
    target_type: FreshnessTargetType,
    target_id: UUID,
    as_of: datetime | None = None,
) -> FreshnessEvaluation:
    """Evaluate a clock-derived state without persisting it."""

    evaluated_at = _aware(as_of or utc_now(), "freshness_as_of_invalid")
    effective = await resolve_effective_freshness_policy(
        session,
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
    )
    if effective is None:
        return FreshnessEvaluation(
            project_id=project_id,
            target_type=target_type,
            target_id=target_id,
            state="UNCLASSIFIED",
            policy_id=None,
            policy_key=None,
            policy_version=None,
            freshness_class=None,
            policy_source=None,
            policy_topic_id=None,
            verification_id=None,
            verified_at=None,
            due_at=None,
            stale_at=None,
            reasons=("no_freshness_policy",),
        )

    policy = effective.policy
    verification = await _latest_verification(
        session,
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
        as_of=evaluated_at,
    )
    if verification is None:
        return FreshnessEvaluation(
            project_id=project_id,
            target_type=target_type,
            target_id=target_id,
            state="UNKNOWN",
            policy_id=policy.id,
            policy_key=policy.policy_key,
            policy_version=policy.version,
            freshness_class=policy.freshness_class,
            policy_source=effective.source,
            policy_topic_id=effective.topic_id,
            verification_id=None,
            verified_at=None,
            due_at=None,
            stale_at=None,
            reasons=("verification_missing",),
        )

    verified_at = _aware(verification.verified_at, "freshness_verification_time_invalid")
    stale_at = verified_at + timedelta(days=policy.max_age_days)
    due_at = stale_at - timedelta(days=policy.refresh_lead_days)
    reasons: list[str] = []

    if await _basis_source_superseded(
        session,
        verification=verification,
        as_of=evaluated_at,
    ):
        state: FreshnessState = "STALE"
        reasons.append("source_superseded")
    elif evaluated_at >= stale_at:
        state = "STALE"
        reasons.append("max_age_exceeded")
    elif evaluated_at >= due_at:
        state = "DUE"
        reasons.append("refresh_window_open")
    else:
        state = "FRESH"
        reasons.append("within_freshness_window")

    return FreshnessEvaluation(
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
        state=state,
        policy_id=policy.id,
        policy_key=policy.policy_key,
        policy_version=policy.version,
        freshness_class=policy.freshness_class,
        policy_source=effective.source,
        policy_topic_id=effective.topic_id,
        verification_id=verification.id,
        verified_at=verified_at,
        due_at=due_at,
        stale_at=stale_at,
        reasons=tuple(reasons),
    )


__all__ = [
    "EffectiveFreshnessPolicy",
    "FreshnessAssignmentTargetType",
    "FreshnessClass",
    "FreshnessError",
    "FreshnessEvaluation",
    "FreshnessState",
    "FreshnessTargetType",
    "ensure_freshness_assignment",
    "ensure_freshness_policy",
    "ensure_source_document_observation",
    "evaluate_freshness",
    "normalize_freshness_policy_key",
    "record_lineage_verification",
    "replace_freshness_assignment",
    "resolve_effective_freshness_policy",
    "retire_freshness_policy",
]
