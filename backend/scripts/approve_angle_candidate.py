"""Persist and verify one exact Founder-approved Journal Angle candidate."""

# ruff: noqa: E402

import argparse
import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from app.modules.content_engine.journal.angle import (
    approve_angle_candidate,
    handoff_approved_angle,
)
from app.modules.harness.models import Artifact

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _positive_int_arg(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _non_empty_arg(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return value.strip()


def _hash_arg(value: str) -> str:
    normalized = value.strip().lower()
    if _HASH_PATTERN.fullmatch(normalized) is None:
        raise argparse.ArgumentTypeError("must be a 64-character lowercase SHA-256 hex value")
    return normalized


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist and verify one exact human-approved Journal Angle candidate."
    )
    parser.add_argument("--angle-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--expected-artifact-version", required=True, type=_positive_int_arg)
    parser.add_argument("--expected-artifact-hash", required=True, type=_hash_arg)
    parser.add_argument("--selected-angle-id", required=True, type=_non_empty_arg)
    parser.add_argument("--approved-by", required=True, type=_non_empty_arg)
    parser.add_argument("--approval-reason", required=True, type=_non_empty_arg)
    return parser


def _candidate_hash_from_artifact(artifact: Artifact, selected_angle_id: str) -> str:
    payload = artifact.content_json
    if not isinstance(payload, dict):
        raise ValueError("angle_artifact_payload_invalid")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("angle_artifact_candidates_invalid")
    selected = next(
        (
            candidate
            for candidate in candidates
            if isinstance(candidate, dict) and candidate.get("angle_id") == selected_angle_id
        ),
        None,
    )
    if selected is None:
        raise ValueError("angle_selected_candidate_not_found")
    encoded = json.dumps(
        selected,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def _run(args: argparse.Namespace) -> None:
    angle_artifact_id = cast(UUID, args.angle_artifact_id)
    artifact_version = cast(int, args.expected_artifact_version)
    artifact_hash = cast(str, args.expected_artifact_hash)
    selected_angle_id = cast(str, args.selected_angle_id)

    async with SessionLocal() as session:
        artifact = await session.get(Artifact, angle_artifact_id)
        if artifact is None:
            raise ValueError("angle_artifact_not_found")
        candidate_hash = _candidate_hash_from_artifact(artifact, selected_angle_id)
        approval = await approve_angle_candidate(
            session,
            angle_artifact_id=angle_artifact_id,
            expected_artifact_version=artifact_version,
            expected_artifact_hash=artifact_hash,
            selected_angle_id=selected_angle_id,
            expected_candidate_hash=candidate_hash,
            approved_by=cast(str, args.approved_by),
            approval_reason=cast(str, args.approval_reason),
        )
        await session.commit()
        approval_id = approval.id

    async with SessionLocal() as session:
        handoff = await handoff_approved_angle(
            session,
            angle_artifact_id=angle_artifact_id,
            expected_artifact_version=artifact_version,
            expected_artifact_hash=artifact_hash,
            selected_angle_id=selected_angle_id,
            expected_candidate_hash=candidate_hash,
        )
        if handoff.approval.id != approval_id:
            raise ValueError("angle_approval_handoff_mismatch")

    print(
        json.dumps(
            {
                "approval_id": str(handoff.approval.id),
                "run_id": str(handoff.approval.run_id),
                "angle_artifact_id": str(handoff.artifact.id),
                "angle_artifact_version": handoff.artifact.version,
                "angle_artifact_hash": handoff.artifact.content_hash,
                "selected_angle_id": handoff.candidate.angle_id,
                "selected_candidate_hash": candidate_hash,
                "approved_by": handoff.approval.approved_by,
                "approval_reason": handoff.approval.approval_reason,
                "handoff_verified": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
