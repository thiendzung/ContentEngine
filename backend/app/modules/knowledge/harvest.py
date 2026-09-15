from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import ContentCase
from app.modules.knowledge.admission import verify_candidate_snapshot_lineage
from app.modules.knowledge.freshness import FreshnessEvaluation, evaluate_freshness
from app.modules.knowledge.harvest_models import KnowledgeHarvest
from app.modules.knowledge.models import KnowledgeCandidate
from app.modules.knowledge.topic_models import KnowledgeTopicLink, TopicEdge, TopicNode

HARVEST_METHOD = "approved_candidate_topic_scope_v1"


class KnowledgeHarvestError(ValueError):
    """Raised when a deterministic knowledge harvest cannot be built safely."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _required_text(value: str, code: str, *, max_length: int | None = None) -> str:
    normalized = value.strip()
    if not normalized or (max_length is not None and len(normalized) > max_length):
        raise KnowledgeHarvestError(code)
    return normalized


def _as_utc(value: datetime, code: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise KnowledgeHarvestError(code)
    return value.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_payload(
    *,
    project_id: UUID,
    content_case_id: UUID | None,
    locale: str,
    as_of: datetime,
    requested_topic_ids: tuple[UUID, ...],
    expanded_topic_ids: tuple[UUID, ...],
    items: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "harvest_method": HARVEST_METHOD,
        "project_id": str(project_id),
        "content_case_id": str(content_case_id) if content_case_id is not None else None,
        "locale": locale,
        "as_of": _iso(as_of),
        "requested_topic_ids": [str(value) for value in requested_topic_ids],
        "expanded_topic_ids": [str(value) for value in expanded_topic_ids],
        "items": items,
    }


def rebuild_knowledge_harvest_snapshot(
    harvest: KnowledgeHarvest,
) -> tuple[dict[str, object], str]:
    """Rebuild a persisted harvest's canonical immutable snapshot."""

    try:
        requested_topic_ids = tuple(UUID(value) for value in harvest.requested_topic_ids_json)
        expanded_topic_ids = tuple(UUID(value) for value in harvest.expanded_topic_ids_json)
    except ValueError as exc:
        raise KnowledgeHarvestError("knowledge_harvest_topic_id_invalid") from exc
    if any(not isinstance(item, dict) for item in harvest.items_json):
        raise KnowledgeHarvestError("knowledge_harvest_item_invalid")
    items = [dict(item) for item in harvest.items_json if isinstance(item, dict)]
    payload = _snapshot_payload(
        project_id=harvest.project_id,
        content_case_id=harvest.content_case_id,
        locale=harvest.locale,
        as_of=_as_utc(harvest.as_of, "knowledge_harvest_as_of_invalid"),
        requested_topic_ids=requested_topic_ids,
        expanded_topic_ids=expanded_topic_ids,
        items=items,
    )
    return payload, _canonical_hash(payload)


def verify_knowledge_harvest_snapshot(harvest: KnowledgeHarvest) -> dict[str, object]:
    """Fail closed if a downstream consumer receives a corrupted harvest row."""

    if harvest.harvest_method != HARVEST_METHOD:
        raise KnowledgeHarvestError("knowledge_harvest_method_invalid")
    payload, recomputed_hash = rebuild_knowledge_harvest_snapshot(harvest)
    if recomputed_hash != harvest.snapshot_hash:
        raise KnowledgeHarvestError("knowledge_harvest_snapshot_hash_mismatch")
    return payload


def _advisory_lock_key(project_id: UUID, snapshot_hash: str) -> int:
    digest = hashlib.sha256(f"{project_id}:{snapshot_hash}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


async def _lock_snapshot(
    session: AsyncSession,
    *,
    project_id: UUID,
    snapshot_hash: str,
) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _advisory_lock_key(project_id, snapshot_hash)},
    )


async def _validate_content_case(
    session: AsyncSession,
    *,
    project_id: UUID,
    content_case_id: UUID | None,
) -> None:
    if content_case_id is None:
        return
    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None:
        raise KnowledgeHarvestError("knowledge_harvest_content_case_not_found")
    if content_case.project_id != project_id:
        raise KnowledgeHarvestError("knowledge_harvest_content_case_project_mismatch")


