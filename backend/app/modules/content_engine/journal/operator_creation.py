"""Idempotent operator receipt for Journal case creation."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.journal.operator_control import (
    OperatorControlError,
    OperatorState,
    create_or_reuse_journal_case,
    get_operator_state,
)
from app.modules.content_engine.models import LocaleVariant


class OperatorCreateResult(BaseModel):
    command_id: UUID
    content_case_id: UUID
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
        variant = await session.scalar(
            select(LocaleVariant)
            .where(LocaleVariant.content_case_id == existing.content_case_id)
            .order_by(LocaleVariant.created_at, LocaleVariant.id)
            .limit(1)
        )
        if variant is None:
            raise OperatorControlError("operator_create_receipt_variant_missing")
        state = await get_operator_state(session, content_case_id=existing.content_case_id)
        return OperatorCreateResult(
            command_id=existing.id,
            content_case_id=existing.content_case_id,
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
    state = created.state
    command = OperatorCommand(
        content_case_id=created.content_case_id,
        run_id=None,
        step_run_id=None,
        job_id=None,
        intent="create",
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=state.state_version,
        resolved_action_key="create_journal_case",
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
        source_locale_variant_id=created.source_locale_variant_id,
        reused_case=created.reused,
        replayed=False,
        state=state,
    )


__all__ = ["OperatorCreateResult", "create_journal_case_with_receipt"]
