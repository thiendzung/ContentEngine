from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.content_coverage import (
    ContentCoverageError,
    build_content_coverage,
)
from app.modules.content_engine.journal.review_console import (
    ReviewConsoleError,
    get_review_case,
)
from app.modules.content_engine.models import (
    AudienceHypothesis,
    ContentCase,
    ContentExperiment,
    ContentItem,
    ContentItemJourneyStage,
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
    NeedHypothesis,
    Project,
    SettingsSnapshot,
)
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ContextManifest,
)
from app.modules.harness.outbox import (
    OutboxIntent,
    ReconciliationRequiredError,
)
from app.modules.harness.persistence import (
    claim_next_job,
    pause_for_approval,
    resolve_approval,
    transition_run,
)
from app.modules.measurement.models import (
    ContentPerformanceObservation,
    PerformanceMetric,
    PerformanceSnapshot,
)
from app.modules.measurement.service import (
    MetricInput,
    get_measurement_identity,
    ingest_performance_snapshot,
    record_performance_observation,
)
from app.modules.publishing import service as publishing_service
from app.modules.publishing.models import PublishedContent, PublishEvent
from app.modules.publishing.service import (
    PublishError,
    WordPressReconciliation,
    WordPressWriteRequest,
    WordPressWriteResult,
    begin_wordpress_dispatch,
    execute_wordpress_call,
    execute_wordpress_reconciliation,
    prepare_publish_package,
    prepare_wordpress_dispatch,
    prepare_wordpress_reconciliation,
    record_wordpress_execution_result,
    record_wordpress_reconciliation,
    submit_publish_decision,
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


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _content(locale: str = "en") -> dict[str, object]:
    return {
        "schema_version": 1,
        "draft": {
            "locale": locale,
            "title": "How to Check an Artwork Before You Buy",
            "standfirst": "Use a few calm checks before deciding.",
            "lead_markdown": "Start with what you can verify.",
            "sections": [
                {
                    "section_id": "signals",
                    "heading": "Signals worth checking",
                    "body_markdown": "A signal tells you what to inspect, not what to conclude.",
                    "evidence_refs": [],
                    "originality_refs": [],
                    "unresolved_factual_claims": [],
                }
            ],
            "closing_markdown": "Ask for provenance when it matters to your decision.",
            "lead_evidence_refs": [],
            "lead_originality_refs": [],
            "internal_link_intents": ["artwork provenance guide"],
            "unresolved_factual_claims": [],
        },
    }


@dataclass
class PMFixture:
    project: Project
    need: NeedHypothesis
    opportunity: ContentOpportunity
    content_case: ContentCase
    variant: LocaleVariant
    item: ContentItem
    source_run: ContentRun
    version: ContentVersion
    final_artifact: Artifact
    experiment: ContentExperiment


async def _fake_quality_refs(
    _session: AsyncSession,
    *,
    content_case_id: UUID,
    locale_variant_id: UUID,
    final_artifact_id: UUID,
) -> dict[str, object]:
    del _session
    return {
        "assertion_audit": {
            "artifact": {
                "id": str(uuid4()),
                "version": 1,
                "content_hash": "1" * 64,
            },
            "evaluation_id": str(uuid4()),
            "result": "pass",
        },
        "source_copy": {
            "artifact": {
                "id": str(uuid4()),
                "version": 1,
                "content_hash": "2" * 64,
            },
            "evaluation_id": str(uuid4()),
            "result": "pass",
        },
        "reader_value": {
            "artifact": {
                "id": str(uuid4()),
                "version": 1,
                "content_hash": "3" * 64,
            },
            "evaluation_id": str(uuid4()),
            "result": "pass",
        },
        "search_ai": {
            "artifact": {
                "id": str(uuid4()),
                "version": 1,
                "content_hash": "4" * 64,
            },
            "evaluation_id": str(uuid4()),
            "result": "warn",
        },
        "binding": {
            "content_case_id": str(content_case_id),
            "locale_variant_id": str(locale_variant_id),
            "final_artifact_id": str(final_artifact_id),
        },
    }


async def _fixture(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> PMFixture:
    monkeypatch.setattr(
        publishing_service,
        "_quality_refs",
        _fake_quality_refs,
    )
    now = datetime.now(UTC)
    project = Project(
        slug=f"pm01-{uuid4().hex[:8]}",
        name="PM-01 fixture",
        default_locale="en",
    )
    session.add(project)
    await session.flush()

    audience = AudienceHypothesis(
        project_id=project.id,
        name="First-time international art buyer",
        description="A visitor buying original art for the first time.",
        status="TESTING",
    )
    session.add(audience)
    await session.flush()

    need = NeedHypothesis(
        project_id=project.id,
        audience_hypothesis_id=audience.id,
        type="question",
        statement="How can I check an artwork before buying?",
        audience_scope="first-time international art buyer",
        situation="considering an original artwork in Vietnam",
        origin="founder_proposed",
        status="TESTING",
        version=3,
    )
    session.add(need)
    await session.flush()

    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader="first-time international art buyer",
        situation="before buying an artwork",
        need="reduce uncertainty before deciding",
        question="How can I check an artwork before buying?",
        intent="evaluate",
        promise="A calm verification path.",
        what_is_actually_new="MOTGU separates signals from proof.",
        next_discovery_step="Check real provenance material.",
        decision="CREATE",
        priority="NOW",
        suggested_content_type="journal",
        suggested_role="cluster",
        selected_by="founder",
        selected_at=now,
        selection_reason="Useful pre-purchase question.",
    )
    session.add(opportunity)
    await session.flush()

    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        audience_hypothesis_id=audience.id,
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="Verify before deciding.",
        content_hypothesis="Clear checks can reduce avoidable uncertainty.",
        originality_statement="MOTGU separates observable signals from conclusions.",
        reader_before="Unsure what can be verified.",
        reader_after="Knows what to check and what still needs evidence.",
    )
    session.add(content_case)
    await session.flush()

    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="cluster",
        primary_question=opportunity.question,
        primary_intent="evaluate",
        primary_query="how to check an artwork before buying",
    )
    session.add(variant)
    await session.flush()

    item = ContentItem(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_type="journal",
        canonical_key=f"journal:{content_case.id}:en",
    )
    session.add(item)
    await session.flush()
    session.add(
        ContentItemJourneyStage(
            content_item_id=item.id,
            stage_key="trust",
            linked_by="founder",
            reason="Helps the buyer verify before purchase.",
        )
    )
    snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json={},
        source_version_refs_json=["pm01:test"],
        content_hash="a" * 64,
    )
    session.add(snapshot)
    await session.flush()

    source_run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_item_id=item.id,
        run_mode="create",
        status="running",
        current_step="final_review",
        settings_snapshot_id=snapshot.id,
        started_at=now,
    )
    session.add(source_run)
    await session.flush()

    final_payload = _content()
    final_artifact = Artifact(
        run_id=source_run.id,
        artifact_type="final_content",
        locale="en",
        version=1,
        content_json=final_payload,
        content_hash=_hash(final_payload),
    )
    session.add(final_artifact)
    session.add(
        ContextManifest(
            run_id=source_run.id,
            settings_snapshot_id=snapshot.id,
            prompt_version="journal_writer_en:v1",
            recipe_version="journal_writer_en_v1:v1",
            content_hash="b" * 64,
        )
    )
    await session.flush()

    await pause_for_approval(
        session,
        run_id=source_run.id,
        step_key="final_review",
        artifact_id=final_artifact.id,
    )
    final_approval = await resolve_approval(
        session,
        run_id=source_run.id,
        step_key="final_review",
        artifact_id=final_artifact.id,
        decision="approved",
        actor_id="founder",
        comment="Approved final content.",
    )
    assert final_approval.decision == "approved"

    version = ContentVersion(
        content_item_id=item.id,
        version_no=1,
        final_artifact_id=final_artifact.id,
        change_reason="Founder approved final content.",
        status="approved",
        content_json=final_payload,
        created_by_run_id=source_run.id,
    )
    session.add(version)
    await transition_run(
        session,
        run_id=source_run.id,
        status="completed",
    )

    experiment = ContentExperiment(
        project_id=project.id,
        content_opportunity_id=opportunity.id,
        need_hypothesis_id=need.id,
        hypothesis_version=need.version,
        expected_behaviour="Reader continues to provenance or artwork detail.",
        measurement_plan_json=["7d search exposure", "30d transitions and inquiry"],
        metric_definitions_json=[
            "impressions",
            "clicks",
            "sessions",
            "engaged_sessions",
            "artwork_transition",
            "inquiry",
        ],
        minimum_evidence_json=["non-zero exposure", "review window reached"],
        review_window_start=now,
        review_window_end=now + timedelta(days=30),
        status="PLANNED",
    )
    session.add(experiment)

    lens_run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        run_mode="create",
        status="completed",
        current_step="lens_selection",
        settings_snapshot_id=snapshot.id,
        started_at=now - timedelta(minutes=10),
        completed_at=now - timedelta(minutes=9),
    )
    session.add(lens_run)
    await session.flush()
    lens_payload = {
        "schema_version": 1,
        "artifact_type": "lens_selection",
        "run_ref": {
            "run_id": str(lens_run.id),
            "step_run_id": None,
            "content_case_id": str(content_case.id),
            "locale_variant_id": str(variant.id),
            "locale": "en",
        },
        "primary_lens": "SIGNALS",
        "merged_lenses": ["METHOD"],
    }
    session.add(
        Artifact(
            run_id=lens_run.id,
            artifact_type="lens_selection",
            locale="en",
            version=1,
            content_json=lens_payload,
            content_hash=_hash(lens_payload),
        )
    )
    await session.flush()

    return PMFixture(
        project=project,
        need=need,
        opportunity=opportunity,
        content_case=content_case,
        variant=variant,
        item=item,
        source_run=source_run,
        version=version,
        final_artifact=final_artifact,
        experiment=experiment,
    )


