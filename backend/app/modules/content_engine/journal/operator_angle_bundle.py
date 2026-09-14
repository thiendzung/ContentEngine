"""Bind an existing validated Journal bundle to one exact context manifest."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.harness.models import Artifact, ContentRun, ContextManifest, StepRun


class OperatorAngleBundleError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def bind_bundle_context_manifest(
    session: AsyncSession,
    *,
    base_bundle_artifact_id: UUID,
    context_manifest_id: UUID,
    research_execution: dict[str, object] | None = None,
) -> Artifact:
    """Create/reuse an immutable bundle snapshot carrying exact context and research audit.

    ``load_journal_input_bundle`` already validates the optional ``context_manifest``
    field. The extra ``research_execution`` object is audit metadata: the inherited
    ``REUSE_EXISTING`` decision still describes the handoff action, while this snapshot
    records whether the evidence was produced immediately before that handoff.
    """

    base = await session.get(Artifact, base_bundle_artifact_id)
    manifest = await session.get(ContextManifest, context_manifest_id)
    if base is None or base.artifact_type != "journal_input_bundle":
        raise OperatorAngleBundleError("operator_angle_bundle_base_invalid")
    if base.content_json is None or _canonical_hash(base.content_json) != base.content_hash:
        raise OperatorAngleBundleError("operator_angle_bundle_base_stale")
    if manifest is None or manifest.run_id != base.run_id:
        raise OperatorAngleBundleError("operator_angle_bundle_manifest_mismatch")
    run = await session.get(ContentRun, base.run_id)
    if run is None or manifest.settings_snapshot_id != run.settings_snapshot_id:
        raise OperatorAngleBundleError("operator_angle_bundle_settings_mismatch")
    if manifest.step_run_id is None:
        raise OperatorAngleBundleError("operator_angle_bundle_manifest_step_required")
    step = await session.get(StepRun, manifest.step_run_id)
    if step is None or step.run_id != run.id:
        raise OperatorAngleBundleError("operator_angle_bundle_manifest_step_mismatch")

    payload = json.loads(json.dumps(base.content_json, ensure_ascii=False))
    if not isinstance(payload, dict):
        raise OperatorAngleBundleError("operator_angle_bundle_payload_invalid")
    evidence_set = payload.get("evidence_set")
    originality_pack = payload.get("originality_pack")
    if not isinstance(evidence_set, dict) or not isinstance(originality_pack, dict):
        raise OperatorAngleBundleError("operator_angle_bundle_payload_invalid")
    if str(manifest.evidence_set_id) != evidence_set.get("id"):
        raise OperatorAngleBundleError("operator_angle_bundle_evidence_mismatch")
    if str(manifest.originality_pack_id) != originality_pack.get("id"):
        raise OperatorAngleBundleError("operator_angle_bundle_originality_mismatch")

    payload["context_manifest"] = {
        "id": str(manifest.id),
        "content_hash": manifest.content_hash,
    }
    if research_execution is not None:
        cloned = json.loads(json.dumps(research_execution, ensure_ascii=False))
        if not isinstance(cloned, dict):
            raise OperatorAngleBundleError("operator_angle_bundle_research_audit_invalid")
        payload["research_execution"] = cloned

    content_hash = _canonical_hash(payload)
    existing = await session.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == run.id,
            Artifact.artifact_type == "journal_input_bundle",
            Artifact.content_hash == content_hash,
        )
        .limit(1)
    )
    if existing is not None:
        return existing

    latest = await session.scalar(
        select(func.coalesce(func.max(Artifact.version), 0)).where(
            Artifact.run_id == run.id,
            Artifact.artifact_type == "journal_input_bundle",
        )
    )
    artifact = Artifact(
        run_id=run.id,
        step_run_id=step.id,
        artifact_type="journal_input_bundle",
        locale=base.locale,
        version=int(latest or 0) + 1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    if str(artifact.id) not in step.output_artifact_refs_json:
        step.output_artifact_refs_json = [
            *step.output_artifact_refs_json,
            str(artifact.id),
        ]
        await session.flush()
    return artifact


__all__ = ["OperatorAngleBundleError", "bind_bundle_context_manifest"]
