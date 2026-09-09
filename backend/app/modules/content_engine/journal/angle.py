"""CE05 PR-B.2 structured Angle generation and human approval gates."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import AngleApproval
from app.modules.content_engine.journal.research_handoff import (
    JournalResearchHandoff,
    JournalResearchHandoffError,
    ResearchDecision,
    _opportunity_payload,
)
from app.modules.content_engine.models import ContentOpportunity
from app.modules.harness.models import Artifact, ContentRun, ContextManifest, StepRun

_CONTENT_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_JOURNAL_INPUT_BUNDLE_SCHEMA_VERSION = 1
ANGLE_CANDIDATES_SCHEMA_VERSION = 1
ANGLE_GENERATOR_VERSION = "ce05.angle_generator.v1"
_UPSTREAM_BLOCKING_DECISIONS = {"MERGE", "LINK_ONLY", "DO_NOT_WRITE"}


class AngleGenerationError(ValueError):
    """Raised when an Angle input, model result, or artifact is not safe to use."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class AngleApprovalError(ValueError):
    """Raised when an Angle approval is absent, stale, or conflicting."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class AngleModelPort(Protocol):
    """Provider-neutral seam for a structured Angle model call."""

    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class AngleCandidate:
    angle_id: str
    working_title: str
    reader_problem: str
    central_question: str
    core_promise: str
    point_of_view: str
    why_now: str
    evidence_refs: tuple[str, ...]
    originality_refs: tuple[str, ...]
    excluded_claims: tuple[str, ...]
    risks: tuple[str, ...]
    confidence: float
    locale: str

    def to_dict(self) -> dict[str, object]:
        return {
            "angle_id": self.angle_id,
            "working_title": self.working_title,
            "reader_problem": self.reader_problem,
            "central_question": self.central_question,
            "core_promise": self.core_promise,
            "point_of_view": self.point_of_view,
            "why_now": self.why_now,
            "evidence_refs": list(self.evidence_refs),
            "originality_refs": list(self.originality_refs),
            "excluded_claims": list(self.excluded_claims),
            "risks": list(self.risks),
            "confidence": self.confidence,
            "locale": self.locale,
        }


@dataclass(frozen=True, slots=True)
class JournalInputBundle:
    artifact: Artifact
    payload: dict[str, object]
    research_decision: ResearchDecision
    opportunity: dict[str, object]
    evidence_set_id: UUID
    evidence_set_version: int
    evidence_set_hash: str
    evidence_ids: tuple[UUID, ...]
    originality_pack_id: UUID
    originality_pack_hash: str
    originality_refs: tuple[str, ...]
    locale: str
    context_manifest: ContextManifest | None = None


@dataclass(frozen=True, slots=True)
class AngleGenerationResult:
    artifact: Artifact
    candidates: tuple[AngleCandidate, ...]
    model_attempts: int


@dataclass(frozen=True, slots=True)
class ApprovedAngle:
    artifact: Artifact
    candidate: AngleCandidate
    approval: AngleApproval


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and _CONTENT_HASH_PATTERN.fullmatch(value) is not None


def _as_dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AngleGenerationError(code)
    return cast(dict[str, object], value)


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AngleGenerationError(code)
    return value.strip()


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AngleGenerationError(code)
    return value


def _string_list(value: object, code: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise AngleGenerationError(code)
    return [item.strip() for item in value]


def _uuid(value: object, code: str) -> UUID:
    if not isinstance(value, str):
        raise AngleGenerationError(code)
    try:
        return UUID(value)
    except ValueError as exc:
        raise AngleGenerationError(code) from exc


def _clone_json(value: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(json.dumps(value, ensure_ascii=False)))


def angle_candidate_hash(candidate: AngleCandidate) -> str:
    """Hash only the normalized candidate snapshot selected by a human."""

    return _canonical_hash(candidate.to_dict())


def _normalize_evidence_ref(value: object) -> str:
    ref = _text(value, "angle_evidence_ref_invalid")
    if ref.startswith("evidence:"):
        ref = ref.removeprefix("evidence:")
    try:
        return str(UUID(ref))
    except ValueError as exc:
        raise AngleGenerationError("angle_evidence_ref_invalid") from exc


def _normalize_originality_ref(value: object, allowed: set[str]) -> str:
    ref = _text(value, "angle_originality_ref_invalid")
    if ref.startswith("originality:"):
        ref = ref.removeprefix("originality:")
    if ref not in allowed:
        raise AngleGenerationError("angle_originality_ref_outside_pack")
    return ref


def _originality_refs(items: Sequence[object]) -> tuple[str, ...]:
    refs: list[str] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("source_ref"), str):
            source_ref = item["source_ref"].strip()
            if source_ref:
                refs.append(source_ref)
    return tuple(refs)


def _candidate_from_raw(
    raw: object,
    *,
    locale: str,
    allowed_evidence: set[str],
    allowed_originality: set[str],
) -> AngleCandidate:
    candidate = _as_dict(raw, "angle_model_output_candidate_invalid")
    fields = (
        "angle_id",
        "working_title",
        "reader_problem",
        "central_question",
        "core_promise",
        "point_of_view",
        "why_now",
        "evidence_refs",
        "originality_refs",
        "excluded_claims",
        "risks",
        "confidence",
        "locale",
    )
    if any(field not in candidate for field in fields):
        raise AngleGenerationError("angle_model_output_schema_invalid")
    raw_evidence_refs = _string_list(candidate["evidence_refs"], "angle_evidence_refs_invalid")
    if not raw_evidence_refs:
        raise AngleGenerationError("angle_evidence_refs_required")
    evidence_refs = tuple(_normalize_evidence_ref(ref) for ref in raw_evidence_refs)
    if any(ref not in allowed_evidence for ref in evidence_refs):
        raise AngleGenerationError("angle_evidence_ref_outside_evidence_set")
    if len(set(evidence_refs)) != len(evidence_refs):
        raise AngleGenerationError("angle_evidence_ref_duplicate")
    raw_originality_refs = _string_list(
        candidate["originality_refs"], "angle_originality_refs_invalid"
    )
    if not raw_originality_refs:
        raise AngleGenerationError("angle_originality_refs_required")
    originality_refs = tuple(
        _normalize_originality_ref(ref, allowed_originality) for ref in raw_originality_refs
    )
    if len(set(originality_refs)) != len(originality_refs):
        raise AngleGenerationError("angle_originality_ref_duplicate")
    confidence = candidate["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise AngleGenerationError("angle_confidence_invalid")
    if not 0 <= float(confidence) <= 1:
        raise AngleGenerationError("angle_confidence_invalid")
    candidate_locale = _text(candidate["locale"], "angle_locale_invalid")
    if candidate_locale != locale:
        raise AngleGenerationError("angle_locale_mismatch")
    return AngleCandidate(
        angle_id=_text(candidate["angle_id"], "angle_id_required"),
        working_title=_text(candidate["working_title"], "angle_working_title_required"),
        reader_problem=_text(candidate["reader_problem"], "angle_reader_problem_required"),
        central_question=_text(candidate["central_question"], "angle_central_question_required"),
        core_promise=_text(candidate["core_promise"], "angle_core_promise_required"),
        point_of_view=_text(candidate["point_of_view"], "angle_point_of_view_required"),
        why_now=_text(candidate["why_now"], "angle_why_now_required"),
        evidence_refs=evidence_refs,
        originality_refs=originality_refs,
        excluded_claims=tuple(
            _string_list(candidate["excluded_claims"], "angle_excluded_claims_invalid")
        ),
        risks=tuple(_string_list(candidate["risks"], "angle_risks_invalid")),
        confidence=float(confidence),
        locale=candidate_locale,
    )


def _decode_model_output(raw: object) -> object:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AngleGenerationError("angle_model_output_json_invalid") from exc
    if isinstance(raw, dict) and "candidates" in raw:
        return raw["candidates"]
    return raw


def _validate_candidates(
    raw: object,
    *,
    bundle: JournalInputBundle,
) -> tuple[AngleCandidate, ...]:
    decoded = _decode_model_output(raw)
    if not isinstance(decoded, list) or not 3 <= len(decoded) <= 5:
        raise AngleGenerationError("angle_candidate_count_invalid")
    allowed_evidence = {str(item) for item in bundle.evidence_ids}
    allowed_originality = set(bundle.originality_refs)
    candidates = tuple(
        _candidate_from_raw(
            item,
            locale=bundle.locale,
            allowed_evidence=allowed_evidence,
            allowed_originality=allowed_originality,
        )
        for item in decoded
    )
    angle_ids = [item.angle_id for item in candidates]
    if len(set(angle_ids)) != len(angle_ids):
        raise AngleGenerationError("angle_id_duplicate")
    return candidates


async def load_journal_input_bundle(
    session: AsyncSession,
    *,
    journal_input_bundle_id: UUID,
    expected_content_hash: str | None = None,
) -> JournalInputBundle:
    """Reload and revalidate the immutable upstream bundle before every Angle use."""

    artifact = await session.get(Artifact, journal_input_bundle_id)
    if artifact is None:
        raise AngleGenerationError("journal_input_bundle_not_found")
    if artifact.artifact_type != "journal_input_bundle":
        raise AngleGenerationError("journal_input_bundle_type_invalid")
    if not _valid_hash(artifact.content_hash):
        raise AngleGenerationError("journal_input_bundle_hash_invalid")
    if expected_content_hash is not None and artifact.content_hash != expected_content_hash:
        raise AngleGenerationError("journal_input_bundle_snapshot_stale")
    if artifact.content_json is None:
        raise AngleGenerationError("journal_input_bundle_payload_missing")
    payload = _as_dict(artifact.content_json, "journal_input_bundle_payload_invalid")
    if _canonical_hash(payload) != artifact.content_hash:
        raise AngleGenerationError("journal_input_bundle_snapshot_stale")
    if payload.get("schema_version") != _JOURNAL_INPUT_BUNDLE_SCHEMA_VERSION:
        raise AngleGenerationError("journal_input_bundle_schema_invalid")
    if payload.get("artifact_type") != "journal_input_bundle":
        raise AngleGenerationError("journal_input_bundle_type_invalid")

    decision_value = payload.get("research_decision")
    if not isinstance(decision_value, str):
        raise AngleGenerationError("angle_research_decision_invalid")
    try:
        decision = ResearchDecision(decision_value)
    except ValueError as exc:
        raise AngleGenerationError("angle_research_decision_invalid") from exc
    if decision is ResearchDecision.BLOCKED:
        raise AngleGenerationError("angle_research_decision_blocked")
    for key, code in (
        ("provider_calls", "journal_provider_call_count_invalid"),
        ("model_calls", "journal_model_call_count_invalid"),
    ):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise AngleGenerationError(code)
    if decision is ResearchDecision.REUSE_EXISTING and (
        payload["provider_calls"] or payload["model_calls"]
    ):
        raise AngleGenerationError("reuse_existing_requires_zero_calls")

    run = await session.get(ContentRun, artifact.run_id)
    if run is None:
        raise AngleGenerationError("journal_input_bundle_run_not_found")
    opportunity = _as_dict(payload.get("opportunity"), "angle_opportunity_snapshot_invalid")
    opportunity_id = _uuid(opportunity.get("id"), "angle_opportunity_id_invalid")
    current_opportunity = await session.get(ContentOpportunity, opportunity_id)
    if current_opportunity is None:
        raise AngleGenerationError("angle_opportunity_not_found")
    if current_opportunity.project_id != run.project_id:
        raise AngleGenerationError("angle_opportunity_project_mismatch")
    if current_opportunity.decision in _UPSTREAM_BLOCKING_DECISIONS:
        raise AngleGenerationError("angle_upstream_decision_blocked")
    if _opportunity_payload(current_opportunity) != opportunity:
        raise AngleGenerationError("angle_opportunity_snapshot_stale")
    if current_opportunity.decision in _UPSTREAM_BLOCKING_DECISIONS:
        raise AngleGenerationError("angle_upstream_decision_blocked")
    locale = _text(opportunity.get("locale"), "angle_locale_invalid")

    evidence_payload = _as_dict(
        payload.get("evidence_set"), "angle_evidence_set_snapshot_invalid"
    )
    evidence_set_id = _uuid(evidence_payload.get("id"), "angle_evidence_set_id_invalid")
    evidence_set_version = _positive_int(
        evidence_payload.get("version"), "angle_evidence_set_version_invalid"
    )
    evidence_hash = evidence_payload.get("content_hash")
    if not _valid_hash(evidence_hash):
        raise AngleGenerationError("angle_evidence_set_hash_invalid")
    evidence_hash = cast(str, evidence_hash)
    handoff = JournalResearchHandoff()
    try:
        evidence = await handoff.handoff_evidence_set(
            session,
            project_id=run.project_id,
            content_case_id=run.content_case_id,
            evidence_set_id=evidence_set_id,
            expected_version=evidence_set_version,
            expected_content_hash=evidence_hash,
        )
    except JournalResearchHandoffError as exc:
        raise AngleGenerationError(exc.code) from exc

    originality_payload = _as_dict(
        payload.get("originality_pack"), "angle_originality_pack_snapshot_invalid"
    )
    originality_pack_id = _uuid(
        originality_payload.get("id"), "angle_originality_pack_id_invalid"
    )
    originality_hash = originality_payload.get("snapshot_hash")
    if not _valid_hash(originality_hash):
        raise AngleGenerationError("angle_originality_pack_hash_invalid")
    originality_hash = cast(str, originality_hash)
    try:
        originality = await handoff.handoff_originality_pack(
            session,
            content_case_id=run.content_case_id,
            originality_pack_id=originality_pack_id,
            expected_snapshot_hash=originality_hash,
        )
    except JournalResearchHandoffError as exc:
        raise AngleGenerationError(exc.code) from exc

    context_manifest = None
    raw_manifest = payload.get("context_manifest")
    if raw_manifest is not None:
        manifest_payload = _as_dict(raw_manifest, "angle_context_manifest_invalid")
        manifest_id = _uuid(manifest_payload.get("id"), "angle_context_manifest_id_invalid")
        context_manifest = await session.get(ContextManifest, manifest_id)
        if context_manifest is None or context_manifest.run_id != run.id:
            raise AngleGenerationError("angle_context_manifest_mismatch")
        if context_manifest.evidence_set_id != evidence_set_id:
            raise AngleGenerationError("angle_context_manifest_evidence_mismatch")
        if context_manifest.originality_pack_id != originality_pack_id:
            raise AngleGenerationError("angle_context_manifest_originality_mismatch")
        expected_manifest_hash = manifest_payload.get("content_hash")
        if (
            expected_manifest_hash is not None
            and expected_manifest_hash != context_manifest.content_hash
        ):
            raise AngleGenerationError("angle_context_manifest_snapshot_stale")

    return JournalInputBundle(
        artifact=artifact,
        payload=payload,
        research_decision=decision,
        opportunity=opportunity,
        evidence_set_id=evidence.evidence_set_id,
        evidence_set_version=evidence.version,
        evidence_set_hash=evidence.content_hash,
        evidence_ids=evidence.evidence_ids,
        originality_pack_id=originality.originality_pack_id,
        originality_pack_hash=originality.snapshot_hash,
        originality_refs=_originality_refs(originality.item_refs),
        locale=locale,
        context_manifest=context_manifest,
    )


async def persist_angle_candidates(
    session: AsyncSession,
    *,
    bundle: JournalInputBundle,
    candidates: Sequence[AngleCandidate],
    provider: str,
    model: str,
    model_calls: int,
    provider_calls: int = 0,
    generator_version: str = ANGLE_GENERATOR_VERSION,
    schema_version: int = ANGLE_CANDIDATES_SCHEMA_VERSION,
    step_run_id: UUID | None = None,
) -> Artifact:
    """Persist or reuse one immutable, exact Angle candidate artifact."""

    refreshed_bundle = await load_journal_input_bundle(
        session,
        journal_input_bundle_id=bundle.artifact.id,
        expected_content_hash=bundle.artifact.content_hash,
    )
    if refreshed_bundle.artifact.id != bundle.artifact.id:
        raise AngleGenerationError("journal_input_bundle_snapshot_mismatch")
    if not isinstance(provider, str) or not provider.strip():
        raise AngleGenerationError("angle_provider_metadata_required")
    if not isinstance(model, str) or not model.strip():
        raise AngleGenerationError("angle_model_metadata_required")
    if isinstance(model_calls, bool) or not isinstance(model_calls, int) or model_calls < 0:
        raise AngleGenerationError("angle_model_call_count_invalid")
    if (
        isinstance(provider_calls, bool)
        or not isinstance(provider_calls, int)
        or provider_calls < 0
    ):
        raise AngleGenerationError("angle_provider_call_count_invalid")
    if provider_calls != 0:
        raise AngleGenerationError("angle_provider_calls_forbidden")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version <= 0
    ):
        raise AngleGenerationError("angle_schema_version_invalid")
    if not isinstance(generator_version, str) or not generator_version.strip():
        raise AngleGenerationError("angle_generator_version_required")
    validated = _validate_candidates(
        [candidate.to_dict() for candidate in candidates], bundle=refreshed_bundle
    )
    payload: dict[str, object] = {
        "schema_version": schema_version,
        "artifact_type": "angle_candidates",
        "journal_input_bundle": {
            "id": str(refreshed_bundle.artifact.id),
            "version": refreshed_bundle.artifact.version,
            "content_hash": refreshed_bundle.artifact.content_hash,
        },
        "generator": {
            "version": generator_version,
            "schema_version": schema_version,
        },
        "model": {
            "provider": provider.strip(),
            "model": model.strip(),
        },
        "provider_calls": provider_calls,
        "model_calls": model_calls,
        "candidates": [candidate.to_dict() for candidate in validated],
    }
    artifact_hash = _canonical_hash(payload)
    existing = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == refreshed_bundle.artifact.run_id,
            Artifact.artifact_type == "angle_candidates",
            Artifact.content_hash == artifact_hash,
        )
    )
    if existing is not None:
        if existing.content_json != payload:
            raise AngleGenerationError("angle_artifact_hash_collision")
        return existing
    latest_version = await session.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.run_id == refreshed_bundle.artifact.run_id,
            Artifact.artifact_type == "angle_candidates",
        )
    )
    artifact = Artifact(
        run_id=refreshed_bundle.artifact.run_id,
        step_run_id=step_run_id or refreshed_bundle.artifact.step_run_id,
        artifact_type="angle_candidates",
        locale=refreshed_bundle.locale,
        version=(latest_version or 0) + 1,
        content_json=payload,
        content_hash=artifact_hash,
    )
    session.add(artifact)
    await session.flush()
    if artifact.step_run_id is not None:
        step = await session.get(StepRun, artifact.step_run_id)
        if step is None or step.run_id != artifact.run_id:
            raise AngleGenerationError("angle_artifact_step_mismatch")
        if str(artifact.id) not in step.output_artifact_refs_json:
            step.output_artifact_refs_json = [*step.output_artifact_refs_json, str(artifact.id)]
            await session.flush()
    return artifact


class AngleGenerator:
    """Generate typed candidates with one bounded validation retry."""

    def __init__(self, *, max_attempts: int = 2) -> None:
        if (
            isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or not 1 <= max_attempts <= 3
        ):
            raise ValueError("max_attempts must be between 1 and 3")
        self.max_attempts = max_attempts

    async def generate_candidates(
        self,
        session: AsyncSession,
        *,
        journal_input_bundle_id: UUID,
        model: AngleModelPort,
        provider: str,
        model_name: str,
        expected_bundle_hash: str | None = None,
        generator_version: str = ANGLE_GENERATOR_VERSION,
        schema_version: int = ANGLE_CANDIDATES_SCHEMA_VERSION,
        step_run_id: UUID | None = None,
    ) -> AngleGenerationResult:
        bundle = await load_journal_input_bundle(
            session,
            journal_input_bundle_id=journal_input_bundle_id,
            expected_content_hash=expected_bundle_hash,
        )
        last_error: AngleGenerationError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw = await model.generate(
                    input_bundle=_clone_json(bundle.payload),
                    attempt=attempt,
                )
                candidates = _validate_candidates(raw, bundle=bundle)
            except AngleGenerationError as exc:
                last_error = exc
                if attempt == self.max_attempts:
                    raise AngleGenerationError(
                        "angle_model_output_invalid",
                        f"bounded retries exhausted ({exc.code})",
                    ) from exc
                continue
            artifact = await persist_angle_candidates(
                session,
                bundle=bundle,
                candidates=candidates,
                provider=provider,
                model=model_name,
                model_calls=attempt,
                provider_calls=0,
                generator_version=generator_version,
                schema_version=schema_version,
                step_run_id=step_run_id,
            )
            return AngleGenerationResult(
                artifact=artifact,
                candidates=candidates,
                model_attempts=attempt,
            )
        raise AngleGenerationError("angle_model_output_invalid") from last_error


def _artifact_candidates(
    artifact: Artifact,
    *,
    bundle: JournalInputBundle,
) -> tuple[AngleCandidate, ...]:
    if artifact.artifact_type != "angle_candidates":
        raise AngleApprovalError("angle_artifact_type_invalid")
    if (
        artifact.content_json is None
        or _canonical_hash(artifact.content_json) != artifact.content_hash
    ):
        raise AngleApprovalError("angle_artifact_snapshot_stale")
    payload = _as_dict(artifact.content_json, "angle_artifact_payload_invalid")
    raw_candidates = payload.get("candidates")
    try:
        return _validate_candidates(raw_candidates, bundle=bundle)
    except AngleGenerationError as exc:
        raise AngleApprovalError(exc.code) from exc


def _validate_artifact_snapshot(
    artifact: Artifact,
    *,
    expected_version: int,
    expected_hash: str,
) -> None:
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version <= 0
    ):
        raise AngleApprovalError("angle_artifact_version_invalid")
    if not _valid_hash(expected_hash):
        raise AngleApprovalError("angle_artifact_hash_invalid")
    if artifact.version != expected_version or artifact.content_hash != expected_hash:
        raise AngleApprovalError("angle_artifact_snapshot_stale")
    if not _valid_hash(artifact.content_hash) or artifact.content_json is None:
        raise AngleApprovalError("angle_artifact_snapshot_stale")
    if _canonical_hash(artifact.content_json) != artifact.content_hash:
        raise AngleApprovalError("angle_artifact_snapshot_stale")


def _approval_matches(
    approval: AngleApproval,
    *,
    artifact: Artifact,
    selected_angle_id: str,
    candidate_hash: str,
    approved_by: str,
    approval_reason: str,
) -> bool:
    return (
        approval.angle_artifact_id == artifact.id
        and approval.angle_artifact_version == artifact.version
        and approval.angle_artifact_hash == artifact.content_hash
        and approval.selected_angle_id == selected_angle_id
        and approval.selected_candidate_hash == candidate_hash
        and approval.approved_by == approved_by
        and approval.approval_reason == approval_reason
    )


async def approve_angle_candidate(
    session: AsyncSession,
    *,
    angle_artifact_id: UUID,
    expected_artifact_version: int,
    expected_artifact_hash: str,
    selected_angle_id: str,
    expected_candidate_hash: str,
    approved_by: str,
    approval_reason: str,
) -> AngleApproval:
    """Persist one exact human decision; model output cannot call this implicitly."""

    selected_id = _text(selected_angle_id, "angle_selected_id_required")
    approver = _text(approved_by, "angle_approver_required")
    reason = _text(approval_reason, "angle_approval_reason_required")
    if not _valid_hash(expected_candidate_hash):
        raise AngleApprovalError("angle_candidate_hash_invalid")
    artifact = await session.scalar(
        select(Artifact).where(Artifact.id == angle_artifact_id).with_for_update()
    )
    if artifact is None:
        raise AngleApprovalError("angle_artifact_not_found")
    _validate_artifact_snapshot(
        artifact,
        expected_version=expected_artifact_version,
        expected_hash=expected_artifact_hash,
    )
    payload = _as_dict(artifact.content_json, "angle_artifact_payload_invalid")
    bundle_payload = _as_dict(
        payload.get("journal_input_bundle"), "angle_artifact_bundle_ref_invalid"
    )
    bundle_id = _uuid(bundle_payload.get("id"), "angle_artifact_bundle_ref_invalid")
    bundle_hash = bundle_payload.get("content_hash")
    if not _valid_hash(bundle_hash):
        raise AngleApprovalError("angle_artifact_bundle_ref_invalid")
    bundle_hash = cast(str, bundle_hash)
    try:
        bundle = await load_journal_input_bundle(
            session,
            journal_input_bundle_id=bundle_id,
            expected_content_hash=bundle_hash,
        )
    except AngleGenerationError as exc:
        raise AngleApprovalError(exc.code) from exc
    candidates = _artifact_candidates(artifact, bundle=bundle)
    selected = next(
        (candidate for candidate in candidates if candidate.angle_id == selected_id),
        None,
    )
    if selected is None:
        raise AngleApprovalError("angle_selected_candidate_not_found")
    candidate_hash = angle_candidate_hash(selected)
    if candidate_hash != expected_candidate_hash:
        raise AngleApprovalError("angle_candidate_snapshot_stale")

    approvals = list(
        (
            await session.scalars(
                select(AngleApproval).where(AngleApproval.angle_artifact_id == artifact.id)
            )
        ).all()
    )
    for approval in approvals:
        if _approval_matches(
            approval,
            artifact=artifact,
            selected_angle_id=selected_id,
            candidate_hash=candidate_hash,
            approved_by=approver,
            approval_reason=reason,
        ):
            return approval
        raise AngleApprovalError("angle_approval_conflict")

    approval = AngleApproval(
        run_id=artifact.run_id,
        angle_artifact_id=artifact.id,
        angle_artifact_version=artifact.version,
        angle_artifact_hash=artifact.content_hash,
        selected_angle_id=selected_id,
        selected_candidate_hash=candidate_hash,
        approved_by=approver,
        approval_reason=reason,
        approved_at=datetime.now(UTC),
    )
    session.add(approval)
    await session.flush()
    return approval


async def handoff_approved_angle(
    session: AsyncSession,
    *,
    angle_artifact_id: UUID,
    expected_artifact_version: int,
    expected_artifact_hash: str,
    selected_angle_id: str,
    expected_candidate_hash: str,
) -> ApprovedAngle:
    """Expose an Angle to the next step only after exact human approval."""

    selected_id = _text(selected_angle_id, "angle_selected_id_required")
    if not _valid_hash(expected_candidate_hash):
        raise AngleApprovalError("angle_candidate_hash_invalid")
    artifact = await session.get(Artifact, angle_artifact_id)
    if artifact is None:
        raise AngleApprovalError("angle_artifact_not_found")
    _validate_artifact_snapshot(
        artifact,
        expected_version=expected_artifact_version,
        expected_hash=expected_artifact_hash,
    )
    payload = _as_dict(artifact.content_json, "angle_artifact_payload_invalid")
    bundle_payload = _as_dict(
        payload.get("journal_input_bundle"), "angle_artifact_bundle_ref_invalid"
    )
    bundle_id = _uuid(bundle_payload.get("id"), "angle_artifact_bundle_ref_invalid")
    bundle_hash = bundle_payload.get("content_hash")
    if not _valid_hash(bundle_hash):
        raise AngleApprovalError("angle_artifact_bundle_ref_invalid")
    bundle_hash = cast(str, bundle_hash)
    try:
        bundle = await load_journal_input_bundle(
            session,
            journal_input_bundle_id=bundle_id,
            expected_content_hash=bundle_hash,
        )
    except AngleGenerationError as exc:
        raise AngleApprovalError(exc.code) from exc
    candidates = _artifact_candidates(artifact, bundle=bundle)
    selected = next(
        (candidate for candidate in candidates if candidate.angle_id == selected_id),
        None,
    )
    if selected is None:
        raise AngleApprovalError("angle_selected_candidate_not_found")
    actual_candidate_hash = angle_candidate_hash(selected)
    if actual_candidate_hash != expected_candidate_hash:
        raise AngleApprovalError("angle_candidate_snapshot_stale")
    approvals = list(
        (
            await session.scalars(
                select(AngleApproval).where(AngleApproval.angle_artifact_id == artifact.id)
            )
        ).all()
    )
    if not approvals:
        raise AngleApprovalError("angle_approval_required")
    approval = approvals[0]
    if not _approval_matches(
        approval,
        artifact=artifact,
        selected_angle_id=selected_id,
        candidate_hash=actual_candidate_hash,
        approved_by=approval.approved_by,
        approval_reason=approval.approval_reason,
    ):
        raise AngleApprovalError("angle_approval_conflict")
    return ApprovedAngle(artifact=artifact, candidate=selected, approval=approval)


__all__ = [
    "ANGLE_CANDIDATES_SCHEMA_VERSION",
    "ANGLE_GENERATOR_VERSION",
    "AngleApproval",
    "AngleApprovalError",
    "AngleCandidate",
    "AngleGenerationError",
    "AngleGenerationResult",
    "AngleGenerator",
    "AngleModelPort",
    "ApprovedAngle",
    "JournalInputBundle",
    "angle_candidate_hash",
    "approve_angle_candidate",
    "handoff_approved_angle",
    "load_journal_input_bundle",
    "persist_angle_candidates",
]
