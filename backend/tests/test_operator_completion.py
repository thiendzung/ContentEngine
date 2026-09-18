from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_review_console import (
    ReviewFixture,
    _approved_fixture,
    _draft,
    _hash,
    isolated_session,
)

from app.modules.content_engine.journal.models import JournalRequiredLocale
from app.modules.content_engine.journal.operator_runtime import (
    get_operator_state,
    resolve_next_operator_action,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    _required_locale_completion_binding,
)
from app.modules.content_engine.journal.review_action_view import get_action_aware_review_case
from app.modules.content_engine.models import ContentItem, ContentVersion, LocaleVariant
from app.modules.harness.models import Approval, Artifact, ContentRun
from app.modules.harness.persistence import transition_run


async def _canonical_completed_fixture(session: AsyncSession) -> ReviewFixture:
    fixture = await _approved_fixture(session)
    source_runs = list(
        (
            await session.scalars(
                select(ContentRun).where(
                    ContentRun.content_case_id == fixture.content_case.id,
                    ContentRun.current_step == "outline",
                )
            )
        ).all()
    )
    assert len(source_runs) == 1
    source_run = source_runs[0]
    await transition_run(session, run_id=source_run.id, status="running")
    await transition_run(session, run_id=source_run.id, status="completed")
    session.add_all(
        [
            JournalRequiredLocale(
                content_case_id=fixture.content_case.id,
                locale="en",
                role="source",
                declared_by="founder",
            ),
            JournalRequiredLocale(
                content_case_id=fixture.content_case.id,
                locale="vi-VN",
                role="translation",
                declared_by="founder",
            ),
        ]
    )
    await session.flush()
    return fixture


async def _add_required_locale_item(
    session: AsyncSession,
    *,
    fixture: ReviewFixture,
    locale: str,
) -> tuple[LocaleVariant, ContentItem]:
    variant = LocaleVariant(
        content_case_id=fixture.content_case.id,
        locale=locale,
        content_role="cluster",
        primary_question=f"Question for {locale}",
        primary_intent="evaluate",
    )
    session.add(variant)
    await session.flush()
    item = ContentItem(
        project_id=fixture.content_case.project_id,
        content_case_id=fixture.content_case.id,
        locale_variant_id=variant.id,
        content_type="journal",
        canonical_key=f"journal:{fixture.content_case.id}:{locale}",
    )
    session.add_all(
        [
            item,
            JournalRequiredLocale(
                content_case_id=fixture.content_case.id,
                locale=locale,
                role="translation",
                declared_by="founder",
            ),
        ]
    )
    await session.flush()
    return variant, item


