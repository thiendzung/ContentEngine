from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.modules.knowledge.harvest import (
    rebuild_knowledge_harvest_snapshot,
    verify_knowledge_harvest_snapshot,
)
from app.modules.knowledge.harvest_models import KnowledgeHarvest

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
PROJECT_ID = UUID("10000000-0000-0000-0000-000000000001")
TOPIC_A = UUID("20000000-0000-0000-0000-000000000001")
TOPIC_B = UUID("20000000-0000-0000-0000-000000000002")
CANDIDATE_A = UUID("30000000-0000-0000-0000-000000000001")
CANDIDATE_B = UUID("30000000-0000-0000-0000-000000000002")
LINK_A = UUID("40000000-0000-0000-0000-000000000001")
EVIDENCE_SET = UUID("50000000-0000-0000-0000-000000000001")
CLAIM = UUID("60000000-0000-0000-0000-000000000001")
EVIDENCE = UUID("70000000-0000-0000-0000-000000000001")
DOCUMENT = UUID("80000000-0000-0000-0000-000000000001")
SOURCE = UUID("90000000-0000-0000-0000-000000000001")


def valid_scope_graph() -> dict[str, object]:
    return {
        "topics": [
            {
                "topic_id": str(TOPIC_A),
                "canonical_key": "synthetic-topic-a",
                "name": "Synthetic Topic A",
                "node_type": "topic",
                "description": "Synthetic K3 scope topic.",
                "status": "active",
                "metadata": {"fixture": "k3"},
            }
        ],
        "contains_edges": [],
    }


def valid_item(*, candidate_id: UUID, topic_id: UUID = TOPIC_A) -> dict[str, object]:
    return {
        "candidate_id": str(candidate_id),
        "candidate_content_hash": "a" * 64,
        "locale": "en",
        "statement": "Synthetic approved fact.",
        "summary": "Synthetic approved fact with verified provenance.",
        "entity_refs": [],
        "admission": {
            "status": "APPROVED",
            "reviewer": "founder",
            "review_reason": "Synthetic semantic-integrity fixture.",
        },
        "scoped_topic_links": [
            {
                "link_id": str(LINK_A),
                "topic_id": str(topic_id),
                "relevance_score": 1000,
                "link_method": "manual",
                "linked_by": "founder",
                "metadata": {},
            }
        ],
        "freshness": {
            "state": "FRESH",
            "policy_id": None,
            "policy_key": None,
            "policy_version": None,
            "freshness_class": None,
            "policy_source": None,
            "policy_topic_id": None,
            "verification_id": None,
            "verified_at": None,
            "due_at": None,
            "stale_at": None,
            "reasons": ["within_freshness_window"],
        },
        "lineage": {
            "evidence_set": {
                "id": str(EVIDENCE_SET),
                "version": 1,
                "content_hash": "b" * 64,
            },
            "claim_id": str(CLAIM),
            "evidence_ids": [str(EVIDENCE)],
            "source_document_ids": [str(DOCUMENT)],
            "source_ids": [str(SOURCE)],
            "relation_counts": {"supports": 1, "contradicts": 0, "context": 0},
            "evidence_refs": [{}],
        },
    }


def valid_harvest() -> KnowledgeHarvest:
    return KnowledgeHarvest(
        project_id=PROJECT_ID,
        content_case_id=None,
        locale="en",
        as_of=T0,
        requested_topic_ids_json=[str(TOPIC_A)],
        expanded_topic_ids_json=[str(TOPIC_A)],
        scope_graph_json=valid_scope_graph(),
        items_json=[valid_item(candidate_id=CANDIDATE_A)],
        harvest_method="approved_candidate_topic_scope_v1",
        snapshot_hash="f" * 64,
        created_by="policy:k3-test",
    )


def test_verifier_rejects_requested_topic_outside_expanded_scope() -> None:
    harvest = valid_harvest()
    harvest.requested_topic_ids_json = [str(TOPIC_B)]
    with pytest.raises(ValueError, match="knowledge_harvest_requested_not_in_expanded"):
        verify_knowledge_harvest_snapshot(harvest)


def test_verifier_rejects_scope_graph_missing_expanded_topic() -> None:
    harvest = valid_harvest()
    harvest.scope_graph_json = {"topics": [], "contains_edges": []}
    with pytest.raises(ValueError, match="knowledge_harvest_scope_topics_required"):
        verify_knowledge_harvest_snapshot(harvest)


def test_scope_graph_semantics_are_bound_into_snapshot_hash() -> None:
    harvest = valid_harvest()
    _, snapshot_hash = rebuild_knowledge_harvest_snapshot(harvest)
    harvest.snapshot_hash = snapshot_hash
    verify_knowledge_harvest_snapshot(harvest)

    graph = deepcopy(harvest.scope_graph_json)
    topics = graph["topics"]
    assert isinstance(topics, list)
    topic = topics[0]
    assert isinstance(topic, dict)
    topic["name"] = "Changed Topic Meaning"
    harvest.scope_graph_json = graph
    with pytest.raises(ValueError, match="knowledge_harvest_snapshot_hash_mismatch"):
        verify_knowledge_harvest_snapshot(harvest)


def test_verifier_rejects_duplicate_candidate_items() -> None:
    harvest = valid_harvest()
    harvest.items_json = [deepcopy(harvest.items_json[0]), deepcopy(harvest.items_json[0])]
    with pytest.raises(ValueError, match="knowledge_harvest_candidate_duplicate"):
        verify_knowledge_harvest_snapshot(harvest)


def test_verifier_rejects_scoped_topic_link_outside_expanded_scope() -> None:
    harvest = valid_harvest()
    item = deepcopy(harvest.items_json[0])
    assert isinstance(item, dict)
    links = item["scoped_topic_links"]
    assert isinstance(links, list)
    link = links[0]
    assert isinstance(link, dict)
    link["topic_id"] = str(TOPIC_B)
    harvest.items_json = [item]
    with pytest.raises(ValueError, match="knowledge_harvest_scoped_topic_outside_scope"):
        verify_knowledge_harvest_snapshot(harvest)


def test_verifier_rejects_noncanonical_candidate_order() -> None:
    harvest = valid_harvest()
    first = valid_item(candidate_id=CANDIDATE_A)
    second = valid_item(candidate_id=CANDIDATE_B)
    harvest.items_json = [second, first]
    with pytest.raises(ValueError, match="knowledge_harvest_items_not_canonical"):
        verify_knowledge_harvest_snapshot(harvest)


def test_verifier_rejects_invalid_freshness_state() -> None:
    harvest = valid_harvest()
    item = deepcopy(harvest.items_json[0])
    assert isinstance(item, dict)
    freshness = item["freshness"]
    assert isinstance(freshness, dict)
    freshness["state"] = "MAYBE_FRESH"
    harvest.items_json = [item]
    with pytest.raises(ValueError, match="knowledge_harvest_freshness_state_invalid"):
        verify_knowledge_harvest_snapshot(harvest)