class FakeWordPress:
    def __init__(self, *, unknown_first: bool = False) -> None:
        self.unknown_first = unknown_first
        self.execute_count = 0
        self.reconcile_count = 0
        self.records: dict[str, WordPressWriteResult] = {}

    async def execute(self, request: WordPressWriteRequest) -> WordPressWriteResult:
        self.execute_count += 1
        external_id = request.expected_external_id or "101"
        status = "draft" if request.action == "draft" else "publish"
        success = WordPressWriteResult(
            outcome="confirmed_success",
            external_id=external_id,
            canonical_url="https://motgu.com/journal/check-an-artwork",
            external_revision_id=f"rev-{self.execute_count}",
            external_status=status,
            published_at=datetime.now(UTC) if status == "publish" else None,
        )
        self.records[request.idempotency_key] = success
        if self.unknown_first and self.execute_count == 1:
            return WordPressWriteResult(
                outcome="unknown",
                message="connection closed after request body was sent",
            )
        return success

    async def reconcile(
        self,
        request: WordPressWriteRequest,
    ) -> WordPressReconciliation:
        self.reconcile_count += 1
        row = self.records.get(request.idempotency_key)
        if row is None:
            return WordPressReconciliation(outcome="confirmed_absent")
        return WordPressReconciliation(
            outcome="confirmed_success",
            external_id=row.external_id,
            canonical_url=row.canonical_url,
            external_revision_id=row.external_revision_id,
            external_status=row.external_status,
            published_at=row.published_at,
        )


