from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.journal.models import AngleApproval, OutlineApproval
from app.modules.content_engine.journal.review_console import (
    get_review_case,
    list_review_cases,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
    NeedHypothesis,
    Project,
    SettingsSnapshot,
)
from app.modules.harness.models import Approval, Artifact, ContentRun, QualityEvaluation


@asynccontextmanager
async def isolated_session():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _draft(locale: str) -> dict[str, object]:
    title = (
        "Mức giá của tác phẩm"
        if locale == "vi-VN"
        else "What an Artwork Price Can Tell You"
    )
    return {
        "schema_version": 1,
        "draft": {
            "locale": locale,
            "title": title,
            "standfirst": "Read price as context.",
            "lead_markdown": "Price is one part of the context.",
            "sections": [
                {
                    "section_id": "price-as-context",
                    "heading": "Price as context",
                    "body_markdown": "Use price as context, not a verdict.",
                    "evidence_refs": [],
                    "originality_refs": [],
                    "unresolved_factual_claims": [],
                }
            ],
            "closing_markdown": "Check what you can verify.",
            "lead_evidence_refs": [],
            "lead_originality_refs": [],
            "internal_link_intents": [],
            "unresolved_factual_claims": [],
        },
    }


@dataclass
class ReviewFixture:
    content_case: ContentCase
    variants: dict[str, LocaleVariant]
    items: dict[str, ContentItem]
    versions: dict[str, ContentVersion]
    writer_runs: dict[str, ContentRun]
    source_drafts: dict[str, Artifact]
    final_artifacts: dict[str, Artifact]
    final_approvals: dict[str, Approval]
    current_audits: dict[str, Artifact]
    source_copies: dict[str, Artifact]


async def _base_case(
    session: AsyncSession,
) -> tuple[Project, ContentCase, ContentOpportunity]:
    project = Project(slug=f"review-{uuid4().hex[:8]}", name="Review fixture")
    session.add(project)
    await session.flush()
    hypothesis = NeedHypothesis(
        project_id=project.id,
        type="pain",
        statement="Buyer wants price context.",
        audience_scope="first-time buyers",
        situation="considering original art",
        origin="founder_proposed",
    )
    session.add(hypothesis)
    await session.flush()
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=hypothesis.id,
        locale="en",
        reader="first-time buyer",
        situation="looking at an artwork price",
        need="understand price context",
        question="What can an artwork price tell me?",
        intent="evaluate",
        promise="Read price as context.",
        what_is_actually_new="A calm first-buyer framing.",
        next_discovery_step="Verify current artwork details.",
        decision="CREATE",
        priority="NOW",
        suggested_content_type="journal",
        suggested_role="cluster",
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=hypothesis.id,
        content_opportunity_id=opportunity.id,
        desired_action="Evaluate calmly.",
        content_hypothesis="Context reduces uncertainty.",
        originality_statement="No universal pricing formula.",
        reader_before="Price feels like a verdict.",
        reader_after="Price becomes one contextual input.",
    )
    session.add(content_case)
    await session.flush()
    return project, content_case, opportunity


