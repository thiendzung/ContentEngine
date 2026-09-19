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
RESEARCH_FAILURE_DIAGNOSTIC_SCHEMA_VERSION = 1
RESEARCH_FAILURE_DIAGNOSTIC_ARTIFACT_TYPE = "research_failure_diagnostic"


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


def _bounded_text(value: str | None, *, limit: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized[:limit]


def _diagnostic_source_payload(source: object) -> dict[str, object]:
    provider = getattr(source, "provider", "")
    query = getattr(source, "query", "")
    url = getattr(source, "url", "")
    title = getattr(source, "title", "")
    source_type = getattr(source, "source_type", "")
    commercial_bias = getattr(source, "commercial_bias", "")
    found_via = getattr(source, "found_via", "")
    relation = getattr(source, "relation", "")
    intended_use = getattr(source, "intended_use", "")
    why_selected = getattr(source, "why_selected", "")
    parent_url = getattr(source, "parent_url", None)
    return {
        "provider": _bounded_text(str(provider), limit=100) or "",
        "query": _bounded_text(str(query), limit=1000) or "",
        "url": _bounded_text(str(url), limit=2048) or "",
        "title": _bounded_text(str(title), limit=500) or "",
        "source_type": _bounded_text(str(source_type), limit=100) or "",
        "commercial_bias": getattr(commercial_bias, "value", str(commercial_bias)),
        "found_via": _bounded_text(str(found_via), limit=100) or "",
        "relation": getattr(relation, "value", str(relation)),
        "intended_use": getattr(intended_use, "value", str(intended_use)),
        "why_selected": _bounded_text(str(why_selected), limit=500) or "",
        "parent_url": _bounded_text(str(parent_url), limit=2048) if parent_url else None,
    }


def research_failure_diagnostic_payload(
    result: EvidenceResearchResult,
) -> dict[str, object]:
    research = result.research
    required_use = research.request.required_intended_use
    return {
        "schema_version": RESEARCH_FAILURE_DIAGNOSTIC_SCHEMA_VERSION,
        "artifact_type": RESEARCH_FAILURE_DIAGNOSTIC_ARTIFACT_TYPE,
        "evidence_eligible": result.evidence_eligible,
        "research": {
            "query": _bounded_text(research.request.query, limit=1000) or "",
            "locale": _bounded_text(research.request.locale, limit=32) or "",
            "country": _bounded_text(research.request.country, limit=32) or "",
            "required_intended_use": (
                required_use.value if required_use is not None else None
            ),
            "stop_reason": _bounded_text(research.stop_reason, limit=200) or "",
            "sufficient": research.sufficient,
            "external_provider_calls": research.external_provider_calls,
            "pages_read": len(research.documents),
            "decisions": [
                {
                    "provider": _bounded_text(decision.provider, limit=100) or "",
                    "status": decision.status.value,
                    "reason": _bounded_text(decision.reason, limit=500) or "",
                    "failure_class": _bounded_text(
                        decision.failure_class,
                        limit=100,
                    ),
                }
                for decision in research.decisions[:50]
            ],
            "source_candidates": [
                _diagnostic_source_payload(source)
                for source in research.source_candidates[:50]
            ],
            "selected_sources": [
                _diagnostic_source_payload(source)
                for source in research.selected_sources[:50]
            ],
            "read_documents": [
                {
                    "provider": _bounded_text(document.provider, limit=100) or "",
                    "requested_url": _bounded_text(
                        document.requested_url or document.url,
                        limit=2048,
                    ),
                    "final_url": _bounded_text(
                        document.final_url or document.url,
                        limit=2048,
                    ),
                    "title": _bounded_text(document.title, limit=500),
                }
                for document in research.documents[:50]
            ],
        },
        "relation_counts": dict(result.relation_counts),
        "research_gaps": [
            _bounded_text(gap, limit=1000) or "" for gap in result.research_gaps[:50]
        ],
    }


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


async def persist_research_failure_diagnostic(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
    payload: dict[str, object],
) -> Artifact:
    step = await session.get(StepRun, step_run_id)
    if step is None:
        raise ValueError("research_failure_step_run_not_found")
    if step.run_id != run_id:
        raise ValueError("research_failure_step_run_must_belong_to_run")
    if payload.get("artifact_type") != RESEARCH_FAILURE_DIAGNOSTIC_ARTIFACT_TYPE:
        raise ValueError("research_failure_diagnostic_type_invalid")

    research = payload.get("research")
    locale = research.get("locale") if isinstance(research, dict) else None
    current_version = await session.scalar(
        select(func.coalesce(func.max(Artifact.version), 0)).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == RESEARCH_FAILURE_DIAGNOSTIC_ARTIFACT_TYPE,
        )
    )
    artifact = Artifact(
        run_id=run_id,
        step_run_id=step_run_id,
        artifact_type=RESEARCH_FAILURE_DIAGNOSTIC_ARTIFACT_TYPE,
        locale=locale if isinstance(locale, str) else None,
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