async def _active_topic_scope(
    session: AsyncSession,
    *,
    project_id: UUID,
    root_topic_ids: tuple[UUID, ...],
) -> tuple[UUID, ...]:
    roots: list[TopicNode] = []
    for topic_id in root_topic_ids:
        topic = await session.get(TopicNode, topic_id)
        if topic is None:
            raise KnowledgeHarvestError("knowledge_harvest_root_topic_not_found")
        if topic.project_id != project_id:
            raise KnowledgeHarvestError("knowledge_harvest_root_topic_project_mismatch")
        if topic.status != "active":
            raise KnowledgeHarvestError("knowledge_harvest_root_topic_not_active")
        roots.append(topic)

    output: set[UUID] = {topic.id for topic in roots}
    frontier: set[UUID] = set(output)
    seen: set[UUID] = set()
    while frontier:
        batch = frontier - seen
        if not batch:
            break
        seen.update(batch)
        children = set(
            (
                await session.scalars(
                    select(TopicNode.id)
                    .join(TopicEdge, TopicEdge.child_topic_id == TopicNode.id)
                    .where(
                        TopicEdge.project_id == project_id,
                        TopicEdge.relation_type == "contains",
                        TopicEdge.parent_topic_id.in_(batch),
                        TopicNode.project_id == project_id,
                        TopicNode.status == "active",
                    )
                )
            ).all()
        )
        output.update(children)
        frontier = children
    return tuple(sorted(output, key=str))


def _freshness_payload(evaluation: FreshnessEvaluation) -> dict[str, object]:
    return {
        "state": evaluation.state,
        "policy_id": str(evaluation.policy_id) if evaluation.policy_id else None,
        "policy_key": evaluation.policy_key,
        "policy_version": evaluation.policy_version,
        "freshness_class": evaluation.freshness_class,
        "policy_source": evaluation.policy_source,
        "policy_topic_id": (
            str(evaluation.policy_topic_id) if evaluation.policy_topic_id else None
        ),
        "verification_id": (
            str(evaluation.verification_id) if evaluation.verification_id else None
        ),
        "verified_at": _iso(evaluation.verified_at),
        "due_at": _iso(evaluation.due_at),
        "stale_at": _iso(evaluation.stale_at),
        "reasons": list(evaluation.reasons),
    }


def _lineage_payload(snapshot: dict[str, object]) -> dict[str, object]:
    return {
        "evidence_set": snapshot.get("evidence_set"),
        "claim_id": snapshot.get("claim_id"),
        "evidence_ids": snapshot.get("evidence_ids"),
        "source_document_ids": snapshot.get("source_document_ids"),
        "source_ids": snapshot.get("source_ids"),
        "relation_counts": snapshot.get("relation_counts"),
        "evidence_refs": snapshot.get("evidence_refs"),
    }


async def _harvest_items(
    session: AsyncSession,
    *,
    project_id: UUID,
    locale: str,
    expanded_topic_ids: tuple[UUID, ...],
    as_of: datetime,
) -> list[dict[str, object]]:
    links = tuple(
        (
            await session.scalars(
                select(KnowledgeTopicLink)
                .join(
                    KnowledgeCandidate,
                    KnowledgeCandidate.id == KnowledgeTopicLink.knowledge_candidate_id,
                )
                .where(
                    KnowledgeTopicLink.project_id == project_id,
                    KnowledgeTopicLink.topic_id.in_(expanded_topic_ids),
                    KnowledgeTopicLink.knowledge_candidate_id.is_not(None),
                    KnowledgeCandidate.project_id == project_id,
                    KnowledgeCandidate.status == "APPROVED",
                    KnowledgeCandidate.locale == locale,
                )
                .order_by(
                    KnowledgeTopicLink.knowledge_candidate_id,
                    KnowledgeTopicLink.topic_id,
                    KnowledgeTopicLink.id,
                )
            )
        ).all()
    )

    links_by_candidate: dict[UUID, list[KnowledgeTopicLink]] = {}
    for link in links:
        if link.knowledge_candidate_id is None:
            continue
        links_by_candidate.setdefault(link.knowledge_candidate_id, []).append(link)

    items: list[dict[str, object]] = []
    for candidate_id in sorted(links_by_candidate, key=str):
        candidate = await session.get(KnowledgeCandidate, candidate_id)
        if candidate is None:
            raise KnowledgeHarvestError("knowledge_harvest_candidate_not_found")
        if candidate.project_id != project_id:
            raise KnowledgeHarvestError("knowledge_harvest_candidate_project_mismatch")
        if candidate.status != "APPROVED":
            raise KnowledgeHarvestError("knowledge_harvest_candidate_not_approved")
        if candidate.locale != locale:
            raise KnowledgeHarvestError("knowledge_harvest_candidate_locale_mismatch")
        if not candidate.reviewer or not candidate.reviewer.strip():
            raise KnowledgeHarvestError("knowledge_harvest_candidate_reviewer_missing")
        if not candidate.review_reason or not candidate.review_reason.strip():
            raise KnowledgeHarvestError("knowledge_harvest_candidate_review_reason_missing")

        snapshot, candidate_content_hash = await verify_candidate_snapshot_lineage(
            session,
            candidate=candidate,
        )
        freshness = await evaluate_freshness(
            session,
            project_id=project_id,
            target_type="knowledge_candidate",
            target_id=candidate.id,
            as_of=as_of,
        )
        scoped_links = [
            {
                "link_id": str(link.id),
                "topic_id": str(link.topic_id),
                "relevance_score": link.relevance_score,
                "link_method": link.link_method,
                "linked_by": link.linked_by,
                "metadata": link.metadata_json,
            }
            for link in links_by_candidate[candidate.id]
        ]
        items.append(
            {
                "candidate_id": str(candidate.id),
                "candidate_content_hash": candidate_content_hash,
                "locale": candidate.locale,
                "statement": candidate.statement,
                "summary": candidate.summary,
                "entity_refs": list(candidate.entity_refs_json),
                "admission": {
                    "status": candidate.status,
                    "reviewer": candidate.reviewer,
                    "review_reason": candidate.review_reason,
                },
                "scoped_topic_links": scoped_links,
                "freshness": _freshness_payload(freshness),
                "lineage": _lineage_payload(snapshot),
            }
        )
    return items


