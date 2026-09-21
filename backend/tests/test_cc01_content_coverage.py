from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.main import app
from app.modules.content_engine.content_coverage import (
    ContentCoverageError,
    build_content_coverage,
    ensure_content_case_supporting_need,
    ensure_content_item_journey_stage,
)
from app.modules.content_engine.models import (
    AudienceHypothesis,
    ContentCase,
    ContentCaseSupportingNeed,
    ContentItem,
    ContentItemJourneyStage,
    ContentOpportunity,
    ContentVersion,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    Project,
    SettingsSnapshot,
)
from app.modules.harness.models import (
    Approval,
    Artifact,
    ContentRun,
    ModelCall,
    QualityEvaluation,
    ToolCall,
)


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


async def _project(session: AsyncSession, label: str) -> Project:
    project = Project(
        slug=f"{label}-{uuid4().hex[:8]}",
        name=label,
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


async def _audience(
    session: AsyncSession,
    *,
    project_id: UUID,
    name: str,
) -> AudienceHypothesis:
    row = AudienceHypothesis(
        project_id=project_id,
        name=name,
        description=f"{name} description",
        status="PROPOSED",
    )
    session.add(row)
    await session.flush()
    return row


async def _need(
    session: AsyncSession,
    *,
    project_id: UUID,
    audience_id: UUID | None = None,
    statement: str | None = None,
) -> NeedHypothesis:
    row = NeedHypothesis(
        project_id=project_id,
        audience_hypothesis_id=audience_id,
        type="question",
        statement=statement or f"Need {uuid4().hex}",
        audience_scope="first-time buyer",
        situation="considering an artwork",
        origin="research",
        status="PROPOSED",
        alternative_explanations_json=[],
        missing_evidence_json=[],
        version=1,
    )
    session.add(row)
    await session.flush()
    return row


async def _opportunity(
    session: AsyncSession,
    *,
    project_id: UUID,
    need: NeedHypothesis,
    locale: str = "en",
    decision: str = "CREATE",
    refs: list[str] | None = None,
    selected: bool = False,
) -> ContentOpportunity:
    opportunity = ContentOpportunity(
        project_id=project_id,
        need_hypothesis_id=need.id,
        locale=locale,
        reader="first-time buyer",
        situation=need.situation,
        need=need.statement,
        question=f"Question for {need.id}",
        intent="evaluate",
        promise="Help the reader make a grounded decision.",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=refs or [],
        what_is_actually_new="Bounded coverage fixture.",
        next_discovery_step="Relevant artwork",
        decision=decision,
        priority="NEXT",
        reasons_json=["fixture"],
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
    )
    session.add(opportunity)
    await session.flush()
    if selected:
        selection = HumanSelection(
            content_opportunity_id=opportunity.id,
            selected_by="founder",
            reason="Selected for CC-01 fixture.",
        )
        session.add(selection)
        await session.flush()
    return opportunity


async def _content_case(
    session: AsyncSession,
    *,
    project_id: UUID,
    need: NeedHypothesis,
    audience_id: UUID | None = None,
    opportunity: ContentOpportunity | None = None,
) -> ContentCase:
    source_opportunity = opportunity or await _opportunity(
        session,
        project_id=project_id,
        need=need,
    )
    row = ContentCase(
        project_id=project_id,
        content_type="journal",
        audience_hypothesis_id=audience_id,
        need_hypothesis_id=need.id,
        content_opportunity_id=source_opportunity.id,
        desired_action="read",
        content_hypothesis="Useful answer improves understanding.",
        originality_statement="Fixture originality statement.",
        reader_before="uncertain",
        reader_after="better informed",
        status="draft",
    )
    session.add(row)
    await session.flush()
    return row


async def _item(
    session: AsyncSession,
    *,
    project_id: UUID,
    content_case: ContentCase,
    locale: str = "en",
    question: str = "How do I evaluate this?",
    intent: str = "evaluate",
    suffix: str | None = None,
) -> tuple[LocaleVariant, ContentItem]:
    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale=locale,
        content_role="cluster",
        primary_question=question,
        primary_intent=intent,
        status="draft",
    )
    session.add(variant)
    await session.flush()
    item = ContentItem(
        project_id=project_id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_type="journal",
        status="draft",
        canonical_key=(
            f"journal:{content_case.id}:{locale}:{suffix or uuid4().hex[:6]}"
        ),
    )
    session.add(item)
    await session.flush()
    return variant, item


