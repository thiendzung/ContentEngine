"""Exact publication identity guard and immutable Rank Math inspection capture."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import ContentItem, ContentVersion
from app.modules.harness.models import Artifact, ContentRun
from app.modules.publishing.models import PublishedContent, PublishEvent
from app.modules.publishing.rank_math_gateway import RankMathInspection
from app.modules.publishing.service import PUBLISH_PACKAGE_ARTIFACT_TYPE

RANK_MATH_CAPTURE_SCHEMA_VERSION = 1

_CAPABILITY_ARTIFACT_TYPES = {
    "rank-math/get-post-seo-meta": "rank_math_seo_meta",
    "rank-math/get-post-schema": "rank_math_schema",
    "rank-math/get-post-links": "rank_math_links",
}

_SECRET_KEYS = {
    "access_token",
    "refresh_token",
    "auth_token",
    "id_token",
    "api_key",
    "apikey",
    "client_secret",
    "private_key",
    "secret",
    "password",
    "authorization",
    "cookie",
    "credential",
    "credentials",
}


class RankMathCaptureError(ValueError):
    """Stable fail-closed P2C2.3 capture error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RankMathCaptureResult:
    artifact: Artifact
    publish_event: PublishEvent
    replayed: bool


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RankMathCaptureError(code)
    return value.strip()


def _sensitive_key(key: str) -> bool:
    return key.strip().lower().replace("-", "_") in _SECRET_KEYS


