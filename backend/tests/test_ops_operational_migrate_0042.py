from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from scripts import ops_operational_migrate_0042 as migrate


def _manifest(*, dump_sha256: str) -> dict[str, object]:
    return {
        "format_version": 2,
        "source_database": "contentengine",
        "source_host": "localhost",
        "source_port": 5432,
        "source_migration_revision": migrate._EXPECTED_SOURCE_REVISION,
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


def test_current_migration_contract_is_exact() -> None:
    assert migrate._EXPECTED_SOURCE_DATABASE == "contentengine"
    assert migrate._EXPECTED_SOURCE_REVISION == "20260915_0034"
    assert migrate._EXPECTED_TARGET_REVISION == "20260923_0042"
    assert migrate._EXPECTED_UPGRADE_CHAIN == (
        "20260921_0035",
        "20260921_0036",
        "20260921_0037",
        "20260922_0038",
        "20260922_0039",
        "20260922_0040",
        "20260922_0041",
        "20260923_0042",
    )


def test_required_schema_contract_contains_p2c23_objects() -> None:
    assert "published_contents" in migrate._EXPECTED_TABLES
    assert "publish_events" in migrate._EXPECTED_TABLES
    assert "learning_validations" in migrate._EXPECTED_TABLES
    assert "validate_publish_event_scope" in migrate._EXPECTED_FUNCTIONS
    assert (
        migrate._EXPECTED_TRIGGERS["publish_events_immutable"] == "publish_events"
    )
    assert (
        migrate._EXPECTED_TRIGGERS["learning_validations_guard"]
        == "learning_validations"
    )


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

    with pytest.raises(migrate.CurrentOperationalMigrationError, match=code):
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
        "backend_processes": [],
        "frontend_processes": [],
        "worker_processes": [],
    }


@pytest.mark.parametrize(
    ("active_port", "stdout", "code"),
    [
        (8000, "", "backend_runtime_active"),
        (3000, "", "frontend_runtime_active"),
        (None, "123 uvicorn app.main:app --host 127.0.0.1\n", "backend_runtime_active"),
        (None, "123 next start\n", "frontend_runtime_active"),
        (
            None,
            "123 python -m scripts.run_operator_worker\n",
            "worker_runtime_active",
        ),
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

    with pytest.raises(migrate.CurrentOperationalMigrationError, match=code):
        migrate._runtime_guard()


def test_manifest_binds_authorized_dump_hash(tmp_path: Path) -> None:
    backup = tmp_path / "snapshot.dump"
    backup.write_bytes(b"current-recovery-point")
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    manifest = tmp_path / "snapshot.json"
    manifest.write_text(json.dumps(_manifest(dump_sha256=digest)), encoding="utf-8")

    loaded = migrate._load_manifest(
        backup,
        manifest,
        expected_dump_sha256=digest,
    )

    assert loaded["dump_sha256"] == digest


def test_manifest_rejects_wrong_authorized_dump_hash(tmp_path: Path) -> None:
    backup = tmp_path / "snapshot.dump"
    backup.write_bytes(b"current-recovery-point")
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    manifest = tmp_path / "snapshot.json"
    manifest.write_text(json.dumps(_manifest(dump_sha256=digest)), encoding="utf-8")

    with pytest.raises(
        migrate.CurrentOperationalMigrationError,
        match="authorized_backup_hash_mismatch",
    ):
        migrate._load_manifest(
            backup,
            manifest,
            expected_dump_sha256="f" * 64,
        )


def test_manifest_rejects_wrong_source_revision() -> None:
    manifest = _manifest(dump_sha256="a" * 64)
    manifest["source_migration_revision"] = "20260914_0027"
    source = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/contentengine"
    )

    with pytest.raises(
        migrate.CurrentOperationalMigrationError,
        match="unexpected_source_migration_revision",
    ):
        migrate._manifest_source_revision(manifest, source)


class _Revision:
    def __init__(self, revision: str, down_revision: str | None) -> None:
        self.revision = revision
        self.down_revision = down_revision


class _Script:
    def __init__(self) -> None:
        chain = (
            migrate._EXPECTED_SOURCE_REVISION,
            *migrate._EXPECTED_UPGRADE_CHAIN,
        )
        self._revisions: dict[str, _Revision] = {}
        previous: str | None = None
        for revision in chain:
            self._revisions[revision] = _Revision(revision, previous)
            previous = revision

    def get_current_head(self) -> str:
        return migrate._EXPECTED_TARGET_REVISION

    def get_revision(self, revision: str) -> _Revision | None:
        return self._revisions.get(revision)


def test_upgrade_chain_is_exact() -> None:
    assert migrate._upgrade_chain(
        _Script(),  # type: ignore[arg-type]
        migrate._EXPECTED_SOURCE_REVISION,
    ) == migrate._EXPECTED_UPGRADE_CHAIN


def test_upgrade_chain_rejects_wrong_code_head() -> None:
    script = _Script()
    script.get_current_head = lambda: "wrong"  # type: ignore[method-assign]

    with pytest.raises(
        migrate.CurrentOperationalMigrationError,
        match="unexpected_code_migration_head",
    ):
        migrate._upgrade_chain(
            script,  # type: ignore[arg-type]
            migrate._EXPECTED_SOURCE_REVISION,
        )


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
        migrate.CurrentOperationalMigrationError,
        match="unexpected_operational_database",
    ):
        migrate._run_source_upgrade(wrong)

    assert called is False


