from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from scripts import ops_migration_rehearsal as rehearsal


def test_upgrade_chain_is_exact_expected_chain() -> None:
    chain = rehearsal._upgrade_chain(
        rehearsal._alembic_script(),
        rehearsal._EXPECTED_SOURCE_REVISION,
    )

    assert chain == rehearsal._EXPECTED_UPGRADE_CHAIN
    assert chain[-1] == rehearsal._EXPECTED_TARGET_REVISION


def test_upgrade_chain_rejects_wrong_source_revision() -> None:
    with pytest.raises(
        rehearsal.MigrationRehearsalError,
        match="source_revision_not_in_chain|migration_chain_not_linear",
    ):
        rehearsal._upgrade_chain(
            rehearsal._alembic_script(),
            "not-a-real-revision",
        )


def test_manifest_requires_exact_o1_1_dump_hash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "snapshot.dump"
    manifest = tmp_path / "snapshot.json"
    backup.write_bytes(b"snapshot")
    manifest.write_text(
        json.dumps(
            {
                "format_version": 2,
                "dump_sha256": rehearsal._EXPECTED_DUMP_SHA256,
                "fingerprint": {
                    "content_cases": 1,
                    "content_runs": 11,
                    "approvals": 2,
                    "artifacts": 33,
                    "content_versions": 2,
                    "artifact_hash": "a" * 64,
                    "lineage_hash": "b" * 64,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        rehearsal,
        "_sha256",
        lambda _path: rehearsal._EXPECTED_DUMP_SHA256,
    )

    loaded = rehearsal._load_manifest(backup, manifest)

    assert loaded["format_version"] == 2


def test_manifest_rejects_non_v2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "snapshot.dump"
    manifest = tmp_path / "snapshot.json"
    backup.write_bytes(b"snapshot")
    manifest.write_text(
        json.dumps(
            {
                "format_version": 1,
                "dump_sha256": rehearsal._EXPECTED_DUMP_SHA256,
                "fingerprint": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        rehearsal,
        "_sha256",
        lambda _path: rehearsal._EXPECTED_DUMP_SHA256,
    )

    with pytest.raises(
        rehearsal.MigrationRehearsalError,
        match="manifest_format_v2_required",
    ):
        rehearsal._load_manifest(backup, manifest)


def test_manifest_rejects_different_valid_dump(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "snapshot.dump"
    manifest = tmp_path / "snapshot.json"
    backup.write_bytes(b"snapshot")
    other_hash = "c" * 64
    manifest.write_text(
        json.dumps(
            {
                "format_version": 2,
                "dump_sha256": other_hash,
                "fingerprint": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rehearsal, "_sha256", lambda _path: other_hash)

    with pytest.raises(
        rehearsal.MigrationRehearsalError,
        match="unexpected_o1_1_backup_hash",
    ):
        rehearsal._load_manifest(backup, manifest)


def test_manifest_source_contract_requires_exact_o1_source() -> None:
    source = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/contentengine"
    )
    manifest = {
        "format_version": 2,
        "source_database": "contentengine",
        "source_host": "localhost",
        "source_port": 5432,
        "source_migration_revision": rehearsal._EXPECTED_SOURCE_REVISION,
    }

    assert (
        rehearsal._manifest_source_revision(manifest, source)
        == rehearsal._EXPECTED_SOURCE_REVISION
    )


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("source_database", "other", "manifest_source_database_mismatch"),
        ("source_host", "127.0.0.1", "manifest_source_host_mismatch"),
        ("source_port", 55432, "manifest_source_port_mismatch"),
        (
            "source_migration_revision",
            "20260915_0028",
            "unexpected_source_migration_revision",
        ),
    ],
)
def test_manifest_source_contract_rejects_drift(
    field: str,
    value: object,
    code: str,
) -> None:
    source = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/contentengine"
    )
    manifest: dict[str, object] = {
        "format_version": 2,
        "source_database": "contentengine",
        "source_host": "localhost",
        "source_port": 5432,
        "source_migration_revision": rehearsal._EXPECTED_SOURCE_REVISION,
    }
    manifest[field] = value

    with pytest.raises(rehearsal.MigrationRehearsalError, match=code):
        rehearsal._manifest_source_revision(manifest, source)


def test_expected_fingerprint_requires_exact_shape() -> None:
    manifest = {
        "fingerprint": {
            "content_cases": 1,
            "content_runs": 11,
            "approvals": 2,
            "artifacts": 33,
            "content_versions": 2,
            "artifact_hash": "a" * 64,
            "lineage_hash": "b" * 64,
        }
    }

    result = rehearsal._expected_fingerprint(manifest)

    assert set(result) == {
        "content_cases",
        "content_runs",
        "approvals",
        "artifacts",
        "content_versions",
        "artifact_hash",
        "lineage_hash",
    }


def test_expected_fingerprint_rejects_extra_or_missing_fields() -> None:
    manifest = {
        "fingerprint": {
            "content_cases": 1,
            "content_runs": 11,
        }
    }

    with pytest.raises(
        rehearsal.MigrationRehearsalError,
        match="manifest_fingerprint_shape_invalid",
    ):
        rehearsal._expected_fingerprint(manifest)


def test_alembic_upgrade_targets_only_disposable_database(
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

    monkeypatch.setattr(rehearsal.subprocess, "run", fake_run)
    target = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/"
        "contentengine_migration_restore_test"
    )

    rehearsal._run_alembic_upgrade(target)

    command = captured["command"]
    assert isinstance(command, list)
    assert command[-2:] == ["upgrade", rehearsal._EXPECTED_TARGET_REVISION]
    assert captured["app_env"] == "development"
    database_url = str(captured["database_url"])
    assert "contentengine_migration_restore_test" in database_url
    assert database_url.endswith("/contentengine_migration_restore_test")


def test_schema_contract_contains_expected_migration_objects() -> None:
    assert "source_document_observations" in rehearsal._EXPECTED_TABLES
    assert "model_route_decisions" in rehearsal._EXPECTED_TABLES
    assert "validate_source_document_observation" in rehearsal._EXPECTED_FUNCTIONS
    assert rehearsal._EXPECTED_TRIGGERS["routed_model_calls_guard"] == "model_calls"


def test_manifest_blocks_when_backup_hash_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "snapshot.dump"
    manifest = tmp_path / "snapshot.json"
    backup.write_bytes(b"snapshot")
    manifest.write_text(
        json.dumps(
            {
                "format_version": 2,
                "dump_sha256": rehearsal._EXPECTED_DUMP_SHA256,
                "fingerprint": {},
            }
        ),
        encoding="utf-8",
    )

    def unreadable(_path: Path) -> str:
        raise OSError("unreadable")

    monkeypatch.setattr(rehearsal, "_sha256", unreadable)

    with pytest.raises(
        rehearsal.MigrationRehearsalError,
        match="backup_hash_unavailable",
    ):
        rehearsal._load_manifest(backup, manifest)