async def _version(
    session: AsyncSession,
    *,
    item: ContentItem,
    version_no: int,
    status: str,
) -> ContentVersion:
    row = ContentVersion(
        content_item_id=item.id,
        version_no=version_no,
        change_reason=f"CC-01 fixture v{version_no}",
        status=status,
        content_json={"title": f"Version {version_no}"},
    )
    session.add(row)
    await session.flush()
    return row


async def _negative_final_review(
    session: AsyncSession,
    *,
    project_id: UUID,
    content_case: ContentCase,
    variant: LocaleVariant,
    item: ContentItem,
    decision: str = "changes_requested",
) -> Approval:
    snapshot = SettingsSnapshot(
        project_id=project_id,
        resolved_settings_json={},
        source_version_refs_json=[],
        content_hash="0" * 64,
    )
    session.add(snapshot)
    await session.flush()
    run = ContentRun(
        project_id=project_id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_item_id=item.id,
        run_mode="create",
        status="waiting_approval",
        current_step="final_review",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    artifact = Artifact(
        run_id=run.id,
        artifact_type="final_content",
        locale=variant.locale,
        version=1,
        content_json={"title": "Rejected fixture"},
        content_hash="1" * 64,
    )
    session.add(artifact)
    await session.flush()
    approval = Approval(
        run_id=run.id,
        step_key="final_review",
        artifact_id=artifact.id,
        decision=decision,
        actor_id="founder",
        comment="Needs revision.",
    )
    session.add(approval)
    await session.flush()
    return approval


def _lane(report: dict[str, object], need_id: UUID) -> dict[str, object]:
    rows = report["needs"]
    assert isinstance(rows, list)
    for raw in rows:
        assert isinstance(raw, dict)
        need = raw["need"]
        assert isinstance(need, dict)
        if need["id"] == str(need_id):
            return raw
    raise AssertionError(f"Missing coverage lane for {need_id}")


@pytest.mark.asyncio
async def test_supporting_need_link_is_audited_scoped_and_immutable() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        foreign = await _project(session, "foreign")
        audience = await _audience(
            session,
            project_id=project.id,
            name="First-time buyer",
        )
        other_audience = await _audience(
            session,
            project_id=project.id,
            name="Other audience",
        )
        primary = await _need(
            session,
            project_id=project.id,
            audience_id=audience.id,
        )
        supporting = await _need(
            session,
            project_id=project.id,
            audience_id=audience.id,
        )
        case = await _content_case(
            session,
            project_id=project.id,
            need=primary,
            audience_id=audience.id,
        )

        first = await ensure_content_case_supporting_need(
            session,
            content_case_id=case.id,
            need_hypothesis_id=supporting.id,
            linked_by="founder",
            reason="This article also answers the supporting question.",
        )
        replay = await ensure_content_case_supporting_need(
            session,
            content_case_id=case.id,
            need_hypothesis_id=supporting.id,
            linked_by="founder",
            reason="This article also answers the supporting question.",
        )
        assert replay.need_hypothesis_id == first.need_hypothesis_id

        with pytest.raises(
            ContentCoverageError,
            match="content_coverage_supporting_need_replay_conflict",
        ):
            await ensure_content_case_supporting_need(
                session,
                content_case_id=case.id,
                need_hypothesis_id=supporting.id,
                linked_by="founder",
                reason="Changed reason.",
            )

        with pytest.raises(
            ContentCoverageError,
            match="content_coverage_supporting_need_is_primary",
        ):
            await ensure_content_case_supporting_need(
                session,
                content_case_id=case.id,
                need_hypothesis_id=primary.id,
                linked_by="founder",
                reason="Primary must not be duplicated as supporting.",
            )

        foreign_need = await _need(session, project_id=foreign.id)
        with pytest.raises(
            ContentCoverageError,
            match="content_coverage_supporting_need_project_mismatch",
        ):
            await ensure_content_case_supporting_need(
                session,
                content_case_id=case.id,
                need_hypothesis_id=foreign_need.id,
                linked_by="founder",
                reason="Cross-project link must fail.",
            )

        wrong_audience_need = await _need(
            session,
            project_id=project.id,
            audience_id=other_audience.id,
        )
        with pytest.raises(
            ContentCoverageError,
            match="content_coverage_supporting_need_audience_mismatch",
        ):
            await ensure_content_case_supporting_need(
                session,
                content_case_id=case.id,
                need_hypothesis_id=wrong_audience_need.id,
                linked_by="founder",
                reason="Audience mismatch must fail.",
            )

        with pytest.raises(
            DBAPIError,
            match="content_case_supporting_need_is_immutable",
        ):
            async with session.begin_nested():
                first.reason = "Direct rewrite."
                await session.flush()

        await session.refresh(first)
        with pytest.raises(
            DBAPIError,
            match="content_case_supporting_need_delete_forbidden",
        ):
            async with session.begin_nested():
                await session.delete(first)
                await session.flush()

        with pytest.raises(
            DBAPIError,
            match="content_coverage_supporting_need_project_mismatch",
        ):
            async with session.begin_nested():
                session.add(
                    ContentCaseSupportingNeed(
                        content_case_id=case.id,
                        need_hypothesis_id=foreign_need.id,
                        linked_by="direct-db-test",
                        reason="DB guard must reject this.",
                    )
                )
                await session.flush()


@pytest.mark.asyncio
async def test_coverage_scope_drift_is_rejected_after_links() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        foreign = await _project(session, "foreign")
        audience = await _audience(
            session,
            project_id=project.id,
            name="Coverage audience",
        )
        primary = await _need(session, project_id=project.id)
        supporting = await _need(session, project_id=project.id)
        case = await _content_case(
            session,
            project_id=project.id,
            need=primary,
            audience_id=audience.id,
        )
        await ensure_content_case_supporting_need(
            session,
            content_case_id=case.id,
            need_hypothesis_id=supporting.id,
            linked_by="founder",
            reason="Bind supporting need.",
        )

        with pytest.raises(
            DBAPIError,
            match="content_coverage_linked_case_scope_immutable",
        ):
            async with session.begin_nested():
                case.project_id = foreign.id
                await session.flush()

        await session.refresh(case)
        with pytest.raises(
            DBAPIError,
            match="content_coverage_linked_need_scope_immutable",
        ):
            async with session.begin_nested():
                supporting.project_id = foreign.id
                await session.flush()

        await session.refresh(supporting)
        with pytest.raises(
            DBAPIError,
            match="content_coverage_audience_project_change_forbidden",
        ):
            async with session.begin_nested():
                audience.project_id = foreign.id
                await session.flush()


@pytest.mark.asyncio
async def test_primary_need_identity_cannot_be_reassigned() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        primary = await _need(
            session,
            project_id=project.id,
            statement="Original primary need",
        )
        replacement = await _need(
            session,
            project_id=project.id,
            statement="Different same-project need",
        )
        content_case = await _content_case(
            session,
            project_id=project.id,
            need=primary,
        )

        with pytest.raises(
            DBAPIError,
            match="content_coverage_primary_need_immutable",
        ):
            async with session.begin_nested():
                content_case.need_hypothesis_id = replacement.id
                await session.flush()


@pytest.mark.asyncio
async def test_item_journey_link_is_config_valid_audited_and_immutable() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)
        case = await _content_case(
            session,
            project_id=project.id,
            need=need,
        )
        _variant, item = await _item(
            session,
            project_id=project.id,
            content_case=case,
        )

        first = await ensure_content_item_journey_stage(
            session,
            content_item_id=item.id,
            stage_key="aware",
            linked_by="founder",
            reason="Useful when the reader first recognizes this need.",
        )
        second = await ensure_content_item_journey_stage(
            session,
            content_item_id=item.id,
            stage_key="trust",
            linked_by="founder",
            reason="Also useful while building trust.",
        )
        replay = await ensure_content_item_journey_stage(
            session,
            content_item_id=item.id,
            stage_key="aware",
            linked_by="founder",
            reason="Useful when the reader first recognizes this need.",
        )
        assert replay.stage_key == first.stage_key
        assert second.stage_key == "trust"

        with pytest.raises(
            ContentCoverageError,
            match="content_coverage_journey_stage_not_configured",
        ):
            await ensure_content_item_journey_stage(
                session,
                content_item_id=item.id,
                stage_key="not_configured",
                linked_by="founder",
                reason="Invalid stage.",
            )

        with pytest.raises(
            DBAPIError,
            match="content_item_journey_stage_is_immutable",
        ):
            async with session.begin_nested():
                first.reason = "Direct rewrite."
                await session.flush()

        await session.refresh(first)
        with pytest.raises(
            DBAPIError,
            match="content_item_journey_stage_delete_forbidden",
        ):
            async with session.begin_nested():
                await session.delete(first)
                await session.flush()

        with pytest.raises(
            DBAPIError,
            match="content_coverage_linked_item_scope_immutable",
        ):
            async with session.begin_nested():
                item.content_case_id = uuid4()
                await session.flush()


