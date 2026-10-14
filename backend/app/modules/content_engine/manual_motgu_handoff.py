"""Deterministic Founder-authored article handoff to MOTGU CONTENT02.

This module is deliberately pure: no DB, network, model, publish, or provider calls.
ContentEngine remains the authoring owner; MOTGU OPS remains the release authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, NoReturn

CONTENT02_SCHEMA_VERSION = 1
CONTENT02_TYPE = "journal"
CONTENT02_MAX_BYTES = 512 * 1024
_JS_MAX_SAFE_INTEGER = 9_007_199_254_740_991

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_TEXT_LIMITS = {
    "content_id": 200,
    "seo_title": 300,
    "title": 300,
    "meta_description": 600,
    "body": 200_000,
    "primary_question": 500,
    "fact_check_status": 80,
    "translation_status": 80,
    "publication_status": 80,
}
_ARRAY_LIMITS = {
    "audience_refs": 100,
    "related_artist_ids": 100,
    "related_series_ids": 100,
    "related_artwork_model_ids": 100,
    "related_piece_ids": 100,
    "evidence_refs": 200,
    "must_not_claim": 100,
    "settings_refs": 32,
}
_ENTITY_ARRAY_FIELDS = (
    "related_artist_ids",
    "related_series_ids",
    "related_artwork_model_ids",
    "related_piece_ids",
)
_PACKAGE_INPUT_FIELDS = frozenset(
    {
        "content_id",
        "package_version",
        "locale",
        "slug",
        "title",
        "seo_title",
        "meta_description",
        "body",
        "primary_question",
        *list(_ARRAY_LIMITS),
    }
)


class ManualMotguHandoffError(ValueError):
    """Fail-closed manual handoff error with a stable machine code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ManualMotguHandoff:
    package: dict[str, Any]
    package_json: str
    provenance: dict[str, Any]
    provenance_json: str


def _fail(code: str) -> NoReturn:
    raise ManualMotguHandoffError(code)


def _stable_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        _fail("manual_handoff_json_invalid")


def _utf8(value: str) -> bytes:
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError:
        _fail("manual_handoff_json_invalid")