async def _approve_and_claim(
    session: AsyncSession,
    *,
    package_run_id: UUID,
    package_artifact_id: UUID,
    worker_id: str,
):
    decision = await submit_publish_decision(
        session,
        publish_run_id=package_run_id,
        package_artifact_id=package_artifact_id,
        decision="approved",
        actor_id="founder",
        comment="Authorized external WordPress handoff.",
    )
    dispatch = await prepare_wordpress_dispatch(
        session,
        publish_run_id=package_run_id,
        package_artifact_id=package_artifact_id,
    )
    claimed = await claim_next_job(
        session,
        worker_id=worker_id,
        lease_duration=timedelta(minutes=5),
    )
    assert claimed is not None
    assert claimed.id == dispatch.job.id
    return decision, dispatch, claimed


@pytest.mark.asyncio
async def test_pm01_draft_then_publish_and_measurement_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, monkeypatch)

        draft_package = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="draft",
        )
        assert draft_package.run.status == "waiting_approval"
        with pytest.raises(PublishError, match="publish_dispatch_state_invalid"):
            await prepare_wordpress_dispatch(
                session,
                publish_run_id=draft_package.run.id,
                package_artifact_id=draft_package.artifact.id,
            )

        _decision, _dispatch, claimed = await _approve_and_claim(
            session,
            package_run_id=draft_package.run.id,
            package_artifact_id=draft_package.artifact.id,
            worker_id="pm01-draft-worker",
        )
        gateway = FakeWordPress()
        prepared = await begin_wordpress_dispatch(
            session,
            job_id=claimed.id,
            worker_id="pm01-draft-worker",
        )
        assert prepared.dispatch.intent.status == "processing"
        external = await execute_wordpress_call(
            gateway=gateway,
            request=prepared.request,
        )
        mapping, draft_event = await record_wordpress_execution_result(
            session,
            job_id=claimed.id,
            worker_id="pm01-draft-worker",
            result=external,
        )
        assert mapping is not None
        assert draft_event is not None
        assert draft_event.action == "draft"
        assert mapping.external_status == "draft"
        assert fixture.version.status == "approved"
        assert fixture.experiment.status == "PLANNED"

        publish_package = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        _decision, _dispatch, claimed = await _approve_and_claim(
            session,
            package_run_id=publish_package.run.id,
            package_artifact_id=publish_package.artifact.id,
            worker_id="pm01-publish-worker",
        )
        prepared = await begin_wordpress_dispatch(
            session,
            job_id=claimed.id,
            worker_id="pm01-publish-worker",
        )
        assert prepared.request.expected_external_id == "101"
        external = await execute_wordpress_call(
            gateway=gateway,
            request=prepared.request,
        )
        mapping2, publish_event = await record_wordpress_execution_result(
            session,
            job_id=claimed.id,
            worker_id="pm01-publish-worker",
            result=external,
        )
        assert mapping2 is not None and publish_event is not None
        assert mapping2.id == mapping.id
        assert publish_event.action == "update_publish"
        assert mapping2.external_status == "publish"
        assert mapping2.published_at is not None
        assert fixture.version.status == "approved"
        assert mapping2.current_content_version_id == fixture.version.id
        assert publish_event.content_version_id == fixture.version.id
        assert publish_event.content_experiment_id == fixture.experiment.id
        assert fixture.item.status == "published"
        assert fixture.experiment.status == "RUNNING"
        assert fixture.experiment.content_version_id == fixture.version.id

        coverage = await build_content_coverage(
            session,
            project_id=fixture.project.id,
            need_id=fixture.need.id,
            locale="en",
        )
        assert coverage["needs"][0]["coverage_status"] == "PUBLISHED"
        review = await get_review_case(
            session,
            content_case_id=fixture.content_case.id,
        )
        assert review.locales[0].publication_state == "PUBLISHED"
        assert review.locales[0].next_action == "PUBLISHED"

        window_end = datetime.now(UTC)
        window_start = window_end - timedelta(days=7)
        first = await ingest_performance_snapshot(
            session,
            published_content_id=mapping2.id,
            content_version_id=fixture.version.id,
            provider="search_console",
            window_start=window_start,
            window_end=window_end,
            raw_metrics={
                "page": mapping2.canonical_url,
                "queries": ["check artwork before buying"],
            },
            metrics=[
                MetricInput(
                    metric_date=window_end,
                    metric_name="impressions",
                    metric_value=120,
                ),
                MetricInput(
                    metric_date=window_end,
                    metric_name="clicks",
                    metric_value=9,
                ),
            ],
        )
        replay = await ingest_performance_snapshot(
            session,
            published_content_id=mapping2.id,
            content_version_id=fixture.version.id,
            provider="search_console",
            window_start=window_start,
            window_end=window_end,
            raw_metrics={
                "page": mapping2.canonical_url,
                "queries": ["check artwork before buying"],
            },
            metrics=[
                MetricInput(
                    metric_date=window_end,
                    metric_name="impressions",
                    metric_value=120,
                ),
                MetricInput(
                    metric_date=window_end,
                    metric_name="clicks",
                    metric_value=9,
                ),
            ],
        )
        assert replay.replayed is True
        assert replay.snapshot.id == first.snapshot.id
        assert [row.id for row in replay.metrics] == [row.id for row in first.metrics]

        observation = await record_performance_observation(
            session,
            published_content_id=mapping2.id,
            content_version_id=fixture.version.id,
            observation_type="search_exposure",
            statement="The page has early search exposure; this does not prove the Need.",
            data_status="EARLY_SIGNAL",
            observed_at=window_end,
            metric_refs=[row.id for row in first.metrics],
        )
        assert observation.data_status == "EARLY_SIGNAL"

        identity = await get_measurement_identity(
            session,
            published_content_id=mapping2.id,
        )
        assert identity["content"]["content_version_id"] == str(fixture.version.id)
        assert identity["content"]["source_content_version_id"] == str(
            fixture.version.id
        )
        assert identity["customer"]["need_hypothesis_id"] == str(fixture.need.id)
        assert identity["customer"]["journey_stages"] == ["trust"]
        assert identity["lens_selection"]["primary_lens"] == "SIGNALS"
        assert identity["experiment"]["id"] == str(fixture.experiment.id)
        assert identity["publish_event"]["content_experiment_id"] == str(
            fixture.experiment.id
        )
        assert identity["published_content"]["canonical_url"] == mapping2.canonical_url

        assert gateway.execute_count == 2
        assert int(
            await session.scalar(select(func.count()).select_from(PublishedContent)) or 0
        ) == 1
        assert int(
            await session.scalar(select(func.count()).select_from(PublishEvent)) or 0
        ) == 2
        with pytest.raises(DBAPIError, match="pm01_publish_event_is_immutable"):
            async with session.begin_nested():
                await session.execute(
                    update(PublishEvent)
                    .where(PublishEvent.id == publish_event.id)
                    .values(action="draft")
                )
        assert int(
            await session.scalar(select(func.count()).select_from(PerformanceSnapshot)) or 0
        ) == 1
        assert int(
            await session.scalar(select(func.count()).select_from(PerformanceMetric)) or 0
        ) == 2
        assert int(
            await session.scalar(
                select(func.count()).select_from(ContentPerformanceObservation)
            )
            or 0
        ) == 1


