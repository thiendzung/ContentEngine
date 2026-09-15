from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    LocaleVariant,
    NeedHypothesis,
    Project,
    SettingsSnapshot,
)
from app.modules.harness.model_policy import verify_route_decision
from app.modules.harness.model_policy_models import ModelRouteDecision
from app.modules.harness.models import ContentRun, ModelCall, StepRun
from app.modules.harness.runtime import (
    ContextInputs,
    ModelCandidate,
    RuntimeConfigurationError,
    SettingsModelRouter,
    build_context_manifest,
    start_model_call,
)


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


def policy_settings(*, max_calls: int = 2) -> dict[str, object]:
    return {
        "models": {
            "angle": {
                "policy": "journal_production",
                "capability": "balanced_reasoning",
            }
        },
        "model_policies": {
            "journal_production": {
                "version": 1,
                "allowed_providers": ["codex_cli"],
                "capabilities": {
                    "balanced_reasoning": {
                        "candidates": [
                            {"provider": "codex_cli", "model": "balanced-v1"},
                            {"provider": "codex_cli", "model": "strong-v1"},
                        ],
                        "max_escalations": 1,
                        "allowed_escalation_reasons": [
                            "validation_failure",
                            "quality_failure",
                            "runtime_failure",
                        ],
                        "max_model_calls_per_step": max_calls,
                    }
                },
            }
        },
    }


def snapshot(*, settings: dict[str, object] | None = None) -> SettingsSnapshot:
    return SettingsSnapshot(
        id=uuid4(),
        project_id=uuid4(),
        resolved_settings_json=settings or policy_settings(),
        source_version_refs_json=["settings:test-policy"],
        content_hash="a" * 64,
    )


def test_policy_router_selects_primary_and_bounded_escalation() -> None:
    settings_snapshot = snapshot()
    router = SettingsModelRouter()

    primary = router.resolve(
        task_key="angle",
        settings_snapshot=settings_snapshot,
    )
    assert primary.route_key == "policy:journal_production:balanced_reasoning"
    assert primary.primary.provider == "codex_cli"
    assert primary.primary.model == "balanced-v1"
    assert primary.primary.policy_selection is not None
    assert primary.primary.policy_selection.candidate_index == 0
    assert primary.primary.policy_selection.escalation_reason is None
    assert primary.fallbacks == ()

    escalation = router.resolve(
        task_key="angle",
        settings_snapshot=settings_snapshot,
        attempt_index=1,
        escalation_reason="quality_failure",
    )
    assert escalation.primary.provider == "codex_cli"
    assert escalation.primary.model == "strong-v1"
    assert escalation.primary.policy_selection is not None
    assert escalation.primary.policy_selection.candidate_index == 1
    assert escalation.primary.policy_selection.escalation_reason == "quality_failure"

    with pytest.raises(
        RuntimeConfigurationError,
        match="model_policy_escalation_reason_required",
    ):
        router.resolve(
            task_key="angle",
            settings_snapshot=settings_snapshot,
            attempt_index=1,
        )
    with pytest.raises(
        RuntimeConfigurationError,
        match="model_policy_escalation_reason_not_allowed",
    ):
        router.resolve(
            task_key="angle",
            settings_snapshot=settings_snapshot,
            attempt_index=1,
            escalation_reason="because_i_want_to",
        )
    with pytest.raises(
        RuntimeConfigurationError,
        match="model_policy_escalation_limit_exceeded",
    ):
        router.resolve(
            task_key="angle",
            settings_snapshot=settings_snapshot,
            attempt_index=2,
            escalation_reason="quality_failure",
        )


def test_policy_router_fails_closed_on_provider_and_budget_misconfiguration() -> None:
    disallowed = policy_settings()
    policy = disallowed["model_policies"]
    assert isinstance(policy, dict)
    journal = policy["journal_production"]
    assert isinstance(journal, dict)
    capabilities = journal["capabilities"]
    assert isinstance(capabilities, dict)
    balanced = capabilities["balanced_reasoning"]
    assert isinstance(balanced, dict)
    candidates = balanced["candidates"]
    assert isinstance(candidates, list)
    second = candidates[1]
    assert isinstance(second, dict)
    second["provider"] = "unapproved_provider"
    with pytest.raises(RuntimeConfigurationError, match="model_policy_provider_not_allowed"):
        SettingsModelRouter().resolve(
            task_key="angle",
            settings_snapshot=snapshot(settings=disallowed),
        )

    with pytest.raises(
        RuntimeConfigurationError,
        match="model_policy_max_calls_blocks_escalation",
    ):
        SettingsModelRouter().resolve(
            task_key="angle",
            settings_snapshot=snapshot(settings=policy_settings(max_calls=1)),
        )


def test_legacy_router_remains_exact_and_rejects_policy_escalation_inputs() -> None:
    legacy = snapshot(
        settings={
            "models": {"draft": {"route": "writer"}},
            "model_routes": {
                "writer": {
                    "provider": "provider-a",
                    "model": "writer-v1",
                    "fallbacks": [
                        {"provider": "provider-b", "model": "writer-v2"}
                    ],
                }
            },
        }
    )
    route = SettingsModelRouter().resolve(task_key="draft", settings_snapshot=legacy)
    assert route.primary == ModelCandidate(provider="provider-a", model="writer-v1")
    assert route.fallbacks == (
        ModelCandidate(provider="provider-b", model="writer-v2"),
    )
    with pytest.raises(
        RuntimeConfigurationError,
        match="legacy_model_route_escalation_not_supported",
    ):
        SettingsModelRouter().resolve(
            task_key="draft",
            settings_snapshot=legacy,
            attempt_index=1,
            escalation_reason="quality_failure",
        )


