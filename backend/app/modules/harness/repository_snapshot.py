"""Materialize an exact Git-tracked repository snapshot for read-only agent work."""

from __future__ import annotations

import asyncio
import io
import os
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path


class RepositorySnapshotError(RuntimeError):
    """Fail-closed repository snapshot error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class RepositorySnapshotSpec:
    repository_root: str
    revision: str


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    root: Path
    revision: str
    tree_hash: str


@dataclass(frozen=True, slots=True)
class _CommandResult:
    stdout: bytes
    stderr: bytes
    exit_code: int


async def _run_git(*argv: str, timeout: float = 30.0) -> _CommandResult:
    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except FileNotFoundError as exc:
        raise RepositorySnapshotError("repository_git_missing") from exc
    except TimeoutError as exc:
        raise RepositorySnapshotError("repository_git_timeout") from exc
    return _CommandResult(stdout=stdout, stderr=stderr, exit_code=process.returncode or 0)


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="replace").strip()


def _validate_member(member: tarfile.TarInfo) -> None:
    path = Path(member.name)
    if path.is_absolute() or ".." in path.parts:
        raise RepositorySnapshotError("repository_archive_path_invalid")
    if member.issym() or member.islnk():
        raise RepositorySnapshotError("repository_archive_link_not_allowed")
    if not (member.isdir() or member.isfile()):
        raise RepositorySnapshotError("repository_archive_member_not_allowed")


def _make_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_file():
            path.chmod(0o444)
        elif path.is_dir():
            path.chmod(0o555)
    root.chmod(0o555)


async def materialize_repository_snapshot(
    spec: RepositorySnapshotSpec,
    *,
    destination: Path,
) -> RepositorySnapshot:
    """Export exactly one commit's tracked files into an immutable worker-visible directory."""

    if not _SHA_RE.fullmatch(spec.revision.strip()):
        raise RepositorySnapshotError("repository_revision_invalid")
    root = Path(spec.repository_root).expanduser().resolve()
    if not root.is_dir():
        raise RepositorySnapshotError("repository_root_invalid")
    if destination.exists():
        raise RepositorySnapshotError("repository_snapshot_destination_exists")

    resolved = await _run_git(
        "-C",
        str(root),
        "rev-parse",
        "--verify",
        f"{spec.revision}^{{commit}}",
    )
    if resolved.exit_code != 0:
        raise RepositorySnapshotError("repository_revision_unresolvable")
    revision = _decode(resolved.stdout)
    if revision != spec.revision:
        raise RepositorySnapshotError("repository_revision_mismatch")

    tree = await _run_git("-C", str(root), "rev-parse", f"{revision}^{{tree}}")
    if tree.exit_code != 0:
        raise RepositorySnapshotError("repository_tree_unresolvable")
    tree_hash = _decode(tree.stdout)
    if not _SHA_RE.fullmatch(tree_hash):
        raise RepositorySnapshotError("repository_tree_invalid")

    archive = await _run_git("-C", str(root), "archive", "--format=tar", revision)
    if archive.exit_code != 0:
        raise RepositorySnapshotError("repository_archive_failed")

    destination.mkdir(parents=True, exist_ok=False)
    try:
        with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as bundle:
            members = bundle.getmembers()
            for member in members:
                _validate_member(member)
            bundle.extractall(destination, members=members, filter="data")
        _make_read_only(destination)
    except RepositorySnapshotError:
        raise
    except (OSError, tarfile.TarError) as exc:
        raise RepositorySnapshotError("repository_snapshot_materialize_failed") from exc

    # Defense-in-depth: the exported view must never inherit write permission.
    if os.access(destination, os.W_OK) and os.geteuid() != 0:
        raise RepositorySnapshotError("repository_snapshot_not_read_only")

    return RepositorySnapshot(root=destination, revision=revision, tree_hash=tree_hash)


__all__ = [
    "RepositorySnapshot",
    "RepositorySnapshotError",
    "RepositorySnapshotSpec",
    "materialize_repository_snapshot",
]
