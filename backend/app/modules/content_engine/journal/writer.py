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
from app.modules.content_engine.models import ContentCase, LocaleVariant
from app.modules.harness.models import Artifact, ContentRun, ContextManifest, StepRun, utc_now

WRITER_SCHEMA_VERSION = 1
WRITER_GENERATOR_VERSION = "ce05.journal_writer.v1"
WRITER_HANDOFF_SCHEMA_VERSION = 1
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
class WriterRunHandoff:
    run: ContentRun
    locale_variant: LocaleVariant
    artifact: Artifact
    created: bool


@dataclass(frozen=True, slots=True)
class WriterInput:
    writer_run: ContentRun
    locale_variant: LocaleVariant
    handoff_artifact: Artifact
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


def _case_payload(content_case: ContentCase) -> dict[str, object]:
    return {
        "id": str(content_case.id),
        "project_id": str(content_case.project_id),
        "content_type": content_case.content_type,
        "audience_hypothesis_id": (
            str(content_case.audience_hypothesis_id)
            if content_case.audience_hypothesis_id is not None
            else None
        ),
        "need_hypothesis_id": str(content_case.need_hypothesis_id),
        "content_opportunity_id": str(content_case.content_opportunity_id),
        "desired_action": content_case.desired_action,
        "content_hypothesis": content_case.content_hypothesis,
        "originality_statement": content_case.originality_statement,
        "reader_before": content_case.reader_before,
        "reader_after": content_case.reader_after,
        "status": content_case.status,
    }


def _variant_payload(variant: LocaleVariant) -> dict[str, object]:
    return {
        "id": str(variant.id),
        "content_case_id": str(variant.content_case_id),
        "locale": variant.locale,
        "content_role": variant.content_role,
        "primary_question": variant.primary_question,
        "primary_intent": variant.primary_intent,
        "secondary_intent": variant.secondary_intent,
        "primary_query": variant.primary_query,
        "keyword_notes": variant.keyword_notes_json,
        "emotion_arc": variant.emotion_arc_json,
        "must_include": variant.must_include_json,
        "must_not_claim": variant.must_not_claim_json,
        "status": variant.status,
    }


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


async def _load_exact_outline(
    session: AsyncSession,
    *,
    outline_artifact_id: UUID,
    expected_outline_version: int,
    expected_outline_hash: str,
) -> tuple[Artifact, dict[str, object], dict[str, object], OutlineInput]:
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
        raise WriterGenerationError("writer_outline_source_run_mismatch")
    return artifact, payload, outline_payload, upstream


def _writer_handoff_payload(
    *,
    source_run: ContentRun,
    outline_artifact: Artifact,
    locale_variant: LocaleVariant,
) -> dict[str, object]:
    return {
        "schema_version": WRITER_HANDOFF_SCHEMA_VERSION,
        "artifact_type": "writer_handoff",
        "source_run_id": str(source_run.id),
        "source_outline": {
            "id": str(outline_artifact.id),
            "version": outline_artifact.version,
            "content_hash": outline_artifact.content_hash,
        },
        "content_case_id": str(source_run.content_case_id),
        "target_locale_variant": {
            "id": str(locale_variant.id),
            "locale": locale_variant.locale,
        },
        "settings_snapshot_id": str(source_run.settings_snapshot_id),
    }


async def ensure_writer_run(
    session: AsyncSession,
    *,
    source_run_id: UUID,
    outline_artifact_id: UUID,
    expected_outline_version: int,
    expected_outline_hash: str,
    locale: str,
) -> WriterRunHandoff:
    """Create/reuse one locale-specific Writer run without changing the shared upstream run."""

    target_locale = _locale(locale)
    outline_artifact, _payload, _outline, _upstream = await _load_exact_outline(
        session,
        outline_artifact_id=outline_artifact_id,
        expected_outline_version=expected_outline_version,
        expected_outline_hash=expected_outline_hash,
    )
    if outline_artifact.run_id != source_run_id:
        raise WriterGenerationError("writer_source_run_mismatch")
    source_run = await session.get(ContentRun, source_run_id)
    if source_run is None:
        raise WriterGenerationError("writer_source_run_not_found")
    if source_run.status not in {"waiting_approval", "completed"}:
        raise WriterGenerationError("writer_source_run_state_invalid", source_run.status)
    content_case = await session.get(ContentCase, source_run.content_case_id)
    if content_case is None or content_case.project_id != source_run.project_id:
        raise WriterGenerationError("writer_content_case_invalid")
    variants = list(
        (
            await session.scalars(
                select(LocaleVariant).where(
                    LocaleVariant.content_case_id == source_run.content_case_id,
                    LocaleVariant.locale == target_locale,
                )
            )
        ).all()
    )
    if not variants:
        raise WriterGenerationError("writer_locale_variant_missing", target_locale)
    if len(variants) != 1:
        raise WriterGenerationError("writer_locale_variant_ambiguous", target_locale)
    variant = variants[0]

    handoff_payload = _writer_handoff_payload(
        source_run=source_run,
        outline_artifact=outline_artifact,
        locale_variant=variant,
    )
    handoff_hash = _canonical_hash(handoff_payload)
    existing_handoffs = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.artifact_type == "writer_handoff",
                    Artifact.content_hash == handoff_hash,
                )
            )
        ).all()
    )
    if len(existing_handoffs) > 1:
        raise WriterGenerationError("writer_handoff_duplicate")
    if existing_handoffs:
        handoff = existing_handoffs[0]
        if handoff.content_json != handoff_payload:
            raise WriterGenerationError("writer_handoff_hash_collision")
        run = await session.get(ContentRun, handoff.run_id)
        if run is None:
            raise WriterGenerationError("writer_run_not_found")
        if (
            run.id == source_run.id
            or run.project_id != source_run.project_id
            or run.content_case_id != source_run.content_case_id
            or run.locale_variant_id != variant.id
            or run.settings_snapshot_id != source_run.settings_snapshot_id
            or run.run_mode != "localize"
        ):
            raise WriterGenerationError("writer_handoff_run_mismatch")
        return WriterRunHandoff(
            run=run,
            locale_variant=variant,
            artifact=handoff,
            created=False,
        )

    run = ContentRun(
        project_id=source_run.project_id,
        content_case_id=source_run.content_case_id,
        locale_variant_id=variant.id,
        content_item_id=None,
        run_mode="localize",
        status="pending",
        current_step=None,
        settings_snapshot_id=source_run.settings_snapshot_id,
        started_at=utc_now(),
    )
    session.add(run)
    await session.flush()
    handoff = Artifact(
        run_id=run.id,
        artifact_type="writer_handoff",
        locale=target_locale,
        version=1,
        content_json=handoff_payload,
        content_hash=handoff_hash,
    )
    session.add(handoff)
    await session.flush()
    return WriterRunHandoff(
        run=run,
        locale_variant=variant,
        artifact=handoff,
        created=True,
    )


