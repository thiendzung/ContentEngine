"""Canonical exception-driven Control Center read model.

UX-01A is read-only. It derives operator-facing state from existing durable
authorities and never creates approvals, artifacts, model/tool calls, research,
publication, or Customer Truth mutations.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.operator_control import OperatorControlError
from app.modules.content_engine.journal.operator_runtime import (
    resolve_next_operator_action,
)
from app.modules.content_engine.journal.operator_view import get_operator_case_view
from app.modules.content_engine.journal.production_board import (
    ProductionBoardCase,
    list_production_board_cases,
)
from app.modules.content_engine.models import Project
from app.modules.harness.models import Approval, Artifact, ContentRun
from app.modules.harness.persistence import get_latest_checkpoint
from app.modules.learning.models import (
    LearningCandidate,
    LearningCandidateReview,
    LearningResolution,
    LearningValidation,
)
from app.modules.learning.regression import (
    LearningRegressionError,
    validate_learning_resolution_readiness,
)


class ControlCenterError(ValueError):
    """Stable fail-closed Control Center error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ControlCenterCounts(BaseModel):
    running: int = 0
    queued: int = 0
    blocked: int = 0
    needs_human: int = 0
    completed_today: int = 0


class ControlCenterActionDestination(BaseModel):
    kind: str
    action_ref: str
    entity_id: str
    href: str | None = None


class NeedsMeItem(BaseModel):
    id: str
    type: Literal[
        "content_approval",
        "publish_authorization",
        "policy_gate",
        "learning_candidate_review",
        "learning_resolution",
    ]
    reason: str
    canonical_status: str
    created_at: datetime
    updated_at: datetime
    destination: ControlCenterActionDestination
    why_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class ControlCenterIssue(BaseModel):
    code: str
    entity_type: str
    entity_id: str
    message: str


class ControlCenterSummary(BaseModel):
    project_id: UUID
    project_slug: str
    as_of: datetime
    timezone: str
    counts: ControlCenterCounts
    issues: list[ControlCenterIssue] = Field(default_factory=list)


class ControlCenterSnapshot(BaseModel):
    summary: ControlCenterSummary
    needs_me: list[NeedsMeItem] = Field(default_factory=list)


async def resolve_project(
    session: AsyncSession,
    *,
    project_slug: str,
) -> Project:
    slug = project_slug.strip()
    if not slug:
        raise ControlCenterError("control_center_project_not_found")
    project = await session.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise ControlCenterError("control_center_project_not_found")
    return project


def _zone(name: str) -> ZoneInfo:
    normalized = name.strip()
    if not normalized:
        raise ControlCenterError("control_center_timezone_invalid")
    try:
        return ZoneInfo(normalized)
    except ZoneInfoNotFoundError as exc:
        raise ControlCenterError("control_center_timezone_invalid") from exc


def _local_day_bounds(
    *,
    as_of: datetime,
    timezone_name: str,
) -> tuple[datetime, datetime]:
    zone = _zone(timezone_name)
    aware = as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=UTC)
    local = aware.astimezone(zone)
    local_start = datetime.combine(local.date(), time.min, tzinfo=zone)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def _operator_href(board: ProductionBoardCase | None, case_id: UUID) -> str:
    if board is not None and board.operator_managed:
        return f"/operator/journal/{case_id}"
    return f"/?case={case_id}"


def _approval_kind(
    run: ContentRun,
    step_key: str,
) -> tuple[
    Literal["content_approval", "publish_authorization", "policy_gate"],
    str,
]:
    if run.run_mode == "publish" or step_key == "publish_authorization":
        return "publish_authorization", "Authorize external publication"
    if step_key in {
        "angle",
        "angle_generation",
        "outline",
        "journal_outline",
        "final_review",
    }:
        labels = {
            "angle": "Approve selected content angle",
            "angle_generation": "Approve selected content angle",
            "outline": "Approve content outline",
            "journal_outline": "Approve content outline",
            "final_review": "Approve final content",
        }
        return "content_approval", labels[step_key]
    return "policy_gate", f"Explicit human approval required for {step_key}"


