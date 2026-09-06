import hashlib
import json
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import KnowledgeChunk, SourceDocument


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_document_id(*, source_id: UUID, document_content_hash: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"contentengine:document:{source_id}:{document_content_hash}")


def stable_chunk_id(*, source_document_id: UUID, text: str, ordinal: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"contentengine:chunk:{source_document_id}:{ordinal}:{text}")


def stable_chunk_fingerprint(*, text: str, ordinal: int) -> str:
    return content_hash(f"{ordinal}\x1f{text}")


def evidence_set_hash(evidence_ids: list[str]) -> str:
    payload = json.dumps(evidence_ids, separators=(",", ":"), sort_keys=False)
    return content_hash(payload)


async def get_existing_document(
    session: AsyncSession, *, source_id: UUID, document_content_hash: str
) -> SourceDocument | None:
    result = await session.execute(
        select(SourceDocument).where(
            SourceDocument.source_id == source_id,
            SourceDocument.content_hash == document_content_hash,
        )
    )
    return result.scalars().one_or_none()


async def get_existing_chunk(
    session: AsyncSession, *, source_document_id: UUID, fingerprint: str
) -> KnowledgeChunk | None:
    result = await session.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.source_document_id == source_document_id,
            KnowledgeChunk.fingerprint == fingerprint,
        )
    )
    return result.scalars().one_or_none()
