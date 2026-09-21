"""F4 bilingual quality orchestration over the existing Journal primitives.

This module is deliberately a small adapter.  Review/revise, Assertion Audit and
Source-copy continue to own their generation, validation and persistence contracts;
the adapter only binds their exact inputs to the two independent locale lanes.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.assertion_audit import load_assertion_audit_input
from app.modules.content_engine.journal.assertion_audit_agent_bridge import (
    assertion_audit_registry_config,
)
from app.modules.content_engine.journal.assertion_audit_execution import (
    prepare_assertion_audit_run,
)
from app.modules.content_engine.journal.models import OperatorCommand
from app.modules.content_engine.journal.operator_control import (
    OperatorCommandResult,
    OperatorControlError,
    OperatorIntent,
)
from app.modules.content_engine.journal.operator_locking import lock_operator_idempotency
from app.modules.content_engine.journal.operator_writers import (
    WriterLane,
    WriterLaneProgress,
    get_writer_lane_progress,
)
from app.modules.content_engine.journal.quality_readiness import (
    READER_VALUE_TASK_KEYS,
    READINESS_ARTIFACT_TYPES,
    READINESS_HANDOFF_TYPES,
    SEARCH_AI_TASK_KEYS,
    QualityReadinessInput,
    ensure_quality_readiness_run,
    load_quality_readiness_input,
)
from app.modules.content_engine.journal.review_revise import load_review_revise_input
from app.modules.content_engine.journal.review_revise_agent_bridge import (
    review_revise_registry_config,
)
from app.modules.content_engine.journal.source_copy import (
    SOURCE_COPY_TASK_KEYS,
    SourceCopyInput,
    ensure_source_copy_run,
    load_source_copy_input,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    LocaleVariant,
    SettingsSnapshot,
)
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    Job,
    QualityEvaluation,
    StepRun,
    utc_now,
)
from app.modules.harness.persistence import (
    enqueue_job,
    get_latest_checkpoint,
    pause_for_approval,
    transition_run,
    transition_step_run,
)
from app.modules.harness.runtime import SettingsModelRouter
from app.modules.system.settings_service import active_prompt_definition, active_recipe_definition

QUALITY_LOCALES = ("vi-VN", "en")
# The task keys are part of the approved registry contract and must remain exact.
QUALITY_REVIEW_TASK_KEYS = {"vi-VN": "review_revise_vi", "en": "review_revise_en"}
QUALITY_AUDIT_TASK_KEYS = {"vi-VN": "assertion_audit_vi", "en": "assertion_audit_en"}
QUALITY_MAX_JOB_ATTEMPTS = 2
_QUALITY_INTEGRITY_FAILURE_MARKERS = (
    "stale",
    "snapshot",
    "mismatch",
    "conflict",
    "not_pass",
    "content_invalid",
)


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _ref(artifact: Artifact | None) -> dict[str, object] | None:
    if artifact is None:
        return None
    return {
        "id": str(artifact.id),
        "version": artifact.version,
        "content_hash": artifact.content_hash,
    }


def _job_payload(job: Job | None) -> dict[str, object] | None:
    if job is None:
        return None
    return {"id": str(job.id), "status": job.status, "attempt": job.attempt}


def _latest_job(jobs: tuple[Job, ...]) -> Job | None:
    return jobs[-1] if jobs else None


def _stage_has_integrity_failure(stage: QualityStage) -> bool:
    job = stage.job
    if job is None or job.status not in {"failed", "cancelled"}:
        return False
    code = stage.run.failure_code if stage.run is not None else None
    if code is None and stage.step is not None and isinstance(stage.step.error_json, dict):
        raw_code = stage.step.error_json.get("class")
        code = raw_code if isinstance(raw_code, str) else None
    return code is not None and any(marker in code for marker in _QUALITY_INTEGRITY_FAILURE_MARKERS)


@dataclass(frozen=True, slots=True)
class QualityStage:
    run: ContentRun | None = None
    handoff: Artifact | None = None
    step: StepRun | None = None
    jobs: tuple[Job, ...] = ()
    artifact: Artifact | None = None
    evaluation: QualityEvaluation | None = None
    attempt: int = 1

    @property
    def job(self) -> Job | None:
        return _latest_job(self.jobs)


@dataclass(frozen=True, slots=True)
class QualityLane:
    locale: str
    variant: LocaleVariant
    writer: WriterLane
    review: QualityStage
    audit: QualityStage
    source_copy: QualityStage
    reader_value: QualityStage
    search_ai: QualityStage
    final_item: ContentItem | None = None
    final_content: Artifact | None = None
    final_review: StepRun | None = None
    checkpoint: Artifact | None = None

    @property
    def source_draft(self) -> Artifact | None:
        return self.writer.draft

    @property
    def revised_draft(self) -> Artifact | None:
        return self.review.artifact

    @property
    def status(self) -> str:
        review_job = self.review.job
        if (
            self.final_content is not None
            and self.final_review is not None
            and _pending_checkpoint(self.checkpoint)
            == {"step_key": "final_review", "artifact_id": str(self.final_content.id)}
        ):
            return "final_gate_ready"
        search_eval = self.search_ai.evaluation
        if search_eval is not None:
            return "quality_blocked" if search_eval.result == "fail" else "qualified"
        search_job = self.search_ai.job
        if search_job is not None and search_job.status in {"queued", "leased"}:
            return "search_ai_running" if search_job.status == "leased" else "search_ai_queued"
        if (
            (search_job is not None and search_job.status in {"failed", "cancelled"})
            or (
                self.search_ai.run is not None
                and self.search_ai.run.status in {"failed", "cancelled"}
            )
        ):
            if _stage_has_integrity_failure(self.search_ai):
                return "quality_blocked"
            is_exhausted = (
                self.search_ai.attempt >= QUALITY_MAX_JOB_ATTEMPTS
                or (search_job is not None and search_job.attempt >= QUALITY_MAX_JOB_ATTEMPTS)
                or (
                    self.search_ai.run is not None
                    and self.search_ai.run.failure_code == "operator_quality_retry_exhausted"
                )
            )
            return "execution_failed_exhausted" if is_exhausted else "execution_failed_retryable"

        reader_eval = self.reader_value.evaluation
        if reader_eval is not None:
            if reader_eval.result == "fail":
                return "quality_blocked"
            return "reader_value_ready" if self.search_ai.run is None else "search_ai_queued"
        reader_job = self.reader_value.job
        if reader_job is not None and reader_job.status in {"queued", "leased"}:
            return (
                "reader_value_running"
                if reader_job.status == "leased"
                else "reader_value_queued"
            )
        if (
            (reader_job is not None and reader_job.status in {"failed", "cancelled"})
            or (
                self.reader_value.run is not None
                and self.reader_value.run.status in {"failed", "cancelled"}
            )
        ):
            if _stage_has_integrity_failure(self.reader_value):
                return "quality_blocked"
            is_exhausted = (
                self.reader_value.attempt >= QUALITY_MAX_JOB_ATTEMPTS
                or (reader_job is not None and reader_job.attempt >= QUALITY_MAX_JOB_ATTEMPTS)
                or (
                    self.reader_value.run is not None
                    and self.reader_value.run.failure_code == "operator_quality_retry_exhausted"
                )
            )
            return "execution_failed_exhausted" if is_exhausted else "execution_failed_retryable"

        if self.source_copy.evaluation is not None:
            result = self.source_copy.evaluation.result
            findings = self.source_copy.evaluation.findings_json
            fail_count = findings.get("fail_count", 0) if isinstance(findings, dict) else 0
            if result == "fail" or fail_count:
                return "quality_blocked"
            return "source_copy_ready"
        source_job = self.source_copy.job
        if source_job is not None and source_job.status in {"queued", "leased"}:
            return "source_copy_running" if source_job.status == "leased" else "source_copy_queued"
        if (
            (source_job is not None and source_job.status in {"failed", "cancelled"})
            or (
                self.source_copy.run is not None
                and self.source_copy.run.status in {"failed", "cancelled"}
            )
        ):
            if _stage_has_integrity_failure(self.source_copy):
                return "quality_blocked"
            is_exhausted = (
                self.source_copy.attempt >= QUALITY_MAX_JOB_ATTEMPTS
                or (source_job is not None and source_job.attempt >= QUALITY_MAX_JOB_ATTEMPTS)
                or (
                    self.source_copy.run is not None
                    and self.source_copy.run.failure_code == "operator_quality_retry_exhausted"
                )
            )
            return (
                "execution_failed_exhausted"
                if is_exhausted
                else "execution_failed_retryable"
            )
        audit_eval = self.audit.evaluation
        if audit_eval is not None:
            findings = audit_eval.findings_json
            critical_unsupported = findings.get("critical_unsupported_count", 0)
            critical_contradicted = findings.get("critical_contradicted_count", 0)
            if audit_eval.result == "fail" or critical_unsupported or critical_contradicted:
                return "quality_blocked"
            return "audit_running" if self.source_copy.run is None else "source_copy_queued"
        audit_job = self.audit.job
        if audit_job is not None and audit_job.status in {"queued", "leased"}:
            return "audit_running" if audit_job.status == "leased" else "audit_queued"
        if (
            (audit_job is not None and audit_job.status in {"failed", "cancelled"})
            or (
                self.audit.run is not None
                and self.audit.run.status in {"failed", "cancelled"}
            )
        ):
            if _stage_has_integrity_failure(self.audit):
                return "quality_blocked"
            is_exhausted = (
                self.audit.attempt >= QUALITY_MAX_JOB_ATTEMPTS
                or (audit_job is not None and audit_job.attempt >= QUALITY_MAX_JOB_ATTEMPTS)
                or (
                    self.audit.run is not None
                    and self.audit.run.failure_code == "operator_quality_retry_exhausted"
                )
            )
            return (
                "execution_failed_exhausted"
                if is_exhausted
                else "execution_failed_retryable"
            )
        if review_job is not None and review_job.status in {"queued", "leased"}:
            return "review_running" if review_job.status == "leased" else "review_queued"
        if review_job is not None and review_job.status in {"failed", "cancelled"}:
            if _stage_has_integrity_failure(self.review):
                return "quality_blocked"
            review_attempt = (
                self.review.attempt
                if self.review.step is not None
                else review_job.attempt
            )
            is_exhausted = (
                review_attempt >= QUALITY_MAX_JOB_ATTEMPTS
                or review_job.attempt >= QUALITY_MAX_JOB_ATTEMPTS
                or (
                    self.writer.run is not None
                    and self.writer.run.failure_code == "operator_quality_retry_exhausted"
                )
            )
            return (
                "execution_failed_exhausted"
                if is_exhausted
                else "execution_failed_retryable"
            )
        return "not_dispatched"


@dataclass(frozen=True, slots=True)
class QualityProgress:
    content_case_id: UUID
    writer_progress: WriterLaneProgress
    lanes: tuple[QualityLane, ...]

    @property
    def dispatched(self) -> bool:
        return any(
            lane.review.step is not None
            or lane.audit.run is not None
            or lane.source_copy.run is not None
            or lane.reader_value.run is not None
            or lane.search_ai.run is not None
            or lane.final_content is not None
            for lane in self.lanes
        )

    @property
    def all_qualified(self) -> bool:
        return bool(self.lanes) and all(
            lane.status in {"qualified", "final_gate_ready"} for lane in self.lanes
        )

    @property
    def final_gate_ready(self) -> bool:
        return bool(self.lanes) and all(lane.status == "final_gate_ready" for lane in self.lanes)

    @property
    def has_active_job(self) -> bool:
        return any(
            stage.job is not None and stage.job.status in {"queued", "leased"}
            for lane in self.lanes
            for stage in (
                lane.review,
                lane.audit,
                lane.source_copy,
                lane.reader_value,
                lane.search_ai,
            )
        )

    @property
    def has_content_block(self) -> bool:
        return any(lane.status == "quality_blocked" for lane in self.lanes)

    @property
    def has_exhausted_failure(self) -> bool:
        return any(lane.status == "execution_failed_exhausted" for lane in self.lanes)

    @property
    def has_retryable_failure(self) -> bool:
        return any(lane.status == "execution_failed_retryable" for lane in self.lanes)

    @property
    def version_payload(self) -> dict[str, object]:
        return {
            "source_run_id": str(self.writer_progress.source_run.id),
            "outline": _ref(self.writer_progress.outline_artifact),
            "lanes": [
                {
                    "locale": lane.locale,
                    "variant_id": str(lane.variant.id),
                    "writer_run_id": str(lane.writer.run.id) if lane.writer.run else None,
                    "writer_source": _ref(lane.source_draft),
                    "review": {
                        "step": _step_payload(lane.review.step),
                        "jobs": [_job_payload(job) for job in lane.review.jobs],
                        "revised": _ref(lane.revised_draft),
                    },
                    "audit": {
                        "run_id": str(lane.audit.run.id) if lane.audit.run else None,
                        "handoff": _ref(lane.audit.handoff),
                        "step": _step_payload(lane.audit.step),
                        "jobs": [_job_payload(job) for job in lane.audit.jobs],
                        "artifact": _ref(lane.audit.artifact),
                        "evaluation": _evaluation_payload(lane.audit.evaluation),
                    },
                    "source_copy": {
                        "run_id": str(lane.source_copy.run.id) if lane.source_copy.run else None,
                        "handoff": _ref(lane.source_copy.handoff),
                        "step": _step_payload(lane.source_copy.step),
                        "jobs": [_job_payload(job) for job in lane.source_copy.jobs],
                        "artifact": _ref(lane.source_copy.artifact),
                        "evaluation": _evaluation_payload(lane.source_copy.evaluation),
                    },
                    "reader_value": {
                        "run_id": str(lane.reader_value.run.id) if lane.reader_value.run else None,
                        "handoff": _ref(lane.reader_value.handoff),
                        "step": _step_payload(lane.reader_value.step),
                        "jobs": [_job_payload(job) for job in lane.reader_value.jobs],
                        "artifact": _ref(lane.reader_value.artifact),
                        "evaluation": _evaluation_payload(lane.reader_value.evaluation),
                    },
                    "search_ai": {
                        "run_id": str(lane.search_ai.run.id) if lane.search_ai.run else None,
                        "handoff": _ref(lane.search_ai.handoff),
                        "step": _step_payload(lane.search_ai.step),
                        "jobs": [_job_payload(job) for job in lane.search_ai.jobs],
                        "artifact": _ref(lane.search_ai.artifact),
                        "evaluation": _evaluation_payload(lane.search_ai.evaluation),
                    },
                    "final": {
                        "content_item_id": str(lane.final_item.id) if lane.final_item else None,
                        "artifact": _ref(lane.final_content),
                        "step": _step_payload(lane.final_review),
                        "checkpoint": _pending_checkpoint(lane.checkpoint),
                    },
                }
                for lane in self.lanes
            ],
        }

    @property
    def state_version(self) -> str:
        return _sha(self.version_payload)


def _step_payload(step: StepRun | None) -> dict[str, object] | None:
    if step is None:
        return None
    return {
        "id": str(step.id),
        "step_key": step.step_key,
        "attempt": step.attempt,
        "status": step.status,
        "inputs": list(step.input_artifact_refs_json),
        "outputs": list(step.output_artifact_refs_json),
        "error": step.error_json,
    }


def _evaluation_payload(evaluation: QualityEvaluation | None) -> dict[str, object] | None:
    if evaluation is None:
        return None
    return {
        "id": str(evaluation.id),
        "result": evaluation.result,
        "evaluator_key": evaluation.evaluator_key,
        "evaluator_version": evaluation.evaluator_version,
        "findings": evaluation.findings_json,
    }


def _pending_checkpoint(checkpoint: Artifact | None) -> object:
    if checkpoint is None or not isinstance(checkpoint.content_json, dict):
        return None
    return checkpoint.content_json.get("pending_approval")


def _payload_id(payload: object, key: str) -> str | None:
    if not isinstance(payload, dict) or not isinstance(payload.get(key), str):
        return None
    return cast(str, payload.get(key))


def _payload_ref(payload: object, key: str) -> dict[str, object] | None:
    value = payload.get(key) if isinstance(payload, dict) else None
    return cast(dict[str, object], value) if isinstance(value, dict) else None


async def _stage_for_handoff(
    session: AsyncSession,
    *,
    handoff_type: str,
    locale: str,
    writer: WriterLane,
    source_draft: Artifact | None,
    task_key: str,
    audit_artifact: Artifact | None = None,
    audit_evaluation: QualityEvaluation | None = None,
    source_copy_artifact: Artifact | None = None,
    source_copy_evaluation: QualityEvaluation | None = None,
    reader_value_artifact: Artifact | None = None,
    reader_value_evaluation: QualityEvaluation | None = None,
) -> QualityStage:
    if writer.run is None or source_draft is None:
        return QualityStage()
    rows = list(
        (
            await session.scalars(
                select(Artifact)
                .where(
                    Artifact.artifact_type == handoff_type,
                    Artifact.locale == locale,
                )
                .order_by(Artifact.created_at, Artifact.id)
            )
        ).all()
    )
    matches: list[tuple[Artifact, ContentRun]] = []
    for handoff in rows:
        payload = handoff.content_json
        if not isinstance(payload, dict):
            continue
        if payload.get("task_key") != task_key:
            continue
        if handoff_type == "assertion_audit_handoff":
            source_run_ref = _payload_ref(payload, "source_writer_run")
            source_ref = _payload_ref(payload, "source_draft")
            matches_source = (
                source_run_ref is not None
                and source_run_ref.get("id") == str(writer.run.id)
                and source_ref is not None
                and source_ref == _ref(source_draft)
            )
        elif handoff_type == "source_copy_handoff":
            if audit_artifact is None or audit_evaluation is None:
                matches_source = False
            else:
                source_run_ref_text = _payload_id(payload, "source_writer_run_id")
                source_ref = _payload_ref(payload, "source_draft")
                audit_payload = payload.get("assertion_audit")
                audit_ref = (
                    audit_payload.get("artifact") if isinstance(audit_payload, dict) else None
                )
                audit_eval_id = (
                    audit_payload.get("quality_evaluation_id")
                    if isinstance(audit_payload, dict)
                    else None
                )
                matches_source = (
                    source_run_ref_text == str(writer.run.id)
                    and source_ref is not None
                    and source_ref == _ref(source_draft)
                    and isinstance(audit_ref, dict)
                    and audit_ref == _ref(audit_artifact)
                    and audit_eval_id == str(audit_evaluation.id)
                )
        else:
            source_run_ref_text = _payload_id(payload, "source_writer_run_id")
            source_ref = _payload_ref(payload, "source_draft")
            source_copy_payload = payload.get("source_copy")
            source_copy_ref = (
                source_copy_payload.get("artifact")
                if isinstance(source_copy_payload, dict)
                else None
            )
            source_copy_eval_ref = (
                source_copy_payload.get("quality_evaluation")
                if isinstance(source_copy_payload, dict)
                else None
            )
            matches_source = (
                source_run_ref_text == str(writer.run.id)
                and source_ref is not None
                and source_ref == _ref(source_draft)
                and source_copy_artifact is not None
                and source_copy_evaluation is not None
                and source_copy_ref == _ref(source_copy_artifact)
                and isinstance(source_copy_eval_ref, dict)
                and source_copy_eval_ref.get("id") == str(source_copy_evaluation.id)
            )
            if matches_source and handoff_type == READINESS_HANDOFF_TYPES["search_ai"]:
                reader_payload = payload.get("reader_value")
                reader_ref = (
                    reader_payload.get("artifact")
                    if isinstance(reader_payload, dict)
                    else None
                )
                reader_eval_ref = (
                    reader_payload.get("quality_evaluation")
                    if isinstance(reader_payload, dict)
                    else None
                )
                matches_source = (
                    reader_value_artifact is not None
                    and reader_value_evaluation is not None
                    and reader_ref == _ref(reader_value_artifact)
                    and isinstance(reader_eval_ref, dict)
                    and reader_eval_ref.get("id") == str(reader_value_evaluation.id)
                )
        if not matches_source:
            continue
        run = await session.get(ContentRun, handoff.run_id)
        if run is None or run.content_case_id != writer.run.content_case_id:
            raise OperatorControlError("operator_quality_handoff_run_mismatch")
        matches.append((handoff, run))
    active = [
        (handoff, run) for handoff, run in matches if run.status not in {"failed", "cancelled"}
    ]
    if len(active) > 1:
        raise OperatorControlError("operator_quality_active_run_conflict", locale)
    if active:
        selected = active[0]
    elif matches:
        # Keep the latest terminal run visible so the resolver can distinguish a
        # retryable technical failure from an absent stage. A replacement
        # active run, when present, always wins above.
        terminal_matches = sorted(
            matches,
            key=lambda item: (item[1].created_at, item[1].id),
        )
        selected = terminal_matches[-1]
    else:
        return QualityStage()
    distinct_runs = {r.id for _h, r in matches}
    attempt = max(len(distinct_runs), 1)
    handoff, run = selected
    steps = list(
        (
            await session.scalars(
                select(StepRun)
                .where(StepRun.run_id == run.id, StepRun.step_key == task_key)
                .order_by(StepRun.attempt, StepRun.created_at, StepRun.id)
            )
        ).all()
    )
    if len(steps) > 1:
        raise OperatorControlError("operator_quality_step_conflict", locale)
    step = steps[0] if steps else None
    jobs: tuple[Job, ...] = ()
    artifact: Artifact | None = None
    evaluation: QualityEvaluation | None = None
    if step is not None:
        jobs = tuple(
            sorted(
                list((await session.scalars(select(Job).where(Job.step_run_id == step.id))).all()),
                key=lambda job: (job.attempt, job.created_at, str(job.id)),
            )
        )
        candidates = list(
            (
                await session.scalars(
                    select(Artifact).where(
                        Artifact.run_id == run.id,
                        Artifact.step_run_id == step.id,
                        Artifact.artifact_type.in_(
                            (
                                "assertion_audit",
                                "source_copy_check",
                                READINESS_ARTIFACT_TYPES["reader_value"],
                                READINESS_ARTIFACT_TYPES["search_ai"],
                            )
                        ),
                        Artifact.locale == locale,
                    )
                )
            ).all()
        )
        if len(candidates) > 1:
            raise OperatorControlError("operator_quality_artifact_conflict", locale)
        artifact = candidates[0] if candidates else None
        if artifact is not None:
            evaluations = list(
                (
                    await session.scalars(
                        select(QualityEvaluation).where(
                            QualityEvaluation.run_id == run.id,
                            QualityEvaluation.artifact_id == artifact.id,
                        )
                    )
                ).all()
            )
            if len(evaluations) != 1:
                raise OperatorControlError("operator_quality_evaluation_conflict", locale)
            evaluation = evaluations[0]
    return QualityStage(
        run=run,
        handoff=handoff,
        step=step,
        jobs=jobs,
        artifact=artifact,
        evaluation=evaluation,
        attempt=attempt,
    )


async def _review_stage(
    session: AsyncSession,
    *,
    writer: WriterLane,
    locale: str,
) -> QualityStage:
    if writer.run is None:
        return QualityStage()
    steps = list(
        (
            await session.scalars(
                select(StepRun)
                .where(
                    StepRun.run_id == writer.run.id,
                    StepRun.step_key == QUALITY_REVIEW_TASK_KEYS[locale],
                )
                .order_by(StepRun.attempt, StepRun.created_at, StepRun.id)
            )
        ).all()
    )
    if len(steps) > QUALITY_MAX_JOB_ATTEMPTS:
        raise OperatorControlError("operator_quality_review_attempt_conflict", locale)
    if not steps:
        return QualityStage()
    step = steps[-1]
    jobs = tuple(
        sorted(
            list(
                (
                    await session.scalars(
                        select(Job).where(Job.step_run_id.in_([row.id for row in steps]))
                    )
                ).all()
            ),
            key=lambda job: (job.attempt, job.created_at, str(job.id)),
        )
    )
    revised_candidates = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == writer.run.id,
                    Artifact.step_run_id == step.id,
                    Artifact.artifact_type == "journal_draft",
                    Artifact.locale == locale,
                )
            )
        ).all()
    )
    if len(revised_candidates) > 1:
        raise OperatorControlError("operator_quality_revised_draft_conflict", locale)
    return QualityStage(
        step=step,
        jobs=jobs,
        artifact=revised_candidates[0] if revised_candidates else None,
        attempt=step.attempt,
    )


async def get_quality_progress(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    source_run_id: UUID | None,
) -> QualityProgress | None:
    source_run = (
        await session.get(ContentRun, source_run_id) if source_run_id is not None else None
    )
    if source_run is None or source_run.current_step != "outline":
        candidates = list(
            (
                await session.scalars(
                    select(ContentRun).where(
                        ContentRun.content_case_id == content_case_id,
                        ContentRun.current_step == "outline",
                        ContentRun.run_mode != "eval",
                    )
                )
            ).all()
        )
        if len(candidates) == 1:
            source_run_id = candidates[0].id
        elif len(candidates) > 1:
            raise OperatorControlError("operator_quality_source_run_conflict")
        else:
            return None
    writer_progress = await get_writer_lane_progress(
        session, content_case_id=content_case_id, source_run_id=source_run_id
    )
    if writer_progress is None or not writer_progress.dispatched:
        return None
    lanes: list[QualityLane] = []
    any_quality = False
    for writer in writer_progress.lanes:
        review = await _review_stage(session, writer=writer, locale=writer.required_locale)
        audit_input_draft = review.artifact
        audit = await _stage_for_handoff(
            session,
            handoff_type="assertion_audit_handoff",
            locale=writer.required_locale,
            writer=writer,
            source_draft=audit_input_draft,
            task_key=QUALITY_AUDIT_TASK_KEYS[writer.required_locale],
        )
        source_copy = await _stage_for_handoff(
            session,
            handoff_type="source_copy_handoff",
            locale=writer.required_locale,
            writer=writer,
            source_draft=audit_input_draft,
            task_key=SOURCE_COPY_TASK_KEYS[writer.required_locale],
            audit_artifact=audit.artifact,
            audit_evaluation=audit.evaluation,
        )
        reader_value = await _stage_for_handoff(
            session,
            handoff_type=READINESS_HANDOFF_TYPES["reader_value"],
            locale=writer.required_locale,
            writer=writer,
            source_draft=audit_input_draft,
            task_key=READER_VALUE_TASK_KEYS[writer.required_locale],
            source_copy_artifact=source_copy.artifact,
            source_copy_evaluation=source_copy.evaluation,
        )
        search_ai = await _stage_for_handoff(
            session,
            handoff_type=READINESS_HANDOFF_TYPES["search_ai"],
            locale=writer.required_locale,
            writer=writer,
            source_draft=audit_input_draft,
            task_key=SEARCH_AI_TASK_KEYS[writer.required_locale],
            source_copy_artifact=source_copy.artifact,
            source_copy_evaluation=source_copy.evaluation,
            reader_value_artifact=reader_value.artifact,
            reader_value_evaluation=reader_value.evaluation,
        )
        item = None
        final_content = None
        final_review = None
        checkpoint = None
        if writer.run is not None:
            canonical = f"journal:{content_case_id}:{writer.required_locale}"
            item_rows = list(
                (
                    await session.scalars(
                        select(ContentItem).where(
                            ContentItem.content_case_id == content_case_id,
                            ContentItem.locale_variant_id == writer.variant.id,
                        )
                    )
                ).all()
            )
            if len(item_rows) > 1:
                raise OperatorControlError(
                    "operator_quality_content_item_conflict", writer.required_locale
                )
            item = item_rows[0] if item_rows and item_rows[0].canonical_key == canonical else None
            if item_rows and item is None:
                raise OperatorControlError(
                    "operator_quality_content_item_identity_conflict", writer.required_locale
                )
            if item is not None:
                finals = list(
                    (
                        await session.scalars(
                            select(Artifact).where(
                                Artifact.run_id == writer.run.id,
                                Artifact.artifact_type == "final_content",
                                Artifact.locale == writer.required_locale,
                            )
                        )
                    ).all()
                )
                if len(finals) > 1:
                    raise OperatorControlError(
                        "operator_quality_final_artifact_conflict", writer.required_locale
                    )
                final_content = finals[0] if finals else None
                final_steps = list(
                    (
                        await session.scalars(
                            select(StepRun).where(
                                StepRun.run_id == writer.run.id,
                                StepRun.step_key == "final_review",
                            )
                        )
                    ).all()
                )
                if len(final_steps) > 1:
                    raise OperatorControlError(
                        "operator_quality_final_step_conflict", writer.required_locale
                    )
                final_review = final_steps[0] if final_steps else None
                checkpoint = await get_latest_checkpoint(session, run_id=writer.run.id)
        lane = QualityLane(
            locale=writer.required_locale,
            variant=writer.variant,
            writer=writer,
            review=review,
            audit=audit,
            source_copy=source_copy,
            reader_value=reader_value,
            search_ai=search_ai,
            final_item=item,
            final_content=final_content,
            final_review=final_review,
            checkpoint=checkpoint,
        )
        any_quality = any_quality or lane.status != "not_dispatched"
        lanes.append(lane)
    if not any_quality:
        return None
    return QualityProgress(
        content_case_id=content_case_id, writer_progress=writer_progress, lanes=tuple(lanes)
    )


async def pending_quality_commands(
    session: AsyncSession, *, content_case_id: UUID
) -> list[OperatorCommand]:
    return list(
        (
            await session.scalars(
                select(OperatorCommand).where(
                    OperatorCommand.content_case_id == content_case_id,
                    OperatorCommand.resolved_action_key == "writers_to_quality",
                    OperatorCommand.status == "queued",
                )
            )
        ).all()
    )


async def settle_quality_command(
    session: AsyncSession,
    *,
    progress: QualityProgress | None,
    state_version: str,
) -> None:
    if progress is None or progress.has_active_job:
        return
    if progress.final_gate_ready:
        status, error = "completed", None
    elif progress.has_content_block:
        status, error = "failed", "operator_quality_blocked"
    elif progress.has_exhausted_failure:
        status, error = "failed", "operator_quality_retry_exhausted"
    elif progress.has_retryable_failure:
        status, error = "failed", "operator_quality_job_failed"
    else:
        return
    for command in await pending_quality_commands(
        session, content_case_id=progress.content_case_id
    ):
        command.status = status
        command.error_code = error
        command.state_after = state_version
    await session.flush()


def _command_hash(*, content_case_id: UUID, intent: str, state_version: str) -> str:
    return _sha(
        {
            "content_case_id": str(content_case_id),
            "intent": intent,
            "expected_state_version": state_version,
            "action_key": "writers_to_quality",
        }
    )


def _review_dedupe(*, command_id: UUID, locale: str, source: Artifact, attempt: int = 1) -> str:
    payload = {
        "command": str(command_id),
        "locale": locale,
        "source": _ref(source),
        "attempt": attempt,
    }
    return f"operator:quality:review:{_sha(payload)}"


async def _review_registry_versions(session: AsyncSession, *, locale: str) -> tuple[str, str]:
    config = review_revise_registry_config(locale)
    prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
    recipe = await active_recipe_definition(
        session,
        recipe_key=config.recipe_key,
        content_type="journal",
        locale=locale,
        task_key=config.task_key,
    )
    return f"{prompt.prompt_key}:v{prompt.version}", f"{recipe.recipe_key}:v{recipe.version}"


async def _enqueue_source_copy_step(
    session: AsyncSession,
    *,
    source_input: SourceCopyInput,
    locale: str,
    dedupe_suffix: str,
) -> None:
    """Create/reuse the deterministic Source-copy StepRun and Job."""

    source_run, handoff, _ = await ensure_source_copy_run(
        session,
        source_input=source_input,
        task_key=SOURCE_COPY_TASK_KEYS[locale],
    )
    steps = list(
        (
            await session.scalars(
                select(StepRun).where(
                    StepRun.run_id == source_run.id,
                    StepRun.step_key == SOURCE_COPY_TASK_KEYS[locale],
                )
            )
        ).all()
    )
    if len(steps) > 1:
        raise OperatorControlError("operator_quality_source_copy_step_conflict", locale)
    if steps:
        step = steps[0]
        if step.status in {"failed", "skipped"}:
            raise OperatorControlError("operator_quality_source_copy_step_terminal", locale)
    else:
        step = StepRun(
            run_id=source_run.id,
            step_key=SOURCE_COPY_TASK_KEYS[locale],
            attempt=1,
            status="pending",
            input_artifact_refs_json=[
                str(handoff.id),
                str(source_input.source_artifact.id),
                str(source_input.assertion_audit_artifact.id),
                str(source_input.writer_input.outline_artifact.id),
            ],
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
    await enqueue_job(
        session,
        run_id=source_run.id,
        step_run_id=step.id,
        dedupe_key=f"operator:quality:source-copy:{dedupe_suffix}",
    )


async def _enqueue_readiness_retry(
    session: AsyncSession,
    *,
    source_input: QualityReadinessInput,
    dedupe_suffix: str,
) -> None:
    task_key = (
        READER_VALUE_TASK_KEYS[source_input.writer_input.locale]
        if source_input.stage == "reader_value"
        else SEARCH_AI_TASK_KEYS[source_input.writer_input.locale]
    )
    run, handoff, _ = await ensure_quality_readiness_run(
        session,
        source_input=source_input,
        task_key=task_key,
    )
    step = await session.scalar(
        select(StepRun).where(
            StepRun.run_id == run.id,
            StepRun.step_key == task_key,
        )
    )
    if step is None:
        refs = [
            str(handoff.id),
            str(source_input.source_artifact.id),
            str(source_input.source_copy_artifact.id),
        ]
        if source_input.reader_value_artifact is not None:
            refs.append(str(source_input.reader_value_artifact.id))
        step = StepRun(
            run_id=run.id,
            step_key=task_key,
            attempt=1,
            status="pending",
            input_artifact_refs_json=refs,
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
    await enqueue_job(
        session,
        run_id=run.id,
        step_run_id=step.id,
        dedupe_key=f"operator:quality:{task_key}:{dedupe_suffix}",
    )


async def _queue_quality_retry_lane(
    session: AsyncSession,
    *,
    command: OperatorCommand,
    progress: QualityProgress,
    lane: QualityLane,
) -> None:
    if lane.writer.run is None:
        raise OperatorControlError("operator_quality_retry_writer_missing")
    if lane.review.job is not None and lane.review.job.status in {"failed", "cancelled"}:
        review_attempt = (
            lane.review.step.attempt
            if lane.review.step is not None
            else lane.review.job.attempt
        )
        if (
            lane.review.step is None
            or review_attempt >= QUALITY_MAX_JOB_ATTEMPTS
            or lane.review.job.attempt >= QUALITY_MAX_JOB_ATTEMPTS
            or (
                lane.writer.run is not None
                and lane.writer.run.failure_code == "operator_quality_retry_exhausted"
            )
        ):
            raise OperatorControlError("operator_quality_retry_exhausted")
        if lane.writer.run.status == "failed":
            raise OperatorControlError("operator_quality_retry_writer_terminal")
        retry_step = StepRun(
            run_id=lane.writer.run.id,
            step_key=QUALITY_REVIEW_TASK_KEYS[lane.locale],
            attempt=lane.review.step.attempt + 1,
            status="pending",
            input_artifact_refs_json=list(lane.review.step.input_artifact_refs_json),
            output_artifact_refs_json=[],
        )
        session.add(retry_step)
        await session.flush()
        if lane.writer.run.status == "waiting_approval":
            await transition_run(session, run_id=lane.writer.run.id, status="running")
        lane.writer.run.current_step = QUALITY_REVIEW_TASK_KEYS[lane.locale]
        await enqueue_job(
            session,
            run_id=lane.writer.run.id,
            step_run_id=retry_step.id,
            dedupe_key=_review_dedupe(
                command_id=command.id,
                locale=lane.locale,
                source=lane.source_draft,
                attempt=retry_step.attempt,
            )
            if lane.source_draft is not None
            else f"operator:quality:review-retry:{command.id}:{lane.locale}",
        )
        return
    revised = lane.revised_draft
    if revised is None:
        raise OperatorControlError("operator_quality_retry_revised_missing")
    if (
        (lane.audit.job is not None and lane.audit.job.status in {"failed", "cancelled"})
        or (lane.audit.run is not None and lane.audit.run.status in {"failed", "cancelled"})
    ):
        if (
            lane.audit.attempt >= QUALITY_MAX_JOB_ATTEMPTS
            or (lane.audit.job is not None and lane.audit.job.attempt >= QUALITY_MAX_JOB_ATTEMPTS)
            or (
                lane.audit.run is not None
                and lane.audit.run.failure_code == "operator_quality_retry_exhausted"
            )
        ):
            raise OperatorControlError("operator_quality_retry_exhausted")
        audit_input = await load_assertion_audit_input(
            session,
            writer_run_id=lane.writer.run.id,
            revised_draft_artifact_id=revised.id,
            expected_revised_draft_version=revised.version,
            expected_revised_draft_hash=revised.content_hash,
            outline_artifact_id=progress.writer_progress.outline_artifact.id,
            expected_outline_version=progress.writer_progress.outline_artifact.version,
            expected_outline_hash=progress.writer_progress.outline_artifact.content_hash,
            locale=lane.locale,
        )
        config = assertion_audit_registry_config(lane.locale)
        prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=config.recipe_key,
            content_type="journal",
            locale=lane.locale,
            task_key=config.task_key,
        )
        snapshot = await session.get(SettingsSnapshot, lane.writer.run.settings_snapshot_id)
        if snapshot is None:
            raise OperatorControlError("operator_quality_settings_missing")
        route = SettingsModelRouter().resolve(task_key="angle", settings_snapshot=snapshot).primary
        audit_context = await prepare_assertion_audit_run(
            session,
            source_input=audit_input,
            task_key=config.task_key,
            prompt_version=f"{prompt.prompt_key}:v{prompt.version}",
            recipe_version=f"{recipe.recipe_key}:v{recipe.version}",
            provider=route.provider,
            model=route.model,
        )
        await enqueue_job(
            session,
            run_id=audit_context.audit_run.id,
            step_run_id=audit_context.step_run.id,
            dedupe_key=f"operator:quality:audit-retry:{command.id}:{lane.locale}",
        )
        return
    if (
        (
            lane.source_copy.job is not None
            and lane.source_copy.job.status in {"failed", "cancelled"}
        )
        or (
            lane.source_copy.run is not None
            and lane.source_copy.run.status in {"failed", "cancelled"}
        )
    ):
        if (
            lane.source_copy.attempt >= QUALITY_MAX_JOB_ATTEMPTS
            or (
                lane.source_copy.job is not None
                and lane.source_copy.job.attempt >= QUALITY_MAX_JOB_ATTEMPTS
            )
            or (
                lane.source_copy.run is not None
                and lane.source_copy.run.failure_code == "operator_quality_retry_exhausted"
            )
        ):
            raise OperatorControlError("operator_quality_retry_exhausted")
        if lane.audit.artifact is None or lane.audit.evaluation is None:
            raise OperatorControlError("operator_quality_retry_audit_missing")
        source_input = await load_source_copy_input(
            session,
            writer_run_id=lane.writer.run.id,
            source_draft_artifact_id=revised.id,
            expected_source_draft_version=revised.version,
            expected_source_draft_hash=revised.content_hash,
            assertion_audit_artifact_id=lane.audit.artifact.id,
            expected_assertion_audit_version=lane.audit.artifact.version,
            expected_assertion_audit_hash=lane.audit.artifact.content_hash,
            assertion_audit_quality_evaluation_id=lane.audit.evaluation.id,
            outline_artifact_id=progress.writer_progress.outline_artifact.id,
            expected_outline_version=progress.writer_progress.outline_artifact.version,
            expected_outline_hash=progress.writer_progress.outline_artifact.content_hash,
            locale=lane.locale,
        )
        await _enqueue_source_copy_step(
            session,
            source_input=source_input,
            locale=lane.locale,
            dedupe_suffix=f"retry:{command.id}:{lane.locale}",
        )
        return
    if (
        (
            lane.reader_value.job is not None
            and lane.reader_value.job.status in {"failed", "cancelled"}
        )
        or (
            lane.reader_value.run is not None
            and lane.reader_value.run.status in {"failed", "cancelled"}
        )
    ):
        if lane.source_copy.artifact is None or lane.source_copy.evaluation is None:
            raise OperatorControlError("operator_quality_retry_source_copy_missing")
        readiness_input = await load_quality_readiness_input(
            session,
            stage="reader_value",
            writer_run_id=lane.writer.run.id,
            source_draft_artifact_id=revised.id,
            expected_source_draft_version=revised.version,
            expected_source_draft_hash=revised.content_hash,
            outline_artifact_id=progress.writer_progress.outline_artifact.id,
            expected_outline_version=progress.writer_progress.outline_artifact.version,
            expected_outline_hash=progress.writer_progress.outline_artifact.content_hash,
            source_copy_artifact_id=lane.source_copy.artifact.id,
            source_copy_quality_evaluation_id=lane.source_copy.evaluation.id,
            locale=lane.locale,
        )
        await _enqueue_readiness_retry(
            session,
            source_input=readiness_input,
            dedupe_suffix=f"retry:{command.id}:{lane.locale}",
        )
        return
    if (
        (lane.search_ai.job is not None and lane.search_ai.job.status in {"failed", "cancelled"})
        or (lane.search_ai.run is not None and lane.search_ai.run.status in {"failed", "cancelled"})
    ):
        if (
            lane.source_copy.artifact is None
            or lane.source_copy.evaluation is None
            or lane.reader_value.artifact is None
            or lane.reader_value.evaluation is None
        ):
            raise OperatorControlError("operator_quality_retry_readiness_missing")
        readiness_input = await load_quality_readiness_input(
            session,
            stage="search_ai",
            writer_run_id=lane.writer.run.id,
            source_draft_artifact_id=revised.id,
            expected_source_draft_version=revised.version,
            expected_source_draft_hash=revised.content_hash,
            outline_artifact_id=progress.writer_progress.outline_artifact.id,
            expected_outline_version=progress.writer_progress.outline_artifact.version,
            expected_outline_hash=progress.writer_progress.outline_artifact.content_hash,
            source_copy_artifact_id=lane.source_copy.artifact.id,
            source_copy_quality_evaluation_id=lane.source_copy.evaluation.id,
            locale=lane.locale,
            reader_value_artifact_id=lane.reader_value.artifact.id,
            reader_value_quality_evaluation_id=lane.reader_value.evaluation.id,
        )
        await _enqueue_readiness_retry(
            session,
            source_input=readiness_input,
            dedupe_suffix=f"retry:{command.id}:{lane.locale}",
        )
        return
    raise OperatorControlError("operator_quality_retry_stage_missing")


async def _queue_quality_retry(
    session: AsyncSession,
    *,
    command: OperatorCommand,
    progress: QualityProgress,
) -> None:
    failed = [lane for lane in progress.lanes if lane.status == "execution_failed_retryable"]
    if not failed:
        raise OperatorControlError("operator_quality_retry_lane_conflict")
    for lane in failed:
        await _queue_quality_retry_lane(
            session,
            command=command,
            progress=progress,
            lane=lane,
        )


async def submit_writers_to_quality_command(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    intent: str,
    expected_state_version: str,
    idempotency_key: str,
    actor_id: str,
    resolved_state: object,
) -> OperatorCommandResult:
    """Create the single semantic F4 command and its two durable Review jobs."""

    if intent not in {"continue", "retry", "cancel"}:
        raise OperatorControlError("operator_intent_not_allowed")
    key = idempotency_key.strip()
    if not key or len(key) > 200 or len(expected_state_version) != 64:
        raise OperatorControlError("operator_idempotency_key_invalid")
    request_hash = _command_hash(
        content_case_id=content_case_id, intent=intent, state_version=expected_state_version
    )
    await lock_operator_idempotency(session, key=key)
    existing = await session.scalar(
        select(OperatorCommand).where(OperatorCommand.idempotency_key == key)
    )
    if existing is not None:
        if existing.content_case_id != content_case_id or existing.request_hash != request_hash:
            raise OperatorControlError("operator_idempotency_conflict")
        return OperatorCommandResult(
            command_id=existing.id,
            content_case_id=existing.content_case_id,
            intent=cast(OperatorIntent, existing.intent),
            status=existing.status,
            state_before=existing.state_before,
            state_after=existing.state_after,
            job_id=existing.job_id,
            replayed=True,
        )
    progress = await get_quality_progress(
        session,
        content_case_id=content_case_id,
        source_run_id=getattr(resolved_state, "current_run_id", None),
    )
    if progress is None:
        writer_progress = await get_writer_lane_progress(
            session,
            content_case_id=content_case_id,
            source_run_id=getattr(resolved_state, "current_run_id", None),
        )
        if writer_progress is None or not writer_progress.all_complete:
            raise OperatorControlError("operator_quality_writer_entry_invalid")
        progress = QualityProgress(content_case_id, writer_progress, tuple())
    if getattr(resolved_state, "state_version", None) != expected_state_version:
        raise OperatorControlError("operator_state_stale")
    if intent == "continue" and progress.lanes:
        raise OperatorControlError("operator_quality_already_dispatched")
    if intent == "retry" and (
        progress is None or not progress.dispatched or not progress.has_retryable_failure
    ):
        raise OperatorControlError("operator_quality_retry_requires_failed_job")

    source_run = progress.writer_progress.source_run
    command = OperatorCommand(
        content_case_id=content_case_id,
        run_id=source_run.id,
        step_run_id=None,
        job_id=None,
        intent=intent,
        idempotency_key=key,
        request_hash=request_hash,
        expected_state_version=expected_state_version,
        resolved_action_key="writers_to_quality",
        status="accepted",
        error_code=None,
        actor_id=actor_id,
        state_before=expected_state_version,
        state_after=None,
    )
    session.add(command)
    await session.flush()
    if intent == "cancel":
        if progress is None or not progress.has_active_job:
            raise OperatorControlError("operator_quality_cancel_requires_queued_job")
        now = utc_now()
        for lane in progress.lanes:
            for stage in (
                lane.review,
                lane.audit,
                lane.source_copy,
                lane.reader_value,
                lane.search_ai,
            ):
                job = stage.job
                if job is not None and job.status == "queued":
                    job.status = "cancelled"
                    job.updated_at = now
        command.status = "cancelled"
        command.error_code = None
        await session.flush()
        settle_progress = await get_quality_progress(
            session, content_case_id=content_case_id, source_run_id=source_run.id
        )
        from app.modules.content_engine.journal.operator_runtime import get_operator_state

        op_state = await get_operator_state(
            session, content_case_id=content_case_id, preflight_checked=True
        )
        if settle_progress is not None:
            await settle_quality_command(
                session,
                progress=settle_progress,
                state_version=op_state.state_version,
            )
        command.state_after = op_state.state_version
        await session.flush()
        return OperatorCommandResult(
            command_id=command.id,
            content_case_id=content_case_id,
            intent=cast(OperatorIntent, intent),
            status=command.status,
            state_before=command.state_before,
            state_after=command.state_after,
            job_id=None,
            replayed=False,
        )
    if intent == "retry":
        assert progress is not None
        await _queue_quality_retry(session, command=command, progress=progress)
        command.status = "queued"
        await session.flush()
        from app.modules.content_engine.journal.operator_runtime import get_operator_state

        op_state = await get_operator_state(
            session, content_case_id=content_case_id, preflight_checked=True
        )
        command.state_after = op_state.state_version
        await session.flush()
        return OperatorCommandResult(
            command_id=command.id,
            content_case_id=content_case_id,
            intent=cast(OperatorIntent, intent),
            status=command.status,
            state_before=command.state_before,
            state_after=command.state_after,
            job_id=None,
            replayed=False,
        )

    for writer_lane in progress.writer_progress.lanes:
        if (
            writer_lane.run is None
            or writer_lane.step is None
            or writer_lane.draft is None
            or writer_lane.handoff is None
        ):
            raise OperatorControlError(
                "operator_quality_writer_entry_invalid", writer_lane.required_locale
            )
        if writer_lane.run.status != "waiting_approval":
            raise OperatorControlError(
                "operator_quality_writer_state_invalid", writer_lane.required_locale
            )
        try:
            review_input = await load_review_revise_input(
                session,
                writer_run_id=writer_lane.run.id,
                source_draft_artifact_id=writer_lane.draft.id,
                expected_source_draft_version=writer_lane.draft.version,
                expected_source_draft_hash=writer_lane.draft.content_hash,
                outline_artifact_id=progress.writer_progress.outline_artifact.id,
                expected_outline_version=progress.writer_progress.outline_artifact.version,
                expected_outline_hash=progress.writer_progress.outline_artifact.content_hash,
                locale=writer_lane.required_locale,
            )
            prompt_version, recipe_version = await _review_registry_versions(
                session, locale=writer_lane.required_locale
            )
        except Exception as exc:
            raise OperatorControlError(
                "operator_quality_review_input_invalid", str(getattr(exc, "code", exc))
            ) from exc
        del review_input, prompt_version, recipe_version
        step = StepRun(
            run_id=writer_lane.run.id,
            step_key=QUALITY_REVIEW_TASK_KEYS[writer_lane.required_locale],
            attempt=1,
            status="pending",
            input_artifact_refs_json=[
                str(writer_lane.draft.id),
                str(progress.writer_progress.outline_artifact.id),
                str(writer_lane.handoff.id),
            ],
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
        await transition_run(session, run_id=writer_lane.run.id, status="running")
        writer_lane.run.current_step = QUALITY_REVIEW_TASK_KEYS[writer_lane.required_locale]
        writer_lane.run.failure_code = None
        writer_lane.run.failure_message = None
        await session.flush()
        job = await enqueue_job(
            session,
            run_id=writer_lane.run.id,
            step_run_id=step.id,
            dedupe_key=_review_dedupe(
                command_id=command.id,
                locale=writer_lane.required_locale,
                source=writer_lane.draft,
            ),
        )
        # Parent receipts intentionally have no single job_id: this is a fan-out.
        del job
    command.status = "queued"
    await session.flush()
    from app.modules.content_engine.journal.operator_runtime import get_operator_state

    op_state = await get_operator_state(
        session, content_case_id=content_case_id, preflight_checked=True
    )
    command.state_after = op_state.state_version
    await session.flush()
    return OperatorCommandResult(
        command_id=command.id,
        content_case_id=content_case_id,
        intent=cast(OperatorIntent, intent),
        status=command.status,
        state_before=command.state_before,
        state_after=command.state_after,
        job_id=None,
        replayed=False,
    )


async def _exact_final_item(
    session: AsyncSession,
    *,
    content_case: ContentCase,
    variant: LocaleVariant,
) -> ContentItem:
    canonical = f"journal:{content_case.id}:{variant.locale}"
    by_key = list(
        (
            await session.scalars(
                select(ContentItem).where(
                    ContentItem.project_id == content_case.project_id,
                    ContentItem.canonical_key == canonical,
                )
            )
        ).all()
    )
    by_variant = list(
        (
            await session.scalars(
                select(ContentItem).where(ContentItem.locale_variant_id == variant.id)
            )
        ).all()
    )
    if len(by_key) > 1 or len(by_variant) > 1:
        raise OperatorControlError("operator_quality_content_item_conflict", variant.locale)
    if by_key and by_key[0].locale_variant_id != variant.id:
        raise OperatorControlError(
            "operator_quality_content_item_identity_conflict", variant.locale
        )
    if by_variant and by_variant[0].canonical_key != canonical:
        raise OperatorControlError(
            "operator_quality_content_item_identity_conflict", variant.locale
        )
    if by_key:
        item = by_key[0]
    elif by_variant:
        item = by_variant[0]
    else:
        item = ContentItem(
            project_id=content_case.project_id,
            content_case_id=content_case.id,
            locale_variant_id=variant.id,
            content_type="journal",
            status="draft",
            canonical_key=canonical,
        )
        session.add(item)
        await session.flush()
    if (
        item.project_id != content_case.project_id
        or item.content_case_id != content_case.id
        or item.locale_variant_id != variant.id
        or item.content_type != "journal"
        or item.canonical_key != canonical
    ):
        raise OperatorControlError(
            "operator_quality_content_item_identity_conflict", variant.locale
        )
    return item


async def prepare_final_gates(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    progress: QualityProgress,
) -> QualityProgress:
    """Prepare both locale final-review gates from one exact quality snapshot."""

    if not progress.all_qualified:
        raise OperatorControlError("operator_quality_final_gate_requires_all_qualified")
    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None or content_case.content_type != "journal":
        raise OperatorControlError("operator_case_not_found")
    prepared: list[QualityLane] = []
    for lane in progress.lanes:
        if lane.writer.run is None or lane.revised_draft is None:
            raise OperatorControlError("operator_quality_final_source_missing", lane.locale)
        item = await _exact_final_item(session, content_case=content_case, variant=lane.variant)
        if lane.writer.run.content_item_id is None:
            lane.writer.run.content_item_id = item.id
        elif lane.writer.run.content_item_id != item.id:
            raise OperatorControlError("operator_quality_writer_content_item_conflict", lane.locale)
        if lane.audit.run is not None:
            lane.audit.run.content_item_id = item.id
        if lane.source_copy.run is not None:
            lane.source_copy.run.content_item_id = item.id
        if lane.reader_value.run is not None:
            lane.reader_value.run.content_item_id = item.id
        if lane.search_ai.run is not None:
            lane.search_ai.run.content_item_id = item.id
        if lane.writer.run.status == "waiting_approval":
            await transition_run(session, run_id=lane.writer.run.id, status="running")
        elif lane.writer.run.status != "running":
            raise OperatorControlError("operator_quality_final_writer_state_invalid", lane.locale)
        steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == lane.writer.run.id,
                        StepRun.step_key == "final_review",
                    )
                )
            ).all()
        )
        if len(steps) > 1 or (steps and steps[0].attempt != 1):
            raise OperatorControlError("operator_quality_final_step_conflict", lane.locale)
        if lane.reader_value.artifact is None or lane.search_ai.artifact is None:
            raise OperatorControlError("operator_quality_final_readiness_missing", lane.locale)
        expected_final_inputs = [
            str(lane.revised_draft.id),
            str(item.id),
            str(lane.reader_value.artifact.id),
            str(lane.search_ai.artifact.id),
        ]
        step = (
            steps[0]
            if steps
            else StepRun(
                run_id=lane.writer.run.id,
                step_key="final_review",
                attempt=1,
                status="pending",
                input_artifact_refs_json=expected_final_inputs,
                output_artifact_refs_json=[],
            )
        )
        if not steps:
            session.add(step)
            await session.flush()
        elif set(expected_final_inputs) - set(step.input_artifact_refs_json):
            raise OperatorControlError("operator_quality_final_step_input_stale", lane.locale)
        if step.status == "pending":
            await transition_step_run(session, step_run_id=step.id, status="running")
        elif step.status != "running" and step.status != "completed":
            raise OperatorControlError("operator_quality_final_step_state_invalid", lane.locale)
        finals = list(
            (
                await session.scalars(
                    select(Artifact).where(
                        Artifact.run_id == lane.writer.run.id,
                        Artifact.artifact_type == "final_content",
                        Artifact.locale == lane.locale,
                    )
                )
            ).all()
        )
        if len(finals) > 1:
            raise OperatorControlError("operator_quality_final_artifact_conflict", lane.locale)
        if finals:
            final = finals[0]
            if (
                final.version != 1
                or final.step_run_id != step.id
                or final.content_json != copy.deepcopy(lane.revised_draft.content_json)
                or final.content_hash != lane.revised_draft.content_hash
            ):
                raise OperatorControlError("operator_quality_final_artifact_stale", lane.locale)
        else:
            final = Artifact(
                run_id=lane.writer.run.id,
                step_run_id=step.id,
                artifact_type="final_content",
                locale=lane.locale,
                version=1,
                content_json=copy.deepcopy(lane.revised_draft.content_json),
                content_hash=lane.revised_draft.content_hash,
            )
            session.add(final)
            await session.flush()
            step.output_artifact_refs_json = [*step.output_artifact_refs_json, str(final.id)]
        if step.status == "running":
            await transition_step_run(session, step_run_id=step.id, status="completed")
        prepared.append(
            QualityLane(
                locale=lane.locale,
                variant=lane.variant,
                writer=lane.writer,
                review=lane.review,
                audit=lane.audit,
                source_copy=lane.source_copy,
                reader_value=lane.reader_value,
                search_ai=lane.search_ai,
                final_item=item,
                final_content=final,
                final_review=step,
                checkpoint=None,
            )
        )
    # Only after both artifacts and steps validate do we expose per-locale approval waits.
    for lane in prepared:
        assert lane.writer.run is not None and lane.final_content is not None
        latest = await get_latest_checkpoint(session, run_id=lane.writer.run.id)
        pending = _pending_checkpoint(latest)
        expected = {"step_key": "final_review", "artifact_id": str(lane.final_content.id)}
        if pending != expected:
            await pause_for_approval(
                session,
                run_id=lane.writer.run.id,
                step_key="final_review",
                artifact_id=lane.final_content.id,
            )
    await session.flush()
    refreshed = await get_quality_progress(
        session,
        content_case_id=content_case_id,
        source_run_id=progress.writer_progress.source_run.id,
    )
    if refreshed is None or not refreshed.final_gate_ready:
        raise OperatorControlError("operator_quality_final_gate_not_ready")
    return refreshed


__all__ = [
    "QUALITY_AUDIT_TASK_KEYS",
    "QUALITY_LOCALES",
    "QUALITY_MAX_JOB_ATTEMPTS",
    "QUALITY_REVIEW_TASK_KEYS",
    "QualityLane",
    "QualityProgress",
    "QualityStage",
    "get_quality_progress",
    "pending_quality_commands",
    "prepare_final_gates",
    "settle_quality_command",
    "submit_writers_to_quality_command",
]