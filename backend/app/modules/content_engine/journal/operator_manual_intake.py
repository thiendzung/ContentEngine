"""Founder-authored Journal intake mapped into canonical planning + operator records."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal import operator_runtime
from app.modules.content_engine.journal.models import (
    JournalIntakeSpec,
    JournalRequiredLocale,
    OperatorCommand,
)
from app.modules.content_engine.journal.operator_bootstrap import (
    OperatorBootstrapError,
    ensure_operator_bootstrap_run,
)
from app.modules.content_engine.journal.operator_control import (
    OperatorControlError,
    OperatorState,
    create_or_reuse_journal_case,
)
from app.modules.content_engine.journal.operator_locking import (
    lock_operator_idempotency,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    ensure_required_locales,
    ensure_start_to_angle_step,
    normalize_journal_locale,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    Project,
    utc_now,
)
from app.modules.knowledge.models import OriginalityPack
from app.modules.knowledge.originality_pack import (
    OriginalityPackApprovalError,
    approve_originality_pack,
    originality_pack_snapshot_hash,
)
from app.modules.research.evidence.contracts import ORIGINALITY_MATERIAL_TYPE


class FounderJournalIntakeResult(BaseModel):
    command_id: UUID
    need_hypothesis_id: UUID
    content_opportunity_id: UUID
    content_case_id: UUID
    bootstrap_run_id: UUID
    source_locale_variant_id: UUID
    originality_pack_id: UUID
    required_locales: list[str]
    coverage_requirements: list[str]
    research_country: str
    replayed: bool
    state: OperatorState


def _text(value: str, code: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise OperatorControlError(code)
    return normalized


def _normalized_locales(values: list[str]) -> list[str]:
    normalized = sorted(normalize_journal_locale(value) for value in values)
    if not normalized or any(not value or len(value) > 32 for value in normalized):
        raise OperatorControlError("operator_required_locales_invalid")
    if len(set(normalized)) != len(normalized):
        raise OperatorControlError("operator_required_locales_duplicate")
    return normalized


def _normalized_coverage_requirements(values: list[str]) -> list[str]:
    if not values or len(values) > 12:
        raise OperatorControlError("operator_manual_coverage_requirements_invalid")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value, "operator_manual_coverage_requirement_required")
        if len(text) > 500:
            raise OperatorControlError("operator_manual_coverage_requirement_too_long")
        key = text.casefold()
        if key in seen:
            raise OperatorControlError("operator_manual_coverage_requirement_duplicate")
        seen.add(key)
        normalized.append(text)
    return normalized


def _request_hash(**payload: object) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def _source_variant(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    locale: str,
) -> LocaleVariant:
    variant = await session.scalar(
        select(LocaleVariant)
        .where(
            LocaleVariant.content_case_id == content_case_id,
            LocaleVariant.locale == locale,
        )
        .limit(1)
    )
    if variant is None:
        raise OperatorControlError("operator_create_receipt_variant_missing")
    return variant


async def _approved_originality_pack(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> OriginalityPack:
    pack = await session.scalar(
        select(OriginalityPack)
        .where(
            OriginalityPack.content_case_id == content_case_id,
            OriginalityPack.status == "approved",
        )
        .order_by(OriginalityPack.created_at.asc(), OriginalityPack.id.asc())
        .limit(1)
    )
    if pack is None:
        raise OperatorControlError("operator_manual_intake_originality_missing")
    return pack


async def _replay_result(
    session: AsyncSession,
    *,
    command: OperatorCommand,
) -> FounderJournalIntakeResult:
    content_case = await session.get(ContentCase, command.content_case_id)
    if content_case is None or command.run_id is None:
        raise OperatorControlError("operator_manual_intake_receipt_missing")
    opportunity = await session.get(
        ContentOpportunity,
        content_case.content_opportunity_id,
    )
    need = await session.get(NeedHypothesis, content_case.need_hypothesis_id)
    spec = await session.scalar(
        select(JournalIntakeSpec).where(
            JournalIntakeSpec.content_case_id == content_case.id
        )
    )
    if opportunity is None or need is None or spec is None:
        raise OperatorControlError("operator_manual_intake_receipt_missing")
    variant = await _source_variant(
        session,
        content_case_id=content_case.id,
        locale=opportunity.locale,
    )
    pack = await _approved_originality_pack(
        session,
        content_case_id=content_case.id,
    )
    required = list(
        (
            await session.scalars(
                select(JournalRequiredLocale.locale)
                .where(JournalRequiredLocale.content_case_id == content_case.id)
                .order_by(JournalRequiredLocale.locale)
            )
        ).all()
    )
    state = await operator_runtime.get_operator_state(
        session,
        content_case_id=content_case.id,
    )
    return FounderJournalIntakeResult(
        command_id=command.id,
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        content_case_id=content_case.id,
        bootstrap_run_id=command.run_id,
        source_locale_variant_id=variant.id,
        originality_pack_id=pack.id,
        required_locales=required,
        coverage_requirements=list(opportunity.coverage_requirements_json),
        research_country=spec.research_country,
        replayed=True,
        state=state,
    )


async def create_founder_journal_intake(
    session: AsyncSession,
    *,
    project_slug: str,
    source_locale: str,
    research_country: str,
    required_locales: list[str],
    reader: str,
    situation: str,
    need: str,
    question: str,
    intent: str,
    promise: str,
    coverage_requirements: list[str],
    selection_reason: str,
    originality_material: str,
    originality_writer_use: str,
    originality_guardrails: str,
    idempotency_key: str,
    actor_id: str = "founder",
) -> FounderJournalIntakeResult:
    """Persist Founder intent without pretending it was discovered market/customer truth.

    The originality fields are explicit MOTGU-owned material submitted by the Founder.
    Submitting this exact request authorizes the exact resulting OriginalityPack snapshot.
    Intake is durable planning data; execution preflight is enforced before Job enqueue.
    """

    key = idempotency_key.strip()
    if not key or len(key) > 200:
        raise OperatorControlError("operator_idempotency_key_invalid")
    actor = _text(actor_id, "operator_actor_required")
    project_key = _text(project_slug, "operator_project_required")
    source = normalize_journal_locale(
        _text(source_locale, "operator_source_locale_required")
    )
    country = _text(
        research_country,
        "operator_research_country_required",
    ).lower()
    if len(country) > 8:
        raise OperatorControlError("operator_research_country_invalid")
    locales = _normalized_locales(required_locales)
    if source not in locales:
        raise OperatorControlError("operator_source_locale_not_required")

    reader_text = _text(reader, "operator_manual_reader_required")
    situation_text = _text(situation, "operator_manual_situation_required")
    need_text = _text(need, "operator_manual_need_required")
    question_text = _text(question, "operator_manual_question_required")
    intent_text = _text(intent, "operator_manual_intent_required")
    promise_text = _text(promise, "operator_manual_promise_required")
    coverage = _normalized_coverage_requirements(coverage_requirements)
    reason_text = _text(
        selection_reason,
        "operator_manual_selection_reason_required",
    )
    material_text = _text(
        originality_material,
        "operator_manual_originality_material_required",
    )
    writer_use_text = _text(
        originality_writer_use,
        "operator_manual_originality_writer_use_required",
    )
    guardrails_text = _text(
        originality_guardrails,
        "operator_manual_originality_guardrails_required",
    )
    request_hash = _request_hash(
        project_slug=project_key,
        source_locale=source,
        research_country=country,
        required_locales=locales,
        reader=reader_text,
        situation=situation_text,
        need=need_text,
        question=question_text,
        intent=intent_text,
        promise=promise_text,
        coverage_requirements=coverage,
        selection_reason=reason_text,
        originality_material=material_text,
        originality_writer_use=writer_use_text,
        originality_guardrails=guardrails_text,
    )

    await lock_operator_idempotency(session, key=key)
    existing = await session.scalar(
        select(OperatorCommand).where(OperatorCommand.idempotency_key == key)
    )
    if existing is not None:
        if (
            existing.intent != "create"
            or existing.resolved_action_key != "founder_manual_journal_intake"
            or existing.request_hash != request_hash
        ):
            raise OperatorControlError("operator_idempotency_conflict")
        return await _replay_result(session, command=existing)

    project = await session.scalar(
        select(Project).where(Project.slug == project_key).limit(1)
    )
    if project is None:
        raise OperatorControlError("operator_project_not_found")

    hypothesis = NeedHypothesis(
        project_id=project.id,
        audience_hypothesis_id=None,
        type="question",
        statement=need_text,
        audience_scope=reader_text,
        situation=situation_text,
        origin="founder_manual",
        status="PROPOSED",
        alternative_explanations_json=[],
        missing_evidence_json=[
            "Founder manual intake is editorial intent, not customer or market evidence.",
            "Factual support must pass the bounded research/read-source evidence gate.",
        ],
        version=1,
    )
    session.add(hypothesis)
    await session.flush()

    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale=source,
        reader=reader_text,
        situation=situation_text,
        need=need_text,
        question=question_text,
        intent=intent_text,
        promise=promise_text,
        coverage_requirements_json=coverage,
        motgu_material_refs_json=[],
        material_gaps_json=[
            "Factual evidence must be researched and read before Angle generation."
        ],
        existing_content_refs_json=[],
        what_is_actually_new=(
            "Founder-authored editorial framing. This record does not assert observed "
            "customer demand."
        ),
        next_discovery_step=(
            "Run bounded evidence research before Angle generation."
        ),
        decision="CREATE",
        priority="NOW",
        reasons_json=["Explicit Founder manual selection for Journal production."],
        suggested_content_type="journal",
        suggested_role="primary",
        version=1,
        selected_by=actor,
        selected_at=utc_now(),
        selection_reason=reason_text,
    )
    session.add(opportunity)
    await session.flush()
    session.add(
        HumanSelection(
            content_opportunity_id=opportunity.id,
            selected_by=actor,
            reason=reason_text,
            selected_at=opportunity.selected_at,
        )
    )
    await session.flush()

    created = await create_or_reuse_journal_case(
        session,
        content_opportunity_id=opportunity.id,
        expected_opportunity_version=opportunity.version,
    )
    session.add(
        JournalIntakeSpec(
            content_case_id=created.content_case_id,
            source_locale=source,
            research_country=country,
            intake_hash=request_hash,
            submitted_by=actor,
        )
    )
    await ensure_required_locales(
        session,
        content_case_id=created.content_case_id,
        source_locale=source,
        required_locales=locales,
        declared_by=actor,
    )

    pack = OriginalityPack(
        content_case_id=created.content_case_id,
        item_refs_json=[
            {
                "type": ORIGINALITY_MATERIAL_TYPE,
                "source_ref": f"founder_manual_intake:{request_hash}",
                "material": material_text,
                "writer_use": writer_use_text,
                "guardrails": guardrails_text,
                "approval_ref": f"founder:{actor}:manual_intake:{request_hash}",
            }
        ],
        summary=(
            "Founder-submitted MOTGU-owned editorial material. It is first-party "
            "originality input and must not be presented as external customer or "
            "market evidence."
        ),
        status="draft",
    )
    session.add(pack)
    await session.flush()
    try:
        pack = await approve_originality_pack(
            session,
            originality_pack_id=pack.id,
            expected_snapshot_hash=originality_pack_snapshot_hash(pack),
            approved_by=actor,
            approval_reason=(
                "Founder submitted and authorized this exact material at manual intake."
            ),
        )
    except OriginalityPackApprovalError as exc:
        raise OperatorControlError(str(exc)) from exc

    try:
        bootstrap_run, _ = await ensure_operator_bootstrap_run(
            session,
            content_case_id=created.content_case_id,
            locale_variant_id=created.source_locale_variant_id,
        )
    except OperatorBootstrapError as exc:
        raise OperatorControlError(exc.code) from exc
    await ensure_start_to_angle_step(session, run_id=bootstrap_run.id)
    state = await operator_runtime.get_operator_state(
        session,
        content_case_id=created.content_case_id,
        preflight_checked=True,
    )
    if state.status != "READY" or state.primary_intent != "start":
        raise OperatorControlError("operator_manual_intake_not_startable")

    command = OperatorCommand(
        content_case_id=created.content_case_id,
        run_id=bootstrap_run.id,
        step_run_id=state.current_step_run_id,
        job_id=None,
        result_ref_id=opportunity.id,
        intent="create",
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=state.state_version,
        resolved_action_key="founder_manual_journal_intake",
        status="completed",
        error_code=None,
        actor_id=actor,
        state_before=state.state_version,
        state_after=state.state_version,
    )
    session.add(command)
    await session.flush()
    return FounderJournalIntakeResult(
        command_id=command.id,
        need_hypothesis_id=hypothesis.id,
        content_opportunity_id=opportunity.id,
        content_case_id=created.content_case_id,
        bootstrap_run_id=bootstrap_run.id,
        source_locale_variant_id=created.source_locale_variant_id,
        originality_pack_id=pack.id,
        required_locales=locales,
        coverage_requirements=coverage,
        research_country=country,
        replayed=False,
        state=state,
    )


__all__ = ["FounderJournalIntakeResult", "create_founder_journal_intake"]
