from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import LocaleVariant
from app.modules.harness.models import ContentRun
from app.modules.knowledge.brief_models import JournalKnowledgeBriefBinding
from app.modules.knowledge.brief_ref import (
    KnowledgeBriefRefError,
    load_bound_knowledge_brief,
)


class KnowledgeBriefBindingError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class BoundKnowledgeBrief:
    binding: JournalKnowledgeBriefBinding
    brief_id: UUID
    snapshot_hash: str


def _actor(value: str) -> str:
    actor = value.strip()
    if not actor:
        raise KnowledgeBriefBindingError("knowledge_brief_binding_actor_required")
    return actor


async def _run_scope(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> tuple[ContentRun, LocaleVariant]:
    run = await session.get(ContentRun, run_id)
    if run is None:
        raise KnowledgeBriefBindingError("knowledge_brief_binding_run_not_found")
    variant = await session.get(LocaleVariant, run.locale_variant_id)
    if variant is None or variant.content_case_id != run.content_case_id:
        raise KnowledgeBriefBindingError("knowledge_brief_binding_variant_mismatch")
    return run, variant


async def bind_knowledge_brief_to_run(
    session: AsyncSession,
    *,
    run_id: UUID,
    knowledge_brief_id: UUID,
    bound_by: str,
) -> JournalKnowledgeBriefBinding:
    """Bind one exact verified K5 brief to a run; exact replay is idempotent."""

    actor = _actor(bound_by)
    run, variant = await _run_scope(session, run_id=run_id)
    try:
        brief = await load_bound_knowledge_brief(
            session,
            brief_id=knowledge_brief_id,
            project_id=run.project_id,
            content_case_id=run.content_case_id,
            locale=variant.locale,
        )
    except KnowledgeBriefRefError as exc:
        raise KnowledgeBriefBindingError(exc.code) from exc

    existing = await session.scalar(
        select(JournalKnowledgeBriefBinding).where(
            JournalKnowledgeBriefBinding.run_id == run.id
        )
    )
    if existing is not None:
        if (
            existing.content_case_id != run.content_case_id
            or existing.locale_variant_id != variant.id
            or existing.knowledge_brief_id != brief.id
            or existing.knowledge_brief_hash != brief.snapshot_hash
            or existing.bound_by != actor
        ):
            raise KnowledgeBriefBindingError("knowledge_brief_binding_conflict")
        return existing

    binding = JournalKnowledgeBriefBinding(
        run_id=run.id,
        content_case_id=run.content_case_id,
        locale_variant_id=variant.id,
        knowledge_brief_id=brief.id,
        knowledge_brief_hash=brief.snapshot_hash,
        bound_by=actor,
    )
    session.add(binding)
    await session.flush()
    return binding


async def load_run_knowledge_brief_binding(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> BoundKnowledgeBrief | None:
    """Load and revalidate the immutable run binding before production use."""

    binding = await session.scalar(
        select(JournalKnowledgeBriefBinding).where(
            JournalKnowledgeBriefBinding.run_id == run_id
        )
    )
    if binding is None:
        return None

    run, variant = await _run_scope(session, run_id=run_id)
    if (
        binding.content_case_id != run.content_case_id
        or binding.locale_variant_id != variant.id
    ):
        raise KnowledgeBriefBindingError("knowledge_brief_binding_scope_mismatch")
    try:
        brief = await load_bound_knowledge_brief(
            session,
            brief_id=binding.knowledge_brief_id,
            project_id=run.project_id,
            content_case_id=run.content_case_id,
            locale=variant.locale,
            expected_snapshot_hash=binding.knowledge_brief_hash,
        )
    except KnowledgeBriefRefError as exc:
        raise KnowledgeBriefBindingError(exc.code) from exc
    return BoundKnowledgeBrief(
        binding=binding,
        brief_id=brief.id,
        snapshot_hash=brief.snapshot_hash,
    )


__all__ = [
    "BoundKnowledgeBrief",
    "KnowledgeBriefBindingError",
    "bind_knowledge_brief_to_run",
    "load_run_knowledge_brief_binding",
]
