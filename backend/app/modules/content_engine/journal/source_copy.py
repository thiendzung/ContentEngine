"""CE05 T05.15 bounded deterministic source-copy check.

This module deliberately does not call a model or any external source.  It compares
visible Journal segments with the exact locked EvidenceSet excerpts and the approved
OriginalityPack text fields only.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.assertion_audit import (
    ASSERTION_AUDIT_EVALUATOR_VERSION,
    ASSERTION_AUDIT_GENERATOR_VERSION,
    ASSERTION_AUDIT_SCHEMA_VERSION,
    AssertionAuditError,
    AuditSourceSegment,
    _source_segments,
    _summary,
    load_assertion_audit_input,
    validate_assertion_audit_output,
)
from app.modules.content_engine.journal.assertion_audit_execution import (
    validate_source_writer_eligibility,
)
from app.modules.content_engine.journal.writer import (
    JournalDraft,
    WriterGenerationError,
    WriterInput,
    _canonical_hash,
    _dict,
    _validate_model_output,
    load_writer_input,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.models import Artifact, ContentRun, QualityEvaluation, StepRun, utc_now
from app.modules.harness.persistence import transition_run, transition_step_run
from app.modules.knowledge.models import Evidence, EvidenceSet, OriginalityPack
from app.modules.knowledge.originality_pack import originality_pack_snapshot_hash

SOURCE_COPY_GENERATOR_VERSION = "ce05.journal_source_copy.v2"
SOURCE_COPY_EVALUATOR_KEY = "source_copy_basic_gate"
SOURCE_COPY_EVALUATOR_VERSION = "ce05.source_copy.basic_gate.v2"
SOURCE_COPY_SCHEMA_VERSION = 1
SOURCE_COPY_HANDOFF_SCHEMA_VERSION = 1
SOURCE_COPY_TASK_KEYS = {"vi-VN": "source_copy_check_vi", "en": "source_copy_check_en"}
SOURCE_COPY_IGNORE_MAX_TOKENS = 7
SOURCE_COPY_WARN_MAX_TOKENS = 11
SOURCE_COPY_WARN_MIN_TOKENS = 8
SOURCE_COPY_FAIL_MIN_TOKENS = 12
_ASSERTION_AUDIT_VERSION_PAIRS = frozenset(
    {
        ("ce05.journal_assertion_audit.v3", "ce05.assertion_audit.hard_gate.v3"),
        (ASSERTION_AUDIT_GENERATOR_VERSION, ASSERTION_AUDIT_EVALUATOR_VERSION),
    }
)

# Punctuation is a word-token boundary.  In particular, straight and curly
# apostrophes both split a word so typography-only changes cannot evade the
# exact contiguous-token check.
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_SOURCE_KINDS = {
    "evidence_excerpt",
    "originality_material",
    "originality_writer_use",
    "originality_guardrail",
}


class SourceCopyError(ValueError):
    """Raised when source-copy input or durable state is unsafe."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class _Token:
    value: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class SourceCopySource:
    source_kind: str
    source_ref: str
    source_field: str
    source_text: str
    source_text_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "source_field": self.source_field,
            "source_text_hash": self.source_text_hash,
        }


@dataclass(frozen=True, slots=True)
class SourceCopyFinding:
    locale: str
    draft_segment_id: str
    draft_location: str
    draft_text: str
    source_kind: str
    source_ref: str
    source_field: str
    source_text_hash: str
    matched_draft_span: dict[str, object]
    matched_source_span: dict[str, object]
    normalized_match: str
    overlap_token_count: int
    classification: str

    def to_dict(self) -> dict[str, object]:
        return {
            "locale": self.locale,
            "draft_segment_id": self.draft_segment_id,
            "draft_location": self.draft_location,
            "draft_text": self.draft_text,
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "source_field": self.source_field,
            "source_text_hash": self.source_text_hash,
            "matched_draft_span": self.matched_draft_span,
            "matched_source_span": self.matched_source_span,
            "normalized_match": self.normalized_match,
            "overlap_token_count": self.overlap_token_count,
            "classification": self.classification,
        }


@dataclass(frozen=True, slots=True)
class SourceCopyCheck:
    result: str
    findings: tuple[SourceCopyFinding, ...]
    finding_count: int
    warn_count: int
    fail_count: int
    max_overlap_tokens: int

    def summary(self) -> dict[str, int | str]:
        return {
            "result": self.result,
            "finding_count": self.finding_count,
            "warn_count": self.warn_count,
            "fail_count": self.fail_count,
            "max_overlap_tokens": self.max_overlap_tokens,
        }


@dataclass(frozen=True, slots=True)
class SourceCopyInput:
    writer_input: WriterInput
    source_artifact: Artifact
    source_draft: JournalDraft
    assertion_audit_artifact: Artifact
    assertion_audit_evaluation: QualityEvaluation
    sources: tuple[SourceCopySource, ...]
    segments: tuple[AuditSourceSegment, ...]
    settings_snapshot_hash: str | None = None


@dataclass(frozen=True, slots=True)
class SourceCopyResult:
    eval_run: ContentRun
    handoff: Artifact
    step_run: StepRun
    artifact: Artifact
    evaluation: QualityEvaluation
    check: SourceCopyCheck
    reused: bool
    model_attempts: int = 0


