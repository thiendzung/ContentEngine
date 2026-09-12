"""Durable human approval gate for one exact CE05 Journal Outline snapshot."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import OutlineApproval
from app.modules.content_engine.journal.outline import OutlineGenerationError, load_outline_input
from app.modules.harness.models import Artifact, ContentRun

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class OutlineApprovalError(ValueError):
    """Raised when an Outline approval is absent, stale, or conflicting."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class ApprovedOutline:
    artifact: Artifact
    approval: OutlineApproval


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and _HASH_PATTERN.fullmatch(value) is not None


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OutlineApprovalError(code)
    return value.strip()


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise OutlineApprovalError(code)
    return cast(dict[str, object], value)


def _uuid(value: object, code: str) -> UUID:
    if not isinstance(value, str):
        raise OutlineApprovalError(code)
    try:
        return UUID(value)
    except ValueError as exc:
        raise OutlineApprovalError(code) from exc


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OutlineApprovalError(code)
    return value


def _validate_snapshot(
    artifact: Artifact,
    *,
    expected_version: int,
    expected_hash: str,
) -> None:
    if artifact.artifact_type != "journal_outline":
        raise OutlineApprovalError("outline_approval_artifact_type_invalid")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version <= 0
    ):
        raise OutlineApprovalError("outline_approval_artifact_version_invalid")
    if not _valid_hash(expected_hash):
        raise OutlineApprovalError("outline_approval_artifact_hash_invalid")
    if artifact.version != expected_version or artifact.content_hash != expected_hash:
        raise OutlineApprovalError("outline_approval_snapshot_stale")
    if artifact.content_json is None or not _valid_hash(artifact.content_hash):
        raise OutlineApprovalError("outline_approval_snapshot_stale")
    if _canonical_hash(artifact.content_json) != artifact.content_hash:
        raise OutlineApprovalError("outline_approval_snapshot_stale")
    payload = _dict(artifact.content_json, "outline_approval_payload_invalid")
    if payload.get("artifact_type") != "journal_outline":
        raise OutlineApprovalError("outline_approval_payload_invalid")


async def _validate_upstream(session: AsyncSession, artifact: Artifact) -> None:
    payload = _dict(artifact.content_json, "outline_approval_payload_invalid")
    approved_angle = _dict(
        payload.get("approved_angle"), "outline_approval_angle_ref_invalid"
    )
    angle_artifact = _dict(
        approved_angle.get("artifact"), "outline_approval_angle_ref_invalid"
    )
    angle_approval = _dict(
        approved_angle.get("approval"), "outline_approval_angle_ref_invalid"
    )
    angle_artifact_id = _uuid(
        angle_artifact.get("id"), "outline_approval_angle_ref_invalid"
    )
    angle_version = _positive_int(
        angle_artifact.get("version"), "outline_approval_angle_ref_invalid"
    )
    angle_hash = angle_artifact.get("content_hash")
    candidate_hash = angle_approval.get("selected_candidate_hash")
    if not _valid_hash(angle_hash) or not _valid_hash(candidate_hash):
        raise OutlineApprovalError("outline_approval_angle_ref_invalid")
    selected_angle_id = _text(
        angle_approval.get("selected_angle_id"), "outline_approval_angle_ref_invalid"
    )
    angle_approval_id = _uuid(
        angle_approval.get("id"), "outline_approval_angle_ref_invalid"
    )
    try:
        upstream = await load_outline_input(
            session,
            angle_artifact_id=angle_artifact_id,
            expected_angle_artifact_version=angle_version,
            expected_angle_artifact_hash=cast(str, angle_hash),
            selected_angle_id=selected_angle_id,
            expected_candidate_hash=cast(str, candidate_hash),
            expected_approval_id=angle_approval_id,
        )
    except OutlineGenerationError as exc:
        raise OutlineApprovalError("outline_approval_upstream_invalid", str(exc)) from exc
    if upstream.approved_angle.artifact.run_id != artifact.run_id:
        raise OutlineApprovalError("outline_approval_run_mismatch")


