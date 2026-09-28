from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from test_run_records import create_run, isolated_session

from app.modules.harness.models import Artifact, Job, StepRun
from app.modules.publishing.assisted import (
    ASSISTED_OBSERVATION_ARTIFACT_TYPE,
    PublishAssistedError,
    record_publish_assisted_observation,
)
from app.modules.publishing.models import PublishEvent, PublishedContent


def _draft_payload() -> dict[str, object]:
    return {
        "locale": "vi-VN",
        "title": "Cách nhìn một tác phẩm trước khi quyết định",
        "standfirst": "Một cách tiếp cận bình tĩnh cho người mua lần đầu.",
        "lead_markdown": "Bắt đầu từ những gì bạn có thể xác minh.",
        "sections": [
            {
                "section_id": "work",
                "heading": "Nhìn vào chính tác phẩm",
                "body_markdown": "Ghi lại chất liệu, kích thước và thông tin tác giả.",
            },
            {
                "section_id": "questions",
                "heading": "Hỏi những điều còn chưa rõ",
                "body_markdown": "Nếu thông tin chưa đủ, bạn có thể dừng và hỏi thêm.",
            },
        ],
        "closing_markdown": "Một quyết định tốt không cần bị thúc ép.",
    }


@pytest.mark.asyncio
async def test_publish_assisted_records_manual_snapshot_without_pm01_binding() -> None:
    async with isolated_session() as session:
        _project, run, _snapshot = await create_run(session)
        source = Artifact(
            run_id=run.id,
            step_run_id=None,
            artifact_type="journal_draft",
            locale="vi-VN",
            version=1,
            content_json=_draft_payload(),
            content_hash="a" * 64,
        )
        session.add(source)
        await session.flush()

        manual = (
            "# Cách nhìn một tác phẩm trước khi quyết định\n\n"
            "Tôi thường bắt đầu từ những gì có thể kiểm tra ngay.\n\n"
            "## Nhìn vào chính tác phẩm\n\n"
            "Ghi lại chất liệu, kích thước và thông tin tác giả trước khi hỏi sâu hơn.\n\n"
            "## Hỏi những điều còn chưa rõ\n\n"
            "Nếu thông tin chưa đủ, tôi sẽ dừng lại và hỏi thêm thay vì vội mua.\n\n"
            "Một quyết định tốt không cần bị thúc ép."
        )
        result = await record_publish_assisted_observation(
            session,
            source_run_id=run.id,
            phase="draft",
            actor_id="founder",
            content_markdown=manual,
            source_artifact_id=source.id,
            note="Founder edited the assisted draft before publishing.",
        )

        payload = result.artifact.content_json
        assert isinstance(payload, dict)
        assert result.replayed is False
        assert result.artifact.artifact_type == ASSISTED_OBSERVATION_ARTIFACT_TYPE
        assert payload["mode"] == "founder_manual_publish_assisted"
        assert payload["phase"] == "draft"
        source_ref = payload["source_ai_artifact"]
        assert isinstance(source_ref, dict)
        assert source_ref["id"] == str(source.id)
        delta = payload["edit_delta"]
        assert isinstance(delta, dict)
        assert delta["status"] == "compared"
        assert isinstance(delta["similarity_ratio"], float)
        publication = payload["publication_observation"]
        assert isinstance(publication, dict)
        assert publication["canonical_pm01_bound"] is False
        pipeline = payload["pipeline_snapshot"]
        assert isinstance(pipeline, dict)
        assert pipeline["run_id"] == str(run.id)
        assert await session.scalar(
            select(func.count()).select_from(PublishedContent)
        ) == 0
        assert await session.scalar(select(func.count()).select_from(PublishEvent)) == 0


