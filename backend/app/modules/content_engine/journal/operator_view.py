"""Authoritative read projection for the Journal operator console.

The projection is intentionally read-only. It exposes persisted business state and exact
immutable bindings needed by the UI, while leaving all workflow decisions to the operator
control plane.
"""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.angle import (
    _artifact_candidates,
    angle_candidate_hash,
    load_journal_input_bundle,
)
from app.modules.content_engine.journal.models import JournalIntakeSpec, JournalRequiredLocale
from app.modules.content_engine.journal.operator_control import OperatorControlError, OperatorState
from app.modules.content_engine.journal.operator_vertical_slice import get_operator_state_v45
from app.modules.content_engine.models import ContentCase, ContentOpportunity
from app.modules.harness.models import Artifact
from app.modules.harness.persistence import get_latest_checkpoint

LocaleRole = Literal["source", "translation"]


class OperatorRequiredLocaleView(BaseModel):
    locale: str
    role: LocaleRole


class OperatorIntakeView(BaseModel):
    source_locale: str
    research_country: str
    required_locales: list[OperatorRequiredLocaleView] = Field(default_factory=list)


class OperatorAngleArtifactView(BaseModel):
    id: UUID
    version: int
    content_hash: str


class OperatorAngleCandidateView(BaseModel):
    angle_id: str
    candidate_hash: str
    working_title: str
    reader_problem: str
    central_question: str
    core_promise: str
    point_of_view: str
    why_now: str
    evidence_refs: list[str]
    originality_refs: list[str]
    excluded_claims: list[str]
    risks: list[str]
    confidence: float
    locale: str


class OperatorAngleGateView(BaseModel):
    type: Literal["angle"] = "angle"
    artifact: OperatorAngleArtifactView
    candidates: list[OperatorAngleCandidateView]


class OperatorCaseView(BaseModel):
    content_case_id: UUID
    question: str
    reader: str
    situation: str
    need: str
    intent: str
    promise: str
    state: OperatorState
    intake: OperatorIntakeView
    pending_gate: OperatorAngleGateView | None = None


def _bundle_ref(artifact: Artifact) -> tuple[UUID, int, str]:
    payload = artifact.content_json
    if not isinstance(payload, dict):
        raise OperatorControlError("operator_angle_projection_invalid")
    raw_ref = payload.get("journal_input_bundle")
    if not isinstance(raw_ref, dict):
        raise OperatorControlError("operator_angle_projection_invalid")
    raw_id = raw_ref.get("id")
    version = raw_ref.get("version")
    content_hash = raw_ref.get("content_hash")
    if not isinstance(raw_id, str):
        raise OperatorControlError("operator_angle_projection_invalid")
    try:
        bundle_id = UUID(raw_id)
    except ValueError as exc:
        raise OperatorControlError("operator_angle_projection_invalid") from exc
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise OperatorControlError("operator_angle_projection_invalid")
    if not isinstance(content_hash, str) or len(content_hash) != 64:
        raise OperatorControlError("operator_angle_projection_invalid")
    return bundle_id, version, content_hash


def _locale_role(value: str) -> LocaleRole:
    if value not in {"source", "translation"}:
        raise OperatorControlError("operator_required_locales_invalid")
    return cast(LocaleRole, value)


async def _pending_angle_artifact(
    session: AsyncSession,
    *,
    state: OperatorState,
) -> Artifact:
    if state.current_run_id is None or state.current_step_run_id is None:
        raise OperatorControlError("operator_angle_projection_missing")
    checkpoint = await get_latest_checkpoint(session, run_id=state.current_run_id)
    if checkpoint is None or not isinstance(checkpoint.content_json, dict):
        raise OperatorControlError("operator_angle_projection_missing")
    pending = checkpoint.content_json.get("pending_approval")
    if not isinstance(pending, dict) or pending.get("step_key") != "angle":
        raise OperatorControlError("operator_angle_projection_stale")
    raw_artifact_id = pending.get("artifact_id")
    if not isinstance(raw_artifact_id, str):
        raise OperatorControlError("operator_angle_projection_invalid")
    try:
        artifact_id = UUID(raw_artifact_id)
    except ValueError as exc:
        raise OperatorControlError("operator_angle_projection_invalid") from exc
    artifact = await session.get(Artifact, artifact_id)
    if (
        artifact is None
        or artifact.run_id != state.current_run_id
        or artifact.step_run_id != state.current_step_run_id
        or artifact.artifact_type != "angle_candidates"
    ):
        raise OperatorControlError("operator_angle_projection_stale")
    return artifact


