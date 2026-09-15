from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.modules.knowledge.brief_models import KnowledgeBrief

KNOWLEDGE_BRIEF_REF_PREFIX = "knowledge_brief"
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class KnowledgeBriefRefError(ValueError):
    """Raised when a typed KnowledgeBrief reference cannot be trusted."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParsedKnowledgeBriefRef:
    brief_id: UUID
    snapshot_hash: str


def knowledge_brief_snapshot(brief: KnowledgeBrief) -> dict[str, object]:
    """Return the exact K5 snapshot allowed into Journal context/model input."""

    return {
        "id": str(brief.id),
        "method": brief.brief_method,
        "snapshot_hash": brief.snapshot_hash,
        "payload": copy.deepcopy(brief.brief_json),
    }


def format_knowledge_brief_ref(brief: KnowledgeBrief) -> str:
    if not _HASH_PATTERN.fullmatch(brief.snapshot_hash):
        raise KnowledgeBriefRefError("knowledge_brief_ref_hash_invalid")
    return f"{KNOWLEDGE_BRIEF_REF_PREFIX}:{brief.id}:{brief.snapshot_hash}"


def parse_knowledge_brief_ref(raw_ref: str) -> ParsedKnowledgeBriefRef:
    if not isinstance(raw_ref, str):
        raise KnowledgeBriefRefError("knowledge_brief_ref_invalid")
    parts = raw_ref.split(":")
    if len(parts) != 3 or parts[0] != KNOWLEDGE_BRIEF_REF_PREFIX:
        raise KnowledgeBriefRefError("knowledge_brief_ref_invalid")
    try:
        brief_id = UUID(parts[1])
    except ValueError as exc:
        raise KnowledgeBriefRefError("knowledge_brief_ref_invalid") from exc
    if parts[1] != str(brief_id):
        raise KnowledgeBriefRefError("knowledge_brief_ref_not_canonical")
    if not _HASH_PATTERN.fullmatch(parts[2]):
        raise KnowledgeBriefRefError("knowledge_brief_ref_hash_invalid")
    return ParsedKnowledgeBriefRef(brief_id=brief_id, snapshot_hash=parts[2])


async def load_bound_knowledge_brief(
    session: AsyncSession,
    *,
    brief_id: UUID,
    project_id: UUID,
    content_case_id: UUID,
    locale: str,
    expected_snapshot_hash: str | None = None,
) -> KnowledgeBrief:
    # Lazy imports keep the lightweight typed-ref boundary usable while the
    # knowledge admission/content-engine modules are still being initialized.
    from app.modules.knowledge.brief import KnowledgeBriefError, verify_knowledge_brief
    from app.modules.knowledge.brief_models import KnowledgeBrief

    brief = await session.get(KnowledgeBrief, brief_id)
    if brief is None:
        raise KnowledgeBriefRefError("knowledge_brief_ref_not_found")
    try:
        await verify_knowledge_brief(session, brief=brief)
    except KnowledgeBriefError as exc:
        raise KnowledgeBriefRefError(str(exc)) from exc
    if expected_snapshot_hash is not None and brief.snapshot_hash != expected_snapshot_hash:
        raise KnowledgeBriefRefError("knowledge_brief_ref_snapshot_mismatch")
    if brief.project_id != project_id:
        raise KnowledgeBriefRefError("knowledge_brief_ref_project_mismatch")
    if brief.content_case_id != content_case_id:
        raise KnowledgeBriefRefError("knowledge_brief_ref_case_mismatch")
    if brief.locale != locale:
        raise KnowledgeBriefRefError("knowledge_brief_ref_locale_mismatch")
    return brief


async def resolve_bound_knowledge_brief_refs(
    session: AsyncSession,
    *,
    refs: tuple[str, ...] | list[str],
    project_id: UUID,
    content_case_id: UUID,
    locale: str,
) -> KnowledgeBrief | None:
    typed_refs: list[str] = []
    for raw_ref in refs:
        if not isinstance(raw_ref, str):
            raise KnowledgeBriefRefError("knowledge_brief_ref_invalid")
        if raw_ref.startswith(KNOWLEDGE_BRIEF_REF_PREFIX):
            typed_refs.append(raw_ref)
    if len(typed_refs) > 1:
        raise KnowledgeBriefRefError("knowledge_brief_ref_multiple")
    if not typed_refs:
        return None
    parsed = parse_knowledge_brief_ref(typed_refs[0])
    return await load_bound_knowledge_brief(
        session,
        brief_id=parsed.brief_id,
        project_id=project_id,
        content_case_id=content_case_id,
        locale=locale,
        expected_snapshot_hash=parsed.snapshot_hash,
    )


__all__ = [
    "KNOWLEDGE_BRIEF_REF_PREFIX",
    "KnowledgeBriefRefError",
    "ParsedKnowledgeBriefRef",
    "format_knowledge_brief_ref",
    "knowledge_brief_snapshot",
    "load_bound_knowledge_brief",
    "parse_knowledge_brief_ref",
    "resolve_bound_knowledge_brief_refs",
]