@pytest.mark.asyncio
async def test_pm01_ambiguous_wordpress_result_reconciles_without_duplicate_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, monkeypatch)
        package = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        _decision, dispatch, claimed = await _approve_and_claim(
            session,
            package_run_id=package.run.id,
            package_artifact_id=package.artifact.id,
            worker_id="pm01-ambiguous-worker",
        )
        gateway = FakeWordPress(unknown_first=True)

        prepared = await begin_wordpress_dispatch(
            session,
            job_id=claimed.id,
            worker_id="pm01-ambiguous-worker",
        )
        result = await execute_wordpress_call(
            gateway=gateway,
            request=prepared.request,
        )
        assert result.outcome == "unknown"
        mapping, event = await record_wordpress_execution_result(
            session,
            job_id=claimed.id,
            worker_id="pm01-ambiguous-worker",
            result=result,
        )
        assert mapping is None and event is None
        await session.refresh(dispatch.intent)
        assert dispatch.intent.status == "needs_reconciliation"

        with pytest.raises(ReconciliationRequiredError):
            await begin_wordpress_dispatch(
                session,
                job_id=claimed.id,
                worker_id="pm01-ambiguous-worker",
            )

        reconciliation_call = await prepare_wordpress_reconciliation(
            session,
            job_id=claimed.id,
            worker_id="pm01-ambiguous-worker",
        )
        reconciliation = await execute_wordpress_reconciliation(
            gateway=gateway,
            request=reconciliation_call.request,
        )
        outcome, mapping, event = await record_wordpress_reconciliation(
            session,
            job_id=claimed.id,
            worker_id="pm01-ambiguous-worker",
            result=reconciliation,
        )
        assert outcome == "confirmed_success"
        assert mapping is not None and event is not None
        assert gateway.execute_count == 1
        assert gateway.reconcile_count == 1
        assert int(
            await session.scalar(select(func.count()).select_from(PublishedContent)) or 0
        ) == 1
        assert int(
            await session.scalar(select(func.count()).select_from(PublishEvent)) or 0
        ) == 1
        outbox = await session.get(OutboxIntent, dispatch.intent.id)
        assert outbox is not None and outbox.status == "completed"


