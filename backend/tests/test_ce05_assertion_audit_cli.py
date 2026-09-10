from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_real_o4_assertion_audit_cli_help() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/assert_real_o4_journal_draft.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--revised-draft-artifact-id" in completed.stdout
    assert "--outline-artifact-id" in completed.stdout
    assert "--expected-provider" in completed.stdout
    assert "--expected-model" in completed.stdout
