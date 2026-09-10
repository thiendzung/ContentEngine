from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_real_o4_writer_cli_help() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/generate_real_o4_journal_draft.py", "--help"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    for flag in (
        "--source-run-id",
        "--outline-artifact-id",
        "--outline-artifact-version",
        "--outline-artifact-hash",
        "--locale",
        "--expected-provider",
        "--expected-model",
    ):
        assert flag in completed.stdout
    assert "vi-VN" in completed.stdout
    assert "en" in completed.stdout
