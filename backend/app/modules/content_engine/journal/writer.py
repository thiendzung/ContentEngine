"""CE05 T05.11/T05.12 grounded bilingual Journal draft generation."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.outline import OutlineInput, load_outline_input
from app.modules.harness.models import Artifact, ContentRun, ContextManifest, StepRun

WRITER_SCHEMA_VERSION = 1
WRITER_GENERATOR_VERSION = "ce05.journal_writer.v1"
SUPPORTED_WRITER_LOCALES = {"vi-VN", "en"}


class WriterGenerationError(ValueError):
    """Raised when Writer inputs, model output or persistence are unsafe."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class WriterModelPort(Protocol):
    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class DraftSection:
    section_id: str
    heading: str
    body_markdown: str
    evidence_refs: tuple[str, ...]
    originality_refs: tuple[str, ...]
    unresolved_factual_claims: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "heading": self.heading,
            "body_markdown": self.body_markdown,
            "evidence_refs": list(self.evidence_refs),
            "originality_refs": list(self.originality_refs),
            "unresolved_factual_claims": list(self.unresolved_factual_claims),
        }


@dataclass(frozen=True, slots=True)
class JournalDraft:
    locale: str
    title: str
    standfirst: str
    lead_markdown: str
    lead_evidence_refs: tuple[str, ...]
    lead_originality_refs: tuple[str, ...]
    sections: tuple[DraftSection, ...]
    closing_markdown: str
    internal_link_intents: tuple[str, ...]
    unresolved_factual_claims: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "locale": self.locale,
            "title": self.title,
            "standfirst": self.standfirst,
            "lead_markdown": self.lead_markdown,
            "lead_evidence_refs": list(self.lead_evidence_refs),
            "lead_originality_refs": list(self.lead_originality_refs),
            "sections": [section.to_dict() for section in self.sections],
            "closing_markdown": self.closing_markdown,
            "internal_link_intents": list(self.internal_link_intents),
            "unresolved_factual_claims": list(self.unresolved_factual_claims),
        }


@dataclass(frozen=True, slots=True)
class WriterInput:
    outline_artifact: Artifact
    outline_payload: dict[str, object]
    outline_input: OutlineInput
    locale: str
    model_input: dict[str, object]


@dataclass(frozen=True, slots=True)
class WriterGenerationResult:
    artifact: Artifact
    draft: JournalDraft
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


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise WriterGenerationError(code)
    return cast(dict[str, object], value)


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WriterGenerationError(code)
    return value.strip()


