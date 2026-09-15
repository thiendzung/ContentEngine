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
_FRESHNESS_STATES = {"FRESH", "DUE", "STALE", "UNKNOWN", "UNCLASSIFIED"}
_LINK_METHODS = {"manual", "deterministic", "model"}
_TOPIC_NODE_TYPES = {"pillar", "cluster", "topic", "subtopic"}
_SCOPE_GRAPH_KEYS = {"topics", "contains_edges"}
_TOPIC_SNAPSHOT_KEYS = {
    "topic_id",
    "canonical_key",
    "name",
    "node_type",
    "description",
    "status",
    "metadata",
}
_EDGE_SNAPSHOT_KEYS = {
    "edge_id",
    "parent_topic_id",
    "child_topic_id",
    "relation_type",
    "created_by",
    "metadata",
}


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
    scope_graph: dict[str, object],
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
        "scope_graph": scope_graph,
        "items": items,
    }


def _mapping(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise KnowledgeHarvestError(code)
    return value


def _list(value: object, code: str) -> list[object]:
    if not isinstance(value, list):
        raise KnowledgeHarvestError(code)
    return value


def _canonical_uuid_text(value: object, code: str) -> str:
    if not isinstance(value, str):
        raise KnowledgeHarvestError(code)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise KnowledgeHarvestError(code) from exc
    canonical = str(parsed)
    if value != canonical:
        raise KnowledgeHarvestError(code)
    return canonical


def _canonical_uuid_tuple(
    value: object,
    *,
    invalid_code: str,
    empty_code: str,
    canonical_code: str,
) -> tuple[UUID, ...]:
    raw = _list(value, invalid_code)
    if not raw:
        raise KnowledgeHarvestError(empty_code)
    parsed = tuple(UUID(_canonical_uuid_text(item, invalid_code)) for item in raw)
    if len(set(parsed)) != len(parsed) or parsed != tuple(sorted(parsed, key=str)):
        raise KnowledgeHarvestError(canonical_code)
    return parsed


def _validate_scope_graph(
    value: object,
    *,
    expanded_topic_ids: set[str],
) -> dict[str, object]:
    graph = _mapping(value, "knowledge_harvest_scope_graph_invalid")
    if set(graph) != _SCOPE_GRAPH_KEYS:
        raise KnowledgeHarvestError("knowledge_harvest_scope_graph_shape_invalid")

    raw_topics = _list(graph.get("topics"), "knowledge_harvest_scope_topics_invalid")
    if not raw_topics:
        raise KnowledgeHarvestError("knowledge_harvest_scope_topics_required")
    topics: list[dict[str, object]] = []
    topic_ids: list[str] = []
    for raw_topic in raw_topics:
        topic = _mapping(raw_topic, "knowledge_harvest_scope_topic_invalid")
        if set(topic) != _TOPIC_SNAPSHOT_KEYS:
            raise KnowledgeHarvestError("knowledge_harvest_scope_topic_shape_invalid")
        topic_id = _canonical_uuid_text(
            topic.get("topic_id"),
            "knowledge_harvest_scope_topic_id_invalid",
        )
        if topic_id not in expanded_topic_ids:
            raise KnowledgeHarvestError("knowledge_harvest_scope_topic_outside_scope")
        canonical_key = topic.get("canonical_key")
        name = topic.get("name")
        node_type = topic.get("node_type")
        description = topic.get("description")
        if not isinstance(canonical_key, str) or not canonical_key.strip():
            raise KnowledgeHarvestError("knowledge_harvest_scope_topic_invalid")
        if not isinstance(name, str) or not name.strip():
            raise KnowledgeHarvestError("knowledge_harvest_scope_topic_invalid")
        if node_type not in _TOPIC_NODE_TYPES:
            raise KnowledgeHarvestError("knowledge_harvest_scope_topic_invalid")
        if description is not None and not isinstance(description, str):
            raise KnowledgeHarvestError("knowledge_harvest_scope_topic_invalid")
        if topic.get("status") != "active":
            raise KnowledgeHarvestError("knowledge_harvest_scope_topic_not_active")
        _mapping(topic.get("metadata"), "knowledge_harvest_scope_topic_invalid")
        topic_ids.append(topic_id)
        topics.append(topic)

    if len(set(topic_ids)) != len(topic_ids):
        raise KnowledgeHarvestError("knowledge_harvest_scope_topic_duplicate")
    if set(topic_ids) != expanded_topic_ids:
        raise KnowledgeHarvestError("knowledge_harvest_scope_topic_set_mismatch")
    if topic_ids != sorted(topic_ids):
        raise KnowledgeHarvestError("knowledge_harvest_scope_topics_not_canonical")

    raw_edges = _list(
        graph.get("contains_edges"),
        "knowledge_harvest_scope_edges_invalid",
    )
    edges: list[dict[str, object]] = []
    edge_ids: set[str] = set()
    edge_sort_keys: list[tuple[str, str, str]] = []
    edge_pairs: set[tuple[str, str]] = set()
    for raw_edge in raw_edges:
        edge = _mapping(raw_edge, "knowledge_harvest_scope_edge_invalid")
        if set(edge) != _EDGE_SNAPSHOT_KEYS:
            raise KnowledgeHarvestError("knowledge_harvest_scope_edge_shape_invalid")
        edge_id = _canonical_uuid_text(
            edge.get("edge_id"),
            "knowledge_harvest_scope_edge_id_invalid",
        )
        parent_id = _canonical_uuid_text(
            edge.get("parent_topic_id"),
            "knowledge_harvest_scope_edge_topic_id_invalid",
        )
        child_id = _canonical_uuid_text(
            edge.get("child_topic_id"),
            "knowledge_harvest_scope_edge_topic_id_invalid",
        )
        if parent_id not in expanded_topic_ids or child_id not in expanded_topic_ids:
            raise KnowledgeHarvestError("knowledge_harvest_scope_edge_outside_scope")
        if parent_id == child_id or edge.get("relation_type") != "contains":
            raise KnowledgeHarvestError("knowledge_harvest_scope_edge_invalid")
        created_by = edge.get("created_by")
        if not isinstance(created_by, str) or not created_by.strip():
            raise KnowledgeHarvestError("knowledge_harvest_scope_edge_invalid")
        _mapping(edge.get("metadata"), "knowledge_harvest_scope_edge_invalid")
        if edge_id in edge_ids:
            raise KnowledgeHarvestError("knowledge_harvest_scope_edge_duplicate")
        pair = (parent_id, child_id)
        if pair in edge_pairs:
            raise KnowledgeHarvestError("knowledge_harvest_scope_edge_duplicate")
        edge_ids.add(edge_id)
        edge_pairs.add(pair)
        edge_sort_keys.append((parent_id, child_id, edge_id))
        edges.append(edge)

    if edge_sort_keys != sorted(edge_sort_keys):
        raise KnowledgeHarvestError("knowledge_harvest_scope_edges_not_canonical")
    return {"topics": topics, "contains_edges": edges}


def _validate_lineage(item: dict[str, object]) -> None:
    lineage = _mapping(item.get("lineage"), "knowledge_harvest_lineage_invalid")
    evidence_set = _mapping(
        lineage.get("evidence_set"),
        "knowledge_harvest_lineage_evidence_set_invalid",
    )
    _canonical_uuid_text(
        evidence_set.get("id"),
        "knowledge_harvest_lineage_evidence_set_invalid",
    )
    version = evidence_set.get("version")
    if not isinstance(version, int) or version < 1:
        raise KnowledgeHarvestError("knowledge_harvest_lineage_evidence_set_invalid")
    content_hash = evidence_set.get("content_hash")
    if not isinstance(content_hash, str) or len(content_hash) != 64:
        raise KnowledgeHarvestError("knowledge_harvest_lineage_evidence_set_invalid")
    _canonical_uuid_text(lineage.get("claim_id"), "knowledge_harvest_lineage_claim_invalid")
    for key in ("evidence_ids", "source_document_ids", "source_ids"):
        values = _list(lineage.get(key), f"knowledge_harvest_lineage_{key}_invalid")
        if not values:
            raise KnowledgeHarvestError(f"knowledge_harvest_lineage_{key}_invalid")
        canonical = [
            _canonical_uuid_text(value, f"knowledge_harvest_lineage_{key}_invalid")
            for value in values
        ]
        if len(set(canonical)) != len(canonical):
            raise KnowledgeHarvestError(f"knowledge_harvest_lineage_{key}_invalid")
    _mapping(
        lineage.get("relation_counts"),
        "knowledge_harvest_lineage_relation_counts_invalid",
    )
    refs = _list(
        lineage.get("evidence_refs"),
        "knowledge_harvest_lineage_evidence_refs_invalid",
    )
    if not refs or any(not isinstance(value, dict) for value in refs):
        raise KnowledgeHarvestError("knowledge_harvest_lineage_evidence_refs_invalid")


def _validate_scoped_links(
    item: dict[str, object],
    *,
    expanded_topic_ids: set[str],
) -> None:
    raw_links = _list(
        item.get("scoped_topic_links"),
        "knowledge_harvest_scoped_topic_links_invalid",
    )
    if not raw_links:
        raise KnowledgeHarvestError("knowledge_harvest_scoped_topic_links_required")

    topic_ids: set[str] = set()
    sort_keys: list[tuple[str, str]] = []
    for raw_link in raw_links:
        link = _mapping(raw_link, "knowledge_harvest_scoped_topic_link_invalid")
        link_id = _canonical_uuid_text(
            link.get("link_id"),
            "knowledge_harvest_scoped_topic_link_invalid",
        )
        topic_id = _canonical_uuid_text(
            link.get("topic_id"),
            "knowledge_harvest_scoped_topic_link_invalid",
        )
        if topic_id not in expanded_topic_ids:
            raise KnowledgeHarvestError("knowledge_harvest_scoped_topic_outside_scope")
        if topic_id in topic_ids:
            raise KnowledgeHarvestError("knowledge_harvest_scoped_topic_duplicate")
        topic_ids.add(topic_id)
        sort_keys.append((topic_id, link_id))

        relevance = link.get("relevance_score")
        if not isinstance(relevance, int) or not 0 <= relevance <= 1000:
            raise KnowledgeHarvestError("knowledge_harvest_scoped_topic_link_invalid")
        if link.get("link_method") not in _LINK_METHODS:
            raise KnowledgeHarvestError("knowledge_harvest_scoped_topic_link_invalid")
        linked_by = link.get("linked_by")
        if not isinstance(linked_by, str) or not linked_by.strip():
            raise KnowledgeHarvestError("knowledge_harvest_scoped_topic_link_invalid")
        _mapping(link.get("metadata"), "knowledge_harvest_scoped_topic_link_invalid")

    if sort_keys != sorted(sort_keys):
        raise KnowledgeHarvestError("knowledge_harvest_scoped_topic_links_not_canonical")


def _validate_item(
    item: dict[str, object],
    *,
    locale: str,
    expanded_topic_ids: set[str],
) -> str:
    candidate_id = _canonical_uuid_text(
        item.get("candidate_id"),
        "knowledge_harvest_candidate_id_invalid",
    )
    candidate_hash = item.get("candidate_content_hash")
    if (
        not isinstance(candidate_hash, str)
        or len(candidate_hash) != 64
        or any(char not in "0123456789abcdef" for char in candidate_hash)
    ):
        raise KnowledgeHarvestError("knowledge_harvest_candidate_hash_invalid")
    if item.get("locale") != locale:
        raise KnowledgeHarvestError("knowledge_harvest_item_locale_mismatch")
    statement = item.get("statement")
    if not isinstance(statement, str) or not statement.strip():
        raise KnowledgeHarvestError("knowledge_harvest_candidate_text_invalid")
    summary = item.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise KnowledgeHarvestError("knowledge_harvest_candidate_text_invalid")
    _list(item.get("entity_refs"), "knowledge_harvest_candidate_entity_refs_invalid")

    admission = _mapping(item.get("admission"), "knowledge_harvest_admission_invalid")
    if admission.get("status") != "APPROVED":
        raise KnowledgeHarvestError("knowledge_harvest_candidate_not_approved")
    for field in ("reviewer", "review_reason"):
        value = admission.get(field)
        if not isinstance(value, str) or not value.strip():
            raise KnowledgeHarvestError("knowledge_harvest_admission_invalid")

    freshness = _mapping(item.get("freshness"), "knowledge_harvest_freshness_invalid")
    if freshness.get("state") not in _FRESHNESS_STATES:
        raise KnowledgeHarvestError("knowledge_harvest_freshness_state_invalid")
    reasons = _list(freshness.get("reasons"), "knowledge_harvest_freshness_invalid")
    if any(not isinstance(reason, str) or not reason for reason in reasons):
        raise KnowledgeHarvestError("knowledge_harvest_freshness_invalid")

    _validate_scoped_links(item, expanded_topic_ids=expanded_topic_ids)
    _validate_lineage(item)
    return candidate_id


def rebuild_knowledge_harvest_snapshot(
    harvest: KnowledgeHarvest,
) -> tuple[dict[str, object], str]:
    """Rebuild and semantically validate a persisted immutable harvest snapshot."""

    requested_topic_ids = _canonical_uuid_tuple(
        harvest.requested_topic_ids_json,
        invalid_code="knowledge_harvest_topic_id_invalid",
        empty_code="knowledge_harvest_requested_topic_required",
        canonical_code="knowledge_harvest_requested_topics_not_canonical",
    )
    expanded_topic_ids = _canonical_uuid_tuple(
        harvest.expanded_topic_ids_json,
        invalid_code="knowledge_harvest_topic_id_invalid",
        empty_code="knowledge_harvest_expanded_topic_required",
        canonical_code="knowledge_harvest_expanded_topics_not_canonical",
    )
    if not set(requested_topic_ids).issubset(expanded_topic_ids):
        raise KnowledgeHarvestError("knowledge_harvest_requested_not_in_expanded")

    expanded_text = {str(value) for value in expanded_topic_ids}
    scope_graph = _validate_scope_graph(
        harvest.scope_graph_json,
        expanded_topic_ids=expanded_text,
    )
    raw_items = _list(harvest.items_json, "knowledge_harvest_items_invalid")
    items = [_mapping(item, "knowledge_harvest_item_invalid") for item in raw_items]
    candidate_ids = [
        _validate_item(
            item,
            locale=harvest.locale,
            expanded_topic_ids=expanded_text,
        )
        for item in items
    ]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise KnowledgeHarvestError("knowledge_harvest_candidate_duplicate")
    if candidate_ids != sorted(candidate_ids):
        raise KnowledgeHarvestError("knowledge_harvest_items_not_canonical")

    payload = _snapshot_payload(
        project_id=harvest.project_id,
        content_case_id=harvest.content_case_id,
        locale=harvest.locale,
        as_of=_as_utc(harvest.as_of, "knowledge_harvest_as_of_invalid"),
        requested_topic_ids=requested_topic_ids,
        expanded_topic_ids=expanded_topic_ids,
        scope_graph=scope_graph,
        items=items,
    )
    return payload, _canonical_hash(payload)


def verify_knowledge_harvest_snapshot(harvest: KnowledgeHarvest) -> dict[str, object]:
    """Fail closed before any downstream K4/K5 consumer uses the snapshot."""

    if harvest.harvest_method != HARVEST_METHOD:
        raise KnowledgeHarvestError("knowledge_harvest_method_invalid")
    payload, recomputed_hash = rebuild_knowledge_harvest_snapshot(harvest)
    if recomputed_hash != harvest.snapshot_hash:
        raise KnowledgeHarvestError("knowledge_harvest_snapshot_hash_mismatch")
    return payload


def _advisory_lock_key(project_id: UUID, snapshot_hash: str) -> int:
    digest = hashlib.sha256(f"{project_id}:{snapshot_hash}".encode()).digest()
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


async def _snapshot_scope_graph(
    session: AsyncSession,
    *,
    project_id: UUID,
    expanded_topic_ids: tuple[UUID, ...],
) -> dict[str, object]:
    topics = tuple(
        (
            await session.scalars(
                select(TopicNode)
                .where(
                    TopicNode.project_id == project_id,
                    TopicNode.id.in_(expanded_topic_ids),
                    TopicNode.status == "active",
                )
                .order_by(TopicNode.id)
            )
        ).all()
    )
    if tuple(topic.id for topic in topics) != expanded_topic_ids:
        raise KnowledgeHarvestError("knowledge_harvest_scope_topic_set_changed")

    edges = tuple(
        (
            await session.scalars(
                select(TopicEdge)
                .where(
                    TopicEdge.project_id == project_id,
                    TopicEdge.relation_type == "contains",
                    TopicEdge.parent_topic_id.in_(expanded_topic_ids),
                    TopicEdge.child_topic_id.in_(expanded_topic_ids),
                )
                .order_by(
                    TopicEdge.parent_topic_id,
                    TopicEdge.child_topic_id,
                    TopicEdge.id,
                )
            )
        ).all()
    )
    return {
        "topics": [
            {
                "topic_id": str(topic.id),
                "canonical_key": topic.canonical_key,
                "name": topic.name,
                "node_type": topic.node_type,
                "description": topic.description,
                "status": topic.status,
                "metadata": topic.metadata_json,
            }
            for topic in topics
        ],
        "contains_edges": [
            {
                "edge_id": str(edge.id),
                "parent_topic_id": str(edge.parent_topic_id),
                "child_topic_id": str(edge.child_topic_id),
                "relation_type": edge.relation_type,
                "created_by": edge.created_by,
                "metadata": edge.metadata_json,
            }
            for edge in edges
        ],
    }


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
    scope_graph = await _snapshot_scope_graph(
        session,
        project_id=project_id,
        expanded_topic_ids=expanded,
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
        scope_graph=scope_graph,
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
        return existing

    harvest = KnowledgeHarvest(
        project_id=project_id,
        content_case_id=content_case_id,
        locale=exact_locale,
        as_of=cutoff,
        requested_topic_ids_json=[str(value) for value in requested],
        expanded_topic_ids_json=[str(value) for value in expanded],
        scope_graph_json=scope_graph,
        items_json=items,
        harvest_method=HARVEST_METHOD,
        snapshot_hash=snapshot_hash,
        created_by=actor,
    )
    verify_knowledge_harvest_snapshot(harvest)
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
