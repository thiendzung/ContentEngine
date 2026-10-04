from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import func, select
from test_ce05_review_console import (
    _approved_fixture,
    _base_case,
    _draft,
    _hash,
    _persist_lineage,
    _persist_quality,
    isolated_session,
)

from app.modules.content_engine.journal.review_action_view import get_action_aware_review_case
from app.modules.content_engine.journal.review_actions import (
    ReviewActionError,
    submit_review_decision,
)
from app.modules.content_engine.models import (
    ContentItem,
    ContentVersion,
    LocaleVariant,
    SettingsSnapshot,
)
from app.modules.harness.models import (
    Approval,
    Artifact,
    ContentRun,
    QualityEvaluation,
    StepRun,
)
from app.modules.harness.persistence import pause_for_approval


@dataclass
class PendingReviewFixture:
    content_case_id: UUID
    variant: LocaleVariant
    writer_run: ContentRun
    source_draft: Artifact
    final_artifact: Artifact


async def _pending_fixture(session) -> PendingReviewFixture:
    project, content_case, _opportunity = await _base_case(session)
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={"models": {}},
        source_version_refs_json=["fixture"],
        content_hash="a" * 64,
    )
    session.add(snapshot)
    await session.flush()

    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="cluster",
        primary_question="What can an artwork price tell me?",
        primary_intent="evaluate",
    )
    session.add(variant)
    await session.flush()
    await _persist_lineage(
        session,
        project=project,
        content_case=content_case,
        snapshot=snapshot,
        variant=variant,
    )

    item = ContentItem(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_type="journal",
        canonical_key=f"journal:{content_case.id}:en",
    )
    session.add(item)
    await session.flush()

    writer_run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_item_id=item.id,
        run_mode="create",
        status="running",
        current_step="final_review",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(writer_run)
    await session.flush()

    draft_payload = _draft("en")
    draft_hash = _hash(draft_payload)
    source_draft = Artifact(
        run_id=writer_run.id,
        artifact_type="journal_draft",
        locale="en",
        version=4,
        content_json=draft_payload,
        content_hash=draft_hash,
    )
    final_artifact = Artifact(
        run_id=writer_run.id,
        artifact_type="final_content",
        locale="en",
        version=1,
        content_json=draft_payload,
        content_hash=draft_hash,
    )
    session.add_all([source_draft, final_artifact])
    await session.flush()

    await _persist_quality(
        session,
        project=project,
        content_case=content_case,
        snapshot=snapshot,
        variant=variant,
        item=item,
        writer_run=writer_run,
        source_draft=source_draft,
    )
    await session.flush()
    await pause_for_approval(
        session,
        run_id=writer_run.id,
        step_key="final_review",
        artifact_id=final_artifact.id,
    )
    await session.flush()

    detail = await get_action_aware_review_case(
        session,
        content_case_id=content_case.id,
    )
    panel = detail.locales[0]
    assert panel.next_action == "AWAITING_FOUNDER_APPROVAL"
    assert panel.content_item_id == item.id
    assert panel.final_content is not None
    assert panel.final_content.id == final_artifact.id
    return PendingReviewFixture(
        content_case_id=content_case.id,
        variant=variant,
        writer_run=writer_run,
        source_draft=source_draft,
        final_artifact=final_artifact,
    )


async def _persist_new_failing_audit(session, fixture: PendingReviewFixture) -> None:
    audit_run = ContentRun(
        project_id=fixture.writer_run.project_id,
        content_case_id=fixture.writer_run.content_case_id,
        locale_variant_id=fixture.variant.id,
        content_item_id=fixture.writer_run.content_item_id,
        run_mode="eval",
        status="completed",
        current_step="assertion_audit",
        settings_snapshot_id=fixture.writer_run.settings_snapshot_id,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    session.add(audit_run)
    await session.flush()
    payload = {
        "source_draft": {
            "id": str(fixture.source_draft.id),
            "version": fixture.source_draft.version,
            "content_hash": fixture.source_draft.content_hash,
        },
        "summary": {
            "result": "fail",
            "critical_unsupported_count": 1,
            "critical_contradicted_count": 0,
            "unsupported_count": 1,
            "contradicted_count": 0,
        },
    }
    audit = Artifact(
        run_id=audit_run.id,
        artifact_type="assertion_audit",
        locale="en",
        version=1,
        content_json=payload,
        content_hash=_hash(payload),
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
            result="fail",
            severity="critical",
            findings_json={"fixture": True},
        )
    )
    await session.flush()


async def _counts(session) -> tuple[int, int]:
    approvals = int(await session.scalar(select(func.count()).select_from(Approval)) or 0)
    versions = int(
        await session.scalar(select(func.count()).select_from(ContentVersion)) or 0
    )
    return approvals, versions