def _matches(
    approval: OutlineApproval,
    *,
    artifact: Artifact,
    approved_by: str,
    approval_reason: str,
) -> bool:
    return (
        approval.run_id == artifact.run_id
        and approval.outline_artifact_id == artifact.id
        and approval.outline_artifact_version == artifact.version
        and approval.outline_artifact_hash == artifact.content_hash
        and approval.approved_by == approved_by
        and approval.approval_reason == approval_reason
    )


async def approve_outline_artifact(
    session: AsyncSession,
    *,
    outline_artifact_id: UUID,
    expected_artifact_version: int,
    expected_artifact_hash: str,
    approved_by: str,
    approval_reason: str,
) -> OutlineApproval:
    """Persist one exact human Outline decision without mutating the Outline."""

    approver = _text(approved_by, "outline_approver_required")
    reason = _text(approval_reason, "outline_approval_reason_required")
    artifact = await session.scalar(
        select(Artifact).where(Artifact.id == outline_artifact_id).with_for_update()
    )
    if artifact is None:
        raise OutlineApprovalError("outline_approval_artifact_not_found")
    _validate_snapshot(
        artifact,
        expected_version=expected_artifact_version,
        expected_hash=expected_artifact_hash,
    )
    await _validate_upstream(session, artifact)

    approvals = list(
        (
            await session.scalars(
                select(OutlineApproval).where(
                    OutlineApproval.outline_artifact_id == artifact.id
                )
            )
        ).all()
    )
    for approval in approvals:
        if _matches(
            approval,
            artifact=artifact,
            approved_by=approver,
            approval_reason=reason,
        ):
            return approval
        raise OutlineApprovalError("outline_approval_conflict")

    run = await session.get(ContentRun, artifact.run_id)
    if run is None:
        raise OutlineApprovalError("outline_approval_run_not_found")
    if run.status != "waiting_approval":
        raise OutlineApprovalError("outline_approval_run_state_invalid", run.status)

    approval = OutlineApproval(
        run_id=artifact.run_id,
        outline_artifact_id=artifact.id,
        outline_artifact_version=artifact.version,
        outline_artifact_hash=artifact.content_hash,
        approved_by=approver,
        approval_reason=reason,
        approved_at=datetime.now(UTC),
    )
    session.add(approval)
    await session.flush()
    return approval


async def handoff_approved_outline(
    session: AsyncSession,
    *,
    outline_artifact_id: UUID,
    expected_artifact_version: int,
    expected_artifact_hash: str,
    expected_approval_id: UUID,
) -> ApprovedOutline:
    """Expose an Outline downstream only after exact persisted human approval."""

    artifact = await session.get(Artifact, outline_artifact_id)
    if artifact is None:
        raise OutlineApprovalError("outline_approval_artifact_not_found")
    _validate_snapshot(
        artifact,
        expected_version=expected_artifact_version,
        expected_hash=expected_artifact_hash,
    )
    await _validate_upstream(session, artifact)
    approvals = list(
        (
            await session.scalars(
                select(OutlineApproval).where(
                    OutlineApproval.outline_artifact_id == artifact.id
                )
            )
        ).all()
    )
    if not approvals:
        raise OutlineApprovalError("outline_approval_required")
    if len(approvals) != 1:
        raise OutlineApprovalError("outline_approval_conflict")
    approval = approvals[0]
    if approval.id != expected_approval_id:
        raise OutlineApprovalError("outline_approval_id_mismatch")
    if not _matches(
        approval,
        artifact=artifact,
        approved_by=approval.approved_by,
        approval_reason=approval.approval_reason,
    ):
        raise OutlineApprovalError("outline_approval_conflict")
    return ApprovedOutline(artifact=artifact, approval=approval)


__all__ = [
    "ApprovedOutline",
    "OutlineApproval",
    "OutlineApprovalError",
    "approve_outline_artifact",
    "handoff_approved_outline",
]
