from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from app.modules.research.discovery.artifact import load_discovery_selection_snapshot
from app.modules.research.keyword_plan.contracts import (
    ContentDecision,
    HypothesisStatus,
    OpportunityPriority,
)


def _artifact_payload() -> tuple[dict[str, object], str]:
    opportunity_id = "opp_price_test"
    hypothesis_id = "need_price_test"
    payload: dict[str, object] = {
        "schema_version": 1,
        "artifact_type": "discovery_research_report",
        "evidence_eligible": False,
        "planning_refs": {
            "need_hypothesis_id": str(uuid4()),
            "signal_ids": {},
            "opportunity_ids": {opportunity_id: str(uuid4())},
        },
        "opportunity_map": {
            "project_id": "motgu",
            "locale": "en",
            "seed": "first-time art buyer understanding artwork price",
            "version": 1,
            "need_hypothesis": {
                "id": hypothesis_id,
                "statement": "Understand whether an original artwork price makes sense.",
                "audience_scope": "international first-time art buyer",
                "situation": "considering an original artwork",
                "need_type": "question",
                "origin": "founder_proposed",
                "status": "PROPOSED",
                "support_signal_refs": [],
                "contradict_signal_refs": [],
                "alternative_explanations": ["General curiosity may explain demand."],
                "missing_evidence": ["Direct MOTGU observation is still missing."],
                "version": 1,
            },
            "opportunities": [
                {
                    "id": opportunity_id,
                    "need_hypothesis_id": hypothesis_id,
                    "locale": "en",
                    "reader": "international first-time art buyer",
                    "situation": "considering an original artwork",
                    "need": "Understand whether an original artwork price makes sense.",
                    "question": "How much should I spend on my first painting?",
                    "intent": "evaluate",
                    "promise": "Help the reader evaluate the displayed artwork price.",
                    "topic_key": "price",
                    "signal_refs": [],
                    "motgu_material_refs": [],
                    "material_gaps": ["Approved MOTGU material is still required."],
                    "existing_content_refs": [],
                    "what_is_actually_new": "Keep as a research candidate until MOTGU material is attached.",
                    "next_discovery_step": "Relevant Artwork / Artist",
                    "decision": "CREATE",
                    "priority": "LATER",
                    "reasons": ["single_search_signal_only"],
                    "suggested_content_type": "journal",
                    "suggested_role": "cluster",
                    "version": 1,
                    "selected_by": None,
                    "selected_at": None,
                    "selection_reason": None,
                }
            ],
        },
    }
    return payload, opportunity_id


def test_load_discovery_selection_snapshot_reads_only_persisted_plan(tmp_path: Path) -> None:
    payload, opportunity_id = _artifact_payload()
    artifact = tmp_path / "discovery.json"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    result, refs = load_discovery_selection_snapshot(
        artifact,
        opportunity_id=opportunity_id,
    )

    assert result.need_hypothesis.status is HypothesisStatus.PROPOSED
    assert result.opportunities[0].id == opportunity_id
    assert result.opportunities[0].decision is ContentDecision.CREATE
    assert result.opportunities[0].priority is OpportunityPriority.LATER
    assert refs.opportunity_ids[opportunity_id]


def test_load_discovery_selection_snapshot_rejects_wrong_schema(tmp_path: Path) -> None:
    payload, opportunity_id = _artifact_payload()
    payload["schema_version"] = 2
    artifact = tmp_path / "discovery.json"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported_discovery_artifact_schema_version"):
        load_discovery_selection_snapshot(
            artifact,
            opportunity_id=opportunity_id,
        )


def test_discovery_selection_runner_help_works_without_pythonpath() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/select_discovery_opportunity.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Persist one explicit human selection" in completed.stdout
