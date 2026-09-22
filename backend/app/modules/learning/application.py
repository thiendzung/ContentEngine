"""LL-01C human review and safe Customer Map application."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
    utc_now,
)
from app.modules.customer_intelligence.insights import (
    CustomerInsightError,
    ensure_customer_insight,
    link_customer_insight_signal,
)
from app.modules.customer_intelligence.living_map import (
    CustomerMapError,
    ensure_customer_insight_need_link,
    refresh_customer_map_snapshot_artifact,
)
from app.modules.customer_intelligence.models import CustomerInsight
from app.modules.harness.models import Artifact
from app.modules.learning.models import (
    LearningApplication,
    LearningCandidate,
    LearningCandidateAssessment,
    LearningCandidateObservation,
    LearningCandidateReview,
    LearningCandidateSignal,
)
from app.modules.learning.service import LearningError, _validated_assessment_payload

ReviewDecision = Literal[
    "APPROVE",
    "REJECT",
    "REQUEST_MORE_EVIDENCE",
    "NO_MAP_CHANGE",
]


class LearningApplicationError(ValueError):
    """Stable fail-closed LL-01C error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CandidateSnapshot:
    candidate: LearningCandidate
    snapshot_hash: str
    target_snapshot: dict[str, object]
    signal_links: tuple[tuple[UUID, str], ...]
    assessment_ids: tuple[UUID, ...]
    observation_links: tuple[tuple[UUID, str], ...]
    source_run_id: UUID


@dataclass(frozen=True, slots=True)
class CandidateReviewResult:
    review: LearningCandidateReview
    replayed: bool