def _string_list(value: object, code: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise WriterGenerationError(code)
    return [item.strip() for item in value]


def _locale(value: str) -> str:
    locale = value.strip()
    if locale not in SUPPORTED_WRITER_LOCALES:
        raise WriterGenerationError("writer_locale_unsupported", locale)
    return locale


def _normalize_evidence_refs(values: object, code: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw in _string_list(values, code):
        ref = raw.removeprefix("evidence:")
        try:
            normalized.append(str(UUID(ref)))
        except ValueError as exc:
            raise WriterGenerationError(code) from exc
    if len(set(normalized)) != len(normalized):
        raise WriterGenerationError("writer_evidence_ref_duplicate")
    return tuple(normalized)


def _normalize_originality_refs(values: object, code: str) -> tuple[str, ...]:
    normalized = [raw.removeprefix("originality:") for raw in _string_list(values, code)]
    if len(set(normalized)) != len(normalized):
        raise WriterGenerationError("writer_originality_ref_duplicate")
    return tuple(normalized)


def writer_model_input_hash(model_input: dict[str, object]) -> str:
    return _canonical_hash(_clone_json(model_input))


def _generation_fingerprint(
    *,
    locale: str,
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
            "locale": locale,
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


def _outline_upstream(payload: dict[str, object]) -> tuple[UUID, int, str, str, str, UUID]:
    approved = _dict(payload.get("approved_angle"), "writer_approved_angle_ref_invalid")
    artifact_ref = _dict(approved.get("artifact"), "writer_angle_artifact_ref_invalid")
    approval_ref = _dict(approved.get("approval"), "writer_angle_approval_ref_invalid")
    raw_artifact_id = artifact_ref.get("id")
    raw_version = artifact_ref.get("version")
    raw_hash = artifact_ref.get("content_hash")
    raw_angle_id = approval_ref.get("selected_angle_id")
    raw_candidate_hash = approval_ref.get("selected_candidate_hash")
    raw_approval_id = approval_ref.get("id")
    if (
        not isinstance(raw_artifact_id, str)
        or not isinstance(raw_version, int)
        or isinstance(raw_version, bool)
        or raw_version <= 0
        or not isinstance(raw_hash, str)
        or not isinstance(raw_angle_id, str)
        or not raw_angle_id.strip()
        or not isinstance(raw_candidate_hash, str)
        or not isinstance(raw_approval_id, str)
    ):
        raise WriterGenerationError("writer_approved_angle_ref_invalid")
    try:
        artifact_id = UUID(raw_artifact_id)
        approval_id = UUID(raw_approval_id)
    except ValueError as exc:
        raise WriterGenerationError("writer_approved_angle_ref_invalid") from exc
    return (
        artifact_id,
        raw_version,
        raw_hash,
        raw_angle_id.strip(),
        raw_candidate_hash,
        approval_id,
    )


async def load_writer_input(
    session: AsyncSession,
    *,
    outline_artifact_id: UUID,
    expected_outline_version: int,
    expected_outline_hash: str,
    locale: str,
) -> WriterInput:
    """Reload one exact Outline and build an allow-listed locale-independent Writer input."""

    target_locale = _locale(locale)
    artifact = await session.get(Artifact, outline_artifact_id)
    if artifact is None or artifact.artifact_type != "journal_outline":
        raise WriterGenerationError("writer_outline_not_found")
    if artifact.version != expected_outline_version or artifact.content_hash != expected_outline_hash:
        raise WriterGenerationError("writer_outline_snapshot_mismatch")
    payload = _dict(artifact.content_json, "writer_outline_payload_invalid")
    if _canonical_hash(payload) != artifact.content_hash:
        raise WriterGenerationError("writer_outline_snapshot_stale")
    if payload.get("artifact_type") != "journal_outline":
        raise WriterGenerationError("writer_outline_payload_invalid")
    outline_payload = _dict(payload.get("outline"), "writer_outline_content_invalid")

    (
        angle_artifact_id,
        angle_version,
        angle_hash,
        selected_angle_id,
        candidate_hash,
        approval_id,
    ) = _outline_upstream(payload)
    try:
        upstream = await load_outline_input(
            session,
            angle_artifact_id=angle_artifact_id,
            expected_angle_artifact_version=angle_version,
            expected_angle_artifact_hash=angle_hash,
            selected_angle_id=selected_angle_id,
            expected_candidate_hash=candidate_hash,
            expected_approval_id=approval_id,
        )
    except ValueError as exc:
        raise WriterGenerationError("writer_outline_upstream_invalid", str(exc)) from exc
    if upstream.approved_angle.artifact.run_id != artifact.run_id:
        raise WriterGenerationError("writer_run_mismatch")

    opportunity = _dict(upstream.model_input.get("opportunity"), "writer_opportunity_invalid")
    evidence_set = _dict(upstream.model_input.get("evidence_set"), "writer_evidence_input_invalid")
    originality_pack = _dict(
        upstream.model_input.get("originality_pack"),
        "writer_originality_input_invalid",
    )
    model_input: dict[str, object] = {
        "locale": target_locale,
        "independence_rule": (
            "Generate directly from the approved Outline and shared evidence. "
            "Do not translate, inspect, quote or depend on another locale draft."
        ),
        "journal_outline_ref": {
            "id": str(artifact.id),
            "version": artifact.version,
            "content_hash": artifact.content_hash,
        },
        "outline": cast(dict[str, object], _clone_json(outline_payload)),
        "approved_angle": cast(dict[str, object], _clone_json(payload["approved_angle"])),
        "opportunity": cast(dict[str, object], _clone_json(opportunity)),
        "evidence_set": cast(dict[str, object], _clone_json(evidence_set)),
        "originality_pack": cast(dict[str, object], _clone_json(originality_pack)),
        "hard_guard": (
            "No specific current artwork price, sale status, physical location, artist intent, "
            "scarcity or other live commerce fact may be invented. If a new factual claim is "
            "needed but unsupported by this input, declare it unresolved instead of writing it."
        ),
    }
    return WriterInput(
        outline_artifact=artifact,
        outline_payload=outline_payload,
        outline_input=upstream,
        locale=target_locale,
        model_input=model_input,
    )


def _outline_ref_tuple(value: object, code: str, *, evidence: bool) -> tuple[str, ...]:
    if evidence:
        return _normalize_evidence_refs(value, code)
    return _normalize_originality_refs(value, code)


def _validate_model_output(raw: object, *, writer_input: WriterInput) -> JournalDraft:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WriterGenerationError("writer_model_output_json_invalid") from exc
    payload = _dict(raw, "writer_model_output_schema_invalid")
    output_locale = _text(payload.get("locale"), "writer_output_locale_required")
    if output_locale != writer_input.locale:
        raise WriterGenerationError("writer_output_locale_mismatch")

    outline = writer_input.outline_payload
    expected_lead_evidence = _outline_ref_tuple(
        outline.get("primary_answer_evidence_refs"),
        "writer_outline_primary_evidence_invalid",
        evidence=True,
    )
    expected_lead_originality = _outline_ref_tuple(
        outline.get("primary_answer_originality_refs"),
        "writer_outline_primary_originality_invalid",
        evidence=False,
    )
    lead_evidence = _normalize_evidence_refs(
        payload.get("lead_evidence_refs"),
        "writer_lead_evidence_invalid",
    )
    lead_originality = _normalize_originality_refs(
        payload.get("lead_originality_refs"),
        "writer_lead_originality_invalid",
    )
    if lead_evidence != expected_lead_evidence or lead_originality != expected_lead_originality:
        raise WriterGenerationError("writer_lead_support_mismatch")

    raw_outline_sections = outline.get("sections")
    raw_draft_sections = payload.get("sections")
    if not isinstance(raw_outline_sections, list) or not isinstance(raw_draft_sections, list):
        raise WriterGenerationError("writer_sections_invalid")
    if len(raw_draft_sections) != len(raw_outline_sections):
        raise WriterGenerationError("writer_section_count_mismatch")

    sections: list[DraftSection] = []
    for raw_outline_section, raw_draft_section in zip(
        raw_outline_sections,
        raw_draft_sections,
        strict=True,
    ):
        outline_section = _dict(raw_outline_section, "writer_outline_section_invalid")
        draft_section = _dict(raw_draft_section, "writer_section_invalid")
        expected_id = _text(outline_section.get("section_id"), "writer_outline_section_invalid")
        section_id = _text(draft_section.get("section_id"), "writer_section_id_required")
        if section_id != expected_id:
            raise WriterGenerationError("writer_section_order_mismatch")
        expected_evidence = _outline_ref_tuple(
            outline_section.get("evidence_refs"),
            "writer_outline_section_evidence_invalid",
            evidence=True,
        )
        expected_originality = _outline_ref_tuple(
            outline_section.get("originality_refs"),
            "writer_outline_section_originality_invalid",
            evidence=False,
        )
        evidence_refs = _normalize_evidence_refs(
            draft_section.get("evidence_refs"),
            "writer_section_evidence_invalid",
        )
        originality_refs = _normalize_originality_refs(
            draft_section.get("originality_refs"),
            "writer_section_originality_invalid",
        )
        if evidence_refs != expected_evidence or originality_refs != expected_originality:
            raise WriterGenerationError("writer_section_support_mismatch", section_id)
        sections.append(
            DraftSection(
                section_id=section_id,
                heading=_text(draft_section.get("heading"), "writer_section_heading_required"),
                body_markdown=_text(
                    draft_section.get("body_markdown"),
                    "writer_section_body_required",
                ),
                evidence_refs=evidence_refs,
                originality_refs=originality_refs,
                unresolved_factual_claims=tuple(
                    _string_list(
                        draft_section.get("unresolved_factual_claims"),
                        "writer_section_unresolved_invalid",
                    )
                ),
            )
        )

    allowed_links: set[str] = set()
    for raw_outline_section in raw_outline_sections:
        section = _dict(raw_outline_section, "writer_outline_section_invalid")
        allowed_links.update(
            _string_list(
                section.get("internal_link_targets"),
                "writer_outline_internal_links_invalid",
            )
        )
    internal_links = tuple(
        _string_list(payload.get("internal_link_intents"), "writer_internal_links_invalid")
    )
    if any(link not in allowed_links for link in internal_links):
        raise WriterGenerationError("writer_internal_link_outside_outline")

    return JournalDraft(
        locale=writer_input.locale,
        title=_text(payload.get("title"), "writer_title_required"),
        standfirst=_text(payload.get("standfirst"), "writer_standfirst_required"),
        lead_markdown=_text(payload.get("lead_markdown"), "writer_lead_required"),
        lead_evidence_refs=lead_evidence,
        lead_originality_refs=lead_originality,
        sections=tuple(sections),
        closing_markdown=_text(payload.get("closing_markdown"), "writer_closing_required"),
        internal_link_intents=internal_links,
        unresolved_factual_claims=tuple(
            _string_list(
                payload.get("unresolved_factual_claims"),
                "writer_unresolved_invalid",
            )
        ),
    )


def _model_identity(model: WriterModelPort) -> tuple[str, str] | None:
    resolver = getattr(model, "resolved_model_identity", None)
    if resolver is None:
        return None
    if not callable(resolver):
        raise WriterGenerationError("writer_model_route_mismatch")
    identity = resolver()
    if (
        not isinstance(identity, tuple)
        or len(identity) != 2
        or any(not isinstance(value, str) or not value.strip() for value in identity)
    ):
        raise WriterGenerationError("writer_model_route_mismatch")
    return identity[0].strip(), identity[1].strip()


async def _execution_manifest(
    session: AsyncSession,
    *,
    writer_input: WriterInput,
    context_manifest_id: UUID,
    prompt_version: str,
    recipe_version: str,
) -> ContextManifest:
    manifest = await session.get(ContextManifest, context_manifest_id)
    run = await session.get(ContentRun, writer_input.outline_artifact.run_id)
    if manifest is None or run is None or manifest.run_id != run.id:
        raise WriterGenerationError("writer_context_manifest_mismatch")
    if manifest.settings_snapshot_id != run.settings_snapshot_id:
        raise WriterGenerationError("writer_settings_snapshot_mismatch")
    bundle = writer_input.outline_input.bundle
    if manifest.evidence_set_id != bundle.evidence_set_id:
        raise WriterGenerationError("writer_context_evidence_mismatch")
    if manifest.originality_pack_id != bundle.originality_pack_id:
        raise WriterGenerationError("writer_context_originality_mismatch")
    if manifest.prompt_version != prompt_version:
        raise WriterGenerationError("writer_prompt_snapshot_mismatch")
    if manifest.recipe_version != recipe_version:
        raise WriterGenerationError("writer_recipe_snapshot_mismatch")
    return manifest


async def _existing_draft(
    session: AsyncSession,
    *,
    writer_input: WriterInput,
    fingerprint: str,
) -> WriterGenerationResult | None:
    artifacts = list(
        (
            await session.scalars(
                select(Artifact)
                .where(
                    Artifact.run_id == writer_input.outline_artifact.run_id,
                    Artifact.artifact_type == "journal_draft",
                    Artifact.locale == writer_input.locale,
                )
                .order_by(Artifact.version)
            )
        ).all()
    )
    for artifact in artifacts:
        payload = artifact.content_json
        if not isinstance(payload, dict) or payload.get("generation_fingerprint") != fingerprint:
            continue
        if _canonical_hash(payload) != artifact.content_hash:
            raise WriterGenerationError("writer_artifact_snapshot_stale")
        draft_payload = _dict(payload.get("draft"), "writer_artifact_payload_invalid")
        draft = _validate_model_output(draft_payload, writer_input=writer_input)
        if draft.to_dict() != draft_payload:
            raise WriterGenerationError("writer_artifact_payload_stale")
        return WriterGenerationResult(
            artifact=artifact,
            draft=draft,
            model_attempts=0,
            reused=True,
        )
    return None


async def persist_journal_draft(
    session: AsyncSession,
    *,
    writer_input: WriterInput,
    draft: JournalDraft,
    provider: str,
    model: str,
    model_calls: int,
    prompt_version: str,
    recipe_version: str,
    context_manifest: ContextManifest,
    generator_version: str = WRITER_GENERATOR_VERSION,
    schema_version: int = WRITER_SCHEMA_VERSION,
) -> Artifact:
    """Persist one immutable locale draft bound to the exact accepted Outline."""

    if not provider.strip() or not model.strip():
        raise WriterGenerationError("writer_model_metadata_required")
    if isinstance(model_calls, bool) or not isinstance(model_calls, int) or model_calls <= 0:
        raise WriterGenerationError("writer_model_call_count_invalid")
    input_hash = writer_model_input_hash(writer_input.model_input)
    fingerprint = _generation_fingerprint(
        locale=writer_input.locale,
        model_input_hash=input_hash,
        provider=provider.strip(),
        model=model.strip(),
        prompt_version=prompt_version,
        recipe_version=recipe_version,
        context_manifest_hash=context_manifest.content_hash,
        generator_version=generator_version,
        schema_version=schema_version,
    )
    bundle = writer_input.outline_input.bundle
    payload: dict[str, object] = {
        "schema_version": schema_version,
        "artifact_type": "journal_draft",
        "locale": writer_input.locale,
        "generation_fingerprint": fingerprint,
        "journal_outline": {
            "id": str(writer_input.outline_artifact.id),
            "version": writer_input.outline_artifact.version,
            "content_hash": writer_input.outline_artifact.content_hash,
        },
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
        "generator": {"version": generator_version, "schema_version": schema_version},
        "model": {"provider": provider.strip(), "model": model.strip()},
        "provider_calls": 0,
        "model_calls": model_calls,
        "draft": draft.to_dict(),
    }
    content_hash = _canonical_hash(payload)
    existing = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == writer_input.outline_artifact.run_id,
            Artifact.artifact_type == "journal_draft",
            Artifact.locale == writer_input.locale,
            Artifact.content_hash == content_hash,
        )
    )
    if existing is not None:
        if existing.content_json != payload:
            raise WriterGenerationError("writer_artifact_hash_collision")
        return existing
    latest_version = await session.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.run_id == writer_input.outline_artifact.run_id,
            Artifact.artifact_type == "journal_draft",
            Artifact.locale == writer_input.locale,
        )
    )
    artifact = Artifact(
        run_id=writer_input.outline_artifact.run_id,
        step_run_id=context_manifest.step_run_id,
        artifact_type="journal_draft",
        locale=writer_input.locale,
        version=(latest_version or 0) + 1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    if artifact.step_run_id is not None:
        step = await session.get(StepRun, artifact.step_run_id)
        if step is None or step.run_id != artifact.run_id:
            raise WriterGenerationError("writer_artifact_step_mismatch")
        if str(artifact.id) not in step.output_artifact_refs_json:
            step.output_artifact_refs_json = [*step.output_artifact_refs_json, str(artifact.id)]
            await session.flush()
    return artifact


class WriterGenerator:
    """Generate and persist one locale draft directly from the accepted Outline."""

    def __init__(self, *, max_attempts: int = 2) -> None:
        if (
            isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or not 1 <= max_attempts <= 3
        ):
            raise ValueError("max_attempts must be between 1 and 3")
        self.max_attempts = max_attempts

    async def generate_draft(
        self,
        session: AsyncSession,
        *,
        outline_artifact_id: UUID,
        expected_outline_version: int,
        expected_outline_hash: str,
        locale: str,
        model: WriterModelPort,
        provider: str,
        model_name: str,
        context_manifest_id: UUID,
        prompt_version: str,
        recipe_version: str,
        generator_version: str = WRITER_GENERATOR_VERSION,
        schema_version: int = WRITER_SCHEMA_VERSION,
    ) -> WriterGenerationResult:
        writer_input = await load_writer_input(
            session,
            outline_artifact_id=outline_artifact_id,
            expected_outline_version=expected_outline_version,
            expected_outline_hash=expected_outline_hash,
            locale=locale,
        )
        manifest = await _execution_manifest(
            session,
            writer_input=writer_input,
            context_manifest_id=context_manifest_id,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
        )
        routed = _model_identity(model)
        if routed is not None and (
            provider.strip() != routed[0] or model_name.strip() != routed[1]
        ):
            raise WriterGenerationError("writer_model_route_mismatch")
        artifact_provider, artifact_model = routed or (provider.strip(), model_name.strip())
        if not artifact_provider or not artifact_model:
            raise WriterGenerationError("writer_model_metadata_required")
        input_hash = writer_model_input_hash(writer_input.model_input)
        fingerprint = _generation_fingerprint(
            locale=writer_input.locale,
            model_input_hash=input_hash,
            provider=artifact_provider,
            model=artifact_model,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
            context_manifest_hash=manifest.content_hash,
            generator_version=generator_version,
            schema_version=schema_version,
        )
        existing = await _existing_draft(
            session,
            writer_input=writer_input,
            fingerprint=fingerprint,
        )
        if existing is not None:
            return existing

        last_error: WriterGenerationError | None = None
        model_input = copy.deepcopy(writer_input.model_input)
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw = await model.generate(input_bundle=model_input, attempt=attempt)
                draft = _validate_model_output(raw, writer_input=writer_input)
            except WriterGenerationError as exc:
                last_error = exc
                if attempt == self.max_attempts:
                    raise WriterGenerationError(
                        "writer_model_output_invalid",
                        f"bounded retries exhausted ({exc.code})",
                    ) from exc
                continue
            artifact = await persist_journal_draft(
                session,
                writer_input=writer_input,
                draft=draft,
                provider=artifact_provider,
                model=artifact_model,
                model_calls=attempt,
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                context_manifest=manifest,
                generator_version=generator_version,
                schema_version=schema_version,
            )
            return WriterGenerationResult(
                artifact=artifact,
                draft=draft,
                model_attempts=attempt,
                reused=False,
            )
        raise WriterGenerationError("writer_model_output_invalid") from last_error


__all__ = [
    "DraftSection",
    "JournalDraft",
    "SUPPORTED_WRITER_LOCALES",
    "WriterGenerationError",
    "WriterGenerationResult",
    "WriterGenerator",
    "WriterInput",
    "WriterModelPort",
    "WRITER_GENERATOR_VERSION",
    "WRITER_SCHEMA_VERSION",
    "load_writer_input",
    "persist_journal_draft",
    "writer_model_input_hash",
]