def normalize_source_copy_text(value: str) -> str:
    """Normalize only for matching; never mutate the stored draft or source."""

    return unicodedata.normalize("NFKC", value).casefold()


def normalize_source_copy_tokens(value: str) -> tuple[str, ...]:
    normalized = normalize_source_copy_text(value)
    return tuple(match.group(0) for match in _TOKEN.finditer(normalized))


def _tokens(value: str) -> tuple[_Token, ...]:
    normalized = normalize_source_copy_text(value)
    return tuple(
        _Token(match.group(0), match.start(), match.end())
        for match in _TOKEN.finditer(normalized)
    )


def _source_text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _span(value: str, token_values: tuple[_Token, ...], start: int, end: int) -> dict[str, object]:
    normalized = normalize_source_copy_text(value)
    first = token_values[start]
    last = token_values[end - 1]
    return {
        "start": first.start,
        "end": last.end,
        "text": normalized[first.start : last.end],
    }


def _maximal_overlaps(
    draft_text: str,
    source_text: str,
) -> tuple[tuple[int, int, int], ...]:
    draft_tokens = _tokens(draft_text)
    source_tokens = _tokens(source_text)
    matches: list[tuple[int, int, int]] = []
    for draft_index, draft_token in enumerate(draft_tokens):
        for source_index, source_token in enumerate(source_tokens):
            if draft_token.value != source_token.value:
                continue
            if (
                draft_index > 0
                and source_index > 0
                and draft_tokens[draft_index - 1].value == source_tokens[source_index - 1].value
            ):
                continue
            length = 1
            while (
                draft_index + length < len(draft_tokens)
                and source_index + length < len(source_tokens)
                and draft_tokens[draft_index + length].value
                == source_tokens[source_index + length].value
            ):
                length += 1
            matches.append((draft_index, source_index, length))

    # A maximal match is persisted once per source/segment.  This also removes
    # contained matches in repeated-token inputs without fuzzy interpretation.
    maximal: list[tuple[int, int, int]] = []
    for candidate in matches:
        draft_start, source_start, length = candidate
        draft_end = draft_start + length
        source_end = source_start + length
        contained = any(
            candidate != other
            and draft_start >= other[0]
            and draft_end <= other[0] + other[2]
            and source_start >= other[1]
            and source_end <= other[1] + other[2]
            for other in matches
        )
        if not contained:
            maximal.append(candidate)
    return tuple(sorted(set(maximal), key=lambda item: (item[0], item[1], -item[2])))


def classify_source_copy_overlap(overlap_token_count: int) -> str | None:
    if overlap_token_count <= SOURCE_COPY_IGNORE_MAX_TOKENS:
        return None
    if overlap_token_count <= SOURCE_COPY_WARN_MAX_TOKENS:
        return "warn"
    return "fail"


def check_source_copy(
    *,
    locale: str,
    segments: tuple[AuditSourceSegment, ...],
    sources: tuple[SourceCopySource, ...],
) -> SourceCopyCheck:
    findings: list[SourceCopyFinding] = []
    max_overlap = 0
    for raw_segment in segments:
        segment = raw_segment
        segment_id = segment.segment_id
        location = segment.location
        draft_text = segment.source_text
        draft_tokens = _tokens(draft_text)
        for source in sources:
            source_tokens = _tokens(source.source_text)
            for draft_start, source_start, length in _maximal_overlaps(
                draft_text, source.source_text
            ):
                max_overlap = max(max_overlap, length)
                classification = classify_source_copy_overlap(length)
                if classification is None:
                    continue
                normalized = " ".join(
                    token.value for token in draft_tokens[draft_start : draft_start + length]
                )
                findings.append(
                    SourceCopyFinding(
                        locale=locale,
                        draft_segment_id=segment_id,
                        draft_location=location,
                        draft_text=draft_text,
                        source_kind=source.source_kind,
                        source_ref=source.source_ref,
                        source_field=source.source_field,
                        source_text_hash=source.source_text_hash,
                        matched_draft_span=_span(
                            draft_text, draft_tokens, draft_start, draft_start + length
                        ),
                        matched_source_span=_span(
                            source.source_text,
                            source_tokens,
                            source_start,
                            source_start + length,
                        ),
                        normalized_match=normalized,
                        overlap_token_count=length,
                        classification=classification,
                    )
                )
    findings.sort(
        key=lambda finding: (
            finding.draft_segment_id,
            finding.source_kind,
            finding.source_ref,
            cast(int, finding.matched_draft_span["start"]),
            cast(int, finding.matched_source_span["start"]),
        )
    )
    warn_count = sum(finding.classification == "warn" for finding in findings)
    fail_count = sum(finding.classification == "fail" for finding in findings)
    result = "fail" if fail_count else ("warn" if warn_count else "pass")
    return SourceCopyCheck(
        result=result,
        findings=tuple(findings),
        finding_count=len(findings),
        warn_count=warn_count,
        fail_count=fail_count,
        max_overlap_tokens=max_overlap,
    )


def _source_ref(artifact: Artifact) -> dict[str, object]:
    return {
        "id": str(artifact.id),
        "version": artifact.version,
        "content_hash": artifact.content_hash,
    }


