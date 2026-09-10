"""CE05 T05.14 bounded English post-audit revision."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.assertion_audit import (
    ASSERTION_AUDIT_EVALUATOR_KEY,
    ASSERTION_AUDIT_EVALUATOR_VERSION,
    ASSERTION_AUDIT_GENERATOR_VERSION,
    _source_segments,
    _split_sentences,
    _summary,
    load_assertion_audit_input,
    validate_assertion_audit_output,
)
from app.modules.content_engine.journal.review_revise import (
    ReviewReviseInput,
    load_review_revise_input,
    unresolved_factual_claims,
)
from app.modules.content_engine.journal.writer import (
    JournalDraft,
    WriterGenerationError,
    WriterInput,
    WriterModelPort,
    _canonical_hash,
    _dict,
    _model_identity,
    _validate_model_output,
    writer_model_input_hash,
)
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ContextManifest,
    QualityEvaluation,
    StepRun,
)

POST_AUDIT_REVISION_GENERATOR_VERSION = "ce05.journal_post_audit_revision.v1"
POST_AUDIT_REVISION_SCHEMA_VERSION = 1
POST_AUDIT_REVISION_TASK_KEY = "post_audit_revise_en"

_TARGET_FINDINGS = (
    (
        "lead:1",
        "You cannot tell whether an original artwork is fairly priced from the number alone.",
        "fact",
        "critical",
    ),
    (
        "section:understand-price-context:1",
        "Prices are context-dependent.",
        "fact",
        "critical",
    ),
    (
        "section:understand-price-context:3",
        "That helps explain why the price alone is not an objective answer.",
        "interpretation",
        "medium",
    ),
    (
        "section:understand-price-context:4",
        (
            "It does not establish that a particular artwork is fairly or unfairly priced, "
            "and price alone does not prove quality, importance or investment value."
        ),
        "fact",
        "critical",
    ),
    (
        "section:ask-for-context:3",
        (
            "These questions invite useful explanation without turning the conversation "
            "into a pricing formula."
        ),
        "interpretation",
        "medium",
    ),
)
_TARGET_IDS = tuple(item[0] for item in _TARGET_FINDINGS)


@dataclass(frozen=True, slots=True)
class PostAuditFinding:
    segment_id: str
    assertion_text: str
    assertion_type: str
    support_status: str
    severity: str
    rationale: str
    evidence_refs: tuple[str, ...]
    originality_refs: tuple[str, ...]
    claim_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "segment_id": self.segment_id,
            "assertion_text": self.assertion_text,
            "assertion_type": self.assertion_type,
            "support_status": self.support_status,
            "severity": self.severity,
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
            "originality_refs": list(self.originality_refs),
            "claim_refs": list(self.claim_refs),
        }


@dataclass(frozen=True, slots=True)
class PostAuditRevisionInput:
    review_input: ReviewReviseInput
    audit_artifact: Artifact
    quality_evaluation: QualityEvaluation
    findings: tuple[PostAuditFinding, ...]
    findings_hash: str
    model_input: dict[str, object]

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
class PostAuditRevisionResult:
    artifact: Artifact
    draft: JournalDraft
    findings_hash: str
    model_attempts: int
    reused: bool


def _audit_ref(payload: dict[str, object], key: str, error: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise WriterGenerationError(error)
    return cast(dict[str, object], value)


async def _load_failed_audit(
    session: AsyncSession,
    *,
    audit_artifact_id: UUID,
    expected_audit_version: int,
    expected_audit_hash: str,
    quality_evaluation_id: UUID,
    source_input: ReviewReviseInput,
) -> tuple[Artifact, QualityEvaluation, tuple[PostAuditFinding, ...], str]:
    audit = await session.get(Artifact, audit_artifact_id)
    if audit is None or audit.artifact_type != "assertion_audit":
        raise WriterGenerationError("post_audit_failed_audit_not_found")
    if (
        audit.version != expected_audit_version
        or audit.content_hash != expected_audit_hash
        or audit.version != 1
    ):
        raise WriterGenerationError("post_audit_failed_audit_snapshot_mismatch")
    if audit.locale != "en" or audit.run_id == source_input.writer_input.writer_run.id:
        raise WriterGenerationError("post_audit_failed_audit_lineage_mismatch")
    audit_run = await session.get(ContentRun, audit.run_id)
    writer_run = source_input.writer_input.writer_run
    if (
        audit_run is None
        or audit_run.run_mode != "eval"
        or audit_run.status != "completed"
        or audit_run.project_id != writer_run.project_id
        or audit_run.content_case_id != writer_run.content_case_id
        or audit_run.locale_variant_id != source_input.writer_input.locale_variant.id
        or audit_run.settings_snapshot_id != writer_run.settings_snapshot_id
    ):
        raise WriterGenerationError("post_audit_failed_audit_run_invalid")
    payload = _dict(audit.content_json, "post_audit_failed_audit_payload_invalid")
    if _canonical_hash(payload) != audit.content_hash:
        raise WriterGenerationError("post_audit_failed_audit_snapshot_stale")
    if payload.get("artifact_type") != "assertion_audit":
        raise WriterGenerationError("post_audit_failed_audit_payload_invalid")
    generator = _audit_ref(payload, "generator", "post_audit_failed_audit_generator_invalid")
    if (
        generator.get("version") != ASSERTION_AUDIT_GENERATOR_VERSION
        or generator.get("schema_version") != 1
    ):
        raise WriterGenerationError("post_audit_failed_audit_generator_mismatch")
    source_ref = _audit_ref(payload, "source_draft", "post_audit_failed_audit_source_ref_invalid")
    source = source_input.source_artifact
    if (
        source_ref.get("id") != str(source.id)
        or source_ref.get("version") != source.version
        or source_ref.get("content_hash") != source.content_hash
        or payload.get("source_writer_run_id") != str(source_input.writer_input.writer_run.id)
    ):
        raise WriterGenerationError("post_audit_failed_audit_source_mismatch")
    outline_ref = _audit_ref(
        payload,
        "journal_outline",
        "post_audit_failed_audit_outline_ref_invalid",
    )
    outline = source_input.writer_input.outline_artifact
    if (
        outline_ref.get("id") != str(outline.id)
        or outline_ref.get("version") != outline.version
        or outline_ref.get("content_hash") != outline.content_hash
    ):
        raise WriterGenerationError("post_audit_failed_audit_outline_mismatch")
    bundle = source_input.writer_input.outline_input.bundle
    evidence_ref = _audit_ref(
        payload,
        "evidence_set",
        "post_audit_failed_audit_evidence_ref_invalid",
    )
    originality_ref = _audit_ref(
        payload,
        "originality_pack",
        "post_audit_failed_audit_originality_ref_invalid",
    )
    if (
        evidence_ref.get("id") != str(bundle.evidence_set_id)
        or evidence_ref.get("version") != bundle.evidence_set_version
        or evidence_ref.get("content_hash") != bundle.evidence_set_hash
        or originality_ref.get("id") != str(bundle.originality_pack_id)
        or originality_ref.get("snapshot_hash") != bundle.originality_pack_hash
    ):
        raise WriterGenerationError("post_audit_failed_audit_upstream_mismatch")

    raw_segments = payload.get("segments")
    raw_output = {"locale": "en", "segments": raw_segments}
    try:
        audit_input = await load_assertion_audit_input(
            session,
            writer_run_id=source_input.writer_input.writer_run.id,
            revised_draft_artifact_id=source.id,
            expected_revised_draft_version=source.version,
            expected_revised_draft_hash=source.content_hash,
            outline_artifact_id=source_input.writer_input.outline_artifact.id,
            expected_outline_version=source_input.writer_input.outline_artifact.version,
            expected_outline_hash=source_input.writer_input.outline_artifact.content_hash,
            locale="en",
        )
        audited_segments = validate_assertion_audit_output(
            raw_output,
            audit_input=audit_input,
        )
    except Exception as exc:
        if isinstance(exc, WriterGenerationError):
            raise
        raise WriterGenerationError("post_audit_failed_audit_content_invalid", str(exc)) from exc
    summary = _summary(audited_segments)
    if payload.get("summary") != summary or summary["result"] != "fail":
        raise WriterGenerationError("post_audit_failed_audit_summary_mismatch")

    expected_by_id = {item[0]: item for item in _TARGET_FINDINGS}
    findings: list[PostAuditFinding] = []
    for segment in audited_segments:
        for assertion in segment.assertions:
            if assertion.support_status != "unsupported":
                continue
            expected = expected_by_id.get(segment.segment_id)
            if expected is None or assertion.assertion_text != expected[1]:
                raise WriterGenerationError("post_audit_failed_audit_finding_mismatch")
            if (
                assertion.assertion_type != expected[2]
                or assertion.severity != expected[3]
            ):
                raise WriterGenerationError("post_audit_failed_audit_finding_mismatch")
            findings.append(
                PostAuditFinding(
                    segment_id=segment.segment_id,
                    assertion_text=assertion.assertion_text,
                    assertion_type=assertion.assertion_type,
                    support_status=assertion.support_status,
                    severity=assertion.severity,
                    rationale=assertion.rationale,
                    evidence_refs=assertion.evidence_refs,
                    originality_refs=assertion.originality_refs,
                    claim_refs=assertion.claim_refs,
                )
            )
    if tuple(item.segment_id for item in findings) != _TARGET_IDS:
        raise WriterGenerationError("post_audit_failed_audit_finding_set_mismatch")
    if summary["unsupported_count"] != len(_TARGET_FINDINGS) or summary["contradicted_count"] != 0:
        raise WriterGenerationError("post_audit_failed_audit_finding_count_mismatch")
    findings_hash = _canonical_hash([item.to_dict() for item in findings])

    evaluation = await session.get(QualityEvaluation, quality_evaluation_id)
    if evaluation is None:
        raise WriterGenerationError("post_audit_quality_evaluation_not_found")
    if (
        evaluation.run_id != audit.run_id
        or evaluation.artifact_id != audit.id
        or evaluation.evaluator_key != ASSERTION_AUDIT_EVALUATOR_KEY
        or evaluation.evaluator_version != ASSERTION_AUDIT_EVALUATOR_VERSION
        or evaluation.result != "fail"
        or evaluation.severity != "critical"
    ):
        raise WriterGenerationError("post_audit_quality_evaluation_mismatch")
    findings_json = _dict(evaluation.findings_json, "post_audit_quality_findings_invalid")
    if (
        findings_json.get("source_draft_id") != str(source.id)
        or findings_json.get("source_draft_hash") != source.content_hash
        or findings_json.get("assertion_audit_artifact_id") != str(audit.id)
        or findings_json.get("assertion_audit_hash") != audit.content_hash
        or findings_json.get("unsupported_count") != len(_TARGET_FINDINGS)
        or findings_json.get("contradicted_count") != 0
        or findings_json.get("critical_unsupported_count") != 3
        or findings_json.get("critical_contradicted_count") != 0
    ):
        raise WriterGenerationError("post_audit_quality_evaluation_snapshot_mismatch")
    return audit, evaluation, tuple(findings), findings_hash


async def load_post_audit_revision_input(
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
) -> PostAuditRevisionInput:
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
    if review_input.source_artifact.version != 2:
        raise WriterGenerationError("post_audit_source_draft_version_invalid")
    if review_input.writer_input.writer_run.status != "waiting_approval":
        raise WriterGenerationError(
            "post_audit_writer_run_state_invalid",
            review_input.writer_input.writer_run.status,
        )
    audit, evaluation, findings, findings_hash = await _load_failed_audit(
        session,
        audit_artifact_id=failed_audit_artifact_id,
        expected_audit_version=expected_failed_audit_version,
        expected_audit_hash=expected_failed_audit_hash,
        quality_evaluation_id=failed_quality_evaluation_id,
        source_input=review_input,
    )
    model_input = copy.deepcopy(review_input.model_input)
    model_input.update(
        {
            "failed_assertion_audit_ref": {
                "id": str(audit.id),
                "version": audit.version,
                "content_hash": audit.content_hash,
            },
            "failed_quality_evaluation_ref": {
                "id": str(evaluation.id),
                "evaluator_key": evaluation.evaluator_key,
                "evaluator_version": evaluation.evaluator_version,
                "result": evaluation.result,
            },
            "target_findings": [finding.to_dict() for finding in findings],
            "target_findings_hash": findings_hash,
            "post_audit_revision_policy": {
                "mode": "exact_five_sentence_replacements",
                "requirements": [
                    "return_only_the_five_target_replacements",
                    "preserve_all_non_target_visible_copy_byte_identical",
                    "preserve_exact_section_ids_order_and_support_refs",
                    "do_not_add_evidence_or_originality_refs",
                    "do_not_add_research_tools_urls_or_sibling_locale_input",
                    "recast_unsupported_claims_as_bounded_reader_guidance",
                    "return_one_sentence_per_target",
                ],
            },
        }
    )
    return PostAuditRevisionInput(
        review_input=review_input,
        audit_artifact=audit,
        quality_evaluation=evaluation,
        findings=findings,
        findings_hash=findings_hash,
        model_input=model_input,
    )


def _required_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WriterGenerationError(code)
    return value.strip()


def validate_post_audit_revision_output(
    raw: object,
    *,
    revision_input: PostAuditRevisionInput,
) -> dict[str, str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WriterGenerationError("post_audit_revision_output_json_invalid") from exc
    payload = _dict(raw, "post_audit_revision_output_invalid")
    if set(payload) != {"locale", "revisions"} or payload.get("locale") != "en":
        raise WriterGenerationError("post_audit_revision_output_contract_invalid")
    revisions = payload.get("revisions")
    if not isinstance(revisions, list) or len(revisions) != len(_TARGET_FINDINGS):
        raise WriterGenerationError("post_audit_revision_target_count_invalid")
    expected_sources = {
        finding.segment_id: finding.assertion_text for finding in revision_input.findings
    }
    if tuple(expected_sources) != _TARGET_IDS:
        raise WriterGenerationError("post_audit_revision_target_binding_invalid")
    replacements: dict[str, str] = {}
    for raw_revision in revisions:
        revision = _dict(raw_revision, "post_audit_revision_item_invalid")
        if set(revision) != {"segment_id", "source_text", "replacement_text"}:
            raise WriterGenerationError("post_audit_revision_item_contract_invalid")
        segment_id = _required_text(
            revision.get("segment_id"),
            "post_audit_revision_segment_id_required",
        )
        if segment_id in replacements or segment_id not in expected_sources:
            raise WriterGenerationError("post_audit_revision_target_ids_invalid")
        source_text = _required_text(
            revision.get("source_text"),
            "post_audit_revision_source_text_required",
        )
        if source_text != expected_sources[segment_id]:
            raise WriterGenerationError("post_audit_revision_source_text_mismatch", segment_id)
        replacement = _required_text(
            revision.get("replacement_text"),
            "post_audit_revision_replacement_required",
        )
        if replacement == source_text or "\n" in replacement or "\r" in replacement:
            raise WriterGenerationError("post_audit_revision_replacement_invalid", segment_id)
        if len(_split_sentences(replacement)) != 1:
            raise WriterGenerationError(
                "post_audit_revision_replacement_not_one_sentence",
                segment_id,
            )
        replacements[segment_id] = replacement
    if tuple(replacements) != _TARGET_IDS:
        raise WriterGenerationError("post_audit_revision_target_ids_invalid")
    return replacements


def _replace_once(value: str, source: str, replacement: str, *, segment_id: str) -> str:
    if value.count(source) != 1:
        raise WriterGenerationError("post_audit_revision_source_occurrence_invalid", segment_id)
    return value.replace(source, replacement, 1)


def _apply_replacements(
    revision_input: PostAuditRevisionInput,
    replacements: dict[str, str],
) -> JournalDraft:
    source = revision_input.source_draft
    payload = copy.deepcopy(source.to_dict())
    for segment_id, replacement in replacements.items():
        source_text = next(
            finding.assertion_text
            for finding in revision_input.findings
            if finding.segment_id == segment_id
        )
        if segment_id == "lead:1":
            payload["lead_markdown"] = _replace_once(
                cast(str, payload["lead_markdown"]),
                source_text,
                replacement,
                segment_id=segment_id,
            )
            continue
        prefix, section_id, _index = segment_id.split(":", 2)
        if prefix != "section":
            raise WriterGenerationError("post_audit_revision_target_location_invalid", segment_id)
        sections = payload.get("sections")
        if not isinstance(sections, list):
            raise WriterGenerationError("post_audit_revision_sections_invalid")
        matching = [
            _dict(section, "post_audit_revision_section_invalid")
            for section in sections
            if isinstance(section, dict) and section.get("section_id") == section_id
        ]
        if len(matching) != 1:
            raise WriterGenerationError("post_audit_revision_target_section_invalid", section_id)
        section = matching[0]
        section["body_markdown"] = _replace_once(
            cast(str, section.get("body_markdown")),
            source_text,
            replacement,
            segment_id=segment_id,
        )

    try:
        revised = _validate_model_output(payload, writer_input=revision_input.writer_input)
    except WriterGenerationError:
        raise
    if unresolved_factual_claims(revised):
        raise WriterGenerationError("post_audit_revision_unresolved_claims")
    _validate_non_target_immutability(source, revised, replacements)
    return revised


def _validate_non_target_immutability(
    source: JournalDraft,
    revised: JournalDraft,
    replacements: dict[str, str],
) -> None:
    source_payload = source.to_dict()
    revised_payload = revised.to_dict()
    for key in (
        "locale",
        "title",
        "standfirst",
        "lead_evidence_refs",
        "lead_originality_refs",
        "internal_link_intents",
        "unresolved_factual_claims",
    ):
        if revised_payload[key] != source_payload[key]:
            raise WriterGenerationError("post_audit_revision_protected_field_changed", key)
    source_sections = cast(list[object], source_payload["sections"])
    revised_sections = cast(list[object], revised_payload["sections"])
    if len(source_sections) != len(revised_sections):
        raise WriterGenerationError("post_audit_revision_section_count_changed")
    for source_section, revised_section in zip(source_sections, revised_sections, strict=True):
        before = _dict(source_section, "post_audit_revision_section_invalid")
        after = _dict(revised_section, "post_audit_revision_section_invalid")
        for key in (
            "section_id",
            "heading",
            "evidence_refs",
            "originality_refs",
            "unresolved_factual_claims",
        ):
            if before[key] != after[key]:
                raise WriterGenerationError("post_audit_revision_protected_field_changed", key)

    source_segments = _source_segments(source)
    revised_segments = _source_segments(revised)
    if [segment.segment_id for segment in source_segments] != [
        segment.segment_id for segment in revised_segments
    ]:
        raise WriterGenerationError("post_audit_revision_segment_structure_changed")
    expected_replacements = set(replacements)
    for before_segment, after_segment in zip(source_segments, revised_segments, strict=True):
        if before_segment.segment_id in expected_replacements:
            if after_segment.source_text != replacements[before_segment.segment_id]:
                raise WriterGenerationError(
                    "post_audit_revision_target_replacement_mismatch",
                    before_segment.segment_id,
                )
        elif before_segment.source_text != after_segment.source_text:
            raise WriterGenerationError(
                "post_audit_revision_non_target_copy_changed",
                before_segment.segment_id,
            )


def _revision_writer_input(revision_input: PostAuditRevisionInput) -> WriterInput:
    base = revision_input.writer_input
    return WriterInput(
        writer_run=base.writer_run,
        locale_variant=base.locale_variant,
        handoff_artifact=base.handoff_artifact,
        outline_artifact=base.outline_artifact,
        outline_payload=base.outline_payload,
        outline_input=base.outline_input,
        locale=base.locale,
        model_input=copy.deepcopy(revision_input.model_input),
    )


def _revision_fingerprint(
    *,
    revision_input: PostAuditRevisionInput,
    model_input_hash: str,
    provider: str,
    model: str,
    prompt_version: str,
    recipe_version: str,
    context_manifest_hash: str,
) -> str:
    return _canonical_hash(
        {
            "source_draft_id": str(revision_input.source_artifact.id),
            "source_draft_version": revision_input.source_artifact.version,
            "source_draft_hash": revision_input.source_artifact.content_hash,
            "failed_audit_artifact_id": str(revision_input.audit_artifact.id),
            "failed_audit_artifact_version": revision_input.audit_artifact.version,
            "failed_audit_artifact_hash": revision_input.audit_artifact.content_hash,
            "quality_evaluation_id": str(revision_input.quality_evaluation.id),
            "findings_hash": revision_input.findings_hash,
            "locale": "en",
            "model_input_hash": model_input_hash,
            "provider": provider,
            "model": model,
            "prompt_version": prompt_version,
            "recipe_version": recipe_version,
            "context_manifest_hash": context_manifest_hash,
            "generator_version": POST_AUDIT_REVISION_GENERATOR_VERSION,
            "schema_version": POST_AUDIT_REVISION_SCHEMA_VERSION,
        }
    )


async def _existing_revision(
    session: AsyncSession,
    *,
    revision_input: PostAuditRevisionInput,
    writer_input: WriterInput,
    fingerprint: str,
    expected_step_run_id: UUID,
) -> PostAuditRevisionResult | None:
    artifacts = list(
        (
            await session.scalars(
                select(Artifact)
                .where(
                    Artifact.run_id == writer_input.writer_run.id,
                    Artifact.artifact_type == "journal_draft",
                    Artifact.locale == "en",
                )
                .order_by(Artifact.version)
            )
        ).all()
    )
    matching: list[Artifact] = []
    for artifact in artifacts:
        payload = artifact.content_json
        if not isinstance(payload, dict) or payload.get("generation_fingerprint") != fingerprint:
            continue
        if _canonical_hash(payload) != artifact.content_hash:
            raise WriterGenerationError("post_audit_revision_artifact_snapshot_stale")
        matching.append(artifact)
    if not matching:
        return None
    if len(matching) != 1 or matching[0].version != revision_input.source_artifact.version + 1:
        raise WriterGenerationError("post_audit_revision_artifact_version_conflict")
    artifact = matching[0]
    if artifact.step_run_id != expected_step_run_id:
        raise WriterGenerationError("post_audit_revision_artifact_step_mismatch")
    step = await session.get(StepRun, expected_step_run_id)
    if step is None or step.status != "completed":
        raise WriterGenerationError("post_audit_revision_completed_step_required")
    payload = _dict(artifact.content_json, "post_audit_revision_artifact_payload_invalid")
    draft_payload = _dict(payload.get("draft"), "post_audit_revision_draft_payload_invalid")
    draft = _validate_model_output(draft_payload, writer_input=writer_input)
    if draft.to_dict() != draft_payload:
        raise WriterGenerationError("post_audit_revision_artifact_payload_stale")
    revision_meta = _dict(
        payload.get("post_audit_revision"),
        "post_audit_revision_metadata_invalid",
    )
    raw_replacements = revision_meta.get("replacement_texts")
    if not isinstance(raw_replacements, dict):
        raise WriterGenerationError("post_audit_revision_replacements_missing")
    replacements = {
        str(key): _required_text(value, "post_audit_revision_replacement_invalid")
        for key, value in raw_replacements.items()
    }
    if tuple(replacements) != _TARGET_IDS:
        raise WriterGenerationError("post_audit_revision_replacement_set_invalid")
    _validate_non_target_immutability(revision_input.source_draft, draft, replacements)
    return PostAuditRevisionResult(
        artifact=artifact,
        draft=draft,
        findings_hash=revision_input.findings_hash,
        model_attempts=0,
        reused=True,
    )


async def _persist_revision(
    session: AsyncSession,
    *,
    revision_input: PostAuditRevisionInput,
    writer_input: WriterInput,
    draft: JournalDraft,
    provider: str,
    model: str,
    model_attempts: int,
    prompt_version: str,
    recipe_version: str,
    context_manifest: ContextManifest,
    fingerprint: str,
    model_input_hash: str,
    replacements: dict[str, str],
) -> Artifact:
    if not provider.strip() or not model.strip() or model_attempts <= 0:
        raise WriterGenerationError("post_audit_revision_model_metadata_invalid")
    if context_manifest.run_id != writer_input.writer_run.id:
        raise WriterGenerationError("post_audit_revision_context_run_mismatch")
    step = await session.get(StepRun, context_manifest.step_run_id)
    if (
        step is None
        or step.run_id != writer_input.writer_run.id
        or step.step_key != POST_AUDIT_REVISION_TASK_KEY
    ):
        raise WriterGenerationError("post_audit_revision_step_ownership_mismatch")
    audit_ref = {
        "id": str(revision_input.audit_artifact.id),
        "version": revision_input.audit_artifact.version,
        "content_hash": revision_input.audit_artifact.content_hash,
    }
    payload: dict[str, object] = {
        "schema_version": POST_AUDIT_REVISION_SCHEMA_VERSION,
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
        "journal_outline": {
            "id": str(writer_input.outline_artifact.id),
            "version": writer_input.outline_artifact.version,
            "content_hash": writer_input.outline_artifact.content_hash,
        },
        "evidence_set": {
            "id": str(writer_input.outline_input.bundle.evidence_set_id),
            "version": writer_input.outline_input.bundle.evidence_set_version,
            "content_hash": writer_input.outline_input.bundle.evidence_set_hash,
        },
        "originality_pack": {
            "id": str(writer_input.outline_input.bundle.originality_pack_id),
            "snapshot_hash": writer_input.outline_input.bundle.originality_pack_hash,
        },
        "post_audit_revision": {
            "source_draft": {
                "id": str(revision_input.source_artifact.id),
                "version": revision_input.source_artifact.version,
                "content_hash": revision_input.source_artifact.content_hash,
            },
            "failed_assertion_audit": audit_ref,
            "failed_quality_evaluation": {
                "id": str(revision_input.quality_evaluation.id),
                "evaluator_key": revision_input.quality_evaluation.evaluator_key,
                "evaluator_version": revision_input.quality_evaluation.evaluator_version,
                "result": revision_input.quality_evaluation.result,
            },
            "target_findings_hash": revision_input.findings_hash,
            "replacement_texts": dict(replacements),
        },
        "model_input": {"content_hash": model_input_hash},
        "execution_context": {
            "context_manifest_id": str(context_manifest.id),
            "context_manifest_hash": context_manifest.content_hash,
            "settings_snapshot_id": str(context_manifest.settings_snapshot_id),
            "prompt_version": prompt_version,
            "recipe_version": recipe_version,
        },
        "generator": {
            "version": POST_AUDIT_REVISION_GENERATOR_VERSION,
            "schema_version": POST_AUDIT_REVISION_SCHEMA_VERSION,
        },
        "model": {"provider": provider.strip(), "model": model.strip()},
        "provider_calls": 0,
        "model_calls": model_attempts,
        "draft": draft.to_dict(),
    }
    content_hash = _canonical_hash(payload)
    existing = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == writer_input.writer_run.id,
            Artifact.artifact_type == "journal_draft",
            Artifact.locale == "en",
            Artifact.content_hash == content_hash,
        )
    )
    if existing is not None:
        if (
            existing.content_json != payload
            or existing.version != revision_input.source_artifact.version + 1
        ):
            raise WriterGenerationError("post_audit_revision_artifact_hash_collision")
        return existing
    latest = await session.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.run_id == writer_input.writer_run.id,
            Artifact.artifact_type == "journal_draft",
        )
    )
    if latest != revision_input.source_artifact.version:
        raise WriterGenerationError("post_audit_revision_next_version_conflict")
    artifact = Artifact(
        run_id=writer_input.writer_run.id,
        step_run_id=context_manifest.step_run_id,
        artifact_type="journal_draft",
        locale="en",
        version=revision_input.source_artifact.version + 1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    if artifact.step_run_id is not None:
        step = await session.get(StepRun, artifact.step_run_id)
        if step is None or step.run_id != artifact.run_id:
            raise WriterGenerationError("post_audit_revision_artifact_step_mismatch")
        if str(artifact.id) not in step.output_artifact_refs_json:
            step.output_artifact_refs_json = [*step.output_artifact_refs_json, str(artifact.id)]
            await session.flush()
    return artifact


class PostAuditRevisionGenerator:
    """Apply five bounded model replacements to one immutable EN draft."""

    def __init__(self, *, max_attempts: int = 2) -> None:
        if (
            isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or not 1 <= max_attempts <= 3
        ):
            raise ValueError("max_attempts must be between 1 and 3")
        self.max_attempts = max_attempts

    async def revise_draft(
        self,
        session: AsyncSession,
        *,
        revision_input: PostAuditRevisionInput,
        model: WriterModelPort,
        provider: str,
        model_name: str,
        context_manifest: ContextManifest,
        prompt_version: str,
        recipe_version: str,
    ) -> PostAuditRevisionResult:
        writer_input = _revision_writer_input(revision_input)
        if writer_input.writer_run.status in {"completed", "failed", "cancelled"}:
            raise WriterGenerationError("post_audit_writer_run_state_invalid")
        if context_manifest.settings_snapshot_id != writer_input.writer_run.settings_snapshot_id:
            raise WriterGenerationError("post_audit_revision_settings_snapshot_mismatch")
        if (
            context_manifest.evidence_set_id
            != writer_input.outline_input.bundle.evidence_set_id
        ):
            raise WriterGenerationError("post_audit_revision_context_evidence_mismatch")
        if (
            context_manifest.originality_pack_id
            != writer_input.outline_input.bundle.originality_pack_id
        ):
            raise WriterGenerationError("post_audit_revision_context_originality_mismatch")
        if (
            context_manifest.prompt_version != prompt_version
            or context_manifest.recipe_version != recipe_version
        ):
            raise WriterGenerationError("post_audit_revision_context_registry_mismatch")
        step = await session.get(StepRun, context_manifest.step_run_id)
        if (
            step is None
            or step.run_id != writer_input.writer_run.id
            or step.step_key != POST_AUDIT_REVISION_TASK_KEY
        ):
            raise WriterGenerationError("post_audit_revision_step_ownership_mismatch")
        routed = _model_identity(model)
        if routed is not None and (provider.strip(), model_name.strip()) != routed:
            raise WriterGenerationError("post_audit_revision_model_route_mismatch")
        artifact_provider, artifact_model = routed or (provider.strip(), model_name.strip())
        if not artifact_provider or not artifact_model:
            raise WriterGenerationError("post_audit_revision_model_metadata_invalid")
        model_input_hash = writer_model_input_hash(writer_input.model_input)
        fingerprint = _revision_fingerprint(
            revision_input=revision_input,
            model_input_hash=model_input_hash,
            provider=artifact_provider,
            model=artifact_model,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
            context_manifest_hash=context_manifest.content_hash,
        )
        context_step_id = context_manifest.step_run_id
        if context_step_id is None:
            raise WriterGenerationError("post_audit_revision_step_ownership_mismatch")
        existing = await _existing_revision(
            session,
            revision_input=revision_input,
            writer_input=writer_input,
            fingerprint=fingerprint,
            expected_step_run_id=context_step_id,
        )
        if existing is not None:
            if writer_input.writer_run.status != "waiting_approval":
                raise WriterGenerationError("post_audit_writer_run_state_invalid")
            return existing
        if writer_input.writer_run.status != "running" or step.status != "running":
            raise WriterGenerationError("post_audit_revision_generation_state_invalid")
        latest = await session.scalar(
            select(func.max(Artifact.version)).where(
                Artifact.run_id == writer_input.writer_run.id,
                Artifact.artifact_type == "journal_draft",
            )
        )
        if latest != revision_input.source_artifact.version:
            raise WriterGenerationError("post_audit_revision_next_version_conflict")

        last_error: WriterGenerationError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw = await model.generate(
                    input_bundle=copy.deepcopy(revision_input.model_input),
                    attempt=attempt,
                )
                replacements = validate_post_audit_revision_output(
                    raw,
                    revision_input=revision_input,
                )
                revised = _apply_replacements(revision_input, replacements)
            except WriterGenerationError as exc:
                last_error = exc
                if attempt == self.max_attempts:
                    raise WriterGenerationError(
                        "post_audit_revision_model_output_invalid",
                        f"bounded retries exhausted ({exc.code})",
                    ) from exc
                continue
            artifact = await _persist_revision(
                session,
                revision_input=revision_input,
                writer_input=writer_input,
                draft=revised,
                provider=artifact_provider,
                model=artifact_model,
                model_attempts=attempt,
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                context_manifest=context_manifest,
                fingerprint=fingerprint,
                model_input_hash=model_input_hash,
                replacements=replacements,
            )
            return PostAuditRevisionResult(
                artifact=artifact,
                draft=revised,
                findings_hash=revision_input.findings_hash,
                model_attempts=attempt,
                reused=False,
            )
        raise WriterGenerationError("post_audit_revision_model_output_invalid") from last_error


__all__ = [
    "POST_AUDIT_REVISION_GENERATOR_VERSION",
    "POST_AUDIT_REVISION_SCHEMA_VERSION",
    "POST_AUDIT_REVISION_TASK_KEY",
    "PostAuditFinding",
    "PostAuditRevisionGenerator",
    "PostAuditRevisionInput",
    "PostAuditRevisionResult",
    "load_post_audit_revision_input",
    "validate_post_audit_revision_output",
]
