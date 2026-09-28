"""Publish-assisted observation lane for real manual operation.

This module records what actually happened without pretending that a manual publication
has passed the canonical PM-01 publication contract.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import LocaleVariant
from app.modules.harness.models import Artifact, ContentRun, Job, StepRun
from app.modules.research.utils import validate_public_http_url

ASSISTED_OBSERVATION_ARTIFACT_TYPE = "publish_assisted_observation"
ASSISTED_OBSERVATION_SCHEMA_VERSION = 1
AssistedPhase = Literal["draft", "published"]


class PublishAssistedError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PublishAssistedObservationResult:
    artifact: Artifact
    replayed: bool


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clean_text(value: str, code: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise PublishAssistedError(code)
    return normalized


def _draft_payload(payload: dict[str, object]) -> dict[str, object]:
    nested = payload.get("draft")
    if isinstance(nested, dict):
        return cast(dict[str, object], nested)
    return payload


def _artifact_visible_text(artifact: Artifact) -> str | None:
    if not isinstance(artifact.content_json, dict):
        return None
    payload = _draft_payload(cast(dict[str, object], artifact.content_json))
    title = payload.get("title")
    standfirst = payload.get("standfirst")
    lead = payload.get("lead_markdown")
    closing = payload.get("closing_markdown")
    sections = payload.get("sections")
    if not all(isinstance(value, str) for value in (title, standfirst, lead, closing)):
        return None
    if not isinstance(sections, list):
        return None

    parts = [
        f"# {cast(str, title).strip()}",
        cast(str, standfirst).strip(),
        cast(str, lead).strip(),
    ]
    for raw in sections:
        if not isinstance(raw, dict):
            return None
        heading = raw.get("heading")
        body = raw.get("body_markdown")
        if not isinstance(heading, str) or not isinstance(body, str):
            return None
        parts.append(f"## {heading.strip()}\n\n{body.strip()}")
    parts.append(cast(str, closing).strip())
    return "\n\n".join(part for part in parts if part)


def _edit_delta(source: str | None, manual: str) -> dict[str, object]:
    if source is None:
        return {
            "status": "source_text_unavailable",
            "source_chars": None,
            "manual_chars": len(manual),
            "similarity_ratio": None,
            "changed_blocks": None,
            "added_lines": None,
            "removed_lines": None,
        }

    source_lines = source.splitlines()
    manual_lines = manual.splitlines()
    matcher = SequenceMatcher(a=source_lines, b=manual_lines, autojunk=False)
    opcodes = matcher.get_opcodes()
    changed = [opcode for opcode in opcodes if opcode[0] != "equal"]
    added_lines = sum(j2 - j1 for tag, _i1, _i2, j1, j2 in changed if tag in {"insert", "replace"})
    removed_lines = sum(
        i2 - i1
        for tag, i1, i2, _j1, _j2 in changed
        if tag in {"delete", "replace"}
    )
    return {
        "status": "compared",
        "source_chars": len(source),
        "manual_chars": len(manual),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "manual_sha256": hashlib.sha256(manual.encode("utf-8")).hexdigest(),
        "similarity_ratio": round(matcher.ratio(), 6),
        "changed_blocks": len(changed),
        "added_lines": added_lines,
        "removed_lines": removed_lines,
    }


async def _pipeline_snapshot(
    session: AsyncSession,
    *,
    run: ContentRun,
) -> dict[str, object]:
    rows = list(
        (
            await session.execute(
                select(Job, StepRun.step_key)
                .join(StepRun, StepRun.id == Job.step_run_id)
                .where(Job.run_id == run.id)
                .order_by(Job.created_at.asc(), Job.id.asc())
            )
        ).all()
    )
    return {
        "run_id": str(run.id),
        "run_status": run.status,
        "current_step": run.current_step,
        "failure_code": run.failure_code,
        "jobs": [
            {
                "id": str(job.id),
                "attempt": job.attempt,
                "status": job.status,
                "step_key": step_key,
            }
            for job, step_key in rows
        ],
    }


async def record_publish_assisted_observation(
    session: AsyncSession,
    *,
    source_run_id: UUID,
    phase: AssistedPhase,
    actor_id: str,
    content_markdown: str,
    source_artifact_id: UUID | None = None,
    canonical_url: str | None = None,
    external_id: str | None = None,
    note: str | None = None,
) -> PublishAssistedObservationResult:
    """Append one immutable operational observation.

    The record is intentionally not PublishedContent/PublishEvent. It is an observed
    manual state that may later be reconciled to canonical PM-01 lineage.
    """

    if phase not in {"draft", "published"}:
        raise PublishAssistedError("publish_assisted_phase_invalid")
    actor = _clean_text(actor_id, "publish_assisted_actor_required")
    manual = _clean_text(content_markdown, "publish_assisted_content_required")

    run = await session.scalar(
        select(ContentRun).where(ContentRun.id == source_run_id).with_for_update()
    )
    if run is None or run.run_mode == "eval":
        raise PublishAssistedError("publish_assisted_source_run_invalid")
    variant = await session.get(LocaleVariant, run.locale_variant_id)
    if variant is None or variant.content_case_id != run.content_case_id:
        raise PublishAssistedError("publish_assisted_locale_binding_invalid")

    normalized_url: str | None = None
    if canonical_url is not None and canonical_url.strip():
        try:
            normalized_url = validate_public_http_url(canonical_url.strip())
        except ValueError as exc:
            raise PublishAssistedError("publish_assisted_url_invalid") from exc
    if phase == "published" and normalized_url is None:
        raise PublishAssistedError("publish_assisted_published_url_required")

    source_artifact: Artifact | None = None
    source_text: str | None = None
    source_ref: dict[str, object] | None = None
    if source_artifact_id is not None:
        source_artifact = await session.get(Artifact, source_artifact_id)
        if source_artifact is None:
            raise PublishAssistedError("publish_assisted_source_artifact_missing")
        source_artifact_run = await session.get(ContentRun, source_artifact.run_id)
        if (
            source_artifact_run is None
            or source_artifact_run.content_case_id != run.content_case_id
            or source_artifact_run.locale_variant_id != run.locale_variant_id
        ):
            raise PublishAssistedError("publish_assisted_source_artifact_mismatch")
        source_text = _artifact_visible_text(source_artifact)
        source_ref = {
            "id": str(source_artifact.id),
            "run_id": str(source_artifact.run_id),
            "artifact_type": source_artifact.artifact_type,
            "version": source_artifact.version,
            "content_hash": source_artifact.content_hash,
        }

    payload: dict[str, object] = {
        "schema_version": ASSISTED_OBSERVATION_SCHEMA_VERSION,
        "artifact_type": ASSISTED_OBSERVATION_ARTIFACT_TYPE,
        "mode": "founder_manual_publish_assisted",
        "phase": phase,
        "identity": {
            "project_id": str(run.project_id),
            "content_case_id": str(run.content_case_id),
            "locale_variant_id": str(run.locale_variant_id),
            "content_item_id": str(run.content_item_id) if run.content_item_id else None,
            "locale": variant.locale,
        },
        "actor_id": actor,
        "source_ai_artifact": source_ref,
        "manual_snapshot": {
            "content_markdown": manual,
            "content_sha256": hashlib.sha256(manual.encode("utf-8")).hexdigest(),
        },
        "edit_delta": _edit_delta(source_text, manual),
        "publication_observation": {
            "canonical_url": normalized_url,
            "external_id": (
                external_id.strip()
                if isinstance(external_id, str) and external_id.strip()
                else None
            ),
            "canonical_pm01_bound": False,
        },
        "pipeline_snapshot": await _pipeline_snapshot(session, run=run),
        "note": note.strip() if isinstance(note, str) and note.strip() else None,
    }
    content_hash = _hash(payload)

    existing = await session.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == run.id,
            Artifact.artifact_type == ASSISTED_OBSERVATION_ARTIFACT_TYPE,
            Artifact.content_hash == content_hash,
        )
        .order_by(Artifact.version.asc(), Artifact.id.asc())
        .limit(1)
    )
    if existing is not None:
        if existing.content_json != payload:
            raise PublishAssistedError("publish_assisted_replay_conflict")
        return PublishAssistedObservationResult(artifact=existing, replayed=True)

    next_version = int(
        await session.scalar(
            select(func.coalesce(func.max(Artifact.version), 0) + 1).where(
                Artifact.run_id == run.id,
                Artifact.artifact_type == ASSISTED_OBSERVATION_ARTIFACT_TYPE,
            )
        )
        or 1
    )
    artifact = Artifact(
        run_id=run.id,
        step_run_id=None,
        artifact_type=ASSISTED_OBSERVATION_ARTIFACT_TYPE,
        locale=variant.locale,
        version=next_version,
        content_json=payload,
        content_hash=content_hash,
        external_ref=normalized_url if phase == "published" else None,
    )
    session.add(artifact)
    await session.flush()
    return PublishAssistedObservationResult(artifact=artifact, replayed=False)


__all__ = [
    "ASSISTED_OBSERVATION_ARTIFACT_TYPE",
    "PublishAssistedError",
    "PublishAssistedObservationResult",
    "record_publish_assisted_observation",
]