def _bundle_refs(writer_input: WriterInput) -> dict[str, object]:
    bundle = writer_input.outline_input.bundle
    return {
        "evidence_set": {
            "id": str(bundle.evidence_set_id),
            "version": bundle.evidence_set_version,
            "content_hash": bundle.evidence_set_hash,
        },
        "originality_pack": {
            "id": str(bundle.originality_pack_id),
            "snapshot_hash": bundle.originality_pack_hash,
        },
    }


async def _build_sources(
    session: AsyncSession,
    *,
    source_input: SourceCopyInput,
) -> tuple[SourceCopySource, ...]:
    bundle = source_input.writer_input.outline_input.bundle
    evidence_set = await session.get(EvidenceSet, bundle.evidence_set_id)
    if evidence_set is None:
        raise SourceCopyError("source_copy_evidence_set_missing")
    if (
        evidence_set.version != bundle.evidence_set_version
        or evidence_set.content_hash != bundle.evidence_set_hash
        or evidence_set.status != "locked"
        or evidence_set.content_case_id != source_input.writer_input.writer_run.content_case_id
    ):
        raise SourceCopyError("source_copy_evidence_set_snapshot_mismatch")
    try:
        evidence_ids = [UUID(value) for value in evidence_set.evidence_ids_json]
    except (TypeError, ValueError) as exc:
        raise SourceCopyError("source_copy_evidence_ids_invalid") from exc
    evidence_rows = list(
        (
            await session.scalars(select(Evidence).where(Evidence.id.in_(evidence_ids)))
        ).all()
    )
    if {row.id for row in evidence_rows} != set(evidence_ids):
        raise SourceCopyError("source_copy_evidence_row_missing")

    pack = await session.get(OriginalityPack, bundle.originality_pack_id)
    if pack is None:
        raise SourceCopyError("source_copy_originality_pack_missing")
    if (
        pack.content_case_id != source_input.writer_input.writer_run.content_case_id
        or pack.status != "approved"
        or not isinstance(pack.approved_by, str)
        or not pack.approved_by.strip()
        or not isinstance(pack.approval_reason, str)
        or not pack.approval_reason.strip()
        or originality_pack_snapshot_hash(pack) != bundle.originality_pack_hash
        or pack.snapshot_hash != bundle.originality_pack_hash
    ):
        raise SourceCopyError("source_copy_originality_pack_snapshot_mismatch")

    sources: list[SourceCopySource] = []
    for evidence in sorted(evidence_rows, key=lambda row: str(row.id)):
        sources.append(
            SourceCopySource(
                source_kind="evidence_excerpt",
                source_ref=f"evidence:{evidence.id}",
                source_field="evidence_excerpt",
                source_text=evidence.excerpt,
                source_text_hash=_source_text_hash(evidence.excerpt),
            )
        )
    for index, raw_item in enumerate(pack.item_refs_json):
        if not isinstance(raw_item, dict):
            continue
        item = cast(dict[str, object], raw_item)
        raw_ref = item.get("source_ref")
        source_ref = (
            str(raw_ref).strip()
            if isinstance(raw_ref, str) and raw_ref.strip()
            else f"item:{index}"
        )
        for field, source_kind in (
            ("material", "originality_material"),
            ("writer_use", "originality_writer_use"),
            ("guardrails", "originality_guardrail"),
        ):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                continue
            sources.append(
                SourceCopySource(
                    source_kind=source_kind,
                    source_ref=f"originality:{source_ref}",
                    source_field=field,
                    source_text=value,
                    source_text_hash=_source_text_hash(value),
                )
            )
    if not sources:
        raise SourceCopyError("source_copy_source_corpus_empty")
    return tuple(sources)


