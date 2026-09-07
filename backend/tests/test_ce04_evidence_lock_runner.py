from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_evidence_set_lock_runner_help_works_without_pythonpath() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/lock_evidence_set.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "without provider calls" in completed.stdout