@pytest.mark.asyncio
async def test_review_action_approve_persists_version_and_completes_run() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        before = await _counts(session)
        result = await submit_review_decision(
            session,
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
            decision="approved",
            actor_id="founder",
            comment="Duyệt từ giao diện.",
        )
        after = await _counts(session)
        assert after == (before[0] + 1, before[1] + 1)
        assert result.content_version_id is not None
        assert result.writer_run_status == "completed"
        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case_id,
        )
        panel = detail.locales[0]
        assert panel.next_action == "APPROVED_NOT_PUBLISHED"
        assert panel.final_approval is not None
        assert panel.final_approval.decision == "approved"


@pytest.mark.asyncio
async def test_review_action_changes_requested_is_durable_and_requires_comment() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        before = await _counts(session)
        with pytest.raises(ReviewActionError, match="review_action_comment_required"):
            await submit_review_decision(
                session,
                content_case_id=fixture.content_case_id,
                locale_variant_id=fixture.variant.id,
                decision="changes_requested",
                actor_id="founder",
                comment="",
            )
        assert await _counts(session) == before

        result = await submit_review_decision(
            session,
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
            decision="changes_requested",
            actor_id="founder",
            comment="Rút gọn đoạn mở đầu.",
        )
        after = await _counts(session)
        assert after == (before[0] + 1, before[1])
        assert result.writer_run_status == "waiting_approval"
        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case_id,
        )
        panel = detail.locales[0]
        assert panel.consistency_state == "CONSISTENT"
        assert panel.next_action == "REVISION_REQUESTED"
        assert panel.final_approval is not None
        assert panel.final_approval.decision == "changes_requested"


@pytest.mark.asyncio
async def test_final_revision_v2_approval_creates_version_two_and_completes() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        requested = await submit_review_decision(
            session,
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
            decision="changes_requested",
            actor_id="founder",
            comment="Làm rõ câu kết.",
        )
        assert requested.writer_run_status == "waiting_approval"
        revised_payload = dict(fixture.final_artifact.content_json)
        revised_payload["closing_markdown"] = "Hãy kiểm tra câu hỏi tiếp theo."
        revised = Artifact(
            run_id=fixture.writer_run.id,
            artifact_type="journal_draft",
            locale="en",
            version=5,
            content_json=revised_payload,
            content_hash=_hash(revised_payload),
        )
        session.add(revised)
        revised_final = Artifact(
            run_id=fixture.writer_run.id,
            artifact_type="final_content",
            locale="en",
            version=2,
            content_json=revised_payload,
            content_hash=_hash(revised_payload),
        )
        session.add(revised_final)
        await session.flush()
        audit_candidates = list(
            (
                await session.scalars(
                    select(Artifact).where(
                        Artifact.artifact_type == "assertion_audit",
                        Artifact.locale == "en",
                    )
                )
            ).all()
        )
        old_audit = next(
            candidate
            for candidate in audit_candidates
            if isinstance(candidate.content_json, dict)
            and candidate.content_json.get("source_draft", {}).get("id")
            == str(fixture.source_draft.id)
        )
        assert old_audit is not None
        audit_payload = copy.deepcopy(old_audit.content_json)
        assert isinstance(audit_payload, dict)
        audit_payload["source_draft"] = {
            "id": str(revised.id),
            "version": revised.version,
            "content_hash": revised.content_hash,
        }
        new_audit = Artifact(
            run_id=old_audit.run_id,
            artifact_type="assertion_audit",
            locale="en",
            version=old_audit.version + 1,
            content_json=audit_payload,
            content_hash=_hash(audit_payload),
        )
        session.add(new_audit)
        await session.flush()
        old_audit_eval = await session.scalar(
            select(QualityEvaluation).where(QualityEvaluation.artifact_id == old_audit.id)
        )
        assert old_audit_eval is not None
        session.add(
            QualityEvaluation(
                run_id=old_audit_eval.run_id,
                artifact_id=new_audit.id,
                evaluator_key=old_audit_eval.evaluator_key,
                evaluator_version=old_audit_eval.evaluator_version,
                evaluator_type=old_audit_eval.evaluator_type,
                result=old_audit_eval.result,
                severity=old_audit_eval.severity,
                findings_json=old_audit_eval.findings_json,
            )
        )
        copy_candidates = list(
            (
                await session.scalars(
                    select(Artifact).where(
                        Artifact.artifact_type == "source_copy_check",
                        Artifact.locale == "en",
                    )
                )
            ).all()
        )
        old_copy = next(
            candidate
            for candidate in copy_candidates
            if isinstance(candidate.content_json, dict)
            and candidate.content_json.get("source_draft", {}).get("id")
            == str(fixture.source_draft.id)
        )
        assert old_copy is not None
        copy_payload = copy.deepcopy(old_copy.content_json)
        assert isinstance(copy_payload, dict)
        copy_payload["source_draft"] = audit_payload["source_draft"]
        copy_payload["assertion_audit"] = {
            "artifact": {
                "id": str(new_audit.id),
                "version": new_audit.version,
                "content_hash": new_audit.content_hash,
            }
        }
        new_copy = Artifact(
            run_id=old_copy.run_id,
            artifact_type="source_copy_check",
            locale="en",
            version=old_copy.version + 1,
            content_json=copy_payload,
            content_hash=_hash(copy_payload),
        )
        session.add(new_copy)
        await session.flush()
        old_copy_eval = await session.scalar(
            select(QualityEvaluation).where(QualityEvaluation.artifact_id == old_copy.id)
        )
        assert old_copy_eval is not None
        session.add(
            QualityEvaluation(
                run_id=old_copy_eval.run_id,
                artifact_id=new_copy.id,
                evaluator_key=old_copy_eval.evaluator_key,
                evaluator_version=old_copy_eval.evaluator_version,
                evaluator_type=old_copy_eval.evaluator_type,
                result=old_copy_eval.result,
                severity=old_copy_eval.severity,
                findings_json=old_copy_eval.findings_json,
            )
        )
        checkpoint_payload = {
            "pending_approval": {
                "step_key": "final_review",
                "artifact_id": str(revised_final.id),
            }
        }
        checkpoint = await session.scalar(
            select(Artifact)
            .where(
                Artifact.run_id == fixture.writer_run.id,
                Artifact.artifact_type == "checkpoint",
            )
            .order_by(Artifact.version.desc())
        )
        assert checkpoint is not None
        session.add(
            Artifact(
                run_id=fixture.writer_run.id,
                artifact_type="checkpoint",
                locale="en",
                version=checkpoint.version + 1,
                content_json=checkpoint_payload,
                content_hash=_hash(checkpoint_payload),
            )
        )
        session.add(
            ContentVersion(
                content_item_id=fixture.writer_run.content_item_id,
                version_no=1,
                change_reason="Prior revised draft snapshot",
                status="draft",
                content_json=fixture.final_artifact.content_json,
                created_by_run_id=fixture.writer_run.id,
                final_artifact_id=fixture.final_artifact.id,
            )
        )
        fixture.writer_run.status = "waiting_approval"
        await session.flush()
        result = await submit_review_decision(
            session,
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
            decision="approved",
            actor_id="founder",
            comment="Duyệt bản sửa v2.",
        )
        assert result.content_version_id is not None
        assert result.content_version_no == 2
        version = await session.get(ContentVersion, result.content_version_id)
        assert version is not None
        assert version.final_artifact_id == revised_final.id
        assert version.version_no == 2
        assert fixture.writer_run.status == "completed"
        assert await session.scalar(
            select(func.count(ContentVersion.id)).where(
                ContentVersion.content_item_id == fixture.writer_run.content_item_id
            )
        ) == 2


