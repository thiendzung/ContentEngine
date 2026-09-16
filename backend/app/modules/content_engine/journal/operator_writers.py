"""Small shared primitives for the F3 independent Writer lanes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import (
    JournalRequiredLocale,
    OperatorCommand,
    OutlineApproval,
)
from app.modules.content_engine.journal.operator_control import OperatorControlError
from app.modules.content_engine.models import LocaleVariant
from app.modules.harness.models import Artifact, ContentRun, Job, StepRun

WRITER_STEP_BY_LOCALE: dict[str, str] = {
    "vi-VN": "writer_vi",
    "en": "writer_en",
}
WRITER_LOCALES = tuple(WRITER_STEP_BY_LOCALE)
WRITER_MAX_JOB_ATTEMPTS = 2


@dataclass(frozen=True, slots=True)
class WriterLane:
    required_locale: str
    variant: LocaleVariant
    run: ContentRun | None
    step: StepRun | None
    jobs: tuple[Job, ...]
    handoff: Artifact | None
    draft: Artifact | None

    @property
    def latest_job(self) -> Job | None:
        return self.jobs[-1] if self.jobs else None

    @property
    def status(self) -> str:
        job = self.latest_job
        if job is not None:
            if job.status == "queued":
                return "queued"
            if job.status == "leased":
                return "running"
            if job.status in {"failed", "cancelled"}:
                return "failed"
        if self.step is not None and self.step.status == "failed":
            return "failed"
        if (
            self.draft is not None
            and self.step is not None
            and self.step.status == "completed"
            and self.run is not None
            and self.run.status == "waiting_approval"
        ):
            return "completed"
        if self.step is not None and self.step.status == "running":
            return "running"
        return "pending"


@dataclass(frozen=True, slots=True)
class WriterLaneProgress:
    content_case_id: UUID
    source_run: ContentRun
    outline_artifact: Artifact
    outline_approval: OutlineApproval
    required_locales: tuple[str, ...]
    lanes: tuple[WriterLane, ...]

    @property
    def dispatched(self) -> bool:
        return any(lane.run is not None for lane in self.lanes)

    @property
    def all_complete(self) -> bool:
        return bool(self.lanes) and all(lane.status == "completed" for lane in self.lanes)

    @property
    def has_active_job(self) -> bool:
        return any(lane.status in {"queued", "running"} for lane in self.lanes)

    @property
    def has_queued_job(self) -> bool:
        return any(lane.status == "queued" for lane in self.lanes)

    @property
    def has_failed_lane(self) -> bool:
        return any(lane.status == "failed" for lane in self.lanes)

    @property
    def has_exhausted_lane(self) -> bool:
        """Return whether a failed/cancelled lane reached its bounded job limit."""

        return any(
            lane.latest_job is not None
            and lane.latest_job.status in {"failed", "cancelled"}
            and lane.latest_job.attempt >= WRITER_MAX_JOB_ATTEMPTS
            for lane in self.lanes
        )

    @property
    def has_retryable_failed_lane(self) -> bool:
        """Return whether at least one failed lane can receive one more job."""

        return any(
            lane.latest_job is not None
            and lane.latest_job.status in {"failed", "cancelled"}
            and lane.latest_job.attempt < WRITER_MAX_JOB_ATTEMPTS
            for lane in self.lanes
        )

    @property
    def version_payload(self) -> dict[str, object]:
        return {
            "required_locales": list(self.required_locales),
            "outline": {
                "id": str(self.outline_artifact.id),
                "version": self.outline_artifact.version,
                "content_hash": self.outline_artifact.content_hash,
                "approval_id": str(self.outline_approval.id),
            },
            "lanes": [
                {
                    "locale": lane.required_locale,
                    "variant_id": str(lane.variant.id),
                    "run_id": str(lane.run.id) if lane.run else None,
                    "run_status": lane.run.status if lane.run else None,
                    "step_run_id": str(lane.step.id) if lane.step else None,
                    "step_status": lane.step.status if lane.step else None,
                    "step_attempt": lane.step.attempt if lane.step else None,
                    "jobs": [
                        {
                            "id": str(job.id),
                            "status": job.status,
                            "attempt": job.attempt,
                        }
                        for job in lane.jobs
                    ],
                    "draft": None
                    if lane.draft is None
                    else {
                        "id": str(lane.draft.id),
                        "version": lane.draft.version,
                        "content_hash": lane.draft.content_hash,
                    },
                }
                for lane in self.lanes
            ],
        }


async def exact_outline_approval(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> tuple[OutlineApproval, Artifact]:
    approvals = list(
        (
            await session.scalars(
                select(OutlineApproval)
                .where(OutlineApproval.run_id == run_id)
                .order_by(OutlineApproval.created_at, OutlineApproval.id)
            )
        ).all()
    )
    if len(approvals) != 1:
        raise OperatorControlError("operator_outline_approval_conflict")
    approval = approvals[0]
    artifact = await session.get(Artifact, approval.outline_artifact_id)
    if (
        artifact is None
        or artifact.run_id != run_id
        or artifact.artifact_type != "journal_outline"
        or artifact.version != approval.outline_artifact_version
        or artifact.content_hash != approval.outline_artifact_hash
    ):
        raise OperatorControlError("operator_outline_snapshot_stale")
    return approval, artifact


def _validate_handoff(
    handoff: Artifact,
    *,
    source_run: ContentRun,
    outline_artifact: Artifact,
    approval: OutlineApproval,
    variant: LocaleVariant,
) -> None:
    payload = handoff.content_json
    if not isinstance(payload, dict) or payload.get("artifact_type") != "writer_handoff":
        raise OperatorControlError("operator_writer_handoff_invalid")
    source_outline = payload.get("source_outline")
    target = payload.get("target_locale_variant")
    outline_approval = payload.get("outline_approval")
    if not isinstance(source_outline, dict) or not isinstance(target, dict):
        raise OperatorControlError("operator_writer_handoff_invalid")
    if (
        source_outline.get("id") != str(outline_artifact.id)
        or source_outline.get("version") != outline_artifact.version
        or source_outline.get("content_hash") != outline_artifact.content_hash
        or payload.get("source_run_id") != str(source_run.id)
        or target.get("id") != str(variant.id)
        or target.get("locale") != variant.locale
    ):
        raise OperatorControlError("operator_writer_handoff_stale")
    if (
        not isinstance(outline_approval, dict)
        or outline_approval.get("id") != str(approval.id)
    ):
        raise OperatorControlError("operator_writer_approval_binding_invalid")


async def get_writer_lane_progress(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    source_run_id: UUID | None,
) -> WriterLaneProgress | None:
    """Read the F3 aggregate without creating or mutating any runtime records."""

    if source_run_id is None:
        return None
    source_run = await session.get(ContentRun, source_run_id)
    if (
        source_run is None
        or source_run.content_case_id != content_case_id
        or source_run.current_step != "outline"
    ):
        return None
    requirements = list(
        (
            await session.scalars(
                select(JournalRequiredLocale)
                .where(JournalRequiredLocale.content_case_id == content_case_id)
                .order_by(JournalRequiredLocale.locale, JournalRequiredLocale.id)
            )
        ).all()
    )
    if not requirements:
        return None
    required_locales = tuple(row.locale for row in requirements)
    if any(locale not in WRITER_STEP_BY_LOCALE for locale in required_locales):
        raise OperatorControlError("operator_writer_locale_unsupported")
    if len(set(required_locales)) != len(required_locales):
        raise OperatorControlError("operator_writer_locale_conflict")
    source_variant = await session.get(LocaleVariant, source_run.locale_variant_id)
    if source_variant is None or source_variant.locale not in required_locales:
        raise OperatorControlError("operator_writer_source_locale_conflict")
    for requirement in requirements:
        expected_role = (
            "source" if requirement.locale == source_variant.locale else "translation"
        )
        if requirement.role != expected_role:
            raise OperatorControlError("operator_writer_locale_role_conflict")
    approval_rows = list(
        (
            await session.scalars(
                select(OutlineApproval)
                .where(OutlineApproval.run_id == source_run.id)
                .order_by(OutlineApproval.created_at, OutlineApproval.id)
            )
        ).all()
    )
    if not approval_rows:
        return None
    approval, outline_artifact = await exact_outline_approval(
        session,
        run_id=source_run.id,
    )

    variants: dict[str, list[LocaleVariant]] = {}
    for locale in required_locales:
        rows = list(
            (
                await session.scalars(
                    select(LocaleVariant).where(
                        LocaleVariant.content_case_id == content_case_id,
                        LocaleVariant.locale == locale,
                    )
                )
            ).all()
        )
        if len(rows) != 1:
            raise OperatorControlError("operator_writer_locale_variant_conflict", locale)
        variants[locale] = rows

    all_runs = list(
        (
            await session.scalars(
                select(ContentRun).where(
                    ContentRun.content_case_id == content_case_id,
                    ContentRun.run_mode == "localize",
                )
            )
        ).all()
    )
    lanes: list[WriterLane] = []
    for locale in required_locales:
        variant = variants[locale][0]
        matching_runs = [row for row in all_runs if row.locale_variant_id == variant.id]
        if len(matching_runs) > 1:
            raise OperatorControlError("operator_writer_run_conflict", locale)
        run = matching_runs[0] if matching_runs else None
        if run is None:
            lanes.append(
                WriterLane(
                    required_locale=locale,
                    variant=variant,
                    run=None,
                    step=None,
                    jobs=(),
                    handoff=None,
                    draft=None,
                )
            )
            continue
        handoffs = list(
            (
                await session.scalars(
                    select(Artifact).where(
                        Artifact.run_id == run.id,
                        Artifact.artifact_type == "writer_handoff",
                    )
                )
            ).all()
        )
        if len(handoffs) != 1:
            raise OperatorControlError("operator_writer_handoff_conflict", locale)
        handoff = handoffs[0]
        _validate_handoff(
            handoff,
            source_run=source_run,
            outline_artifact=outline_artifact,
            approval=approval,
            variant=variant,
        )
        steps = list(
            (
                await session.scalars(
                    select(StepRun).where(
                        StepRun.run_id == run.id,
                        StepRun.step_key == WRITER_STEP_BY_LOCALE[locale],
                    )
                )
            ).all()
        )
        if len(steps) != 1:
            raise OperatorControlError("operator_writer_step_conflict", locale)
        step = steps[0]
        jobs = tuple(
            sorted(
                list(
                    (
                        await session.scalars(
                            select(Job).where(Job.step_run_id == step.id)
                        )
                    ).all()
                ),
                key=lambda job: (job.attempt, job.created_at, str(job.id)),
            )
        )
        drafts = list(
            (
                await session.scalars(
                    select(Artifact).where(
                        Artifact.run_id == run.id,
                        Artifact.artifact_type == "journal_draft",
                        Artifact.locale == locale,
                    )
                )
            ).all()
        )
        if len(drafts) > 1:
            raise OperatorControlError("operator_writer_draft_conflict", locale)
        lanes.append(
            WriterLane(
                required_locale=locale,
                variant=variant,
                run=run,
                step=step,
                jobs=jobs,
                handoff=handoff,
                draft=drafts[0] if drafts else None,
            )
        )
    return WriterLaneProgress(
        content_case_id=content_case_id,
        source_run=source_run,
        outline_artifact=outline_artifact,
        outline_approval=approval,
        required_locales=required_locales,
        lanes=tuple(lanes),
    )


async def pending_writer_commands(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> list[OperatorCommand]:
    return list(
        (
            await session.scalars(
                select(OperatorCommand).where(
                    OperatorCommand.content_case_id == content_case_id,
                    OperatorCommand.resolved_action_key == "outline_to_writers",
                    OperatorCommand.status == "queued",
                )
            )
        ).all()
    )


__all__ = [
    "WRITER_LOCALES",
    "WRITER_MAX_JOB_ATTEMPTS",
    "WRITER_STEP_BY_LOCALE",
    "WriterLane",
    "WriterLaneProgress",
    "exact_outline_approval",
    "get_writer_lane_progress",
    "pending_writer_commands",
]
