from __future__ import annotations

import copy
from dataclasses import replace
from typing import cast

import pytest
from test_ce05_assertion_audit import _passing_output, _source, isolated_session

from app.modules.content_engine.journal.assertion_audit import (
    _summary,
    validate_assertion_audit_output,
)
from app.modules.content_engine.journal.assertion_audit_agent_bridge import (
    _sanitize_supported_evidence_refs,
)


def test_assertion_audit_bridge_keeps_only_supportive_allowed_refs_for_supported_claim() -> None:
    model_input: dict[str, object] = {
        "evidence_catalog": [
            {"evidence_id": "support", "evidence_relation": "supports"},
            {"evidence_id": "qualify", "evidence_relation": "qualifies"},
            {"evidence_id": "context", "evidence_relation": "context_only"},
            {"evidence_id": "contra", "evidence_relation": "contradicts"},
        ],
        "source_segments": [
            {
                "segment_id": "lead:1",
                "allowed_evidence_refs": ["support", "qualify", "context", "contra"],
            }
        ],
    }
    raw: dict[str, object] = {
        "locale": "en",
        "segments": [
            {
                "segment_id": "lead:1",
                "assertions": [
                    {
                        "support_status": "supported",
                        "evidence_refs": ["support", "context", "qualify", "contra"],
                    }
                ],
            }
        ],
    }

    normalized, removed = _sanitize_supported_evidence_refs(raw, audit_model_input=model_input)

    assert removed == 2
    normalized_payload = cast(dict[str, object], normalized)
    segment = cast(list[dict[str, object]], normalized_payload["segments"])[0]
    assertion = cast(list[dict[str, object]], segment["assertions"])[0]
    assert assertion["evidence_refs"] == ["support", "qualify"]
    assert cast(list[dict[str, object]], cast(dict[str, object], raw)["segments"])[0][
        "assertions"
    ] == [
        {
            "support_status": "supported",
            "evidence_refs": ["support", "context", "qualify", "contra"],
        }
    ]


@pytest.mark.asyncio
async def test_context_only_supported_ref_becomes_quality_failure() -> None:
    async with isolated_session() as session:
        _fixture, _source_artifact, audit_input = await _source(session)
        target = next(
            segment
            for segment in audit_input.segments
            if segment.required_assertive and segment.allowed_evidence_refs
        )
        evidence_ref = target.allowed_evidence_refs[0]

        relations = dict(audit_input.evidence_relations)
        relations[evidence_ref] = "context_only"
        patched_input = replace(audit_input, evidence_relations=relations)

        model_input = copy.deepcopy(audit_input.model_input)
        catalog = cast(list[dict[str, object]], model_input["evidence_catalog"])
        catalog_row = next(row for row in catalog if row.get("evidence_id") == evidence_ref)
        catalog_row["evidence_relation"] = "context_only"

        output = _passing_output(patched_input)
        normalized, removed = _sanitize_supported_evidence_refs(
            output,
            audit_model_input=model_input,
        )

        assert removed >= 1
        audited = validate_assertion_audit_output(normalized, audit_input=patched_input)
        target_assertion = next(
            assertion
            for segment in audited
            if segment.segment_id == target.segment_id
            for assertion in segment.assertions
        )
        assert target_assertion.support_status == "unsupported"
        assert target_assertion.evidence_refs == ()
        assert target_assertion.claim_refs == ()
        assert target_assertion.severity == "critical"
        summary = _summary(audited)
        assert summary["result"] == "fail"
        assert cast(int, summary["critical_unsupported_count"]) >= 1