@pytest.mark.asyncio
async def test_review_action_reject_cancels_without_content_version() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        before = await _counts(session)
        result = await submit_review_decision(
            session,
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
            decision="rejected",
            actor_id="founder",
            comment="Không phù hợp định hướng.",
        )
        after = await _counts(session)
        assert after == (before[0] + 1, before[1])
        assert result.writer_run_status == "cancelled"
        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case_id,
        )
        panel = detail.locales[0]
        assert panel.consistency_state == "CONSISTENT"
        assert panel.next_action == "REJECTED"


@pytest.mark.asyncio
async def test_review_action_exact_replay_creates_no_duplicate() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        first = await submit_review_decision(
            session,
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
            decision="approved",
            actor_id="founder",
            comment="Duyệt.",
        )
        counts = await _counts(session)
        replay = await submit_review_decision(
            session,
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
            decision="approved",
            actor_id="founder",
            comment="Duyệt.",
        )
        assert replay.replayed is True
        assert replay.approval_id == first.approval_id
        assert replay.content_version_id == first.content_version_id
        assert await _counts(session) == counts


@pytest.mark.asyncio
async def test_changes_requested_replay_fails_closed_if_revision_already_started() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        comment = "Giữ nguyên phạm vi bằng chứng và sửa giọng văn."
        first = await submit_review_decision(
            session,
            content_case_id=fixture.content_case_id,
            locale_variant_id=fixture.variant.id,
            decision="changes_requested",
            actor_id="founder",
            comment=comment,
        )
        assert first.writer_run_status == "waiting_approval"
        fixture.writer_run.status = "running"
        session.add(
            StepRun(
                run_id=fixture.writer_run.id,
                step_key="final_revision_en",
                attempt=1,
                status="pending",
            )
        )
        await session.flush()
        with pytest.raises(ReviewActionError, match="review_action_replay_state_invalid"):
            await submit_review_decision(
                session,
                content_case_id=fixture.content_case_id,
                locale_variant_id=fixture.variant.id,
                decision="changes_requested",
                actor_id="founder",
                comment=comment,
            )


@pytest.mark.asyncio
async def test_review_action_quality_failure_creates_no_decision() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        await _persist_new_failing_audit(session, fixture)
        before = await _counts(session)
        with pytest.raises(ReviewActionError, match="review_action_quality_blocked"):
            await submit_review_decision(
                session,
                content_case_id=fixture.content_case_id,
                locale_variant_id=fixture.variant.id,
                decision="approved",
                actor_id="founder",
                comment="Duyệt.",
            )
        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_m1_already_approved_state_exposes_no_write_action() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case.id,
        )
        for panel in detail.locales:
            assert panel.next_action == "APPROVED_NOT_PUBLISHED"
