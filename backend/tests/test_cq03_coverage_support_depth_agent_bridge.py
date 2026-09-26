from __future__ import annotations

from app.modules.content_engine.journal.coverage_support_depth_agent_bridge import (
    _bind_output_schema,
)
from app.modules.content_engine.journal.coverage_support_depth_eval import (
    build_coverage_support_depth_model_input,
)


def _base_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "integer"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "requirement_id": {"type": "string"},
                        "status": {"type": "string"},
                        "evidence_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "caveat_evidence_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "originality_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "rationale": {"type": "string"},
                        "gaps": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            },
        },
    }


def test_output_schema_binds_exact_allowed_refs() -> None:
    model_input = build_coverage_support_depth_model_input(
        coverage_requirements=["One", "Two"],
        evidence_items=[
            {"evidence_id": "ev-support", "relation": "supports"},
            {"evidence_id": "ev-context", "relation": "context_only"},
        ],
        originality_items=[
            {
                "type": "motgu_owned_material",
                "source_ref": "motgu:one",
                "material": "Owned material",
                "writer_use": "Use as first-party context",
                "guardrails": "Do not call it external proof",
                "approval_ref": "approval:one",
            }
        ],
        evidence_set_ref={"id": "es", "version": 1, "content_hash": "a" * 64},
        originality_pack_ref={"id": "op", "snapshot_hash": "b" * 64},
    )

    schema = _bind_output_schema(_base_schema(), model_input=model_input)
    items = schema["properties"]["items"]  # type: ignore[index]
    assert items["minItems"] == 2  # type: ignore[index]
    assert items["maxItems"] == 2  # type: ignore[index]
    props = items["items"]["properties"]  # type: ignore[index]
    assert props["requirement_id"]["enum"] == ["coverage-1", "coverage-2"]
    assert props["evidence_refs"]["items"]["enum"] == ["ev-support"]
    assert props["caveat_evidence_refs"]["items"]["enum"] == ["ev-context"]
    assert props["originality_refs"]["items"]["enum"] == ["motgu:one"]