async def _persist_lineage(
    session: AsyncSession,
    *,
    project: Project,
    content_case: ContentCase,
    snapshot: SettingsSnapshot,
    variant: LocaleVariant,
) -> None:
    source_run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        run_mode="create",
        status="waiting_approval",
        current_step="outline",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(source_run)
    await session.flush()
    angle_payload = {
        "artifact_type": "angle_candidates",
        "candidates": [
            {
                "angle_id": "angle-01",
                "working_title": "What an Artwork Price Can—and Can’t—Tell You",
            }
        ],
    }
    angle = Artifact(
        run_id=source_run.id,
        artifact_type="angle_candidates",
        locale="en",
        version=1,
        content_json=angle_payload,
        content_hash=_hash(angle_payload),
    )
    session.add(angle)
    await session.flush()
    angle_approval = AngleApproval(
        run_id=source_run.id,
        angle_artifact_id=angle.id,
        angle_artifact_version=1,
        angle_artifact_hash=angle.content_hash,
        selected_angle_id="angle-01",
        selected_candidate_hash="b" * 64,
        approved_by="founder",
        approval_reason="fixture",
        approved_at=datetime.now(UTC),
    )
    session.add(angle_approval)
    await session.flush()
    outline_payload = {
        "artifact_type": "journal_outline",
        "approved_angle": {
            "artifact": {
                "id": str(angle.id),
                "version": angle.version,
                "content_hash": angle.content_hash,
            },
            "approval": {
                "id": str(angle_approval.id),
                "selected_angle_id": angle_approval.selected_angle_id,
                "selected_candidate_hash": angle_approval.selected_candidate_hash,
            },
        },
    }
    outline = Artifact(
        run_id=source_run.id,
        artifact_type="journal_outline",
        locale="en",
        version=1,
        content_json=outline_payload,
        content_hash=_hash(outline_payload),
    )
    session.add(outline)
    await session.flush()
    session.add(
        OutlineApproval(
            run_id=source_run.id,
            outline_artifact_id=outline.id,
            outline_artifact_version=1,
            outline_artifact_hash=outline.content_hash,
            approved_by="founder",
            approval_reason="fixture",
            approved_at=datetime.now(UTC),
        )
    )


