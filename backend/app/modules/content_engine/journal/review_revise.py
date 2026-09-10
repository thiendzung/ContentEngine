"""CE05 T05.13 bounded Journal review/revise from immutable locale drafts."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

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
from app.modules.harness.models import Artifact, ContextManifest

REVIEW_REVISE_GENERATOR_VERSION = "ce05.journal_review_revise.v1"
REVIEW_REVISE_SCHEMA_VERSION = 1


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
            "revision_policy": {
                "mode": "bounded_review_revise",
                "requirements": [
                    "preserve_exact_section_ids_order_and_support_refs",
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
            return existing

        last_error: WriterGenerationError | None = None
        model_input = copy.deepcopy(writer_input.model_input)
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw = await model.generate(input_bundle=model_input, attempt=attempt)
                revised = _validate_model_output(raw, writer_input=writer_input)
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
