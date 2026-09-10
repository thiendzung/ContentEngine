from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_real_o4_outline_cli_help() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/generate_real_o4_outline.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    for flag in (
        "--run-id",
        "--angle-artifact-id",
        "--angle-artifact-version",
        "--angle-artifact-hash",
        "--selected-angle-id",
        "--candidate-hash",
        "--approval-id",
        "--expected-provider",
        "--expected-model",
    ):
        assert flag in completed.stdout
