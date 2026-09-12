"""Read-only operator review model for persisted Journal state."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.models import AngleApproval, OutlineApproval
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
)
from app.modules.harness.models import Approval, Artifact, ContentRun, QualityEvaluation


class ReviewConsoleError(ValueError):
    """Raised when a Journal review representation cannot be resolved safely."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class ReviewArtifactRef(BaseModel):
    id: UUID
    artifact_type: str
    version: int
    content_hash: str
    locale: str | None = None


class ReviewApprovalRef(BaseModel):
    id: UUID
    decision: str
    actor_id: str
    comment: str | None = None


class ReviewArticleSection(BaseModel):
    section_id: str
    heading: str
    body_markdown: str


class ReviewArticle(BaseModel):
    title: str
    standfirst: str
    lead_markdown: str
    sections: list[ReviewArticleSection]
    closing_markdown: str


class ReviewAuditState(BaseModel):
    artifact: ReviewArtifactRef | None = None
    quality_evaluation_id: UUID | None = None
    result: str = "pending"
    critical_unsupported_count: int = 0
    critical_contradicted_count: int = 0
    unsupported_count: int = 0
    contradicted_count: int = 0


class ReviewSourceCopyState(BaseModel):
    artifact: ReviewArtifactRef | None = None
    quality_evaluation_id: UUID | None = None
    result: str = "pending"
    fail_count: int = 0
    warn_count: int = 0
    finding_count: int = 0
    max_overlap_tokens: int = 0
    findings: list[dict[str, Any]] = Field(default_factory=list)


class ReviewProvenance(BaseModel):
    writer_run_id: UUID | None = None
    writer_run_status: str | None = None
    source_draft: ReviewArtifactRef | None = None
    final_content: ReviewArtifactRef | None = None
    content_version_id: UUID | None = None
    content_version_no: int | None = None
    content_version_status: str | None = None


class ReviewLocalePanel(BaseModel):
    locale_variant_id: UUID
    locale: str
    locale_status: str
    content_item_id: UUID | None = None
    canonical_key: str | None = None
    content_item_status: str | None = None
    content_version_id: UUID | None = None
    content_version_no: int | None = None
    content_version_status: str | None = None
    final_content: ReviewArtifactRef | None = None
    article: ReviewArticle | None = None
    final_approval: ReviewApprovalRef | None = None
    assertion_audit: ReviewAuditState
    source_copy: ReviewSourceCopyState
    provenance: ReviewProvenance
    quality_state: str
    publication_state: str
    consistency_state: str
    issues: list[str] = Field(default_factory=list)
    next_action: str
    next_action_label: str


class ReviewLocaleSummary(BaseModel):
    locale_variant_id: UUID
    locale: str
    content_item_id: UUID | None = None
    canonical_key: str | None = None
    content_item_status: str | None = None
    content_version_id: UUID | None = None
    content_version_no: int | None = None
    content_version_status: str | None = None
    writer_run_status: str | None = None
    final_approval_present: bool
    quality_state: str
    publication_state: str
    consistency_state: str
    next_action: str
    next_action_label: str


class ReviewAngleLineage(BaseModel):
    artifact: ReviewArtifactRef
    approval_id: UUID
    selected_angle_id: str
    selected_working_title: str | None = None
    approved_by: str


class ReviewOutlineLineage(BaseModel):
    artifact: ReviewArtifactRef
    approval_id: UUID
    approved_by: str


class ReviewCaseSummary(BaseModel):
    id: UUID
    status: str
    content_type: str
    opportunity_question: str
    opportunity_decision: str
    locales: list[ReviewLocaleSummary]
    quality_state: str
    publication_state: str
    consistency_state: str
    next_action: str
    next_action_label: str


class ReviewCaseDetail(BaseModel):
    id: UUID
    status: str
    content_type: str
    opportunity_question: str
    opportunity_decision: str
    reader_before: str
    reader_after: str
    content_hypothesis: str
    angle: ReviewAngleLineage | None = None
    outline: ReviewOutlineLineage | None = None
    locales: list[ReviewLocalePanel]
    quality_state: str
    publication_state: str
    consistency_state: str
    issues: list[str] = Field(default_factory=list)
    next_action: str
    next_action_label: str