@pytest.mark.asyncio
async def test_content_coverage_statuses_are_evidence_bounded() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")

        missing = await _need(
            session,
            project_id=project.id,
            statement="Missing coverage need",
        )

        planned = await _need(
            session,
            project_id=project.id,
            statement="Planned coverage need",
        )
        await _opportunity(
            session,
            project_id=project.id,
            need=planned,
            decision="CREATE",
            selected=True,
        )

        in_progress = await _need(
            session,
            project_id=project.id,
            statement="In progress coverage need",
        )
        in_progress_case = await _content_case(
            session,
            project_id=project.id,
            need=in_progress,
        )
        await _item(
            session,
            project_id=project.id,
            content_case=in_progress_case,
        )

        published = await _need(
            session,
            project_id=project.id,
            statement="Published coverage need",
        )
        published_case = await _content_case(
            session,
            project_id=project.id,
            need=published,
        )
        _published_variant, published_item = await _item(
            session,
            project_id=project.id,
            content_case=published_case,
        )
        await _version(
            session,
            item=published_item,
            version_no=1,
            status="published",
        )

        needs_update = await _need(
            session,
            project_id=project.id,
            statement="Needs update coverage need",
        )
        update_case = await _content_case(
            session,
            project_id=project.id,
            need=needs_update,
        )
        _update_variant, update_item = await _item(
            session,
            project_id=project.id,
            content_case=update_case,
        )
        await _version(
            session,
            item=update_item,
            version_no=1,
            status="published",
        )
        await _opportunity(
            session,
            project_id=project.id,
            need=needs_update,
            decision="UPDATE",
            refs=[str(update_item.id)],
            selected=True,
        )

        weak = await _need(
            session,
            project_id=project.id,
            statement="Weak coverage need",
        )
        weak_case = await _content_case(
            session,
            project_id=project.id,
            need=weak,
        )
        weak_variant, weak_item = await _item(
            session,
            project_id=project.id,
            content_case=weak_case,
        )
        await _negative_final_review(
            session,
            project_id=project.id,
            content_case=weak_case,
            variant=weak_variant,
            item=weak_item,
        )

        insufficient = await _need(
            session,
            project_id=project.id,
            statement="Insufficient coverage need",
        )
        await _opportunity(
            session,
            project_id=project.id,
            need=insufficient,
            decision="UPDATE",
            refs=["not-a-content-item-ref"],
            selected=True,
        )

        report = await build_content_coverage(
            session,
            project_id=project.id,
        )

        assert _lane(report, missing.id)["coverage_status"] == "MISSING"
        assert _lane(report, planned.id)["coverage_status"] == "PLANNED"
        assert (
            _lane(report, in_progress.id)["coverage_status"]
            == "IN_PROGRESS"
        )
        assert _lane(report, published.id)["coverage_status"] == "PUBLISHED"
        assert (
            _lane(report, needs_update.id)["coverage_status"]
            == "NEEDS_UPDATE"
        )
        assert _lane(report, weak.id)["coverage_status"] == "WEAK"
        assert (
            _lane(report, insufficient.id)["coverage_status"]
            == "INSUFFICIENT_DATA"
        )

        semantics = report["semantics"]
        assert isinstance(semantics, dict)
        assert semantics["published_does_not_mean_customer_problem_solved"] is True
        assert semantics["working_status_requires_measurement"] is True


