from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.knowledge.brief_ref import (
    KNOWLEDGE_BRIEF_MAX_MODEL_BYTES,
    KnowledgeBriefRefError,
    knowledge_brief_snapshot,
)


def _brief(payload: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        brief_method="coverage_bound_knowledge_brief_v1",
        snapshot_hash="a" * 64,
        brief_json=payload,
    )


def test_knowledge_brief_snapshot_allows_bounded_payload() -> None:
    brief = _brief({"summary": "bounded", "items": ["one", "two"]})
    snapshot = knowledge_brief_snapshot(brief)

    assert snapshot["id"] == str(brief.id)
    assert snapshot["payload"] == brief.brief_json
    assert snapshot["payload"] is not brief.brief_json


def test_knowledge_brief_snapshot_rejects_oversized_payload() -> None:
    brief = _brief({"text": "x" * (KNOWLEDGE_BRIEF_MAX_MODEL_BYTES + 1)})

    with pytest.raises(
        KnowledgeBriefRefError,
        match="knowledge_brief_ref_payload_too_large",
    ):
        knowledge_brief_snapshot(brief)