@pytest.mark.asyncio
async def test_publish_assisted_replay_is_idempotent() -> None:
    async with isolated_session() as session:
        _project, run, _snapshot = await create_run(session)
        kwargs = {
            "source_run_id": run.id,
            "phase": "draft",
            "actor_id": "founder",
            "content_markdown": "# Draft\n\nA real founder-edited draft.",
            "note": "same observation",
        }
        first = await record_publish_assisted_observation(session, **kwargs)
        second = await record_publish_assisted_observation(session, **kwargs)

        assert first.replayed is False
        assert second.replayed is True
        assert second.artifact.id == first.artifact.id
        assert await session.scalar(
            select(func.count())
            .select_from(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.artifact_type == ASSISTED_OBSERVATION_ARTIFACT_TYPE,
            )
        ) == 1


@pytest.mark.asyncio
async def test_publish_assisted_published_snapshot_requires_public_url() -> None:
    async with isolated_session() as session:
        _project, run, _snapshot = await create_run(session)
        with pytest.raises(
            PublishAssistedError,
            match="publish_assisted_published_url_required",
        ):
            await record_publish_assisted_observation(
                session,
                source_run_id=run.id,
                phase="published",
                actor_id="founder",
                content_markdown="# Published\n\nVisible article.",
            )


@pytest.mark.asyncio
async def test_publish_assisted_published_snapshot_records_url_without_canonical_pm01() -> None:
    async with isolated_session() as session:
        _project, run, _snapshot = await create_run(session)
        result = await record_publish_assisted_observation(
            session,
            source_run_id=run.id,
            phase="published",
            actor_id="founder",
            content_markdown="# Published\n\nVisible article.",
            canonical_url="https://motgu.com/example-article/",
            external_id="wp-123",
        )

        payload = result.artifact.content_json
        assert isinstance(payload, dict)
        publication = payload["publication_observation"]
        assert isinstance(publication, dict)
        assert publication["canonical_url"] == "https://motgu.com/example-article/"
        assert publication["external_id"] == "wp-123"
        assert publication["canonical_pm01_bound"] is False
        assert result.artifact.external_ref == "https://motgu.com/example-article/"


@pytest.mark.asyncio
async def test_publish_assisted_source_artifact_must_share_case_and_locale() -> None:
    async with isolated_session() as session:
        _project, first_run, _snapshot = await create_run(session)
        _project2, second_run, _snapshot2 = await create_run(session)
        foreign = Artifact(
            run_id=second_run.id,
            step_run_id=None,
            artifact_type="journal_draft",
            locale="vi-VN",
            version=1,
            content_json=_draft_payload(),
            content_hash="b" * 64,
        )
        session.add(foreign)
        await session.flush()

        with pytest.raises(
            PublishAssistedError,
            match="publish_assisted_source_artifact_mismatch",
        ):
            await record_publish_assisted_observation(
                session,
                source_run_id=first_run.id,
                phase="draft",
                actor_id="founder",
                content_markdown="# Manual\n\nDraft.",
                source_artifact_id=foreign.id,
            )


@pytest.mark.asyncio
async def test_publish_assisted_captures_pipeline_job_state() -> None:
    async with isolated_session() as session:
        _project, run, _snapshot = await create_run(session)
        step = StepRun(
            run_id=run.id,
            step_key="start_to_angle",
            attempt=1,
            status="running",
        )
        session.add(step)
        await session.flush()
        job = Job(
            run_id=run.id,
            step_run_id=step.id,
            status="failed",
            available_at=datetime.now(UTC),
            attempt=3,
            dedupe_key=f"publish-assisted-test:{run.id}",
        )
        session.add(job)
        await session.flush()

        result = await record_publish_assisted_observation(
            session,
            source_run_id=run.id,
            phase="draft",
            actor_id="founder",
            content_markdown="# Draft\n\nObserved while the shadow lane is blocked.",
        )

        payload = result.artifact.content_json
        assert isinstance(payload, dict)
        pipeline = payload["pipeline_snapshot"]
        assert isinstance(pipeline, dict)
        jobs = pipeline["jobs"]
        assert isinstance(jobs, list)
        assert jobs == [
            {
                "id": str(job.id),
                "attempt": 3,
                "status": "failed",
                "step_key": "start_to_angle",
            }
        ]