@pytest.mark.asyncio
async def test_invalid_update_ref_does_not_erase_known_published_coverage() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)
        content_case = await _content_case(
            session,
            project_id=project.id,
            need=need,
        )
        _variant, item = await _item(
            session,
            project_id=project.id,
            content_case=content_case,
        )
        await _version(
            session,
            item=item,
            version_no=1,
            status="published",
        )
        await _opportunity(
            session,
            project_id=project.id,
            need=need,
            decision="UPDATE",
            refs=["not-a-content-item-ref"],
            selected=True,
        )

        report = await build_content_coverage(
            session,
            project_id=project.id,
        )
        lane = _lane(report, need.id)
        assert lane["coverage_status"] == "PUBLISHED"
        assert "selected_update_target_ref_invalid" in lane["reason_codes"]
        assert lane["invalid_update_target_refs"] == [
            "not-a-content-item-ref"
        ]


@pytest.mark.asyncio
async def test_newer_unpublished_revision_is_needs_update() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)
        case = await _content_case(
            session,
            project_id=project.id,
            need=need,
        )
        _variant, item = await _item(
            session,
            project_id=project.id,
            content_case=case,
        )
        await _version(
            session,
            item=item,
            version_no=1,
            status="published",
        )
        await _version(
            session,
            item=item,
            version_no=2,
            status="draft",
        )

        report = await build_content_coverage(
            session,
            project_id=project.id,
        )
        assert _lane(report, need.id)["coverage_status"] == "NEEDS_UPDATE"