class _CaseRows:
    def __init__(
        self,
        *,
        content_case: ContentCase,
        opportunity: ContentOpportunity,
        variants: list[LocaleVariant],
        items: list[ContentItem],
        versions: list[ContentVersion],
        runs: list[ContentRun],
        artifacts: list[Artifact],
        approvals: list[Approval],
        evaluations: list[QualityEvaluation],
        angle_approvals: list[AngleApproval],
        outline_approvals: list[OutlineApproval],
    ) -> None:
        self.content_case = content_case
        self.opportunity = opportunity
        self.variants = variants
        self.items = items
        self.versions = versions
        self.runs = runs
        self.artifacts = artifacts
        self.approvals = approvals
        self.evaluations = evaluations
        self.angle_approvals = angle_approvals
        self.outline_approvals = outline_approvals
        self.run_by_id = {row.id: row for row in runs}
        self.artifact_by_id = {row.id: row for row in artifacts}


async def _load_case_rows(session: AsyncSession, content_case_id: UUID) -> _CaseRows:
    content_case = await session.get(ContentCase, content_case_id)
    if content_case is None or content_case.content_type != "journal":
        raise ReviewConsoleError("journal_review_case_not_found")
    opportunity = await session.get(ContentOpportunity, content_case.content_opportunity_id)
    if opportunity is None:
        raise ReviewConsoleError("journal_review_opportunity_missing")

    variants = list(
        (
            await session.scalars(
                select(LocaleVariant)
                .where(LocaleVariant.content_case_id == content_case.id)
                .order_by(LocaleVariant.locale, LocaleVariant.id)
            )
        ).all()
    )
    items = list(
        (
            await session.scalars(
                select(ContentItem)
                .where(ContentItem.content_case_id == content_case.id)
                .order_by(ContentItem.canonical_key, ContentItem.id)
            )
        ).all()
    )
    item_ids = [row.id for row in items]
    versions = (
        list(
            (
                await session.scalars(
                    select(ContentVersion)
                    .where(ContentVersion.content_item_id.in_(item_ids))
                    .order_by(
                        ContentVersion.content_item_id,
                        ContentVersion.version_no,
                        ContentVersion.id,
                    )
                )
            ).all()
        )
        if item_ids
        else []
    )
    runs = list(
        (
            await session.scalars(
                select(ContentRun)
                .where(ContentRun.content_case_id == content_case.id)
                .order_by(ContentRun.started_at, ContentRun.id)
            )
        ).all()
    )
    run_ids = [row.id for row in runs]
    artifacts = (
        list(
            (
                await session.scalars(
                    select(Artifact)
                    .where(Artifact.run_id.in_(run_ids))
                    .order_by(Artifact.created_at, Artifact.id)
                )
            ).all()
        )
        if run_ids
        else []
    )
    approvals = (
        list(
            (
                await session.scalars(
                    select(Approval)
                    .where(Approval.run_id.in_(run_ids))
                    .order_by(Approval.created_at, Approval.id)
                )
            ).all()
        )
        if run_ids
        else []
    )
    evaluations = (
        list(
            (
                await session.scalars(
                    select(QualityEvaluation)
                    .where(QualityEvaluation.run_id.in_(run_ids))
                    .order_by(QualityEvaluation.created_at, QualityEvaluation.id)
                )
            ).all()
        )
        if run_ids
        else []
    )
    angle_approvals = (
        list(
            (
                await session.scalars(
                    select(AngleApproval)
                    .where(AngleApproval.run_id.in_(run_ids))
                    .order_by(AngleApproval.approved_at, AngleApproval.id)
                )
            ).all()
        )
        if run_ids
        else []
    )
    outline_approvals = (
        list(
            (
                await session.scalars(
                    select(OutlineApproval)
                    .where(OutlineApproval.run_id.in_(run_ids))
                    .order_by(OutlineApproval.approved_at, OutlineApproval.id)
                )
            ).all()
        )
        if run_ids
        else []
    )
    return _CaseRows(
        content_case=content_case,
        opportunity=opportunity,
        variants=variants,
        items=items,
        versions=versions,
        runs=runs,
        artifacts=artifacts,
        approvals=approvals,
        evaluations=evaluations,
        angle_approvals=angle_approvals,
        outline_approvals=outline_approvals,
    )


