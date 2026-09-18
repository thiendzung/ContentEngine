from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _validate_refs(base: str, head: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "make",
            "-C",
            str(REPO_ROOT),
            "ocr-validate-refs",
            f"OCR_BASE={base}",
            f"OCR_HEAD={head}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_ocr_ref_validation_accepts_exact_full_commit_sha() -> None:
    sha = _git_head()

    result = _validate_refs(sha, sha)

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "ref_factory",
    [
        lambda _sha: "main",
        lambda _sha: "v1.0.0",
        lambda _sha: "HEAD",
        lambda _sha: "HEAD~0",
        lambda sha: sha[:12],
    ],
)
def test_ocr_ref_validation_rejects_non_exact_refs(
    ref_factory: Callable[[str], str],
) -> None:
    sha = _git_head()
    ref = ref_factory(sha)

    result = _validate_refs(ref, sha)

    assert result.returncode != 0
    assert "exact full 40-character lowercase commit SHA" in result.stdout + result.stderr