async def _angle_gate(
    session: AsyncSession,
    *,
    state: OperatorState,
) -> OperatorAngleGateView:
    artifact = await _pending_angle_artifact(session, state=state)
    bundle_id, bundle_version, bundle_hash = _bundle_ref(artifact)
    try:
        bundle = await load_journal_input_bundle(
            session,
            journal_input_bundle_id=bundle_id,
            expected_content_hash=bundle_hash,
        )
        if bundle.artifact.version != bundle_version:
            raise OperatorControlError("operator_angle_projection_stale")
        candidates = _artifact_candidates(artifact, bundle=bundle)
    except OperatorControlError:
        raise
    except ValueError as exc:
        raise OperatorControlError("operator_angle_projection_stale") from exc
    if not candidates:
        raise OperatorControlError("operator_angle_projection_missing")
    return OperatorAngleGateView(
        artifact=OperatorAngleArtifactView(
            id=artifact.id,
            version=artifact.version,
            content_hash=artifact.content_hash,
        ),
        candidates=[
            OperatorAngleCandidateView(
                angle_id=candidate.angle_id,
                candidate_hash=angle_candidate_hash(candidate),
                working_title=candidate.working_title,
                reader_problem=candidate.reader_problem,
                central_question=candidate.central_question,
                core_promise=candidate.core_promise,
                point_of_view=candidate.point_of_view,
                why_now=candidate.why_now,
                evidence_refs=list(candidate.evidence_refs),
                originality_refs=list(candidate.originality_refs),
                excluded_claims=list(candidate.excluded_claims),
                risks=list(candidate.risks),
                confidence=candidate.confidence,
                locale=candidate.locale,
            )
            for candidate in candidates
        ],
    )


async def get_operator_case_view(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> OperatorCaseView:
    """Return the browser projection for one Journal case from persisted canonical state."""

    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None or content_case.content_type != "journal":
        raise OperatorControlError("operator_case_not_found")
    opportunity = await session.get(ContentOpportunity, content_case.content_opportunity_id)
    spec = await session.scalar(
        select(JournalIntakeSpec).where(JournalIntakeSpec.content_case_id == content_case.id)
    )
    if opportunity is None or spec is None:
        raise OperatorControlError("operator_manual_intake_receipt_missing")
    requirements = list(
        (
            await session.scalars(
                select(JournalRequiredLocale)
                .where(JournalRequiredLocale.content_case_id == content_case.id)
                .order_by(JournalRequiredLocale.role, JournalRequiredLocale.locale)
            )
        ).all()
    )
    if not requirements:
        raise OperatorControlError("operator_required_locales_missing")
    state = await get_operator_state_v45(session, content_case_id=content_case.id)
    pending_gate = None
    if state.status == "AWAITING_APPROVAL" and state.human_gate == "angle":
        pending_gate = await _angle_gate(session, state=state)
    return OperatorCaseView(
        content_case_id=content_case.id,
        question=opportunity.question,
        reader=opportunity.reader,
        situation=opportunity.situation,
        need=opportunity.need,
        intent=opportunity.intent,
        promise=opportunity.promise,
        state=state,
        intake=OperatorIntakeView(
            source_locale=spec.source_locale,
            research_country=spec.research_country,
            required_locales=[
                OperatorRequiredLocaleView(locale=row.locale, role=_locale_role(row.role))
                for row in requirements
            ],
        ),
        pending_gate=pending_gate,
    )


__all__ = [
    "OperatorAngleCandidateView",
    "OperatorAngleGateView",
    "OperatorCaseView",
    "OperatorIntakeView",
    "OperatorRequiredLocaleView",
    "get_operator_case_view",
]
