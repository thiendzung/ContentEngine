from __future__ import annotations

from pathlib import Path

import pytest

from scripts import ops_release_lifecycle as lifecycle


def test_final_document_forces_explicit_status() -> None:
    document = lifecycle._final_document(
        status="BLOCKED",
        evidence={"status": "READY", "mode": "controlled_release_lifecycle"},
        blocker="backend_readiness_failed",
        secondary_blockers=["runtime_ports_still_active_after_shutdown"],
    )

    assert document["status"] == "BLOCKED"
    assert document["blocker"] == "backend_readiness_failed"
    assert document["secondary_blockers"] == [
        "runtime_ports_still_active_after_shutdown"
    ]


def test_validate_checkout_requires_exact_clean_head_and_local_venv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    head = "a" * 40
    backend_root = tmp_path / "backend"
    python = backend_root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()

    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return head
        if args == ("status", "--porcelain"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(lifecycle, "_run_git", fake_git)
    monkeypatch.setattr(lifecycle, "_backend_root", lambda: backend_root)
    monkeypatch.setattr(lifecycle.sys, "executable", str(python))

    result = lifecycle._validate_checkout(head)

    assert result["head"] == head
    assert result["clean"] is True
    assert result["python"] == str(python.resolve())


@pytest.mark.parametrize(
    ("head", "actual", "status", "code"),
    [
        ("short", "a" * 40, "", "authorized_head_invalid"),
        ("a" * 40, "b" * 40, "", "authorized_head_mismatch"),
        ("a" * 40, "a" * 40, " M tracked.py", "release_checkout_dirty"),
    ],
)
def test_validate_checkout_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    head: str,
    actual: str,
    status: str,
    code: str,
) -> None:
    backend_root = tmp_path / "backend"
    python = backend_root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()

    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return actual
        if args == ("status", "--porcelain"):
            return status
        raise AssertionError(args)

    monkeypatch.setattr(lifecycle, "_run_git", fake_git)
    monkeypatch.setattr(lifecycle, "_backend_root", lambda: backend_root)
    monkeypatch.setattr(lifecycle.sys, "executable", str(python))

    with pytest.raises(lifecycle.ReleaseLifecycleError, match=code):
        lifecycle._validate_checkout(head)


def test_validate_checkout_rejects_historical_python(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    head = "a" * 40
    backend_root = tmp_path / "backend"
    expected = backend_root / ".venv" / "bin" / "python"
    expected.parent.mkdir(parents=True)
    expected.touch()
    other = tmp_path / "historical" / ".venv" / "bin" / "python"
    other.parent.mkdir(parents=True)
    other.touch()

    monkeypatch.setattr(lifecycle, "_run_git", lambda *args: head if args[0] == "rev-parse" else "")
    monkeypatch.setattr(lifecycle, "_backend_root", lambda: backend_root)
    monkeypatch.setattr(lifecycle.sys, "executable", str(other))

    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="release_python_environment_mismatch",
    ):
        lifecycle._validate_checkout(head)


def test_frontend_build_requires_exact_checkout_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frontend = tmp_path / "frontend"
    build_id = frontend / ".next" / "BUILD_ID"
    next_binary = frontend / "node_modules" / ".bin" / "next"
    build_id.parent.mkdir(parents=True)
    next_binary.parent.mkdir(parents=True)
    build_id.write_text("build-123\n", encoding="utf-8")
    next_binary.touch()

    monkeypatch.setattr(lifecycle, "_frontend_root", lambda: frontend)
    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/usr/bin/npm" if name == "npm" else None)

    assert lifecycle._validate_frontend_build() == {
        "npm": "/usr/bin/npm",
        "build_id": "build-123",
    }


def test_prestart_runtime_guard_accepts_stopped_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lifecycle, "_port_listening", lambda _port: False)
    monkeypatch.setattr(lifecycle, "_process_table", lambda: "")

    result = lifecycle._prestart_runtime_guard()

    assert result["ports"] == {"8000": "STOPPED", "3000": "STOPPED"}
    assert result["process_markers"] == []


@pytest.mark.parametrize(
    ("port", "process_table", "code"),
    [
        (8000, "", "application_runtime_port_active"),
        (3000, "", "application_runtime_port_active"),
        (None, "123 uvicorn app.main:app", "application_runtime_process_active"),
        (None, "123 next start", "application_runtime_process_active"),
        (
            None,
            "123 python -m scripts.run_operator_worker_loop",
            "application_runtime_process_active",
        ),
    ],
)
def test_prestart_runtime_guard_blocks_existing_runtime(
    monkeypatch: pytest.MonkeyPatch,
    port: int | None,
    process_table: str,
    code: str,
) -> None:
    monkeypatch.setattr(
        lifecycle,
        "_port_listening",
        lambda candidate: port is not None and candidate == port,
    )
    monkeypatch.setattr(lifecycle, "_process_table", lambda: process_table)

    with pytest.raises(lifecycle.ReleaseLifecycleError, match=code):
        lifecycle._prestart_runtime_guard()


def test_snapshot_comparison_fails_on_any_durable_delta() -> None:
    baseline = {"core": {"artifacts": 33}}
    changed = {"core": {"artifacts": 34}}

    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="durable_state_changed",
    ):
        lifecycle._require_snapshot_equal(
            baseline,
            changed,
            code="durable_state_changed",
        )


def test_runtime_contract_is_exact() -> None:
    assert lifecycle._EXPECTED_DATABASE == "contentengine"
    assert lifecycle._EXPECTED_REVISION == "20260915_0034"
    assert lifecycle._RUNTIME_PORTS == (8000, 3000)
    assert set(lifecycle._FINGERPRINT_TABLES) == {
        "jobs",
        "step_runs",
        "model_calls",
        "tool_calls",
        "outbox_intents",
    }


def test_listener_evidence_requires_loopback_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        returncode = 0
        stdout = (
            "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
            "Python 123 user 10u IPv4 0x0 0t0 TCP 127.0.0.1:8000 (LISTEN)\n"
        )

    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/usr/sbin/lsof")
    monkeypatch.setattr(lifecycle.subprocess, "run", lambda *args, **kwargs: Result())

    lines = lifecycle._listener_evidence(8000)

    assert lines == [
        "Python 123 user 10u IPv4 0x0 0t0 TCP 127.0.0.1:8000 (LISTEN)"
    ]


def test_listener_evidence_rejects_non_loopback_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        returncode = 0
        stdout = (
            "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
            "Python 123 user 10u IPv4 0x0 0t0 TCP *:8000 (LISTEN)\n"
        )

    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/usr/sbin/lsof")
    monkeypatch.setattr(lifecycle.subprocess, "run", lambda *args, **kwargs: Result())

    with pytest.raises(
        lifecycle.ReleaseLifecycleError,
        match="runtime_listener_not_loopback_only",
    ):
        lifecycle._listener_evidence(8000)


def test_make_target_requires_exact_authorized_head() -> None:
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(
        encoding="utf-8"
    )
    target = makefile.split("release-lifecycle:", maxsplit=1)[1].split(
        "backend-check:", maxsplit=1
    )[0]

    assert 'test -n "$(AUTHORIZED_HEAD)"' in target
    assert "scripts.ops_release_lifecycle" in target
    assert '--authorized-head "$(AUTHORIZED_HEAD)"' in target
    assert "backend-dev" not in target
    assert "frontend-dev" not in target
    assert "operator-worker-loop" not in target