async def load_source_copy_input(
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
    outline_artifact_id: UUID,
    expected_outline_version: int,
    expected_outline_hash: str,
    locale: str,
) -> SourceCopyInput:
    writer_input = await load_writer_input(
        session,
        writer_run_id=writer_run_id,
        outline_artifact_id=outline_artifact_id,
        expected_outline_version=expected_outline_version,
        expected_outline_hash=expected_outline_hash,
        locale=locale,
    )
    source = await session.get(Artifact, source_draft_artifact_id)
    if (
        source is None
        or source.artifact_type != "journal_draft"
        or source.run_id != writer_run_id
        or source.locale != locale
        or source.version != expected_source_draft_version
        or source.content_hash != expected_source_draft_hash
    ):
        raise SourceCopyError("source_copy_source_draft_snapshot_mismatch")
    try:
        validate_source_writer_eligibility(
            writer_input=writer_input,
            source_artifact=source,
        )
    except AssertionAuditError as exc:
        raise SourceCopyError(
            "source_copy_writer_run_state_invalid", writer_input.writer_run.status
        ) from exc
    payload = _dict(source.content_json, "source_copy_source_draft_payload_invalid")
    if _canonical_hash(payload) != source.content_hash:
        raise SourceCopyError("source_copy_source_draft_snapshot_stale")
    try:
        draft = _validate_model_output(
            _dict(payload.get("draft"), "source_copy_draft_invalid"),
            writer_input=writer_input,
        )
    except WriterGenerationError as exc:
        raise SourceCopyError("source_copy_source_draft_invalid", exc.code) from exc
    if draft.to_dict() != payload.get("draft"):
        raise SourceCopyError("source_copy_source_draft_snapshot_stale")

    audit = await session.get(Artifact, assertion_audit_artifact_id)
    if (
        audit is None
        or audit.artifact_type != "assertion_audit"
        or audit.run_id == writer_run_id
        or audit.locale != locale
        or audit.version != expected_assertion_audit_version
        or audit.content_hash != expected_assertion_audit_hash
    ):
        raise SourceCopyError("source_copy_assertion_audit_snapshot_mismatch")
    audit_run = await session.get(ContentRun, audit.run_id)
    if (
        audit_run is None
        or audit_run.run_mode != "eval"
        or audit_run.status != "completed"
        or audit_run.project_id != writer_input.writer_run.project_id
        or audit_run.content_case_id != writer_input.writer_run.content_case_id
        or audit_run.locale_variant_id != writer_input.locale_variant.id
        or audit_run.settings_snapshot_id != writer_input.writer_run.settings_snapshot_id
    ):
        raise SourceCopyError("source_copy_assertion_audit_run_invalid")
    audit_payload = _dict(audit.content_json, "source_copy_assertion_audit_payload_invalid")
    if _canonical_hash(audit_payload) != audit.content_hash:
        raise SourceCopyError("source_copy_assertion_audit_snapshot_stale")
    generator = audit_payload.get("generator")
    if (
        not isinstance(generator, dict)
        or generator.get("schema_version") != ASSERTION_AUDIT_SCHEMA_VERSION
    ):
        raise SourceCopyError("source_copy_assertion_audit_generator_mismatch")
    if audit_payload.get("source_draft") != _source_ref(source):
        raise SourceCopyError("source_copy_assertion_audit_source_mismatch")
    if audit_payload.get("journal_outline") != _source_ref(writer_input.outline_artifact):
        raise SourceCopyError("source_copy_assertion_audit_outline_mismatch")
    bundle_refs = _bundle_refs(writer_input)
    if (
        audit_payload.get("evidence_set") != bundle_refs["evidence_set"]
        or audit_payload.get("originality_pack") != bundle_refs["originality_pack"]
    ):
        raise SourceCopyError("source_copy_assertion_audit_upstream_mismatch")
    raw_audit_segments = audit_payload.get("segments")
    if not isinstance(raw_audit_segments, list):
        raise SourceCopyError("source_copy_assertion_audit_segments_invalid")
    expected_segments = _source_segments(draft)
    if len(raw_audit_segments) != len(expected_segments):
        raise SourceCopyError("source_copy_assertion_audit_segment_count_mismatch")
    for expected_segment, raw_segment in zip(expected_segments, raw_audit_segments, strict=True):
        if not isinstance(raw_segment, dict):
            raise SourceCopyError("source_copy_assertion_audit_segment_invalid")
        raw_refs = raw_segment.get("assertions")
        if not isinstance(raw_refs, list):
            raise SourceCopyError("source_copy_assertion_audit_assertions_invalid")
        for raw_assertion in raw_refs:
            if not isinstance(raw_assertion, dict):
                raise SourceCopyError("source_copy_assertion_audit_assertion_invalid")
            raw_originality = raw_assertion.get("originality_refs")
            if not isinstance(raw_originality, list) or any(
                not isinstance(ref, str) or ref not in expected_segment.allowed_originality_refs
                for ref in raw_originality
            ):
                raise SourceCopyError("source_copy_assertion_audit_noncanonical_originality_ref")
    try:
        audit_input = await load_assertion_audit_input(
            session,
            writer_run_id=writer_run_id,
            revised_draft_artifact_id=source.id,
            expected_revised_draft_version=source.version,
            expected_revised_draft_hash=source.content_hash,
            outline_artifact_id=outline_artifact_id,
            expected_outline_version=expected_outline_version,
            expected_outline_hash=expected_outline_hash,
            locale=locale,
        )
        audit_segments = validate_assertion_audit_output(
            {"locale": locale, "segments": raw_audit_segments},
            audit_input=audit_input,
        )
    except Exception as exc:
        raise SourceCopyError("source_copy_assertion_audit_content_invalid", str(exc)) from exc
    audit_summary = _summary(audit_segments)
    if (
        audit_payload.get("summary") != audit_summary
        or audit_summary.get("result") not in {"pass", "warn"}
        or audit_summary.get("critical_unsupported_count") != 0
        or audit_summary.get("critical_contradicted_count") != 0
    ):
        raise SourceCopyError("source_copy_assertion_audit_not_pass")
    evaluation = await session.get(QualityEvaluation, assertion_audit_quality_evaluation_id)
    expected_findings = {
        "source_draft_id": str(source.id),
        "source_draft_hash": source.content_hash,
        "assertion_audit_artifact_id": str(audit.id),
        "assertion_audit_hash": audit.content_hash,
        **audit_summary,
    }
    if (
        evaluation is None
        or evaluation.run_id != audit.run_id
        or evaluation.artifact_id != audit.id
        or evaluation.evaluator_key != "assertion_audit_hard_gate"
        or (
            generator.get("version"),
            evaluation.evaluator_version,
        )
        not in _ASSERTION_AUDIT_VERSION_PAIRS
        or evaluation.evaluator_type != "deterministic"
        or evaluation.result != audit_summary.get("result")
        or evaluation.findings_json != expected_findings
    ):
        raise SourceCopyError("source_copy_assertion_audit_evaluation_mismatch")

    settings_snapshot = await session.get(
        SettingsSnapshot, writer_input.writer_run.settings_snapshot_id
    )
    if settings_snapshot is None:
        raise SourceCopyError("source_copy_settings_snapshot_missing")

    source_input = SourceCopyInput(
        writer_input=writer_input,
        source_artifact=source,
        source_draft=draft,
        assertion_audit_artifact=audit,
        assertion_audit_evaluation=evaluation,
        sources=(),
        segments=_source_segments(draft),
        settings_snapshot_hash=settings_snapshot.content_hash,
    )
    sources = await _build_sources(session, source_input=source_input)
    return SourceCopyInput(
        writer_input=writer_input,
        source_artifact=source,
        source_draft=draft,
        assertion_audit_artifact=audit,
        assertion_audit_evaluation=evaluation,
        sources=sources,
        segments=_source_segments(draft),
        settings_snapshot_hash=source_input.settings_snapshot_hash,
    )


