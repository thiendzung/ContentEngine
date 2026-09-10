"""CE05 T05.14 bounded assertion audit for immutable revised Journal drafts."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.review_revise import unresolved_factual_claims
from app.modules.content_engine.journal.writer import (
    JournalDraft,
    WriterGenerationError,
    WriterInput,
    _canonical_hash,
    _dict,
    _execution_manifest,
    _model_identity,
    _normalize_evidence_refs,
    _normalize_originality_refs,
    _text,
    _validate_model_output,
    load_writer_input,
    writer_model_input_hash,
)
from app.modules.harness.models import Artifact, ContextManifest, QualityEvaluation, StepRun
from app.modules.knowledge.models import Claim, Evidence, EvidenceSet

ASSERTION_AUDIT_GENERATOR_VERSION = "ce05.journal_assertion_audit.v1"
ASSERTION_AUDIT_SCHEMA_VERSION = 1
ASSERTION_AUDIT_EVALUATOR_VERSION = "ce05.assertion_audit.hard_gate.v1"
ASSERTION_AUDIT_EVALUATOR_KEY = "assertion_audit_hard_gate"

_ASSERTION_TYPES = {
    "fact",
    "brand_statement",
    "artist_intent",
    "interpretation",
    "opinion",
    "visual_observation",
    "practical_live_information",
}
_SUPPORT_STATUSES = {"supported", "unsupported", "contradicted", "interpretation", "opinion"}
_SEVERITIES = {"none", "low", "medium", "high", "critical"}
_HARD_FAIL_TYPES = {
    "fact",
    "brand_statement",
    "artist_intent",
    "visual_observation",
    "practical_live_information",
}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class AssertionAuditModelPort(Protocol):
    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class AuditSourceSegment:
    segment_id: str
    location: str
    source_text: str
    required_assertive: bool
    allowed_evidence_refs: tuple[str, ...]
    allowed_originality_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "segment_id": self.segment_id,
            "location": self.location,
            "source_text": self.source_text,
            "required_assertive": self.required_assertive,
            "allowed_evidence_refs": list(self.allowed_evidence_refs),
            "allowed_originality_refs": list(self.allowed_originality_refs),
        }


@dataclass(frozen=True, slots=True)
class AuditedAssertion:
    assertion_text: str
    assertion_type: str
    support_status: str
    severity: str
    evidence_refs: tuple[str, ...]
    originality_refs: tuple[str, ...]
    claim_refs: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return {
            "assertion_text": self.assertion_text,
            "assertion_type": self.assertion_type,
            "support_status": self.support_status,
            "severity": self.severity,
            "evidence_refs": list(self.evidence_refs),
            "originality_refs": list(self.originality_refs),
            "claim_refs": list(self.claim_refs),
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class AuditedSegment:
    segment_id: str
    location: str
    source_text: str
    disposition: str
    non_assertive_reason: str
    assertions: tuple[AuditedAssertion, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "segment_id": self.segment_id,
            "location": self.location,
            "source_text": self.source_text,
            "disposition": self.disposition,
            "non_assertive_reason": self.non_assertive_reason,
            "assertions": [assertion.to_dict() for assertion in self.assertions],
        }


@dataclass(frozen=True, slots=True)
class AssertionAuditInput:
    writer_input: WriterInput
    source_artifact: Artifact
    source_draft: JournalDraft
    segments: tuple[AuditSourceSegment, ...]
    evidence_claim_refs: dict[str, str]
    evidence_relations: dict[str, str]
    model_input: dict[str, object]


@dataclass(frozen=True, slots=True)
class AssertionAuditResult:
    artifact: Artifact
    evaluation: QualityEvaluation
    segments: tuple[AuditedSegment, ...]
    result: str
    critical_unsupported_count: int
    critical_contradicted_count: int
    unsupported_count: int
    contradicted_count: int
    model_attempts: int
    reused: bool


class AssertionAuditError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def _string_list(value: object, code: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise AssertionAuditError(code)
    return [item.strip() for item in value]


def _split_sentences(value: str) -> tuple[str, ...]:
    parts: list[str] = []
    for paragraph in value.splitlines():
        text = paragraph.strip()
        if not text:
            continue
        parts.extend(part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip())
    return tuple(parts)


def _source_segments(draft: JournalDraft) -> tuple[AuditSourceSegment, ...]:
    segments: list[AuditSourceSegment] = [
        AuditSourceSegment(
            segment_id="title",
            location="title",
            source_text=draft.title,
            required_assertive=False,
            allowed_evidence_refs=(),
            allowed_originality_refs=(),
        ),
        AuditSourceSegment(
            segment_id="standfirst",
            location="standfirst",
            source_text=draft.standfirst,
            required_assertive=True,
            allowed_evidence_refs=draft.lead_evidence_refs,
            allowed_originality_refs=draft.lead_originality_refs,
        ),
    ]
    for index, sentence in enumerate(_split_sentences(draft.lead_markdown), start=1):
        segments.append(
            AuditSourceSegment(
                segment_id=f"lead:{index}",
                location="lead",
                source_text=sentence,
                required_assertive=True,
                allowed_evidence_refs=draft.lead_evidence_refs,
                allowed_originality_refs=draft.lead_originality_refs,
            )
        )
    for section in draft.sections:
        segments.append(
            AuditSourceSegment(
                segment_id=f"section:{section.section_id}:heading",
                location=f"section:{section.section_id}:heading",
                source_text=section.heading,
                required_assertive=False,
                allowed_evidence_refs=section.evidence_refs,
                allowed_originality_refs=section.originality_refs,
            )
        )
        for index, sentence in enumerate(_split_sentences(section.body_markdown), start=1):
            segments.append(
                AuditSourceSegment(
                    segment_id=f"section:{section.section_id}:{index}",
                    location=f"section:{section.section_id}",
                    source_text=sentence,
                    required_assertive=True,
                    allowed_evidence_refs=section.evidence_refs,
                    allowed_originality_refs=section.originality_refs,
                )
            )
    for index, sentence in enumerate(_split_sentences(draft.closing_markdown), start=1):
        segments.append(
            AuditSourceSegment(
                segment_id=f"closing:{index}",
                location="closing",
                source_text=sentence,
                required_assertive=True,
                allowed_evidence_refs=(),
                allowed_originality_refs=(),
            )
        )
    return tuple(segments)


async def _evidence_catalog(
    session: AsyncSession,
    *,
    writer_input: WriterInput,
    segments: tuple[AuditSourceSegment, ...],
) -> tuple[list[dict[str, object]], dict[str, str], dict[str, str]]:
    bundle = writer_input.outline_input.bundle
    evidence_set = await session.get(EvidenceSet, bundle.evidence_set_id)
    if evidence_set is None:
        raise AssertionAuditError("assertion_audit_evidence_set_missing")
    if (
        evidence_set.version != bundle.evidence_set_version
        or evidence_set.content_hash != bundle.evidence_set_hash
        or evidence_set.status != "locked"
    ):
        raise AssertionAuditError("assertion_audit_evidence_set_snapshot_mismatch")

    allowed_set = set(evidence_set.evidence_ids_json)
    used_ids = sorted({ref for segment in segments for ref in segment.allowed_evidence_refs})
    if any(ref not in allowed_set for ref in used_ids):
        raise AssertionAuditError("assertion_audit_evidence_outside_locked_set")
    if not used_ids:
        return [], {}, {}

    parsed_ids = [UUID(value) for value in used_ids]
    rows = list((await session.scalars(select(Evidence).where(Evidence.id.in_(parsed_ids)))).all())
    by_id = {str(row.id): row for row in rows}
    if set(by_id) != set(used_ids):
        raise AssertionAuditError("assertion_audit_evidence_row_missing")

    catalog: list[dict[str, object]] = []
    claim_refs: dict[str, str] = {}
    relations: dict[str, str] = {}
    for evidence_id in used_ids:
        evidence = by_id[evidence_id]
        claim = await session.get(Claim, evidence.claim_id)
        if claim is None:
            raise AssertionAuditError("assertion_audit_claim_missing", evidence_id)
        claim_refs[evidence_id] = str(claim.id)
        relations[evidence_id] = evidence.relation
        catalog.append(
            {
                "evidence_id": evidence_id,
                "claim_id": str(claim.id),
                "claim_statement": claim.statement,
                "claim_type": claim.claim_type,
                "claim_importance": claim.importance,
                "evidence_relation": evidence.relation,
                "authority_level": evidence.authority_level,
                "evidence_excerpt": evidence.excerpt,
            }
        )
    return catalog, claim_refs, relations


def _source_payload(
    artifact: Artifact,
    *,
    writer_input: WriterInput,
) -> tuple[dict[str, object], JournalDraft]:
    if artifact.artifact_type != "journal_draft" or artifact.run_id != writer_input.writer_run.id:
        raise AssertionAuditError("assertion_audit_source_lineage_mismatch")
    if artifact.locale != writer_input.locale:
        raise AssertionAuditError("assertion_audit_source_locale_mismatch")
    payload = _dict(artifact.content_json, "assertion_audit_source_payload_invalid")
    if _canonical_hash(payload) != artifact.content_hash:
        raise AssertionAuditError("assertion_audit_source_snapshot_stale")
    draft_payload = _dict(payload.get("draft"), "assertion_audit_source_draft_invalid")
    try:
        draft = _validate_model_output(draft_payload, writer_input=writer_input)
    except WriterGenerationError as exc:
        raise AssertionAuditError("assertion_audit_source_draft_invalid", exc.code) from exc
    if draft.to_dict() != draft_payload:
        raise AssertionAuditError("assertion_audit_source_draft_payload_stale")
    if unresolved_factual_claims(draft):
        raise AssertionAuditError("assertion_audit_source_unresolved_claims")
    return payload, draft


async def load_assertion_audit_input(
    session: AsyncSession,
    *,
    writer_run_id: UUID,
    revised_draft_artifact_id: UUID,
    expected_revised_draft_version: int,
    expected_revised_draft_hash: str,
    outline_artifact_id: UUID,
    expected_outline_version: int,
    expected_outline_hash: str,
    locale: str,
) -> AssertionAuditInput:
    writer_input = await load_writer_input(
        session,
        writer_run_id=writer_run_id,
        outline_artifact_id=outline_artifact_id,
        expected_outline_version=expected_outline_version,
        expected_outline_hash=expected_outline_hash,
        locale=locale,
    )
    source = await session.get(Artifact, revised_draft_artifact_id)
    if source is None:
        raise AssertionAuditError("assertion_audit_source_draft_not_found")
    if (
        source.version != expected_revised_draft_version
        or source.content_hash != expected_revised_draft_hash
    ):
        raise AssertionAuditError("assertion_audit_source_snapshot_mismatch")
    _payload, draft = _source_payload(source, writer_input=writer_input)
    segments = _source_segments(draft)
    catalog, claim_refs, relations = await _evidence_catalog(
        session,
        writer_input=writer_input,
        segments=segments,
    )
    originality_pack = copy.deepcopy(writer_input.model_input.get("originality_pack"))
    model_input: dict[str, object] = {
        "locale": writer_input.locale,
        "source_draft_ref": {
            "id": str(source.id),
            "version": source.version,
            "content_hash": source.content_hash,
        },
        "source_draft": draft.to_dict(),
        "source_segments": [segment.to_dict() for segment in segments],
        "evidence_catalog": catalog,
        "originality_pack": originality_pack,
        "audit_policy": {
            "mode": "bounded_assertion_audit",
            "requirements": [
                "audit_every_required_source_segment",
                "copy_source_text_and_assertion_text_verbatim",
                "use_only_location_allowed_support_refs",
                "distinguish_external_fact_from_editorial_guidance",
                "do_not_treat_negated_investment_or_scarcity_guards_as_promotional_claims",
                "do_not_treat_generic_live_data_guidance_as_a_concrete_current_commerce_fact",
                "never_add_research_or_new_facts",
                "critical_unsupported_or_contradicted_assertions_fail",
            ],
        },
    }
    return AssertionAuditInput(
        writer_input=writer_input,
        source_artifact=source,
        source_draft=draft,
        segments=segments,
        evidence_claim_refs=claim_refs,
        evidence_relations=relations,
        model_input=model_input,
    )


def _severity_for(
    *,
    assertion_type: str,
    support_status: str,
    model_severity: str,
) -> str:
    if support_status in {"unsupported", "contradicted"} and assertion_type in _HARD_FAIL_TYPES:
        return "critical"
    if support_status == "contradicted" and model_severity in {"none", "low", "medium"}:
        return "high"
    if support_status == "unsupported" and model_severity == "none":
        return "medium"
    return model_severity


def _validate_assertion(
    raw: object,
    *,
    segment: AuditSourceSegment,
    audit_input: AssertionAuditInput,
) -> AuditedAssertion:
    value = _dict(raw, "assertion_audit_assertion_invalid")
    assertion_text = _text(value.get("assertion_text"), "assertion_audit_assertion_text_required")
    if assertion_text not in segment.source_text:
        raise AssertionAuditError("assertion_audit_assertion_not_verbatim", segment.segment_id)
    assertion_type = _text(value.get("assertion_type"), "assertion_audit_type_required")
    if assertion_type not in _ASSERTION_TYPES:
        raise AssertionAuditError("assertion_audit_type_invalid", assertion_type)
    support_status = _text(value.get("support_status"), "assertion_audit_support_required")
    if support_status not in _SUPPORT_STATUSES:
        raise AssertionAuditError("assertion_audit_support_invalid", support_status)
    model_severity = _text(value.get("severity"), "assertion_audit_severity_required")
    if model_severity not in _SEVERITIES:
        raise AssertionAuditError("assertion_audit_severity_invalid", model_severity)
    try:
        evidence_refs = _normalize_evidence_refs(
            value.get("evidence_refs"),
            "assertion_audit_evidence_refs_invalid",
        )
        originality_refs = _normalize_originality_refs(
            value.get("originality_refs"),
            "assertion_audit_originality_refs_invalid",
        )
    except WriterGenerationError as exc:
        raise AssertionAuditError(exc.code) from exc
    if any(ref not in segment.allowed_evidence_refs for ref in evidence_refs):
        raise AssertionAuditError(
            "assertion_audit_evidence_ref_outside_location",
            segment.segment_id,
        )
    if any(ref not in segment.allowed_originality_refs for ref in originality_refs):
        raise AssertionAuditError(
            "assertion_audit_originality_ref_outside_location",
            segment.segment_id,
        )
    if support_status == "supported" and not evidence_refs and not originality_refs:
        raise AssertionAuditError("assertion_audit_supported_without_ref", segment.segment_id)
    if support_status == "interpretation" and assertion_type not in {
        "interpretation",
        "brand_statement",
    }:
        raise AssertionAuditError("assertion_audit_interpretation_type_mismatch")
    if support_status == "opinion" and assertion_type != "opinion":
        raise AssertionAuditError("assertion_audit_opinion_type_mismatch")
    if assertion_type == "artist_intent" and support_status != "supported":
        model_severity = "critical"
    for evidence_ref in evidence_refs:
        relation = audit_input.evidence_relations[evidence_ref]
        if support_status == "supported" and relation not in {"supports", "qualifies"}:
            raise AssertionAuditError("assertion_audit_evidence_relation_not_supportive")
    claim_refs = tuple(audit_input.evidence_claim_refs[ref] for ref in evidence_refs)
    severity = _severity_for(
        assertion_type=assertion_type,
        support_status=support_status,
        model_severity=model_severity,
    )
    return AuditedAssertion(
        assertion_text=assertion_text,
        assertion_type=assertion_type,
        support_status=support_status,
        severity=severity,
        evidence_refs=evidence_refs,
        originality_refs=originality_refs,
        claim_refs=claim_refs,
        rationale=_text(value.get("rationale"), "assertion_audit_rationale_required"),
    )


def validate_assertion_audit_output(
    raw: object,
    *,
    audit_input: AssertionAuditInput,
) -> tuple[AuditedSegment, ...]:
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AssertionAuditError("assertion_audit_output_json_invalid") from exc
    payload = _dict(raw, "assertion_audit_output_invalid")
    if payload.get("locale") != audit_input.writer_input.locale:
        raise AssertionAuditError("assertion_audit_output_locale_mismatch")
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list) or len(raw_segments) != len(audit_input.segments):
        raise AssertionAuditError("assertion_audit_segment_count_mismatch")

    audited: list[AuditedSegment] = []
    for source, raw_segment in zip(audit_input.segments, raw_segments, strict=True):
        value = _dict(raw_segment, "assertion_audit_segment_invalid")
        if (
            value.get("segment_id") != source.segment_id
            or value.get("source_text") != source.source_text
        ):
            raise AssertionAuditError(
                "assertion_audit_segment_snapshot_mismatch",
                source.segment_id,
            )
        disposition = _text(value.get("disposition"), "assertion_audit_disposition_required")
        if disposition not in {"assertive", "non_assertive"}:
            raise AssertionAuditError("assertion_audit_disposition_invalid")
        reason = value.get("non_assertive_reason")
        if not isinstance(reason, str):
            raise AssertionAuditError("assertion_audit_non_assertive_reason_invalid")
        raw_assertions = value.get("assertions")
        if not isinstance(raw_assertions, list):
            raise AssertionAuditError("assertion_audit_assertions_invalid")
        if source.required_assertive and disposition != "assertive":
            raise AssertionAuditError(
                "assertion_audit_required_segment_not_audited",
                source.segment_id,
            )
        if disposition == "assertive" and not raw_assertions:
            raise AssertionAuditError("assertion_audit_assertive_segment_empty", source.segment_id)
        if disposition == "non_assertive" and raw_assertions:
            raise AssertionAuditError(
                "assertion_audit_non_assertive_has_assertions",
                source.segment_id,
            )
        assertions = tuple(
            _validate_assertion(item, segment=source, audit_input=audit_input)
            for item in raw_assertions
        )
        audited.append(
            AuditedSegment(
                segment_id=source.segment_id,
                location=source.location,
                source_text=source.source_text,
                disposition=disposition,
                non_assertive_reason=reason.strip(),
                assertions=assertions,
            )
        )
    return tuple(audited)


def _summary(segments: tuple[AuditedSegment, ...]) -> dict[str, int | str]:
    assertions = [assertion for segment in segments for assertion in segment.assertions]
    critical_unsupported = sum(
        assertion.support_status == "unsupported" and assertion.severity == "critical"
        for assertion in assertions
    )
    critical_contradicted = sum(
        assertion.support_status == "contradicted" and assertion.severity == "critical"
        for assertion in assertions
    )
    unsupported = sum(assertion.support_status == "unsupported" for assertion in assertions)
    contradicted = sum(assertion.support_status == "contradicted" for assertion in assertions)
    if critical_unsupported or critical_contradicted:
        result = "fail"
    elif unsupported or contradicted:
        result = "warn"
    else:
        result = "pass"
    return {
        "result": result,
        "assertion_count": len(assertions),
        "critical_unsupported_count": critical_unsupported,
        "critical_contradicted_count": critical_contradicted,
        "unsupported_count": unsupported,
        "contradicted_count": contradicted,
    }


def _fingerprint(
    *,
    audit_input: AssertionAuditInput,
    model_input_hash: str,
    provider: str,
    model: str,
    prompt_version: str,
    recipe_version: str,
    context_manifest_hash: str,
) -> str:
    return _canonical_hash(
        {
            "source_draft_id": str(audit_input.source_artifact.id),
            "source_draft_version": audit_input.source_artifact.version,
            "source_draft_hash": audit_input.source_artifact.content_hash,
            "locale": audit_input.writer_input.locale,
            "model_input_hash": model_input_hash,
            "provider": provider,
            "model": model,
            "prompt_version": prompt_version,
            "recipe_version": recipe_version,
            "context_manifest_hash": context_manifest_hash,
            "generator_version": ASSERTION_AUDIT_GENERATOR_VERSION,
            "schema_version": ASSERTION_AUDIT_SCHEMA_VERSION,
        }
    )


async def _evaluation_for(
    session: AsyncSession,
    *,
    artifact: Artifact,
) -> QualityEvaluation:
    rows = list(
        (
            await session.scalars(
                select(QualityEvaluation).where(
                    QualityEvaluation.run_id == artifact.run_id,
                    QualityEvaluation.artifact_id == artifact.id,
                    QualityEvaluation.evaluator_key == ASSERTION_AUDIT_EVALUATOR_KEY,
                    QualityEvaluation.evaluator_version == ASSERTION_AUDIT_EVALUATOR_VERSION,
                )
            )
        ).all()
    )
    if len(rows) != 1:
        raise AssertionAuditError("assertion_audit_quality_evaluation_missing_or_duplicate")
    return rows[0]


async def _existing_audit(
    session: AsyncSession,
    *,
    audit_input: AssertionAuditInput,
    fingerprint: str,
) -> AssertionAuditResult | None:
    artifacts = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == audit_input.writer_input.writer_run.id,
                    Artifact.artifact_type == "assertion_audit",
                    Artifact.locale == audit_input.writer_input.locale,
                )
            )
        ).all()
    )
    matching: list[Artifact] = []
    for artifact in artifacts:
        payload = artifact.content_json
        if isinstance(payload, dict) and payload.get("generation_fingerprint") == fingerprint:
            if _canonical_hash(payload) != artifact.content_hash:
                raise AssertionAuditError("assertion_audit_artifact_snapshot_stale")
            matching.append(artifact)
    if not matching:
        return None
    if len(matching) != 1:
        raise AssertionAuditError("assertion_audit_artifact_duplicate")
    artifact = matching[0]
    payload = _dict(artifact.content_json, "assertion_audit_artifact_payload_invalid")
    raw_segments = payload.get("segments")
    raw_output = {"locale": audit_input.writer_input.locale, "segments": raw_segments}
    segments = validate_assertion_audit_output(raw_output, audit_input=audit_input)
    summary = _summary(segments)
    if payload.get("summary") != summary:
        raise AssertionAuditError("assertion_audit_summary_stale")
    evaluation = await _evaluation_for(session, artifact=artifact)
    if evaluation.result != summary["result"]:
        raise AssertionAuditError("assertion_audit_evaluation_stale")
    result = summary["result"]
    if not isinstance(result, str):
        raise AssertionAuditError("assertion_audit_summary_result_invalid")
    return AssertionAuditResult(
        artifact=artifact,
        evaluation=evaluation,
        segments=segments,
        result=result,
        critical_unsupported_count=cast(int, summary["critical_unsupported_count"]),
        critical_contradicted_count=cast(int, summary["critical_contradicted_count"]),
        unsupported_count=cast(int, summary["unsupported_count"]),
        contradicted_count=cast(int, summary["contradicted_count"]),
        model_attempts=0,
        reused=True,
    )


async def _persist_audit(
    session: AsyncSession,
    *,
    audit_input: AssertionAuditInput,
    segments: tuple[AuditedSegment, ...],
    model_input_hash: str,
    fingerprint: str,
    provider: str,
    model: str,
    model_attempts: int,
    prompt_version: str,
    recipe_version: str,
    context_manifest: ContextManifest,
) -> AssertionAuditResult:
    summary = _summary(segments)
    payload: dict[str, object] = {
        "schema_version": ASSERTION_AUDIT_SCHEMA_VERSION,
        "artifact_type": "assertion_audit",
        "locale": audit_input.writer_input.locale,
        "generation_fingerprint": fingerprint,
        "source_draft": {
            "id": str(audit_input.source_artifact.id),
            "version": audit_input.source_artifact.version,
            "content_hash": audit_input.source_artifact.content_hash,
        },
        "journal_outline": {
            "id": str(audit_input.writer_input.outline_artifact.id),
            "version": audit_input.writer_input.outline_artifact.version,
            "content_hash": audit_input.writer_input.outline_artifact.content_hash,
        },
        "evidence_set": {
            "id": str(audit_input.writer_input.outline_input.bundle.evidence_set_id),
            "version": audit_input.writer_input.outline_input.bundle.evidence_set_version,
            "content_hash": audit_input.writer_input.outline_input.bundle.evidence_set_hash,
        },
        "originality_pack": {
            "id": str(audit_input.writer_input.outline_input.bundle.originality_pack_id),
            "snapshot_hash": audit_input.writer_input.outline_input.bundle.originality_pack_hash,
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
            "version": ASSERTION_AUDIT_GENERATOR_VERSION,
            "schema_version": ASSERTION_AUDIT_SCHEMA_VERSION,
        },
        "model": {"provider": provider, "model": model, "model_calls": model_attempts},
        "segments": [segment.to_dict() for segment in segments],
        "summary": summary,
    }
    content_hash = _canonical_hash(payload)
    artifact = Artifact(
        run_id=audit_input.writer_input.writer_run.id,
        step_run_id=context_manifest.step_run_id,
        artifact_type="assertion_audit",
        locale=audit_input.writer_input.locale,
        version=1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    if artifact.step_run_id is not None:
        step = await session.get(StepRun, artifact.step_run_id)
        if step is None or step.run_id != artifact.run_id:
            raise AssertionAuditError("assertion_audit_artifact_step_mismatch")
        step.output_artifact_refs_json = [*step.output_artifact_refs_json, str(artifact.id)]
        await session.flush()
    result_value = summary["result"]
    if not isinstance(result_value, str):
        raise AssertionAuditError("assertion_audit_summary_result_invalid")
    result = result_value
    severity = "critical" if result == "fail" else ("medium" if result == "warn" else "none")
    evaluation = QualityEvaluation(
        run_id=artifact.run_id,
        artifact_id=artifact.id,
        evaluator_key=ASSERTION_AUDIT_EVALUATOR_KEY,
        evaluator_version=ASSERTION_AUDIT_EVALUATOR_VERSION,
        evaluator_type="deterministic",
        result=result,
        score=None,
        severity=severity,
        findings_json={
            "source_draft_id": str(audit_input.source_artifact.id),
            "source_draft_hash": audit_input.source_artifact.content_hash,
            "assertion_audit_artifact_id": str(artifact.id),
            "assertion_audit_hash": artifact.content_hash,
            **summary,
        },
    )
    session.add(evaluation)
    await session.flush()
    return AssertionAuditResult(
        artifact=artifact,
        evaluation=evaluation,
        segments=segments,
        result=result,
        critical_unsupported_count=cast(int, summary["critical_unsupported_count"]),
        critical_contradicted_count=cast(int, summary["critical_contradicted_count"]),
        unsupported_count=cast(int, summary["unsupported_count"]),
        contradicted_count=cast(int, summary["contradicted_count"]),
        model_attempts=model_attempts,
        reused=False,
    )


class AssertionAuditGenerator:
    """Extract and classify assertions; deterministic validation owns the hard gate."""

    def __init__(self, *, max_attempts: int = 2) -> None:
        if (
            isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or not 1 <= max_attempts <= 3
        ):
            raise ValueError("max_attempts must be between 1 and 3")
        self.max_attempts = max_attempts

    async def audit_draft(
        self,
        session: AsyncSession,
        *,
        writer_run_id: UUID,
        revised_draft_artifact_id: UUID,
        expected_revised_draft_version: int,
        expected_revised_draft_hash: str,
        outline_artifact_id: UUID,
        expected_outline_version: int,
        expected_outline_hash: str,
        locale: str,
        model: AssertionAuditModelPort,
        provider: str,
        model_name: str,
        context_manifest_id: UUID,
        prompt_version: str,
        recipe_version: str,
    ) -> AssertionAuditResult:
        audit_input = await load_assertion_audit_input(
            session,
            writer_run_id=writer_run_id,
            revised_draft_artifact_id=revised_draft_artifact_id,
            expected_revised_draft_version=expected_revised_draft_version,
            expected_revised_draft_hash=expected_revised_draft_hash,
            outline_artifact_id=outline_artifact_id,
            expected_outline_version=expected_outline_version,
            expected_outline_hash=expected_outline_hash,
            locale=locale,
        )
        manifest = await _execution_manifest(
            session,
            writer_input=audit_input.writer_input,
            context_manifest_id=context_manifest_id,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
        )
        routed = _model_identity(model)
        if routed is not None and (provider.strip(), model_name.strip()) != routed:
            raise AssertionAuditError("assertion_audit_model_route_mismatch")
        artifact_provider, artifact_model = routed or (provider.strip(), model_name.strip())
        if not artifact_provider or not artifact_model:
            raise AssertionAuditError("assertion_audit_model_metadata_required")
        model_input_hash = writer_model_input_hash(audit_input.model_input)
        fingerprint = _fingerprint(
            audit_input=audit_input,
            model_input_hash=model_input_hash,
            provider=artifact_provider,
            model=artifact_model,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
            context_manifest_hash=manifest.content_hash,
        )
        existing = await _existing_audit(
            session,
            audit_input=audit_input,
            fingerprint=fingerprint,
        )
        if existing is not None:
            return existing

        last_error: AssertionAuditError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw = await model.generate(
                    input_bundle=copy.deepcopy(audit_input.model_input),
                    attempt=attempt,
                )
                segments = validate_assertion_audit_output(raw, audit_input=audit_input)
            except (AssertionAuditError, WriterGenerationError) as exc:
                last_error = (
                    exc
                    if isinstance(exc, AssertionAuditError)
                    else AssertionAuditError(exc.code)
                )
                if attempt == self.max_attempts:
                    raise AssertionAuditError(
                        "assertion_audit_model_output_invalid",
                        f"bounded retries exhausted ({last_error.code})",
                    ) from exc
                continue
            return await _persist_audit(
                session,
                audit_input=audit_input,
                segments=segments,
                model_input_hash=model_input_hash,
                fingerprint=fingerprint,
                provider=artifact_provider,
                model=artifact_model,
                model_attempts=attempt,
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                context_manifest=manifest,
            )
        raise AssertionAuditError("assertion_audit_model_output_invalid") from last_error


__all__ = [
    "ASSERTION_AUDIT_EVALUATOR_KEY",
    "ASSERTION_AUDIT_EVALUATOR_VERSION",
    "ASSERTION_AUDIT_GENERATOR_VERSION",
    "ASSERTION_AUDIT_SCHEMA_VERSION",
    "AssertionAuditError",
    "AssertionAuditGenerator",
    "AssertionAuditInput",
    "AssertionAuditModelPort",
    "AssertionAuditResult",
    "AuditSourceSegment",
    "AuditedAssertion",
    "AuditedSegment",
    "load_assertion_audit_input",
    "validate_assertion_audit_output",
]
