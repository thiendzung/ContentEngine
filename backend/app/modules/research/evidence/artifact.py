from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.harness.models import Artifact, StepRun
from app.modules.research.evidence.contracts import EvidenceResearchResult

EVIDENCE_ARTIFACT_SCHEMA_VERSION = 1


def evidence_workflow_payload(result: EvidenceResearchResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": EVIDENCE_ARTIFACT_SCHEMA_VERSION,
        "artifact_type": result.artifact_type,
        "evidence_eligible": result.evidence_eligible,
        "research": {
            "query": result.research.request.query,
            "locale": result.research.request.locale,
            "country": result.research.request.country,
            "stop_reason": result.research.stop_reason,
            "sufficient": result.research.sufficient,
            "external_provider_calls": result.research.external_provider_calls,
            "decisions": [
                {
                    "provider": decision.provider,
                    "status": decision.status.value,
                    "reason": decision.reason,
                    "failure_class": decision.failure_class,
                }
                for decision in result.research.decisions
            ],
        },
        "content_case_id": str(result.content_case_id),
        "source_document_ids": [str(value) for value in result.source_document_ids],
        "claim_ids": [str(value) for value in result.claim_ids],
        "evidence_ids": [str(value) for value in result.evidence_ids],
        "relation_counts": dict(result.relation_counts),
        "evidence_set": {
            "id": str(result.evidence_set_id) if result.evidence_set_id else None,
            "version": result.evidence_set_version,
            "content_hash": result.evidence_set_content_hash,
            "status": result.evidence_set_status,
        },
        "originality_pack": {
            "id": str(result.originality_pack_id) if result.originality_pack_id else None,
            "item_count": result.originality_item_count,
        },
        "research_gaps": list(result.research_gaps),
    }
    return payload


def evidence_workflow_json(result: EvidenceResearchResult) -> str:
    return json.dumps(
        evidence_workflow_payload(result),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def write_evidence_workflow_artifact(
    result: EvidenceResearchResult,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(evidence_workflow_json(result), encoding="utf-8")
    return path


def _payload_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def persist_evidence_artifact(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
    result: EvidenceResearchResult,
) -> Artifact:
    step = await session.get(StepRun, step_run_id)
    if step is None:
        raise ValueError("evidence_step_run_not_found")
    if step.run_id != run_id:
        raise ValueError("evidence_step_run_must_belong_to_run")

    current_version = await session.scalar(
        select(func.coalesce(func.max(Artifact.version), 0)).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == result.artifact_type,
        )
    )
    payload = evidence_workflow_payload(result)
    artifact = Artifact(
        run_id=run_id,
        step_run_id=step_run_id,
        artifact_type=result.artifact_type,
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