def _thresholds() -> dict[str, int]:
    return {
        "ignore_max_tokens": SOURCE_COPY_IGNORE_MAX_TOKENS,
        "warn_min_tokens": SOURCE_COPY_WARN_MIN_TOKENS,
        "warn_max_tokens": SOURCE_COPY_WARN_MAX_TOKENS,
        "fail_min_tokens": SOURCE_COPY_FAIL_MIN_TOKENS,
    }


def _handoff_payload(
    *,
    source_input: SourceCopyInput,
    settings_snapshot: SettingsSnapshot,
    task_key: str,
) -> dict[str, object]:
    writer_run = source_input.writer_input.writer_run
    payload: dict[str, object] = {
        "schema_version": SOURCE_COPY_HANDOFF_SCHEMA_VERSION,
        "artifact_type": "source_copy_handoff",
        "task_key": task_key,
        "project_id": str(writer_run.project_id),
        "content_case_id": str(writer_run.content_case_id),
        "locale_variant": {
            "id": str(source_input.writer_input.locale_variant.id),
            "locale": source_input.writer_input.locale,
        },
        "source_writer_run_id": str(writer_run.id),
        "source_draft": _source_ref(source_input.source_artifact),
        "assertion_audit": {
            "artifact": _source_ref(source_input.assertion_audit_artifact),
            "quality_evaluation_id": str(source_input.assertion_audit_evaluation.id),
        },
        "journal_outline": _source_ref(source_input.writer_input.outline_artifact),
        **_bundle_refs(source_input.writer_input),
        "settings_snapshot": {
            "id": str(settings_snapshot.id),
            "content_hash": settings_snapshot.content_hash,
        },
        "algorithm": {
            "name": "exact_contiguous_normalized_token_overlap",
            "generator_version": SOURCE_COPY_GENERATOR_VERSION,
            "evaluator_key": SOURCE_COPY_EVALUATOR_KEY,
            "evaluator_version": SOURCE_COPY_EVALUATOR_VERSION,
            "schema_version": SOURCE_COPY_SCHEMA_VERSION,
            "thresholds": _thresholds(),
        },
    }
    return payload


def _validate_handoff(
    handoff: Artifact,
    *,
    payload: dict[str, object],
    source_input: SourceCopyInput,
    task_key: str,
) -> None:
    expected_locale = source_input.writer_input.locale
    if (
        handoff.artifact_type != "source_copy_handoff"
        or handoff.version != 1
        or handoff.step_run_id is not None
        or handoff.locale != expected_locale
        or handoff.content_json != payload
        or _canonical_hash(payload) != handoff.content_hash
        or handoff.run_id == source_input.writer_input.writer_run.id
        or payload.get("task_key") != task_key
    ):
        raise SourceCopyError("source_copy_handoff_snapshot_invalid")


async def ensure_source_copy_run(
    session: AsyncSession,
    *,
    source_input: SourceCopyInput,
    task_key: str,
) -> tuple[ContentRun, Artifact, bool]:
    if task_key != SOURCE_COPY_TASK_KEYS.get(source_input.writer_input.locale):
        raise SourceCopyError("source_copy_task_locale_mismatch")
    settings_snapshot = await session.get(
        SettingsSnapshot, source_input.writer_input.writer_run.settings_snapshot_id
    )
    if settings_snapshot is None:
        raise SourceCopyError("source_copy_settings_snapshot_missing")
    if (
        source_input.settings_snapshot_hash is not None
        and source_input.settings_snapshot_hash != settings_snapshot.content_hash
    ):
        raise SourceCopyError("source_copy_settings_snapshot_mismatch")
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
                    Artifact.artifact_type == "source_copy_handoff",
                    Artifact.content_hash == handoff_hash,
                )
            )
        ).all()
    )
    reusable: list[tuple[ContentRun, Artifact]] = []
    for handoff in handoffs:
        _validate_handoff(handoff, payload=payload, source_input=source_input, task_key=task_key)
        run = await session.get(ContentRun, handoff.run_id)
        if run is None:
            raise SourceCopyError("source_copy_handoff_run_missing")
        if (
            run.run_mode != "eval"
            or run.project_id != source_input.writer_input.writer_run.project_id
            or run.content_case_id != source_input.writer_input.writer_run.content_case_id
            or run.locale_variant_id != source_input.writer_input.locale_variant.id
            or run.content_item_id != source_input.writer_input.writer_run.content_item_id
            or run.settings_snapshot_id != source_input.writer_input.writer_run.settings_snapshot_id
        ):
            raise SourceCopyError("source_copy_handoff_run_mismatch")
        if run.status not in {"failed", "cancelled"}:
            reusable.append((run, handoff))
    if len(reusable) > 1:
        raise SourceCopyError("source_copy_reusable_run_duplicate")
    if reusable:
        return (*reusable[0], True)

    run = ContentRun(
        project_id=source_input.writer_input.writer_run.project_id,
        content_case_id=source_input.writer_input.writer_run.content_case_id,
        locale_variant_id=source_input.writer_input.locale_variant.id,
        content_item_id=source_input.writer_input.writer_run.content_item_id,
        run_mode="eval",
        status="pending",
        current_step=task_key,
        settings_snapshot_id=source_input.writer_input.writer_run.settings_snapshot_id,
        started_at=utc_now(),
    )
    session.add(run)
    await session.flush()
    handoff = Artifact(
        run_id=run.id,
        artifact_type="source_copy_handoff",
        locale=source_input.writer_input.locale,
        version=1,
        content_json=payload,
        content_hash=handoff_hash,
    )
    session.add(handoff)
    await session.flush()
    return run, handoff, False


