"""CE05 PR-B.1 handoff gates for the existing CE04 research workflows."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import ContentCase, ContentOpportunity
from app.modules.harness.models import Artifact, ContentRun, StepRun
from app.modules.knowledge.models import EvidenceSet, EvidenceSetApproval, OriginalityPack
from app.modules.knowledge.originality_pack import originality_pack_snapshot_hash
from app.modules.knowledge.persistence import evidence_set_hash
from app.modules.research.discovery.service import (
    DiscoveryWorkflowRequest,
    DiscoveryWorkflowResult,
    OpportunityHandoff,
)
from app.modules.research.evidence.contracts import (
    EvidenceResearchRequest,
    EvidenceResearchResult,
    count_usable_originality_items,
)

_CONTENT_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_JOURNAL_INPUT_BUNDLE_SCHEMA_VERSION = 1


class ResearchDecision(StrEnum):
    REUSE_EXISTING = "REUSE_EXISTING"
    RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
    BLOCKED = "BLOCKED"


class JournalResearchHandoffError(ValueError):
    """Raised when a CE05 research input cannot cross its handoff gate."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class DiscoveryWorkflowPort(Protocol):
    async def run(
        self,
        session: AsyncSession,
        *,
        request: DiscoveryWorkflowRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
        persist_plan: bool = False,
    ) -> DiscoveryWorkflowResult: ...

    async def select_and_persist(
        self,
        session: AsyncSession,
        result: DiscoveryWorkflowResult,
        *,
        opportunity_id: str,
        selected_by: str,
        reason: str,
    ) -> DiscoveryWorkflowResult: ...

    def handoff(self, result: DiscoveryWorkflowResult) -> OpportunityHandoff: ...