@pytest.mark.asyncio
async def test_unresolved_quality_failure_marks_unpublished_coverage_weak() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)
        content_case = await _content_case(
            session,
            project_id=project.id,
            need=need,
        )
        variant = LocaleVariant(
            content_case_id=content_case.id,
            locale="en",
            content_role="cluster",
            primary_question="Quality-blocked fixture?",
            primary_intent="evaluate",
            status="draft",
        )
        session.add(variant)
        await session.flush()
        snapshot = SettingsSnapshot(
            project_id=project.id,
            resolved_settings_json={},
            source_version_refs_json=[],
            content_hash="2" * 64,
        )
        session.add(snapshot)
        await session.flush()
        run = ContentRun(
            project_id=project.id,
            content_case_id=content_case.id,
            locale_variant_id=variant.id,
            content_item_id=None,
            run_mode="create",
            status="running",
            current_step="assertion_audit_en",
            settings_snapshot_id=snapshot.id,
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()
        artifact = Artifact(
            run_id=run.id,
            artifact_type="assertion_audit",
            locale="en",
            version=1,
            content_json={"findings": ["critical unsupported claim"]},
            content_hash="3" * 64,
        )
        session.add(artifact)
        await session.flush()
        evaluation = QualityEvaluation(
            run_id=run.id,
            artifact_id=artifact.id,
            evaluator_key="assertion_audit_en",
            evaluator_version="v1",
            evaluator_type="deterministic",
            result="fail",
            score=None,
            severity="critical",
            findings_json={"critical_unsupported_count": 1},
        )
        session.add(evaluation)
        await session.flush()

        report = await build_content_coverage(
            session,
            project_id=project.id,
        )
        assert _lane(report, need.id)["coverage_status"] == "WEAK"


@pytest.mark.asyncio
async def test_same_need_is_not_duplicate_without_same_structural_question() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)

        case_one = await _content_case(
            session,
            project_id=project.id,
            need=need,
        )
        _v1, item_one = await _item(
            session,
            project_id=project.id,
            content_case=case_one,
            question="How do I know a painting is original?",
            intent="trust",
        )
        await _version(
            session,
            item=item_one,
            version_no=1,
            status="published",
        )

        case_two = await _content_case(
            session,
            project_id=project.id,
            need=need,
        )
        _v2, item_two = await _item(
            session,
            project_id=project.id,
            content_case=case_two,
            question="How much should I spend on my first painting?",
            intent="evaluate",
        )
        await _version(
            session,
            item=item_two,
            version_no=1,
            status="published",
        )

        report = await build_content_coverage(
            session,
            project_id=project.id,
        )
        lane = _lane(report, need.id)
        assert lane["coverage_status"] == "PUBLISHED"
        assert lane["duplicate_candidates"] == []


