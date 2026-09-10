"""CE05 T05.10 grounded Journal Outline generation and persistence."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.angle import (
    ApprovedAngle,
    JournalInputBundle,
    handoff_approved_angle,
    load_journal_input_bundle,
)
from app.modules.harness.models import Artifact, ContentRun, ContextManifest, StepRun

OUTLINE_SCHEMA_VERSION = 1
OUTLINE_GENERATOR_VERSION = "ce05.outline_generator.v1"
_SUPPORT_TYPES = {"factual", "motgu_original", "editorial", "mixed"}


class OutlineGenerationError(ValueError):
    """Raised when approved inputs, model output or Outline persistence is unsafe."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class OutlineModelPort(Protocol):
    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class OutlineSection:
    section_id: str
    heading: str
    purpose: str
    answer_direction: str
    support_type: str
    evidence_refs: tuple[str, ...]
    originality_refs: tuple[str, ...]
    claim_guards: tuple[str, ...]
    reader_movement: str
    internal_link_targets: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "heading": self.heading,
            "purpose": self.purpose,
            "answer_direction": self.answer_direction,
            "support_type": self.support_type,
            "evidence_refs": list(self.evidence_refs),
            "originality_refs": list(self.originality_refs),
            "claim_guards": list(self.claim_guards),
            "reader_movement": self.reader_movement,
            "internal_link_targets": list(self.internal_link_targets),
        }


@dataclass(frozen=True, slots=True)
class JournalOutline:
    primary_answer: str
    primary_answer_support_type: str
    primary_answer_evidence_refs: tuple[str, ...]
    primary_answer_originality_refs: tuple[str, ...]
    primary_answer_claim_guard: str
    sections: tuple[OutlineSection, ...]
    must_not_claim: tuple[str, ...]
    angle_risks: tuple[str, ...]

    def model_output_dict(self) -> dict[str, object]:
        return {
            "primary_answer": self.primary_answer,
            "primary_answer_support_type": self.primary_answer_support_type,
            "primary_answer_evidence_refs": list(self.primary_answer_evidence_refs),
            "primary_answer_originality_refs": list(self.primary_answer_originality_refs),
            "primary_answer_claim_guard": self.primary_answer_claim_guard,
            "sections": [section.to_dict() for section in self.sections],
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self.model_output_dict(),
            "must_not_claim": list(self.must_not_claim),
            "angle_risks": list(self.angle_risks),
        }


@dataclass(frozen=True, slots=True)
class OutlineInput:
    approved_angle: ApprovedAngle
    bundle: JournalInputBundle
    model_input: dict[str, object]


@dataclass(frozen=True, slots=True)
class OutlineGenerationResult:
    artifact: Artifact
    outline: JournalOutline
    model_attempts: int
    reused: bool


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clone_json(value: object) -> object:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OutlineGenerationError(code)
    return value.strip()


