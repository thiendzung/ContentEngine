"""Deterministic, one-way Obsidian projection for approved knowledge."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.admission import (
    KnowledgeCandidateAdmissionError,
    verify_candidate_snapshot_lineage,
)
from app.modules.knowledge.models import KnowledgeCandidate


class KnowledgeMirrorError(ValueError):
    """Raised when an approved candidate cannot be mirrored safely."""


@dataclass(frozen=True)
class KnowledgeMirrorResult:
    candidate_id: UUID
    path: Path
    content: str
    dry_run: bool


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _yaml_list(values: list[str]) -> list[str]:
    return [f"  - {_yaml_string(value)}" for value in values]


def _string_list_value(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise KnowledgeMirrorError(f"candidate_{field}_invalid")
    return cast(list[str], value)


def _required_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeMirrorError(f"candidate_{field}_required")
    return value


def render_knowledge_markdown(
    *,
    candidate: KnowledgeCandidate,
    candidate_snapshot: dict[str, Any],
    candidate_content_hash: str,
) -> str:
    """Render only stable approved-candidate fields and human-readable references."""

    reviewer = _required_string(candidate.reviewer, field="reviewer")
    review_reason = _required_string(candidate.review_reason, field="review_reason")
    statement = _required_string(candidate.statement, field="statement")
    summary = _required_string(candidate.summary, field="summary")
    evidence_set = candidate_snapshot["evidence_set"]
    evidence_refs = candidate_snapshot["evidence_refs"]
    if not isinstance(evidence_set, dict) or not isinstance(evidence_refs, list):
        raise KnowledgeMirrorError("candidate_snapshot_invalid")
    evidence_set = cast(dict[str, object], evidence_set)
    evidence_refs = cast(list[object], evidence_refs)

    evidence_set_id = _required_string(evidence_set.get("id"), field="evidence_set_id")
    evidence_set_version = evidence_set.get("version")
    evidence_set_hash = _required_string(
        evidence_set.get("content_hash"), field="evidence_set_content_hash"
    )
    claim_id = _required_string(candidate_snapshot.get("claim_id"), field="claim_id")
    source_refs = _string_list_value(candidate_snapshot.get("source_refs"), field="source_refs")
    evidence_ids = _string_list_value(
        candidate_snapshot.get("evidence_ids"), field="evidence_ids"
    )
    source_document_ids = _string_list_value(
        candidate_snapshot.get("source_document_ids"), field="source_document_ids"
    )
    source_ids = _string_list_value(candidate_snapshot.get("source_ids"), field="source_ids")
    if isinstance(evidence_set_version, bool) or not isinstance(evidence_set_version, int):
        raise KnowledgeMirrorError("candidate_evidence_set_version_invalid")

    lines = [
        "---",
        f"id: {_yaml_string(str(candidate.id))}",
        f"project_id: {_yaml_string(str(candidate.project_id))}",
        "status: APPROVED",
        "type: knowledge",
        f"locale: {('null' if candidate.locale is None else _yaml_string(candidate.locale))}",
        f"candidate_content_hash: {_yaml_string(candidate_content_hash)}",
        f"reviewer: {_yaml_string(reviewer)}",
        "source_refs:",
        *_yaml_list(source_refs),
        f"evidence_set_id: {_yaml_string(evidence_set_id)}",
        f"evidence_set_version: {evidence_set_version}",
        f"evidence_set_content_hash: {_yaml_string(evidence_set_hash)}",
        f"claim_id: {_yaml_string(claim_id)}",
        "evidence_ids:",
        *_yaml_list(evidence_ids),
        "source_document_ids:",
        *_yaml_list(source_document_ids),
        "source_ids:",
        *_yaml_list(source_ids),
        "---",
        "",
        "# Knowledge",
        "",
        statement,
        "",
        "## Summary",
        "",
        summary,
        "",
        "## Review",
        "",
        review_reason,
        "",
        "## Provenance",
        "",
        "method: locked_evidence_set_extraction",
        f"evidence set: {evidence_set_id} / version {evidence_set_version}",
        f"claim: {claim_id}",
        "evidence references:",
    ]
    for evidence_ref in evidence_refs:
        if not isinstance(evidence_ref, dict):
            raise KnowledgeMirrorError("candidate_evidence_ref_invalid")
        evidence_id = _required_string(evidence_ref.get("evidence_id"), field="evidence_id")
        relation = _required_string(evidence_ref.get("relation"), field="evidence_relation")
        locator = _required_string(evidence_ref.get("locator"), field="evidence_locator")
        lines.append(f"- {evidence_id} — {relation} — {locator}")
    for source_document_id in source_document_ids:
        lines.append(f"- source document: {source_document_id}")
    for source_id in source_ids:
        lines.append(f"- source: {source_id}")
    return "\n".join(lines) + "\n"


def _vault_output_path(*, vault_path: Path, candidate_id: UUID, create: bool) -> Path:
    root = vault_path.expanduser().resolve(strict=False)
    if root.is_symlink() or not root.exists() or not root.is_dir():
        raise KnowledgeMirrorError("vault_path_must_be_existing_directory")
    knowledge_dir = root / "10_Knowledge"
    if knowledge_dir.is_symlink() or (knowledge_dir.exists() and not knowledge_dir.is_dir()):
        raise KnowledgeMirrorError("knowledge_directory_invalid")
    if create and not knowledge_dir.exists():
        knowledge_dir.mkdir()
    output_path = knowledge_dir / f"{candidate_id}.md"
    if output_path.parent != knowledge_dir or output_path.name != f"{candidate_id}.md":
        raise KnowledgeMirrorError("knowledge_path_traversal_rejected")
    if output_path.exists() and output_path.is_dir():
        raise KnowledgeMirrorError("knowledge_output_path_is_directory")
    return output_path


def _atomic_write(path: Path, content: str) -> None:
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.stem}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


async def export_approved_knowledge(
    session: AsyncSession,
    *,
    candidate_id: UUID,
    vault_path: Path,
    dry_run: bool = False,
) -> KnowledgeMirrorResult:
    """Render one approved candidate without mutating database state."""

    candidate = await session.get(KnowledgeCandidate, candidate_id)
    if candidate is None:
        raise KnowledgeMirrorError("candidate_not_found")
    if candidate.status != "APPROVED":
        raise KnowledgeMirrorError("candidate_status_not_exportable")
    try:
        snapshot, candidate_content_hash = await verify_candidate_snapshot_lineage(
            session,
            candidate=candidate,
        )
    except KnowledgeCandidateAdmissionError as exc:
        raise KnowledgeMirrorError(str(exc)) from exc
    output_path = _vault_output_path(
        vault_path=vault_path,
        candidate_id=candidate.id,
        create=not dry_run,
    )
    content = render_knowledge_markdown(
        candidate=candidate,
        candidate_snapshot=snapshot,
        candidate_content_hash=candidate_content_hash,
    )
    if not dry_run:
        _atomic_write(output_path, content)
    return KnowledgeMirrorResult(
        candidate_id=candidate.id,
        path=output_path,
        content=content,
        dry_run=dry_run,
    )