def test_require_no_future_schema_blocks_any_existing_object() -> None:
    with pytest.raises(
        migrate.CurrentOperationalMigrationError,
        match="unexpected_future_schema_objects_present",
    ):
        migrate._require_no_future_schema(
            {"tables": ["published_contents"], "functions": [], "triggers": []}
        )


def test_require_expected_schema_accepts_exact_contract() -> None:
    migrate._require_expected_schema(
        {
            "tables": list(migrate._EXPECTED_TABLES),
            "functions": list(migrate._EXPECTED_FUNCTIONS),
            "triggers": [
                f"{table_name}.{trigger_name}"
                for trigger_name, table_name in migrate._EXPECTED_TRIGGERS.items()
            ],
        }
    )


def test_require_expected_schema_rejects_missing_table() -> None:
    with pytest.raises(
        migrate.CurrentOperationalMigrationError,
        match="required_tables_missing",
    ):
        migrate._require_expected_schema(
            {
                "tables": list(migrate._EXPECTED_TABLES[:-1]),
                "functions": list(migrate._EXPECTED_FUNCTIONS),
                "triggers": [
                    f"{table_name}.{trigger_name}"
                    for trigger_name, table_name in migrate._EXPECTED_TRIGGERS.items()
                ],
            }
        )


def test_final_document_forces_blocked_status_over_payload() -> None:
    document = migrate._final_document(
        status="BLOCKED",
        payload={"status": "READY", "mode": "operational_source_migration_0034_0042"},
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


def test_make_target_requires_all_authorization_inputs() -> None:
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(
        encoding="utf-8"
    )
    target = makefile.split("operational-migrate-0042:", maxsplit=1)[1].split(
        "release-lifecycle:", maxsplit=1
    )[0]

    assert 'test -n "$(BACKUP)"' in target
    assert 'test -n "$(AUTHORIZED_HEAD)"' in target
    assert 'test -n "$(EXPECTED_DUMP_SHA256)"' in target
    assert 'test -n "$(EXPECTED_SOURCE_DOCUMENTS_COUNT)"' in target
    assert 'test -n "$(EXPECTED_SOURCE_DOCUMENTS_SHA256)"' in target
    assert "scripts.ops_operational_migrate_0042" in target
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
    assert "make migrate" not in target