def _string_list(value: object, code: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise OutlineGenerationError(code)
    return [item.strip() for item in value]


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise OutlineGenerationError(code)
    return cast(dict[str, object], value)


def _normalize_evidence_ref(value: str) -> str:
    ref = value.removeprefix("evidence:")
    try:
        return str(UUID(ref))
    except ValueError as exc:
        raise OutlineGenerationError("outline_evidence_ref_invalid") from exc


def _normalize_originality_ref(value: str, allowed: set[str]) -> str:
    ref = value.removeprefix("originality:")
    if ref not in allowed:
        raise OutlineGenerationError("outline_originality_ref_outside_pack")
    return ref


def _support_type(value: object, code: str) -> str:
    support = _text(value, code)
    if support not in _SUPPORT_TYPES:
        raise OutlineGenerationError(code)
    return support


def _validate_support(
    *,
    support_type: str,
    evidence_refs: tuple[str, ...],
    originality_refs: tuple[str, ...],
    code_prefix: str,
) -> None:
    if support_type == "factual" and not evidence_refs:
        raise OutlineGenerationError(f"{code_prefix}_evidence_required")
    if support_type == "motgu_original" and not originality_refs:
        raise OutlineGenerationError(f"{code_prefix}_originality_required")
    if support_type == "mixed" and (not evidence_refs or not originality_refs):
        raise OutlineGenerationError(f"{code_prefix}_mixed_support_required")


def outline_model_input_hash(model_input: dict[str, object]) -> str:
    return _canonical_hash(_clone_json(model_input))


def _generation_fingerprint(
    *,
    model_input_hash: str,
    provider: str,
    model: str,
    prompt_version: str,
    recipe_version: str,
    context_manifest_hash: str,
    generator_version: str,
    schema_version: int,
) -> str:
    return _canonical_hash(
        {
            "model_input_hash": model_input_hash,
            "provider": provider,
            "model": model,
            "prompt_version": prompt_version,
            "recipe_version": recipe_version,
            "context_manifest_hash": context_manifest_hash,
            "generator_version": generator_version,
            "schema_version": schema_version,
        }
    )


def _approved_angle_payload(approved: ApprovedAngle) -> dict[str, object]:
    return {
        "artifact": {
            "id": str(approved.artifact.id),
            "version": approved.artifact.version,
            "content_hash": approved.artifact.content_hash,
        },
        "approval": {
            "id": str(approved.approval.id),
            "selected_angle_id": approved.approval.selected_angle_id,
            "selected_candidate_hash": approved.approval.selected_candidate_hash,
            "approved_by": approved.approval.approved_by,
        },
        "candidate": approved.candidate.to_dict(),
    }


async def load_outline_input(
    session: AsyncSession,
    *,
    angle_artifact_id: UUID,
    expected_angle_artifact_version: int,
    expected_angle_artifact_hash: str,
    selected_angle_id: str,
    expected_candidate_hash: str,
    expected_approval_id: UUID,
) -> OutlineInput:
    """Reload the exact approved Angle and rebuild the allow-listed Outline input."""

    try:
        approved = await handoff_approved_angle(
            session,
            angle_artifact_id=angle_artifact_id,
            expected_artifact_version=expected_angle_artifact_version,
            expected_artifact_hash=expected_angle_artifact_hash,
            selected_angle_id=selected_angle_id,
            expected_candidate_hash=expected_candidate_hash,
        )
    except ValueError as exc:
        raise OutlineGenerationError("outline_approved_angle_invalid", str(exc)) from exc
    if approved.approval.id != expected_approval_id:
        raise OutlineGenerationError("outline_angle_approval_mismatch")

    angle_payload = _dict(approved.artifact.content_json, "outline_angle_artifact_payload_invalid")
    bundle_ref = _dict(
        angle_payload.get("journal_input_bundle"),
        "outline_bundle_ref_invalid",
    )
    raw_bundle_id = bundle_ref.get("id")
    raw_bundle_hash = bundle_ref.get("content_hash")
    if not isinstance(raw_bundle_id, str) or not isinstance(raw_bundle_hash, str):
        raise OutlineGenerationError("outline_bundle_ref_invalid")
    try:
        bundle_id = UUID(raw_bundle_id)
    except ValueError as exc:
        raise OutlineGenerationError("outline_bundle_ref_invalid") from exc
    try:
        bundle = await load_journal_input_bundle(
            session,
            journal_input_bundle_id=bundle_id,
            expected_content_hash=raw_bundle_hash,
        )
    except ValueError as exc:
        raise OutlineGenerationError("outline_bundle_invalid", str(exc)) from exc
    if bundle.artifact.run_id != approved.artifact.run_id:
        raise OutlineGenerationError("outline_run_mismatch")

    angle_input = bundle.angle_model_input
    evidence_set = _dict(angle_input.get("evidence_set"), "outline_evidence_input_invalid")
    originality_pack = _dict(
        angle_input.get("originality_pack"),
        "outline_originality_input_invalid",
    )
    opportunity = _dict(angle_input.get("opportunity"), "outline_opportunity_input_invalid")
    model_input: dict[str, object] = {
        "approved_angle": _approved_angle_payload(approved),
        "journal_input_bundle_ref": {
            "id": str(bundle.artifact.id),
            "version": bundle.artifact.version,
            "content_hash": bundle.artifact.content_hash,
        },
        "opportunity": cast(dict[str, object], _clone_json(opportunity)),
        "evidence_set": cast(dict[str, object], _clone_json(evidence_set)),
        "originality_pack": cast(dict[str, object], _clone_json(originality_pack)),
    }
    upstream_context = angle_input.get("context")
    if upstream_context is not None:
        model_input["upstream_context"] = _clone_json(upstream_context)
    return OutlineInput(approved_angle=approved, bundle=bundle, model_input=model_input)


def _allowed_refs(outline_input: OutlineInput) -> tuple[set[str], set[str]]:
    evidence_set = _dict(
        outline_input.model_input.get("evidence_set"),
        "outline_evidence_input_invalid",
    )
    evidence_items = evidence_set.get("evidence")
    if not isinstance(evidence_items, list):
        raise OutlineGenerationError("outline_evidence_input_invalid")
    evidence_refs = {
        item["evidence_id"]
        for item in evidence_items
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }
    originality_pack = _dict(
        outline_input.model_input.get("originality_pack"),
        "outline_originality_input_invalid",
    )
    originality_items = originality_pack.get("items")
    if not isinstance(originality_items, list):
        raise OutlineGenerationError("outline_originality_input_invalid")
    originality_refs = {
        item["source_ref"]
        for item in originality_items
        if isinstance(item, dict) and isinstance(item.get("source_ref"), str)
    }
    if not evidence_refs or not originality_refs:
        raise OutlineGenerationError("outline_support_input_empty")
    return evidence_refs, originality_refs


def _validated_refs(
    raw_evidence: object,
    raw_originality: object,
    *,
    allowed_evidence: set[str],
    allowed_originality: set[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    evidence_refs = tuple(
        _normalize_evidence_ref(ref)
        for ref in _string_list(raw_evidence, "outline_evidence_refs_invalid")
    )
    originality_refs = tuple(
        _normalize_originality_ref(ref, allowed_originality)
        for ref in _string_list(raw_originality, "outline_originality_refs_invalid")
    )
    if len(set(evidence_refs)) != len(evidence_refs):
        raise OutlineGenerationError("outline_evidence_ref_duplicate")
    if len(set(originality_refs)) != len(originality_refs):
        raise OutlineGenerationError("outline_originality_ref_duplicate")
    if any(ref not in allowed_evidence for ref in evidence_refs):
        raise OutlineGenerationError("outline_evidence_ref_outside_set")
    return evidence_refs, originality_refs


def _decode_model_output(raw: object) -> dict[str, object]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OutlineGenerationError("outline_model_output_json_invalid") from exc
    return _dict(raw, "outline_model_output_schema_invalid")


def _validate_model_output(raw: object, *, outline_input: OutlineInput) -> JournalOutline:
    payload = _decode_model_output(raw)
    allowed_evidence, allowed_originality = _allowed_refs(outline_input)

    primary_evidence, primary_originality = _validated_refs(
        payload.get("primary_answer_evidence_refs"),
        payload.get("primary_answer_originality_refs"),
        allowed_evidence=allowed_evidence,
        allowed_originality=allowed_originality,
    )
    primary_support_type = _support_type(
        payload.get("primary_answer_support_type"),
        "outline_primary_answer_support_type_invalid",
    )
    _validate_support(
        support_type=primary_support_type,
        evidence_refs=primary_evidence,
        originality_refs=primary_originality,
        code_prefix="outline_primary_answer",
    )

    raw_sections = payload.get("sections")
    if not isinstance(raw_sections, list) or not 3 <= len(raw_sections) <= 8:
        raise OutlineGenerationError("outline_section_count_invalid")
    sections: list[OutlineSection] = []
    for raw_section in raw_sections:
        section = _dict(raw_section, "outline_section_invalid")
        evidence_refs, originality_refs = _validated_refs(
            section.get("evidence_refs"),
            section.get("originality_refs"),
            allowed_evidence=allowed_evidence,
            allowed_originality=allowed_originality,
        )
        support_type = _support_type(
            section.get("support_type"),
            "outline_section_support_type_invalid",
        )
        _validate_support(
            support_type=support_type,
            evidence_refs=evidence_refs,
            originality_refs=originality_refs,
            code_prefix="outline_section",
        )
        claim_guards = tuple(
            _string_list(section.get("claim_guards"), "outline_claim_guards_invalid")
        )
        if not claim_guards:
            raise OutlineGenerationError("outline_claim_guards_required")
        sections.append(
            OutlineSection(
                section_id=_text(section.get("section_id"), "outline_section_id_required"),
                heading=_text(section.get("heading"), "outline_heading_required"),
                purpose=_text(section.get("purpose"), "outline_purpose_required"),
                answer_direction=_text(
                    section.get("answer_direction"),
                    "outline_answer_direction_required",
                ),
                support_type=support_type,
                evidence_refs=evidence_refs,
                originality_refs=originality_refs,
                claim_guards=claim_guards,
                reader_movement=_text(
                    section.get("reader_movement"),
                    "outline_reader_movement_required",
                ),
                internal_link_targets=tuple(
                    _string_list(
                        section.get("internal_link_targets"),
                        "outline_internal_link_targets_invalid",
                    )
                ),
            )
        )
    section_ids = [section.section_id for section in sections]
    if len(set(section_ids)) != len(section_ids):
        raise OutlineGenerationError("outline_section_id_duplicate")

    selected = outline_input.approved_angle.candidate
    return JournalOutline(
        primary_answer=_text(payload.get("primary_answer"), "outline_primary_answer_required"),
        primary_answer_support_type=primary_support_type,
        primary_answer_evidence_refs=primary_evidence,
        primary_answer_originality_refs=primary_originality,
        primary_answer_claim_guard=_text(
            payload.get("primary_answer_claim_guard"),
            "outline_primary_answer_claim_guard_required",
        ),
        sections=tuple(sections),
        must_not_claim=tuple(selected.excluded_claims),
        angle_risks=tuple(selected.risks),
    )


def _model_identity(model: OutlineModelPort) -> tuple[str, str] | None:
    resolver = getattr(model, "resolved_model_identity", None)
    if resolver is None:
        return None
    if not callable(resolver):
        raise OutlineGenerationError("outline_model_route_mismatch")
    identity = resolver()
    if (
        not isinstance(identity, tuple)
        or len(identity) != 2
        or any(not isinstance(value, str) or not value.strip() for value in identity)
    ):
        raise OutlineGenerationError("outline_model_route_mismatch")
    return identity[0].strip(), identity[1].strip()


async def _execution_manifest(
    session: AsyncSession,
    *,
    outline_input: OutlineInput,
    context_manifest_id: UUID,
    prompt_version: str,
    recipe_version: str,
) -> ContextManifest:
    manifest = await session.get(ContextManifest, context_manifest_id)
    run = await session.get(ContentRun, outline_input.approved_angle.artifact.run_id)
    if manifest is None or run is None or manifest.run_id != run.id:
        raise OutlineGenerationError("outline_context_manifest_mismatch")
    if manifest.settings_snapshot_id != run.settings_snapshot_id:
        raise OutlineGenerationError("outline_settings_snapshot_mismatch")
    if manifest.evidence_set_id != outline_input.bundle.evidence_set_id:
        raise OutlineGenerationError("outline_context_evidence_mismatch")
    if manifest.originality_pack_id != outline_input.bundle.originality_pack_id:
        raise OutlineGenerationError("outline_context_originality_mismatch")
    if manifest.prompt_version != prompt_version:
        raise OutlineGenerationError("outline_prompt_snapshot_mismatch")
    if manifest.recipe_version != recipe_version:
        raise OutlineGenerationError("outline_recipe_snapshot_mismatch")
    return manifest


async def _existing_outline(
    session: AsyncSession,
    *,
    run_id: UUID,
    fingerprint: str,
    outline_input: OutlineInput,
) -> OutlineGenerationResult | None:
    artifacts = list(
        (
            await session.scalars(
                select(Artifact)
                .where(Artifact.run_id == run_id, Artifact.artifact_type == "journal_outline")
                .order_by(Artifact.version)
            )
        ).all()
    )
    for artifact in artifacts:
        payload = artifact.content_json
        if not isinstance(payload, dict) or payload.get("generation_fingerprint") != fingerprint:
            continue
        if _canonical_hash(payload) != artifact.content_hash:
            raise OutlineGenerationError("outline_artifact_snapshot_stale")
        raw_outline = payload.get("outline")
        outline_payload = _dict(raw_outline, "outline_artifact_payload_invalid")
        model_output = {
            key: outline_payload[key]
            for key in (
                "primary_answer",
                "primary_answer_support_type",
                "primary_answer_evidence_refs",
                "primary_answer_originality_refs",
                "primary_answer_claim_guard",
                "sections",
            )
            if key in outline_payload
        }
        outline = _validate_model_output(model_output, outline_input=outline_input)
        if outline.to_dict() != outline_payload:
            raise OutlineGenerationError("outline_artifact_payload_stale")
        return OutlineGenerationResult(
            artifact=artifact,
            outline=outline,
            model_attempts=0,
            reused=True,
        )
    return None


async def persist_journal_outline(
    session: AsyncSession,
    *,
    outline_input: OutlineInput,
    outline: JournalOutline,
    provider: str,
    model: str,
    model_calls: int,
    prompt_version: str,
    recipe_version: str,
    context_manifest: ContextManifest,
    generator_version: str = OUTLINE_GENERATOR_VERSION,
    schema_version: int = OUTLINE_SCHEMA_VERSION,
) -> Artifact:
    """Persist one immutable Outline bound to exact approved upstream snapshots."""

    if not provider.strip() or not model.strip():
        raise OutlineGenerationError("outline_model_metadata_required")
    if isinstance(model_calls, bool) or not isinstance(model_calls, int) or model_calls <= 0:
        raise OutlineGenerationError("outline_model_call_count_invalid")
    input_hash = outline_model_input_hash(outline_input.model_input)
    fingerprint = _generation_fingerprint(
        model_input_hash=input_hash,
        provider=provider.strip(),
        model=model.strip(),
        prompt_version=prompt_version,
        recipe_version=recipe_version,
        context_manifest_hash=context_manifest.content_hash,
        generator_version=generator_version,
        schema_version=schema_version,
    )
    approved = outline_input.approved_angle
    bundle = outline_input.bundle
    payload: dict[str, object] = {
        "schema_version": schema_version,
        "artifact_type": "journal_outline",
        "generation_fingerprint": fingerprint,
        "journal_input_bundle": {
            "id": str(bundle.artifact.id),
            "version": bundle.artifact.version,
            "content_hash": bundle.artifact.content_hash,
        },
        "approved_angle": _approved_angle_payload(approved),
        "evidence_set": {
            "id": str(bundle.evidence_set_id),
            "version": bundle.evidence_set_version,
            "content_hash": bundle.evidence_set_hash,
        },
        "originality_pack": {
            "id": str(bundle.originality_pack_id),
            "snapshot_hash": bundle.originality_pack_hash,
        },
        "model_input": {"content_hash": input_hash},
        "execution_context": {
            "context_manifest_id": str(context_manifest.id),
            "context_manifest_hash": context_manifest.content_hash,
            "settings_snapshot_id": str(context_manifest.settings_snapshot_id),
            "prompt_version": prompt_version,
            "recipe_version": recipe_version,
        },
        "generator": {
            "version": generator_version,
            "schema_version": schema_version,
        },
        "model": {"provider": provider.strip(), "model": model.strip()},
        "provider_calls": 0,
        "model_calls": model_calls,
        "outline": outline.to_dict(),
    }
    content_hash = _canonical_hash(payload)
    existing = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == approved.artifact.run_id,
            Artifact.artifact_type == "journal_outline",
            Artifact.content_hash == content_hash,
        )
    )
    if existing is not None:
        if existing.content_json != payload:
            raise OutlineGenerationError("outline_artifact_hash_collision")
        return existing
    latest_version = await session.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.run_id == approved.artifact.run_id,
            Artifact.artifact_type == "journal_outline",
        )
    )
    artifact = Artifact(
        run_id=approved.artifact.run_id,
        step_run_id=context_manifest.step_run_id,
        artifact_type="journal_outline",
        locale=approved.candidate.locale,
        version=(latest_version or 0) + 1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    if artifact.step_run_id is not None:
        step = await session.get(StepRun, artifact.step_run_id)
        if step is None or step.run_id != artifact.run_id:
            raise OutlineGenerationError("outline_artifact_step_mismatch")
        if str(artifact.id) not in step.output_artifact_refs_json:
            step.output_artifact_refs_json = [*step.output_artifact_refs_json, str(artifact.id)]
            await session.flush()
    return artifact


class OutlineGenerator:
    """Generate and persist one exact, reviewable Journal Outline."""

    def __init__(self, *, max_attempts: int = 2) -> None:
        if (
            isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or not 1 <= max_attempts <= 3
        ):
            raise ValueError("max_attempts must be between 1 and 3")
        self.max_attempts = max_attempts

    async def generate_outline(
        self,
        session: AsyncSession,
        *,
        angle_artifact_id: UUID,
        expected_angle_artifact_version: int,
        expected_angle_artifact_hash: str,
        selected_angle_id: str,
        expected_candidate_hash: str,
        expected_approval_id: UUID,
        model: OutlineModelPort,
        provider: str,
        model_name: str,
        context_manifest_id: UUID,
        prompt_version: str,
        recipe_version: str,
        generator_version: str = OUTLINE_GENERATOR_VERSION,
        schema_version: int = OUTLINE_SCHEMA_VERSION,
    ) -> OutlineGenerationResult:
        outline_input = await load_outline_input(
            session,
            angle_artifact_id=angle_artifact_id,
            expected_angle_artifact_version=expected_angle_artifact_version,
            expected_angle_artifact_hash=expected_angle_artifact_hash,
            selected_angle_id=selected_angle_id,
            expected_candidate_hash=expected_candidate_hash,
            expected_approval_id=expected_approval_id,
        )
        manifest = await _execution_manifest(
            session,
            outline_input=outline_input,
            context_manifest_id=context_manifest_id,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
        )
        routed = _model_identity(model)
        if routed is not None and (
            provider.strip() != routed[0] or model_name.strip() != routed[1]
        ):
            raise OutlineGenerationError("outline_model_route_mismatch")
        artifact_provider, artifact_model = routed or (provider.strip(), model_name.strip())
        if not artifact_provider or not artifact_model:
            raise OutlineGenerationError("outline_model_metadata_required")
        input_hash = outline_model_input_hash(outline_input.model_input)
        fingerprint = _generation_fingerprint(
            model_input_hash=input_hash,
            provider=artifact_provider,
            model=artifact_model,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
            context_manifest_hash=manifest.content_hash,
            generator_version=generator_version,
            schema_version=schema_version,
        )
        existing = await _existing_outline(
            session,
            run_id=outline_input.approved_angle.artifact.run_id,
            fingerprint=fingerprint,
            outline_input=outline_input,
        )
        if existing is not None:
            return existing

        last_error: OutlineGenerationError | None = None
        model_input = cast(dict[str, object], copy.deepcopy(outline_input.model_input))
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw = await model.generate(input_bundle=model_input, attempt=attempt)
                outline = _validate_model_output(raw, outline_input=outline_input)
            except OutlineGenerationError as exc:
                last_error = exc
                if attempt == self.max_attempts:
                    raise OutlineGenerationError(
                        "outline_model_output_invalid",
                        f"bounded retries exhausted ({exc.code})",
                    ) from exc
                continue
            artifact = await persist_journal_outline(
                session,
                outline_input=outline_input,
                outline=outline,
                provider=artifact_provider,
                model=artifact_model,
                model_calls=attempt,
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                context_manifest=manifest,
                generator_version=generator_version,
                schema_version=schema_version,
            )
            return OutlineGenerationResult(
                artifact=artifact,
                outline=outline,
                model_attempts=attempt,
                reused=False,
            )
        raise OutlineGenerationError("outline_model_output_invalid") from last_error


__all__ = [
    "JournalOutline",
    "OutlineGenerationError",
    "OutlineGenerationResult",
    "OutlineGenerator",
    "OutlineInput",
    "OutlineModelPort",
    "OutlineSection",
    "OUTLINE_GENERATOR_VERSION",
    "OUTLINE_SCHEMA_VERSION",
    "load_outline_input",
    "outline_model_input_hash",
    "persist_journal_outline",
]
