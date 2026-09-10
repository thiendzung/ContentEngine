"""CE05 T05.14 deterministic English post-audit closing cleanup."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.assertion_audit import (
    ASSERTION_AUDIT_EVALUATOR_KEY,
    ASSERTION_AUDIT_EVALUATOR_VERSION,
    ASSERTION_AUDIT_GENERATOR_VERSION,
    AssertionAuditError,
    _summary,
    load_assertion_audit_input,
    validate_assertion_audit_output,
)
from app.modules.content_engine.journal.review_revise import (
    ReviewReviseInput,
    load_review_revise_input,
)
from app.modules.content_engine.journal.writer import (
    JournalDraft,
    WriterGenerationError,
    WriterInput,
    _canonical_hash,
    _dict,
    _validate_model_output,
)
from app.modules.harness.models import Artifact, ContentRun, QualityEvaluation, StepRun

POST_AUDIT_CLEANUP_GENERATOR_VERSION = "ce05.journal_post_audit_cleanup.v1"
POST_AUDIT_CLEANUP_SCHEMA_VERSION = 1
POST_AUDIT_CLEANUP_TASK_KEY = "post_audit_cleanup_en"

CLOSING_SEGMENT_ID = "closing:3"
CLOSING_SENTENCE_TO_REMOVE = (
    "There is nothing formal about asking for a clearer answer."
)
SOURCE_CLOSING_MARKDOWN = (
    "Take your time. If anything is unclear, ask before deciding. "
    "There is nothing formal about asking for a clearer answer."
)
RESULT_CLOSING_MARKDOWN = "Take your time. If anything is unclear, ask before deciding."


@dataclass(frozen=True, slots=True)
class PostAuditCleanupInput:
    review_input: ReviewReviseInput
    failed_audit_artifact: Artifact
    failed_quality_evaluation: QualityEvaluation
    finding: dict[str, object]

    @property
    def writer_input(self) -> WriterInput:
        return self.review_input.writer_input

    @property
    def source_artifact(self) -> Artifact:
        return self.review_input.source_artifact

    @property
    def source_draft(self) -> JournalDraft:
        return self.review_input.source_draft


@dataclass(frozen=True, slots=True)
class PostAuditCleanupResult:
    artifact: Artifact
    draft: JournalDraft
    model_attempts: int
    reused: bool


def _ref(payload: dict[str, object], key: str, code: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise WriterGenerationError(code)
    return cast(dict[str, object], value)


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
        {
            "id": str(bundle.originality_pack_id),
            "snapshot_hash": bundle.originality_pack_hash,
        },
    )


async def _load_failed_audit(
    session: AsyncSession,
    *,
    cleanup_input: ReviewReviseInput,
    audit_artifact_id: UUID,
    expected_audit_version: int,
    expected_audit_hash: str,
    quality_evaluation_id: UUID,
) -> tuple[Artifact, QualityEvaluation, dict[str, object]]:
    source = cleanup_input.source_artifact
    writer_input = cleanup_input.writer_input
    audit = await session.get(Artifact, audit_artifact_id)
    if audit is None or audit.artifact_type != "assertion_audit":
        raise WriterGenerationError("post_audit_cleanup_failed_audit_not_found")
    if (
        audit.version != expected_audit_version
        or audit.content_hash != expected_audit_hash
        or audit.version != 1
        or audit.locale != "en"
        or audit.run_id == writer_input.writer_run.id
    ):
        raise WriterGenerationError("post_audit_cleanup_failed_audit_snapshot_mismatch")
    audit_run = await session.get(ContentRun, audit.run_id)
    writer_run = writer_input.writer_run
    if (
        audit_run is None
        or audit_run.run_mode != "eval"
        or audit_run.status != "completed"
        or audit_run.project_id != writer_run.project_id
        or audit_run.content_case_id != writer_run.content_case_id
        or audit_run.locale_variant_id != writer_input.locale_variant.id
        or audit_run.settings_snapshot_id != writer_run.settings_snapshot_id
    ):
        raise WriterGenerationError("post_audit_cleanup_failed_audit_run_invalid")

    payload = _dict(audit.content_json, "post_audit_cleanup_failed_audit_payload_invalid")
    if _canonical_hash(payload) != audit.content_hash:
        raise WriterGenerationError("post_audit_cleanup_failed_audit_snapshot_stale")
    if payload.get("artifact_type") != "assertion_audit" or payload.get("locale") != "en":
        raise WriterGenerationError("post_audit_cleanup_failed_audit_payload_invalid")
    generator = _ref(
        payload,
        "generator",
        "post_audit_cleanup_failed_audit_generator_invalid",
    )
    if (
        generator.get("version") != ASSERTION_AUDIT_GENERATOR_VERSION
        or generator.get("schema_version") != 1
    ):
        raise WriterGenerationError("post_audit_cleanup_failed_audit_generator_mismatch")
    expected_source = _source_ref(source)
    if (
        _ref(payload, "source_draft", "post_audit_cleanup_failed_audit_source_invalid")
        != expected_source
        or payload.get("source_writer_run_id") != str(writer_run.id)
    ):
        raise WriterGenerationError("post_audit_cleanup_failed_audit_source_mismatch")
    expected_outline = _source_ref(writer_input.outline_artifact)
    if (
        _ref(payload, "journal_outline", "post_audit_cleanup_failed_audit_outline_invalid")
        != expected_outline
    ):
        raise WriterGenerationError("post_audit_cleanup_failed_audit_outline_mismatch")
    evidence_ref, originality_ref = _bundle_refs(writer_input)
    if (
        _ref(payload, "evidence_set", "post_audit_cleanup_failed_audit_evidence_invalid")
        != evidence_ref
        or _ref(
            payload,
            "originality_pack",
            "post_audit_cleanup_failed_audit_originality_invalid",
        )
        != originality_ref
    ):
        raise WriterGenerationError("post_audit_cleanup_failed_audit_upstream_mismatch")

    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list):
        raise WriterGenerationError("post_audit_cleanup_failed_audit_segments_invalid")
    try:
        audit_input = await load_assertion_audit_input(
            session,
            writer_run_id=writer_run.id,
            revised_draft_artifact_id=source.id,
            expected_revised_draft_version=source.version,
            expected_revised_draft_hash=source.content_hash,
            outline_artifact_id=writer_input.outline_artifact.id,
            expected_outline_version=writer_input.outline_artifact.version,
            expected_outline_hash=writer_input.outline_artifact.content_hash,
            locale="en",
        )
        audited_segments = validate_assertion_audit_output(
            {"locale": "en", "segments": raw_segments},
            audit_input=audit_input,
        )
    except (AssertionAuditError, WriterGenerationError) as exc:
        raise WriterGenerationError(
            "post_audit_cleanup_failed_audit_content_invalid",
            str(exc),
        ) from exc
    summary = _summary(audited_segments)
    if payload.get("summary") != summary:
        raise WriterGenerationError("post_audit_cleanup_failed_audit_summary_stale")
    if summary != {
        "result": "fail",
        "assertion_count": summary["assertion_count"],
        "critical_unsupported_count": 1,
        "critical_contradicted_count": 0,
        "unsupported_count": 1,
        "contradicted_count": 0,
    }:
        raise WriterGenerationError("post_audit_cleanup_failed_audit_summary_mismatch")

    findings: list[dict[str, object]] = []
    for segment in audited_segments:
        for assertion in segment.assertions:
            if assertion.support_status in {"unsupported", "contradicted"}:
                findings.append(
                    {
                        "segment_id": segment.segment_id,
                        "assertion_text": assertion.assertion_text,
                        "assertion_type": assertion.assertion_type,
                        "support_status": assertion.support_status,
                        "severity": assertion.severity,
                        "evidence_refs": list(assertion.evidence_refs),
                        "originality_refs": list(assertion.originality_refs),
                        "claim_refs": list(assertion.claim_refs),
                    }
                )
    if len(findings) != 1 or findings[0] != {
        "segment_id": CLOSING_SEGMENT_ID,
        "assertion_text": CLOSING_SENTENCE_TO_REMOVE,
        "assertion_type": "brand_statement",
        "support_status": "unsupported",
        "severity": "critical",
        "evidence_refs": [],
        "originality_refs": [],
        "claim_refs": [],
    }:
        raise WriterGenerationError("post_audit_cleanup_failed_audit_finding_mismatch")

    evaluation = await session.get(QualityEvaluation, quality_evaluation_id)
    if evaluation is None:
        raise WriterGenerationError("post_audit_cleanup_quality_evaluation_not_found")
    if (
        evaluation.run_id != audit.run_id
        or evaluation.artifact_id != audit.id
        or evaluation.evaluator_key != ASSERTION_AUDIT_EVALUATOR_KEY
        or evaluation.evaluator_version != ASSERTION_AUDIT_EVALUATOR_VERSION
        or evaluation.evaluator_type != "deterministic"
        or evaluation.result != "fail"
        or evaluation.severity != "critical"
    ):
        raise WriterGenerationError("post_audit_cleanup_quality_evaluation_mismatch")
    expected_findings = {
        "source_draft_id": str(source.id),
        "source_draft_hash": source.content_hash,
        "assertion_audit_artifact_id": str(audit.id),
        "assertion_audit_hash": audit.content_hash,
        **summary,
    }
    if evaluation.findings_json != expected_findings:
        raise WriterGenerationError("post_audit_cleanup_quality_evaluation_snapshot_mismatch")
    return audit, evaluation, findings[0]


async def load_post_audit_cleanup_input(
    session: AsyncSession,
    *,
    writer_run_id: UUID,
    source_draft_artifact_id: UUID,
    expected_source_draft_version: int,
    expected_source_draft_hash: str,
    failed_audit_artifact_id: UUID,
    expected_failed_audit_version: int,
    expected_failed_audit_hash: str,
    failed_quality_evaluation_id: UUID,
    outline_artifact_id: UUID,
    expected_outline_version: int,
    expected_outline_hash: str,
) -> PostAuditCleanupInput:
    review_input = await load_review_revise_input(
        session,
        writer_run_id=writer_run_id,
        source_draft_artifact_id=source_draft_artifact_id,
        expected_source_draft_version=expected_source_draft_version,
        expected_source_draft_hash=expected_source_draft_hash,
        outline_artifact_id=outline_artifact_id,
        expected_outline_version=expected_outline_version,
        expected_outline_hash=expected_outline_hash,
        locale="en",
    )
    if review_input.writer_input.writer_run.status != "waiting_approval":
        raise WriterGenerationError(
            "post_audit_cleanup_writer_run_state_invalid",
            review_input.writer_input.writer_run.status,
        )
    if review_input.source_artifact.version != 3:
        raise WriterGenerationError("post_audit_cleanup_source_draft_version_invalid")
    if review_input.source_draft.closing_markdown != SOURCE_CLOSING_MARKDOWN:
        raise WriterGenerationError("post_audit_cleanup_source_closing_mismatch")
    audit, evaluation, finding = await _load_failed_audit(
        session,
        cleanup_input=review_input,
        audit_artifact_id=failed_audit_artifact_id,
        expected_audit_version=expected_failed_audit_version,
        expected_audit_hash=expected_failed_audit_hash,
        quality_evaluation_id=failed_quality_evaluation_id,
    )
    return PostAuditCleanupInput(
        review_input=review_input,
        failed_audit_artifact=audit,
        failed_quality_evaluation=evaluation,
        finding=finding,
    )


def _cleanup_fingerprint(cleanup_input: PostAuditCleanupInput) -> str:
    return _canonical_hash(
        {
            "operation": "remove_exact_sentence",
            "writer_run_id": str(cleanup_input.writer_input.writer_run.id),
            "source_draft": _source_ref(cleanup_input.source_artifact),
            "failed_assertion_audit": _source_ref(cleanup_input.failed_audit_artifact),
            "failed_quality_evaluation_id": str(cleanup_input.failed_quality_evaluation.id),
            "finding": cleanup_input.finding,
            "removed_segment_id": CLOSING_SEGMENT_ID,
            "removed_segment_text": CLOSING_SENTENCE_TO_REMOVE,
            "generator_version": POST_AUDIT_CLEANUP_GENERATOR_VERSION,
            "schema_version": POST_AUDIT_CLEANUP_SCHEMA_VERSION,
        }
    )


def _cleanup_draft(cleanup_input: PostAuditCleanupInput) -> JournalDraft:
    source = cleanup_input.source_draft
    if source.closing_markdown != SOURCE_CLOSING_MARKDOWN:
        raise WriterGenerationError("post_audit_cleanup_source_closing_mismatch")
    payload = copy.deepcopy(source.to_dict())
    closing = cast(str, payload["closing_markdown"])
    removable = f" {CLOSING_SENTENCE_TO_REMOVE}"
    if not closing.endswith(removable) or closing.count(removable) != 1:
        raise WriterGenerationError("post_audit_cleanup_removable_sentence_mismatch")
    payload["closing_markdown"] = closing[: -len(removable)]
    try:
        draft = _validate_model_output(payload, writer_input=cleanup_input.writer_input)
    except WriterGenerationError:
        raise
    if draft.to_dict() != payload:
        raise WriterGenerationError("post_audit_cleanup_output_snapshot_stale")
    for key, value in source.to_dict().items():
        if key != "closing_markdown" and draft.to_dict()[key] != value:
            raise WriterGenerationError("post_audit_cleanup_non_target_copy_changed", key)
    if draft.closing_markdown != RESULT_CLOSING_MARKDOWN:
        raise WriterGenerationError("post_audit_cleanup_result_closing_mismatch")
    return draft


def _cleanup_payload(
    cleanup_input: PostAuditCleanupInput,
    *,
    draft: JournalDraft,
    step: StepRun,
    fingerprint: str,
) -> dict[str, object]:
    writer_input = cleanup_input.writer_input
    evidence_ref, originality_ref = _bundle_refs(writer_input)
    return {
        "schema_version": POST_AUDIT_CLEANUP_SCHEMA_VERSION,
        "artifact_type": "journal_draft",
        "locale": "en",
        "generation_fingerprint": fingerprint,
        "writer_handoff": {
            "id": str(writer_input.handoff_artifact.id),
            "content_hash": writer_input.handoff_artifact.content_hash,
            "source_run_id": str(writer_input.outline_artifact.run_id),
            "writer_run_id": str(writer_input.writer_run.id),
            "locale_variant_id": str(writer_input.locale_variant.id),
        },
        "journal_outline": _source_ref(writer_input.outline_artifact),
        "evidence_set": evidence_ref,
        "originality_pack": originality_ref,
        "post_audit_cleanup": {
            "source_draft": _source_ref(cleanup_input.source_artifact),
            "failed_assertion_audit": _source_ref(cleanup_input.failed_audit_artifact),
            "failed_quality_evaluation": {
                "id": str(cleanup_input.failed_quality_evaluation.id),
                "evaluator_key": cleanup_input.failed_quality_evaluation.evaluator_key,
                "evaluator_version": cleanup_input.failed_quality_evaluation.evaluator_version,
                "result": cleanup_input.failed_quality_evaluation.result,
            },
            "finding": cleanup_input.finding,
            "removed_segment_id": CLOSING_SEGMENT_ID,
            "removed_segment_text": CLOSING_SENTENCE_TO_REMOVE,
            "source_closing_markdown": SOURCE_CLOSING_MARKDOWN,
            "result_closing_markdown": RESULT_CLOSING_MARKDOWN,
            "mode": "deterministic_exact_sentence_deletion",
        },
        "execution_context": {
            "step_run_id": str(step.id),
            "settings_snapshot_id": str(writer_input.writer_run.settings_snapshot_id),
        },
        "generator": {
            "version": POST_AUDIT_CLEANUP_GENERATOR_VERSION,
            "schema_version": POST_AUDIT_CLEANUP_SCHEMA_VERSION,
        },
        "model_calls": 0,
        "provider_calls": 0,
        "tool_calls": 0,
        "draft": draft.to_dict(),
    }


def _validate_persisted_artifact(
    artifact: Artifact,
    *,
    cleanup_input: PostAuditCleanupInput,
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
        raise WriterGenerationError("post_audit_cleanup_artifact_binding_mismatch")
    payload = _dict(artifact.content_json, "post_audit_cleanup_artifact_payload_invalid")
    if payload.get("generation_fingerprint") != fingerprint:
        raise WriterGenerationError("post_audit_cleanup_artifact_fingerprint_mismatch")
    if _canonical_hash(payload) != artifact.content_hash:
        raise WriterGenerationError("post_audit_cleanup_artifact_snapshot_stale")
    draft_payload = _dict(payload.get("draft"), "post_audit_cleanup_draft_payload_invalid")
    draft = _validate_model_output(draft_payload, writer_input=cleanup_input.writer_input)
    if draft.to_dict() != draft_payload:
        raise WriterGenerationError("post_audit_cleanup_draft_payload_stale")
    if draft.closing_markdown != RESULT_CLOSING_MARKDOWN:
        raise WriterGenerationError("post_audit_cleanup_result_closing_mismatch")
    cleanup_meta = _dict(
        payload.get("post_audit_cleanup"),
        "post_audit_cleanup_metadata_invalid",
    )
    if (
        cleanup_meta.get("source_draft") != _source_ref(cleanup_input.source_artifact)
        or cleanup_meta.get("failed_assertion_audit")
        != _source_ref(cleanup_input.failed_audit_artifact)
        or cleanup_meta.get("removed_segment_id") != CLOSING_SEGMENT_ID
        or cleanup_meta.get("removed_segment_text") != CLOSING_SENTENCE_TO_REMOVE
        or cleanup_meta.get("source_closing_markdown") != SOURCE_CLOSING_MARKDOWN
        or cleanup_meta.get("result_closing_markdown") != RESULT_CLOSING_MARKDOWN
        or payload.get("model_calls") != 0
        or payload.get("provider_calls") != 0
        or payload.get("tool_calls") != 0
        or "prompt_version" in payload
        or "recipe_version" in payload
        or "context_manifest_id" in payload
    ):
        raise WriterGenerationError("post_audit_cleanup_artifact_metadata_mismatch")
    for key, value in cleanup_input.source_draft.to_dict().items():
        if key != "closing_markdown" and draft.to_dict()[key] != value:
            raise WriterGenerationError("post_audit_cleanup_non_target_copy_changed", key)
    return draft


async def _existing_cleanup(
    session: AsyncSession,
    *,
    cleanup_input: PostAuditCleanupInput,
    step: StepRun,
    fingerprint: str,
) -> PostAuditCleanupResult | None:
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
    if len(matching) != 1:
        raise WriterGenerationError("post_audit_cleanup_artifact_duplicate")
    if step.status != "completed":
        raise WriterGenerationError("post_audit_cleanup_completed_step_required")
    draft = _validate_persisted_artifact(
        matching[0],
        cleanup_input=cleanup_input,
        step=step,
        fingerprint=fingerprint,
    )
    return PostAuditCleanupResult(
        artifact=matching[0],
        draft=draft,
        model_attempts=0,
        reused=True,
    )


async def _persist_cleanup(
    session: AsyncSession,
    *,
    cleanup_input: PostAuditCleanupInput,
    draft: JournalDraft,
    step: StepRun,
    fingerprint: str,
) -> Artifact:
    if step.status != "running":
        raise WriterGenerationError("post_audit_cleanup_step_state_invalid")
    latest = await session.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.run_id == cleanup_input.writer_input.writer_run.id,
            Artifact.artifact_type == "journal_draft",
        )
    )
    if latest != cleanup_input.source_artifact.version:
        raise WriterGenerationError("post_audit_cleanup_next_version_conflict")
    payload = _cleanup_payload(
        cleanup_input,
        draft=draft,
        step=step,
        fingerprint=fingerprint,
    )
    content_hash = _canonical_hash(payload)
    artifact = Artifact(
        run_id=cleanup_input.writer_input.writer_run.id,
        step_run_id=step.id,
        artifact_type="journal_draft",
        locale="en",
        version=cleanup_input.source_artifact.version + 1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    if str(artifact.id) not in step.output_artifact_refs_json:
        step.output_artifact_refs_json = [*step.output_artifact_refs_json, str(artifact.id)]
        await session.flush()
    return artifact


class PostAuditCleanupGenerator:
    """Delete one locked unsupported closing sentence without invoking a model."""

    async def cleanup_draft(
        self,
        session: AsyncSession,
        *,
        cleanup_input: PostAuditCleanupInput,
        step_run_id: UUID,
    ) -> PostAuditCleanupResult:
        run = cleanup_input.writer_input.writer_run
        if run.status in {"completed", "failed", "cancelled"}:
            raise WriterGenerationError("post_audit_cleanup_writer_run_state_invalid")
        step = await session.get(StepRun, step_run_id)
        if (
            step is None
            or step.run_id != run.id
            or step.step_key != POST_AUDIT_CLEANUP_TASK_KEY
        ):
            raise WriterGenerationError("post_audit_cleanup_step_ownership_mismatch")
        fingerprint = _cleanup_fingerprint(cleanup_input)
        existing = await _existing_cleanup(
            session,
            cleanup_input=cleanup_input,
            step=step,
            fingerprint=fingerprint,
        )
        if existing is not None:
            if run.status != "waiting_approval":
                raise WriterGenerationError("post_audit_cleanup_writer_run_state_invalid")
            return existing
        if run.status != "running" or step.status != "running":
            raise WriterGenerationError("post_audit_cleanup_generation_state_invalid")
        draft = _cleanup_draft(cleanup_input)
        artifact = await _persist_cleanup(
            session,
            cleanup_input=cleanup_input,
            draft=draft,
            step=step,
            fingerprint=fingerprint,
        )
        return PostAuditCleanupResult(
            artifact=artifact,
            draft=draft,
            model_attempts=0,
            reused=False,
        )


__all__ = [
    "CLOSING_SEGMENT_ID",
    "CLOSING_SENTENCE_TO_REMOVE",
    "POST_AUDIT_CLEANUP_GENERATOR_VERSION",
    "POST_AUDIT_CLEANUP_SCHEMA_VERSION",
    "POST_AUDIT_CLEANUP_TASK_KEY",
    "PostAuditCleanupGenerator",
    "PostAuditCleanupInput",
    "PostAuditCleanupResult",
    "RESULT_CLOSING_MARKDOWN",
    "SOURCE_CLOSING_MARKDOWN",
    "load_post_audit_cleanup_input",
]