async def load_writer_input(
    session: AsyncSession,
    *,
    writer_run_id: UUID,
    outline_artifact_id: UUID,
    expected_outline_version: int,
    expected_outline_hash: str,
    locale: str,
) -> WriterInput:
    """Reload one exact accepted Outline and exact locale-specific Writer-run contract."""

    target_locale = _locale(locale)
    artifact, payload, outline_payload, upstream = await _load_exact_outline(
        session,
        outline_artifact_id=outline_artifact_id,
        expected_outline_version=expected_outline_version,
        expected_outline_hash=expected_outline_hash,
    )
    source_run = await session.get(ContentRun, artifact.run_id)
    writer_run = await session.get(ContentRun, writer_run_id)
    if source_run is None or writer_run is None:
        raise WriterGenerationError("writer_run_not_found")
    if writer_run.id == source_run.id:
        raise WriterGenerationError("writer_locale_run_required")
    if (
        writer_run.project_id != source_run.project_id
        or writer_run.content_case_id != source_run.content_case_id
        or writer_run.settings_snapshot_id != source_run.settings_snapshot_id
        or writer_run.run_mode != "localize"
    ):
        raise WriterGenerationError("writer_run_lineage_mismatch")
    variant = await session.get(LocaleVariant, writer_run.locale_variant_id)
    content_case = await session.get(ContentCase, writer_run.content_case_id)
    if variant is None or content_case is None:
        raise WriterGenerationError("writer_locale_context_missing")
    if variant.content_case_id != content_case.id or variant.locale != target_locale:
        raise WriterGenerationError("writer_locale_variant_mismatch")
    if content_case.project_id != writer_run.project_id:
        raise WriterGenerationError("writer_content_case_invalid")

    expected_handoff_payload = _writer_handoff_payload(
        source_run=source_run,
        outline_artifact=artifact,
        locale_variant=variant,
    )
    expected_handoff_hash = _canonical_hash(expected_handoff_payload)
    handoff = await session.scalar(
        select(Artifact).where(
            Artifact.run_id == writer_run.id,
            Artifact.artifact_type == "writer_handoff",
            Artifact.content_hash == expected_handoff_hash,
        )
    )
    if handoff is None or handoff.content_json != expected_handoff_payload:
        raise WriterGenerationError("writer_handoff_missing_or_stale")

    opportunity = _dict(upstream.model_input.get("opportunity"), "writer_opportunity_invalid")
    evidence_set = _dict(upstream.model_input.get("evidence_set"), "writer_evidence_input_invalid")
    originality_pack = _dict(
        upstream.model_input.get("originality_pack"),
        "writer_originality_input_invalid",
    )
    model_input: dict[str, object] = {
        "locale": target_locale,
        "independence_rule": (
            "Generate directly from the approved Outline, target LocaleVariant and shared evidence. "
            "Do not translate, inspect, quote or depend on another locale draft."
        ),
        "writer_handoff_ref": {
            "id": str(handoff.id),
            "content_hash": handoff.content_hash,
            "source_run_id": str(source_run.id),
        },
        "journal_outline_ref": {
            "id": str(artifact.id),
            "version": artifact.version,
            "content_hash": artifact.content_hash,
        },
        "content_case": _case_payload(content_case),
        "locale_variant": _variant_payload(variant),
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
        writer_run=writer_run,
        locale_variant=variant,
        handoff_artifact=handoff,
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
    run = writer_input.writer_run
    if manifest is None or manifest.run_id != run.id:
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
                    Artifact.run_id == writer_input.writer_run.id,
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
    """Persist one immutable locale draft bound to the exact accepted Outline and locale run."""

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
            Artifact.run_id == writer_input.writer_run.id,
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
            Artifact.run_id == writer_input.writer_run.id,
            Artifact.artifact_type == "journal_draft",
        )
    )
    artifact = Artifact(
        run_id=writer_input.writer_run.id,
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
        writer_run_id: UUID,
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
            writer_run_id=writer_run_id,
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
    "WriterRunHandoff",
    "WRITER_GENERATOR_VERSION",
    "WRITER_HANDOFF_SCHEMA_VERSION",
    "WRITER_SCHEMA_VERSION",
    "ensure_writer_run",
    "load_writer_input",
    "persist_journal_draft",
    "writer_model_input_hash",
]