def _validation_reason(status: str) -> str | None:
    if status == "VALIDATED":
        return "Later independent evidence is ready for a human promotion/keep decision."
    if status == "REGRESSED":
        return (
            "Later evidence indicates regression; "
            "a human rollback/reject/keep decision is required."
        )
    if status == "CONTESTED":
        return "Independent support and contradiction coexist; a human resolution is required."
    return None


def _signal_refs(rows: list[object]) -> list[str]:
    refs: list[str] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        value = raw.get("signal_id")
        if isinstance(value, str) and value:
            refs.append(f"signal:{value}")
    return sorted(set(refs))


def _operator_gate_reason(gate: str) -> str:
    labels = {
        "angle": "Approve selected content angle",
        "outline": "Approve content outline",
        "final_review": "Approve final content",
    }
    return labels.get(gate, f"Explicit human approval required for {gate}")


async def _pending_operator_items(
    session: AsyncSession,
    *,
    board: list[ProductionBoardCase],
) -> tuple[
    list[NeedsMeItem],
    list[ControlCenterIssue],
    set[UUID],
    set[UUID],
    dict[UUID, str],
]:
    items: list[NeedsMeItem] = []
    issues: list[ControlCenterIssue] = []
    blocked_cases: set[UUID] = set()
    gate_cases: set[UUID] = set()
    status_by_case: dict[UUID, str] = {}

    for row in board:
        if not row.operator_managed:
            continue
        try:
            action = await resolve_next_operator_action(
                session,
                content_case_id=row.id,
            )
        except OperatorControlError as exc:
            issues.append(
                ControlCenterIssue(
                    code=f"control_center_{exc.code}",
                    entity_type="content_case",
                    entity_id=str(row.id),
                    message=(
                        "Operator state is inconsistent; "
                        "no human action is exposed."
                    ),
                )
            )
            blocked_cases.add(row.id)
            status_by_case[row.id] = "BLOCKED"
            continue

        if action.status in {"BLOCKED", "NOT_READY"}:
            status_by_case[row.id] = "BLOCKED"
            blocked_cases.add(row.id)
        elif action.status == "RUNNING":
            status_by_case[row.id] = "RUNNING"
        elif action.status in {"QUEUED", "READY"}:
            status_by_case[row.id] = "QUEUED"
        elif action.status == "COMPLETE":
            status_by_case[row.id] = "COMPLETED"
        elif action.status == "AWAITING_APPROVAL":
            status_by_case[row.id] = "NEEDS_HUMAN"

        if action.status != "AWAITING_APPROVAL" or action.human_gate is None:
            if row.status_group == "AWAITING_APPROVAL":
                issues.append(
                    ControlCenterIssue(
                        code="control_center_operator_gate_missing",
                        entity_type="content_case",
                        entity_id=str(row.id),
                        message=(
                            "Production board expects a human gate but canonical "
                            "Operator Runtime does not expose one."
                        ),
                    )
                )
                blocked_cases.add(row.id)
                status_by_case[row.id] = "BLOCKED"
            continue

        gate = action.human_gate
        try:
            operator_view = await get_operator_case_view(
                session,
                content_case_id=row.id,
            )
        except OperatorControlError as exc:
            issues.append(
                ControlCenterIssue(
                    code=f"control_center_{exc.code}",
                    entity_type="content_case",
                    entity_id=str(row.id),
                    message=(
                        "Operator approval binding is stale or inconsistent; "
                        "no human action is exposed."
                    ),
                )
            )
            blocked_cases.add(row.id)
            status_by_case[row.id] = "BLOCKED"
            continue
        if (
            operator_view.state.state_version != action.state_version
            or operator_view.state.status != "AWAITING_APPROVAL"
            or operator_view.state.human_gate != gate
        ):
            issues.append(
                ControlCenterIssue(
                    code="control_center_operator_gate_stale",
                    entity_type="content_case",
                    entity_id=str(row.id),
                    message=(
                        "Operator approval projection changed during read; "
                        "no human action is exposed."
                    ),
                )
            )
            blocked_cases.add(row.id)
            status_by_case[row.id] = "BLOCKED"
            continue

        evidence_refs: list[str] = []
        pending_gate = operator_view.pending_gate
        if gate in {"angle", "outline"}:
            if pending_gate is None or pending_gate.type != gate:
                issues.append(
                    ControlCenterIssue(
                        code="control_center_operator_gate_binding_missing",
                        entity_type="content_case",
                        entity_id=str(row.id),
                        message=(
                            "Operator gate has no exact pending artifact binding; "
                            "no human action is exposed."
                        ),
                    )
                )
                blocked_cases.add(row.id)
                continue
            evidence_refs.append(
                f"artifact:{pending_gate.artifact.id}:"
                f"{pending_gate.artifact.content_hash}"
            )
        elif gate == "final_review":
            for lane in operator_view.quality_lanes:
                if not lane.pending_approval_ready or lane.final_content is None:
                    continue
                if lane.final_content.id is None or lane.final_content.content_hash is None:
                    continue
                evidence_refs.append(
                    f"artifact:{lane.final_content.id}:"
                    f"{lane.final_content.content_hash}"
                )
            if not evidence_refs:
                issues.append(
                    ControlCenterIssue(
                        code="control_center_operator_final_binding_missing",
                        entity_type="content_case",
                        entity_id=str(row.id),
                        message=(
                            "Final review gate has no exact final-content binding; "
                            "no human action is exposed."
                        ),
                    )
                )
                blocked_cases.add(row.id)
                status_by_case[row.id] = "BLOCKED"
                continue

        gate_cases.add(row.id)
        why_refs = [
            f"operator_state:{action.state_version}",
            f"content_case:{row.id}",
        ]
        if action.current_run_id is not None:
            why_refs.append(f"run:{action.current_run_id}")
        if action.current_step_run_id is not None:
            why_refs.append(f"step_run:{action.current_step_run_id}")
        items.append(
            NeedsMeItem(
                id=f"operator-gate:{row.id}:{gate}:{action.state_version}",
                type="content_approval",
                reason=_operator_gate_reason(gate),
                canonical_status="AWAITING_APPROVAL",
                created_at=row.updated_at,
                updated_at=row.updated_at,
                destination=ControlCenterActionDestination(
                    kind="content_approval",
                    action_ref=(
                        f"operator_decision:{row.id}:{gate}:"
                        f"{action.state_version}"
                    ),
                    entity_id=str(row.id),
                    href=f"/operator/journal/{row.id}",
                ),
                why_refs=why_refs,
                evidence_refs=sorted(set(evidence_refs)),
            )
        )

    return items, issues, blocked_cases, gate_cases, status_by_case