@pytest.mark.asyncio
async def test_pm01_measurement_rejects_metric_provider_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, monkeypatch)
        package = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        _decision, _dispatch, claimed = await _approve_and_claim(
            session,
            package_run_id=package.run.id,
            package_artifact_id=package.artifact.id,
            worker_id="pm01-metric-worker",
        )
        gateway = FakeWordPress()
        prepared = await begin_wordpress_dispatch(
            session,
            job_id=claimed.id,
            worker_id="pm01-metric-worker",
        )
        result = await execute_wordpress_call(
            gateway=gateway,
            request=prepared.request,
        )
        mapping, _event = await record_wordpress_execution_result(
            session,
            job_id=claimed.id,
            worker_id="pm01-metric-worker",
            result=result,
        )
        assert mapping is not None
        now = datetime.now(UTC)
        with pytest.raises(
            ValueError,
            match="measurement_metric_provider_mismatch",
        ):
            await ingest_performance_snapshot(
                session,
                published_content_id=mapping.id,
                content_version_id=mapping.current_content_version_id,
                provider="search_console",
                window_start=now - timedelta(days=1),
                window_end=now,
                raw_metrics={},
                metrics=[
                    MetricInput(
                        metric_date=now,
                        metric_name="sessions",
                        metric_value=Decimal("5"),
                    )
                ],
            )