async def create_policy_runtime(
    session: AsyncSession,
) -> tuple[ContentRun, StepRun, SettingsSnapshot]:
    project = (
        await session.execute(select(Project).where(Project.slug == "motgu"))
    ).scalar_one()
    suffix = uuid4().hex[:8]
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement=f"Routing policy need {suffix}",
        audience_scope="test",
        situation="routing policy test",
        origin="founder_proposed",
        status="PROPOSED",
        alternative_explanations_json=[],
        missing_evidence_json=[],
    )
    session.add(need)
    await session.flush()
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader="test",
        situation="routing policy test",
        need="bounded model spend",
        question="Can route selection be audited?",
        intent="learn",
        promise="route deterministically",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new=f"routing policy {suffix}",
        next_discovery_step="none",
        decision="CREATE",
        priority="NOW",
        reasons_json=["test"],
        suggested_content_type="journal",
        selected_by="founder",
        selected_at=datetime.now(UTC),
        selection_reason="routing policy test",
    )
    session.add(opportunity)
    await session.flush()
    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="test routing",
        content_hypothesis="bounded routing reduces spend drift",
        originality_statement="synthetic only",
        reader_before="unrouted",
        reader_after="routed",
        status="draft",
    )
    session.add(content_case)
    await session.flush()
    locale = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="primary",
        primary_question="Can route selection be audited?",
        primary_intent="learn",
        status="draft",
    )
    settings_snapshot = SettingsSnapshot(
        project_id=project.id,
        resolved_settings_json=policy_settings(),
        source_version_refs_json=["settings:test-policy"],
        content_hash="b" * 64,
    )
    session.add_all([locale, settings_snapshot])
    await session.flush()
    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=locale.id,
        run_mode="create",
        status="running",
        current_step="angle",
        settings_snapshot_id=settings_snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    step = StepRun(
        run_id=run.id,
        step_key="angle",
        attempt=1,
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add(step)
    await session.flush()
    return run, step, settings_snapshot


@pytest.mark.asyncio
async def test_policy_call_persists_audit_and_budget_blocks_third_call_before_insert() -> None:
    async with isolated_session() as session:
        run, step, settings_snapshot = await create_policy_runtime(session)
        manifest = await build_context_manifest(
            session,
            run_id=run.id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version="angle:v1",
                recipe_version="journal_angle:v1",
            ),
        )
        router = SettingsModelRouter()
        primary = router.resolve(task_key="angle", settings_snapshot=settings_snapshot)
        first_call = await start_model_call(
            session,
            run_id=run.id,
            step_run_id=step.id,
            context_manifest_id=manifest.id,
            task_key="angle",
            route=primary.primary,
            purpose="policy primary",
            prompt_version="angle:v1",
        )
        first_decision = await session.scalar(
            select(ModelRouteDecision).where(
                ModelRouteDecision.model_call_id == first_call.id
            )
        )
        assert first_decision is not None
        assert first_decision.candidate_index == 0
        assert first_decision.policy_key == "journal_production"
        assert first_decision.capability == "balanced_reasoning"
        assert first_decision.settings_snapshot_id == settings_snapshot.id
        assert verify_route_decision(
            first_decision,
            settings_snapshot=settings_snapshot,
        )["model"] == "balanced-v1"

        escalation = router.resolve(
            task_key="angle",
            settings_snapshot=settings_snapshot,
            attempt_index=1,
            escalation_reason="quality_failure",
        )
        second_call = await start_model_call(
            session,
            run_id=run.id,
            step_run_id=step.id,
            context_manifest_id=manifest.id,
            task_key="angle",
            route=escalation.primary,
            purpose="policy escalation",
            prompt_version="angle:v1",
        )
        second_decision = await session.scalar(
            select(ModelRouteDecision).where(
                ModelRouteDecision.model_call_id == second_call.id
            )
        )
        assert second_decision is not None
        assert second_decision.candidate_index == 1
        assert second_decision.escalation_reason == "quality_failure"

        before_calls = await session.scalar(
            select(func.count(ModelCall.id)).where(ModelCall.step_run_id == step.id)
        )
        assert before_calls == 2
        with pytest.raises(
            RuntimeConfigurationError,
            match="model_policy_call_budget_exhausted",
        ):
            await start_model_call(
                session,
                run_id=run.id,
                step_run_id=step.id,
                context_manifest_id=manifest.id,
                task_key="angle",
                route=primary.primary,
                purpose="must not start",
                prompt_version="angle:v1",
            )
        after_calls = await session.scalar(
            select(func.count(ModelCall.id)).where(ModelCall.step_run_id == step.id)
        )
        assert after_calls == 2


@pytest.mark.asyncio
async def test_route_decision_database_row_is_immutable() -> None:
    async with isolated_session() as session:
        run, step, settings_snapshot = await create_policy_runtime(session)
        manifest = await build_context_manifest(
            session,
            run_id=run.id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version="angle:v1",
                recipe_version="journal_angle:v1",
            ),
        )
        route = SettingsModelRouter().resolve(
            task_key="angle",
            settings_snapshot=settings_snapshot,
        )
        call = await start_model_call(
            session,
            run_id=run.id,
            step_run_id=step.id,
            context_manifest_id=manifest.id,
            task_key="angle",
            route=route.primary,
            purpose="immutable audit",
            prompt_version="angle:v1",
        )
        decision = await session.scalar(
            select(ModelRouteDecision).where(ModelRouteDecision.model_call_id == call.id)
        )
        assert decision is not None
        decision.capability = "tampered"
        with pytest.raises(DBAPIError, match="model_route_decision_is_immutable"):
            async with session.begin_nested():
                await session.flush()
