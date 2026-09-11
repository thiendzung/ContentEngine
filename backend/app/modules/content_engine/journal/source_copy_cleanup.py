"""CE05 T05.15 deterministic English source-copy warning cleanup."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.source_copy import (
    SOURCE_COPY_EVALUATOR_KEY,
    SOURCE_COPY_EVALUATOR_VERSION,
    SOURCE_COPY_TASK_KEYS,
    SourceCopyCheck,
    SourceCopyError,
    SourceCopyFinding,
    SourceCopyInput,
    _fingerprint,
    _handoff_payload,
    _validate_handoff,
    load_source_copy_input,
)
from app.modules.content_engine.journal.source_copy import (
    _validate_persisted_artifact as _validate_source_copy_persisted_artifact,
)
from app.modules.content_engine.journal.writer import (
    JournalDraft,
    WriterGenerationError,
    WriterInput,
    _canonical_hash,
    _dict,
    _validate_model_output,
)
from app.modules.content_engine.models import ContentCase, NeedHypothesis, SettingsSnapshot
from app.modules.harness.models import Artifact, ContentRun, QualityEvaluation, StepRun

SOURCE_COPY_CLEANUP_GENERATOR_VERSION = "ce05.journal_source_copy_cleanup.v1"
SOURCE_COPY_CLEANUP_SCHEMA_VERSION = 1
SOURCE_COPY_CLEANUP_TASK_KEY = "source_copy_cleanup_en"
SOURCE_COPY_CLEANUP_SOURCE_COPY_TASK_KEY = SOURCE_COPY_TASK_KEYS["en"]
EXPECTED_CONTENT_CASE_ID = UUID("9ec6133b-5f14-46d0-9866-e3b049e537b5")
EXPECTED_NEED_HYPOTHESIS_ID = UUID("530bdd27-f008-4910-9b3b-df83e007cfa2")

TARGET_SEGMENT_ID = "section:understand-price-context:2"
TARGET_TEXT = "personal interests of both the seller and the purchaser"
REPLACEMENT_TEXT = "different priorities on each side of the transaction"
EXPECTED_SOURCE_TEXT_HASH = "8a02fb1b666d033f562770af5fd870781e1845449b4de3bd3cfebd3b10627eb8"


@dataclass(frozen=True, slots=True)
class SourceCopyCleanupInput:
    writer_input: WriterInput
    source_artifact: Artifact
    source_draft: JournalDraft
    assertion_audit_artifact: Artifact
    assertion_audit_evaluation: QualityEvaluation
    source_copy_input: SourceCopyInput
    source_copy_eval_run: ContentRun
    source_copy_handoff: Artifact
    source_copy_step: StepRun
    source_copy_artifact: Artifact
    source_copy_evaluation: QualityEvaluation
    warning: SourceCopyFinding


@dataclass(frozen=True, slots=True)
class SourceCopyCleanupResult:
    artifact: Artifact
    draft: JournalDraft
    model_attempts: int
    reused: bool


def _source_ref(artifact: Artifact) -> dict[str, object]:
    return {
        "id": str(artifact.id),
        "version": artifact.version,
        "content_hash": artifact.content_hash,
    }


def _bundle_refs(writer_input: WriterInput) -> tuple[dict[str, object], dict[str, object]]:
    bundle = writer_input.outline_input.bundle
    return (
        {
            "id": str(bundle.evidence_set_id),
            "version": bundle.evidence_set_version,
            "content_hash": bundle.evidence_set_hash,
        },
        {"id": str(bundle.originality_pack_id), "snapshot_hash": bundle.originality_pack_hash},
    )


def _visible_copy(draft: JournalDraft) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = [
        ("title", draft.title),
        ("standfirst", draft.standfirst),
        ("lead_markdown", draft.lead_markdown),
    ]
    for section in draft.sections:
        values.append((f"section:{section.section_id}:heading", section.heading))
        values.append((f"section:{section.section_id}:body_markdown", section.body_markdown))
    values.append(("closing_markdown", draft.closing_markdown))
    return tuple(values)


def _validate_target(draft: JournalDraft) -> None:
    target_sections = [
        section for section in draft.sections if section.section_id == "understand-price-context"
    ]
    if len(target_sections) != 1 or target_sections[0].body_markdown.count(TARGET_TEXT) != 1:
        raise WriterGenerationError("source_copy_cleanup_target_occurrence_mismatch")
    occurrences = sum(text.count(TARGET_TEXT) for _location, text in _visible_copy(draft))
    if occurrences != 1:
        raise WriterGenerationError("source_copy_cleanup_target_ambiguous")


def _expected_warning(check: SourceCopyCheck) -> SourceCopyFinding:
    if check.summary() != {
        "result": "warn",
        "finding_count": 1,
        "warn_count": 1,
        "fail_count": 0,
        "max_overlap_tokens": 9,
    }:
        raise WriterGenerationError("source_copy_cleanup_warning_summary_mismatch")
    if len(check.findings) != 1:
        raise WriterGenerationError("source_copy_cleanup_warning_count_mismatch")
    finding = check.findings[0]
    if (
        finding.locale != "en"
        or finding.draft_segment_id != TARGET_SEGMENT_ID
        or finding.draft_location != "section:understand-price-context"
        or finding.source_kind != "evidence_excerpt"
        or finding.source_ref != "evidence:5e97ed0d-8989-47d3-af4e-b2f29a5110cd"
        or finding.source_field != "evidence_excerpt"
        or finding.source_text_hash != EXPECTED_SOURCE_TEXT_HASH
        or finding.normalized_match != TARGET_TEXT
        or finding.overlap_token_count != 9
        or finding.classification != "warn"
    ):
        raise WriterGenerationError("source_copy_cleanup_warning_finding_mismatch")
    return finding


async def _load_source_copy_binding(
    session: AsyncSession,
    *,
    cleanup_input: SourceCopyInput,
    source_copy_eval_run_id: UUID,
    source_copy_handoff_id: UUID,
    source_copy_handoff_hash: str,
    source_copy_step_run_id: UUID,
    source_copy_artifact_id: UUID,
    source_copy_artifact_version: int,
    source_copy_artifact_hash: str,
    source_copy_quality_evaluation_id: UUID,
) -> tuple[ContentRun, Artifact, StepRun, Artifact, QualityEvaluation, SourceCopyFinding]:
    writer_run = cleanup_input.writer_input.writer_run
    eval_run = await session.get(ContentRun, source_copy_eval_run_id)
    if (
        eval_run is None
        or eval_run.run_mode != "eval"
        or eval_run.status != "completed"
        or eval_run.project_id != writer_run.project_id
        or eval_run.content_case_id != writer_run.content_case_id
        or eval_run.locale_variant_id != cleanup_input.writer_input.locale_variant.id
        or eval_run.content_item_id != writer_run.content_item_id
        or eval_run.settings_snapshot_id != writer_run.settings_snapshot_id
    ):
        raise WriterGenerationError("source_copy_cleanup_eval_run_mismatch")

    settings_snapshot = await session.get(SettingsSnapshot, writer_run.settings_snapshot_id)
    if settings_snapshot is None:
        raise WriterGenerationError("source_copy_cleanup_settings_snapshot_missing")

    handoff = await session.get(Artifact, source_copy_handoff_id)
    expected_handoff = _handoff_payload(
        source_input=cleanup_input,
        settings_snapshot=settings_snapshot,
        task_key=SOURCE_COPY_CLEANUP_SOURCE_COPY_TASK_KEY,
    )
    if handoff is None or handoff.content_hash != source_copy_handoff_hash:
        raise WriterGenerationError("source_copy_cleanup_handoff_snapshot_mismatch")
    try:
        _validate_handoff(
            handoff,
            payload=expected_handoff,
            source_input=cleanup_input,
            task_key=SOURCE_COPY_CLEANUP_SOURCE_COPY_TASK_KEY,
        )
    except SourceCopyError as exc:
        raise WriterGenerationError("source_copy_cleanup_handoff_invalid", str(exc)) from exc
    if handoff.run_id != eval_run.id:
        raise WriterGenerationError("source_copy_cleanup_handoff_run_mismatch")

    step = await session.get(StepRun, source_copy_step_run_id)
    input_refs = {
        str(handoff.id),
        str(cleanup_input.source_artifact.id),
        str(cleanup_input.assertion_audit_artifact.id),
        str(cleanup_input.writer_input.outline_artifact.id),
    }
    if (
        step is None
        or step.run_id != eval_run.id
        or step.step_key != SOURCE_COPY_CLEANUP_SOURCE_COPY_TASK_KEY
        or step.attempt != 1
        or step.status != "completed"
        or not input_refs.issubset(set(step.input_artifact_refs_json))
    ):
        raise WriterGenerationError("source_copy_cleanup_step_mismatch")

    artifact = await session.get(Artifact, source_copy_artifact_id)
    if (
        artifact is None
        or artifact.content_hash != source_copy_artifact_hash
        or artifact.version != source_copy_artifact_version
        or artifact.version != 1
        or artifact.run_id != eval_run.id
        or artifact.step_run_id != step.id
    ):
        raise WriterGenerationError("source_copy_cleanup_artifact_snapshot_mismatch")
    try:
        check = _validate_source_copy_persisted_artifact(
            artifact,
            source_input=cleanup_input,
            step=step,
            fingerprint=_fingerprint(
                cleanup_input,
                task_key=SOURCE_COPY_CLEANUP_SOURCE_COPY_TASK_KEY,
            ),
        )
    except SourceCopyError as exc:
        raise WriterGenerationError("source_copy_cleanup_artifact_invalid", str(exc)) from exc
    warning = _expected_warning(check)

    evaluation = await session.get(QualityEvaluation, source_copy_quality_evaluation_id)
    expected_findings = {
        "source_copy_artifact_id": str(artifact.id),
        "source_copy_artifact_hash": artifact.content_hash,
        **check.summary(),
    }
    if (
        evaluation is None
        or evaluation.run_id != eval_run.id
        or evaluation.artifact_id != artifact.id
        or evaluation.evaluator_key != SOURCE_COPY_EVALUATOR_KEY
        or evaluation.evaluator_version != SOURCE_COPY_EVALUATOR_VERSION
        or evaluation.evaluator_type != "deterministic"
        or evaluation.result != "warn"
        or evaluation.severity != "medium"
        or evaluation.findings_json != expected_findings
    ):
        raise WriterGenerationError("source_copy_cleanup_quality_evaluation_mismatch")
    return eval_run, handoff, step, artifact, evaluation, warning


async def load_source_copy_cleanup_input(
    session: AsyncSession,
    *,
    writer_run_id: UUID,
    source_draft_artifact_id: UUID,
    expected_source_draft_version: int,
    expected_source_draft_hash: str,
    assertion_audit_artifact_id: UUID,
    expected_assertion_audit_version: int,
    expected_assertion_audit_hash: str,
    assertion_audit_quality_evaluation_id: UUID,
    source_copy_eval_run_id: UUID,
    source_copy_handoff_id: UUID,
    source_copy_handoff_hash: str,
    source_copy_step_run_id: UUID,
    source_copy_artifact_id: UUID,
    source_copy_artifact_version: int,
    source_copy_artifact_hash: str,
    source_copy_quality_evaluation_id: UUID,
    outline_artifact_id: UUID,
    expected_outline_version: int,
    expected_outline_hash: str,
) -> SourceCopyCleanupInput:
    source_copy_input = await load_source_copy_input(
        session,
        writer_run_id=writer_run_id,
        source_draft_artifact_id=source_draft_artifact_id,
        expected_source_draft_version=expected_source_draft_version,
        expected_source_draft_hash=expected_source_draft_hash,
        assertion_audit_artifact_id=assertion_audit_artifact_id,
        expected_assertion_audit_version=expected_assertion_audit_version,
        expected_assertion_audit_hash=expected_assertion_audit_hash,
        assertion_audit_quality_evaluation_id=assertion_audit_quality_evaluation_id,
        outline_artifact_id=outline_artifact_id,
        expected_outline_version=expected_outline_version,
        expected_outline_hash=expected_outline_hash,
        locale="en",
    )
    writer_input = source_copy_input.writer_input
    if writer_input.writer_run.content_case_id != EXPECTED_CONTENT_CASE_ID:
        raise WriterGenerationError("source_copy_cleanup_content_case_mismatch")
    content_case = await session.get(ContentCase, EXPECTED_CONTENT_CASE_ID)
    if (
        content_case is None
        or content_case.need_hypothesis_id != EXPECTED_NEED_HYPOTHESIS_ID
    ):
        raise WriterGenerationError("source_copy_cleanup_need_hypothesis_binding_mismatch")
    need_hypothesis = await session.get(NeedHypothesis, EXPECTED_NEED_HYPOTHESIS_ID)
    if need_hypothesis is None or need_hypothesis.status != "PROPOSED":
        raise WriterGenerationError("source_copy_cleanup_need_hypothesis_status_mismatch")
    if writer_input.writer_run.status != "waiting_approval":
        raise WriterGenerationError(
            "source_copy_cleanup_writer_run_state_invalid", writer_input.writer_run.status
        )
    if source_copy_input.source_artifact.version != 4:
        raise WriterGenerationError("source_copy_cleanup_source_draft_version_invalid")
    _validate_target(source_copy_input.source_draft)
    eval_run, handoff, step, artifact, evaluation, warning = await _load_source_copy_binding(
        session,
        cleanup_input=source_copy_input,
        source_copy_eval_run_id=source_copy_eval_run_id,
        source_copy_handoff_id=source_copy_handoff_id,
        source_copy_handoff_hash=source_copy_handoff_hash,
        source_copy_step_run_id=source_copy_step_run_id,
        source_copy_artifact_id=source_copy_artifact_id,
        source_copy_artifact_version=source_copy_artifact_version,
        source_copy_artifact_hash=source_copy_artifact_hash,
        source_copy_quality_evaluation_id=source_copy_quality_evaluation_id,
    )
    return SourceCopyCleanupInput(
        writer_input=writer_input,
        source_artifact=source_copy_input.source_artifact,
        source_draft=source_copy_input.source_draft,
        assertion_audit_artifact=source_copy_input.assertion_audit_artifact,
        assertion_audit_evaluation=source_copy_input.assertion_audit_evaluation,
        source_copy_input=source_copy_input,
        source_copy_eval_run=eval_run,
        source_copy_handoff=handoff,
        source_copy_step=step,
        source_copy_artifact=artifact,
        source_copy_evaluation=evaluation,
        warning=warning,
    )


def _cleanup_fingerprint(cleanup_input: SourceCopyCleanupInput) -> str:
    return _canonical_hash(
        {
            "operation": "replace_exact_source_copy_warning",
            "task_key": SOURCE_COPY_CLEANUP_TASK_KEY,
            "writer_run_id": str(cleanup_input.writer_input.writer_run.id),
            "source_draft": _source_ref(cleanup_input.source_artifact),
            "assertion_audit": _source_ref(cleanup_input.assertion_audit_artifact),
            "assertion_audit_quality_evaluation_id": str(
                cleanup_input.assertion_audit_evaluation.id
            ),
            "source_copy_eval_run_id": str(cleanup_input.source_copy_eval_run.id),
            "source_copy_handoff": _source_ref(cleanup_input.source_copy_handoff),
            "source_copy_step_run_id": str(cleanup_input.source_copy_step.id),
            "source_copy_artifact": _source_ref(cleanup_input.source_copy_artifact),
            "source_copy_quality_evaluation_id": str(cleanup_input.source_copy_evaluation.id),
            "warning": cleanup_input.warning.to_dict(),
            "target_segment_id": TARGET_SEGMENT_ID,
            "target_text": TARGET_TEXT,
            "replacement_text": REPLACEMENT_TEXT,
            "generator_version": SOURCE_COPY_CLEANUP_GENERATOR_VERSION,
            "schema_version": SOURCE_COPY_CLEANUP_SCHEMA_VERSION,
        }
    )


def _cleanup_draft(cleanup_input: SourceCopyCleanupInput) -> JournalDraft:
    _validate_target(cleanup_input.source_draft)
    source_payload = cleanup_input.source_draft.to_dict()
    payload = copy.deepcopy(source_payload)
    raw_sections = payload.get("sections")
    if not isinstance(raw_sections, list):
        raise WriterGenerationError("source_copy_cleanup_sections_invalid")
    changed = 0
    for raw_section in raw_sections:
        if not isinstance(raw_section, dict):
            raise WriterGenerationError("source_copy_cleanup_section_invalid")
        if raw_section.get("section_id") != "understand-price-context":
            continue
        body = raw_section.get("body_markdown")
        if not isinstance(body, str) or body.count(TARGET_TEXT) != 1:
            raise WriterGenerationError("source_copy_cleanup_target_occurrence_mismatch")
        raw_section["body_markdown"] = body.replace(TARGET_TEXT, REPLACEMENT_TEXT, 1)
        changed += 1
    if changed != 1:
        raise WriterGenerationError("source_copy_cleanup_target_section_mismatch")
    draft = _validate_model_output(payload, writer_input=cleanup_input.writer_input)
    if draft.to_dict() != payload:
        raise WriterGenerationError("source_copy_cleanup_output_snapshot_stale")
    for key, value in source_payload.items():
        if key != "sections" and draft.to_dict()[key] != value:
            raise WriterGenerationError("source_copy_cleanup_non_target_copy_changed", key)
    for source_section, result_section in zip(
        cast(list[dict[str, object]], source_payload["sections"]),
        cast(list[dict[str, object]], payload["sections"]),
        strict=True,
    ):
        for key, value in source_section.items():
            if (
                source_section.get("section_id") == "understand-price-context"
                and key == "body_markdown"
            ):
                if not isinstance(value, str):
                    raise WriterGenerationError("source_copy_cleanup_target_body_invalid")
                expected = value.replace(TARGET_TEXT, REPLACEMENT_TEXT, 1)
                if result_section.get(key) != expected:
                    raise WriterGenerationError("source_copy_cleanup_target_replacement_mismatch")
            elif result_section.get(key) != value:
                raise WriterGenerationError("source_copy_cleanup_non_target_copy_changed", key)
    return draft


def _cleanup_payload(
    cleanup_input: SourceCopyCleanupInput,
    *,
    draft: JournalDraft,
    step: StepRun,
    fingerprint: str,
) -> dict[str, object]:
    evidence_ref, originality_ref = _bundle_refs(cleanup_input.writer_input)
    return {
        "schema_version": SOURCE_COPY_CLEANUP_SCHEMA_VERSION,
        "artifact_type": "journal_draft",
        "locale": "en",
        "generation_fingerprint": fingerprint,
        "writer_handoff": {
            "id": str(cleanup_input.writer_input.handoff_artifact.id),
            "content_hash": cleanup_input.writer_input.handoff_artifact.content_hash,
            "source_run_id": str(cleanup_input.writer_input.outline_artifact.run_id),
            "writer_run_id": str(cleanup_input.writer_input.writer_run.id),
            "locale_variant_id": str(cleanup_input.writer_input.locale_variant.id),
        },
        "journal_outline": _source_ref(cleanup_input.writer_input.outline_artifact),
        "evidence_set": evidence_ref,
        "originality_pack": originality_ref,
        "settings_snapshot": {
            "id": str(cleanup_input.writer_input.writer_run.settings_snapshot_id),
            "content_hash": cleanup_input.source_copy_input.settings_snapshot_hash,
        },
        "source_copy_warning": {
            "eval_run_id": str(cleanup_input.source_copy_eval_run.id),
            "handoff": _source_ref(cleanup_input.source_copy_handoff),
            "step_run": {
                "id": str(cleanup_input.source_copy_step.id),
                "attempt": cleanup_input.source_copy_step.attempt,
            },
            "artifact": _source_ref(cleanup_input.source_copy_artifact),
            "quality_evaluation": {
                "id": str(cleanup_input.source_copy_evaluation.id),
                "evaluator_key": cleanup_input.source_copy_evaluation.evaluator_key,
                "evaluator_version": cleanup_input.source_copy_evaluation.evaluator_version,
                "result": cleanup_input.source_copy_evaluation.result,
            },
            "finding": cleanup_input.warning.to_dict(),
        },
        "cleanup": {
            "mode": "deterministic_exact_substring_replacement",
            "segment_id": TARGET_SEGMENT_ID,
            "target_text": TARGET_TEXT,
            "replacement_text": REPLACEMENT_TEXT,
        },
        "execution_context": {"step_run_id": str(step.id)},
        "generator": {
            "version": SOURCE_COPY_CLEANUP_GENERATOR_VERSION,
            "schema_version": SOURCE_COPY_CLEANUP_SCHEMA_VERSION,
        },
        "model_calls": 0,
        "provider_calls": 0,
        "tool_calls": 0,
        "draft": draft.to_dict(),
    }


def _validate_persisted_artifact(
    artifact: Artifact,
    *,
    cleanup_input: SourceCopyCleanupInput,
    step: StepRun,
    fingerprint: str,
) -> JournalDraft:
    if (
        artifact.artifact_type != "journal_draft"
        or artifact.locale != "en"
        or artifact.run_id != cleanup_input.writer_input.writer_run.id
        or artifact.step_run_id != step.id
        or artifact.version != cleanup_input.source_artifact.version + 1
    ):
        raise WriterGenerationError("source_copy_cleanup_artifact_binding_mismatch")
    payload = _dict(artifact.content_json, "source_copy_cleanup_artifact_payload_invalid")
    if _canonical_hash(payload) != artifact.content_hash:
        raise WriterGenerationError("source_copy_cleanup_artifact_snapshot_stale")
    draft_payload = _dict(payload.get("draft"), "source_copy_cleanup_draft_payload_invalid")
    draft = _validate_model_output(draft_payload, writer_input=cleanup_input.writer_input)
    if draft.to_dict() != draft_payload:
        raise WriterGenerationError("source_copy_cleanup_draft_payload_stale")
    expected_draft = _cleanup_draft(cleanup_input)
    if draft.to_dict() != expected_draft.to_dict():
        raise WriterGenerationError("source_copy_cleanup_draft_result_mismatch")
    expected_payload = _cleanup_payload(
        cleanup_input,
        draft=draft,
        step=step,
        fingerprint=fingerprint,
    )
    if payload != expected_payload:
        raise WriterGenerationError("source_copy_cleanup_artifact_provenance_mismatch")
    return draft


async def _existing_cleanup(
    session: AsyncSession,
    *,
    cleanup_input: SourceCopyCleanupInput,
    step: StepRun,
    fingerprint: str,
) -> SourceCopyCleanupResult | None:
    artifacts = list(
        (
            await session.scalars(
                select(Artifact)
                .where(
                    Artifact.run_id == cleanup_input.writer_input.writer_run.id,
                    Artifact.artifact_type == "journal_draft",
                    Artifact.locale == "en",
                )
                .order_by(Artifact.version)
            )
        ).all()
    )
    matching = [
        artifact
        for artifact in artifacts
        if isinstance(artifact.content_json, dict)
        and artifact.content_json.get("generation_fingerprint") == fingerprint
    ]
    if not matching:
        return None
    if len(matching) != 1 or step.status != "completed":
        raise WriterGenerationError("source_copy_cleanup_completed_step_required")
    draft = _validate_persisted_artifact(
        matching[0], cleanup_input=cleanup_input, step=step, fingerprint=fingerprint
    )
    return SourceCopyCleanupResult(
        artifact=matching[0], draft=draft, model_attempts=0, reused=True
    )


async def _persist_cleanup(
    session: AsyncSession,
    *,
    cleanup_input: SourceCopyCleanupInput,
    draft: JournalDraft,
    step: StepRun,
    fingerprint: str,
) -> Artifact:
    if step.status != "running":
        raise WriterGenerationError("source_copy_cleanup_step_state_invalid")
    latest = await session.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.run_id == cleanup_input.writer_input.writer_run.id,
            Artifact.artifact_type == "journal_draft",
        )
    )
    if latest != cleanup_input.source_artifact.version:
        raise WriterGenerationError("source_copy_cleanup_next_version_conflict")
    payload = _cleanup_payload(
        cleanup_input, draft=draft, step=step, fingerprint=fingerprint
    )
    artifact = Artifact(
        run_id=cleanup_input.writer_input.writer_run.id,
        step_run_id=step.id,
        artifact_type="journal_draft",
        locale="en",
        version=cleanup_input.source_artifact.version + 1,
        content_json=payload,
        content_hash=_canonical_hash(payload),
    )
    session.add(artifact)
    await session.flush()
    if str(artifact.id) not in step.output_artifact_refs_json:
        step.output_artifact_refs_json = [*step.output_artifact_refs_json, str(artifact.id)]
        await session.flush()
    return artifact


class SourceCopyCleanupGenerator:
    """Replace one exact EN source-copy warning without invoking a model."""

    async def cleanup_draft(
        self,
        session: AsyncSession,
        *,
        cleanup_input: SourceCopyCleanupInput,
        step_run_id: UUID,
    ) -> SourceCopyCleanupResult:
        run = cleanup_input.writer_input.writer_run
        if run.status in {"completed", "failed", "cancelled"}:
            raise WriterGenerationError("source_copy_cleanup_writer_run_state_invalid")
        step = await session.get(StepRun, step_run_id)
        if (
            step is None
            or step.run_id != run.id
            or step.step_key != SOURCE_COPY_CLEANUP_TASK_KEY
        ):
            raise WriterGenerationError("source_copy_cleanup_step_ownership_mismatch")
        fingerprint = _cleanup_fingerprint(cleanup_input)
        existing = await _existing_cleanup(
            session,
            cleanup_input=cleanup_input,
            step=step,
            fingerprint=fingerprint,
        )
        if existing is not None:
            if run.status != "waiting_approval":
                raise WriterGenerationError("source_copy_cleanup_writer_run_state_invalid")
            return existing
        if run.status != "running" or step.status != "running":
            raise WriterGenerationError("source_copy_cleanup_generation_state_invalid")
        draft = _cleanup_draft(cleanup_input)
        artifact = await _persist_cleanup(
            session,
            cleanup_input=cleanup_input,
            draft=draft,
            step=step,
            fingerprint=fingerprint,
        )
        return SourceCopyCleanupResult(
            artifact=artifact, draft=draft, model_attempts=0, reused=False
        )


__all__ = [
    "EXPECTED_SOURCE_TEXT_HASH",
    "EXPECTED_CONTENT_CASE_ID",
    "EXPECTED_NEED_HYPOTHESIS_ID",
    "REPLACEMENT_TEXT",
    "SOURCE_COPY_CLEANUP_GENERATOR_VERSION",
    "SOURCE_COPY_CLEANUP_SCHEMA_VERSION",
    "SOURCE_COPY_CLEANUP_TASK_KEY",
    "TARGET_SEGMENT_ID",
    "TARGET_TEXT",
    "SourceCopyCleanupGenerator",
    "SourceCopyCleanupInput",
    "SourceCopyCleanupResult",
    "load_source_copy_cleanup_input",
]
