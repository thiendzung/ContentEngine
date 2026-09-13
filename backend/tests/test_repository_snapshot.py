from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from app.modules.harness.repository_snapshot import (
    RepositorySnapshotError,
    RepositorySnapshotSpec,
    materialize_repository_snapshot,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "ContentEngine Test")
    _git(root, "config", "user.email", "test@example.invalid")
    (root / "AGENTS.md").write_text("tracked operating contract\n", encoding="utf-8")
    nested = root / "docs"
    nested.mkdir()
    (nested / "TASK.md").write_text("tracked task\n", encoding="utf-8")
    _git(root, "add", "AGENTS.md", "docs/TASK.md")
    _git(root, "commit", "-m", "fixture")
    revision = _git(root, "rev-parse", "HEAD")
    return root, revision


@pytest.mark.asyncio
async def test_snapshot_contains_only_exact_tracked_revision(tmp_path: Path) -> None:
    root, revision = _repo(tmp_path)
    (root / ".env").write_text("SECRET=must-not-cross\n", encoding="utf-8")
    (root / "private-local.txt").write_text("private\n", encoding="utf-8")
    # A tracked file changed after the pinned commit must not leak into the snapshot either.
    (root / "AGENTS.md").write_text("uncommitted change\n", encoding="utf-8")

    snapshot = await materialize_repository_snapshot(
        RepositorySnapshotSpec(repository_root=str(root), revision=revision),
        destination=tmp_path / "snapshot",
    )

    assert snapshot.revision == revision
    assert len(snapshot.tree_hash) == 40
    assert (snapshot.root / "AGENTS.md").read_text(encoding="utf-8") == (
        "tracked operating contract\n"
    )
    assert (snapshot.root / "docs" / "TASK.md").read_text(encoding="utf-8") == "tracked task\n"
    assert not (snapshot.root / ".env").exists()
    assert not (snapshot.root / "private-local.txt").exists()
    assert not (snapshot.root / ".git").exists()
    assert stat.S_IMODE((snapshot.root / "AGENTS.md").stat().st_mode) == 0o444
    assert stat.S_IMODE((snapshot.root / "docs").stat().st_mode) == 0o555


@pytest.mark.asyncio
async def test_snapshot_fails_closed_for_invalid_or_unresolvable_revision(tmp_path: Path) -> None:
    root, revision = _repo(tmp_path)

    with pytest.raises(RepositorySnapshotError, match="repository_revision_invalid"):
        await materialize_repository_snapshot(
            RepositorySnapshotSpec(repository_root=str(root), revision="main"),
            destination=tmp_path / "invalid",
        )

    missing = "0" * 40
    assert missing != revision
    with pytest.raises(RepositorySnapshotError, match="repository_revision_unresolvable"):
        await materialize_repository_snapshot(
            RepositorySnapshotSpec(repository_root=str(root), revision=missing),
            destination=tmp_path / "missing",
        )


@pytest.mark.asyncio
async def test_snapshot_does_not_mutate_live_repository(tmp_path: Path) -> None:
    root, revision = _repo(tmp_path)
    before = _git(root, "status", "--porcelain")

    snapshot = await materialize_repository_snapshot(
        RepositorySnapshotSpec(repository_root=str(root), revision=revision),
        destination=tmp_path / "snapshot",
    )

    assert _git(root, "status", "--porcelain") == before
    assert not os.access(snapshot.root / "AGENTS.md", os.W_OK)