@pytest.mark.asyncio
async def test_pm01_rejected_publish_can_be_reauthorized_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, monkeypatch)
        first = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        rejected = await submit_publish_decision(
            session,
            publish_run_id=first.run.id,
            package_artifact_id=first.artifact.id,
            decision="rejected",
            actor_id="founder",
            comment="Do not publish yet.",
        )
        assert rejected.run.status == "cancelled"

        second = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        assert second.replayed is False
        assert second.run.id != first.run.id
        assert second.artifact.id != first.artifact.id
        assert second.run.status == "waiting_approval"


@pytest.mark.asyncio
async def test_pm01_live_post_cannot_be_downgraded_to_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, monkeypatch)
        live = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        _decision, _dispatch, claimed = await _approve_and_claim(
            session,
            package_run_id=live.run.id,
            package_artifact_id=live.artifact.id,
            worker_id="pm01-live-worker",
        )
        gateway = FakeWordPress()
        prepared = await begin_wordpress_dispatch(
            session,
            job_id=claimed.id,
            worker_id="pm01-live-worker",
        )
        result = await execute_wordpress_call(
            gateway=gateway,
            request=prepared.request,
        )
        mapping, _event = await record_wordpress_execution_result(
            session,
            job_id=claimed.id,
            worker_id="pm01-live-worker",
            result=result,
        )
        assert mapping is not None
        assert mapping.external_status == "publish"

        draft = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="draft",
        )
        _decision, dispatch, claimed = await _approve_and_claim(
            session,
            package_run_id=draft.run.id,
            package_artifact_id=draft.artifact.id,
            worker_id="pm01-live-draft-worker",
        )
        with pytest.raises(
            PublishError,
            match="publish_live_post_draft_overwrite_forbidden",
        ):
            await begin_wordpress_dispatch(
                session,
                job_id=claimed.id,
                worker_id="pm01-live-draft-worker",
            )
        await session.refresh(dispatch.intent)
        assert dispatch.intent.status == "pending"


@pytest.mark.asyncio
async def test_pm01_historical_published_version_can_still_receive_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, monkeypatch)
        package = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        _decision, _dispatch, claimed = await _approve_and_claim(
            session,
            package_run_id=package.run.id,
            package_artifact_id=package.artifact.id,
            worker_id="pm01-history-worker",
        )
        gateway = FakeWordPress()
        prepared = await begin_wordpress_dispatch(
            session,
            job_id=claimed.id,
            worker_id="pm01-history-worker",
        )
        result = await execute_wordpress_call(
            gateway=gateway,
            request=prepared.request,
        )
        mapping, _event = await record_wordpress_execution_result(
            session,
            job_id=claimed.id,
            worker_id="pm01-history-worker",
            result=result,
        )
        assert mapping is not None
        assert mapping.current_content_version_id == fixture.version.id
        assert fixture.version.status == "approved"

        newer_payload = json.loads(json.dumps(fixture.version.content_json))
        newer_payload["pm01_test_revision"] = "later-approved-version"
        newer = ContentVersion(
            content_item_id=fixture.item.id,
            version_no=fixture.version.version_no + 1,
            final_artifact_id=fixture.final_artifact.id,
            change_reason="Simulate a later immutable approved version.",
            status="approved",
            content_json=newer_payload,
            created_by_run_id=fixture.source_run.id,
        )
        session.add(newer)
        await session.flush()
        mapping.current_content_version_id = newer.id
        await session.flush()

        now = datetime.now(UTC)
        ingested = await ingest_performance_snapshot(
            session,
            published_content_id=mapping.id,
            content_version_id=fixture.version.id,
            provider="search_console",
            window_start=now - timedelta(days=1),
            window_end=now,
            raw_metrics={"page": mapping.canonical_url},
            metrics=[
                MetricInput(
                    metric_date=now,
                    metric_name="impressions",
                    metric_value=10,
                )
            ],
        )
        assert ingested.replayed is False
        assert ingested.snapshot.content_version_id == fixture.version.id

        historical_identity = await get_measurement_identity(
            session,
            published_content_id=mapping.id,
            content_version_id=fixture.version.id,
        )
        assert historical_identity["content"]["content_version_id"] == str(
            fixture.version.id
        )
        assert (
            historical_identity["content"]["is_current_published_content_version"]
            is False
        )
        assert historical_identity["experiment"]["id"] == str(
            fixture.experiment.id
        )


