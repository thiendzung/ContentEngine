from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.system import postgres_tools
from app.modules.system.recovery import RecoverySafetyError, validate_restore_target
from app.modules.system.test_database import (
    TestDatabasePreparationError as DatabasePreparationError,
)
from app.modules.system.test_database import validate_test_database_target
from scripts.ops_backup import BackupSafetyError, _backup_dir

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
OPERATIONAL = "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine"
TEST = "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine_ops01_test"
RESTORE = (
    "postgresql+asyncpg://contentengine:contentengine@localhost:5432/"
    "contentengine_restore_test"
)


def test_test_database_guard_accepts_dedicated_test_target() -> None:
    target = validate_test_database_target(database_url=OPERATIONAL, test_database_url=TEST)
    assert target.database == "contentengine_ops01_test"


def test_test_database_guard_rejects_operational_target() -> None:
    with pytest.raises(
        DatabasePreparationError,
        match="test_database_matches_operational_database",
    ):
        validate_test_database_target(database_url=OPERATIONAL, test_database_url=OPERATIONAL)


def test_test_database_guard_rejects_remote_target() -> None:
    with pytest.raises(DatabasePreparationError, match="test_database_not_loopback"):
        validate_test_database_target(
            database_url=OPERATIONAL,
            test_database_url=(
                "postgresql+asyncpg://contentengine:contentengine@db.example.com:5432/"
                "contentengine_test"
            ),
        )


def test_test_database_guard_rejects_unsafe_identifier() -> None:
    with pytest.raises(DatabasePreparationError, match="unsafe_test_database_name"):
        validate_test_database_target(
            database_url=OPERATIONAL,
            test_database_url=(
                "postgresql+asyncpg://contentengine:contentengine@localhost:5432/"
                'contentengine_test";drop_database'
            ),
        )


def test_restore_guard_accepts_disposable_restore_target() -> None:
    target = validate_restore_target(source_url=OPERATIONAL, restore_url=RESTORE)
    assert target.database == "contentengine_restore_test"


def test_restore_guard_rejects_non_disposable_target() -> None:
    with pytest.raises(RecoverySafetyError, match="unsafe_restore_database_name"):
        validate_restore_target(
            source_url=OPERATIONAL,
            restore_url=(
                "postgresql+asyncpg://contentengine:contentengine@localhost:5432/contentengine_copy"
            ),
        )


def test_restore_guard_rejects_unsafe_identifier() -> None:
    with pytest.raises(RecoverySafetyError, match="unsafe_restore_database_name"):
        validate_restore_target(
            source_url=OPERATIONAL,
            restore_url=(
                "postgresql+asyncpg://contentengine:contentengine@localhost:5432/"
                'contentengine_restore_test";drop_database'
            ),
        )


def test_backup_directory_inside_repository_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONTENTENGINE_BACKUP_DIR", str(ROOT / "tmp" / "backups"))
    with pytest.raises(BackupSafetyError, match="backup_directory_inside_repository"):
        _backup_dir()


def test_postgres_tools_prefer_host_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(postgres_tools.shutil, "which", lambda name: f"/usr/bin/{name}")
    capability = postgres_tools.postgres_tool_capability()
    assert capability is not None
    assert capability.mode == "host"
    assert postgres_tools.postgres_tool_command("pg_dump") == ["pg_dump"]


def test_postgres_tools_fall_back_to_running_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_which(name: str) -> str | None:
        return "/usr/bin/docker" if name == "docker" else None

    monkeypatch.setattr(postgres_tools.shutil, "which", fake_which)
    monkeypatch.setattr(
        postgres_tools.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    capability = postgres_tools.postgres_tool_capability()
    assert capability is not None
    assert capability.mode == "container"
    assert postgres_tools.postgres_tool_command("pg_restore") == [
        "docker",
        "compose",
        "-f",
        str(ROOT / "compose.yaml"),
        "-p",
        "contentengine",
        "exec",
        "-T",
        "postgres",
        "pg_restore",
    ]


def test_operational_cli_modules_import_without_cycle() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import scripts.prepare_test_database; "
                "import scripts.ops_preflight; "
                "import scripts.ops_backup; "
                "import scripts.ops_restore_verify"
            ),
        ],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_local_backend_and_postgres_bind_only_to_loopback() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "COMPOSE_PROJECT_NAME ?= contentengine" in makefile
    assert "docker compose -p $(COMPOSE_PROJECT_NAME) up -d postgres" in makefile
    assert "--host 127.0.0.1" in makefile
    assert "--host 0.0.0.0" not in makefile
    assert '"127.0.0.1:5432:5432"' in compose
    assert '"5432:5432"' not in compose.replace('"127.0.0.1:5432:5432"', "")


def test_make_check_resets_and_migrates_test_database_before_pytest() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    backend_check = makefile.split("backend-check:", maxsplit=1)[1].split(
        "frontend-check:", maxsplit=1
    )[0]

    assert "$(MAKE) test-db-reset" in backend_check
    assert "prepare_test_database --reset" in makefile
    assert "APP_ENV=test .venv/bin/pytest" in backend_check
    assert backend_check.index("$(MAKE) test-db-reset") < backend_check.index(
        "APP_ENV=test .venv/bin/pytest"
    )
