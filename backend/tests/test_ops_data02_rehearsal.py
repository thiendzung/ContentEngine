from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from scripts import ops_data02_rehearsal as data02


def _fingerprint() -> dict[str, object]:
    return {
        "content_cases": 1,
        "content_runs": 2,
        "approvals": 3,
        "artifacts": 4,
        "content_versions": 5,
        "artifact_hash": "a" * 64,
        "lineage_hash": "b" * 64,
    }


def test_data02_upgrade_chain_is_exact_current_chain() -> None:
    chain = data02._upgrade_chain(data02._alembic_script(), data02._SOURCE_REVISION)

    assert chain == data02._EXPECTED_UPGRADE_CHAIN
    assert chain[0] == "20260921_0035"
    assert chain[-1] == data02._TARGET_REVISION
    assert len(chain) == 10


def test_manifest_source_revision_requires_current_operational_revision() -> None:
    source = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/contentengine"
    )
    manifest = {
        "source_database": "contentengine",
        "source_host": "localhost",
        "source_port": 5432,
        "source_migration_revision": data02._SOURCE_REVISION,
    }

    assert data02._manifest_source_revision(manifest, source) == data02._SOURCE_REVISION

    manifest["source_migration_revision"] = "20260923_0042"
    with pytest.raises(
        data02.Data02RehearsalError,
        match="unexpected_source_migration_revision",
    ):
        data02._manifest_source_revision(manifest, source)


def test_manifest_requires_exact_fingerprint_shape() -> None:
    manifest = {"fingerprint": _fingerprint()}
    assert data02._expected_fingerprint(manifest) == _fingerprint()

    invalid = {"fingerprint": {**_fingerprint(), "extra": 1}}
    with pytest.raises(
        data02.Data02RehearsalError,
        match="manifest_fingerprint_shape_invalid",
    ):
        data02._expected_fingerprint(invalid)


def test_load_manifest_verifies_format_and_dump_hash(tmp_path: Path) -> None:
    backup = tmp_path / "fresh.dump"
    backup.write_bytes(b"fresh-data02-backup")
    manifest = tmp_path / "fresh.json"
    manifest.write_text(
        json.dumps(
            {
                "format_version": 2,
                "dump_sha256": data02._sha256(backup),
                "fingerprint": _fingerprint(),
            }
        ),
        encoding="utf-8",
    )

    loaded = data02._load_manifest(backup, manifest)
    assert loaded["dump_sha256"] == data02._sha256(backup)

    backup.write_bytes(b"changed")
    with pytest.raises(data02.Data02RehearsalError, match="backup_hash_mismatch"):
        data02._load_manifest(backup, manifest)


def test_alembic_upgrade_targets_only_disposable_database_and_0044(
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

    monkeypatch.setattr(data02.subprocess, "run", fake_run)
    target = make_url(
        "postgresql+asyncpg://contentengine:secret@localhost:5432/"
        "contentengine_data02_restore_test"
    )

    data02._run_alembic_upgrade(target)

    command = captured["command"]
    assert isinstance(command, list)
    assert command[-2:] == ["upgrade", data02._TARGET_REVISION]
    assert captured["app_env"] == "development"
    database_url = str(captured["database_url"])
    assert "contentengine_data02_restore_test" in database_url
    assert database_url.endswith("/contentengine_data02_restore_test")


def test_data02_script_does_not_replace_historical_o1_contract() -> None:
    historical = (
        Path(__file__).resolve().parents[1] / "scripts" / "ops_migration_rehearsal.py"
    ).read_text(encoding="utf-8")

    assert '_EXPECTED_SOURCE_REVISION = "20260914_0027"' in historical
    assert '_EXPECTED_TARGET_REVISION = "20260915_0034"' in historical