@pytest.mark.asyncio
async def test_duplicate_candidate_requires_same_primary_structure() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)
        item_ids: list[str] = []

        for question in (
            "How do I know a painting is original?",
            "  how do i know a PAINTING is original?  ",
        ):
            content_case = await _content_case(
                session,
                project_id=project.id,
                need=need,
            )
            _variant, item = await _item(
                session,
                project_id=project.id,
                content_case=content_case,
                question=question,
                intent="trust",
            )
            await _version(
                session,
                item=item,
                version_no=1,
                status="published",
            )
            item_ids.append(str(item.id))

        report = await build_content_coverage(
            session,
            project_id=project.id,
        )
        lane = _lane(report, need.id)
        duplicates = lane["duplicate_candidates"]
        assert isinstance(duplicates, list)
        assert len(duplicates) == 1
        assert duplicates[0]["content_item_ids"] == sorted(item_ids)
        assert lane["coverage_status"] == "PUBLISHED"
        assert "duplicate_candidate_detected" in lane["reason_codes"]


@pytest.mark.asyncio
async def test_supporting_need_can_share_content_without_becoming_duplicate() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        primary = await _need(
            session,
            project_id=project.id,
            statement="Primary need",
        )
        supporting = await _need(
            session,
            project_id=project.id,
            statement="Supporting need",
        )
        content_case = await _content_case(
            session,
            project_id=project.id,
            need=primary,
        )
        await ensure_content_case_supporting_need(
            session,
            content_case_id=content_case.id,
            need_hypothesis_id=supporting.id,
            linked_by="founder",
            reason="One useful article legitimately supports both needs.",
        )
        _variant, item = await _item(
            session,
            project_id=project.id,
            content_case=content_case,
            question="How do I make a grounded first purchase?",
            intent="evaluate",
        )
        await _version(
            session,
            item=item,
            version_no=1,
            status="published",
        )

        report = await build_content_coverage(
            session,
            project_id=project.id,
        )
        primary_lane = _lane(report, primary.id)
        supporting_lane = _lane(report, supporting.id)

        assert primary_lane["content_items"][0]["need_role"] == "primary"
        assert (
            supporting_lane["content_items"][0]["need_role"]
            == "supporting"
        )
        assert supporting_lane["duplicate_candidates"] == []
        assert supporting_lane["coverage_status"] == "PUBLISHED"