async def _get_step(
    session: AsyncSession,
    *,
    run: ContentRun,
    task_key: str,
    input_refs: list[str],
) -> tuple[StepRun, bool]:
    rows = list(
        (
            await session.scalars(
                select(StepRun)
                .where(StepRun.run_id == run.id, StepRun.step_key == task_key)
                .order_by(StepRun.attempt, StepRun.created_at, StepRun.id)
            )
        ).all()
    )
    if len(rows) > 1:
        raise SourceCopyError("source_copy_step_attempt_conflict")
    if not rows:
        step = StepRun(
            run_id=run.id,
            step_key=task_key,
            attempt=1,
            status="pending",
            input_artifact_refs_json=input_refs,
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
        return step, True
    step = rows[0]
    if not set(input_refs).issubset(set(step.input_artifact_refs_json)):
        raise SourceCopyError("source_copy_step_input_mismatch")
    if step.status in {"failed", "skipped"}:
        raise SourceCopyError("source_copy_existing_step_terminal", step.status)
    return step, False


def _artifact_payload(
    *,
    source_input: SourceCopyInput,
    step: StepRun,
    check: SourceCopyCheck,
    fingerprint: str,
) -> dict[str, object]:
    return {
        "schema_version": SOURCE_COPY_SCHEMA_VERSION,
        "artifact_type": "source_copy_check",
        "locale": source_input.writer_input.locale,
        "generation_fingerprint": fingerprint,
        "source_writer_run_id": str(source_input.writer_input.writer_run.id),
        "source_draft": _source_ref(source_input.source_artifact),
        "assertion_audit": {
            "artifact": _source_ref(source_input.assertion_audit_artifact),
            "quality_evaluation_id": str(source_input.assertion_audit_evaluation.id),
        },
        "journal_outline": _source_ref(source_input.writer_input.outline_artifact),
        **_bundle_refs(source_input.writer_input),
        "settings_snapshot_id": str(source_input.writer_input.writer_run.settings_snapshot_id),
        "settings_snapshot_hash": source_input.settings_snapshot_hash,
        "algorithm": {
            "name": "exact_contiguous_normalized_token_overlap",
            "generator_version": SOURCE_COPY_GENERATOR_VERSION,
            "evaluator_key": SOURCE_COPY_EVALUATOR_KEY,
            "evaluator_version": SOURCE_COPY_EVALUATOR_VERSION,
            "schema_version": SOURCE_COPY_SCHEMA_VERSION,
            "thresholds": _thresholds(),
        },
        "coverage_limitations": [
            "No semantic paraphrase or fuzzy similarity.",
            "No translation similarity.",
            "No published-corpus or Golden-example comparison.",
            "Only locked EvidenceSet excerpts and approved OriginalityPack text fields "
            "were checked.",
        ],
        "execution_context": {"step_run_id": str(step.id)},
        "source_corpus": [source.to_dict() for source in source_input.sources],
        "segments": [
            {
                "segment_id": segment.segment_id,
                "location": segment.location,
                "source_text": segment.source_text,
            }
            for segment in source_input.segments
        ],
        "findings": [finding.to_dict() for finding in check.findings],
        "summary": check.summary(),
        "model_calls": 0,
        "provider_calls": 0,
        "tool_calls": 0,
    }


def _fingerprint(source_input: SourceCopyInput, *, task_key: str) -> str:
    return _canonical_hash(
        {
            "task_key": task_key,
            "locale": source_input.writer_input.locale,
            "source_writer_run_id": str(source_input.writer_input.writer_run.id),
            "source_draft": _source_ref(source_input.source_artifact),
            "assertion_audit": {
                "artifact": _source_ref(source_input.assertion_audit_artifact),
                "quality_evaluation_id": str(source_input.assertion_audit_evaluation.id),
            },
            "journal_outline": _source_ref(source_input.writer_input.outline_artifact),
            **_bundle_refs(source_input.writer_input),
            "settings_snapshot_id": str(source_input.writer_input.writer_run.settings_snapshot_id),
            "settings_snapshot_hash": source_input.settings_snapshot_hash,
            "generator_version": SOURCE_COPY_GENERATOR_VERSION,
            "evaluator_key": SOURCE_COPY_EVALUATOR_KEY,
            "evaluator_version": SOURCE_COPY_EVALUATOR_VERSION,
            "schema_version": SOURCE_COPY_SCHEMA_VERSION,
            "thresholds": _thresholds(),
        }
    )


def _validate_persisted_artifact(
    artifact: Artifact,
    *,
    source_input: SourceCopyInput,
    step: StepRun,
    fingerprint: str,
) -> SourceCopyCheck:
    if (
        artifact.artifact_type != "source_copy_check"
        or artifact.locale != source_input.writer_input.locale
        or artifact.run_id != step.run_id
        or artifact.step_run_id != step.id
        or artifact.version != 1
    ):
        raise SourceCopyError("source_copy_artifact_binding_mismatch")
    payload = _dict(artifact.content_json, "source_copy_artifact_payload_invalid")
    if payload.get("generation_fingerprint") != fingerprint:
        raise SourceCopyError("source_copy_artifact_fingerprint_mismatch")
    if _canonical_hash(payload) != artifact.content_hash:
        raise SourceCopyError("source_copy_artifact_snapshot_stale")
    if payload.get("findings") is None or payload.get("summary") is None:
        raise SourceCopyError("source_copy_artifact_result_missing")
    raw_findings = payload.get("findings")
    summary = payload.get("summary")
    if not isinstance(raw_findings, list) or not isinstance(summary, dict):
        raise SourceCopyError("source_copy_artifact_result_invalid")
    findings: list[SourceCopyFinding] = []
    for raw in raw_findings:
        if not isinstance(raw, dict) or raw.get("classification") not in {"warn", "fail"}:
            raise SourceCopyError("source_copy_finding_invalid")
        string_fields = (
            "locale",
            "draft_segment_id",
            "draft_location",
            "draft_text",
            "source_kind",
            "source_ref",
            "source_field",
            "source_text_hash",
            "normalized_match",
            "classification",
        )
        if any(not isinstance(raw.get(field), str) for field in string_fields):
            raise SourceCopyError("source_copy_finding_invalid")
        if not isinstance(raw.get("matched_draft_span"), dict) or not isinstance(
            raw.get("matched_source_span"), dict
        ):
            raise SourceCopyError("source_copy_finding_invalid")
        overlap = raw.get("overlap_token_count")
        if not isinstance(overlap, int) or isinstance(overlap, bool):
            raise SourceCopyError("source_copy_finding_invalid")
        findings.append(
            SourceCopyFinding(
                locale=cast(str, raw["locale"]),
                draft_segment_id=cast(str, raw["draft_segment_id"]),
                draft_location=cast(str, raw["draft_location"]),
                draft_text=cast(str, raw["draft_text"]),
                source_kind=cast(str, raw["source_kind"]),
                source_ref=cast(str, raw["source_ref"]),
                source_field=cast(str, raw["source_field"]),
                source_text_hash=cast(str, raw["source_text_hash"]),
                matched_draft_span=cast(dict[str, object], raw["matched_draft_span"]),
                matched_source_span=cast(dict[str, object], raw["matched_source_span"]),
                normalized_match=cast(str, raw["normalized_match"]),
                overlap_token_count=overlap,
                classification=cast(str, raw["classification"]),
            )
        )
    expected = check_source_copy(
        locale=source_input.writer_input.locale,
        segments=source_input.segments,
        sources=source_input.sources,
    )
    expected_payload = _artifact_payload(
        source_input=source_input,
        step=step,
        check=expected,
        fingerprint=fingerprint,
    )
    if payload != expected_payload:
        raise SourceCopyError("source_copy_artifact_provenance_mismatch")
    if tuple(finding.to_dict() for finding in findings) != tuple(
        finding.to_dict() for finding in expected.findings
    ) or summary != expected.summary():
        raise SourceCopyError("source_copy_artifact_result_stale")
    return expected


async def _existing_result(
    session: AsyncSession,
    *,
    run: ContentRun,
    handoff: Artifact,
    step: StepRun,
    source_input: SourceCopyInput,
    fingerprint: str,
) -> SourceCopyResult | None:
    artifacts = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == run.id,
                    Artifact.artifact_type == "source_copy_check",
                    Artifact.locale == source_input.writer_input.locale,
                )
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
    if len(matching) != 1 or run.status != "completed" or step.status != "completed":
        raise SourceCopyError("source_copy_completed_state_mismatch")
    check = _validate_persisted_artifact(
        matching[0], source_input=source_input, step=step, fingerprint=fingerprint
    )
    evaluations = list(
        (
            await session.scalars(
                select(QualityEvaluation).where(
                    QualityEvaluation.run_id == run.id,
                    QualityEvaluation.artifact_id == matching[0].id,
                    QualityEvaluation.evaluator_key == SOURCE_COPY_EVALUATOR_KEY,
                    QualityEvaluation.evaluator_version == SOURCE_COPY_EVALUATOR_VERSION,
                )
            )
        ).all()
    )
    if len(evaluations) != 1 or evaluations[0].result != check.result:
        raise SourceCopyError("source_copy_quality_evaluation_missing_or_stale")
    return SourceCopyResult(
        eval_run=run,
        handoff=handoff,
        step_run=step,
        artifact=matching[0],
        evaluation=evaluations[0],
        check=check,
        reused=True,
    )