def _safe_json(value: object, *, depth: int = 0) -> object:
    if depth > 12:
        raise RankMathCaptureError("rank_math_capture_safe_data_invalid")
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RankMathCaptureError("rank_math_capture_safe_data_invalid")
        return value
    if isinstance(value, list):
        return [_safe_json(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or _sensitive_key(key):
                raise RankMathCaptureError("rank_math_capture_safe_data_invalid")
            result[key] = _safe_json(item, depth=depth + 1)
        return result
    raise RankMathCaptureError("rank_math_capture_safe_data_invalid")


def _package_identity(package: Artifact) -> dict[str, object]:
    if (
        package.artifact_type != PUBLISH_PACKAGE_ARTIFACT_TYPE
        or not isinstance(package.content_json, dict)
        or package.content_hash != _hash(package.content_json)
    ):
        raise RankMathCaptureError("rank_math_capture_publish_package_invalid")
    identity = package.content_json.get("identity")
    if not isinstance(identity, dict):
        raise RankMathCaptureError("rank_math_capture_publish_package_invalid")
    return cast(dict[str, object], identity)


async def _current_binding(
    session: AsyncSession,
    *,
    published_content_id: UUID,
    content_version_id: UUID,
) -> tuple[
    PublishedContent,
    ContentVersion,
    ContentItem,
    PublishEvent,
    Artifact,
    ContentRun,
]:
    mapping = await session.scalar(
        select(PublishedContent)
        .where(PublishedContent.id == published_content_id)
        .with_for_update()
    )
    version = await session.get(ContentVersion, content_version_id)
    if mapping is None or version is None:
        raise RankMathCaptureError("rank_math_capture_identity_missing")
    if mapping.target != "wordpress":
        raise RankMathCaptureError("rank_math_capture_target_invalid")
    if mapping.current_content_version_id != version.id:
        raise RankMathCaptureError("rank_math_capture_current_version_required")

    item = await session.get(ContentItem, mapping.content_item_id)
    if (
        item is None
        or version.content_item_id != item.id
        or item.project_id != mapping.project_id
    ):
        raise RankMathCaptureError("rank_math_capture_identity_mismatch")

    event = await session.scalar(
        select(PublishEvent)
        .where(
            PublishEvent.published_content_id == mapping.id,
            PublishEvent.content_version_id == version.id,
        )
        .order_by(PublishEvent.created_at.desc(), PublishEvent.id.desc())
        .limit(1)
    )
    if (
        event is None
        or event.canonical_url != mapping.canonical_url
        or event.external_status != mapping.external_status
        or event.external_revision_id != mapping.external_revision_id
        or event.published_at != mapping.published_at
        or event.result_json.get("external_id") != mapping.external_id
    ):
        raise RankMathCaptureError("rank_math_capture_publish_event_mismatch")

    package = await session.get(Artifact, event.publish_package_artifact_id)
    if package is None:
        raise RankMathCaptureError("rank_math_capture_publish_package_missing")
    identity = _package_identity(package)
    run = await session.get(ContentRun, package.run_id)
    if (
        run is None
        or run.run_mode != "publish"
        or run.project_id != mapping.project_id
        or run.content_case_id != item.content_case_id
        or run.locale_variant_id != item.locale_variant_id
        or run.content_item_id != item.id
    ):
        raise RankMathCaptureError("rank_math_capture_publish_lineage_mismatch")

    expected_identity = {
        "project_id": str(mapping.project_id),
        "content_case_id": str(item.content_case_id),
        "locale_variant_id": str(item.locale_variant_id),
        "content_item_id": str(item.id),
        "content_version_id": str(version.id),
        "content_experiment_id": str(event.content_experiment_id),
    }
    for key, expected in expected_identity.items():
        if identity.get(key) != expected:
            raise RankMathCaptureError("rank_math_capture_publish_lineage_mismatch")

    return mapping, version, item, event, package, run


def _wordpress_post_id(mapping: PublishedContent) -> int:
    if not mapping.external_id.isdigit() or mapping.external_id.startswith("0"):
        raise RankMathCaptureError("rank_math_capture_post_id_invalid")
    post_id = int(mapping.external_id)
    if post_id <= 0:
        raise RankMathCaptureError("rank_math_capture_post_id_invalid")
    return post_id


def _validated_inspection(
    *,
    mapping: PublishedContent,
    inspection: RankMathInspection,
) -> tuple[str, dict[str, object]]:
    artifact_type = _CAPABILITY_ARTIFACT_TYPES.get(inspection.capability)
    if artifact_type is None:
        raise RankMathCaptureError("rank_math_capture_capability_invalid")
    if (
        inspection.payload_schema_version != "1"
        or inspection.source != "rank_math"
        or inspection.upstream_source != "rank_math_native"
    ):
        raise RankMathCaptureError("rank_math_capture_provenance_mismatch")
    if inspection.wordpress_post_id != mapping.external_id:
        raise RankMathCaptureError("rank_math_capture_post_id_mismatch")
    if inspection.wordpress_url != mapping.canonical_url:
        raise RankMathCaptureError("rank_math_capture_canonical_drift")
    if inspection.wordpress_status != mapping.external_status:
        raise RankMathCaptureError("rank_math_capture_status_drift")
    if (
        mapping.external_revision_id is not None
        and inspection.wordpress_modified_gmt != mapping.external_revision_id
    ):
        raise RankMathCaptureError("rank_math_capture_revision_drift")
    if inspection.captured_at.tzinfo is None or inspection.captured_at.utcoffset() is None:
        raise RankMathCaptureError("rank_math_capture_timestamp_invalid")
    if not inspection.rank_math_free_version.strip():
        raise RankMathCaptureError("rank_math_capture_rank_math_version_missing")
    if inspection.safe_data.get("post_id") != _wordpress_post_id(mapping):
        raise RankMathCaptureError("rank_math_capture_safe_data_identity_mismatch")

    safe_data = _safe_json(inspection.safe_data)
    if not isinstance(safe_data, dict):
        raise RankMathCaptureError("rank_math_capture_safe_data_invalid")
    return artifact_type, cast(dict[str, object], safe_data)


def _snapshot_basis(
    *,
    mapping: PublishedContent,
    version: ContentVersion,
    item: ContentItem,
    event: PublishEvent,
    package: Artifact,
    inspection: RankMathInspection,
    safe_data: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": RANK_MATH_CAPTURE_SCHEMA_VERSION,
        "source": "rank_math",
        "upstream_source": "rank_math_native",
        "identity": {
            "project_id": str(mapping.project_id),
            "published_content_id": str(mapping.id),
            "content_item_id": str(item.id),
            "content_version_id": str(version.id),
            "publish_event_id": str(event.id),
            "publish_package_artifact_id": str(package.id),
            "wordpress_post_id": mapping.external_id,
            "canonical_url": mapping.canonical_url,
            "external_revision_id": mapping.external_revision_id,
            "external_status": mapping.external_status,
        },
        "inspection": {
            "payload_schema_version": inspection.payload_schema_version,
            "capability": inspection.capability,
            "wordpress_modified_gmt": inspection.wordpress_modified_gmt,
            "rank_math_free_version": inspection.rank_math_free_version,
            "rank_math_pro_version": inspection.rank_math_pro_version,
            "safe_data": safe_data,
        },
    }


def _capture_payload(
    *,
    basis: dict[str, object],
    snapshot_fingerprint: str,
    inspection: RankMathInspection,
) -> dict[str, object]:
    payload = json.loads(json.dumps(basis, ensure_ascii=False))
    payload["artifact_type"] = "rank_math_inspection"
    payload["snapshot_fingerprint"] = snapshot_fingerprint
    payload["captured_at"] = inspection.captured_at.astimezone(UTC).isoformat()
    return cast(dict[str, object], payload)


def _artifact_matches_identity(
    artifact: Artifact,
    *,
    published_content_id: UUID,
    content_version_id: UUID,
    capability: str,
) -> bool:
    if not isinstance(artifact.content_json, dict):
        return False
    payload = artifact.content_json
    identity = payload.get("identity")
    inspection = payload.get("inspection")
    return (
        isinstance(identity, dict)
        and isinstance(inspection, dict)
        and identity.get("published_content_id") == str(published_content_id)
        and identity.get("content_version_id") == str(content_version_id)
        and inspection.get("capability") == capability
    )


def _validate_stored_artifact(artifact: Artifact) -> dict[str, object]:
    if (
        not isinstance(artifact.content_json, dict)
        or artifact.content_hash != _hash(artifact.content_json)
    ):
        raise RankMathCaptureError("rank_math_capture_artifact_history_invalid")
    payload = artifact.content_json
    if (
        payload.get("schema_version") != RANK_MATH_CAPTURE_SCHEMA_VERSION
        or payload.get("artifact_type") != "rank_math_inspection"
        or not isinstance(payload.get("snapshot_fingerprint"), str)
    ):
        raise RankMathCaptureError("rank_math_capture_artifact_history_invalid")
    return payload


async def capture_rank_math_inspection(
    session: AsyncSession,
    *,
    published_content_id: UUID,
    content_version_id: UUID,
    inspection: RankMathInspection,
) -> RankMathCaptureResult:
    """Persist one validated current Rank Math snapshot as an immutable Artifact."""

    mapping, version, item, event, package, run = await _current_binding(
        session,
        published_content_id=published_content_id,
        content_version_id=content_version_id,
    )
    artifact_type, safe_data = _validated_inspection(
        mapping=mapping,
        inspection=inspection,
    )
    basis = _snapshot_basis(
        mapping=mapping,
        version=version,
        item=item,
        event=event,
        package=package,
        inspection=inspection,
        safe_data=safe_data,
    )
    snapshot_fingerprint = _hash(basis)

    existing = list(
        (
            await session.scalars(
                select(Artifact)
                .where(
                    Artifact.run_id == run.id,
                    Artifact.artifact_type == artifact_type,
                )
                .order_by(Artifact.version.asc(), Artifact.id.asc())
            )
        ).all()
    )
    max_version = 0
    for artifact in existing:
        payload = _validate_stored_artifact(artifact)
        max_version = max(max_version, artifact.version)
        if payload.get("snapshot_fingerprint") == snapshot_fingerprint:
            if not _artifact_matches_identity(
                artifact,
                published_content_id=mapping.id,
                content_version_id=version.id,
                capability=inspection.capability,
            ):
                raise RankMathCaptureError("rank_math_capture_artifact_replay_conflict")
            return RankMathCaptureResult(
                artifact=artifact,
                publish_event=event,
                replayed=True,
            )

    payload = _capture_payload(
        basis=basis,
        snapshot_fingerprint=snapshot_fingerprint,
        inspection=inspection,
    )
    artifact = Artifact(
        run_id=run.id,
        step_run_id=None,
        artifact_type=artifact_type,
        locale=package.locale,
        version=max_version + 1,
        content_json=payload,
        content_hash=_hash(payload),
    )
    session.add(artifact)
    await session.flush()
    return RankMathCaptureResult(
        artifact=artifact,
        publish_event=event,
        replayed=False,
    )


async def get_captured_rank_math_inspection(
    session: AsyncSession,
    *,
    published_content_id: UUID,
    content_version_id: UUID,
    capability: str,
) -> Artifact:
    """Return the latest exact captured snapshot; never synthesize historical state."""

    artifact_type = _CAPABILITY_ARTIFACT_TYPES.get(capability)
    if artifact_type is None:
        raise RankMathCaptureError("rank_math_capture_capability_invalid")

    mapping = await session.get(PublishedContent, published_content_id)
    version = await session.get(ContentVersion, content_version_id)
    if (
        mapping is None
        or version is None
        or mapping.target != "wordpress"
        or version.content_item_id != mapping.content_item_id
    ):
        raise RankMathCaptureError("rank_math_capture_identity_mismatch")

    package_run_ids = list(
        (
            await session.scalars(
                select(Artifact.run_id)
                .join(
                    PublishEvent,
                    PublishEvent.publish_package_artifact_id == Artifact.id,
                )
                .where(
                    PublishEvent.published_content_id == mapping.id,
                    PublishEvent.content_version_id == version.id,
                    Artifact.artifact_type == PUBLISH_PACKAGE_ARTIFACT_TYPE,
                )
                .distinct()
            )
        ).all()
    )
    if package_run_ids:
        artifacts = list(
            (
                await session.scalars(
                    select(Artifact)
                    .where(
                        Artifact.run_id.in_(package_run_ids),
                        Artifact.artifact_type == artifact_type,
                    )
                    .order_by(
                        Artifact.created_at.desc(),
                        Artifact.version.desc(),
                        Artifact.id.desc(),
                    )
                )
            ).all()
        )
        for artifact in artifacts:
            _validate_stored_artifact(artifact)
            if _artifact_matches_identity(
                artifact,
                published_content_id=mapping.id,
                content_version_id=version.id,
                capability=capability,
            ):
                return artifact

    if mapping.current_content_version_id != version.id:
        raise RankMathCaptureError("rank_math_capture_historical_snapshot_missing")
    raise RankMathCaptureError("rank_math_capture_snapshot_missing")


__all__ = [
    "RANK_MATH_CAPTURE_SCHEMA_VERSION",
    "RankMathCaptureError",
    "RankMathCaptureResult",
    "capture_rank_math_inspection",
    "get_captured_rank_math_inspection",
]