async def _pending_harness_items(
    session: AsyncSession,
    *,
    project_id: UUID,
    board_by_case: dict[UUID, ProductionBoardCase],
) -> tuple[
    list[NeedsMeItem],
    list[ControlCenterIssue],
    set[UUID],
    set[UUID],
]:
    runs = list(
        (
            await session.scalars(
                select(ContentRun)
                .where(
                    ContentRun.project_id == project_id,
                    ContentRun.status == "waiting_approval",
                )
                .order_by(ContentRun.created_at, ContentRun.id)
            )
        ).all()
    )
    items: list[NeedsMeItem] = []
    issues: list[ControlCenterIssue] = []
    blocked_cases: set[UUID] = set()
    human_cases: set[UUID] = set()

    for run in runs:
        board = board_by_case.get(run.content_case_id)
        is_publish_gate = (
            run.run_mode == "publish"
            or run.current_step == "publish_authorization"
        )

        # Journal operator state is authoritative for editorial gates. Generic
        # Harness approval rows on those cases are only used for the separate
        # publish authorization.
        if (
            not is_publish_gate
            and board is not None
            and board.operator_managed
        ):
            continue

        # A ContentCase may retain historical waiting_approval runs after a
        # later gate becomes canonical. Only the gate selected by the current
        # production-board projection is actionable; superseded runs are not
        # errors and must not create false BLOCKED work.
        if not is_publish_gate and board is not None:
            if board.status_group != "AWAITING_APPROVAL":
                continue
            if run.current_step is not None and run.current_step != board.stage_key:
                continue

        checkpoint = await get_latest_checkpoint(session, run_id=run.id)
        payload = checkpoint.content_json if checkpoint is not None else None
        pending = payload.get("pending_approval") if isinstance(payload, dict) else None
        if not isinstance(pending, dict):
            issues.append(
                ControlCenterIssue(
                    code="control_center_pending_approval_missing",
                    entity_type="content_run",
                    entity_id=str(run.id),
                    message=(
                        "Run is waiting for approval but has no canonical "
                        "pending-approval checkpoint."
                    ),
                )
            )
            blocked_cases.add(run.content_case_id)
            continue

        step_key = pending.get("step_key")
        artifact_id_raw = pending.get("artifact_id")
        if not isinstance(step_key, str) or not step_key.strip() or not isinstance(
            artifact_id_raw, str
        ):
            issues.append(
                ControlCenterIssue(
                    code="control_center_pending_approval_invalid",
                    entity_type="content_run",
                    entity_id=str(run.id),
                    message="Pending approval checkpoint is malformed.",
                )
            )
            blocked_cases.add(run.content_case_id)
            continue
        try:
            artifact_id = UUID(artifact_id_raw)
        except ValueError:
            issues.append(
                ControlCenterIssue(
                    code="control_center_pending_approval_invalid",
                    entity_type="content_run",
                    entity_id=str(run.id),
                    message="Pending approval artifact identity is invalid.",
                )
            )
            blocked_cases.add(run.content_case_id)
            continue

        artifact = await session.get(Artifact, artifact_id)
        if artifact is None or artifact.run_id != run.id:
            issues.append(
                ControlCenterIssue(
                    code="control_center_pending_approval_artifact_invalid",
                    entity_type="content_run",
                    entity_id=str(run.id),
                    message="Pending approval artifact is missing or belongs to another run.",
                )
            )
            blocked_cases.add(run.content_case_id)
            continue
        latest = await session.scalar(
            select(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.artifact_type == artifact.artifact_type,
            )
            .order_by(Artifact.version.desc(), Artifact.id.desc())
            .limit(1)
        )
        approvals = list(
            (
                await session.scalars(
                    select(Approval).where(
                        Approval.run_id == run.id,
                        Approval.step_key == step_key,
                        Approval.artifact_id == artifact.id,
                    )
                )
            ).all()
        )
        if (
            latest is None
            or latest.id != artifact.id
            or approvals
            or (run.current_step is not None and run.current_step != step_key)
        ):
            issues.append(
                ControlCenterIssue(
                    code="control_center_pending_approval_stale",
                    entity_type="content_run",
                    entity_id=str(run.id),
                    message=(
                        "Waiting approval state is stale or inconsistent; "
                        "no action is exposed."
                    ),
                )
            )
            blocked_cases.add(run.content_case_id)
            continue

        item_type, reason = _approval_kind(run, step_key)
        if (
            item_type == "content_approval"
            and board is not None
            and step_key != board.stage_key
        ):
            continue
        checkpoint_ref = (
            f"artifact:{checkpoint.id}" if checkpoint is not None else f"run:{run.id}"
        )
        human_cases.add(run.content_case_id)
        items.append(
            NeedsMeItem(
                id=f"approval:{run.id}:{step_key}:{artifact.id}",
                type=item_type,
                reason=reason,
                canonical_status="WAITING_APPROVAL",
                created_at=checkpoint.created_at if checkpoint is not None else run.created_at,
                updated_at=run.updated_at,
                destination=ControlCenterActionDestination(
                    kind=item_type,
                    action_ref=f"approval:{run.id}:{step_key}:{artifact.id}",
                    entity_id=str(run.content_case_id),
                    href=_operator_href(board, run.content_case_id),
                ),
                why_refs=[
                    f"run:{run.id}",
                    checkpoint_ref,
                    f"artifact:{artifact.id}",
                ],
                evidence_refs=[f"artifact:{artifact.id}:{artifact.content_hash}"],
            )
        )

    for case_id, board in board_by_case.items():
        if board.operator_managed or board.status_group != "AWAITING_APPROVAL":
            continue
        if case_id in human_cases or case_id in blocked_cases:
            continue
        issues.append(
            ControlCenterIssue(
                code="control_center_canonical_gate_missing",
                entity_type="content_case",
                entity_id=str(case_id),
                message=(
                    "Canonical production state expects a human gate but no "
                    "matching durable approval binding exists."
                ),
            )
        )
        blocked_cases.add(case_id)

    return items, issues, blocked_cases, human_cases


