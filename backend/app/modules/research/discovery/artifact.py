from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.harness.models import Artifact, StepRun

if TYPE_CHECKING:
    from app.modules.research.discovery.service import DiscoveryWorkflowResult


def _json_default(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"unsupported_discovery_artifact_value:{type(value).__name__}")


def discovery_workflow_payload(result: DiscoveryWorkflowResult) -> dict[str, object]:
    """Return a bounded JSON-safe Discovery artifact payload."""

    raw = asdict(result)
    # Round-trip through JSON so nested Enum/UUID values are normalized before DB write.
    payload = json.loads(
        json.dumps(raw, ensure_ascii=False, sort_keys=True, default=_json_default)
    )
    if not isinstance(payload, dict):
        raise TypeError("discovery_artifact_payload_must_be_object")
    return payload


def _payload_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def persist_discovery_artifact(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
    result: DiscoveryWorkflowResult,
) -> Artifact:
    """Persist one immutable Discovery output and bind it to the exact step attempt."""

    step = await session.get(StepRun, step_run_id)
    if step is None:
        raise ValueError("discovery_step_run_not_found")
    if step.run_id != run_id:
        raise ValueError("discovery_step_run_must_belong_to_run")

    artifact_type = result.artifact_type
    current_version = await session.scalar(
        select(func.coalesce(func.max(Artifact.version), 0)).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == artifact_type,
        )
    )
    payload = discovery_workflow_payload(result)
    artifact = Artifact(
        run_id=run_id,
        step_run_id=step_run_id,
        artifact_type=artifact_type,
        locale=result.research.request.locale,
        version=int(current_version or 0) + 1,
        content_json=payload,
        content_hash=_payload_hash(payload),
    )
    session.add(artifact)
    await session.flush()

    artifact_ref = str(artifact.id)
    step.output_artifact_refs_json = list(
        dict.fromkeys((*step.output_artifact_refs_json, artifact_ref))
    )
    await session.flush()
    return artifact
