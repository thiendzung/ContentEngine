from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.modules.content_engine.manual_motgu_handoff import (
    ManualMotguHandoffError,
    build_manual_motgu_handoff,
    write_manual_motgu_handoff,
)


def _source(**overrides: object) -> dict[str, object]:
    source: dict[str, object] = {
        "content_id": "founder-manual-001",
        "package_version": "1",
        "locale": "vi-VN",
        "slug": "cach-chon-tranh-son-dau",
        "title": "Cách chọn tranh sơn dầu",
        "seo_title": "Cách chọn tranh sơn dầu cho người mới",
        "meta_description": "Hướng dẫn thực tế cho người mới chọn tranh sơn dầu.",
        "body": "Một bài viết hoàn toàn do Founder soạn. Tiếng Việt phải được giữ nguyên.",
        "primary_question": "Người mới nên chọn tranh sơn dầu như thế nào?",
        "audience_refs": ["first-time-art-buyer"],
        "related_artist_ids": [],
        "related_series_ids": [],
        "related_artwork_model_ids": [],
        "related_piece_ids": [],
        "evidence_refs": ["founder-note:001"],
        "must_not_claim": [],
        "settings_refs": [],
        "fact_check_status": "pending",
        "translation_status": "independent",
        "publication_status": "draft",
        "authoring_provenance": "HUMAN",
    }
    source.update(overrides)
    return source


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _error(code: str):
    return pytest.raises(ManualMotguHandoffError, match=f"^{code}$")


def test_manual_handoff_builds_exact_content02_hash_and_preserves_unicode() -> None:
    first = build_manual_motgu_handoff(_source())
    second = build_manual_motgu_handoff(_source())

    assert first.package == second.package
    assert first.package_json == second.package_json
    assert first.provenance_json == second.provenance_json

    assert first.package["schema_version"] == 1
    assert first.package["type"] == "journal"
    assert first.package["locale"] == "vi"
    assert first.package["authoring_provenance"] == "HUMAN"
    assert first.package["body"] == (
        "Một bài viết hoàn toàn do Founder soạn. Tiếng Việt phải được giữ nguyên."
    )
    assert "\\u00" not in first.package_json

    payload = dict(first.package)
    declared = payload.pop("package_hash")
    expected = hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()
    assert declared == expected
    assert first.package_json == _stable_json(first.package) + "\n"

    assert first.provenance["provenance"] == "HUMAN"
    assert first.provenance["package_hash"] == declared
    assert "body" not in first.provenance
    assert first.package["publication_status"] == "draft"


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"authoring_provenance": "AI"}, "manual_handoff_provenance_invalid"),
        ({"authoring_provenance": "human"}, "manual_handoff_provenance_invalid"),
        ({"locale": "fr"}, "manual_handoff_locale_invalid"),
        ({"slug": "Không-Hợp-Lệ"}, "manual_handoff_slug_invalid"),
        ({"package_version": 0}, "manual_handoff_package_version_invalid"),
        ({"package_version": True}, "manual_handoff_package_version_invalid"),
        ({"fact_check_status": "approved"}, "manual_handoff_fact_check_status_unsafe"),
        ({"translation_status": "translated"}, "manual_handoff_translation_status_unsafe"),
        ({"publication_status": "published"}, "manual_handoff_publication_status_unsafe"),
        ({"publication_status": "LIVE"}, "manual_handoff_publication_status_unsafe"),
        ({"body": ""}, "manual_handoff_body_invalid"),
        ({"body": "x" * 200_001}, "manual_handoff_body_invalid"),
        ({"related_artist_ids": ["bad id"]}, "manual_handoff_related_artist_ids_invalid"),
        ({"audience_refs": ["same", "same"]}, "manual_handoff_audience_refs_duplicate"),
        ({"evidence_refs": ["x" * 301]}, "manual_handoff_evidence_refs_invalid"),
        ({"settings_refs": ["   "]}, "manual_handoff_settings_refs_invalid"),
    ],
)
def test_manual_handoff_fails_closed_for_invalid_article_input(
    overrides: dict[str, object],
    code: str,
) -> None:
    with _error(code):
        build_manual_motgu_handoff(_source(**overrides))


def test_manual_handoff_normalizes_content02_array_strings_before_hashing() -> None:
    handoff = build_manual_motgu_handoff(
        _source(
            audience_refs=["  first-time-art-buyer  "],
            evidence_refs=["  founder-note:001  "],
        )
    )
    assert handoff.package["audience_refs"] == ["first-time-art-buyer"]
    assert handoff.package["evidence_refs"] == ["founder-note:001"]

    with _error("manual_handoff_audience_refs_duplicate"):
        build_manual_motgu_handoff(
            _source(audience_refs=["same", " same "])
        )


def test_manual_handoff_rejects_unknown_and_missing_fields() -> None:
    unknown = _source()
    unknown["unexpected"] = "shadow schema"
    with _error("manual_handoff_unknown_field"):
        build_manual_motgu_handoff(unknown)

    missing = _source()
    del missing["primary_question"]
    with _error("manual_handoff_required_field_missing"):
        build_manual_motgu_handoff(missing)


def test_manual_handoff_rejects_more_than_100_total_related_entity_refs() -> None:
    artist_ids = [f"artist-{index:03d}" for index in range(100)]
    with _error("manual_handoff_related_entity_refs_too_many"):
        build_manual_motgu_handoff(
            _source(
                related_artist_ids=artist_ids,
                related_piece_ids=["piece-extra"],
            )
        )


def test_manual_handoff_write_is_fail_closed_and_force_is_explicit(tmp_path: Path) -> None:
    handoff = build_manual_motgu_handoff(_source())
    package_path = tmp_path / "article.content02.json"
    provenance_path = tmp_path / "article.provenance.json"

    write_manual_motgu_handoff(
        handoff,
        package_path=package_path,
        provenance_path=provenance_path,
    )
    assert package_path.read_text(encoding="utf-8") == handoff.package_json
    assert provenance_path.read_text(encoding="utf-8") == handoff.provenance_json

    with _error("manual_handoff_output_exists"):
        write_manual_motgu_handoff(
            handoff,
            package_path=package_path,
            provenance_path=provenance_path,
        )

    package_path.write_text("stale", encoding="utf-8")
    write_manual_motgu_handoff(
        handoff,
        package_path=package_path,
        provenance_path=provenance_path,
        overwrite=True,
    )
    assert package_path.read_text(encoding="utf-8") == handoff.package_json


def test_manual_handoff_rejects_same_package_and_provenance_path(tmp_path: Path) -> None:
    handoff = build_manual_motgu_handoff(_source())
    path = tmp_path / "same.json"
    with _error("manual_handoff_output_paths_conflict"):
        write_manual_motgu_handoff(
            handoff,
            package_path=path,
            provenance_path=path,
        )


def test_manual_handoff_cli_exports_without_body_in_stdout_or_sidecar(tmp_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    provenance_path = tmp_path / "provenance.json"
    input_path.write_text(_stable_json(_source()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/export_manual_motgu_package.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--provenance-output",
            str(provenance_path),
        ],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["ok"] is True
    assert report["provenance"] == "HUMAN"
    assert _source()["body"] not in completed.stdout
    sidecar = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert "body" not in sidecar

    blocked = subprocess.run(
        [
            sys.executable,
            "scripts/export_manual_motgu_package.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--provenance-output",
            str(provenance_path),
        ],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert blocked.returncode == 2
    assert json.loads(blocked.stdout)["error"] == "manual_handoff_output_exists"