def _artifact_ref(artifact: Artifact) -> ReviewArtifactRef:
    return ReviewArtifactRef(
        id=artifact.id,
        artifact_type=artifact.artifact_type,
        version=artifact.version,
        content_hash=artifact.content_hash,
        locale=artifact.locale,
    )


def _dict(value: object) -> dict[str, Any] | None:
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _int(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _article_from_artifact(artifact: Artifact | None) -> ReviewArticle | None:
    if artifact is None or not isinstance(artifact.content_json, dict):
        return None
    payload = cast(dict[str, Any], artifact.content_json)
    draft = _dict(payload.get("draft")) or payload
    title = draft.get("title")
    standfirst = draft.get("standfirst")
    lead = draft.get("lead_markdown")
    closing = draft.get("closing_markdown")
    raw_sections = draft.get("sections")
    if not all(isinstance(value, str) for value in (title, standfirst, lead, closing)):
        return None
    if not isinstance(raw_sections, list):
        return None
    sections: list[ReviewArticleSection] = []
    for raw in raw_sections:
        section = _dict(raw)
        if section is None:
            return None
        section_id = section.get("section_id")
        heading = section.get("heading")
        body = section.get("body_markdown")
        if not all(isinstance(value, str) for value in (section_id, heading, body)):
            return None
        sections.append(
            ReviewArticleSection(
                section_id=cast(str, section_id),
                heading=cast(str, heading),
                body_markdown=cast(str, body),
            )
        )
    return ReviewArticle(
        title=cast(str, title),
        standfirst=cast(str, standfirst),
        lead_markdown=cast(str, lead),
        sections=sections,
        closing_markdown=cast(str, closing),
    )


def _source_ref_matches(payload: dict[str, Any], source: Artifact) -> bool:
    raw = _dict(payload.get("source_draft"))
    return bool(
        raw
        and raw.get("id") == str(source.id)
        and raw.get("version") == source.version
        and raw.get("content_hash") == source.content_hash
    )


def _assertion_ref_matches(payload: dict[str, Any], audit: Artifact) -> bool:
    raw = _dict(payload.get("assertion_audit"))
    artifact = _dict(raw.get("artifact")) if raw else None
    return bool(
        artifact
        and artifact.get("id") == str(audit.id)
        and artifact.get("version") == audit.version
        and artifact.get("content_hash") == audit.content_hash
    )


def _quality_state(audit: ReviewAuditState, source_copy: ReviewSourceCopyState) -> str:
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


def _next_action(
    *,
    consistency_state: str,
    quality_state: str,
    final_artifact: Artifact | None,
    final_approval: Approval | None,
    version: ContentVersion | None,
    writer_run: ContentRun | None,
    has_review_output: bool,
) -> tuple[str, str]:
    if consistency_state == "INCONSISTENT":
        return "INCONSISTENT_STATE", "Resolve conflicting persisted bindings"
    if quality_state == "FAIL":
        return "QUALITY_BLOCKED", "Current bytes are blocked by quality gates"
    if final_artifact is not None and final_approval is None:
        return "AWAITING_FOUNDER_APPROVAL", "Awaiting Founder final approval"
    if version is not None and version.status == "published":
        return "PUBLISHED", "Published"
    if version is not None and version.status == "approved":
        return "APPROVED_NOT_PUBLISHED", "Approved; publishing not authorized"
    if has_review_output or (
        writer_run is not None and writer_run.status == "waiting_approval"
    ):
        return "REVIEW_REQUIRED", "Review current content"
    return "NOT_READY", "Content is not ready for review"


def _resolve_lineage(
    rows: _CaseRows,
) -> tuple[ReviewAngleLineage | None, ReviewOutlineLineage | None, list[str]]:
    issues: list[str] = []
    if len(rows.outline_approvals) > 1:
        return None, None, ["multiple_outline_approvals"]
    if len(rows.outline_approvals) == 0 and len(rows.angle_approvals) > 1:
        return None, None, ["multiple_angle_approvals"]

    outline_lineage: ReviewOutlineLineage | None = None
    angle_lineage: ReviewAngleLineage | None = None
    if len(rows.outline_approvals) == 1:
        approval = rows.outline_approvals[0]
        artifact = rows.artifact_by_id.get(approval.outline_artifact_id)
        if artifact is None:
            return None, None, ["approved_outline_artifact_missing"]
        outline_lineage = ReviewOutlineLineage(
            artifact=_artifact_ref(artifact),
            approval_id=approval.id,
            approved_by=approval.approved_by,
        )
        payload = _dict(artifact.content_json)
        approved_angle = _dict(payload.get("approved_angle")) if payload else None
        angle_artifact_ref = (
            _dict(approved_angle.get("artifact")) if approved_angle else None
        )
        angle_approval_ref = (
            _dict(approved_angle.get("approval")) if approved_angle else None
        )
        if angle_artifact_ref is None or angle_approval_ref is None:
            return None, outline_lineage, ["approved_outline_angle_binding_missing"]
        raw_angle_id = angle_artifact_ref.get("id")
        raw_approval_id = angle_approval_ref.get("id")
        try:
            angle_artifact_id = UUID(cast(str, raw_angle_id))
            angle_approval_id = UUID(cast(str, raw_approval_id))
        except (TypeError, ValueError):
            return None, outline_lineage, ["approved_outline_angle_binding_invalid"]
        angle_artifact = rows.artifact_by_id.get(angle_artifact_id)
        angle_approval = next(
            (row for row in rows.angle_approvals if row.id == angle_approval_id),
            None,
        )
        if angle_artifact is None or angle_approval is None:
            return None, outline_lineage, ["approved_angle_binding_not_found"]

        title: str | None = None
        angle_payload = _dict(angle_artifact.content_json)
        raw_candidates = angle_payload.get("candidates") if angle_payload else None
        if isinstance(raw_candidates, list):
            for raw in raw_candidates:
                candidate = _dict(raw)
                if candidate is None:
                    continue
                if candidate.get("angle_id") != angle_approval.selected_angle_id:
                    continue
                working_title = candidate.get("working_title")
                if isinstance(working_title, str):
                    title = working_title
                break
        angle_lineage = ReviewAngleLineage(
            artifact=_artifact_ref(angle_artifact),
            approval_id=angle_approval.id,
            selected_angle_id=angle_approval.selected_angle_id,
            selected_working_title=title,
            approved_by=angle_approval.approved_by,
        )
    elif len(rows.angle_approvals) == 1:
        approval = rows.angle_approvals[0]
        artifact = rows.artifact_by_id.get(approval.angle_artifact_id)
        if artifact is None:
            issues.append("approved_angle_artifact_missing")
        else:
            angle_lineage = ReviewAngleLineage(
                artifact=_artifact_ref(artifact),
                approval_id=approval.id,
                selected_angle_id=approval.selected_angle_id,
                approved_by=approval.approved_by,
            )
    return angle_lineage, outline_lineage, issues


def _current_version(rows: _CaseRows, item: ContentItem | None) -> ContentVersion | None:
    if item is None:
        return None
    active = [
        row
        for row in rows.versions
        if row.content_item_id == item.id and row.status in {"approved", "published"}
    ]
    if not active:
        return None
    return max(active, key=lambda row: (row.version_no, str(row.id)))


def _resolve_locale(rows: _CaseRows, variant: LocaleVariant) -> ReviewLocalePanel:
    issues: list[str] = []
    consistency_state = "CONSISTENT"
    variant_items = [row for row in rows.items if row.locale_variant_id == variant.id]
    if len(variant_items) > 1:
        consistency_state = "INCONSISTENT"
        issues.append("multiple_content_items_for_locale_variant")
    item = variant_items[0] if len(variant_items) == 1 else None
    version = _current_version(rows, item)

    final_artifact: Artifact | None = None
    if version is not None and version.final_artifact_id is not None:
        final_artifact = rows.artifact_by_id.get(version.final_artifact_id)
        if final_artifact is None or final_artifact.artifact_type != "final_content":
            consistency_state = "INCONSISTENT"
            issues.append("content_version_final_artifact_invalid")
            final_artifact = None
    elif item is not None:
        candidates = []
        for artifact in rows.artifacts:
            run = rows.run_by_id.get(artifact.run_id)
            if (
                artifact.artifact_type == "final_content"
                and artifact.locale == variant.locale
                and run is not None
                and run.locale_variant_id == variant.id
            ):
                candidates.append(artifact)
        if len(candidates) == 1:
            final_artifact = candidates[0]
        elif len(candidates) > 1:
            consistency_state = "INCONSISTENT"
            issues.append("multiple_unbound_final_content_artifacts")

    writer_run: ContentRun | None = None
    if version is not None and version.created_by_run_id is not None:
        writer_run = rows.run_by_id.get(version.created_by_run_id)
        if writer_run is None or writer_run.locale_variant_id != variant.id:
            consistency_state = "INCONSISTENT"
            issues.append("content_version_writer_run_invalid")
            writer_run = None
    elif final_artifact is not None:
        writer_run = rows.run_by_id.get(final_artifact.run_id)

    if version is not None and final_artifact is not None:
        if version.content_json != final_artifact.content_json:
            consistency_state = "INCONSISTENT"
            issues.append("content_version_final_content_payload_mismatch")
        if writer_run is not None and final_artifact.run_id != writer_run.id:
            consistency_state = "INCONSISTENT"
            issues.append("final_content_writer_run_mismatch")

    final_approval: Approval | None = None
    if final_artifact is not None:
        final_approvals = [
            approval
            for approval in rows.approvals
            if approval.artifact_id == final_artifact.id
            and approval.step_key == "final_review"
        ]
        if len(final_approvals) == 1 and final_approvals[0].decision == "approved":
            final_approval = final_approvals[0]
        elif len(final_approvals) > 1 or (
            len(final_approvals) == 1
            and final_approvals[0].decision != "approved"
        ):
            consistency_state = "INCONSISTENT"
            issues.append("conflicting_final_approval_state")
    if (
        version is not None
        and version.status in {"approved", "published"}
        and final_approval is None
    ):
        consistency_state = "INCONSISTENT"
        issues.append("content_version_missing_final_approval")

    source_draft: Artifact | None = None
    if writer_run is not None and final_artifact is not None:
        drafts = [
            artifact
            for artifact in rows.artifacts
            if artifact.run_id == writer_run.id
            and artifact.artifact_type == "journal_draft"
            and artifact.locale == variant.locale
            and artifact.content_hash == final_artifact.content_hash
        ]
        if len(drafts) == 1:
            source_draft = drafts[0]
        elif len(drafts) > 1:
            consistency_state = "INCONSISTENT"
            issues.append("multiple_source_drafts_for_final_bytes")

    audit = ReviewAuditState()
    audit_artifact: Artifact | None = None
    if source_draft is not None:
        audit_candidates: list[Artifact] = []
        for artifact in rows.artifacts:
            if (
                artifact.artifact_type != "assertion_audit"
                or artifact.locale != variant.locale
            ):
                continue
            payload = _dict(artifact.content_json)
            if payload is not None and _source_ref_matches(payload, source_draft):
                audit_candidates.append(artifact)
        if len(audit_candidates) == 1:
            audit_artifact = audit_candidates[0]
            payload = _dict(audit_artifact.content_json) or {}
            summary = _dict(payload.get("summary")) or {}
            qes = [
                row
                for row in rows.evaluations
                if row.artifact_id == audit_artifact.id
                and row.evaluator_key == "assertion_audit_hard_gate"
            ]
            if len(qes) != 1:
                consistency_state = "INCONSISTENT"
                issues.append("assertion_audit_quality_evaluation_missing_or_duplicate")
            else:
                qe = qes[0]
                audit = ReviewAuditState(
                    artifact=_artifact_ref(audit_artifact),
                    quality_evaluation_id=qe.id,
                    result=str(summary.get("result", qe.result)),
                    critical_unsupported_count=_int(
                        summary.get("critical_unsupported_count")
                    ),
                    critical_contradicted_count=_int(
                        summary.get("critical_contradicted_count")
                    ),
                    unsupported_count=_int(summary.get("unsupported_count")),
                    contradicted_count=_int(summary.get("contradicted_count")),
                )
        elif len(audit_candidates) > 1:
            consistency_state = "INCONSISTENT"
            issues.append("multiple_assertion_audits_for_final_bytes")

    source_copy = ReviewSourceCopyState()
    if source_draft is not None and audit_artifact is not None:
        copy_candidates: list[Artifact] = []
        for artifact in rows.artifacts:
            if (
                artifact.artifact_type != "source_copy_check"
                or artifact.locale != variant.locale
            ):
                continue
            payload = _dict(artifact.content_json)
            if (
                payload is not None
                and _source_ref_matches(payload, source_draft)
                and _assertion_ref_matches(payload, audit_artifact)
            ):
                copy_candidates.append(artifact)
        if len(copy_candidates) == 1:
            copy_artifact = copy_candidates[0]
            payload = _dict(copy_artifact.content_json) or {}
            summary = _dict(payload.get("summary")) or {}
            raw_findings = payload.get("findings")
            findings = (
                [
                    cast(dict[str, Any], row)
                    for row in raw_findings
                    if isinstance(row, dict)
                ]
                if isinstance(raw_findings, list)
                else []
            )
            qes = [
                row
                for row in rows.evaluations
                if row.artifact_id == copy_artifact.id
                and row.evaluator_key == "source_copy_basic_gate"
            ]
            if len(qes) != 1:
                consistency_state = "INCONSISTENT"
                issues.append("source_copy_quality_evaluation_missing_or_duplicate")
            else:
                qe = qes[0]
                source_copy = ReviewSourceCopyState(
                    artifact=_artifact_ref(copy_artifact),
                    quality_evaluation_id=qe.id,
                    result=str(summary.get("result", qe.result)),
                    fail_count=_int(summary.get("fail_count")),
                    warn_count=_int(summary.get("warn_count")),
                    finding_count=_int(summary.get("finding_count")),
                    max_overlap_tokens=_int(summary.get("max_overlap_tokens")),
                    findings=findings,
                )
        elif len(copy_candidates) > 1:
            consistency_state = "INCONSISTENT"
            issues.append("multiple_source_copy_checks_for_final_bytes")

    quality_state = _quality_state(audit, source_copy)
    if consistency_state == "INCONSISTENT":
        quality_state = "FAIL"
    publication_state = (
        "PUBLISHED"
        if version is not None and version.status == "published"
        else "NOT_PUBLISHED"
    )
    has_review_output = any(
        artifact.artifact_type == "journal_draft"
        and artifact.locale == variant.locale
        and (run := rows.run_by_id.get(artifact.run_id)) is not None
        and run.locale_variant_id == variant.id
        for artifact in rows.artifacts
    )
    next_action, next_action_label = _next_action(
        consistency_state=consistency_state,
        quality_state=quality_state,
        final_artifact=final_artifact,
        final_approval=final_approval,
        version=version,
        writer_run=writer_run,
        has_review_output=has_review_output,
    )
    return ReviewLocalePanel(
        locale_variant_id=variant.id,
        locale=variant.locale,
        locale_status=variant.status,
        content_item_id=item.id if item else None,
        canonical_key=item.canonical_key if item else None,
        content_item_status=item.status if item else None,
        content_version_id=version.id if version else None,
        content_version_no=version.version_no if version else None,
        content_version_status=version.status if version else None,
        final_content=_artifact_ref(final_artifact) if final_artifact else None,
        article=_article_from_artifact(final_artifact),
        final_approval=(
            ReviewApprovalRef(
                id=final_approval.id,
                decision=final_approval.decision,
                actor_id=final_approval.actor_id,
                comment=final_approval.comment,
            )
            if final_approval
            else None
        ),
        assertion_audit=audit,
        source_copy=source_copy,
        provenance=ReviewProvenance(
            writer_run_id=writer_run.id if writer_run else None,
            writer_run_status=writer_run.status if writer_run else None,
            source_draft=_artifact_ref(source_draft) if source_draft else None,
            final_content=_artifact_ref(final_artifact) if final_artifact else None,
            content_version_id=version.id if version else None,
            content_version_no=version.version_no if version else None,
            content_version_status=version.status if version else None,
        ),
        quality_state=quality_state,
        publication_state=publication_state,
        consistency_state=consistency_state,
        issues=issues,
        next_action=next_action,
        next_action_label=next_action_label,
    )


def _aggregate_locales(
    locales: list[ReviewLocalePanel],
) -> tuple[str, str, str, str, str]:
    if not locales:
        return (
            "PENDING",
            "NOT_PUBLISHED",
            "CONSISTENT",
            "NOT_READY",
            "No locale variants",
        )
    published = any(panel.publication_state == "PUBLISHED" for panel in locales)
    if any(panel.consistency_state == "INCONSISTENT" for panel in locales):
        return (
            "FAIL",
            "PUBLISHED" if published else "NOT_PUBLISHED",
            "INCONSISTENT",
            "INCONSISTENT_STATE",
            "Resolve conflicting persisted bindings",
        )
    quality_values = {panel.quality_state for panel in locales}
    quality_state = (
        "FAIL"
        if "FAIL" in quality_values
        else "PENDING"
        if "PENDING" in quality_values
        else "WARN"
        if "WARN" in quality_values
        else "PASS"
    )
    publication_state = "PUBLISHED" if published else "NOT_PUBLISHED"
    priority = (
        "QUALITY_BLOCKED",
        "AWAITING_FOUNDER_APPROVAL",
        "REVIEW_REQUIRED",
        "NOT_READY",
        "APPROVED_NOT_PUBLISHED",
        "PUBLISHED",
    )
    by_code = {panel.next_action: panel.next_action_label for panel in locales}
    next_action = next(
        (code for code in priority if code in by_code),
        locales[0].next_action,
    )
    return (
        quality_state,
        publication_state,
        "CONSISTENT",
        next_action,
        by_code.get(next_action, locales[0].next_action_label),
    )


async def get_review_case(
    session: AsyncSession,
    *,
    content_case_id: UUID,
) -> ReviewCaseDetail:
    rows = await _load_case_rows(session, content_case_id)
    panels = [_resolve_locale(rows, variant) for variant in rows.variants]
    quality, publication, consistency, next_action, next_label = _aggregate_locales(
        panels
    )
    angle, outline, lineage_issues = _resolve_lineage(rows)
    if lineage_issues:
        quality = "FAIL"
        consistency = "INCONSISTENT"
        next_action = "INCONSISTENT_STATE"
        next_label = "Resolve conflicting persisted bindings"
    return ReviewCaseDetail(
        id=rows.content_case.id,
        status=rows.content_case.status,
        content_type=rows.content_case.content_type,
        opportunity_question=rows.opportunity.question,
        opportunity_decision=rows.opportunity.decision,
        reader_before=rows.content_case.reader_before,
        reader_after=rows.content_case.reader_after,
        content_hypothesis=rows.content_case.content_hypothesis,
        angle=angle,
        outline=outline,
        locales=panels,
        quality_state=quality,
        publication_state=publication,
        consistency_state=consistency,
        issues=lineage_issues,
        next_action=next_action,
        next_action_label=next_label,
    )


async def list_review_cases(session: AsyncSession) -> list[ReviewCaseSummary]:
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
        detail = await get_review_case(session, content_case_id=content_case_id)
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


__all__ = [
    "ReviewCaseDetail",
    "ReviewCaseSummary",
    "ReviewConsoleError",
    "get_review_case",
    "list_review_cases",
]