class SourceCopyGenerator:
    """Run the basic exact-overlap check without a model."""

    async def check_draft(
        self,
        session: AsyncSession,
        *,
        source_input: SourceCopyInput,
        eval_run: ContentRun,
        handoff: Artifact,
        step: StepRun,
        task_key: str,
    ) -> SourceCopyResult:
        if eval_run.status in {"completed", "failed", "cancelled"}:
            raise SourceCopyError("source_copy_eval_run_state_invalid", eval_run.status)
        if (
            step.run_id != eval_run.id
            or step.step_key != task_key
            or handoff.run_id != eval_run.id
        ):
            raise SourceCopyError("source_copy_ownership_mismatch")
        fingerprint = _fingerprint(source_input, task_key=task_key)
        existing = await _existing_result(
            session,
            run=eval_run,
            handoff=handoff,
            step=step,
            source_input=source_input,
            fingerprint=fingerprint,
        )
        if existing is not None:
            return existing
        if eval_run.status != "running" or step.status != "running":
            raise SourceCopyError("source_copy_generation_state_invalid")
        check = check_source_copy(
            locale=source_input.writer_input.locale,
            segments=source_input.segments,
            sources=source_input.sources,
        )
        payload = _artifact_payload(
            source_input=source_input,
            step=step,
            check=check,
            fingerprint=fingerprint,
        )
        artifact = Artifact(
            run_id=eval_run.id,
            step_run_id=step.id,
            artifact_type="source_copy_check",
            locale=source_input.writer_input.locale,
            version=1,
            content_json=payload,
            content_hash=_canonical_hash(payload),
        )
        session.add(artifact)
        await session.flush()
        step.output_artifact_refs_json = [*step.output_artifact_refs_json, str(artifact.id)]
        evaluation = QualityEvaluation(
            run_id=eval_run.id,
            artifact_id=artifact.id,
            evaluator_key=SOURCE_COPY_EVALUATOR_KEY,
            evaluator_version=SOURCE_COPY_EVALUATOR_VERSION,
            evaluator_type="deterministic",
            result=check.result,
            score=None,
            severity=(
                "high"
                if check.result == "fail"
                else ("medium" if check.result == "warn" else "none")
            ),
            findings_json={
                "source_copy_artifact_id": str(artifact.id),
                "source_copy_artifact_hash": artifact.content_hash,
                **check.summary(),
            },
        )
        session.add(evaluation)
        await session.flush()
        return SourceCopyResult(
            eval_run=eval_run,
            handoff=handoff,
            step_run=step,
            artifact=artifact,
            evaluation=evaluation,
            check=check,
            reused=False,
        )


