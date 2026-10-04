from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from scripts import ops_operational_migrate_0044 as migrate


def _manifest(*, dump_sha256: str) -> dict[str, object]:
    return {
        "format_version": 2,
        "source_database": "contentengine",
        "source_host": "localhost",
        "source_port": 5432,
        "source_migration_revision": migrate._SOURCE_REVISION,
        "dump_sha256": dump_sha256,
        "fingerprint": {
            "content_cases": 6,
            "content_runs": 16,
            "approvals": 2,
            "artifacts": 57,
            "content_versions": 2,
            "artifact_hash": "a" * 64,
            "lineage_hash": "b" * 64,
        },
    }


def test_operational_0044_contract_is_exact() -> None:
    assert migrate._EXPECTED_SOURCE_DATABASE == "contentengine"
    assert migrate._SOURCE_REVISION == "20260915_0034"
    assert migrate._TARGET_REVISION == "20260926_0044"
    assert migrate._EXPECTED_UPGRADE_CHAIN == (
        "20260921_0035",
        "20260921_0036",
        "20260921_0037",
        "20260922_0038",
        "20260922_0039",
        "20260922_0040",
        "20260922_0041",
        "20260923_0042",
        "20260925_0043",
        "20260926_0044",
    )


def test_operational_0044_runtime_guard_has_no_process_table_polling() -> None:
    source = inspect.getsource(migrate)
    assert '["ps"' not in source
    assert "pgrep" not in source
    assert "time.sleep" not in source
    assert "asyncio.sleep" not in source


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

    with pytest.raises(migrate.OperationalMigration0044Error, match=code):
        migrate._validate_authorized_checkout(authorized_head)


def test_runtime_guard_accepts_stopped_canonical_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(migrate, "_port_listening", lambda _port: False)

    assert migrate._runtime_guard() == {
        "backend_port_8000": "STOPPED",
        "frontend_port_3000": "STOPPED",
    }


@pytest.mark.parametrize(
    ("active_port", "code"),
    [
        (8000, "backend_runtime_active"),
        (3000, "frontend_runtime_active"),
    ],
)
def test_runtime_guard_blocks_active_canonical_ports(
    monkeypatch: pytest.MonkeyPatch,
    active_port: int,
    code: str,
) -> None:
    monkeypatch.setattr(
        migrate,
        "_port_listening",
        lambda port: port == active_port,
    )

    with pytest.raises(migrate.OperationalMigration0044Error, match=code):
        migrate._runtime_guard()


def test_manifest_binds_explicit_authorized_dump_hash(tmp_path: Path) -> None:
    backup = tmp_path / "snapshot.dump"
    backup.write_bytes(b"fresh-operational-recovery-point")
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    manifest = tmp_path / "snapshot.json"
    manifest.write_text(json.dumps(_manifest(dump_sha256=digest)), encoding="utf-8")

    loaded = migrate._load_authorized_manifest(
        backup,
        manifest,
        expected_dump_sha256=digest,
    )

    assert loaded["dump_sha256"] == digest


def test_manifest_rejects_stale_or_wrong_authorized_dump_hash(tmp_path: Path) -> None:
    backup = tmp_path / "snapshot.dump"
    backup.write_bytes(b"fresh-operational-recovery-point")
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    manifest = tmp_path / "snapshot.json"
    manifest.write_text(json.dumps(_manifest(dump_sha256=digest)), encoding="utf-8")

    with pytest.raises(
        migrate.OperationalMigration0044Error,
        match="authorized_backup_hash_mismatch",
    ):
        migrate._load_authorized_manifest(
            backup,
            manifest,
            expected_dump_sha256="f" * 64,
        )


@pytest.mark.parametrize(
    (
        "documents_count",
        "documents_sha",
        "full_data_sha",
        "code",
    ),
    [
        (-1, "a" * 64, "b" * 64, "expected_source_documents_count_invalid"),
        (6, "bad", "b" * 64, "expected_source_documents_sha256_invalid"),
        (6, "a" * 64, "bad", "expected_source_full_data_sha256_invalid"),
    ],
)
def test_expected_source_fingerprint_arguments_fail_closed(
    documents_count: int,
    documents_sha: str,
    full_data_sha: str,
    code: str,
) -> None:
    with pytest.raises(migrate.OperationalMigration0044Error, match=code):
        migrate._validate_expected_source_fingerprints(
            expected_source_documents_count=documents_count,
            expected_source_documents_sha256=documents_sha,
            expected_source_full_data_sha256=full_data_sha,
        )


