from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from scripts import ops_operational_migrate as migrate


def test_authorized_checkout_accepts_exact_clean_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "a" * 40

    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return head
        if args == ("status", "--porcelain"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(migrate, "_run_git", fake_git)

    assert migrate._validate_authorized_checkout(head) == {
        "head": head,
        "clean": True,
    }


@pytest.mark.parametrize(
    ("authorized_head", "actual_head", "status", "code"),
    [
        ("short", "a" * 40, "", "authorized_head_invalid"),
        ("a" * 40, "b" * 40, "", "authorized_head_mismatch"),
        ("a" * 40, "a" * 40, " M tracked.py", "migration_checkout_dirty"),
    ],
)
def test_authorized_checkout_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    authorized_head: str,
    actual_head: str,
    status: str,
    code: str,
) -> None:
    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return actual_head
        if args == ("status", "--porcelain"):
            return status
        raise AssertionError(args)

    monkeypatch.setattr(migrate, "_run_git", fake_git)

    with pytest.raises(migrate.OperationalMigrationError, match=code):
        migrate._validate_authorized_checkout(authorized_head)


def test_runtime_guard_accepts_stopped_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(migrate, "_port_listening", lambda _port: False)
    monkeypatch.setattr(
        migrate.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=""),
    )

    assert migrate._runtime_guard() == {
        "backend_port_8000": "STOPPED",
        "frontend_port_3000": "STOPPED",
        "worker_processes": [],
    }


@pytest.mark.parametrize(
    ("active_port", "stdout", "code"),
    [
        (8000, "", "backend_runtime_active"),
        (3000, "", "frontend_runtime_active"),
        (None, "123 python -m scripts.run_operator_worker\n", "worker_runtime_active"),
        (None, "123 celery -A app worker\n", "worker_runtime_active"),
    ],
)
def test_runtime_guard_blocks_active_application(
    monkeypatch: pytest.MonkeyPatch,
    active_port: int | None,
    stdout: str,
    code: str,
) -> None:
    monkeypatch.setattr(
        migrate,
        "_port_listening",
        lambda port: active_port is not None and port == active_port,
    )
    monkeypatch.setattr(
        migrate.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=stdout),
    )

    with pytest.raises(migrate.OperationalMigrationError, match=code):
        migrate._runtime_guard()


def test_runtime_guard_fails_when_process_state_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(migrate, "_port_listening", lambda _port: False)
    monkeypatch.setattr(
        migrate.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""),
    )

    with pytest.raises(
        migrate.OperationalMigrationError,
        match="runtime_process_state_unavailable",
    ):
        migrate._runtime_guard()


def test_source_upgrade_targets_exact_operational_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> SimpleNamespace:
        captured["command"] = command
        captured["cwd"] = cwd
        captured["database_url"] = env["DATABASE_URL"]
        captured["app_env"] = env["APP_ENV"]
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(migrate.subprocess, "run", fake_run)
    source = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/contentengine"
    )

    migrate._run_source_upgrade(source)

    command = captured["command"]
    assert isinstance(command, list)
    assert command[-2:] == ["upgrade", migrate._EXPECTED_TARGET_REVISION]
    assert captured["app_env"] == "development"
    database_url = str(captured["database_url"])
    assert database_url.endswith("/contentengine")
    assert "restore_test" not in database_url


def test_source_upgrade_rejects_wrong_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal called
        called = True
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(migrate.subprocess, "run", fake_run)
    wrong = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/contentengine_copy"
    )

    with pytest.raises(
        migrate.OperationalMigrationError,
        match="unexpected_operational_database",
    ):
        migrate._run_source_upgrade(wrong)

    assert called is False


def test_source_upgrade_fails_closed_on_alembic_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        migrate.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )
    source = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/contentengine"
    )

    with pytest.raises(
        migrate.OperationalMigrationError,
        match="alembic_upgrade_failed",
    ):
        migrate._run_source_upgrade(source)


def test_operational_migration_contract_is_exact() -> None:
    assert migrate._EXPECTED_SOURCE_DATABASE == "contentengine"
    assert migrate._EXPECTED_SOURCE_REVISION == "20260914_0027"
    assert migrate._EXPECTED_TARGET_REVISION == "20260915_0034"
    assert migrate._EXPECTED_SOURCE_DOCUMENTS == {
        "count": 6,
        "sha256": "865bd5952be18b5ecb14867db335988dfd9f8863683036fb0a911baff3036037",
    }