async def execute_source_copy(
    session: AsyncSession,
    *,
    source_input: SourceCopyInput,
    task_key: str,
) -> SourceCopyResult:
    eval_run, handoff, _run_reused = await ensure_source_copy_run(
        session, source_input=source_input, task_key=task_key
    )
    input_refs = [
        str(handoff.id),
        str(source_input.source_artifact.id),
        str(source_input.assertion_audit_artifact.id),
        str(source_input.writer_input.outline_artifact.id),
    ]
    step, step_created = await _get_step(
        session, run=eval_run, task_key=task_key, input_refs=input_refs
    )
    fingerprint = _fingerprint(source_input, task_key=task_key)
    if eval_run.status == "completed" and step.status == "completed":
        existing = await _existing_result(
            session,
            run=eval_run,
            handoff=handoff,
            step=step,
            source_input=source_input,
            fingerprint=fingerprint,
        )
        if existing is None:
            raise SourceCopyError("source_copy_completed_artifact_missing")
        return existing
    try:
        if eval_run.status == "pending":
            await transition_run(session, run_id=eval_run.id, status="running")
            eval_run.current_step = task_key
        if step.status == "pending":
            await transition_step_run(session, step_run_id=step.id, status="running")
        result = await SourceCopyGenerator().check_draft(
            session,
            source_input=source_input,
            eval_run=eval_run,
            handoff=handoff,
            step=step,
            task_key=task_key,
        )
        if not result.reused:
            await transition_step_run(session, step_run_id=step.id, status="completed")
            await transition_run(session, run_id=eval_run.id, status="completed")
        return result
    except Exception as exc:
        if step.status == "running":
            step.error_json = {"code": str(getattr(exc, "code", exc.__class__.__name__))}
            await transition_step_run(session, step_run_id=step.id, status="failed")
        if eval_run.status == "running":
            eval_run.failure_code = str(getattr(exc, "code", exc.__class__.__name__))
            await transition_run(session, run_id=eval_run.id, status="failed")
        raise


__all__ = [
    "SOURCE_COPY_EVALUATOR_KEY",
    "SOURCE_COPY_EVALUATOR_VERSION",
    "SOURCE_COPY_GENERATOR_VERSION",
    "SOURCE_COPY_SCHEMA_VERSION",
    "SOURCE_COPY_TASK_KEYS",
    "SourceCopyCheck",
    "SourceCopyError",
    "SourceCopyFinding",
    "SourceCopyGenerator",
    "SourceCopyInput",
    "SourceCopyResult",
    "SourceCopySource",
    "check_source_copy",
    "classify_source_copy_overlap",
    "execute_source_copy",
    "load_source_copy_input",
    "normalize_source_copy_text",
    "normalize_source_copy_tokens",
]
