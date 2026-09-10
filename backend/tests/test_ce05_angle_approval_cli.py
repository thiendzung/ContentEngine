from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from app.modules.content_engine.journal.angle import AngleCandidate, angle_candidate_hash
from app.modules.harness.models import Artifact
from scripts.approve_angle_candidate import _candidate_hash_from_artifact


def test_angle_approval_cli_help() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/approve_angle_candidate.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    for flag in (
        "--angle-artifact-id",
        "--expected-artifact-version",
        "--expected-artifact-hash",
        "--selected-angle-id",
        "--approved-by",
        "--approval-reason",
    ):
        assert flag in completed.stdout


def test_cli_candidate_hash_matches_angle_contract() -> None:
    candidate = AngleCandidate(
        angle_id="angle-01",
        working_title="A First-Time Buyer’s Checklist for Understanding an Artwork’s Price",
        reader_problem="A first-time buyer cannot interpret an artwork price.",
        central_question="How should a first-time buyer understand an artwork price?",
        core_promise="Give the reader grounded questions to use before deciding.",
        point_of_view="Treat price as context, not a quality score.",
        why_now="The reader is evaluating a real purchase.",
        evidence_refs=(str(uuid4()),),
        originality_refs=("docs/example.md#ORIG-01",),
        excluded_claims=("No universal pricing formula.",),
        risks=("Do not imply price equals quality.",),
        confidence=0.91,
        locale="en",
    )
    artifact = Artifact(
        run_id=uuid4(),
        artifact_type="angle_candidates",
        locale="en",
        version=1,
        content_json={"candidates": [candidate.to_dict()]},
        content_hash="0" * 64,
    )

    assert _candidate_hash_from_artifact(artifact, "angle-01") == angle_candidate_hash(candidate)