@dataclass(frozen=True, slots=True)
class LearningApplicationResult:
    application: LearningApplication
    replayed: bool
    resulting_target_id: UUID | None
    customer_map_snapshot_artifact_id: UUID | None
    change_report: dict[str, object] | None


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text(value: str, code: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise LearningApplicationError(code)
    return normalized


def _uuid_from_scope(value: object, code: str) -> UUID:
    if not isinstance(value, str):
        raise LearningApplicationError(code)
    try:
        return UUID(value)
    except ValueError as exc:
        raise LearningApplicationError(code) from exc


def _optional_uuid_from_scope(value: object, code: str) -> UUID | None:
    if value is None:
        return None
    return _uuid_from_scope(value, code)


async def _latest_candidate_is_exact(
    session: AsyncSession,
    *,
    candidate: LearningCandidate,
) -> bool:
    newer = await session.scalar(
        select(func.count())
        .select_from(LearningCandidate)
        .where(
            LearningCandidate.project_id == candidate.project_id,
            LearningCandidate.candidate_key == candidate.candidate_key,
            LearningCandidate.version > candidate.version,
        )
    )
    return int(newer or 0) == 0


async def _target_snapshot(
    session: AsyncSession,
    *,
    candidate: LearningCandidate,
    lock_target: bool,
) -> dict[str, object]:
    scope = candidate.scope_json
    frozen_audience = _optional_uuid_from_scope(
        scope.get("audience_hypothesis_id"),
        "learning_review_audience_scope_invalid",
    )
    frozen_need_id = _uuid_from_scope(
        scope.get("need_hypothesis_id"),
        "learning_review_need_scope_invalid",
    )
    frozen_need_version = scope.get("need_hypothesis_version")
    if not isinstance(frozen_need_version, int) or frozen_need_version < 1:
        raise LearningApplicationError("learning_review_need_version_invalid")

    base: dict[str, object] = {
        "target_type": candidate.target_type,
        "target_id": str(candidate.target_id) if candidate.target_id else None,
        "relation": candidate.relation,
        "proposal": candidate.proposal_json,
        "scope": scope,
        "evidence_status": candidate.evidence_status,
    }

    if candidate.target_type == "need_hypothesis":
        if candidate.target_id is None or candidate.target_id != frozen_need_id:
            raise LearningApplicationError("learning_review_need_target_mismatch")
        need_stmt = (
            select(NeedHypothesis)
            .where(NeedHypothesis.id == candidate.target_id)
            .execution_options(populate_existing=True)
        )
        if lock_target:
            need_stmt = need_stmt.with_for_update()
        need = await session.scalar(need_stmt)
        if need is None or need.project_id != candidate.project_id:
            raise LearningApplicationError("learning_review_need_target_stale")
        if need.version != frozen_need_version:
            raise LearningApplicationError("learning_review_need_version_stale")
        if need.audience_hypothesis_id != frozen_audience:
            raise LearningApplicationError("learning_review_need_audience_stale")
        base["current_target"] = {
            "id": str(need.id),
            "version": need.version,
            "status": need.status,
            "audience_hypothesis_id": (
                str(need.audience_hypothesis_id)
                if need.audience_hypothesis_id is not None
                else None
            ),
        }
    elif candidate.target_type == "customer_insight":
        if candidate.target_id is None:
            raise LearningApplicationError("learning_review_insight_target_missing")
        insight_stmt = (
            select(CustomerInsight)
            .where(CustomerInsight.id == candidate.target_id)
            .execution_options(populate_existing=True)
        )
        if lock_target:
            insight_stmt = insight_stmt.with_for_update()
        insight = await session.scalar(insight_stmt)
        if insight is None or insight.project_id != candidate.project_id:
            raise LearningApplicationError("learning_review_insight_target_stale")
        insight_audience = (
            str(insight.audience_hypothesis_id)
            if insight.audience_hypothesis_id is not None
            else None
        )
        if insight_audience != (
            str(frozen_audience) if frozen_audience is not None else None
        ):
            raise LearningApplicationError("learning_review_insight_audience_stale")
        latest_version = await session.scalar(
            select(func.max(CustomerInsight.version)).where(
                CustomerInsight.project_id == insight.project_id,
                CustomerInsight.insight_key == insight.insight_key,
            )
        )
        if latest_version != insight.version:
            raise LearningApplicationError("learning_review_insight_version_stale")
        base["current_target"] = {
            "id": str(insight.id),
            "insight_key": insight.insight_key,
            "version": insight.version,
            "status": insight.status,
            "audience_hypothesis_id": insight_audience,
        }
    elif candidate.target_type == "new_customer_insight":
        if candidate.target_id is not None:
            raise LearningApplicationError("learning_review_new_insight_target_invalid")
        need_stmt = (
            select(NeedHypothesis)
            .where(NeedHypothesis.id == frozen_need_id)
            .execution_options(populate_existing=True)
        )
        if lock_target:
            need_stmt = need_stmt.with_for_update()
        need = await session.scalar(need_stmt)
        if need is None or need.project_id != candidate.project_id:
            raise LearningApplicationError("learning_review_new_insight_need_stale")
        need_audience = (
            str(need.audience_hypothesis_id)
            if need.audience_hypothesis_id is not None
            else None
        )
        if need.version != frozen_need_version:
            raise LearningApplicationError(
                "learning_review_new_insight_need_version_stale"
            )
        if need_audience != (
            str(frozen_audience) if frozen_audience is not None else None
        ):
            raise LearningApplicationError(
                "learning_review_new_insight_audience_stale"
            )
        proposal = candidate.proposal_json
        if set(proposal) != {"insight_type", "situation", "need_relation"}:
            raise LearningApplicationError(
                "learning_review_new_insight_proposal_invalid"
            )
        if not isinstance(proposal.get("insight_type"), str):
            raise LearningApplicationError(
                "learning_review_new_insight_proposal_invalid"
            )
        situation = proposal.get("situation")
        if situation is not None and (
            not isinstance(situation, str) or not situation.strip()
        ):
            raise LearningApplicationError(
                "learning_review_new_insight_proposal_invalid"
            )
        if proposal.get("need_relation") not in {
            "supports",
            "contradicts",
            "context",
        }:
            raise LearningApplicationError(
                "learning_review_new_insight_proposal_invalid"
            )
        base["current_target"] = {
            "need_hypothesis_id": str(need.id),
            "need_version": need.version,
            "need_status": need.status,
            "audience_hypothesis_id": need_audience,
        }
    elif candidate.target_type == "no_map_change":
        if candidate.target_id is not None:
            raise LearningApplicationError("learning_review_no_map_target_invalid")
        base["current_target"] = None
    else:
        raise LearningApplicationError("learning_review_target_type_invalid")

    return base


async def _candidate_snapshot(
    session: AsyncSession,
    *,
    candidate_id: UUID,
    lock: bool,
    lock_target: bool = False,
) -> CandidateSnapshot:
    stmt = select(LearningCandidate).where(LearningCandidate.id == candidate_id)
    if lock:
        stmt = stmt.with_for_update()
    candidate = await session.scalar(stmt)
    if candidate is None:
        raise LearningApplicationError("learning_candidate_not_found")
    if candidate.status != "OPEN":
        raise LearningApplicationError("learning_candidate_not_open")
    if not await _latest_candidate_is_exact(session, candidate=candidate):
        raise LearningApplicationError("learning_candidate_stale")

    project = await session.get(Project, candidate.project_id)
    if project is None:
        raise LearningApplicationError("learning_candidate_project_not_found")

    assessment_links = list(
        (
            await session.scalars(
                select(LearningCandidateAssessment)
                .where(
                    LearningCandidateAssessment.learning_candidate_id
                    == candidate.id
                )
                .order_by(LearningCandidateAssessment.assessment_artifact_id)
            )
        ).all()
    )
    signal_links = list(
        (
            await session.scalars(
                select(LearningCandidateSignal)
                .where(
                    LearningCandidateSignal.learning_candidate_id == candidate.id
                )
                .order_by(
                    LearningCandidateSignal.signal_id,
                    LearningCandidateSignal.relation,
                )
            )
        ).all()
    )
    observation_links = list(
        (
            await session.scalars(
                select(LearningCandidateObservation)
                .where(
                    LearningCandidateObservation.learning_candidate_id
                    == candidate.id
                )
                .order_by(
                    LearningCandidateObservation.observation_id,
                    LearningCandidateObservation.relation,
                )
            )
        ).all()
    )
    if not assessment_links:
        raise LearningApplicationError("learning_candidate_assessment_missing")
    assessment_ids = tuple(
        row.assessment_artifact_id for row in assessment_links
    )
    if candidate.source_assessment_artifact_id not in assessment_ids:
        raise LearningApplicationError(
            "learning_candidate_source_assessment_missing"
        )

    expected_signals: dict[UUID, str] = {}
    expected_observations: dict[UUID, str] = {}
    assessment_hashes: list[dict[str, str]] = []
    source_run_id: UUID | None = None
    for link in assessment_links:
        artifact = await session.get(Artifact, link.assessment_artifact_id)
        if artifact is None:
            raise LearningApplicationError("learning_candidate_assessment_missing")
        try:
            payload = await _validated_assessment_payload(
                session,
                artifact=artifact,
            )
        except LearningError as exc:
            raise LearningApplicationError(
                f"learning_candidate_assessment_{exc.code}"
            ) from exc
        if payload.get("project_id") != str(candidate.project_id):
            raise LearningApplicationError(
                "learning_candidate_assessment_project_mismatch"
            )
        if payload.get("candidate_scope") != candidate.scope_json:
            raise LearningApplicationError(
                "learning_candidate_assessment_scope_mismatch"
            )
        evidence = payload.get("evidence")
        if not isinstance(evidence, dict):
            raise LearningApplicationError(
                "learning_candidate_assessment_evidence_invalid"
            )
        signal_rows = evidence.get("signals")
        observation_rows = evidence.get("observations")
        if not isinstance(signal_rows, list) or not isinstance(
            observation_rows, list
        ):
            raise LearningApplicationError(
                "learning_candidate_assessment_evidence_invalid"
            )
        for row in signal_rows:
            if not isinstance(row, dict):
                raise LearningApplicationError(
                    "learning_candidate_assessment_evidence_invalid"
                )
            signal_id = _uuid_from_scope(
                row.get("id"),
                "learning_candidate_assessment_signal_invalid",
            )
            relation = row.get("relation")
            if relation not in {"supports", "contradicts", "context"}:
                raise LearningApplicationError(
                    "learning_candidate_assessment_signal_invalid"
                )
            previous = expected_signals.get(signal_id)
            if previous is not None and previous != relation:
                raise LearningApplicationError(
                    "learning_candidate_signal_relation_conflict"
                )
            expected_signals[signal_id] = relation
        for row in observation_rows:
            if not isinstance(row, dict):
                raise LearningApplicationError(
                    "learning_candidate_assessment_evidence_invalid"
                )
            observation_id = _uuid_from_scope(
                row.get("id"),
                "learning_candidate_assessment_observation_invalid",
            )
            relation = row.get("relation")
            if relation not in {"supports", "contradicts", "context"}:
                raise LearningApplicationError(
                    "learning_candidate_assessment_observation_invalid"
                )
            previous = expected_observations.get(observation_id)
            if previous is not None and previous != relation:
                raise LearningApplicationError(
                    "learning_candidate_observation_relation_conflict"
                )
            expected_observations[observation_id] = relation
        assessment_hashes.append(
            {
                "id": str(artifact.id),
                "content_hash": artifact.content_hash,
            }
        )
        if artifact.id == candidate.source_assessment_artifact_id:
            source_run_id = artifact.run_id

    actual_signals = {
        row.signal_id: row.relation for row in signal_links
    }
    actual_observations = {
        row.observation_id: row.relation for row in observation_links
    }
    if actual_signals != expected_signals:
        raise LearningApplicationError(
            "learning_candidate_signal_evidence_stale"
        )
    if actual_observations != expected_observations:
        raise LearningApplicationError(
            "learning_candidate_observation_evidence_stale"
        )
    if source_run_id is None:
        raise LearningApplicationError("learning_candidate_source_run_missing")

    signal_snapshot: list[dict[str, object]] = []
    for signal_id, relation in sorted(
        actual_signals.items(),
        key=lambda item: str(item[0]),
    ):
        signal = await session.get(Signal, signal_id)
        if signal is None or signal.project_id != candidate.project_id:
            raise LearningApplicationError("learning_candidate_signal_stale")
        signal_snapshot.append(
            {
                "id": str(signal.id),
                "relation": relation,
                "fingerprint": signal.fingerprint,
                "independence_group": signal.independence_group,
            }
        )

    target_snapshot = await _target_snapshot(
        session,
        candidate=candidate,
        lock_target=lock_target,
    )
    snapshot_payload: dict[str, object] = {
        "candidate": {
            "id": str(candidate.id),
            "project_id": str(candidate.project_id),
            "candidate_key": candidate.candidate_key,
            "version": candidate.version,
            "target_type": candidate.target_type,
            "target_id": str(candidate.target_id) if candidate.target_id else None,
            "statement": candidate.statement,
            "relation": candidate.relation,
            "proposal": candidate.proposal_json,
            "scope": candidate.scope_json,
            "evidence_status": candidate.evidence_status,
            "alternative_explanations": candidate.alternative_explanations_json,
            "missing_evidence": candidate.missing_evidence_json,
            "expected_benefit": candidate.expected_benefit,
            "regression_risk": candidate.regression_risk,
            "source_assessment_artifact_id": str(
                candidate.source_assessment_artifact_id
            ),
            "supersedes_id": (
                str(candidate.supersedes_id)
                if candidate.supersedes_id is not None
                else None
            ),
            "status": candidate.status,
        },
        "assessments": assessment_hashes,
        "signals": signal_snapshot,
        "observations": [
            {
                "id": str(observation_id),
                "relation": relation,
            }
            for observation_id, relation in sorted(
                actual_observations.items(),
                key=lambda item: str(item[0]),
            )
        ],
        "target_snapshot": target_snapshot,
    }
    return CandidateSnapshot(
        candidate=candidate,
        snapshot_hash=_hash(snapshot_payload),
        target_snapshot=target_snapshot,
        signal_links=tuple(
            sorted(actual_signals.items(), key=lambda item: str(item[0]))
        ),
        assessment_ids=assessment_ids,
        observation_links=tuple(
            sorted(actual_observations.items(), key=lambda item: str(item[0]))
        ),
        source_run_id=source_run_id,
    )


def _validate_review_decision(
    snapshot: CandidateSnapshot,
    decision: ReviewDecision,
) -> None:
    if decision not in {
        "APPROVE",
        "REJECT",
        "REQUEST_MORE_EVIDENCE",
        "NO_MAP_CHANGE",
    }:
        raise LearningApplicationError("learning_review_decision_invalid")
    if decision != "APPROVE":
        return
    candidate = snapshot.candidate
    if candidate.target_type == "no_map_change":
        return
    if candidate.evidence_status == "NEEDS_EVIDENCE":
        raise LearningApplicationError("learning_review_evidence_required")
    if candidate.target_type == "need_hypothesis":
        directional = [
            relation
            for _, relation in snapshot.signal_links
            if relation in {"supports", "contradicts"}
        ]
        if not directional:
            raise LearningApplicationError(
                "learning_review_need_directional_evidence_required"
            )


async def review_learning_candidate(
    session: AsyncSession,
    *,
    learning_candidate_id: UUID,
    decision: ReviewDecision,
    reviewed_by: str,
    reason: str,
) -> CandidateReviewResult:
    """Record one immutable human decision without mutating Customer Truth."""

    actor = _text(reviewed_by, "learning_review_reviewer_required")
    rationale = _text(reason, "learning_review_reason_required")
    existing = await session.scalar(
        select(LearningCandidateReview).where(
            LearningCandidateReview.learning_candidate_id
            == learning_candidate_id
        )
    )
    if existing is not None:
        if (
            existing.decision != decision
            or existing.reviewed_by != actor
            or existing.reason != rationale
        ):
            raise LearningApplicationError("learning_review_replay_conflict")
        return CandidateReviewResult(review=existing, replayed=True)

    snapshot = await _candidate_snapshot(
        session,
        candidate_id=learning_candidate_id,
        lock=True,
    )
    _validate_review_decision(snapshot, decision)

    # Re-check after taking the candidate row lock for concurrent review replay.
    existing = await session.scalar(
        select(LearningCandidateReview).where(
            LearningCandidateReview.learning_candidate_id
            == snapshot.candidate.id
        )
    )
    if existing is not None:
        if (
            existing.project_id != snapshot.candidate.project_id
            or existing.candidate_version != snapshot.candidate.version
            or existing.decision != decision
            or existing.reviewed_by != actor
            or existing.reason != rationale
            or existing.candidate_snapshot_hash != snapshot.snapshot_hash
            or existing.target_snapshot_json != snapshot.target_snapshot
        ):
            raise LearningApplicationError("learning_review_replay_conflict")
        return CandidateReviewResult(review=existing, replayed=True)

    review = LearningCandidateReview(
        project_id=snapshot.candidate.project_id,
        learning_candidate_id=snapshot.candidate.id,
        candidate_version=snapshot.candidate.version,
        decision=decision,
        reviewed_by=actor,
        reason=rationale,
        candidate_snapshot_hash=snapshot.snapshot_hash,
        target_snapshot_json=snapshot.target_snapshot,
        reviewed_at=utc_now(),
    )
    session.add(review)
    await session.flush()
    return CandidateReviewResult(review=review, replayed=False)


async def _ensure_need_signal_link(
    session: AsyncSession,
    *,
    need: NeedHypothesis,
    signal_id: UUID,
    relation: str,
) -> None:
    if relation not in {"supports", "contradicts"}:
        return
    signal = await session.get(Signal, signal_id)
    if signal is None or signal.project_id != need.project_id:
        raise LearningApplicationError("learning_apply_need_signal_stale")
    rows = list(
        (
            await session.scalars(
                select(NeedHypothesisSignal).where(
                    NeedHypothesisSignal.need_hypothesis_id == need.id,
                    NeedHypothesisSignal.signal_id == signal.id,
                )
            )
        ).all()
    )
    for row in rows:
        if row.relation != relation:
            raise LearningApplicationError(
                "learning_apply_need_signal_relation_conflict"
            )
        if row.relation == relation:
            return
    session.add(
        NeedHypothesisSignal(
            need_hypothesis_id=need.id,
            signal_id=signal.id,
            relation=relation,
        )
    )
    await session.flush()


async def _require_need_scope_current(
    session: AsyncSession,
    *,
    candidate: LearningCandidate,
) -> NeedHypothesis:
    scope = candidate.scope_json
    need_id = _uuid_from_scope(
        scope.get("need_hypothesis_id"),
        "learning_apply_need_scope_invalid",
    )
    version = scope.get("need_hypothesis_version")
    if not isinstance(version, int) or version < 1:
        raise LearningApplicationError("learning_apply_need_version_invalid")
    need = await session.get(NeedHypothesis, need_id)
    if need is None or need.project_id != candidate.project_id:
        raise LearningApplicationError("learning_apply_need_stale")
    if need.version != version:
        raise LearningApplicationError("learning_apply_need_version_stale")
    frozen_audience = _optional_uuid_from_scope(
        scope.get("audience_hypothesis_id"),
        "learning_apply_audience_scope_invalid",
    )
    if need.audience_hypothesis_id != frozen_audience:
        raise LearningApplicationError("learning_apply_need_audience_stale")
    return need


async def _apply_need(
    session: AsyncSession,
    *,
    snapshot: CandidateSnapshot,
) -> tuple[str, UUID]:
    candidate = snapshot.candidate
    if candidate.target_id is None:
        raise LearningApplicationError("learning_apply_need_target_missing")
    need = await _require_need_scope_current(session, candidate=candidate)
    if need.id != candidate.target_id:
        raise LearningApplicationError("learning_apply_need_target_mismatch")
    directional_count = 0
    for signal_id, relation in snapshot.signal_links:
        if relation in {"supports", "contradicts"}:
            directional_count += 1
            await _ensure_need_signal_link(
                session,
                need=need,
                signal_id=signal_id,
                relation=relation,
            )
    if directional_count == 0:
        raise LearningApplicationError(
            "learning_apply_need_directional_evidence_required"
        )
    return "link_need_signals", need.id


async def _apply_existing_insight(
    session: AsyncSession,
    *,
    snapshot: CandidateSnapshot,
) -> tuple[str, UUID]:
    candidate = snapshot.candidate
    if candidate.target_id is None:
        raise LearningApplicationError("learning_apply_insight_target_missing")
    insight = await session.get(CustomerInsight, candidate.target_id)
    if insight is None or insight.project_id != candidate.project_id:
        raise LearningApplicationError("learning_apply_insight_stale")
    frozen_audience = _optional_uuid_from_scope(
        candidate.scope_json.get("audience_hypothesis_id"),
        "learning_apply_audience_scope_invalid",
    )
    if insight.audience_hypothesis_id != frozen_audience:
        raise LearningApplicationError("learning_apply_insight_audience_stale")
    latest_version = await session.scalar(
        select(func.max(CustomerInsight.version)).where(
            CustomerInsight.project_id == insight.project_id,
            CustomerInsight.insight_key == insight.insight_key,
        )
    )
    if latest_version != insight.version:
        raise LearningApplicationError("learning_apply_insight_version_stale")
    for signal_id, relation in snapshot.signal_links:
        try:
            await link_customer_insight_signal(
                session,
                customer_insight_id=insight.id,
                signal_id=signal_id,
                relation=relation,  # type: ignore[arg-type]
            )
        except CustomerInsightError as exc:
            raise LearningApplicationError(
                f"learning_apply_{exc.code}"
            ) from exc
    return "link_insight_signals", insight.id


async def _apply_new_insight(
    session: AsyncSession,
    *,
    snapshot: CandidateSnapshot,
    applied_by: str,
    review_reason: str,
) -> tuple[str, UUID]:
    candidate = snapshot.candidate
    need = await _require_need_scope_current(session, candidate=candidate)
    proposal = candidate.proposal_json
    if set(proposal) != {"insight_type", "situation", "need_relation"}:
        raise LearningApplicationError("learning_apply_new_insight_proposal_invalid")
    insight_type = proposal.get("insight_type")
    situation = proposal.get("situation")
    need_relation = proposal.get("need_relation")
    if not isinstance(insight_type, str):
        raise LearningApplicationError("learning_apply_new_insight_type_invalid")
    if situation is not None and not isinstance(situation, str):
        raise LearningApplicationError(
            "learning_apply_new_insight_situation_invalid"
        )
    if need_relation not in {"supports", "contradicts", "context"}:
        raise LearningApplicationError(
            "learning_apply_new_insight_need_relation_invalid"
        )
    frozen_audience = _optional_uuid_from_scope(
        candidate.scope_json.get("audience_hypothesis_id"),
        "learning_apply_audience_scope_invalid",
    )
    try:
        insight = await ensure_customer_insight(
            session,
            project_id=candidate.project_id,
            insight_type=insight_type,  # type: ignore[arg-type]
            statement=candidate.statement,
            audience_hypothesis_id=frozen_audience,
            situation=situation,
            alternative_explanations=candidate.alternative_explanations_json,
            missing_evidence=candidate.missing_evidence_json,
        )
    except CustomerInsightError as exc:
        raise LearningApplicationError(
            f"learning_apply_{exc.code}"
        ) from exc
    if insight.status != "CANDIDATE":
        raise LearningApplicationError("learning_apply_new_insight_status_stale")
    latest_version = await session.scalar(
        select(func.max(CustomerInsight.version)).where(
            CustomerInsight.project_id == insight.project_id,
            CustomerInsight.insight_key == insight.insight_key,
        )
    )
    if latest_version != insight.version:
        raise LearningApplicationError("learning_apply_new_insight_version_stale")

    for signal_id, relation in snapshot.signal_links:
        try:
            await link_customer_insight_signal(
                session,
                customer_insight_id=insight.id,
                signal_id=signal_id,
                relation=relation,  # type: ignore[arg-type]
            )
        except CustomerInsightError as exc:
            raise LearningApplicationError(
                f"learning_apply_{exc.code}"
            ) from exc
    try:
        await ensure_customer_insight_need_link(
            session,
            customer_insight_id=insight.id,
            need_hypothesis_id=need.id,
            relation=need_relation,  # type: ignore[arg-type]
            linked_by=applied_by,
            reason=(
                f"Approved LearningCandidate {candidate.id} "
                f"v{candidate.version}: {review_reason}"
            ),
        )
    except CustomerMapError as exc:
        raise LearningApplicationError(
            f"learning_apply_{exc.code}"
        ) from exc
    return "create_candidate_insight", insight.id


async def apply_learning_candidate(
    session: AsyncSession,
    *,
    review_id: UUID,
    applied_by: str,
) -> LearningApplicationResult:
    """Apply one approved review exactly once with stale checks before mutation."""

    actor = _text(applied_by, "learning_apply_actor_required")
    review = await session.get(LearningCandidateReview, review_id)
    if review is None:
        raise LearningApplicationError("learning_review_not_found")

    existing = await session.scalar(
        select(LearningApplication).where(
            LearningApplication.review_id == review.id
        )
    )
    if existing is not None:
        return LearningApplicationResult(
            application=existing,
            replayed=True,
            resulting_target_id=existing.resulting_target_id,
            customer_map_snapshot_artifact_id=(
                existing.customer_map_snapshot_artifact_id
            ),
            change_report=existing.change_report_json,
        )

    if review.decision not in {"APPROVE", "NO_MAP_CHANGE"}:
        raise LearningApplicationError("learning_review_not_applicable")

    # Serialize Customer Truth / Customer Map mutation at project scope.
    # LL-01B candidate creation also uses Project -> Candidate lock ordering,
    # so keeping the same order avoids a cross-slice deadlock.
    locked_project = await session.scalar(
        select(Project)
        .where(Project.id == review.project_id)
        .with_for_update()
    )
    if locked_project is None:
        raise LearningApplicationError("learning_apply_project_not_found")

    snapshot = await _candidate_snapshot(
        session,
        candidate_id=review.learning_candidate_id,
        lock=True,
        lock_target=True,
    )
    if (
        review.project_id != snapshot.candidate.project_id
        or review.candidate_version != snapshot.candidate.version
        or review.candidate_snapshot_hash != snapshot.snapshot_hash
        or review.target_snapshot_json != snapshot.target_snapshot
    ):
        raise LearningApplicationError("learning_review_stale")

    # The candidate row lock serializes same-review applications. Re-check the
    # immutable receipt after the lock so the second caller returns replay.
    existing = await session.scalar(
        select(LearningApplication).where(
            LearningApplication.review_id == review.id
        )
    )
    if existing is not None:
        return LearningApplicationResult(
            application=existing,
            replayed=True,
            resulting_target_id=existing.resulting_target_id,
            customer_map_snapshot_artifact_id=(
                existing.customer_map_snapshot_artifact_id
            ),
            change_report=existing.change_report_json,
        )

    if (
        review.decision == "NO_MAP_CHANGE"
        or snapshot.candidate.target_type == "no_map_change"
    ):
        application = LearningApplication(
            project_id=snapshot.candidate.project_id,
            learning_candidate_id=snapshot.candidate.id,
            candidate_version=snapshot.candidate.version,
            review_id=review.id,
            candidate_snapshot_hash=snapshot.snapshot_hash,
            target_type=snapshot.candidate.target_type,
            target_id=snapshot.candidate.target_id,
            resulting_target_id=None,
            applied_action="no_map_change",
            applied_signal_refs_json=[],
            frozen_scope_json=snapshot.candidate.scope_json,
            before_state_hash=None,
            after_state_hash=None,
            customer_map_snapshot_artifact_id=None,
            change_report_json=None,
            applied_by=actor,
            applied_at=utc_now(),
        )
        session.add(application)
        await session.flush()
        return LearningApplicationResult(
            application=application,
            replayed=False,
            resulting_target_id=None,
            customer_map_snapshot_artifact_id=None,
            change_report=None,
        )

    # Materialize a canonical pre-application snapshot in the same durable run.
    before_refresh = await refresh_customer_map_snapshot_artifact(
        session,
        run_id=snapshot.source_run_id,
        step_run_id=None,
    )
    before_hash = before_refresh.artifact.content_hash

    if snapshot.candidate.target_type == "need_hypothesis":
        action, resulting_target_id = await _apply_need(
            session,
            snapshot=snapshot,
        )
    elif snapshot.candidate.target_type == "customer_insight":
        action, resulting_target_id = await _apply_existing_insight(
            session,
            snapshot=snapshot,
        )
    elif snapshot.candidate.target_type == "new_customer_insight":
        action, resulting_target_id = await _apply_new_insight(
            session,
            snapshot=snapshot,
            applied_by=actor,
            review_reason=review.reason,
        )
    else:
        raise LearningApplicationError("learning_apply_target_type_invalid")

    after_refresh = await refresh_customer_map_snapshot_artifact(
        session,
        run_id=snapshot.source_run_id,
        step_run_id=None,
    )
    if snapshot.candidate.target_type == "need_hypothesis":
        applied_signal_refs = [
            {"signal_id": str(signal_id), "relation": relation}
            for signal_id, relation in snapshot.signal_links
            if relation in {"supports", "contradicts"}
        ]
    else:
        applied_signal_refs = [
            {"signal_id": str(signal_id), "relation": relation}
            for signal_id, relation in snapshot.signal_links
        ]
    application = LearningApplication(
        project_id=snapshot.candidate.project_id,
        learning_candidate_id=snapshot.candidate.id,
        candidate_version=snapshot.candidate.version,
        review_id=review.id,
        candidate_snapshot_hash=snapshot.snapshot_hash,
        target_type=snapshot.candidate.target_type,
        target_id=snapshot.candidate.target_id,
        resulting_target_id=resulting_target_id,
        applied_action=action,
        applied_signal_refs_json=applied_signal_refs,
        frozen_scope_json=snapshot.candidate.scope_json,
        before_state_hash=before_hash,
        after_state_hash=after_refresh.artifact.content_hash,
        customer_map_snapshot_artifact_id=after_refresh.artifact.id,
        change_report_json=after_refresh.change_report,
        applied_by=actor,
        applied_at=utc_now(),
    )
    session.add(application)
    await session.flush()
    return LearningApplicationResult(
        application=application,
        replayed=False,
        resulting_target_id=resulting_target_id,
        customer_map_snapshot_artifact_id=after_refresh.artifact.id,
        change_report=after_refresh.change_report,
    )


__all__ = [
    "CandidateReviewResult",
    "LearningApplicationError",
    "LearningApplicationResult",
    "ReviewDecision",
    "apply_learning_candidate",
    "review_learning_candidate",
]