async def _add_unapproved_active_version(
    session: AsyncSession,
    *,
    fixture: ReviewFixture,
    locale: str,
) -> None:
    variant, item = await _add_required_locale_item(
        session,
        fixture=fixture,
        locale=locale,
    )
    payload = _draft(locale)
    writer_run = ContentRun(
        project_id=fixture.content_case.project_id,
        content_case_id=fixture.content_case.id,
        locale_variant_id=variant.id,
        content_item_id=item.id,
        run_mode="create",
        status="completed",
        current_step="final_review",
        settings_snapshot_id=fixture.writer_runs["en"].settings_snapshot_id,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    session.add(writer_run)
    await session.flush()
    final_artifact = Artifact(
        run_id=writer_run.id,
        artifact_type="final_content",
        locale=locale,
        version=1,
        content_json=payload,
        content_hash=_hash(payload),
    )
    session.add(final_artifact)
    await session.flush()
    session.add(
        ContentVersion(
            content_item_id=item.id,
            version_no=1,
            final_artifact_id=final_artifact.id,
            change_reason="missing approval fixture",
            status="approved",
            content_json=payload,
            created_by_run_id=writer_run.id,
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_exact_required_locale_final_chains_complete_case() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status == "COMPLETE"
        assert state.phase == "Hoàn tất"
        assert state.human_gate is None
        assert state.blocker_code is None

        action = await resolve_next_operator_action(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert action.status == "COMPLETE"
        assert action.action_key == "complete"
        assert action.executable is False
        assert action.blocker_code is None

        detail = await get_action_aware_review_case(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert detail.next_action == "APPROVED_NOT_PUBLISHED"
        assert detail.publication_state == "NOT_PUBLISHED"


@pytest.mark.asyncio
async def test_approved_version_without_exact_final_approval_fails_closed() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        await _add_unapproved_active_version(
            session,
            fixture=fixture,
            locale="fr",
        )

        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status == "BLOCKED"
        assert state.blocker_code == "operator_completion_binding_invalid"

        action = await resolve_next_operator_action(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert action.status == "BLOCKED"
        assert action.action_key is None
        assert action.executable is False
        assert action.blocker_code == "operator_completion_binding_invalid"


@pytest.mark.asyncio
async def test_content_version_bound_to_wrong_final_artifact_and_run_fails_closed() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        _variant, item = await _add_required_locale_item(
            session,
            fixture=fixture,
            locale="fr",
        )
        en_version = fixture.versions["en"]
        session.add(
            ContentVersion(
                content_item_id=item.id,
                version_no=1,
                final_artifact_id=fixture.final_artifacts["en"].id,
                change_reason="wrong binding fixture",
                status="approved",
                content_json=en_version.content_json,
                created_by_run_id=fixture.writer_runs["en"].id,
            )
        )
        await session.flush()

        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status == "BLOCKED"
        assert state.blocker_code == "operator_completion_binding_invalid"


@pytest.mark.asyncio
async def test_extra_non_required_locale_does_not_block_complete() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        session.add(
            LocaleVariant(
                content_case_id=fixture.content_case.id,
                locale="fr",
                content_role="cluster",
                primary_question="Question non requise",
                primary_intent="evaluate",
            )
        )
        await session.flush()

        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status == "COMPLETE"
        assert state.phase == "Hoàn tất"
        assert state.blocker_code is None


@pytest.mark.asyncio
async def test_required_locale_without_active_version_reports_missing_binding() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        await _add_required_locale_item(
            session,
            fixture=fixture,
            locale="fr",
        )

        binding_state, payload = await _required_locale_completion_binding(
            session,
            content_case_id=fixture.content_case.id,
            locale="fr",
        )
        assert binding_state == "missing"
        assert payload["reason"] == "active_content_version_missing"


@pytest.mark.asyncio
async def test_stale_final_review_decision_for_other_artifact_does_not_block_complete() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        writer_run = fixture.writer_runs["en"]
        stale_payload = _draft("en")
        stale_draft = stale_payload["draft"]
        assert isinstance(stale_draft, dict)
        stale_draft["title"] = "Superseded final candidate"
        stale_artifact = Artifact(
            run_id=writer_run.id,
            artifact_type="final_content",
            locale="en",
            version=2,
            content_json=stale_payload,
            content_hash=_hash(stale_payload),
        )
        session.add(stale_artifact)
        await session.flush()
        session.add(
            Approval(
                run_id=writer_run.id,
                step_key="final_review",
                artifact_id=stale_artifact.id,
                decision="rejected",
                actor_id="founder",
                comment="stale decision fixture",
            )
        )
        await session.flush()

        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status == "COMPLETE"
        assert state.blocker_code is None


@pytest.mark.asyncio
async def test_multiple_active_versions_for_required_locale_fail_closed() -> None:
    async with isolated_session() as session:
        fixture = await _canonical_completed_fixture(session)
        first = fixture.versions["en"]
        session.add(
            ContentVersion(
                content_item_id=first.content_item_id,
                version_no=2,
                final_artifact_id=first.final_artifact_id,
                change_reason="conflict fixture",
                status="approved",
                content_json=first.content_json,
                created_by_run_id=first.created_by_run_id,
            )
        )
        await session.flush()

        state = await get_operator_state(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert state.status == "BLOCKED"
        assert state.blocker_code == "operator_completion_binding_invalid"
