from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import ops_release_provenance_0042 as provenance


def _prepare_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "repo"
    backend = root / "backend"
    frontend = root / "frontend"
    venv = backend / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "lib").mkdir()
    (venv / "pyvenv.cfg").write_text("home = /python\n", encoding="utf-8")
    (venv / "bin" / "python").touch()
    backend.mkdir(parents=True, exist_ok=True)
    (backend / "requirements.txt").write_text("sqlalchemy<2.1\n", encoding="utf-8")
    (backend / "requirements-dev.txt").write_text("-r requirements.txt\n", encoding="utf-8")
    (frontend / "node_modules" / ".bin").mkdir(parents=True)
    (frontend / "node_modules" / ".bin" / "next").touch()
    (frontend / ".next").mkdir(parents=True)
    (frontend / ".next" / "BUILD_ID").write_text("build-0042\n", encoding="utf-8")
    (frontend / "package-lock.json").write_text(
        '{"lockfileVersion": 3}\n',
        encoding="utf-8",
    )
    return root, backend, frontend


def test_validate_checkout_requires_exact_clean_full_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "a" * 40

    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return head
        if args == ("status", "--porcelain"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(provenance, "_git", fake_git)

    assert provenance._validate_checkout(head) == head


@pytest.mark.parametrize(
    ("authorized", "actual", "status", "code"),
    [
        ("short", "a" * 40, "", "authorized_head_invalid"),
        ("a" * 40, "b" * 40, "", "authorized_head_mismatch"),
        ("a" * 40, "a" * 40, " M tracked.py", "release_checkout_dirty"),
    ],
)
def test_validate_checkout_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    authorized: str,
    actual: str,
    status: str,
    code: str,
) -> None:
    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return actual
        if args == ("status", "--porcelain"):
            return status
        raise AssertionError(args)

    monkeypatch.setattr(provenance, "_git", fake_git)

    with pytest.raises(provenance.ReleaseProvenanceError, match=code):
        provenance._validate_checkout(authorized)


def test_collect_release_provenance_binds_exact_build_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, backend, frontend = _prepare_tree(tmp_path)
    head = "c" * 40

    monkeypatch.setattr(provenance, "_repository_root", lambda: root)
    monkeypatch.setattr(provenance, "_backend_root", lambda: backend)
    monkeypatch.setattr(provenance, "_frontend_root", lambda: frontend)
    monkeypatch.setattr(provenance, "_validate_checkout", lambda value: value)
    monkeypatch.setattr(
        provenance,
        "_validate_python_environment",
        lambda: {"version": "3.12.13", "implementation": "CPython"},
    )
    monkeypatch.setattr(provenance, "_pip_freeze_sha256", lambda: "d" * 64)
    monkeypatch.setattr(
        provenance,
        "_node_runtime",
        lambda: {"node_version": "v22.22.3", "npm_version": "10.9.8"},
    )

    result = provenance.collect_release_provenance(authorized_head=head)

    assert result == {
        "schema_version": 1,
        "git_head": head,
        "python_version": "3.12.13",
        "python_implementation": "CPython",
        "requirements_sha256": hashlib.sha256(
            (backend / "requirements.txt").read_bytes()
        ).hexdigest(),
        "requirements_dev_sha256": hashlib.sha256(
            (backend / "requirements-dev.txt").read_bytes()
        ).hexdigest(),
        "pip_freeze_sha256": "d" * 64,
        "node_version": "v22.22.3",
        "npm_version": "10.9.8",
        "package_lock_sha256": hashlib.sha256(
            (frontend / "package-lock.json").read_bytes()
        ).hexdigest(),
        "next_build_id": "build-0042",
    }


def test_validate_release_provenance_accepts_exact_match(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    expected = {
        "schema_version": 1,
        "git_head": "e" * 40,
        "python_version": "3.12.13",
        "python_implementation": "CPython",
        "requirements_sha256": "1" * 64,
        "requirements_dev_sha256": "2" * 64,
        "pip_freeze_sha256": "3" * 64,
        "node_version": "v22.22.3",
        "npm_version": "10.9.8",
        "package_lock_sha256": "4" * 64,
        "next_build_id": "build",
    }
    path = tmp_path / "provenance.json"
    path.write_text(json.dumps(expected), encoding="utf-8")
    monkeypatch.setattr(
        provenance,
        "collect_release_provenance",
        lambda *, authorized_head: expected,
    )

    assert provenance.validate_release_provenance(
        authorized_head="e" * 40,
        provenance_path=path,
    ) == expected


def test_validate_release_provenance_rejects_stale_build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    recorded = {
        "schema_version": 1,
        "git_head": "e" * 40,
        "next_build_id": "old",
    }
    actual = {
        "schema_version": 1,
        "git_head": "e" * 40,
        "next_build_id": "new",
    }
    path = tmp_path / "provenance.json"
    path.write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(
        provenance,
        "collect_release_provenance",
        lambda *, authorized_head: actual,
    )

    with pytest.raises(
        provenance.ReleaseProvenanceError,
        match="release_provenance_mismatch",
    ):
        provenance.validate_release_provenance(
            authorized_head="e" * 40,
            provenance_path=path,
        )


def test_validate_release_provenance_rejects_schema_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    recorded = {"schema_version": 99, "git_head": "f" * 40}
    path = tmp_path / "provenance.json"
    path.write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(
        provenance,
        "collect_release_provenance",
        lambda *, authorized_head: recorded,
    )

    with pytest.raises(
        provenance.ReleaseProvenanceError,
        match="release_provenance_schema_unsupported",
    ):
        provenance.validate_release_provenance(
            authorized_head="f" * 40,
            provenance_path=path,
        )


def test_default_provenance_path_is_ignored_artifact_location() -> None:
    assert provenance._DEFAULT_PROVENANCE == Path(
        "artifacts/release/release-0042-provenance.json"
    )
