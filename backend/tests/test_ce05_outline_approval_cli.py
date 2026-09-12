from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_outline_approval_cli_help() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/approve_outline.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    for flag in (
        "--outline-artifact-id",
        "--expected-artifact-version",
        "--expected-artifact-hash",
        "--approved-by",
        "--approval-reason",
    ):
        assert flag in completed.stdout