async def _persist_quality(
    session: AsyncSession,
    *,
    project: Project,
    content_case: ContentCase,
    snapshot: SettingsSnapshot,
    variant: LocaleVariant,
    item: ContentItem,
    writer_run: ContentRun,
    source_draft: Artifact,
) -> tuple[Artifact, Artifact]:
    old_payload = _draft(variant.locale)
    old_draft_payload = old_payload["draft"]
    assert isinstance(old_draft_payload, dict)
    old_draft_payload["title"] = "Old failed draft"
    old_draft = Artifact(
        run_id=writer_run.id,
        artifact_type="journal_draft",
        locale=variant.locale,
        version=1,
        content_json=old_payload,
        content_hash=_hash(old_payload),
    )
    session.add(old_draft)
    await session.flush()
    old_run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_item_id=item.id,
        run_mode="eval",
        status="completed",
        current_step="assertion_audit",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    session.add(old_run)
    await session.flush()
    old_audit_payload = {
        "source_draft": {
            "id": str(old_draft.id),
            "version": old_draft.version,
            "content_hash": old_draft.content_hash,
        },
        "summary": {
            "result": "fail",
            "critical_unsupported_count": 1,
            "critical_contradicted_count": 0,
            "unsupported_count": 1,
            "contradicted_count": 0,
        },
    }
    old_audit = Artifact(
        run_id=old_run.id,
        artifact_type="assertion_audit",
        locale=variant.locale,
        version=1,
        content_json=old_audit_payload,
        content_hash=_hash(old_audit_payload),
    )
    session.add(old_audit)
    await session.flush()
    session.add(
        QualityEvaluation(
            run_id=old_run.id,
            artifact_id=old_audit.id,
            evaluator_key="assertion_audit_hard_gate",
            evaluator_version="ce05.assertion_audit.hard_gate.v5",
            evaluator_type="deterministic",
            result="fail",
            severity="critical",
            findings_json={"fixture": True},
        )
    )

    audit_run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_item_id=item.id,
        run_mode="eval",
        status="completed",
        current_step="assertion_audit",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    session.add(audit_run)
    await session.flush()
    audit_payload = {
        "source_draft": {
            "id": str(source_draft.id),
            "version": source_draft.version,
            "content_hash": source_draft.content_hash,
        },
        "summary": {
            "result": "pass",
            "critical_unsupported_count": 0,
            "critical_contradicted_count": 0,
            "unsupported_count": 0,
            "contradicted_count": 0,
        },
    }
    audit = Artifact(
        run_id=audit_run.id,
        artifact_type="assertion_audit",
        locale=variant.locale,
        version=1,
        content_json=audit_payload,
        content_hash=_hash(audit_payload),
    )
    session.add(audit)
    await session.flush()
    session.add(
        QualityEvaluation(
            run_id=audit_run.id,
            artifact_id=audit.id,
            evaluator_key="assertion_audit_hard_gate",
            evaluator_version="ce05.assertion_audit.hard_gate.v5",
            evaluator_type="deterministic",
            result="pass",
            severity="none",
            findings_json={"fixture": True},
        )
    )

    copy_run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_item_id=item.id,
        run_mode="eval",
        status="completed",
        current_step="source_copy_check",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    session.add(copy_run)
    await session.flush()
    findings: list[dict[str, object]] = []
    if variant.locale == "en":
        first_match = "by the same artist, and the state of the"
        second_match = "oversize or special handling may require a quote"
        findings = [
            {
                "draft_segment_id": "section:condition-and-context:1",
                "draft_location": "section:condition-and-context",
                "draft_text": f"{first_match} market",
                "source_kind": "evidence_excerpt",
                "source_ref": "evidence:fixture",
                "source_field": "evidence_excerpt",
                "source_text_hash": "c" * 64,
                "matched_draft_span": {
                    "start": 0,
                    "end": 45,
                    "text": first_match,
                },
                "matched_source_span": {
                    "start": 0,
                    "end": 45,
                    "text": first_match,
                },
                "normalized_match": "by the same artist and the state of the",
                "overlap_token_count": 9,
                "classification": "warn",
                "locale": "en",
            },
            {
                "draft_segment_id": "section:practical-costs:2",
                "draft_location": "section:practical-costs",
                "draft_text": second_match,
                "source_kind": "originality_material",
                "source_ref": "originality:fixture",
                "source_field": "material",
                "source_text_hash": "d" * 64,
                "matched_draft_span": {
                    "start": 0,
                    "end": 48,
                    "text": second_match,
                },
                "matched_source_span": {
                    "start": 0,
                    "end": 48,
                    "text": second_match,
                },
                "normalized_match": second_match,
                "overlap_token_count": 8,
                "classification": "warn",
                "locale": "en",
            },
        ]
    copy_summary = {
        "result": "warn" if findings else "pass",
        "finding_count": len(findings),
        "warn_count": len(findings),
        "fail_count": 0,
        "max_overlap_tokens": 9 if findings else 0,
    }
    copy_payload = {
        "source_draft": {
            "id": str(source_draft.id),
            "version": source_draft.version,
            "content_hash": source_draft.content_hash,
        },
        "assertion_audit": {
            "artifact": {
                "id": str(audit.id),
                "version": audit.version,
                "content_hash": audit.content_hash,
            }
        },
        "summary": copy_summary,
        "findings": findings,
    }
    source_copy = Artifact(
        run_id=copy_run.id,
        artifact_type="source_copy_check",
        locale=variant.locale,
        version=1,
        content_json=copy_payload,
        content_hash=_hash(copy_payload),
    )
    session.add(source_copy)
    await session.flush()
    session.add(
        QualityEvaluation(
            run_id=copy_run.id,
            artifact_id=source_copy.id,
            evaluator_key="source_copy_basic_gate",
            evaluator_version="ce05.source_copy.basic_gate.v2",
            evaluator_type="deterministic",
            result=copy_summary["result"],
            severity="medium" if findings else "none",
            findings_json={"fixture": True},
        )
    )
    return audit, source_copy


