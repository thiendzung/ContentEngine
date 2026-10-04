"""Exact durable bindings for bounded final-review revisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.writer import _canonical_hash
from app.modules.content_engine.models import ContentItem
from app.modules.harness.models import Approval, Artifact, ContentRun, StepRun

FINAL_REVISION_STEP_KEYS = {"vi-VN": "final_revision_vi", "en": "final_revision_en"}


class FinalRevisionBindingError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class FinalRevisionRequest:
    approval: Approval
    final_artifact: Artifact
    source_draft: Artifact
    writer_run: ContentRun
    outline_artifact: Artifact
    content_item: ContentItem | None

    @property
    def locale(self) -> str:
        if self.final_artifact.locale is None:
            raise FinalRevisionBindingError("final_revision_locale_missing")
        return self.final_artifact.locale

    @property
    def step_key(self) -> str:
        try:
            return FINAL_REVISION_STEP_KEYS[self.locale]
        except KeyError as exc:
            raise FinalRevisionBindingError(
                "final_revision_locale_unsupported", self.locale
            ) from exc


async def _one_source_draft(
    session: AsyncSession,
    *,
    final_artifact: Artifact,
) -> Artifact:
    drafts = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == final_artifact.run_id,
                    Artifact.artifact_type == "journal_draft",
                    Artifact.locale == final_artifact.locale,
                    Artifact.content_hash == final_artifact.content_hash,
                )
            )
        ).all()
    )
    if len(drafts) != 1:
        raise FinalRevisionBindingError("final_revision_source_draft_conflict")
    return drafts[0]


async def _request_from_approval(
    session: AsyncSession,
    *,
    approval: Approval,
) -> FinalRevisionRequest:
    if approval.step_key != "final_review" or approval.decision != "changes_requested":
        raise FinalRevisionBindingError("final_revision_decision_invalid")
    if not isinstance(approval.comment, str) or not approval.comment.strip():
        raise FinalRevisionBindingError("final_revision_comment_required")
    writer_run = await session.get(ContentRun, approval.run_id)
    final_artifact = await session.get(Artifact, approval.artifact_id)
    if (
        writer_run is None
        or final_artifact is None
        or final_artifact.run_id != writer_run.id
        or final_artifact.artifact_type != "final_content"
        or final_artifact.locale is None
    ):
        raise FinalRevisionBindingError("final_revision_final_binding_invalid")
    latest = list(
        (
            await session.scalars(
                select(Artifact)
                .where(
                    Artifact.run_id == writer_run.id,
                    Artifact.artifact_type == "final_content",
                    Artifact.locale == final_artifact.locale,
                )
                .order_by(Artifact.version.desc(), Artifact.id.desc())
            )
        ).all()
    )
    if not latest or latest[0].id != final_artifact.id:
        # A superseded request is historical only when the newer candidate is
        # itself the completed output of a final-review step.  An arbitrary
        # newer artifact must remain a fail-closed binding error.
        if latest and latest[0].step_run_id is not None:
            newer_step = await session.get(StepRun, latest[0].step_run_id)
            if (
                newer_step is not None
                and newer_step.step_key == "final_review"
                and newer_step.status == "completed"
            ):
                raise FinalRevisionBindingError("final_revision_historical_approval")
        raise FinalRevisionBindingError("final_revision_artifact_superseded")
    if len({row.version for row in latest}) != len(latest):
        raise FinalRevisionBindingError("final_revision_artifact_conflict")
    content_item = (
        await session.get(ContentItem, writer_run.content_item_id)
        if writer_run.content_item_id is not None
        else None
    )
    if content_item is not None:
        from app.modules.content_engine.models import ContentVersion

        active = int(
            await session.scalar(
                select(ContentVersion.id)
                .where(
                    ContentVersion.content_item_id == content_item.id,
                    ContentVersion.status.in_(("approved", "published")),
                )
                .limit(1)
            )
            is not None
        )
        if active:
            raise FinalRevisionBindingError("final_revision_active_content_version")
    source_draft = await _one_source_draft(session, final_artifact=final_artifact)
    payload = source_draft.content_json
    if not isinstance(payload, dict) or _canonical_hash(payload) != source_draft.content_hash:
        raise FinalRevisionBindingError("final_revision_source_draft_stale")
    raw_outline = payload.get("journal_outline")
    if not isinstance(raw_outline, dict):
        raise FinalRevisionBindingError("final_revision_outline_ref_missing")
    try:
        outline_id = UUID(cast(str, raw_outline["id"]))
        outline_version = int(cast(int, raw_outline["version"]))
        outline_hash = cast(str, raw_outline["content_hash"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FinalRevisionBindingError("final_revision_outline_ref_invalid") from exc
    outline = await session.get(Artifact, outline_id)
    if (
        outline is None
        or outline.artifact_type != "journal_outline"
        or outline.version != outline_version
        or outline.content_hash != outline_hash
    ):
        raise FinalRevisionBindingError("final_revision_outline_binding_invalid")
    return FinalRevisionRequest(
        approval=approval,
        final_artifact=final_artifact,
        source_draft=source_draft,
        writer_run=writer_run,
        outline_artifact=outline,
        content_item=content_item,
    )


async def load_final_revision_requests(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> tuple[FinalRevisionRequest, ...]:
    approvals = list(
        (
            await session.scalars(
                select(Approval)
                .join(ContentRun, ContentRun.id == Approval.run_id)
                .where(
                    ContentRun.content_case_id == content_case_id,
                    Approval.step_key == "final_review",
                    Approval.decision == "changes_requested",
                )
                .order_by(Approval.created_at, Approval.id)
            )
        ).all()
    )
    requests: list[FinalRevisionRequest] = []
    seen: set[tuple[UUID, UUID]] = set()
    for approval in approvals:
        try:
            request = await _request_from_approval(session, approval=approval)
        except FinalRevisionBindingError as exc:
            # A completed revision creates a newer immutable final candidate;
            # the old changes_requested approval is historical, not a new request.
            if exc.code == "final_revision_historical_approval":
                continue
            raise
        key = (request.writer_run.id, request.final_artifact.id)
        if key in seen:
            raise FinalRevisionBindingError("final_revision_decision_conflict")
        seen.add(key)
        requests.append(request)
    return tuple(requests)


__all__ = [
    "FINAL_REVISION_STEP_KEYS",
    "FinalRevisionBindingError",
    "FinalRevisionRequest",
    "load_final_revision_requests",
]