@pytest.mark.asyncio
async def test_pm01_reconciliation_validates_before_durable_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, monkeypatch)
        package = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        _decision, dispatch, claimed = await _approve_and_claim(
            session,
            package_run_id=package.run.id,
            package_artifact_id=package.artifact.id,
            worker_id="pm01-reconcile-validation-worker",
        )
        gateway = FakeWordPress(unknown_first=True)
        prepared = await begin_wordpress_dispatch(
            session,
            job_id=claimed.id,
            worker_id="pm01-reconcile-validation-worker",
        )
        unknown = await execute_wordpress_call(
            gateway=gateway,
            request=prepared.request,
        )
        assert unknown.outcome == "unknown"
        await record_wordpress_execution_result(
            session,
            job_id=claimed.id,
            worker_id="pm01-reconcile-validation-worker",
            result=unknown,
        )
        await session.refresh(dispatch.intent)
        assert dispatch.intent.status == "needs_reconciliation"

        invalid_success = WordPressReconciliation(
            outcome="confirmed_success",
            external_id="101",
            canonical_url="https://motgu.com/journal/check-an-artwork",
            external_revision_id="rev-invalid",
            external_status="draft",
            published_at=None,
        )
        with pytest.raises(PublishError, match="publish_external_status_mismatch"):
            async with session.begin_nested():
                await record_wordpress_reconciliation(
                    session,
                    job_id=claimed.id,
                    worker_id="pm01-reconcile-validation-worker",
                    result=invalid_success,
                )

        await session.refresh(dispatch.intent)
        assert dispatch.intent.status == "needs_reconciliation"
        assert int(
            await session.scalar(select(func.count()).select_from(PublishedContent)) or 0
        ) == 0
        assert int(
            await session.scalar(select(func.count()).select_from(PublishEvent)) or 0
        ) == 0


@pytest.mark.asyncio
async def test_pm01_experiment_binding_cannot_move_to_another_content_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, monkeypatch)
        first = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        assert first.experiment.content_item_id == fixture.item.id
        assert first.experiment.content_version_id == fixture.version.id

        newer = ContentVersion(
            content_item_id=fixture.item.id,
            version_no=fixture.version.version_no + 1,
            final_artifact_id=fixture.final_artifact.id,
            change_reason="PM-01 binding-conflict fixture.",
            status="approved",
            content_json=fixture.version.content_json,
            created_by_run_id=fixture.source_run.id,
        )
        session.add(newer)
        await session.flush()

        with pytest.raises(
            PublishError,
            match="publish_experiment_content_version_conflict",
        ):
            await prepare_publish_package(
                session,
                content_version_id=newer.id,
                experiment_id=fixture.experiment.id,
                slug="check-an-artwork-v2",
                action="publish",
            )

        with pytest.raises(
            DBAPIError,
            match="pm01_content_experiment_binding_is_immutable",
        ):
            async with session.begin_nested():
                await session.execute(
                    update(ContentExperiment)
                    .where(ContentExperiment.id == fixture.experiment.id)
                    .values(content_version_id=newer.id)
                )


@pytest.mark.asyncio
async def test_pm01_stale_experiment_snapshot_blocks_before_outbox_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, monkeypatch)
        package = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        _decision, dispatch, claimed = await _approve_and_claim(
            session,
            package_run_id=package.run.id,
            package_artifact_id=package.artifact.id,
            worker_id="pm01-stale-experiment-worker",
        )

        fixture.experiment.measurement_plan_json = [
            *fixture.experiment.measurement_plan_json,
            "new plan added after package approval",
        ]
        await session.flush()

        with pytest.raises(
            PublishError,
            match="publish_experiment_snapshot_stale",
        ):
            await begin_wordpress_dispatch(
                session,
                job_id=claimed.id,
                worker_id="pm01-stale-experiment-worker",
            )
        await session.refresh(dispatch.intent)
        assert dispatch.intent.status == "pending"