async def _approved_fixture(session: AsyncSession) -> ReviewFixture:
    project, content_case, _opportunity = await _base_case(session)
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={"models": {}},
        source_version_refs_json=["fixture"],
        content_hash="a" * 64,
    )
    session.add(snapshot)
    await session.flush()

    variants: dict[str, LocaleVariant] = {}
    for locale in ("vi-VN", "en"):
        variant = LocaleVariant(
            content_case_id=content_case.id,
            locale=locale,
            content_role="cluster",
            primary_question="What can an artwork price tell me?",
            primary_intent="evaluate",
        )
        session.add(variant)
        await session.flush()
        variants[locale] = variant
    await _persist_lineage(
        session,
        project=project,
        content_case=content_case,
        snapshot=snapshot,
        variant=variants["en"],
    )

    items: dict[str, ContentItem] = {}
    versions: dict[str, ContentVersion] = {}
    writer_runs: dict[str, ContentRun] = {}
    source_drafts: dict[str, Artifact] = {}
    final_artifacts: dict[str, Artifact] = {}
    final_approvals: dict[str, Approval] = {}
    current_audits: dict[str, Artifact] = {}
    source_copies: dict[str, Artifact] = {}

    for locale in ("vi-VN", "en"):
        variant = variants[locale]
        item = ContentItem(
            project_id=project.id,
            content_case_id=content_case.id,
            locale_variant_id=variant.id,
            content_type="journal",
            canonical_key=f"journal:{content_case.id}:{locale}",
        )
        session.add(item)
        await session.flush()
        items[locale] = item
        writer_run = ContentRun(
            project_id=project.id,
            content_case_id=content_case.id,
            locale_variant_id=variant.id,
            content_item_id=item.id,
            run_mode="create",
            status="completed",
            current_step="final_review",
            settings_snapshot_id=snapshot.id,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        session.add(writer_run)
        await session.flush()
        writer_runs[locale] = writer_run
        draft_payload = _draft(locale)
        draft_hash = _hash(draft_payload)
        source_draft = Artifact(
            run_id=writer_run.id,
            artifact_type="journal_draft",
            locale=locale,
            version=3 if locale == "vi-VN" else 4,
            content_json=draft_payload,
            content_hash=draft_hash,
        )
        final_artifact = Artifact(
            run_id=writer_run.id,
            artifact_type="final_content",
            locale=locale,
            version=1,
            content_json=draft_payload,
            content_hash=draft_hash,
        )
        session.add_all([source_draft, final_artifact])
        await session.flush()
        source_drafts[locale] = source_draft
        final_artifacts[locale] = final_artifact
        version = ContentVersion(
            content_item_id=item.id,
            version_no=1,
            final_artifact_id=final_artifact.id,
            change_reason="Founder-approved final content",
            status="approved",
            content_json=draft_payload,
            created_by_run_id=writer_run.id,
        )
        session.add(version)
        await session.flush()
        versions[locale] = version
        final_approval = Approval(
            run_id=writer_run.id,
            step_key="final_review",
            artifact_id=final_artifact.id,
            decision="approved",
            actor_id="founder",
            comment="Approved exact bytes.",
        )
        session.add(final_approval)
        await session.flush()
        final_approvals[locale] = final_approval
        audit, source_copy = await _persist_quality(
            session,
            project=project,
            content_case=content_case,
            snapshot=snapshot,
            variant=variant,
            item=item,
            writer_run=writer_run,
            source_draft=source_draft,
        )
        current_audits[locale] = audit
        source_copies[locale] = source_copy

    await session.flush()
    return ReviewFixture(
        content_case=content_case,
        variants=variants,
        items=items,
        versions=versions,
        writer_runs=writer_runs,
        source_drafts=source_drafts,
        final_artifacts=final_artifacts,
        final_approvals=final_approvals,
        current_audits=current_audits,
        source_copies=source_copies,
    )


@pytest.mark.asyncio
async def test_review_detail_resolves_current_bilingual_final_state_and_warnings() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        detail = await get_review_case(session, content_case_id=fixture.content_case.id)
        assert [panel.locale for panel in detail.locales] == ["en", "vi-VN"]
        by_locale = {panel.locale: panel for panel in detail.locales}
        assert by_locale["vi-VN"].content_version_id == fixture.versions["vi-VN"].id
        assert by_locale["en"].content_version_id == fixture.versions["en"].id
        assert by_locale["en"].final_content is not None
        assert by_locale["en"].final_content.id == fixture.final_artifacts["en"].id
        assert by_locale["en"].article is not None
        assert by_locale["en"].article.title == "What an Artwork Price Can Tell You"
        assert by_locale["vi-VN"].quality_state == "PASS"
        assert by_locale["en"].quality_state == "WARN"
        assert by_locale["en"].source_copy.warn_count == 2
        overlaps = [
            finding["overlap_token_count"]
            for finding in by_locale["en"].source_copy.findings
        ]
        assert overlaps == [9, 8]
        assert detail.next_action == "APPROVED_NOT_PUBLISHED"
        assert detail.publication_state == "NOT_PUBLISHED"
        assert detail.angle is not None
        assert detail.angle.selected_angle_id == "angle-01"
        assert detail.outline is not None


@pytest.mark.asyncio
async def test_review_detail_does_not_surface_older_failed_audit() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        detail = await get_review_case(session, content_case_id=fixture.content_case.id)
        by_locale = {panel.locale: panel for panel in detail.locales}
        assert by_locale["en"].assertion_audit.artifact is not None
        assert (
            by_locale["en"].assertion_audit.artifact.id
            == fixture.current_audits["en"].id
        )
        assert by_locale["en"].assertion_audit.result == "pass"
        assert by_locale["en"].assertion_audit.critical_unsupported_count == 0


@pytest.mark.asyncio
async def test_review_pending_case_without_content_item_is_bounded() -> None:
    async with isolated_session() as session:
        _project, content_case, _opportunity = await _base_case(session)
        session.add(
            LocaleVariant(
                content_case_id=content_case.id,
                locale="en",
                content_role="cluster",
                primary_question="What can an artwork price tell me?",
                primary_intent="evaluate",
            )
        )
        await session.flush()
        detail = await get_review_case(session, content_case_id=content_case.id)
        assert len(detail.locales) == 1
        panel = detail.locales[0]
        assert panel.content_item_id is None
        assert panel.article is None
        assert panel.quality_state == "PENDING"
        assert panel.next_action == "NOT_READY"


@pytest.mark.asyncio
async def test_review_conflicting_final_approval_fails_closed() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        en = fixture.final_artifacts["en"]
        session.add(
            Approval(
                run_id=fixture.writer_runs["en"].id,
                step_key="final_review",
                artifact_id=en.id,
                decision="rejected",
                actor_id="founder",
                comment="conflict fixture",
            )
        )
        await session.flush()
        detail = await get_review_case(session, content_case_id=fixture.content_case.id)
        en_panel = next(panel for panel in detail.locales if panel.locale == "en")
        assert en_panel.consistency_state == "INCONSISTENT"
        assert en_panel.next_action == "INCONSISTENT_STATE"
        assert detail.consistency_state == "INCONSISTENT"
        assert detail.next_action == "INCONSISTENT_STATE"


@pytest.mark.asyncio
async def test_review_approved_version_without_final_approval_fails_closed() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        approval = fixture.final_approvals["en"]
        await session.execute(delete(Approval).where(Approval.id == approval.id))
        await session.flush()
        detail = await get_review_case(session, content_case_id=fixture.content_case.id)
        en_panel = next(panel for panel in detail.locales if panel.locale == "en")
        assert en_panel.consistency_state == "INCONSISTENT"
        assert "content_version_missing_final_approval" in en_panel.issues
        assert en_panel.next_action == "INCONSISTENT_STATE"


@pytest.mark.asyncio
async def test_review_list_is_small_and_uses_derived_summary() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        summaries = await list_review_cases(session)
        summary = next(row for row in summaries if row.id == fixture.content_case.id)
        assert summary.quality_state == "WARN"
        assert summary.publication_state == "NOT_PUBLISHED"
        assert summary.next_action == "APPROVED_NOT_PUBLISHED"
        assert len(summary.locales) == 2


@pytest.mark.asyncio
async def test_review_reads_do_not_change_row_counts() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        models: tuple[type[object], ...] = (
            ContentRun,
            Artifact,
            Approval,
            QualityEvaluation,
            ContentItem,
            ContentVersion,
        )
        before = {
            model.__name__: int(
                await session.scalar(select(func.count()).select_from(model)) or 0
            )
            for model in models
        }
        await get_review_case(session, content_case_id=fixture.content_case.id)
        await list_review_cases(session)
        after = {
            model.__name__: int(
                await session.scalar(select(func.count()).select_from(model)) or 0
            )
            for model in models
        }
        assert after == before
