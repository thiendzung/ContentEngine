from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import ops_inspect


def test_database_identity_is_sanitized_and_local() -> None:
    identity = ops_inspect._database_identity(
        "postgresql+asyncpg://contentengine:super-secret@localhost:5432/contentengine"
    )

    assert identity == {
        "backend": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "contentengine",
    }


@pytest.mark.parametrize(
    ("database_url", "code"),
    [
        (
            "postgresql+asyncpg://contentengine:x@db.example.com:5432/contentengine",
            "operational_database_not_loopback",
        ),
        (
            "postgresql+asyncpg://contentengine:x@localhost:5432/contentengine_test",
            "operational_database_looks_disposable",
        ),
        (
            "postgresql+asyncpg://contentengine:x@localhost:5432/contentengine_restore_test",
            "operational_database_looks_disposable",
        ),
    ],
)
def test_database_identity_rejects_unsafe_operational_targets(
    database_url: str,
    code: str,
) -> None:
    with pytest.raises(ops_inspect.OperationalInspectionError, match=code):
        ops_inspect._database_identity(database_url)


def test_operational_repository_root_accepts_explicit_existing_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CONTENTENGINE_OPERATIONAL_REPO", str(tmp_path))

    assert ops_inspect._operational_repository_root() == tmp_path.resolve()


@pytest.mark.asyncio
async def test_operational_inspection_ready_when_identity_and_schema_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        app_env="development",
        app_version="0.1.0-ce05",
        database_url="postgresql+asyncpg://contentengine:x@localhost:5432/contentengine",
    )
    inspection_root = ops_inspect._repository_root()
    operational_root = inspection_root.parent / "operational"
    monkeypatch.setattr(ops_inspect, "get_settings", lambda: settings)
    monkeypatch.setattr(
        ops_inspect,
        "_operational_repository_root",
        lambda: operational_root,
    )

    def fake_repo_state(root: Path) -> dict[str, object]:
        if root == inspection_root:
            return {"head": "a" * 40, "clean": True}
        return {"head": "b" * 40, "clean": True}

    monkeypatch.setattr(ops_inspect, "_repository_state", fake_repo_state)
    monkeypatch.setattr(ops_inspect, "_expected_migration_head", lambda: "20260915_0034")

    async def fake_snapshot(_database_url: str) -> dict[str, object]:
        return {
            "current_database": "contentengine",
            "current_user": "contentengine",
            "server_address": "127.0.0.1",
            "server_port": 5432,
            "server_version": "17.0",
            "migration_revision": "20260915_0034",
            "fingerprint": {"content_cases": 1},
        }

    monkeypatch.setattr(ops_inspect, "_database_snapshot", fake_snapshot)

    result = await ops_inspect.build_operational_inspection()

    assert result["status"] == "READY"
    assert result["mode"] == "read_only"
    assert result["blockers"] == []
    assert result["inspection_repository"] == {"head": "a" * 40, "clean": True}
    assert result["operational_repository"] == {"head": "b" * 40, "clean": True}
    assert result["operational_repository_matches_inspection"] is False
    assert result["configured_database"] == {
        "backend": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "contentengine",
    }


@pytest.mark.asyncio
async def test_operational_inspection_blocks_dirty_operational_repo_or_schema_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        app_env="development",
        app_version="0.1.0-ce05",
        database_url="postgresql+asyncpg://contentengine:x@localhost:5432/contentengine",
    )
    inspection_root = ops_inspect._repository_root()
    operational_root = inspection_root.parent / "operational"
    monkeypatch.setattr(ops_inspect, "get_settings", lambda: settings)
    monkeypatch.setattr(
        ops_inspect,
        "_operational_repository_root",
        lambda: operational_root,
    )

    def fake_repo_state(root: Path) -> dict[str, object]:
        if root == inspection_root:
            return {"head": "a" * 40, "clean": True}
        return {"head": "b" * 40, "clean": False}

    monkeypatch.setattr(ops_inspect, "_repository_state", fake_repo_state)
    monkeypatch.setattr(ops_inspect, "_expected_migration_head", lambda: "20260915_0034")

    async def fake_snapshot(_database_url: str) -> dict[str, object]:
        return {
            "current_database": "contentengine",
            "current_user": "contentengine",
            "server_address": "127.0.0.1",
            "server_port": 5432,
            "server_version": "17.0",
            "migration_revision": "20260915_0033",
            "fingerprint": {"content_cases": 1},
        }

    monkeypatch.setattr(ops_inspect, "_database_snapshot", fake_snapshot)

    result = await ops_inspect.build_operational_inspection()

    assert result["status"] == "BLOCKED"
    assert result["blockers"] == [
        "operational_repository_worktree_dirty",
        "migration_revision_mismatch",
    ]


@pytest.mark.asyncio
async def test_operational_inspection_rejects_test_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        app_env="test",
        app_version="0.1.0-ce05",
        database_url="postgresql+asyncpg://contentengine:x@localhost:5432/contentengine",
    )
    monkeypatch.setattr(ops_inspect, "get_settings", lambda: settings)

    with pytest.raises(
        ops_inspect.OperationalInspectionError,
        match="test_environment_not_operational",
    ):
        await ops_inspect.build_operational_inspection()