class EvidenceWorkflowPort(Protocol):
    async def run(
        self,
        session: AsyncSession,
        *,
        request: EvidenceResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> EvidenceResearchResult: ...


@dataclass(frozen=True, slots=True)
class DiscoveryResearchHandoff:
    """The result of the conditional Discovery Research boundary."""

    research_gap_required: bool
    result: DiscoveryWorkflowResult | None
    research_gaps: tuple[str, ...] = ()
    artifact_ref: str | None = None


@dataclass(frozen=True, slots=True)
class OpportunitySelectionHandoff:
    """Exact human selection persisted by the CE04 Opportunity Map seam."""

    opportunity: OpportunityHandoff
    selected_by: str
    selection_reason: str
    selected_at: str

    @property
    def opportunity_id(self) -> str:
        return self.opportunity.opportunity_id

    @property
    def need_hypothesis_id(self) -> str:
        return self.opportunity.need_hypothesis_id


@dataclass(frozen=True, slots=True)
class EvidenceSetHandoff:
    """Exact locked EvidenceSet snapshot allowed into Journal."""

    evidence_set_id: UUID
    project_id: UUID
    content_case_id: UUID
    version: int
    content_hash: str
    evidence_ids: tuple[UUID, ...]
    approval_id: UUID | None
    approved_by: str | None


@dataclass(frozen=True, slots=True)
class OriginalityPackHandoff:
    """Exact OriginalityPack snapshot that passed the MOTGU-material gate."""

    originality_pack_id: UUID
    content_case_id: UUID
    item_refs: tuple[object, ...]
    snapshot_hash: str
    status: str


@dataclass(frozen=True, slots=True)
class EvidenceResearchHandoff:
    """CE04 Evidence Research result after CE05 EvidenceSet/Originality gates."""

    result: EvidenceResearchResult
    evidence_set: EvidenceSetHandoff
    originality_pack: OriginalityPackHandoff


def _raise_handoff_error(exc: ValueError) -> JournalResearchHandoffError:
    return JournalResearchHandoffError(str(exc))


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _valid_content_hash(value: object) -> bool:
    return isinstance(value, str) and _CONTENT_HASH_PATTERN.fullmatch(value) is not None


def select_research_decision(
    *,
    research_gap_required: bool,
    opportunity_selected: bool,
    evidence_set_ready: bool,
    originality_pack_ready: bool,
) -> ResearchDecision:
    """Resolve the bounded CE05 decision without inferring a new opportunity."""

    if not opportunity_selected or not evidence_set_ready or not originality_pack_ready:
        return ResearchDecision.BLOCKED
    if research_gap_required:
        return ResearchDecision.RESEARCH_REQUIRED
    return ResearchDecision.REUSE_EXISTING


def _opportunity_payload(opportunity: ContentOpportunity) -> dict[str, object]:
    return {
        "id": str(opportunity.id),
        "project_id": str(opportunity.project_id),
        "need_hypothesis_id": str(opportunity.need_hypothesis_id),
        "locale": opportunity.locale,
        "reader": opportunity.reader,
        "situation": opportunity.situation,
        "need": opportunity.need,
        "question": opportunity.question,
        "intent": opportunity.intent,
        "promise": opportunity.promise,
        "motgu_material_refs": opportunity.motgu_material_refs_json,
        "material_gaps": opportunity.material_gaps_json,
        "existing_content_refs": opportunity.existing_content_refs_json,
        "what_is_actually_new": opportunity.what_is_actually_new,
        "next_discovery_step": opportunity.next_discovery_step,
        "decision": opportunity.decision,
        "priority": opportunity.priority,
        "reasons": opportunity.reasons_json,
        "suggested_content_type": opportunity.suggested_content_type,
        "suggested_role": opportunity.suggested_role,
        "version": opportunity.version,
        "selected_by": opportunity.selected_by,
        "selected_at": (
            opportunity.selected_at.isoformat()
            if opportunity.selected_at is not None
            else None
        ),
        "selection_reason": opportunity.selection_reason,
    }


class JournalResearchHandoff:
    """Keep CE05 orchestration thin and delegate research behavior to CE04."""

    def __init__(
        self,
        *,
        discovery_workflow: DiscoveryWorkflowPort | None = None,
        evidence_workflow: EvidenceWorkflowPort | None = None,
    ) -> None:
        self._discovery_workflow = discovery_workflow
        self._evidence_workflow = evidence_workflow

    async def run_discovery_research(
        self,
        session: AsyncSession,
        *,
        research_gap_required: bool,
        request: DiscoveryWorkflowRequest | None = None,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> DiscoveryResearchHandoff:
        """Run CE04 Discovery only when the caller has an explicit research gap."""

        if not research_gap_required:
            return DiscoveryResearchHandoff(
                research_gap_required=False,
                result=None,
            )
        if request is None:
            raise JournalResearchHandoffError("discovery_request_required_for_research_gap")
        if self._discovery_workflow is None:
            raise JournalResearchHandoffError("discovery_workflow_required")

        try:
            result = await self._discovery_workflow.run(
                session,
                request=request,
                run_id=run_id,
                step_run_id=step_run_id,
                persist_plan=True,
            )
        except ValueError as exc:
            raise _raise_handoff_error(exc) from exc
        return DiscoveryResearchHandoff(
            research_gap_required=True,
            result=result,
            research_gaps=tuple(result.research_gaps),
            artifact_ref=result.artifact_ref,
        )

    async def select_opportunity(
        self,
        session: AsyncSession,
        *,
        result: DiscoveryWorkflowResult,
        opportunity_id: str,
        selected_by: str,
        reason: str,
    ) -> OpportunitySelectionHandoff:
        """Persist one explicit human selection; never infer or select an opportunity."""

        if not isinstance(opportunity_id, str) or not opportunity_id.strip():
            raise JournalResearchHandoffError("opportunity_selection_id_required")
        if self._discovery_workflow is None:
            raise JournalResearchHandoffError("discovery_workflow_required")
        if result.planning_refs is None:
            raise JournalResearchHandoffError("persisted_discovery_plan_required")

        try:
            await self._discovery_workflow.select_and_persist(
                session,
                result,
                opportunity_id=opportunity_id,
                selected_by=selected_by,
                reason=reason,
            )
            opportunity = self._discovery_workflow.handoff(result)
        except ValueError as exc:
            raise _raise_handoff_error(exc) from exc

        selection = result.opportunity_map.human_selection
        if selection is None:
            raise JournalResearchHandoffError("human_selection_required_before_journal_handoff")
        if opportunity.opportunity_id != opportunity_id.strip():
            raise JournalResearchHandoffError("opportunity_selection_snapshot_mismatch")
        if opportunity.persisted_content_opportunity_id is None:
            raise JournalResearchHandoffError("persisted_opportunity_selection_required")
        return OpportunitySelectionHandoff(
            opportunity=opportunity,
            selected_by=selection.selected_by,
            selection_reason=selection.reason,
            selected_at=selection.selected_at,
        )

    async def run_evidence_research(
        self,
        session: AsyncSession,
        *,
        request: EvidenceResearchRequest,
        run_id: UUID | None = None,
        step_run_id: UUID | None = None,
    ) -> EvidenceResearchHandoff:
        """Reuse CE04 Evidence Research, then require both downstream snapshots."""

        if self._evidence_workflow is None:
            raise JournalResearchHandoffError("evidence_workflow_required")
        try:
            result = await self._evidence_workflow.run(
                session,
                request=request,
                run_id=run_id,
                step_run_id=step_run_id,
            )
        except ValueError as exc:
            raise _raise_handoff_error(exc) from exc

        if (
            result.evidence_set_id is None
            or result.evidence_set_version is None
            or result.evidence_set_content_hash is None
        ):
            raise JournalResearchHandoffError("evidence_set_required_for_journal_handoff")
        evidence_set = await self.handoff_evidence_set(
            session,
            project_id=request.research.project_id,
            content_case_id=result.content_case_id,
            evidence_set_id=result.evidence_set_id,
            expected_version=result.evidence_set_version,
            expected_content_hash=result.evidence_set_content_hash,
        )
        if result.originality_pack_id is None:
            raise JournalResearchHandoffError("originality_pack_required_for_journal_handoff")
        originality_pack = await self.handoff_originality_pack(
            session,
            content_case_id=result.content_case_id,
            originality_pack_id=result.originality_pack_id,
        )
        return EvidenceResearchHandoff(
            result=result,
            evidence_set=evidence_set,
            originality_pack=originality_pack,
        )

    async def handoff_evidence_set(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        content_case_id: UUID,
        evidence_set_id: UUID,
        expected_version: int,
        expected_content_hash: str,
    ) -> EvidenceSetHandoff:
        """Allow only the exact locked EvidenceSet snapshot and its optional approval."""

        if (
            isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
            or expected_version <= 0
        ):
            raise JournalResearchHandoffError("evidence_set_snapshot_version_invalid")
        if not _valid_content_hash(expected_content_hash):
            raise JournalResearchHandoffError("evidence_set_snapshot_hash_invalid")

        evidence_set = await session.get(EvidenceSet, evidence_set_id)
        if evidence_set is None:
            raise JournalResearchHandoffError("evidence_set_not_found")
        if evidence_set.project_id != project_id:
            raise JournalResearchHandoffError("evidence_set_project_mismatch")
        if evidence_set.content_case_id != content_case_id:
            raise JournalResearchHandoffError("evidence_set_content_case_mismatch")
        if evidence_set.version != expected_version:
            raise JournalResearchHandoffError("evidence_set_snapshot_version_mismatch")
        if evidence_set.content_hash != expected_content_hash:
            raise JournalResearchHandoffError("evidence_set_snapshot_hash_mismatch")
        if evidence_set.status != "locked" or evidence_set.locked_at is None:
            raise JournalResearchHandoffError("evidence_set_must_be_locked")
        if (
            not isinstance(evidence_set.evidence_ids_json, list)
            or not evidence_set.evidence_ids_json
            or not all(
                isinstance(item, str) and item.strip()
                for item in evidence_set.evidence_ids_json
            )
        ):
            raise JournalResearchHandoffError("evidence_set_snapshot_invalid")
        if evidence_set.content_hash != evidence_set_hash(evidence_set.evidence_ids_json):
            raise JournalResearchHandoffError("evidence_set_snapshot_stale")
        try:
            evidence_ids = tuple(UUID(value) for value in evidence_set.evidence_ids_json)
        except ValueError as exc:
            raise JournalResearchHandoffError("evidence_set_snapshot_invalid") from exc

        approvals = list(
            (
                await session.scalars(
                    select(EvidenceSetApproval).where(
                        EvidenceSetApproval.evidence_set_id == evidence_set.id
                    )
                )
            ).all()
        )
        approval = None
        if approvals:
            if any(
                item.evidence_set_version != evidence_set.version
                or item.evidence_set_content_hash != evidence_set.content_hash
                for item in approvals
            ):
                raise JournalResearchHandoffError("evidence_set_approval_snapshot_mismatch")
            approval = approvals[0]

        if approval is not None and (
            not isinstance(approval.approved_by, str)
            or not approval.approved_by.strip()
            or not isinstance(approval.approval_reason, str)
            or not approval.approval_reason.strip()
        ):
            raise JournalResearchHandoffError("evidence_set_approval_invalid")
        return EvidenceSetHandoff(
            evidence_set_id=evidence_set.id,
            project_id=evidence_set.project_id,
            content_case_id=content_case_id,
            version=evidence_set.version,
            content_hash=evidence_set.content_hash,
            evidence_ids=evidence_ids,
            approval_id=approval.id if approval is not None else None,
            approved_by=approval.approved_by if approval is not None else None,
        )

    async def handoff_originality_pack(
        self,
        session: AsyncSession,
        *,
        content_case_id: UUID,
        originality_pack_id: UUID,
        expected_item_refs: Sequence[object] | None = None,
        expected_snapshot_hash: str | None = None,
    ) -> OriginalityPackHandoff:
        """Require at least one complete MOTGU-owned item and preserve exact refs."""

        pack = await session.get(OriginalityPack, originality_pack_id)
        if pack is None:
            raise JournalResearchHandoffError("originality_pack_not_found")
        if pack.content_case_id != content_case_id:
            raise JournalResearchHandoffError("originality_pack_content_case_mismatch")
        if pack.status == "draft":
            raise JournalResearchHandoffError("originality_pack_approval_required")
        if pack.status == "retired":
            raise JournalResearchHandoffError("originality_pack_retired")
        if pack.status != "approved":
            raise JournalResearchHandoffError("originality_pack_approval_required")
        if not isinstance(pack.item_refs_json, list):
            raise JournalResearchHandoffError("originality_pack_refs_invalid")
        if count_usable_originality_items(pack.item_refs_json) == 0:
            raise JournalResearchHandoffError("originality_pack_motgu_material_required")
        if (
            not isinstance(pack.approved_by, str)
            or not pack.approved_by.strip()
            or not isinstance(pack.approval_reason, str)
            or not pack.approval_reason.strip()
            or not _valid_content_hash(pack.snapshot_hash)
        ):
            raise JournalResearchHandoffError("originality_pack_approval_metadata_invalid")
        snapshot_hash = originality_pack_snapshot_hash(pack)
        if pack.snapshot_hash != snapshot_hash:
            raise JournalResearchHandoffError("originality_pack_snapshot_stale")
        if expected_item_refs is not None and list(expected_item_refs) != pack.item_refs_json:
            raise JournalResearchHandoffError("originality_pack_refs_mismatch")

        if expected_snapshot_hash is not None:
            if not _valid_content_hash(expected_snapshot_hash):
                raise JournalResearchHandoffError("originality_pack_snapshot_hash_invalid")
            if expected_snapshot_hash != snapshot_hash:
                raise JournalResearchHandoffError("originality_pack_snapshot_hash_mismatch")
        return OriginalityPackHandoff(
            originality_pack_id=pack.id,
            content_case_id=pack.content_case_id,
            item_refs=tuple(pack.item_refs_json),
            snapshot_hash=snapshot_hash,
            status=pack.status,
        )

    async def persist_journal_input_bundle(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        step_run_id: UUID,
        research_decision: ResearchDecision | str,
        opportunity_id: UUID,
        evidence_set: EvidenceSetHandoff,
        originality_pack: OriginalityPackHandoff,
        provider_calls: int,
        model_calls: int,
    ) -> Artifact:
        """Persist one immutable, exact-input bundle for a Journal step."""

        try:
            decision = ResearchDecision(research_decision)
        except ValueError as exc:
            raise JournalResearchHandoffError("journal_research_decision_invalid") from exc
        if decision is ResearchDecision.BLOCKED:
            raise JournalResearchHandoffError("journal_input_bundle_blocked")
        for value, error in (
            (provider_calls, "journal_provider_call_count_invalid"),
            (model_calls, "journal_model_call_count_invalid"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise JournalResearchHandoffError(error)
        if decision is ResearchDecision.REUSE_EXISTING and (provider_calls or model_calls):
            raise JournalResearchHandoffError("reuse_existing_requires_zero_calls")

        run = await session.get(ContentRun, run_id)
        if run is None:
            raise JournalResearchHandoffError("journal_input_bundle_run_not_found")
        step_run = await session.get(StepRun, step_run_id)
        if step_run is None or step_run.run_id != run.id:
            raise JournalResearchHandoffError("journal_input_bundle_step_mismatch")
        opportunity = await session.get(ContentOpportunity, opportunity_id)
        if opportunity is None:
            raise JournalResearchHandoffError("journal_input_bundle_opportunity_not_found")
        if opportunity.project_id != run.project_id:
            raise JournalResearchHandoffError("journal_input_bundle_project_mismatch")
        content_case = await session.get(ContentCase, run.content_case_id)
        if content_case is None:
            raise JournalResearchHandoffError("journal_input_bundle_content_case_not_found")
        if (
            content_case.project_id != run.project_id
            or content_case.content_opportunity_id != opportunity.id
        ):
            raise JournalResearchHandoffError("journal_input_bundle_opportunity_mismatch")
        if not isinstance(opportunity.selected_by, str) or not opportunity.selected_by.strip():
            raise JournalResearchHandoffError("journal_input_bundle_selection_required")

        validated_evidence_set = await self.handoff_evidence_set(
            session,
            project_id=run.project_id,
            content_case_id=run.content_case_id,
            evidence_set_id=evidence_set.evidence_set_id,
            expected_version=evidence_set.version,
            expected_content_hash=evidence_set.content_hash,
        )
        validated_originality_pack = await self.handoff_originality_pack(
            session,
            content_case_id=run.content_case_id,
            originality_pack_id=originality_pack.originality_pack_id,
            expected_item_refs=originality_pack.item_refs,
            expected_snapshot_hash=originality_pack.snapshot_hash,
        )

        payload: dict[str, object] = {
            "schema_version": _JOURNAL_INPUT_BUNDLE_SCHEMA_VERSION,
            "artifact_type": "journal_input_bundle",
            "research_decision": decision.value,
            "opportunity": _opportunity_payload(opportunity),
            "evidence_set": {
                "id": str(validated_evidence_set.evidence_set_id),
                "version": validated_evidence_set.version,
                "content_hash": validated_evidence_set.content_hash,
            },
            "originality_pack": {
                "id": str(validated_originality_pack.originality_pack_id),
                "snapshot_hash": validated_originality_pack.snapshot_hash,
            },
            "provider_calls": provider_calls,
            "model_calls": model_calls,
        }
        bundle_hash = _canonical_hash(payload)
        existing = await session.scalar(
            select(Artifact).where(
                Artifact.run_id == run.id,
                Artifact.artifact_type == "journal_input_bundle",
                Artifact.content_hash == bundle_hash,
            )
        )
        if existing is not None:
            if existing.content_json != payload:
                raise JournalResearchHandoffError("journal_input_bundle_hash_collision")
            if str(existing.id) not in step_run.output_artifact_refs_json:
                step_run.output_artifact_refs_json = [
                    *step_run.output_artifact_refs_json,
                    str(existing.id),
                ]
                await session.flush()
            return existing

        latest_version = await session.scalar(
            select(func.max(Artifact.version)).where(
                Artifact.run_id == run.id,
                Artifact.artifact_type == "journal_input_bundle",
            )
        )
        artifact = Artifact(
            run_id=run.id,
            step_run_id=step_run.id,
            artifact_type="journal_input_bundle",
            locale=opportunity.locale,
            version=(latest_version or 0) + 1,
            content_json=payload,
            content_hash=bundle_hash,
        )
        session.add(artifact)
        await session.flush()
        if str(artifact.id) not in step_run.output_artifact_refs_json:
            step_run.output_artifact_refs_json = [
                *step_run.output_artifact_refs_json,
                str(artifact.id),
            ]
            await session.flush()
        return artifact


__all__ = [
    "DiscoveryResearchHandoff",
    "EvidenceResearchHandoff",
    "EvidenceSetHandoff",
    "JournalResearchHandoff",
    "JournalResearchHandoffError",
    "OpportunitySelectionHandoff",
    "OriginalityPackHandoff",
    "ResearchDecision",
    "originality_pack_snapshot_hash",
    "select_research_decision",
]