async def harvest_knowledge(
    session: AsyncSession,
    *,
    project_id: UUID,
    root_topic_ids: tuple[UUID, ...],
    locale: str,
    as_of: datetime,
    created_by: str,
    content_case_id: UUID | None = None,
) -> KnowledgeHarvest:
    """Create or exactly replay one deterministic approved-knowledge snapshot."""

    actor = _required_text(
        created_by,
        "knowledge_harvest_created_by_required",
        max_length=200,
    )
    exact_locale = _required_text(locale, "knowledge_harvest_locale_required", max_length=32)
    cutoff = _as_utc(as_of, "knowledge_harvest_as_of_invalid")
    if not root_topic_ids:
        raise KnowledgeHarvestError("knowledge_harvest_root_topic_required")
    if len(set(root_topic_ids)) != len(root_topic_ids):
        raise KnowledgeHarvestError("knowledge_harvest_duplicate_root_topic")
    requested = tuple(sorted(root_topic_ids, key=str))

    await _validate_content_case(
        session,
        project_id=project_id,
        content_case_id=content_case_id,
    )
    expanded = await _active_topic_scope(
        session,
        project_id=project_id,
        root_topic_ids=requested,
    )
    items = await _harvest_items(
        session,
        project_id=project_id,
        locale=exact_locale,
        expanded_topic_ids=expanded,
        as_of=cutoff,
    )
    payload = _snapshot_payload(
        project_id=project_id,
        content_case_id=content_case_id,
        locale=exact_locale,
        as_of=cutoff,
        requested_topic_ids=requested,
        expanded_topic_ids=expanded,
        items=items,
    )
    snapshot_hash = _canonical_hash(payload)

    await _lock_snapshot(
        session,
        project_id=project_id,
        snapshot_hash=snapshot_hash,
    )
    existing = await session.scalar(
        select(KnowledgeHarvest).where(
            KnowledgeHarvest.project_id == project_id,
            KnowledgeHarvest.snapshot_hash == snapshot_hash,
        )
    )
    if existing is not None:
        verify_knowledge_harvest_snapshot(existing)
        if existing.created_by != actor:
            raise KnowledgeHarvestError("knowledge_harvest_replay_actor_conflict")
        return existing

    harvest = KnowledgeHarvest(
        project_id=project_id,
        content_case_id=content_case_id,
        locale=exact_locale,
        as_of=cutoff,
        requested_topic_ids_json=[str(value) for value in requested],
        expanded_topic_ids_json=[str(value) for value in expanded],
        items_json=items,
        harvest_method=HARVEST_METHOD,
        snapshot_hash=snapshot_hash,
        created_by=actor,
    )
    session.add(harvest)
    await session.flush()
    return harvest


__all__ = [
    "HARVEST_METHOD",
    "KnowledgeHarvestError",
    "harvest_knowledge",
    "rebuild_knowledge_harvest_snapshot",
    "verify_knowledge_harvest_snapshot",
]
