"""CE05 T05.13 bounded Journal review/revise from immutable locale drafts."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.human_voice import (
    HUMAN_VOICE_POLICY_VERSION,
    REQUIRED_FORBIDDEN_INVENTIONS,
    HumanVoiceGuardError,
    validate_rewrite_structure,
    validate_text_truth_guards,
)
from app.modules.content_engine.journal.human_voice_trace import (
    HumanVoiceTraceError,
    load_human_voice_trace,
    persist_human_voice_trace,
)
from app.modules.content_engine.journal.writer import (
    JournalDraft,
    WriterGenerationError,
    WriterGenerationResult,
    WriterInput,
    WriterModelPort,
    _canonical_hash,
    _execution_manifest,
    _existing_draft,
    _generation_fingerprint,
    _model_identity,
    _validate_model_output,
    load_writer_input,
    persist_journal_draft,
    writer_model_input_hash,
)
from app.modules.harness.models import Artifact

REVIEW_REVISE_GENERATOR_VERSION = "ce05.journal_review_revise.v6"
REVIEW_REVISE_SCHEMA_VERSION = 1
_SUPPORTIVE_EVIDENCE_RELATIONS = ("supports", "qualifies")
_NON_SUPPORTIVE_EVIDENCE_RELATIONS = ("context_only", "contradicts")
_ALLOWED_EVIDENCE_RELATIONS = set(
    (*_SUPPORTIVE_EVIDENCE_RELATIONS, *_NON_SUPPORTIVE_EVIDENCE_RELATIONS)
)


@dataclass(frozen=True, slots=True)
class ReviewReviseInput:
    """Exact immutable source draft plus the Writer lineage used to revise it."""

    writer_input: WriterInput
    source_artifact: Artifact
    source_draft: JournalDraft
    model_input: dict[str, object]


def unresolved_factual_claims(draft: JournalDraft) -> tuple[str, ...]:
    """Return every unresolved item carried by a draft, including section-local items."""

    return (
        *draft.unresolved_factual_claims,
        *(claim for section in draft.sections for claim in section.unresolved_factual_claims),
    )


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise WriterGenerationError(code)
    return cast(dict[str, object], value)


def _source_unresolved_payload(draft: JournalDraft) -> dict[str, object]:
    return {
        "document": list(draft.unresolved_factual_claims),
        "sections": [
            {
                "section_id": section.section_id,
                "claims": list(section.unresolved_factual_claims),
            }
            for section in draft.sections
            if section.unresolved_factual_claims
        ],
    }


def _evidence_relation_policy(writer_input: WriterInput) -> dict[str, object]:
    """Expose exact locked Evidence relations so Review cannot treat context as support."""

    evidence_set = _dict(
        writer_input.model_input.get("evidence_set"),
        "review_revise_evidence_set_invalid",
    )
    raw_items = evidence_set.get("evidence")
    if not isinstance(raw_items, list):
        raise WriterGenerationError("review_revise_evidence_set_invalid")

    relations: dict[str, str] = {}
    for raw_item in raw_items:
        item = _dict(raw_item, "review_revise_evidence_item_invalid")
        evidence_id = item.get("evidence_id")
        relation = item.get("relation")
        if (
            not isinstance(evidence_id, str)
            or not evidence_id.strip()
            or not isinstance(relation, str)
            or relation not in _ALLOWED_EVIDENCE_RELATIONS
        ):
            raise WriterGenerationError("review_revise_evidence_relation_invalid")
        normalized_id = evidence_id.strip()
        if normalized_id in relations:
            raise WriterGenerationError("review_revise_evidence_relation_duplicate")
        relations[normalized_id] = relation

    return {
        "supportive_relations": list(_SUPPORTIVE_EVIDENCE_RELATIONS),
        "non_supportive_relations": list(_NON_SUPPORTIVE_EVIDENCE_RELATIONS),
        "relations_by_evidence_id": relations,
    }


def _segment_support_policy(draft: JournalDraft) -> dict[str, object]:
    """Describe where the Writer schema can bind support refs for visible copy."""

    return {
        "title": {
            "allowed_evidence_refs": [],
            "allowed_originality_refs": [],
            "require_non_assertive": True,
            "reason": "writer_schema_has_no_title_support_ref_fields",
        },
        "standfirst": {
            "allowed_evidence_refs": list(draft.lead_evidence_refs),
            "allowed_originality_refs": list(draft.lead_originality_refs),
        },
        "lead_markdown": {
            "allowed_evidence_refs": list(draft.lead_evidence_refs),
            "allowed_originality_refs": list(draft.lead_originality_refs),
        },
        "sections": [
            {
                "section_id": section.section_id,
                "allowed_evidence_refs": list(section.evidence_refs),
                "allowed_originality_refs": list(section.originality_refs),
            }
            for section in draft.sections
        ],
        "closing_markdown": {
            "allowed_evidence_refs": [],
            "allowed_originality_refs": [],
            "require_non_assertive": True,
            "reason": "writer_schema_has_no_closing_support_ref_fields",
        },
    }


def _human_voice_policy() -> dict[str, object]:
    return {
        "version": HUMAN_VOICE_POLICY_VERSION,
        "mode": "truth_preserving_native_rewrite",
        "may_improve": [
            "rhythm",
            "specificity",
            "warmth",
            "lived_texture",
            "natural_phrasing",
        ],
        "must_preserve": [
            "locale",
            "section_ids_and_order",
            "evidence_refs",
            "originality_refs",
            "internal_link_intents",
            "approved_truth_boundaries",
        ],
        "forbidden_inventions": list(REQUIRED_FORBIDDEN_INVENTIONS),
        "deterministic_guards": [
            "no_new_numeric_token_without_exact_source_or_allowed_support",
            "no_new_direct_quote_without_exact_source_or_allowed_support",
        ],
        "post_rewrite_assertion_audit_required": True,
        "authorship_detection": "not_part_of_task",
        "humanization_percentage": "forbidden",
        "extra_model_call": False,
    }


def _human_voice_evidence_catalog(
    writer_input: WriterInput,
) -> dict[str, tuple[str, ...]]:
    evidence_set = _dict(
        writer_input.model_input.get("evidence_set"),
        "review_revise_evidence_set_invalid",
    )
    raw_items = evidence_set.get("evidence")
    if not isinstance(raw_items, list):
        raise WriterGenerationError("review_revise_evidence_set_invalid")
    relation_policy = _evidence_relation_policy(writer_input)
    relations = relation_policy.get("relations_by_evidence_id")
    if not isinstance(relations, dict):
        raise WriterGenerationError("review_revise_evidence_relation_invalid")

    catalog: dict[str, tuple[str, ...]] = {}
    for raw_item in raw_items:
        item = _dict(raw_item, "review_revise_evidence_item_invalid")
        raw_id = item.get("evidence_id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise WriterGenerationError("review_revise_evidence_relation_invalid")
        evidence_id = raw_id.strip()
        relation = relations.get(evidence_id)
        if relation not in _ALLOWED_EVIDENCE_RELATIONS:
            raise WriterGenerationError("review_revise_evidence_relation_invalid")
        texts: list[str] = []
        if relation in _SUPPORTIVE_EVIDENCE_RELATIONS:
            value = item.get("excerpt")
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())
        catalog[evidence_id] = tuple(dict.fromkeys(texts))
    return catalog


def _human_voice_originality_catalog(
    writer_input: WriterInput,
) -> dict[str, tuple[str, ...]]:
    pack = _dict(
        writer_input.model_input.get("originality_pack"),
        "review_revise_originality_pack_invalid",
    )
    raw_items = pack.get("items")
    if not isinstance(raw_items, list):
        raise WriterGenerationError("review_revise_originality_pack_invalid")

    catalog: dict[str, tuple[str, ...]] = {}
    for raw_item in raw_items:
        item = _dict(raw_item, "review_revise_originality_item_invalid")
        raw_ref = item.get("source_ref")
        if not isinstance(raw_ref, str) or not raw_ref.strip():
            raise WriterGenerationError("review_revise_originality_ref_invalid")
        source_ref = raw_ref.strip()
        if source_ref in catalog:
            raise WriterGenerationError("review_revise_originality_ref_duplicate")
        texts: list[str] = []
        value = item.get("material")
        if isinstance(value, str) and value.strip():
            texts.append(value.strip())
        catalog[source_ref] = tuple(dict.fromkeys(texts))
    return catalog


def _human_voice_support_texts(
    *,
    evidence_catalog: dict[str, tuple[str, ...]],
    originality_catalog: dict[str, tuple[str, ...]],
    evidence_refs: tuple[str, ...],
    originality_refs: tuple[str, ...],
) -> tuple[str, ...]:
    texts: list[str] = []
    for evidence_ref in evidence_refs:
        if evidence_ref not in evidence_catalog:
            raise WriterGenerationError(
                "review_revise_human_voice_evidence_ref_unknown",
                evidence_ref,
            )
        texts.extend(evidence_catalog[evidence_ref])
    for originality_ref in originality_refs:
        if originality_ref not in originality_catalog:
            raise WriterGenerationError(
                "review_revise_human_voice_originality_ref_unknown",
                originality_ref,
            )
        texts.extend(originality_catalog[originality_ref])
    return tuple(dict.fromkeys(texts))


def _validate_human_voice_rewrite(
    *,
    review_input: ReviewReviseInput,
    revised: JournalDraft,
) -> None:
    source = review_input.source_draft
    validate_rewrite_structure(source=source, rewritten=revised)

    evidence_catalog = _human_voice_evidence_catalog(review_input.writer_input)
    originality_catalog = _human_voice_originality_catalog(review_input.writer_input)

    lead_support = _human_voice_support_texts(
        evidence_catalog=evidence_catalog,
        originality_catalog=originality_catalog,
        evidence_refs=source.lead_evidence_refs,
        originality_refs=source.lead_originality_refs,
    )
    validate_text_truth_guards(
        source_text=source.title,
        rewritten_text=revised.title,
    )
    validate_text_truth_guards(
        source_text=source.standfirst,
        rewritten_text=revised.standfirst,
        allowed_support_texts=lead_support,
    )
    validate_text_truth_guards(
        source_text=source.lead_markdown,
        rewritten_text=revised.lead_markdown,
        allowed_support_texts=lead_support,
    )

    for source_section, revised_section in zip(
        source.sections,
        revised.sections,
        strict=True,
    ):
        section_support = _human_voice_support_texts(
            evidence_catalog=evidence_catalog,
            originality_catalog=originality_catalog,
            evidence_refs=source_section.evidence_refs,
            originality_refs=source_section.originality_refs,
        )
        validate_text_truth_guards(
            source_text=source_section.heading,
            rewritten_text=revised_section.heading,
            allowed_support_texts=section_support,
        )
        validate_text_truth_guards(
            source_text=source_section.body_markdown,
            rewritten_text=revised_section.body_markdown,
            allowed_support_texts=section_support,
        )

    validate_text_truth_guards(
        source_text=source.closing_markdown,
        rewritten_text=revised.closing_markdown,
    )


def _validate_source_provenance(
    source_payload: dict[str, object],
    *,
    writer_input: WriterInput,
) -> None:
    if source_payload.get("artifact_type") != "journal_draft":
        raise WriterGenerationError("review_revise_source_payload_invalid")

    outline_ref = _dict(
        source_payload.get("journal_outline"),
        "review_revise_source_outline_ref_invalid",
    )
    if (
        outline_ref.get("id") != str(writer_input.outline_artifact.id)
        or outline_ref.get("version") != writer_input.outline_artifact.version
        or outline_ref.get("content_hash") != writer_input.outline_artifact.content_hash
    ):
        raise WriterGenerationError("review_revise_source_outline_mismatch")

    handoff_ref = _dict(
        source_payload.get("writer_handoff"),
        "review_revise_source_handoff_ref_invalid",
    )
    if (
        handoff_ref.get("id") != str(writer_input.handoff_artifact.id)
        or handoff_ref.get("content_hash") != writer_input.handoff_artifact.content_hash
        or handoff_ref.get("writer_run_id") != str(writer_input.writer_run.id)
        or handoff_ref.get("locale_variant_id") != str(writer_input.locale_variant.id)
    ):
        raise WriterGenerationError("review_revise_source_handoff_mismatch")


def _revision_model_input(
    *,
    writer_input: WriterInput,
    source_artifact: Artifact,
    source_draft: JournalDraft,
) -> dict[str, object]:
    model_input = copy.deepcopy(writer_input.model_input)
    model_input.update(
        {
            "source_draft_ref": {
                "id": str(source_artifact.id),
                "version": source_artifact.version,
                "content_hash": source_artifact.content_hash,
            },
            "source_draft": source_draft.to_dict(),
            "source_unresolved_factual_claims": _source_unresolved_payload(source_draft),
            "human_voice_policy": _human_voice_policy(),
            "revision_policy": {
                "mode": "bounded_review_revise",
                "evidence_relation_policy": _evidence_relation_policy(writer_input),
                "segment_support_policy": _segment_support_policy(source_draft),
                "requirements": [
                    "preserve_exact_section_ids_order_and_support_refs",
                    "review_every_factual_visual_and_live_claim_not_only_declared_unresolved_items",
                    "only_supports_or_qualifies_evidence_relations_can_support_factual_visual_or_live_claims",
                    "context_only_and_contradicts_relations_are_never_support_for_factual_visual_or_live_claims",
                    "remove_unsupported_factual_claims_or_rewrite_them_as_bounded_reader_guidance",
                    "rewrite_unsupported_broad_universal_or_epistemic_claims_as_bounded_reader_guidance",
                    "prefer_direct_reader_actions_over_unproven_universal_claims",
                    "title_has_no_support_ref_fields_and_must_not_contain_unsupported_factual_brand_visual_or_live_claims",
                    "rewrite_unsupported_title_as_non_assertive_reader_guidance_or_topic_label",
                    "avoid_unsupported_geographic_origin_provenance_authorship_or_local_making_propositions_in_title",
                    "closing_markdown_has_no_support_ref_fields_and_must_not_contain_factual_brand_visual_or_live_claims",
                    "keep_supported_factual_closing_points_in_an_existing_ref_bound_section_and_rewrite_closing_as_non_assertive_reader_guidance",
                    "resolve_or_remove_every_unsupported_intended_factual_claim",
                    "do_not_treat_missing_data_as_a_claim_when_the_prose_does_not_assert_it",
                    "never_fabricate_missing_artwork_artist_commerce_or_market_facts",
                    "improve_native_locale_clarity_without_using_sibling_draft_input",
                    "return_zero_unresolved_factual_claims",
                ],
            },
        }
    )
    return model_input


async def load_review_revise_input(
    session: AsyncSession,
    *,
    writer_run_id: UUID,
    source_draft_artifact_id: UUID,
    expected_source_draft_version: int,
    expected_source_draft_hash: str,
    outline_artifact_id: UUID,
    expected_outline_version: int,
    expected_outline_hash: str,
    locale: str,
) -> ReviewReviseInput:
    """Load and verify one immutable Writer draft as the only revision source."""

    writer_input = await load_writer_input(
        session,
        writer_run_id=writer_run_id,
        outline_artifact_id=outline_artifact_id,
        expected_outline_version=expected_outline_version,
        expected_outline_hash=expected_outline_hash,
        locale=locale,
    )
    source = await session.get(Artifact, source_draft_artifact_id)
    if source is None or source.artifact_type != "journal_draft":
        raise WriterGenerationError("review_revise_source_draft_not_found")
    if source.run_id != writer_run_id or source.locale != writer_input.locale:
        raise WriterGenerationError("review_revise_source_draft_lineage_mismatch")
    if (
        source.version != expected_source_draft_version
        or source.content_hash != expected_source_draft_hash
    ):
        raise WriterGenerationError("review_revise_source_draft_snapshot_mismatch")
    source_payload = _dict(source.content_json, "review_revise_source_payload_invalid")
    if _canonical_hash(source_payload) != source.content_hash:
        raise WriterGenerationError("review_revise_source_draft_snapshot_stale")
    _validate_source_provenance(source_payload, writer_input=writer_input)
    draft_payload = _dict(source_payload.get("draft"), "review_revise_source_draft_invalid")
    source_draft = _validate_model_output(draft_payload, writer_input=writer_input)
    if source_draft.to_dict() != draft_payload:
        raise WriterGenerationError("review_revise_source_draft_payload_stale")

    return ReviewReviseInput(
        writer_input=writer_input,
        source_artifact=source,
        source_draft=source_draft,
        model_input=_revision_model_input(
            writer_input=writer_input,
            source_artifact=source,
            source_draft=source_draft,
        ),
    )


def _revision_writer_input(value: ReviewReviseInput) -> WriterInput:
    base = value.writer_input
    return WriterInput(
        writer_run=base.writer_run,
        locale_variant=base.locale_variant,
        handoff_artifact=base.handoff_artifact,
        outline_artifact=base.outline_artifact,
        outline_payload=base.outline_payload,
        outline_input=base.outline_input,
        locale=base.locale,
        model_input=copy.deepcopy(value.model_input),
    )


class ReviewReviseGenerator:
    """Review/revise one immutable locale draft with bounded validation retries."""

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
        writer_run_id: UUID,
        source_draft_artifact_id: UUID,
        expected_source_draft_version: int,
        expected_source_draft_hash: str,
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
        generator_version: str = REVIEW_REVISE_GENERATOR_VERSION,
        schema_version: int = REVIEW_REVISE_SCHEMA_VERSION,
    ) -> WriterGenerationResult:
        review_input = await load_review_revise_input(
            session,
            writer_run_id=writer_run_id,
            source_draft_artifact_id=source_draft_artifact_id,
            expected_source_draft_version=expected_source_draft_version,
            expected_source_draft_hash=expected_source_draft_hash,
            outline_artifact_id=outline_artifact_id,
            expected_outline_version=expected_outline_version,
            expected_outline_hash=expected_outline_hash,
            locale=locale,
        )
        writer_input = _revision_writer_input(review_input)
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
            raise WriterGenerationError("review_revise_model_route_mismatch")
        artifact_provider, artifact_model = routed or (provider.strip(), model_name.strip())
        if not artifact_provider or not artifact_model:
            raise WriterGenerationError("review_revise_model_metadata_required")

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
            if unresolved_factual_claims(existing.draft):
                raise WriterGenerationError("review_revise_reused_draft_not_clean")
            try:
                _validate_human_voice_rewrite(
                    review_input=review_input,
                    revised=existing.draft,
                )
                await load_human_voice_trace(
                    session,
                    source_artifact=review_input.source_artifact,
                    source_draft=review_input.source_draft,
                    rewritten_artifact=existing.artifact,
                    rewritten_draft=existing.draft,
                )
            except HumanVoiceGuardError as exc:
                raise WriterGenerationError(
                    "review_revise_reused_human_voice_guard_failed",
                    exc.code,
                ) from exc
            except HumanVoiceTraceError as exc:
                raise WriterGenerationError(
                    "review_revise_reused_human_voice_trace_invalid",
                    exc.code,
                ) from exc
            return existing

        last_error: WriterGenerationError | None = None
        model_input = copy.deepcopy(writer_input.model_input)
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw = await model.generate(input_bundle=model_input, attempt=attempt)
                revised = _validate_model_output(raw, writer_input=writer_input)
                try:
                    _validate_human_voice_rewrite(
                        review_input=review_input,
                        revised=revised,
                    )
                except HumanVoiceGuardError as exc:
                    raise WriterGenerationError(
                        "review_revise_human_voice_guard_failed",
                        exc.code,
                    ) from exc
                if unresolved_factual_claims(revised):
                    raise WriterGenerationError("review_revise_unresolved_remaining")
            except WriterGenerationError as exc:
                last_error = exc
                if attempt == self.max_attempts:
                    raise WriterGenerationError(
                        "review_revise_model_output_invalid",
                        f"bounded retries exhausted ({exc.code})",
                    ) from exc
                continue

            artifact = await persist_journal_draft(
                session,
                writer_input=writer_input,
                draft=revised,
                provider=artifact_provider,
                model=artifact_model,
                model_calls=attempt,
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                context_manifest=manifest,
                generator_version=generator_version,
                schema_version=schema_version,
            )
            if artifact.id == review_input.source_artifact.id:
                raise WriterGenerationError("review_revise_source_artifact_reused_as_output")
            try:
                await persist_human_voice_trace(
                    session,
                    source_artifact=review_input.source_artifact,
                    source_draft=review_input.source_draft,
                    rewritten_artifact=artifact,
                    rewritten_draft=revised,
                )
            except HumanVoiceTraceError as exc:
                raise WriterGenerationError(
                    "review_revise_human_voice_trace_invalid",
                    exc.code,
                ) from exc
            return WriterGenerationResult(
                artifact=artifact,
                draft=revised,
                model_attempts=attempt,
                reused=False,
            )

        raise WriterGenerationError("review_revise_model_output_invalid") from last_error


__all__ = [
    "REVIEW_REVISE_GENERATOR_VERSION",
    "REVIEW_REVISE_SCHEMA_VERSION",
    "ReviewReviseGenerator",
    "ReviewReviseInput",
    "load_review_revise_input",
    "unresolved_factual_claims",
]
