from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

_SCHEMA_VERSION = 1
_EXPECTED_PYTHON = (3, 12)
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_DEFAULT_PROVENANCE = Path("artifacts/release/release-0042-provenance.json")


class ReleaseProvenanceError(RuntimeError):
    """Raised when exact release-build provenance cannot be established."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _frontend_root() -> Path:
    return _repository_root() / "frontend"


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseProvenanceError("release_provenance_command_failed")
    return result.stdout.strip()


def _git(*args: str) -> str:
    return _run(["git", *args], cwd=_repository_root())


def _sha256(path: Path) -> str:
    if not path.is_file():
        raise ReleaseProvenanceError("release_input_missing")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_checkout(authorized_head: str) -> str:
    if not _FULL_SHA.fullmatch(authorized_head):
        raise ReleaseProvenanceError("authorized_head_invalid")
    actual_head = _git("rev-parse", "HEAD")
    if actual_head != authorized_head:
        raise ReleaseProvenanceError("authorized_head_mismatch")
    if _git("status", "--porcelain") != "":
        raise ReleaseProvenanceError("release_checkout_dirty")
    return actual_head


def _validate_python_environment() -> dict[str, str]:
    if sys.version_info[:2] != _EXPECTED_PYTHON:
        raise ReleaseProvenanceError("release_python_version_unsupported")

    venv_root = (_backend_root() / ".venv").absolute()
    expected_python = (venv_root / "bin" / "python").absolute()
    actual_python = Path(sys.executable).absolute()
    if actual_python != expected_python or Path(sys.prefix).absolute() != venv_root:
        raise ReleaseProvenanceError("release_python_environment_mismatch")
    if venv_root.is_symlink() or (venv_root / "lib").is_symlink():
        raise ReleaseProvenanceError("release_python_environment_symlinked")
    if not (venv_root / "pyvenv.cfg").is_file() or not (venv_root / "lib").is_dir():
        raise ReleaseProvenanceError("release_python_environment_incomplete")

    return {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
    }


def _pip_freeze_sha256() -> str:
    freeze = _run([sys.executable, "-m", "pip", "freeze", "--all"])
    normalized = "\n".join(
        line.strip()
        for line in freeze.splitlines()
        if line.strip()
    )
    return _text_sha256(normalized + "\n")


def _node_runtime() -> dict[str, str]:
    node = shutil.which("node")
    npm = shutil.which("npm")
    if node is None:
        raise ReleaseProvenanceError("node_unavailable")
    if npm is None:
        raise ReleaseProvenanceError("npm_unavailable")
    return {
        "node_version": _run([node, "--version"]),
        "npm_version": _run([npm, "--version"]),
    }


def collect_release_provenance(*, authorized_head: str) -> dict[str, object]:
    head = _validate_checkout(authorized_head)
    python = _validate_python_environment()

    requirements = _backend_root() / "requirements.txt"
    requirements_dev = _backend_root() / "requirements-dev.txt"
    package_lock = _frontend_root() / "package-lock.json"
    build_id_path = _frontend_root() / ".next" / "BUILD_ID"
    next_binary = _frontend_root() / "node_modules" / ".bin" / "next"

    if next_binary.is_symlink():
        resolved = next_binary.resolve()
        if not resolved.is_file():
            raise ReleaseProvenanceError("frontend_next_binary_invalid")
    elif not next_binary.is_file():
        raise ReleaseProvenanceError("frontend_dependencies_missing")

    if not build_id_path.is_file():
        raise ReleaseProvenanceError("frontend_production_build_missing")

    node = _node_runtime()

    return {
        "schema_version": _SCHEMA_VERSION,
        "git_head": head,
        "python_version": python["version"],
        "python_implementation": python["implementation"],
        "requirements_sha256": _sha256(requirements),
        "requirements_dev_sha256": _sha256(requirements_dev),
        "pip_freeze_sha256": _pip_freeze_sha256(),
        "node_version": node["node_version"],
        "npm_version": node["npm_version"],
        "package_lock_sha256": _sha256(package_lock),
        "next_build_id": build_id_path.read_text(encoding="utf-8").strip(),
    }


def _load_provenance(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ReleaseProvenanceError("release_provenance_missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseProvenanceError("release_provenance_invalid") from exc
    if not isinstance(payload, dict):
        raise ReleaseProvenanceError("release_provenance_invalid")
    return payload


def write_release_provenance(
    *,
    authorized_head: str,
    output: Path = _DEFAULT_PROVENANCE,
) -> dict[str, object]:
    payload = collect_release_provenance(authorized_head=authorized_head)
    target = output if output.is_absolute() else _repository_root() / output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def validate_release_provenance(
    *,
    authorized_head: str,
    provenance_path: Path = _DEFAULT_PROVENANCE,
) -> dict[str, object]:
    target = (
        provenance_path
        if provenance_path.is_absolute()
        else _repository_root() / provenance_path
    )
    recorded = _load_provenance(target)
    actual = collect_release_provenance(authorized_head=authorized_head)

    if recorded.get("schema_version") != _SCHEMA_VERSION:
        raise ReleaseProvenanceError("release_provenance_schema_unsupported")
    if recorded != actual:
        raise ReleaseProvenanceError("release_provenance_mismatch")
    return actual


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create exact local release-build provenance for rev-0042 lifecycle proof"
    )
    parser.add_argument("--authorized-head", required=True)
    parser.add_argument("--output", type=Path, default=_DEFAULT_PROVENANCE)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        payload = write_release_provenance(
            authorized_head=args.authorized_head,
            output=args.output,
        )
    except ReleaseProvenanceError as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "mode": "release_build_provenance_0042",
                    "blocker": exc.code,
                },
                sort_keys=True,
                indent=2,
            )
        )
        raise SystemExit(2) from exc

    print(
        json.dumps(
            {
                "status": "READY",
                "mode": "release_build_provenance_0042",
                "provenance": payload,
            },
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
