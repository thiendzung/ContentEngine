"""Idempotent operator receipt for Journal case/run creation."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.journal.operator_bootstrap import (
    OperatorBootstrapError,
    ensure_operator_bootstrap_run,
)
from app.modules.content_engine.journal.operator_control import (
    OperatorControlError,
    OperatorState,
    create_or_reuse_journal_case,
    get_operator_state,
)
from app.modules.content_engine.models import ContentCase, ContentOpportunity, LocaleVariant


class OperatorCreateResult(BaseModel):
    command_id: UUID
    content_case_id: UUID
    bootstrap_run_id: UUID
    source_locale_variant_id: UUID
    reused_case: bool
    replayed: bool
    state: OperatorState


def _request_hash(*, opportunity_id: UUID, version: int) -> str:
    raw = json.dumps(
        {"content_opportunity_id": str(opportunity_id), "expected_opportunity_version": version},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def _source_variant_for_case(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> LocaleVariant:
    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None:
        raise OperatorControlError("operator_create_receipt_case_missing")
    opportunity = await session.get(ContentOpportunity, content_case.content_opportunity_id)
    if opportunity is None:
        raise OperatorControlError("operator_create_receipt_opportunity_missing")
    variant = await session.scalar(
        select(LocaleVariant)
        .where(
            LocaleVariant.content_case_id == content_case.id,
            LocaleVariant.locale == opportunity.locale,
        )
        .order_by(LocaleVariant.created_at, LocaleVariant.id)
        .limit(1)
    )
    if variant is None:
        raise OperatorControlError("operator_create_receipt_variant_missing")
    return variant


async def create_journal_case_with_receipt(
    session: AsyncSession,
    *,
    content_opportunity_id: UUID,
    expected_opportunity_version: int,
    idempotency_key: str,
    actor_id: str = "founder",
) -> OperatorCreateResult:
    key = idempotency_key.strip()
    if not key or len(key) > 200:
        raise OperatorControlError("operator_idempotency_key_invalid")
    request_hash = _request_hash(
        opportunity_id=content_opportunity_id,
        version=expected_opportunity_version,
    )
    existing = await session.scalar(
        select(OperatorCommand).where(OperatorCommand.idempotency_key == key)
    )
    if existing is not None:
        if existing.intent != "create" or existing.request_hash != request_hash:
            raise OperatorControlError("operator_idempotency_conflict")
        if existing.run_id is None:
            raise OperatorControlError("operator_create_receipt_run_missing")
        variant = await _source_variant_for_case(
            session,
            content_case_id=existing.content_case_id,
        )
        state = await get_operator_state(session, content_case_id=existing.content_case_id)
        return OperatorCreateResult(
            command_id=existing.id,
            content_case_id=existing.content_case_id,
            bootstrap_run_id=existing.run_id,
            source_locale_variant_id=variant.id,
            reused_case=True,
            replayed=True,
            state=state,
        )

    created = await create_or_reuse_journal_case(
        session,
        content_opportunity_id=content_opportunity_id,
        expected_opportunity_version=expected_opportunity_version,
    )
    try:
        bootstrap_run, reused_run = await ensure_operator_bootstrap_run(
            session,
            content_case_id=created.content_case_id,
            locale_variant_id=created.source_locale_variant_id,
        )
    except OperatorBootstrapError as exc:
        raise OperatorControlError(exc.code) from exc

    state = await get_operator_state(session, content_case_id=created.content_case_id)
    command = OperatorCommand(
        content_case_id=created.content_case_id,
        run_id=bootstrap_run.id,
        step_run_id=None,
        job_id=None,
        intent="create",
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=state.state_version,
        resolved_action_key="create_journal_case_run",
        status="completed",
        error_code=None,
        actor_id=actor_id,
        state_before=state.state_version,
        state_after=state.state_version,
    )
    session.add(command)
    await session.flush()
    return OperatorCreateResult(
        command_id=command.id,
        content_case_id=created.content_case_id,
        bootstrap_run_id=bootstrap_run.id,
        source_locale_variant_id=created.source_locale_variant_id,
        reused_case=created.reused or reused_run,
        replayed=False,
        state=state,
    )


__all__ = ["OperatorCreateResult", "create_journal_case_with_receipt"]
