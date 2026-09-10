"""Durable CE05 T05.14 assertion-audit eval-run execution boundary."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.assertion_audit import (
    ASSERTION_AUDIT_GENERATOR_VERSION,
    ASSERTION_AUDIT_SCHEMA_VERSION,
    AssertionAuditError,
    AssertionAuditInput,
)
from app.modules.content_engine.journal.writer import _canonical_hash
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.models import Artifact, ContentRun, ContextManifest, StepRun, utc_now
from app.modules.harness.runtime import ContextInputs, build_context_manifest

ASSERTION_AUDIT_HANDOFF_SCHEMA_VERSION = 1
LEGACY_FAILED_VI_WRITER_RUN_ID = UUID("1f0b91a7-39d7-449f-84ad-988fd1e8f44e")
LEGACY_FAILED_VI_DRAFT_ID = UUID("a0afa7d0-af3d-4669-ae18-54c54b87731f")
LEGACY_FAILED_VI_DRAFT_VERSION = 2
LEGACY_FAILED_VI_DRAFT_HASH = (
    "da5fd6e78e19bf4c395797d39379fdb66fd9766f75649e3054e03a0a03677e85"
)


@dataclass(frozen=True, slots=True)
class AssertionAuditRunContext:
    source_input: AssertionAuditInput
    audit_run: ContentRun
    handoff: Artifact
    step_run: StepRun
    context_manifest: ContextManifest
    audit_run_reused: bool
    step_created: bool
    manifest_created: bool


def _handoff_payload(
    *,
    source_input: AssertionAuditInput,
    settings_snapshot: SettingsSnapshot,
    task_key: str,
) -> dict[str, object]:
    writer_run = source_input.writer_input.writer_run
    source_artifact = source_input.source_artifact
    outline = source_input.writer_input.outline_artifact
    variant = source_input.writer_input.locale_variant
    return {
        "schema_version": ASSERTION_AUDIT_HANDOFF_SCHEMA_VERSION,
        "artifact_type": "assertion_audit_handoff",
        "task_key": task_key,
        "generator": {
            "version": ASSERTION_AUDIT_GENERATOR_VERSION,
            "schema_version": ASSERTION_AUDIT_SCHEMA_VERSION,
        },
        "source_writer_run": {
            "id": str(writer_run.id),
            "run_mode": writer_run.run_mode,
        },
        "source_draft": {
            "id": str(source_artifact.id),
            "version": source_artifact.version,
            "content_hash": source_artifact.content_hash,
        },
        "journal_outline": {
            "id": str(outline.id),
            "version": outline.version,
            "content_hash": outline.content_hash,
        },
        "content_case_id": str(writer_run.content_case_id),
        "locale_variant": {"id": str(variant.id), "locale": variant.locale},
        "settings_snapshot": {
            "id": str(settings_snapshot.id),
            "content_hash": settings_snapshot.content_hash,
        },
    }


def _validate_source_writer_state(source_input: AssertionAuditInput) -> None:
    run = source_input.writer_input.writer_run
    if run.status == "waiting_approval":
        return
    if (
        run.status == "failed"
        and run.id == LEGACY_FAILED_VI_WRITER_RUN_ID
        and source_input.writer_input.locale == "vi-VN"
        and source_input.source_artifact.id == LEGACY_FAILED_VI_DRAFT_ID
        and source_input.source_artifact.version == LEGACY_FAILED_VI_DRAFT_VERSION
        and source_input.source_artifact.content_hash == LEGACY_FAILED_VI_DRAFT_HASH
    ):
        return
    raise AssertionAuditError("assertion_audit_source_writer_state_invalid", run.status)


def _validate_handoff(
    *,
    handoff: Artifact,
    payload: dict[str, object],
    source_input: AssertionAuditInput,
    settings_snapshot: SettingsSnapshot,
    task_key: str,
) -> None:
    if (
        handoff.artifact_type != "assertion_audit_handoff"
        or handoff.version != 1
        or handoff.step_run_id is not None
        or handoff.locale != source_input.writer_input.locale
        or handoff.content_json != payload
        or _canonical_hash(payload) != handoff.content_hash
    ):
        raise AssertionAuditError("assertion_audit_handoff_snapshot_invalid")
    if handoff.run_id == source_input.writer_input.writer_run.id:
        raise AssertionAuditError("assertion_audit_handoff_source_run_conflict")
    if payload.get("task_key") != task_key:
        raise AssertionAuditError("assertion_audit_handoff_task_mismatch")
    settings = payload.get("settings_snapshot")
    if not isinstance(settings, dict):
        raise AssertionAuditError("assertion_audit_handoff_settings_invalid")
    if settings.get("id") != str(settings_snapshot.id) or settings.get(
        "content_hash"
    ) != settings_snapshot.content_hash:
        raise AssertionAuditError("assertion_audit_handoff_settings_mismatch")


async def ensure_assertion_audit_run(
    session: AsyncSession,
    *,
    source_input: AssertionAuditInput,
    task_key: str,
) -> tuple[ContentRun, Artifact, bool]:
    """Reuse one non-terminal audit eval or create a replacement for a failed one."""

    _validate_source_writer_state(source_input)
    source_run = source_input.writer_input.writer_run
    settings_snapshot = await session.get(SettingsSnapshot, source_run.settings_snapshot_id)
    if settings_snapshot is None:
        raise AssertionAuditError("assertion_audit_settings_snapshot_missing")

    payload = _handoff_payload(
        source_input=source_input,
        settings_snapshot=settings_snapshot,
        task_key=task_key,
    )
    handoff_hash = _canonical_hash(payload)
    handoffs = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.artifact_type == "assertion_audit_handoff",
                    Artifact.content_hash == handoff_hash,
                )
            )
        ).all()
    )
    reusable: list[tuple[ContentRun, Artifact]] = []
    for handoff in handoffs:
        _validate_handoff(
            handoff=handoff,
            payload=payload,
            source_input=source_input,
            settings_snapshot=settings_snapshot,
            task_key=task_key,
        )
        run = await session.get(ContentRun, handoff.run_id)
        if run is None:
            raise AssertionAuditError("assertion_audit_handoff_run_missing")
        if (
            run.run_mode != "eval"
            or run.project_id != source_run.project_id
            or run.content_case_id != source_run.content_case_id
            or run.locale_variant_id != source_input.writer_input.locale_variant.id
            or run.content_item_id != source_run.content_item_id
            or run.settings_snapshot_id != source_run.settings_snapshot_id
        ):
            raise AssertionAuditError("assertion_audit_handoff_run_mismatch")
        if run.status not in {"failed", "cancelled"}:
            reusable.append((run, handoff))

    if len(reusable) > 1:
        raise AssertionAuditError("assertion_audit_reusable_run_duplicate")
    if reusable:
        run, handoff = reusable[0]
        return run, handoff, True

    run = ContentRun(
        project_id=source_run.project_id,
        content_case_id=source_run.content_case_id,
        locale_variant_id=source_input.writer_input.locale_variant.id,
        content_item_id=source_run.content_item_id,
        run_mode="eval",
        status="pending",
        current_step=task_key,
        settings_snapshot_id=source_run.settings_snapshot_id,
        started_at=utc_now(),
    )
    session.add(run)
    await session.flush()
    handoff = Artifact(
        run_id=run.id,
        artifact_type="assertion_audit_handoff",
        locale=source_input.writer_input.locale,
        version=1,
        content_json=payload,
        content_hash=handoff_hash,
    )
    session.add(handoff)
    await session.flush()
    return run, handoff, False


async def prepare_assertion_audit_run(
    session: AsyncSession,
    *,
    source_input: AssertionAuditInput,
    task_key: str,
    prompt_version: str,
    recipe_version: str,
) -> AssertionAuditRunContext:
    audit_run, handoff, audit_run_reused = await ensure_assertion_audit_run(
        session,
        source_input=source_input,
        task_key=task_key,
    )
    steps = list(
        (
            await session.scalars(
                select(StepRun)
                .where(StepRun.run_id == audit_run.id, StepRun.step_key == task_key)
                .order_by(StepRun.attempt)
            )
        ).all()
    )
    if len(steps) > 1:
        raise AssertionAuditError("assertion_audit_step_attempt_conflict", task_key)
    step_created = not steps
    if step_created:
        step = StepRun(
            run_id=audit_run.id,
            step_key=task_key,
            attempt=1,
            status="pending",
            input_artifact_refs_json=[
                str(handoff.id),
                str(source_input.source_artifact.id),
                str(source_input.writer_input.outline_artifact.id),
            ],
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
    else:
        step = steps[0]
        if step.status in {"failed", "skipped"}:
            raise AssertionAuditError("assertion_audit_existing_step_terminal", step.status)

    manifests = list(
        (
            await session.scalars(
                select(ContextManifest).where(
                    ContextManifest.run_id == audit_run.id,
                    ContextManifest.step_run_id == step.id,
                )
            )
        ).all()
    )
    if len(manifests) > 1:
        raise AssertionAuditError("assertion_audit_context_manifest_duplicate")
    manifest_created = not manifests
    if manifest_created:
        if not step_created:
            raise AssertionAuditError("assertion_audit_context_manifest_missing")
        upstream = source_input.writer_input.outline_input.bundle.context_manifest
        manifest = await build_context_manifest(
            session,
            run_id=audit_run.id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                evidence_set_id=source_input.writer_input.outline_input.bundle.evidence_set_id,
                originality_pack_id=(
                    source_input.writer_input.outline_input.bundle.originality_pack_id
                ),
                approved_knowledge_refs=(
                    tuple(upstream.approved_knowledge_refs_json) if upstream is not None else ()
                ),
                knowledge_chunk_refs=(
                    tuple(upstream.knowledge_chunk_refs_json) if upstream is not None else ()
                ),
                golden_example_refs=(
                    tuple(upstream.golden_example_refs_json) if upstream is not None else ()
                ),
                tool_result_refs=(),
            ),
        )
    else:
        manifest = manifests[0]
        if (
            manifest.prompt_version != prompt_version
            or manifest.recipe_version != recipe_version
            or manifest.settings_snapshot_id != audit_run.settings_snapshot_id
            or manifest.evidence_set_id
            != source_input.writer_input.outline_input.bundle.evidence_set_id
            or manifest.originality_pack_id
            != source_input.writer_input.outline_input.bundle.originality_pack_id
        ):
            raise AssertionAuditError("assertion_audit_context_manifest_snapshot_mismatch")

    if audit_run.status == "completed" and step.status != "completed":
        raise AssertionAuditError("assertion_audit_completed_run_step_mismatch")
    if audit_run.status == "pending" and step.status != "pending":
        raise AssertionAuditError("assertion_audit_pending_run_step_mismatch")
    if audit_run.status == "running" and step.status not in {"pending", "running"}:
        raise AssertionAuditError("assertion_audit_running_run_step_mismatch")
    if audit_run.status not in {"pending", "running", "completed"}:
        raise AssertionAuditError("assertion_audit_run_state_invalid", audit_run.status)

    return AssertionAuditRunContext(
        source_input=source_input,
        audit_run=audit_run,
        handoff=handoff,
        step_run=step,
        context_manifest=manifest,
        audit_run_reused=audit_run_reused,
        step_created=step_created,
        manifest_created=manifest_created,
    )


__all__ = [
    "ASSERTION_AUDIT_HANDOFF_SCHEMA_VERSION",
    "AssertionAuditRunContext",
    "ensure_assertion_audit_run",
    "prepare_assertion_audit_run",
]
