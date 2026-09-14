"""Founder-authored Journal intake mapped into canonical planning + operator records."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import JournalRequiredLocale, OperatorCommand
from app.modules.content_engine.journal.operator_bootstrap import (
    OperatorBootstrapError,
    ensure_operator_bootstrap_run,
)
from app.modules.content_engine.journal.operator_control import (
    OperatorControlError,
    OperatorState,
    create_or_reuse_journal_case,
)
from app.modules.content_engine.journal.operator_locking import lock_operator_idempotency
from app.modules.content_engine.journal.operator_vertical_slice import (
    ensure_required_locales,
    ensure_start_to_angle_step,
    get_operator_state_v45,
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


class FounderJournalIntakeResult(BaseModel):
    command_id: UUID
    need_hypothesis_id: UUID
    content_opportunity_id: UUID
    content_case_id: UUID
    bootstrap_run_id: UUID
    source_locale_variant_id: UUID
    required_locales: list[str]
    replayed: bool
    state: OperatorState


def _text(value: str, code: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise OperatorControlError(code)
    return normalized


def _normalized_locales(values: list[str]) -> list[str]:
    normalized = sorted(value.strip().lower() for value in values)
    if not normalized or any(not value or len(value) > 32 for value in normalized):
        raise OperatorControlError("operator_required_locales_invalid")
    if len(set(normalized)) != len(normalized):
        raise OperatorControlError("operator_required_locales_duplicate")
    return normalized


def _request_hash(
    *,
    project_slug: str,
    source_locale: str,
    required_locales: list[str],
    reader: str,
    situation: str,
    need: str,
    question: str,
    intent: str,
    promise: str,
    selection_reason: str,
) -> str:
    payload = {
        "project_slug": project_slug.strip(),
        "source_locale": source_locale.strip().lower(),
        "required_locales": _normalized_locales(required_locales),
        "reader": reader.strip(),
        "situation": situation.strip(),
        "need": need.strip(),
        "question": question.strip(),
        "intent": intent.strip(),
        "promise": promise.strip(),
        "selection_reason": selection_reason.strip(),
    }
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


async def _replay_result(
    session: AsyncSession,
    *,
    command: OperatorCommand,
) -> FounderJournalIntakeResult:
    content_case = await session.get(ContentCase, command.content_case_id)
    if content_case is None or command.run_id is None:
        raise OperatorControlError("operator_manual_intake_receipt_missing")
    opportunity = await session.get(ContentOpportunity, content_case.content_opportunity_id)
    if opportunity is None:
        raise OperatorControlError("operator_create_receipt_opportunity_missing")
    need = await session.get(NeedHypothesis, content_case.need_hypothesis_id)
    if need is None:
        raise OperatorControlError("operator_manual_intake_need_missing")
    variant = await _source_variant(
        session,
        content_case_id=content_case.id,
        locale=opportunity.locale,
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
    state = await get_operator_state_v45(session, content_case_id=content_case.id)
    return FounderJournalIntakeResult(
        command_id=command.id,
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        content_case_id=content_case.id,
        bootstrap_run_id=command.run_id,
        source_locale_variant_id=variant.id,
        required_locales=required,
        replayed=True,
        state=state,
    )


async def create_founder_journal_intake(
    session: AsyncSession,
    *,
    project_slug: str,
    source_locale: str,
    required_locales: list[str],
    reader: str,
    situation: str,
    need: str,
    question: str,
    intent: str,
    promise: str,
    selection_reason: str,
    idempotency_key: str,
    actor_id: str = "founder",
) -> FounderJournalIntakeResult:
    """Persist Founder intent without pretending it was discovered market/customer truth."""

    key = idempotency_key.strip()
    if not key or len(key) > 200:
        raise OperatorControlError("operator_idempotency_key_invalid")
    actor = _text(actor_id, "operator_actor_required")
    project_key = _text(project_slug, "operator_project_required")
    source = _text(source_locale, "operator_source_locale_required").lower()
    locales = _normalized_locales(required_locales)
    if source not in locales:
        raise OperatorControlError("operator_source_locale_not_required")

    normalized_reader = _text(reader, "operator_manual_reader_required")
    normalized_situation = _text(situation, "operator_manual_situation_required")
    normalized_need = _text(need, "operator_manual_need_required")
    normalized_question = _text(question, "operator_manual_question_required")
    normalized_intent = _text(intent, "operator_manual_intent_required")
    normalized_promise = _text(promise, "operator_manual_promise_required")
    normalized_reason = _text(selection_reason, "operator_manual_selection_reason_required")

    request_hash = _request_hash(
        project_slug=project_key,
        source_locale=source,
        required_locales=locales,
        reader=normalized_reader,
        situation=normalized_situation,
        need=normalized_need,
        question=normalized_question,
        intent=normalized_intent,
        promise=normalized_promise,
        selection_reason=normalized_reason,
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

    project = await session.scalar(select(Project).where(Project.slug == project_key).limit(1))
    if project is None:
        raise OperatorControlError("operator_project_not_found")

    hypothesis = NeedHypothesis(
        project_id=project.id,
        audience_hypothesis_id=None,
        type="question",
        statement=normalized_need,
        audience_scope=normalized_reader,
        situation=normalized_situation,
        origin="founder_manual",
        status="PROPOSED",
        alternative_explanations_json=[],
        missing_evidence_json=[
            "Founder manual intake is editorial intent, not customer or market evidence.",
            "Factual support must pass the bounded research/read-source evidence gate.",
        ],
        version=1,
        reviewed_by=None,
        reviewed_at=None,
        review_reason=None,
    )
    session.add(hypothesis)
    await session.flush()

    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale=source,
        reader=normalized_reader,
        situation=normalized_situation,
        need=normalized_need,
        question=normalized_question,
        intent=normalized_intent,
        promise=normalized_promise,
        motgu_material_refs_json=[],
        material_gaps_json=[
            "Factual evidence must be researched and read before Angle generation.",
            "MOTGU-owned originality material must remain separately provenance-bound.",
        ],
        existing_content_refs_json=[],
        what_is_actually_new=(
            "Founder-authored editorial framing. This record does not assert observed customer demand."
        ),
        next_discovery_step="Run bounded evidence research and validate MOTGU-owned originality input.",
        decision="CREATE",
        priority="NOW",
        reasons_json=["Explicit Founder manual selection for Journal production."],
        suggested_content_type="journal",
        suggested_role="primary",
        version=1,
        selected_by=actor,
        selected_at=utc_now(),
        selection_reason=normalized_reason,
    )
    session.add(opportunity)
    await session.flush()
    session.add(
        HumanSelection(
            content_opportunity_id=opportunity.id,
            selected_by=actor,
            reason=normalized_reason,
            selected_at=opportunity.selected_at,
        )
    )
    await session.flush()

    created = await create_or_reuse_journal_case(
        session,
        content_opportunity_id=opportunity.id,
        expected_opportunity_version=opportunity.version,
    )
    await ensure_required_locales(
        session,
        content_case_id=created.content_case_id,
        source_locale=source,
        required_locales=locales,
        declared_by=actor,
    )
    try:
        bootstrap_run, _ = await ensure_operator_bootstrap_run(
            session,
            content_case_id=created.content_case_id,
            locale_variant_id=created.source_locale_variant_id,
        )
    except OperatorBootstrapError as exc:
        raise OperatorControlError(exc.code) from exc
    await ensure_start_to_angle_step(session, run_id=bootstrap_run.id)

    state = await get_operator_state_v45(session, content_case_id=created.content_case_id)
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
        required_locales=locales,
        replayed=False,
        state=state,
    )


__all__ = ["FounderJournalIntakeResult", "create_founder_journal_intake"]