@pytest.mark.asyncio
async def test_pm01_analytics_conversion_and_insufficient_data_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, monkeypatch)
        package = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        _decision, _dispatch, claimed = await _approve_and_claim(
            session,
            package_run_id=package.run.id,
            package_artifact_id=package.artifact.id,
            worker_id="pm01-measurement-worker",
        )
        gateway = FakeWordPress()
        prepared = await begin_wordpress_dispatch(
            session,
            job_id=claimed.id,
            worker_id="pm01-measurement-worker",
        )
        result = await execute_wordpress_call(
            gateway=gateway,
            request=prepared.request,
        )
        mapping, _event = await record_wordpress_execution_result(
            session,
            job_id=claimed.id,
            worker_id="pm01-measurement-worker",
            result=result,
        )
        assert mapping is not None

        now = datetime.now(UTC)
        start = now - timedelta(days=1)

        analytics = await ingest_performance_snapshot(
            session,
            published_content_id=mapping.id,
            content_version_id=fixture.version.id,
            provider="analytics",
            window_start=start,
            window_end=now,
            raw_metrics={"page": mapping.canonical_url},
            metrics=[
                MetricInput(metric_date=now, metric_name="sessions", metric_value=12),
                MetricInput(
                    metric_date=now,
                    metric_name="engaged_sessions",
                    metric_value=8,
                ),
                MetricInput(
                    metric_date=now,
                    metric_name="artwork_transition",
                    metric_value=3,
                ),
            ],
        )
        assert {row.metric_name for row in analytics.metrics} == {
            "sessions",
            "engaged_sessions",
            "artwork_transition",
        }

        conversion = await ingest_performance_snapshot(
            session,
            published_content_id=mapping.id,
            content_version_id=fixture.version.id,
            provider="motgu_conversion",
            window_start=start,
            window_end=now,
            raw_metrics={"source": "motgu_internal_aggregate"},
            metrics=[
                MetricInput(
                    metric_date=now,
                    metric_name="inquiry",
                    metric_value=1,
                )
            ],
        )
        assert len(conversion.metrics) == 1
        assert conversion.metrics[0].metric_name == "inquiry"

        insufficient = await record_performance_observation(
            session,
            published_content_id=mapping.id,
            content_version_id=fixture.version.id,
            observation_type="conversion_evidence",
            statement=(
                "The current observation window is too small to support "
                "a content-performance conclusion."
            ),
            data_status="INSUFFICIENT_DATA",
            observed_at=now,
            metric_refs=[conversion.metrics[0].id],
        )
        assert insufficient.data_status == "INSUFFICIENT_DATA"


@pytest.mark.asyncio
async def test_pm01_read_models_fail_closed_on_publication_mapping_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        fixture = await _fixture(session, monkeypatch)
        package = await prepare_publish_package(
            session,
            content_version_id=fixture.version.id,
            experiment_id=fixture.experiment.id,
            slug="check-an-artwork",
            action="publish",
        )
        _decision, _dispatch, claimed = await _approve_and_claim(
            session,
            package_run_id=package.run.id,
            package_artifact_id=package.artifact.id,
            worker_id="pm01-read-drift-worker",
        )
        gateway = FakeWordPress()
        prepared = await begin_wordpress_dispatch(
            session,
            job_id=claimed.id,
            worker_id="pm01-read-drift-worker",
        )
        result = await execute_wordpress_call(
            gateway=gateway,
            request=prepared.request,
        )
        mapping, _event = await record_wordpress_execution_result(
            session,
            job_id=claimed.id,
            worker_id="pm01-read-drift-worker",
            result=result,
        )
        assert mapping is not None

        mapping.canonical_url = "https://motgu.com/journal/tampered-without-event"
        await session.flush()

        with pytest.raises(
            ContentCoverageError,
            match="content_coverage_publication_event_mismatch",
        ):
            await build_content_coverage(
                session,
                project_id=fixture.project.id,
                need_id=fixture.need.id,
                locale="en",
            )

        with pytest.raises(
            ReviewConsoleError,
            match="journal_review_publication_event_mismatch",
        ):
            await get_review_case(
                session,
                content_case_id=fixture.content_case.id,
            )

