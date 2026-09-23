from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select
from test_ce05_review_actions import _pending_fixture
from test_ce05_review_console import isolated_session
from test_ll01c_learning_application import _need_candidate

from app.modules.content_engine.models import Project, SettingsVersion
from app.modules.control_center.daily_digest import build_daily_digest
from app.modules.harness.models import Artifact, ModelCall
from app.modules.learning.models import (
    LearningApplication,
    LearningCandidate,
    LearningCandidateReview,
    LearningResolution,
    LearningValidation,
)
from app.modules.learning.read_model import build_learning_overview
from app.modules.system.read_model import build_system_overview


async def _counts(session) -> dict[str, int]:
    async def count(model: Any) -> int:
        return int(
            await session.scalar(select(func.count()).select_from(model)) or 0
        )

    return {
        "candidates": await count(LearningCandidate),
        "reviews": await count(LearningCandidateReview),
        "applications": await count(LearningApplication),
        "validations": await count(LearningValidation),
        "resolutions": await count(LearningResolution),
        "artifacts": await count(Artifact),
        "model_calls": await count(ModelCall),
        "settings_versions": await count(SettingsVersion),
    }


@pytest.mark.asyncio
async def test_ux01d_learning_projection_is_project_scoped_read_only_and_separates_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _fixture, _mapping, signal, assessment, candidate = await _need_candidate(
            session,
            monkeypatch,
        )
        project = await session.get(Project, candidate.project_id)
        assert project is not None
        before = await _counts(session)

        overview = await build_learning_overview(
            session,
            project_slug=project.slug,
        )

        assert await _counts(session) == before
        assert overview.project_id == project.id
        assert overview.semantics["candidate_is_not_customer_truth"] is True
        assert overview.semantics["evidence_is_not_learning_rule"] is True
        assert (
            overview.semantics["application_receipt_required_for_truth_change"]
            is True
        )
        assert overview.semantics["validation_does_not_auto_promote"] is True

        row = next(item for item in overview.candidates if item.id == candidate.id)
        assert row.statement == candidate.statement
        assert row.application is None
        assert row.review is None
        assert {item.kind for item in row.evidence} >= {
            "signal",
            "assessment_artifact",
            "measurement_observation",
        }
        assert any(
            item.kind == "signal"
            and item.id == signal.id
            and item.relation == "supports"
            for item in row.evidence
        )
        assert any(
            item.kind == "assessment_artifact"
            and item.id == assessment.artifact.id
            for item in row.evidence
        )


@pytest.mark.asyncio
async def test_ux01d_system_projection_keeps_policy_config_separate_from_runtime_health() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        project = await session.get(Project, fixture.writer_run.project_id)
        assert project is not None

        policy = SettingsVersion(
            project_id=project.id,
            scope_type="project",
            scope_key=project.slug,
            version=1,
            settings_json={
                "autopilot": {
                    "capability_policy": {
                        "schema_version": 1,
                        "enabled": True,
                        "workers": {
                            "writer-worker": {
                                "capabilities": ["READ", "WRITE_ARTIFACT"],
                                "allowed_actions": ["read.content"],
                                "forbidden_actions": ["publish.external"],
                            }
                        },
                    }
                }
            },
            status="active",
            change_reason="UX-01D system read projection fixture",
            approved_by="founder",
        )
        call = ModelCall(
            run_id=fixture.writer_run.id,
            task_key="writer",
            provider="fixture-provider",
            model="fixture-model",
            purpose="writer",
            prompt_version="fixture-v1",
            input_tokens=120,
            output_tokens=80,
            cost=Decimal("0.012300"),
            status="completed",
        )
        session.add_all([policy, call])
        await session.flush()
        before = await _counts(session)

        overview = await build_system_overview(
            session,
            project_slug=project.slug,
        )

        assert await _counts(session) == before
        assert overview.project_id == project.id
        assert (
            overview.semantics["configured_policy_is_not_runtime_state"]
            is True
        )
        assert (
            overview.semantics["historical_usage_is_not_provider_health"]
            is True
        )
        source = next(
            row
            for row in overview.automation_policy_sources
            if row.settings_version_id == policy.id
        )
        assert source.approval_recorded is True
        assert source.configured_enabled is True
        assert source.workers[0].worker_key == "writer-worker"
        assert source.workers[0].forbidden_actions == ["publish.external"]

        usage = next(
            row
            for row in overview.model_usage
            if row.provider == "fixture-provider"
            and row.model == "fixture-model"
        )
        assert usage.calls == 1
        assert usage.input_tokens == 120
        assert usage.output_tokens == 80
        assert usage.cost == Decimal("0.012300")


@pytest.mark.asyncio
async def test_ux01d_daily_digest_uses_explicit_bounded_window_and_current_coverage_snapshot() -> None:
    async with isolated_session() as session:
        fixture = await _pending_fixture(session)
        project = await session.get(Project, fixture.writer_run.project_id)
        assert project is not None
        before = await _counts(session)
        local_date = datetime.now(UTC).date()

        digest = await build_daily_digest(
            session,
            project_slug=project.slug,
            local_date=local_date,
            timezone_name="UTC",
        )

        assert await _counts(session) == before
        assert digest.project_id == project.id
        assert digest.local_date == local_date
        assert digest.timezone == "UTC"
        assert digest.window_start.hour == 0
        assert digest.window_start.tzinfo is not None
        assert digest.window_end - digest.window_start == timedelta(days=1)
        assert digest.semantics["events_are_durable_facts"] is True
        assert (
            digest.semantics["current_coverage_is_not_historical_change"]
            is True
        )
        assert (
            digest.semantics["measurement_observation_is_not_causal_proof"]
            is True
        )
        assert digest.semantics["digest_does_not_trigger_research"] is True
        assert any(event.domain == "content" for event in digest.events)
        assert any(event.domain == "production" for event in digest.events)
        assert sum(digest.current_coverage_counts.values()) >= 1
