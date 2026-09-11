"""Durable CE05 T05.14 assertion-audit eval-run execution boundary."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.assertion_audit import (
    ASSERTION_AUDIT_EVALUATOR_KEY,
    ASSERTION_AUDIT_EVALUATOR_VERSION,
    ASSERTION_AUDIT_GENERATOR_VERSION,
    ASSERTION_AUDIT_SCHEMA_VERSION,
    AssertionAuditError,
    AssertionAuditInput,
    _fingerprint,
    _summary,
    validate_assertion_audit_output,
)
from app.modules.content_engine.journal.writer import (
    WriterInput,
    _canonical_hash,
    _dict,
    writer_model_input_hash,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ContextManifest,
    ModelCall,
    QualityEvaluation,
    StepRun,
    ToolCall,
    utc_now,
)
from app.modules.harness.runtime import ContextInputs, _stable_hash, build_context_manifest

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
    reusable_run_count: int
    duplicate_run_ids: tuple[UUID, ...]
    duplicate_recovery_used: bool


@dataclass(frozen=True, slots=True)
class _CompletedAuditCandidate:
    run: ContentRun
    handoff: Artifact
    step: StepRun
    manifest: ContextManifest
    artifact: Artifact
    evaluation: QualityEvaluation
    summary: dict[str, int | str]
    provider: str
    model: str
    prompt_version: str
    recipe_version: str


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


def validate_source_writer_eligibility(
    *,
    writer_input: WriterInput,
    source_artifact: Artifact,
) -> None:
    """Validate the exact source-writer states accepted by T05.14."""

    run = writer_input.writer_run
    if run.status == "waiting_approval":
        return
    if (
        run.status == "failed"
        and run.id == LEGACY_FAILED_VI_WRITER_RUN_ID
        and writer_input.locale == "vi-VN"
        and source_artifact.id == LEGACY_FAILED_VI_DRAFT_ID
        and source_artifact.version == LEGACY_FAILED_VI_DRAFT_VERSION
        and source_artifact.content_hash == LEGACY_FAILED_VI_DRAFT_HASH
    ):
        return
    raise AssertionAuditError("assertion_audit_source_writer_state_invalid", run.status)


def _validate_source_writer_state(source_input: AssertionAuditInput) -> None:
    validate_source_writer_eligibility(
        writer_input=source_input.writer_input,
        source_artifact=source_input.source_artifact,
    )


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
    prompt_version: str,
    recipe_version: str,
    provider: str | None = None,
    model: str | None = None,
) -> tuple[ContentRun, Artifact, bool, int, tuple[UUID, ...], bool]:
    """Serialize, validate and resolve one exact Assertion Audit eval run."""

    source_run_id = source_input.writer_input.writer_run.id
    locked_source_run = await session.scalar(
        select(ContentRun)
        .where(ContentRun.id == source_run_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if locked_source_run is None:
        raise AssertionAuditError("assertion_audit_source_writer_run_missing")
    if locked_source_run.status != source_input.writer_input.writer_run.status:
        raise AssertionAuditError("assertion_audit_source_writer_state_changed")
    _validate_source_writer_state(source_input)
    source_run = locked_source_run
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
    active: list[tuple[ContentRun, Artifact]] = []
    completed: list[tuple[ContentRun, Artifact]] = []
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
        if run.status in {"pending", "running"}:
            active.append((run, handoff))
        elif run.status == "completed":
            completed.append((run, handoff))
        elif run.status not in {"failed", "cancelled"}:
            raise AssertionAuditError("assertion_audit_duplicate_run_state_invalid", run.status)

    if active and (len(active) > 1 or completed):
        active_ids = ",".join(
            str(run.id) for run, _handoff in sorted(active, key=lambda item: item[0].id)
        )
        raise AssertionAuditError("assertion_audit_active_duplicate", active_ids)

    if active:
        run, handoff = active[0]
        return run, handoff, True, 1, (run.id,), False

    duplicate_ids = tuple(sorted((run.id for run, _handoff in completed)))
    if len(completed) == 1:
        run, handoff = completed[0]
        return run, handoff, True, 1, duplicate_ids, False
    if completed:
        candidates = [
            await _validate_completed_candidate(
                session,
                source_input=source_input,
                run=run,
                handoff=handoff,
                task_key=task_key,
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                expected_provider=provider,
                expected_model=model,
            )
            for run, handoff in completed
        ]
        first = candidates[0]
        summary_keys = (
            "result",
            "assertion_count",
            "critical_unsupported_count",
            "critical_contradicted_count",
            "unsupported_count",
            "contradicted_count",
        )
        for candidate in candidates[1:]:
            if any(candidate.summary[key] != first.summary[key] for key in summary_keys):
                raise AssertionAuditError("assertion_audit_duplicate_summary_conflict")
            if (
                candidate.provider,
                candidate.model,
                candidate.prompt_version,
                candidate.recipe_version,
            ) != (
                first.provider,
                first.model,
                first.prompt_version,
                first.recipe_version,
            ):
                raise AssertionAuditError("assertion_audit_duplicate_route_conflict")
        canonical = min(candidates, key=lambda item: (item.run.created_at, item.run.id))
        return canonical.run, canonical.handoff, True, len(candidates), duplicate_ids, True

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
    return run, handoff, False, 0, (), False


async def _validate_completed_candidate(
    session: AsyncSession,
    *,
    source_input: AssertionAuditInput,
    run: ContentRun,
    handoff: Artifact,
    task_key: str,
    prompt_version: str,
    recipe_version: str,
    expected_provider: str | None,
    expected_model: str | None,
) -> _CompletedAuditCandidate:
    """Validate one completed duplicate without changing any persisted row."""

    if run.status != "completed":
        raise AssertionAuditError("assertion_audit_duplicate_candidate_not_completed")

    task_steps = list(
        (
            await session.scalars(
                select(StepRun).where(
                    StepRun.run_id == run.id,
                    StepRun.step_key == task_key,
                )
            )
        ).all()
    )
    if len(task_steps) != 1 or task_steps[0].status != "completed":
        raise AssertionAuditError("assertion_audit_duplicate_candidate_step_invalid")
    step = task_steps[0]
    expected_input_refs = [
        str(handoff.id),
        str(source_input.source_artifact.id),
        str(source_input.writer_input.outline_artifact.id),
    ]
    if step.input_artifact_refs_json != expected_input_refs:
        raise AssertionAuditError("assertion_audit_duplicate_candidate_step_binding_invalid")

    manifests = list(
        (
            await session.scalars(
                select(ContextManifest).where(
                    ContextManifest.run_id == run.id,
                    ContextManifest.step_run_id == step.id,
                )
            )
        ).all()
    )
    if len(manifests) != 1:
        raise AssertionAuditError("assertion_audit_duplicate_candidate_manifest_invalid")
    manifest = manifests[0]
    bundle = source_input.writer_input.outline_input.bundle
    upstream = bundle.context_manifest
    expected_approved_refs = tuple(upstream.approved_knowledge_refs_json) if upstream else ()
    expected_knowledge_refs = tuple(upstream.knowledge_chunk_refs_json) if upstream else ()
    expected_golden_refs = tuple(upstream.golden_example_refs_json) if upstream else ()
    if (
        manifest.run_id != run.id
        or manifest.step_run_id != step.id
        or manifest.settings_snapshot_id != run.settings_snapshot_id
        or manifest.prompt_version != prompt_version
        or manifest.recipe_version != recipe_version
        or manifest.evidence_set_id != bundle.evidence_set_id
        or manifest.originality_pack_id != bundle.originality_pack_id
        or tuple(manifest.approved_knowledge_refs_json) != expected_approved_refs
        or tuple(manifest.knowledge_chunk_refs_json) != expected_knowledge_refs
        or tuple(manifest.golden_example_refs_json) != expected_golden_refs
        or tuple(manifest.tool_result_refs_json) != ()
    ):
        raise AssertionAuditError("assertion_audit_duplicate_candidate_manifest_binding_invalid")
    manifest_payload = {
        "run_id": str(run.id),
        "step_run_id": str(step.id),
        "settings_snapshot_id": str(run.settings_snapshot_id),
        "prompt_version": manifest.prompt_version,
        "recipe_version": manifest.recipe_version,
        "evidence_set_id": str(manifest.evidence_set_id) if manifest.evidence_set_id else None,
        "originality_pack_id": (
            str(manifest.originality_pack_id) if manifest.originality_pack_id else None
        ),
        "context_artifact_id": (
            str(manifest.context_artifact_id) if manifest.context_artifact_id else None
        ),
        "approved_knowledge_refs": manifest.approved_knowledge_refs_json,
        "knowledge_chunk_refs": manifest.knowledge_chunk_refs_json,
        "golden_example_refs": manifest.golden_example_refs_json,
        "tool_result_refs": manifest.tool_result_refs_json,
    }
    if _stable_hash(manifest_payload) != manifest.content_hash:
        raise AssertionAuditError("assertion_audit_duplicate_candidate_manifest_stale")

    candidate_handoffs = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == run.id,
                    Artifact.artifact_type == "assertion_audit_handoff",
                )
            )
        ).all()
    )
    if len(candidate_handoffs) != 1 or candidate_handoffs[0].id != handoff.id:
        raise AssertionAuditError("assertion_audit_duplicate_candidate_handoff_invalid")

    audit_artifacts = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == run.id,
                    Artifact.artifact_type == "assertion_audit",
                )
            )
        ).all()
    )
    if len(audit_artifacts) != 1:
        raise AssertionAuditError("assertion_audit_duplicate_candidate_artifact_invalid")
    artifact = audit_artifacts[0]
    if (
        artifact.step_run_id != step.id
        or artifact.locale != source_input.writer_input.locale
        or artifact.version != 1
        or not isinstance(artifact.content_json, dict)
        or _canonical_hash(artifact.content_json) != artifact.content_hash
    ):
        raise AssertionAuditError("assertion_audit_duplicate_candidate_artifact_invalid")
    payload = _dict(artifact.content_json, "assertion_audit_duplicate_candidate_artifact_invalid")
    expected_source = {
        "id": str(source_input.source_artifact.id),
        "version": source_input.source_artifact.version,
        "content_hash": source_input.source_artifact.content_hash,
    }
    expected_outline = {
        "id": str(source_input.writer_input.outline_artifact.id),
        "version": source_input.writer_input.outline_artifact.version,
        "content_hash": source_input.writer_input.outline_artifact.content_hash,
    }
    expected_evidence = {
        "id": str(bundle.evidence_set_id),
        "version": bundle.evidence_set_version,
        "content_hash": bundle.evidence_set_hash,
    }
    expected_originality = {
        "id": str(bundle.originality_pack_id),
        "snapshot_hash": bundle.originality_pack_hash,
    }
    execution_context = payload.get("execution_context")
    generator = payload.get("generator")
    model_payload = payload.get("model")
    if (
        payload.get("artifact_type") != "assertion_audit"
        or payload.get("schema_version") != ASSERTION_AUDIT_SCHEMA_VERSION
        or payload.get("locale") != source_input.writer_input.locale
        or payload.get("source_draft") != expected_source
        or payload.get("source_writer_run_id") != str(source_input.writer_input.writer_run.id)
        or payload.get("journal_outline") != expected_outline
        or payload.get("evidence_set") != expected_evidence
        or payload.get("originality_pack") != expected_originality
        or generator
        != {
            "version": ASSERTION_AUDIT_GENERATOR_VERSION,
            "schema_version": ASSERTION_AUDIT_SCHEMA_VERSION,
        }
        or not isinstance(execution_context, dict)
        or execution_context.get("context_manifest_id") != str(manifest.id)
        or execution_context.get("context_manifest_hash") != manifest.content_hash
        or execution_context.get("settings_snapshot_id") != str(run.settings_snapshot_id)
        or execution_context.get("prompt_version") != prompt_version
        or execution_context.get("recipe_version") != recipe_version
        or not isinstance(model_payload, dict)
    ):
        raise AssertionAuditError("assertion_audit_duplicate_candidate_artifact_binding_invalid")
    model_provider = model_payload.get("provider")
    model_name = model_payload.get("model")
    model_calls = model_payload.get("model_calls")
    if (
        not isinstance(model_provider, str)
        or not isinstance(model_name, str)
        or not model_provider
        or not model_name
        or not isinstance(model_calls, int)
        or isinstance(model_calls, bool)
        or model_calls < 1
    ):
        raise AssertionAuditError("assertion_audit_duplicate_candidate_model_invalid")
    if (
        expected_provider is not None
        and expected_model is not None
        and (model_provider, model_name) != (expected_provider, expected_model)
    ):
        raise AssertionAuditError("assertion_audit_duplicate_candidate_route_invalid")

    model_call_rows = list(
        (
            await session.scalars(
                select(ModelCall).where(
                    ModelCall.run_id == run.id,
                    ModelCall.step_run_id == step.id,
                    ModelCall.context_manifest_id == manifest.id,
                )
            )
        ).all()
    )
    if len(model_call_rows) != model_calls or any(
        call.status != "completed"
        or call.task_key != task_key
        or call.provider != model_provider
        or call.model != model_name
        or call.prompt_version != prompt_version
        for call in model_call_rows
    ):
        raise AssertionAuditError("assertion_audit_duplicate_candidate_model_call_invalid")
    tool_calls = list(
        (
            await session.scalars(select(ToolCall).where(ToolCall.run_id == run.id))
        ).all()
    )
    if tool_calls:
        raise AssertionAuditError("assertion_audit_duplicate_candidate_tool_call_invalid")

    model_input = payload.get("model_input")
    if not isinstance(model_input, dict) or model_input.get(
        "content_hash"
    ) != writer_model_input_hash(source_input.model_input):
        raise AssertionAuditError("assertion_audit_duplicate_candidate_model_input_invalid")
    expected_fingerprint = _fingerprint(
        audit_input=source_input,
        model_input_hash=writer_model_input_hash(source_input.model_input),
        provider=model_provider,
        model=model_name,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
        context_manifest_hash=manifest.content_hash,
    )
    if payload.get("generation_fingerprint") != expected_fingerprint:
        raise AssertionAuditError("assertion_audit_duplicate_candidate_fingerprint_invalid")
    raw_segments = payload.get("segments")
    segments = validate_assertion_audit_output(
        {"locale": source_input.writer_input.locale, "segments": raw_segments},
        audit_input=source_input,
    )
    summary = _summary(segments)
    if payload.get("summary") != summary:
        raise AssertionAuditError("assertion_audit_duplicate_candidate_summary_invalid")

    evaluations = list(
        (
            await session.scalars(
                select(QualityEvaluation).where(QualityEvaluation.run_id == run.id)
            )
        ).all()
    )
    if (
        len(evaluations) != 1
        or evaluations[0].artifact_id != artifact.id
        or evaluations[0].evaluator_key != ASSERTION_AUDIT_EVALUATOR_KEY
        or evaluations[0].evaluator_version != ASSERTION_AUDIT_EVALUATOR_VERSION
    ):
        raise AssertionAuditError("assertion_audit_duplicate_candidate_evaluation_invalid")
    evaluation = evaluations[0]
    expected_severity = {
        "pass": "none",
        "warn": "medium",
        "fail": "critical",
    }[str(summary["result"])]
    if (
        evaluation.evaluator_type != "deterministic"
        or evaluation.result != summary["result"]
        or evaluation.severity != expected_severity
    ):
        raise AssertionAuditError("assertion_audit_duplicate_candidate_evaluation_invalid")
    for key, value in {
        "source_draft_id": str(source_input.source_artifact.id),
        "source_draft_hash": source_input.source_artifact.content_hash,
        "assertion_audit_artifact_id": str(artifact.id),
        "assertion_audit_hash": artifact.content_hash,
        **summary,
    }.items():
        if evaluation.findings_json.get(key) != value:
            raise AssertionAuditError("assertion_audit_duplicate_candidate_evaluation_stale")
    return _CompletedAuditCandidate(
        run=run,
        handoff=handoff,
        step=step,
        manifest=manifest,
        artifact=artifact,
        evaluation=evaluation,
        summary=summary,
        provider=model_provider,
        model=model_name,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )


async def prepare_assertion_audit_run(
    session: AsyncSession,
    *,
    source_input: AssertionAuditInput,
    task_key: str,
    prompt_version: str,
    recipe_version: str,
    provider: str | None = None,
    model: str | None = None,
) -> AssertionAuditRunContext:
    (
        audit_run,
        handoff,
        audit_run_reused,
        reusable_run_count,
        duplicate_run_ids,
        duplicate_recovery_used,
    ) = await ensure_assertion_audit_run(
        session,
        source_input=source_input,
        task_key=task_key,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
        provider=provider,
        model=model,
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
        reusable_run_count=reusable_run_count,
        duplicate_run_ids=duplicate_run_ids,
        duplicate_recovery_used=duplicate_recovery_used,
    )


__all__ = [
    "ASSERTION_AUDIT_HANDOFF_SCHEMA_VERSION",
    "AssertionAuditRunContext",
    "ensure_assertion_audit_run",
    "prepare_assertion_audit_run",
    "validate_source_writer_eligibility",
]
