from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.harness.models import Artifact, StepRun
from app.modules.research.discovery.persistence import PersistedDiscoveryPlan
from app.modules.research.keyword_plan.contracts import (
    ContentDecision,
    ContentOpportunity,
    HypothesisStatus,
    Intent,
    JournalRole,
    NeedHypothesis,
    NeedType,
    OpportunityMapResult,
    OpportunityPriority,
    SuggestedContentType,
)

if TYPE_CHECKING:
    from app.modules.research.discovery.service import DiscoveryWorkflowResult

DISCOVERY_ARTIFACT_SCHEMA_VERSION = 1


def _json_default(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"unsupported_discovery_artifact_value:{type(value).__name__}")


def discovery_workflow_payload(result: DiscoveryWorkflowResult) -> dict[str, object]:
    """Return a bounded JSON-safe Discovery artifact payload."""

    raw = asdict(result)
    raw["schema_version"] = DISCOVERY_ARTIFACT_SCHEMA_VERSION
    # Round-trip through JSON so nested Enum/UUID values are normalized before storage.
    payload = json.loads(
        json.dumps(raw, ensure_ascii=False, sort_keys=True, default=_json_default)
    )
    if not isinstance(payload, dict):
        raise TypeError("discovery_artifact_payload_must_be_object")
    return payload


def discovery_workflow_json(result: DiscoveryWorkflowResult) -> str:
    return json.dumps(
        discovery_workflow_payload(result),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def write_discovery_workflow_artifact(
    result: DiscoveryWorkflowResult,
    path: Path,
) -> Path:
    """Write the pre-ContentCase real-gate artifact without inventing a ContentRun."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(discovery_workflow_json(result), encoding="utf-8")
    return path


def _required_dict(parent: dict[str, object], key: str) -> dict[str, object]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"discovery_artifact_{key}_required")
    return value


def _required_str(parent: dict[str, object], key: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"discovery_artifact_{key}_required")
    return value


def _optional_str(parent: dict[str, object], key: str) -> str | None:
    value = parent.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"discovery_artifact_{key}_invalid")
    return value


def _int_value(parent: dict[str, object], key: str, default: int = 1) -> int:
    value = parent.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"discovery_artifact_{key}_invalid")
    return value


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("discovery_artifact_string_list_required")
    return tuple(value)


def _load_need_hypothesis(payload: dict[str, object]) -> NeedHypothesis:
    return NeedHypothesis(
        id=_required_str(payload, "id"),
        statement=_required_str(payload, "statement"),
        audience_scope=_required_str(payload, "audience_scope"),
        situation=_required_str(payload, "situation"),
        need_type=NeedType(_required_str(payload, "need_type")),
        origin=_required_str(payload, "origin"),
        status=HypothesisStatus(_required_str(payload, "status")),
        support_signal_refs=_string_tuple(payload.get("support_signal_refs")),
        contradict_signal_refs=_string_tuple(payload.get("contradict_signal_refs")),
        alternative_explanations=_string_tuple(payload.get("alternative_explanations")),
        missing_evidence=_string_tuple(payload.get("missing_evidence")),
        version=_int_value(payload, "version"),
    )


def _load_content_opportunity(payload: dict[str, object]) -> ContentOpportunity:
    role_value = _optional_str(payload, "suggested_role")
    selected_by = _optional_str(payload, "selected_by")
    selected_at = _optional_str(payload, "selected_at")
    selection_reason = _optional_str(payload, "selection_reason")

    return ContentOpportunity(
        id=_required_str(payload, "id"),
        need_hypothesis_id=_required_str(payload, "need_hypothesis_id"),
        locale=_required_str(payload, "locale"),
        reader=_required_str(payload, "reader"),
        situation=_required_str(payload, "situation"),
        need=_required_str(payload, "need"),
        question=_required_str(payload, "question"),
        intent=Intent(_required_str(payload, "intent")),
        promise=_required_str(payload, "promise"),
        topic_key=_required_str(payload, "topic_key"),
        signal_refs=_string_tuple(payload.get("signal_refs")),
        motgu_material_refs=_string_tuple(payload.get("motgu_material_refs")),
        material_gaps=_string_tuple(payload.get("material_gaps")),
        existing_content_refs=_string_tuple(payload.get("existing_content_refs")),
        what_is_actually_new=_required_str(payload, "what_is_actually_new"),
        next_discovery_step=_required_str(payload, "next_discovery_step"),
        decision=ContentDecision(_required_str(payload, "decision")),
        priority=OpportunityPriority(_required_str(payload, "priority")),
        reasons=_string_tuple(payload.get("reasons")),
        suggested_content_type=SuggestedContentType(
            _required_str(payload, "suggested_content_type")
        ),
        suggested_role=JournalRole(role_value) if role_value is not None else None,
        version=_int_value(payload, "version"),
        selected_by=selected_by,
        selected_at=selected_at,
        selection_reason=selection_reason,
    )


def load_discovery_selection_snapshot(
    path: Path,
    *,
    opportunity_id: str,
) -> tuple[OpportunityMapResult, PersistedDiscoveryPlan]:
    """Load only the durable planning context needed for a later human selection."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("discovery_artifact_must_be_object")
    if raw.get("schema_version") != DISCOVERY_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported_discovery_artifact_schema_version")
    if raw.get("artifact_type") != "discovery_research_report":
        raise ValueError("invalid_discovery_artifact_type")
    if raw.get("evidence_eligible") is not False:
        raise ValueError("discovery_artifact_must_not_be_evidence_eligible")

    planning_payload = _required_dict(raw, "planning_refs")
    opportunity_ids_raw = _required_dict(planning_payload, "opportunity_ids")
    signal_ids_raw = _required_dict(planning_payload, "signal_ids")
    try:
        need_hypothesis_id = UUID(_required_str(planning_payload, "need_hypothesis_id"))
        signal_ids = {
            str(key): UUID(str(value)) for key, value in signal_ids_raw.items()
        }
        opportunity_ids = {
            str(key): UUID(str(value)) for key, value in opportunity_ids_raw.items()
        }
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_discovery_planning_refs") from exc

    if opportunity_id not in opportunity_ids:
        raise ValueError("selected_opportunity_missing_from_persisted_plan")

    map_payload = _required_dict(raw, "opportunity_map")
    hypothesis = _load_need_hypothesis(_required_dict(map_payload, "need_hypothesis"))
    if hypothesis.status is not HypothesisStatus.PROPOSED:
        raise ValueError("discovery_hypothesis_must_remain_proposed_before_selection")

    opportunities_raw = map_payload.get("opportunities")
    if not isinstance(opportunities_raw, list):
        raise ValueError("discovery_artifact_opportunities_required")
    selected_payload = next(
        (
            item
            for item in opportunities_raw
            if isinstance(item, dict) and item.get("id") == opportunity_id
        ),
        None,
    )
    if selected_payload is None:
        raise ValueError("selected_opportunity_missing_from_artifact")
    selected = _load_content_opportunity(selected_payload)
    if selected.need_hypothesis_id != hypothesis.id:
        raise ValueError("selected_opportunity_hypothesis_mismatch")

    result = OpportunityMapResult(
        project_id=_required_str(map_payload, "project_id"),
        locale=_required_str(map_payload, "locale"),
        seed=_required_str(map_payload, "seed"),
        version=_int_value(map_payload, "version"),
        need_hypothesis=hypothesis,
        opportunities=[selected],
    )
    refs = PersistedDiscoveryPlan(
        need_hypothesis_id=need_hypothesis_id,
        signal_ids=signal_ids,
        opportunity_ids=opportunity_ids,
    )
    return result, refs


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