def _required_text(value: object, key: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        _fail(f"manual_handoff_{key}_invalid")
    return value


def _string_array(source: Mapping[str, object], key: str) -> list[str]:
    value = source.get(key)
    limit = _ARRAY_LIMITS[key]
    if not isinstance(value, list) or len(value) > limit:
        _fail(f"manual_handoff_{key}_invalid")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            _fail(f"manual_handoff_{key}_invalid")
        cleaned = item.strip()
        if not cleaned or len(cleaned) > 300:
            _fail(f"manual_handoff_{key}_invalid")
        if cleaned in seen:
            _fail(f"manual_handoff_{key}_duplicate")
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _package_version(value: object) -> str | int:
    if isinstance(value, bool):
        _fail("manual_handoff_package_version_invalid")
    if isinstance(value, int):
        if value < 1 or value > _JS_MAX_SAFE_INTEGER:
            _fail("manual_handoff_package_version_invalid")
        return value
    if isinstance(value, str) and _VERSION_RE.fullmatch(value):
        return value
    _fail("manual_handoff_package_version_invalid")


def _locale(value: object) -> str:
    if value == "vi-VN" or value == "vi":
        return "vi"
    if value == "en":
        return "en"
    _fail("manual_handoff_locale_invalid")


def _validate_entity_refs(package: Mapping[str, object]) -> None:
    total = 0
    for key in _ENTITY_ARRAY_FIELDS:
        items = package[key]
        if not isinstance(items, list):
            _fail(f"manual_handoff_{key}_invalid")
        total += len(items)
        for value in items:
            if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
                _fail(f"manual_handoff_{key}_invalid")
    if total > 100:
        _fail("manual_handoff_related_entity_refs_too_many")


def build_manual_motgu_handoff(source: Mapping[str, object]) -> ManualMotguHandoff:
    """Build a deterministic MOTGU CONTENT02 package from a HUMAN-authored article."""

    if not isinstance(source, Mapping):
        _fail("manual_handoff_source_invalid")

    keys = set(source)
    unknown = keys - _PACKAGE_INPUT_FIELDS
    missing = _PACKAGE_INPUT_FIELDS - keys
    if unknown:
        _fail("manual_handoff_unknown_field")
    if missing:
        _fail("manual_handoff_required_field_missing")
    content_id = _required_text(source.get("content_id"), "content_id", _TEXT_LIMITS["content_id"])
    if _ID_RE.fullmatch(content_id) is None:
        _fail("manual_handoff_content_id_invalid")

    version = _package_version(source.get("package_version"))
    locale = _locale(source.get("locale"))
    slug = _required_text(source.get("slug"), "slug", 120)
    if _SLUG_RE.fullmatch(slug) is None:
        _fail("manual_handoff_slug_invalid")

    package: dict[str, Any] = {
        "schema_version": CONTENT02_SCHEMA_VERSION,
        "content_id": content_id,
        "package_version": version,
        "type": CONTENT02_TYPE,
        "locale": locale,
        "slug": slug,
        "authoring_provenance": "HUMAN",
        "fact_check_status": "pending",
        "translation_status": "independent",
        "publication_status": "draft",
    }

    for key, limit in _TEXT_LIMITS.items():
        if key in {
            "content_id",
            "fact_check_status",
            "translation_status",
            "publication_status",
        }:
            continue
        package[key] = _required_text(source.get(key), key, limit)

    for key in _ARRAY_LIMITS:
        package[key] = _string_array(source, key)

    _validate_entity_refs(package)

    canonical_without_hash = _stable_json(package)
    package_hash = hashlib.sha256(_utf8(canonical_without_hash)).hexdigest()
    package["package_hash"] = package_hash

    package_json = _stable_json(package) + "\n"
    package_bytes = len(_utf8(package_json))
    if package_bytes > CONTENT02_MAX_BYTES:
        _fail("manual_handoff_package_too_large")

    source_hash = hashlib.sha256(_utf8(_stable_json(dict(source)))).hexdigest()
    provenance = {
        "schema_version": 1,
        "provenance": "HUMAN",
        "content_id": content_id,
        "package_version": str(version),
        "package_hash": package_hash,
        "source_sha256": source_hash,
        "package_bytes": package_bytes,
        "generator": "contentengine.editor-01.manual-motgu-handoff.v1",
    }
    provenance_json = _stable_json(provenance) + "\n"

    return ManualMotguHandoff(
        package=package,
        package_json=package_json,
        provenance=provenance,
        provenance_json=provenance_json,
    )


def write_manual_motgu_handoff(
    handoff: ManualMotguHandoff,
    *,
    package_path: Path,
    provenance_path: Path,
    overwrite: bool = False,
) -> None:
    """Write both handoff files atomically enough for a local explicit operation."""

    package_path = Path(package_path)
    provenance_path = Path(provenance_path)
    if package_path.resolve() == provenance_path.resolve():
        _fail("manual_handoff_output_paths_conflict")
    if not overwrite and (package_path.exists() or provenance_path.exists()):
        _fail("manual_handoff_output_exists")

    package_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.parent.mkdir(parents=True, exist_ok=True)

    package_tmp = package_path.with_name(package_path.name + ".tmp")
    provenance_tmp = provenance_path.with_name(provenance_path.name + ".tmp")
    try:
        package_tmp.write_text(handoff.package_json, encoding="utf-8")
        provenance_tmp.write_text(handoff.provenance_json, encoding="utf-8")
        package_tmp.replace(package_path)
        provenance_tmp.replace(provenance_path)
    finally:
        package_tmp.unlink(missing_ok=True)
        provenance_tmp.unlink(missing_ok=True)


__all__ = [
    "CONTENT02_MAX_BYTES",
    "ManualMotguHandoff",
    "ManualMotguHandoffError",
    "build_manual_motgu_handoff",
    "write_manual_motgu_handoff",
]
