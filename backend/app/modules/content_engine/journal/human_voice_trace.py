"""Immutable CQ-05 Human Voice before/after trace."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.human_voice import (
    HUMAN_VOICE_POLICY_VERSION,
    HumanVoiceStyleComparison,
    compare_draft_style,
)
from app.modules.content_engine.journal.writer import JournalDraft
from app.modules.harness.models import Artifact, StepRun

HUMAN_VOICE_TRACE_ARTIFACT_TYPE = "human_voice_trace"
HUMAN_VOICE_TRACE_GENERATOR_VERSION = "cq05.human_voice_trace.v1"
HUMAN_VOICE_TRACE_SCHEMA_VERSION = 1


class HumanVoiceTraceError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class HumanVoiceTraceResult:
    artifact: Artifact
    style_comparison: HumanVoiceStyleComparison


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def draft_snapshot_hash(draft: JournalDraft) -> str:
    return _hash(draft.to_dict())


def _artifact_ref(artifact: Artifact, *, draft: JournalDraft) -> dict[str, object]:
    return {
        "id": str(artifact.id),
        "version": artifact.version,
        "content_hash": artifact.content_hash,
        "draft_hash": draft_snapshot_hash(draft),
    }


async def _append_step_output_ref(
    session: AsyncSession,
    *,
    artifact: Artifact,
) -> None:
    if artifact.step_run_id is None:
        return
    step = await session.get(StepRun, artifact.step_run_id)
    if step is None or step.run_id != artifact.run_id:
        raise HumanVoiceTraceError("human_voice_trace_step_binding_invalid")
    ref = str(artifact.id)
    if ref not in step.output_artifact_refs_json:
        step.output_artifact_refs_json = [*step.output_artifact_refs_json, ref]
        await session.flush()


def _payload(
    *,
    source_artifact: Artifact,
    source_draft: JournalDraft,
    rewritten_artifact: Artifact,
    rewritten_draft: JournalDraft,
) -> tuple[dict[str, object], HumanVoiceStyleComparison]:
    if (
        source_artifact.artifact_type != "journal_draft"
        or rewritten_artifact.artifact_type != "journal_draft"
        or source_artifact.run_id != rewritten_artifact.run_id
        or source_artifact.locale != rewritten_artifact.locale
        or source_draft.locale != rewritten_draft.locale
        or source_artifact.locale != source_draft.locale
    ):
        raise HumanVoiceTraceError("human_voice_trace_draft_lineage_invalid")
    if source_artifact.id == rewritten_artifact.id:
        raise HumanVoiceTraceError("human_voice_trace_distinct_drafts_required")

    comparison = compare_draft_style(source=source_draft, rewritten=rewritten_draft)
    payload: dict[str, object] = {
        "schema_version": HUMAN_VOICE_TRACE_SCHEMA_VERSION,
        "artifact_type": HUMAN_VOICE_TRACE_ARTIFACT_TYPE,
        "generator_version": HUMAN_VOICE_TRACE_GENERATOR_VERSION,
        "policy_version": HUMAN_VOICE_POLICY_VERSION,
        "locale": source_draft.locale,
        "source_draft": _artifact_ref(source_artifact, draft=source_draft),
        "rewritten_draft": _artifact_ref(rewritten_artifact, draft=rewritten_draft),
        "style_comparison": comparison.to_dict(),
    }
    return payload, comparison


def _validate_ref(
    value: object,
    *,
    artifact: Artifact,
    draft: JournalDraft,
    code: str,
) -> None:
    if not isinstance(value, dict) or set(value) != {
        "id",
        "version",
        "content_hash",
        "draft_hash",
    }:
        raise HumanVoiceTraceError(code)
    if (
        value.get("id") != str(artifact.id)
        or value.get("version") != artifact.version
        or value.get("content_hash") != artifact.content_hash
        or value.get("draft_hash") != draft_snapshot_hash(draft)
    ):
        raise HumanVoiceTraceError(code)


def _validate_trace(
    artifact: Artifact,
    *,
    source_artifact: Artifact,
    source_draft: JournalDraft,
    rewritten_artifact: Artifact,
    rewritten_draft: JournalDraft,
) -> HumanVoiceStyleComparison:
    expected_payload, comparison = _payload(
        source_artifact=source_artifact,
        source_draft=source_draft,
        rewritten_artifact=rewritten_artifact,
        rewritten_draft=rewritten_draft,
    )
    payload = artifact.content_json
    if (
        artifact.run_id != rewritten_artifact.run_id
        or artifact.step_run_id != rewritten_artifact.step_run_id
        or artifact.locale != rewritten_artifact.locale
        or artifact.artifact_type != HUMAN_VOICE_TRACE_ARTIFACT_TYPE
        or not isinstance(payload, dict)
        or set(payload) != set(expected_payload)
        or _hash(payload) != artifact.content_hash
        or payload.get("schema_version") != HUMAN_VOICE_TRACE_SCHEMA_VERSION
        or payload.get("artifact_type") != HUMAN_VOICE_TRACE_ARTIFACT_TYPE
        or payload.get("generator_version") != HUMAN_VOICE_TRACE_GENERATOR_VERSION
        or payload.get("policy_version") != HUMAN_VOICE_POLICY_VERSION
        or payload.get("locale") != rewritten_draft.locale
    ):
        raise HumanVoiceTraceError("human_voice_trace_artifact_invalid")

    _validate_ref(
        payload.get("source_draft"),
        artifact=source_artifact,
        draft=source_draft,
        code="human_voice_trace_source_binding_stale",
    )
    _validate_ref(
        payload.get("rewritten_draft"),
        artifact=rewritten_artifact,
        draft=rewritten_draft,
        code="human_voice_trace_rewrite_binding_stale",
    )
    if payload.get("style_comparison") != comparison.to_dict():
        raise HumanVoiceTraceError("human_voice_trace_comparison_stale")
    return comparison


async def persist_human_voice_trace(
    session: AsyncSession,
    *,
    source_artifact: Artifact,
    source_draft: JournalDraft,
    rewritten_artifact: Artifact,
    rewritten_draft: JournalDraft,
) -> HumanVoiceTraceResult:
    payload, comparison = _payload(
        source_artifact=source_artifact,
        source_draft=source_draft,
        rewritten_artifact=rewritten_artifact,
        rewritten_draft=rewritten_draft,
    )
    content_hash = _hash(payload)
    existing = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == rewritten_artifact.run_id,
            Artifact.artifact_type == HUMAN_VOICE_TRACE_ARTIFACT_TYPE,
            Artifact.content_hash == content_hash,
        )
    )
    if existing is not None:
        validated = _validate_trace(
            existing,
            source_artifact=source_artifact,
            source_draft=source_draft,
            rewritten_artifact=rewritten_artifact,
            rewritten_draft=rewritten_draft,
        )
        await _append_step_output_ref(session, artifact=existing)
        return HumanVoiceTraceResult(artifact=existing, style_comparison=validated)

    latest_version = await session.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.run_id == rewritten_artifact.run_id,
            Artifact.artifact_type == HUMAN_VOICE_TRACE_ARTIFACT_TYPE,
        )
    )
    artifact = Artifact(
        run_id=rewritten_artifact.run_id,
        step_run_id=rewritten_artifact.step_run_id,
        artifact_type=HUMAN_VOICE_TRACE_ARTIFACT_TYPE,
        locale=rewritten_artifact.locale,
        version=(latest_version or 0) + 1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    await _append_step_output_ref(session, artifact=artifact)
    return HumanVoiceTraceResult(artifact=artifact, style_comparison=comparison)


def _binds_rewritten(artifact: Artifact, *, rewritten_artifact: Artifact) -> bool:
    payload = artifact.content_json
    if not isinstance(payload, dict):
        return False
    rewritten = payload.get("rewritten_draft")
    if not isinstance(rewritten, dict):
        return False
    return rewritten.get("id") == str(rewritten_artifact.id)


async def load_human_voice_trace(
    session: AsyncSession,
    *,
    source_artifact: Artifact,
    source_draft: JournalDraft,
    rewritten_artifact: Artifact,
    rewritten_draft: JournalDraft,
) -> HumanVoiceTraceResult:
    rows = list(
        (
            await session.scalars(
                select(Artifact)
                .where(
                    Artifact.run_id == rewritten_artifact.run_id,
                    Artifact.artifact_type == HUMAN_VOICE_TRACE_ARTIFACT_TYPE,
                )
                .order_by(Artifact.version, Artifact.id)
            )
        ).all()
    )
    matches = [
        artifact
        for artifact in rows
        if _binds_rewritten(artifact, rewritten_artifact=rewritten_artifact)
    ]
    if len(matches) != 1:
        raise HumanVoiceTraceError(
            "human_voice_trace_required"
            if not matches
            else "human_voice_trace_conflict"
        )
    artifact = matches[0]
    comparison = _validate_trace(
        artifact,
        source_artifact=source_artifact,
        source_draft=source_draft,
        rewritten_artifact=rewritten_artifact,
        rewritten_draft=rewritten_draft,
    )
    return HumanVoiceTraceResult(artifact=artifact, style_comparison=comparison)


__all__ = [
    "HUMAN_VOICE_TRACE_ARTIFACT_TYPE",
    "HUMAN_VOICE_TRACE_GENERATOR_VERSION",
    "HUMAN_VOICE_TRACE_SCHEMA_VERSION",
    "HumanVoiceTraceError",
    "HumanVoiceTraceResult",
    "draft_snapshot_hash",
    "load_human_voice_trace",
    "persist_human_voice_trace",
]