@pytest.mark.asyncio
async def test_runtime_work_state_reuses_proven_release_quiescence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
        "jobs": {"failed": 2},
        "paused_operator_retries": [{"run_id": "r1"}],
    }

    async def ready(_engine: object) -> dict[str, object]:
        return expected

    monkeypatch.setattr(
        migrate.release_lifecycle_0042,
        "_assert_release_quiescent_state",
        ready,
    )

    assert await migrate._runtime_work_state(object()) == expected  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_runtime_work_state_maps_release_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def blocked(_engine: object) -> dict[str, object]:
        raise migrate.release_lifecycle_0042.ReleaseLifecycleError(
            "nonterminal_jobs_present"
        )

    monkeypatch.setattr(
        migrate.release_lifecycle_0042,
        "_assert_release_quiescent_state",
        blocked,
    )

    with pytest.raises(
        migrate.OperationalMigration0044Error,
        match="nonterminal_jobs_present",
    ):
        await migrate._runtime_work_state(object())  # type: ignore[arg-type]


def test_source_upgrade_targets_exact_0044_operational_database(
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
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(migrate.subprocess, "run", fake_run)
    source = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/contentengine"
    )

    migrate._run_source_upgrade(source)

    command = captured["command"]
    assert isinstance(command, list)
    assert command[-2:] == ["upgrade", "20260926_0044"]
    assert captured["app_env"] == "development"
    assert str(captured["database_url"]).endswith("/contentengine")


def test_source_upgrade_rejects_non_operational_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal called
        called = True
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(migrate.subprocess, "run", fake_run)
    source = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/contentengine_copy"
    )

    with pytest.raises(
        migrate.OperationalMigration0044Error,
        match="unexpected_operational_database",
    ):
        migrate._run_source_upgrade(source)

    assert called is False


def test_final_document_forces_blocked_status_over_payload() -> None:
    document = migrate._final_document(
        status="BLOCKED",
        payload={
            "status": "READY",
            "mode": "operational_source_migration_0034_0044",
        },
        blocker="source_revision_drift",
        secondary_blockers=["post_migration_source_verification_failed"],
        migration_attempted=True,
    )

    assert document["status"] == "BLOCKED"
    assert document["blocker"] == "source_revision_drift"
    assert document["secondary_blockers"] == [
        "post_migration_source_verification_failed"
    ]
    assert document["migration_attempted"] is True


def test_make_target_requires_full_0044_authorization_binding() -> None:
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(
        encoding="utf-8"
    )
    target = makefile.split("operational-migrate-0044:", maxsplit=1)[1].split(
        "release-build-0042:", maxsplit=1
    )[0]

    assert 'test -n "$(BACKUP)"' in target
    assert 'test -n "$(AUTHORIZED_HEAD)"' in target
    assert 'test -n "$(EXPECTED_DUMP_SHA256)"' in target
    assert 'test -n "$(EXPECTED_SOURCE_DOCUMENTS_COUNT)"' in target
    assert 'test -n "$(EXPECTED_SOURCE_DOCUMENTS_SHA256)"' in target
    assert 'test -n "$(EXPECTED_SOURCE_FULL_DATA_SHA256)"' in target
    assert "scripts.ops_operational_migrate_0044" in target
    assert '--authorized-head "$(AUTHORIZED_HEAD)"' in target
    assert '--expected-dump-sha256 "$(EXPECTED_DUMP_SHA256)"' in target
    assert (
        '--expected-source-documents-count "$(EXPECTED_SOURCE_DOCUMENTS_COUNT)"'
        in target
    )
    assert (
        '--expected-source-documents-sha256 '
        '"$(EXPECTED_SOURCE_DOCUMENTS_SHA256)"'
        in target
    )
    assert (
        '--expected-source-full-data-sha256 '
        '"$(EXPECTED_SOURCE_FULL_DATA_SHA256)"'
        in target
    )