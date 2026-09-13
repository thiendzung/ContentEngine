from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.system.recovery import RecoverySafetyError, validate_restore_target
from app.modules.system.test_database import (
    TestDatabasePreparationError as DatabasePreparationError,
)
from app.modules.system.test_database import validate_test_database_target

ROOT = Path(__file__).resolve().parents[2]
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


def test_local_backend_and_postgres_bind_only_to_loopback() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "--host 127.0.0.1" in makefile
    assert "--host 0.0.0.0" not in makefile
    assert '"127.0.0.1:5432:5432"' in compose
    assert '"5432:5432"' not in compose.replace('"127.0.0.1:5432:5432"', "")


def test_make_check_prepares_and_migrates_test_database_before_pytest() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    backend_check = makefile.split("backend-check:", maxsplit=1)[1].split(
        "frontend-check:", maxsplit=1
    )[0]

    assert "$(MAKE) test-db-prepare" in backend_check
    assert "APP_ENV=test .venv/bin/pytest" in backend_check
    assert backend_check.index("$(MAKE) test-db-prepare") < backend_check.index(
        "APP_ENV=test .venv/bin/pytest"
    )