async def _pending_learning_items(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> tuple[list[NeedsMeItem], list[ControlCenterIssue]]:
    items: list[NeedsMeItem] = []
    issues: list[ControlCenterIssue] = []

    candidates = list(
        (
            await session.scalars(
                select(LearningCandidate)
                .where(
                    LearningCandidate.project_id == project_id,
                    LearningCandidate.status == "OPEN",
                    LearningCandidate.evidence_status == "READY_FOR_REVIEW",
                )
                .order_by(LearningCandidate.created_at, LearningCandidate.id)
            )
        ).all()
    )
    candidate_ids = [row.id for row in candidates]
    reviewed_candidate_ids: set[UUID] = set()
    if candidate_ids:
        reviewed_candidate_ids = set(
            (
                await session.scalars(
                    select(LearningCandidateReview.learning_candidate_id).where(
                        LearningCandidateReview.learning_candidate_id.in_(candidate_ids)
                    )
                )
            ).all()
        )
    for candidate in candidates:
        if candidate.id in reviewed_candidate_ids:
            continue
        evidence_refs = [f"artifact:{candidate.source_assessment_artifact_id}"]
        if candidate.target_id is not None:
            evidence_refs.append(f"{candidate.target_type}:{candidate.target_id}")
        items.append(
            NeedsMeItem(
                id=f"learning-candidate:{candidate.id}:v{candidate.version}",
                type="learning_candidate_review",
                reason=(
                    "Learning candidate reached reviewed-evidence readiness "
                    "and requires a human decision."
                ),
                canonical_status="READY_FOR_REVIEW",
                created_at=candidate.created_at,
                updated_at=candidate.updated_at,
                destination=ControlCenterActionDestination(
                    kind="learning_candidate_review",
                    action_ref=f"learning_candidate:{candidate.id}:v{candidate.version}",
                    entity_id=str(candidate.id),
                    href=None,
                ),
                why_refs=[
                    f"learning_candidate:{candidate.id}:v{candidate.version}",
                    f"evidence_status:{candidate.evidence_status}",
                ],
                evidence_refs=evidence_refs,
            )
        )

    validations = list(
        (
            await session.scalars(
                select(LearningValidation)
                .where(LearningValidation.project_id == project_id)
                .order_by(
                    LearningValidation.learning_application_id,
                    LearningValidation.version.desc(),
                    LearningValidation.id.desc(),
                )
            )
        ).all()
    )
    latest: list[LearningValidation] = []
    seen_applications: set[UUID] = set()
    for validation in validations:
        if validation.learning_application_id in seen_applications:
            continue
        seen_applications.add(validation.learning_application_id)
        latest.append(validation)

    validation_ids = [row.id for row in latest]
    resolved_ids: set[UUID] = set()
    if validation_ids:
        resolved_ids = set(
            (
                await session.scalars(
                    select(LearningResolution.learning_validation_id).where(
                        LearningResolution.learning_validation_id.in_(validation_ids)
                    )
                )
            ).all()
        )

    for validation in latest:
        if validation.id in resolved_ids:
            continue
        reason = _validation_reason(validation.validation_status)
        if reason is None:
            continue
        try:
            await validate_learning_resolution_readiness(
                session,
                learning_validation_id=validation.id,
            )
        except LearningRegressionError as exc:
            issues.append(
                ControlCenterIssue(
                    code=f"control_center_{exc.code}",
                    entity_type="learning_validation",
                    entity_id=str(validation.id),
                    message=(
                        "Learning validation is stale or inconsistent; "
                        "no human action is exposed."
                    ),
                )
            )
            continue
        items.append(
            NeedsMeItem(
                id=f"learning-validation:{validation.id}:v{validation.version}",
                type="learning_resolution",
                reason=reason,
                canonical_status=validation.validation_status,
                created_at=validation.created_at,
                updated_at=validation.updated_at,
                destination=ControlCenterActionDestination(
                    kind="learning_resolution",
                    action_ref=f"learning_validation:{validation.id}:v{validation.version}",
                    entity_id=str(validation.id),
                    href=None,
                ),
                why_refs=[
                    f"learning_validation:{validation.id}:v{validation.version}",
                    f"learning_application:{validation.learning_application_id}",
                    f"validation_status:{validation.validation_status}",
                ],
                evidence_refs=(
                    _signal_refs(validation.baseline_signal_refs_json)
                    + _signal_refs(validation.validation_signal_refs_json)
                ),
            )
        )
    return items, issues


async def build_control_center(
    session: AsyncSession,
    *,
    project_slug: str,
    timezone_name: str,
    as_of: datetime | None = None,
) -> ControlCenterSnapshot:
    project = await resolve_project(session, project_slug=project_slug)
    now = as_of or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    zone = _zone(timezone_name)
    day_start, day_end = _local_day_bounds(
        as_of=now,
        timezone_name=zone.key,
    )

    board = await list_production_board_cases(session, project_id=project.id)
    board_by_case = {row.id: row for row in board}

    (
        operator_items,
        operator_issues,
        operator_blocked_cases,
        operator_gate_cases,
        operator_status_by_case,
    ) = await _pending_operator_items(
        session,
        board=board,
    )
    (
        harness_items,
        issues,
        approval_blocked_cases,
        harness_human_case_ids,
    ) = await _pending_harness_items(
        session,
        project_id=project.id,
        board_by_case=board_by_case,
    )
    issues = operator_issues + issues
    human_case_ids = operator_gate_cases | harness_human_case_ids
    learning_items, learning_issues = await _pending_learning_items(
        session,
        project_id=project.id,
    )
    issues.extend(learning_issues)
    needs_me = sorted(
        operator_items + harness_items + learning_items,
        key=lambda row: (row.created_at, row.id),
    )

    completed_runs = list(
        (
            await session.scalars(
                select(ContentRun)
                .where(
                    ContentRun.project_id == project.id,
                    ContentRun.status == "completed",
                    ContentRun.completed_at.is_not(None),
                )
                .order_by(ContentRun.completed_at, ContentRun.id)
            )
        ).all()
    )
    latest_completed_at: dict[UUID, datetime] = {}
    for run in completed_runs:
        if run.completed_at is not None:
            latest_completed_at[run.content_case_id] = run.completed_at
    completed_case_ids = {
        case_id
        for case_id, completed_at in latest_completed_at.items()
        if day_start <= completed_at < day_end
    }

    blocked_case_ids = (
        {
            row.id
            for row in board
            if not row.operator_managed and row.status_group == "BLOCKED"
        }
        | operator_blocked_cases
        | approval_blocked_cases
    )

    def operational_group(row: ProductionBoardCase) -> str:
        if row.id in blocked_case_ids:
            return "BLOCKED"
        if row.id in human_case_ids:
            return "NEEDS_HUMAN"
        if row.operator_managed:
            return operator_status_by_case.get(row.id, "BLOCKED")
        return row.status_group

    counts = ControlCenterCounts(
        running=sum(
            1 for row in board if operational_group(row) == "RUNNING"
        ),
        queued=sum(
            1 for row in board if operational_group(row) == "QUEUED"
        ),
        blocked=sum(
            1 for row in board if operational_group(row) == "BLOCKED"
        ),
        needs_human=len(needs_me),
        completed_today=sum(
            1
            for row in board
            if operational_group(row) == "COMPLETED"
            and row.id in completed_case_ids
        ),
    )
    return ControlCenterSnapshot(
        summary=ControlCenterSummary(
            project_id=project.id,
            project_slug=project.slug,
            as_of=now,
            timezone=zone.key,
            counts=counts,
            issues=issues,
        ),
        needs_me=needs_me,
    )


__all__ = [
    "ControlCenterActionDestination",
    "ControlCenterCounts",
    "ControlCenterError",
    "ControlCenterIssue",
    "ControlCenterSnapshot",
    "ControlCenterSummary",
    "NeedsMeItem",
    "build_control_center",
    "resolve_project",
]