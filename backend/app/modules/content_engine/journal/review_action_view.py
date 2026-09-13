"""Action-aware projection layered over the proven T05.20A read model."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.review_console import (
    ReviewApprovalRef,
    ReviewCaseDetail,
    ReviewCaseSummary,
    ReviewLocalePanel,
    ReviewLocaleSummary,
    get_review_case,
)
from app.modules.content_engine.models import ContentCase
from app.modules.harness.models import Approval


def _raw_quality(panel: ReviewLocalePanel) -> str:
    audit = panel.assertion_audit
    source_copy = panel.source_copy
    if (
        audit.result == "fail"
        or audit.critical_unsupported_count > 0
        or audit.critical_contradicted_count > 0
        or source_copy.result == "fail"
        or source_copy.fail_count > 0
    ):
        return "FAIL"
    if audit.result == "pending" or source_copy.result == "pending":
        return "PENDING"
    if (
        audit.result == "warn"
        or source_copy.result == "warn"
        or source_copy.warn_count > 0
    ):
        return "WARN"
    return "PASS"


def _aggregate(locales: list[ReviewLocalePanel]) -> tuple[str, str, str, str, str]:
    if not locales:
        return (
            "PENDING",
            "NOT_PUBLISHED",
            "CONSISTENT",
            "NOT_READY",
            "Không có biến thể ngôn ngữ",
        )
    published = any(panel.publication_state == "PUBLISHED" for panel in locales)
    publication = "PUBLISHED" if published else "NOT_PUBLISHED"
    if any(panel.consistency_state == "INCONSISTENT" for panel in locales):
        return (
            "FAIL",
            publication,
            "INCONSISTENT",
            "INCONSISTENT_STATE",
            "Resolve conflicting persisted bindings",
        )
    qualities = {panel.quality_state for panel in locales}
    quality = (
        "FAIL"
        if "FAIL" in qualities
        else "PENDING"
        if "PENDING" in qualities
        else "WARN"
        if "WARN" in qualities
        else "PASS"
    )
    priority = (
        "QUALITY_BLOCKED",
        "AWAITING_FOUNDER_APPROVAL",
        "REVISION_REQUESTED",
        "REJECTED",
        "REVIEW_REQUIRED",
        "NOT_READY",
        "APPROVED_NOT_PUBLISHED",
        "PUBLISHED",
    )
    labels = {panel.next_action: panel.next_action_label for panel in locales}
    code = next((item for item in priority if item in labels), locales[0].next_action)
    return (
        quality,
        publication,
        "CONSISTENT",
        code,
        labels.get(code, locales[0].next_action_label),
    )


async def _apply_final_decisions(
    session: AsyncSession,
    detail: ReviewCaseDetail,
) -> ReviewCaseDetail:
    for panel in detail.locales:
        if panel.final_content is None:
            continue
        decisions = list(
            (
                await session.scalars(
                    select(Approval).where(
                        Approval.artifact_id == panel.final_content.id,
                        Approval.step_key == "final_review",
                    )
                )
            ).all()
        )
        if len(decisions) != 1 or decisions[0].decision == "approved":
            continue
        decision = decisions[0]
        remaining_issues = [
            issue
            for issue in panel.issues
            if issue != "conflicting_final_approval_state"
        ]
        if panel.content_version_status in {"approved", "published"}:
            remaining_issues.append("nonapproved_decision_has_active_content_version")
        panel.final_approval = ReviewApprovalRef(
            id=decision.id,
            decision=decision.decision,
            actor_id=decision.actor_id,
            comment=decision.comment,
        )
        panel.issues = remaining_issues
        panel.consistency_state = "INCONSISTENT" if remaining_issues else "CONSISTENT"
        panel.quality_state = "FAIL" if remaining_issues else _raw_quality(panel)
        if remaining_issues:
            panel.next_action = "INCONSISTENT_STATE"
            panel.next_action_label = "Resolve conflicting persisted bindings"
        elif decision.decision == "changes_requested":
            panel.next_action = "REVISION_REQUESTED"
            panel.next_action_label = "Founder đã yêu cầu sửa"
        else:
            panel.next_action = "REJECTED"
            panel.next_action_label = "Founder đã từ chối"

    if detail.issues:
        return detail
    quality, publication, consistency, action, label = _aggregate(detail.locales)
    detail.quality_state = quality
    detail.publication_state = publication
    detail.consistency_state = consistency
    detail.next_action = action
    detail.next_action_label = label
    return detail


async def get_action_aware_review_case(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> ReviewCaseDetail:
    detail = await get_review_case(session, content_case_id=content_case_id)
    return await _apply_final_decisions(session, detail)


async def list_action_aware_review_cases(
    session: AsyncSession,
) -> list[ReviewCaseSummary]:
    case_ids = list(
        (
            await session.scalars(
                select(ContentCase.id)
                .where(ContentCase.content_type == "journal")
                .order_by(ContentCase.created_at, ContentCase.id)
            )
        ).all()
    )
    summaries: list[ReviewCaseSummary] = []
    for content_case_id in case_ids:
        detail = await get_action_aware_review_case(
            session,
            content_case_id=content_case_id,
        )
        summaries.append(
            ReviewCaseSummary(
                id=detail.id,
                status=detail.status,
                content_type=detail.content_type,
                opportunity_question=detail.opportunity_question,
                opportunity_decision=detail.opportunity_decision,
                locales=[
                    ReviewLocaleSummary(
                        locale_variant_id=panel.locale_variant_id,
                        locale=panel.locale,
                        content_item_id=panel.content_item_id,
                        canonical_key=panel.canonical_key,
                        content_item_status=panel.content_item_status,
                        content_version_id=panel.content_version_id,
                        content_version_no=panel.content_version_no,
                        content_version_status=panel.content_version_status,
                        writer_run_status=panel.provenance.writer_run_status,
                        final_approval_present=panel.final_approval is not None,
                        quality_state=panel.quality_state,
                        publication_state=panel.publication_state,
                        consistency_state=panel.consistency_state,
                        next_action=panel.next_action,
                        next_action_label=panel.next_action_label,
                    )
                    for panel in detail.locales
                ],
                quality_state=detail.quality_state,
                publication_state=detail.publication_state,
                consistency_state=detail.consistency_state,
                next_action=detail.next_action,
                next_action_label=detail.next_action_label,
            )
        )
    return summaries


__all__ = ["get_action_aware_review_case", "list_action_aware_review_cases"]
