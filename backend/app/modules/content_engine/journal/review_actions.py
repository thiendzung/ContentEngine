"""Durable Founder decisions from the Journal Review Console."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.review_action_view import get_action_aware_review_case
from app.modules.content_engine.models import ContentItem, ContentVersion
from app.modules.content_engine.persistence import create_next_content_version
from app.modules.harness.models import Approval, Artifact, ContentRun
from app.modules.harness.persistence import resolve_approval, transition_run

ReviewDecision = Literal["approved", "changes_requested", "rejected"]


class ReviewActionError(ValueError):
    """Raised when a Review Console write cannot be applied safely."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class ReviewDecisionResult(BaseModel):
    content_case_id: UUID
    locale_variant_id: UUID
    decision: ReviewDecision
    approval_id: UUID
    writer_run_id: UUID
    writer_run_status: str
    content_version_id: UUID | None = None
    content_version_no: int | None = None
    replayed: bool = False


def _normalized_comment(comment: str | None) -> str | None:
    if comment is None:
        return None
    value = comment.strip()
    return value or None


async def _existing_version(
    session: AsyncSession,
    *,
    content_item_id: UUID,
    final_artifact_id: UUID,
) -> ContentVersion | None:
    rows = list(
        (
            await session.scalars(
                select(ContentVersion)
                .where(ContentVersion.content_item_id == content_item_id)
                .order_by(ContentVersion.version_no, ContentVersion.id)
            )
        ).all()
    )
    active = [row for row in rows if row.status in {"approved", "published"}]
    exact = [row for row in active if row.final_artifact_id == final_artifact_id]
    if len(exact) == 1 and len(active) == 1:
        return exact[0]
    if active:
        raise ReviewActionError("review_action_content_version_conflict")
    return None


async def submit_review_decision(
    session: AsyncSession,
    *,
    content_case_id: UUID,
    locale_variant_id: UUID,
    decision: ReviewDecision,
    actor_id: str,
    comment: str | None,
) -> ReviewDecisionResult:
    """Persist one exact final-review decision and optional approved ContentVersion."""
    normalized_comment = _normalized_comment(comment)
    if not actor_id.strip():
        raise ReviewActionError("review_action_actor_required")
    if decision in {"changes_requested", "rejected"} and normalized_comment is None:
        raise ReviewActionError("review_action_comment_required")

    detail = await get_action_aware_review_case(session, content_case_id=content_case_id)
    panel = next(
        (row for row in detail.locales if row.locale_variant_id == locale_variant_id),
        None,
    )
    if panel is None:
        raise ReviewActionError("review_action_locale_not_found")
    if panel.quality_state not in {"PASS", "WARN"}:
        raise ReviewActionError("review_action_quality_blocked")
    if panel.assertion_audit.critical_unsupported_count > 0:
        raise ReviewActionError("review_action_quality_blocked")
    if panel.assertion_audit.critical_contradicted_count > 0:
        raise ReviewActionError("review_action_quality_blocked")
    if panel.source_copy.fail_count > 0:
        raise ReviewActionError("review_action_quality_blocked")
    if panel.consistency_state != "CONSISTENT":
        raise ReviewActionError("review_action_inconsistent_state")
    if panel.final_content is None or panel.provenance.writer_run_id is None:
        raise ReviewActionError("review_action_final_binding_missing")

    final_artifact = await session.get(Artifact, panel.final_content.id)
    writer_run = await session.scalar(
        select(ContentRun)
        .where(ContentRun.id == panel.provenance.writer_run_id)
        .with_for_update()
    )
    if final_artifact is None or writer_run is None:
        raise ReviewActionError("review_action_final_binding_missing")
    if final_artifact.run_id != writer_run.id or writer_run.locale_variant_id != locale_variant_id:
        raise ReviewActionError("review_action_final_binding_mismatch")
    final_content_json = final_artifact.content_json
    if not isinstance(final_content_json, dict):
        raise ReviewActionError("review_action_final_content_invalid")

    existing_decisions = list(
        (
            await session.scalars(
                select(Approval).where(
                    Approval.run_id == writer_run.id,
                    Approval.step_key == "final_review",
                    Approval.artifact_id == final_artifact.id,
                )
            )
        ).all()
    )
    if existing_decisions:
        if len(existing_decisions) != 1:
            raise ReviewActionError("review_action_decision_conflict")
        existing = existing_decisions[0]
        if existing.decision != decision or existing.comment != normalized_comment:
            raise ReviewActionError("review_action_decision_conflict")
        version: ContentVersion | None = None
        if decision == "approved":
            if panel.content_item_id is None:
                raise ReviewActionError("review_action_content_item_missing")
            version = await _existing_version(
                session,
                content_item_id=panel.content_item_id,
                final_artifact_id=final_artifact.id,
            )
            if version is None:
                raise ReviewActionError("review_action_partial_approved_state")
        return ReviewDecisionResult(
            content_case_id=content_case_id,
            locale_variant_id=locale_variant_id,
            decision=decision,
            approval_id=existing.id,
            writer_run_id=writer_run.id,
            writer_run_status=writer_run.status,
            content_version_id=version.id if version else None,
            content_version_no=version.version_no if version else None,
            replayed=True,
        )

    if panel.next_action != "AWAITING_FOUNDER_APPROVAL":
        raise ReviewActionError("review_action_not_awaiting_founder")
    if writer_run.status != "waiting_approval":
        raise ReviewActionError("review_action_run_state_invalid")

    approval = await resolve_approval(
        session,
        run_id=writer_run.id,
        step_key="final_review",
        artifact_id=final_artifact.id,
        decision=decision,
        actor_id=actor_id.strip(),
        comment=normalized_comment,
    )

    version = None
    if decision == "approved":
        if panel.content_item_id is None:
            raise ReviewActionError("review_action_content_item_missing")
        item = await session.get(ContentItem, panel.content_item_id)
        if item is None or item.locale_variant_id != locale_variant_id:
            raise ReviewActionError("review_action_content_item_missing")
        version = await _existing_version(
            session,
            content_item_id=item.id,
            final_artifact_id=final_artifact.id,
        )
        if version is None:
            version = await create_next_content_version(
                session,
                content_item_id=item.id,
                change_reason="Founder approved from Review Console",
                content_json=final_content_json,
                status="approved",
                created_by_run_id=writer_run.id,
                final_artifact_id=final_artifact.id,
            )
        await transition_run(session, run_id=writer_run.id, status="completed")
        await session.refresh(writer_run)
    else:
        await session.refresh(writer_run)

    return ReviewDecisionResult(
        content_case_id=content_case_id,
        locale_variant_id=locale_variant_id,
        decision=decision,
        approval_id=approval.id,
        writer_run_id=writer_run.id,
        writer_run_status=writer_run.status,
        content_version_id=version.id if version else None,
        content_version_no=version.version_no if version else None,
    )