@pytest.mark.asyncio
async def test_journey_mapping_is_visible_and_stale_stage_fails_closed() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)
        content_case = await _content_case(
            session,
            project_id=project.id,
            need=need,
        )
        _variant, item = await _item(
            session,
            project_id=project.id,
            content_case=content_case,
        )
        await ensure_content_item_journey_stage(
            session,
            content_item_id=item.id,
            stage_key="trust",
            linked_by="founder",
            reason="Trust-stage content mapping.",
        )

        report = await build_content_coverage(
            session,
            project_id=project.id,
        )
        lane = _lane(report, need.id)
        assert lane["content_items"][0]["journey_stages"] == [
            {
                "stage_key": "trust",
                "linked_by": "founder",
                "reason": "Trust-stage content mapping.",
            }
        ]

        session.add(
            ContentItemJourneyStage(
                content_item_id=item.id,
                stage_key="legacy_stage",
                linked_by="direct-db-test",
                reason="Bypass service to test read fail-closed.",
            )
        )
        await session.flush()

        with pytest.raises(
            ContentCoverageError,
            match="content_coverage_journey_stage_stale",
        ):
            await build_content_coverage(
                session,
                project_id=project.id,
            )


@pytest.mark.asyncio
async def test_coverage_filters_by_locale_audience_and_need() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        audience = await _audience(
            session,
            project_id=project.id,
            name="Target audience",
        )
        other_audience = await _audience(
            session,
            project_id=project.id,
            name="Other audience",
        )
        target = await _need(
            session,
            project_id=project.id,
            audience_id=audience.id,
        )
        other = await _need(
            session,
            project_id=project.id,
            audience_id=other_audience.id,
        )

        target_case = await _content_case(
            session,
            project_id=project.id,
            need=target,
            audience_id=audience.id,
        )
        _target_variant, target_item = await _item(
            session,
            project_id=project.id,
            content_case=target_case,
            locale="en",
        )
        await _version(
            session,
            item=target_item,
            version_no=1,
            status="published",
        )

        other_case = await _content_case(
            session,
            project_id=project.id,
            need=other,
            audience_id=other_audience.id,
        )
        await _item(
            session,
            project_id=project.id,
            content_case=other_case,
            locale="vi-VN",
        )

        report = await build_content_coverage(
            session,
            project_id=project.id,
            locale="en",
            audience_id=audience.id,
            need_id=target.id,
        )
        rows = report["needs"]
        assert isinstance(rows, list)
        assert len(rows) == 1
        assert rows[0]["need"]["id"] == str(target.id)
        assert rows[0]["content_items"][0]["locale"] == "en"


@pytest.mark.asyncio
async def test_locale_filter_does_not_treat_other_locale_case_as_in_progress() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        need = await _need(session, project_id=project.id)
        content_case = await _content_case(
            session,
            project_id=project.id,
            need=need,
        )
        _variant, item = await _item(
            session,
            project_id=project.id,
            content_case=content_case,
            locale="vi-VN",
        )
        await _version(
            session,
            item=item,
            version_no=1,
            status="published",
        )

        report = await build_content_coverage(
            session,
            project_id=project.id,
            locale="en",
        )
        lane = _lane(report, need.id)
        assert lane["coverage_status"] == "MISSING"
        assert lane["content_items"] == []


@pytest.mark.asyncio
async def test_coverage_read_does_not_create_model_or_tool_calls() -> None:
    async with isolated_session() as session:
        project = await _project(session, "motgu")
        await _need(session, project_id=project.id)

        before = (
            await session.scalar(select(func.count()).select_from(ModelCall)),
            await session.scalar(select(func.count()).select_from(ToolCall)),
        )
        await build_content_coverage(
            session,
            project_id=project.id,
        )
        after = (
            await session.scalar(select(func.count()).select_from(ModelCall)),
            await session.scalar(select(func.count()).select_from(ToolCall)),
        )
        assert after == before


def test_content_coverage_route_is_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/content-coverage" in paths