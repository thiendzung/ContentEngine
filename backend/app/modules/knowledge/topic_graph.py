from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import (
    Claim,
    Entity,
    KnowledgeCandidate,
    KnowledgeChunk,
    Source,
    SourceDocument,
)
from app.modules.knowledge.topic_models import KnowledgeTopicLink, TopicEdge, TopicNode

TopicNodeType = Literal["pillar", "cluster", "topic", "subtopic"]
TopicRelationType = Literal["contains", "related"]
TopicLinkMethod = Literal["manual", "deterministic", "model"]
KnowledgeTargetType = Literal["claim", "knowledge_candidate", "chunk", "entity"]

_NODE_RANK: dict[str, int] = {
    "pillar": 0,
    "cluster": 1,
    "topic": 2,
    "subtopic": 3,
}


class TopicGraphError(ValueError):
    """Raised when a topic graph mutation would violate a durable graph invariant."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def normalize_topic_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"[^\w.-]+", "-", normalized, flags=re.UNICODE)
    normalized = re.sub(r"-+", "-", normalized).strip("-._")
    if not normalized or len(normalized) > 255:
        raise TopicGraphError("topic_canonical_key_invalid")
    return normalized


def _required_text(value: str, code: str, *, max_length: int | None = None) -> str:
    normalized = value.strip()
    if not normalized or (max_length is not None and len(normalized) > max_length):
        raise TopicGraphError(code)
    return normalized


def _metadata(value: Mapping[str, object] | None) -> dict[str, object]:
    return dict(value or {})


async def _load_topic(session: AsyncSession, topic_id: UUID) -> TopicNode:
    topic = await session.get(TopicNode, topic_id)
    if topic is None:
        raise TopicGraphError("topic_not_found")
    return topic


async def ensure_topic_node(
    session: AsyncSession,
    *,
    project_id: UUID,
    canonical_key: str,
    name: str,
    node_type: TopicNodeType,
    description: str | None = None,
    metadata_json: Mapping[str, object] | None = None,
) -> TopicNode:
    """Create or exactly replay one canonical active topic node."""

    key = normalize_topic_key(canonical_key)
    display_name = _required_text(name, "topic_name_required", max_length=500)
    if node_type not in _NODE_RANK:
        raise TopicGraphError("topic_node_type_invalid")
    normalized_description = description.strip() if description is not None else None
    if normalized_description == "":
        normalized_description = None
    metadata = _metadata(metadata_json)

    existing = await session.scalar(
        select(TopicNode).where(
            TopicNode.project_id == project_id,
            TopicNode.canonical_key == key,
        )
    )
    if existing is not None:
        if (
            existing.name != display_name
            or existing.node_type != node_type
            or existing.description != normalized_description
            or existing.metadata_json != metadata
            or existing.status != "active"
        ):
            raise TopicGraphError("topic_node_replay_conflict")
        return existing

    topic = TopicNode(
        project_id=project_id,
        canonical_key=key,
        name=display_name,
        node_type=node_type,
        description=normalized_description,
        status="active",
        metadata_json=metadata,
    )
    session.add(topic)
    await session.flush()
    return topic


async def _contains_reaches(
    session: AsyncSession,
    *,
    project_id: UUID,
    start_topic_id: UUID,
    target_topic_id: UUID,
) -> bool:
    if start_topic_id == target_topic_id:
        return True

    frontier: set[UUID] = {start_topic_id}
    seen: set[UUID] = set()
    while frontier:
        batch = frontier - seen
        if not batch:
            return False
        seen.update(batch)
        children = set(
            (
                await session.scalars(
                    select(TopicEdge.child_topic_id).where(
                        TopicEdge.project_id == project_id,
                        TopicEdge.relation_type == "contains",
                        TopicEdge.parent_topic_id.in_(batch),
                    )
                )
            ).all()
        )
        if target_topic_id in children:
            return True
        frontier = children
    return False


async def ensure_topic_edge(
    session: AsyncSession,
    *,
    project_id: UUID,
    parent_topic_id: UUID,
    child_topic_id: UUID,
    relation_type: TopicRelationType,
    created_by: str,
    metadata_json: Mapping[str, object] | None = None,
) -> TopicEdge:
    """Create or exactly replay one hierarchy/related edge.

    Related edges are stored in UUID order because their semantics are symmetric.
    Contains edges remain directional and are checked for hierarchy cycles.
    """

    actor = _required_text(created_by, "topic_edge_actor_required", max_length=200)
    metadata = _metadata(metadata_json)
    if relation_type not in {"contains", "related"}:
        raise TopicGraphError("topic_relation_type_invalid")
    if parent_topic_id == child_topic_id:
        raise TopicGraphError("topic_edge_self_link")

    if relation_type == "related" and str(parent_topic_id) > str(child_topic_id):
        parent_topic_id, child_topic_id = child_topic_id, parent_topic_id

    parent = await _load_topic(session, parent_topic_id)
    child = await _load_topic(session, child_topic_id)
    if parent.project_id != project_id or child.project_id != project_id:
        raise TopicGraphError("topic_edge_project_mismatch")
    if parent.status != "active" or child.status != "active":
        raise TopicGraphError("topic_edge_requires_active_topics")

    existing = await session.scalar(
        select(TopicEdge).where(
            TopicEdge.project_id == project_id,
            TopicEdge.parent_topic_id == parent.id,
            TopicEdge.child_topic_id == child.id,
            TopicEdge.relation_type == relation_type,
        )
    )
    if existing is not None:
        if existing.created_by != actor or existing.metadata_json != metadata:
            raise TopicGraphError("topic_edge_replay_conflict")
        return existing

    if relation_type == "contains":
        if await _contains_reaches(
            session,
            project_id=project_id,
            start_topic_id=child.id,
            target_topic_id=parent.id,
        ):
            raise TopicGraphError("topic_contains_cycle")
        if _NODE_RANK[parent.node_type] >= _NODE_RANK[child.node_type]:
            raise TopicGraphError("topic_contains_hierarchy_invalid")

    edge = TopicEdge(
        project_id=project_id,
        parent_topic_id=parent.id,
        child_topic_id=child.id,
        relation_type=relation_type,
        created_by=actor,
        metadata_json=metadata,
    )
    session.add(edge)
    await session.flush()
    return edge


async def descendant_topic_ids(
    session: AsyncSession,
    *,
    project_id: UUID,
    root_topic_id: UUID,
    include_root: bool = True,
) -> tuple[UUID, ...]:
    """Expand only hierarchical `contains` edges in deterministic UUID order."""

    root = await _load_topic(session, root_topic_id)
    if root.project_id != project_id:
        raise TopicGraphError("topic_scope_project_mismatch")

    output: set[UUID] = {root.id} if include_root else set()
    frontier: set[UUID] = {root.id}
    seen: set[UUID] = set()
    while frontier:
        batch = frontier - seen
        if not batch:
            break
        seen.update(batch)
        children = set(
            (
                await session.scalars(
                    select(TopicEdge.child_topic_id).where(
                        TopicEdge.project_id == project_id,
                        TopicEdge.relation_type == "contains",
                        TopicEdge.parent_topic_id.in_(batch),
                    )
                )
            ).all()
        )
        output.update(children)
        frontier = children
    return tuple(sorted(output, key=str))


async def _target_project_id(
    session: AsyncSession,
    *,
    target_type: KnowledgeTargetType,
    target_id: UUID,
) -> UUID:
    if target_type == "claim":
        claim = await session.get(Claim, target_id)
        if claim is None:
            raise TopicGraphError("topic_link_claim_not_found")
        return claim.project_id
    if target_type == "knowledge_candidate":
        candidate = await session.get(KnowledgeCandidate, target_id)
        if candidate is None:
            raise TopicGraphError("topic_link_candidate_not_found")
        return candidate.project_id
    if target_type == "entity":
        entity = await session.get(Entity, target_id)
        if entity is None:
            raise TopicGraphError("topic_link_entity_not_found")
        return entity.project_id
    if target_type == "chunk":
        project_id = await session.scalar(
            select(Source.project_id)
            .join(SourceDocument, SourceDocument.source_id == Source.id)
            .join(KnowledgeChunk, KnowledgeChunk.source_document_id == SourceDocument.id)
            .where(KnowledgeChunk.id == target_id)
        )
        if project_id is None:
            raise TopicGraphError("topic_link_chunk_not_found")
        return project_id
    raise TopicGraphError("topic_link_target_type_invalid")


async def ensure_knowledge_topic_link(
    session: AsyncSession,
    *,
    project_id: UUID,
    topic_id: UUID,
    target_type: KnowledgeTargetType,
    target_id: UUID,
    link_method: TopicLinkMethod,
    linked_by: str,
    relevance_score: int = 1000,
    metadata_json: Mapping[str, object] | None = None,
) -> KnowledgeTopicLink:
    """Create or exactly replay one topic link without changing factual authority."""

    topic = await _load_topic(session, topic_id)
    if topic.project_id != project_id:
        raise TopicGraphError("topic_link_project_mismatch")
    if topic.status != "active":
        raise TopicGraphError("topic_link_requires_active_topic")
    if link_method not in {"manual", "deterministic", "model"}:
        raise TopicGraphError("topic_link_method_invalid")
    actor = _required_text(linked_by, "topic_link_actor_required", max_length=200)
    if relevance_score < 0 or relevance_score > 1000:
        raise TopicGraphError("topic_link_relevance_invalid")
    if await _target_project_id(
        session,
        target_type=target_type,
        target_id=target_id,
    ) != project_id:
        raise TopicGraphError("topic_link_target_project_mismatch")
    metadata = _metadata(metadata_json)

    target_column = {
        "claim": KnowledgeTopicLink.claim_id,
        "knowledge_candidate": KnowledgeTopicLink.knowledge_candidate_id,
        "chunk": KnowledgeTopicLink.chunk_id,
        "entity": KnowledgeTopicLink.entity_id,
    }[target_type]
    existing = await session.scalar(
        select(KnowledgeTopicLink).where(
            KnowledgeTopicLink.topic_id == topic.id,
            target_column == target_id,
        )
    )
    if existing is not None:
        if (
            existing.project_id != project_id
            or existing.relevance_score != relevance_score
            or existing.link_method != link_method
            or existing.linked_by != actor
            or existing.metadata_json != metadata
        ):
            raise TopicGraphError("topic_link_replay_conflict")
        return existing

    link = KnowledgeTopicLink(
        project_id=project_id,
        topic_id=topic.id,
        claim_id=target_id if target_type == "claim" else None,
        knowledge_candidate_id=(
            target_id if target_type == "knowledge_candidate" else None
        ),
        chunk_id=target_id if target_type == "chunk" else None,
        entity_id=target_id if target_type == "entity" else None,
        relevance_score=relevance_score,
        link_method=link_method,
        linked_by=actor,
        metadata_json=metadata,
    )
    session.add(link)
    await session.flush()
    return link


__all__ = [
    "KnowledgeTargetType",
    "TopicGraphError",
    "TopicLinkMethod",
    "TopicNodeType",
    "TopicRelationType",
    "descendant_topic_ids",
    "ensure_knowledge_topic_link",
    "ensure_topic_edge",
    "ensure_topic_node",
    "normalize_topic_key",
]
