from __future__ import annotations

import pytest
from sqlalchemy.exc import DBAPIError
from test_model_routing_policy_v1 import create_policy_runtime, isolated_session

from app.modules.harness.runtime import (
    ContextInputs,
    SettingsModelRouter,
    build_context_manifest,
    start_model_call,
)


async def _routed_call(session):
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
        purpose="audit identity guard",
        prompt_version="angle:v1",
    )
    return call


@pytest.mark.asyncio
async def test_routed_model_call_identity_is_immutable_but_telemetry_remains_mutable() -> None:
    async with isolated_session() as session:
        call = await _routed_call(session)
        call.model = "tampered-model"
        with pytest.raises(DBAPIError, match="routed_model_call_identity_is_immutable"):
            async with session.begin_nested():
                await session.flush()

        await session.refresh(call)
        call.status = "completed"
        call.input_tokens = 120
        call.output_tokens = 40
        call.latency_ms = 75
        call.finish_reason = "stop"
        await session.flush()

        assert call.status == "completed"
        assert call.input_tokens == 120
        assert call.output_tokens == 40
        assert call.latency_ms == 75


@pytest.mark.asyncio
async def test_routed_model_call_cannot_be_deleted_after_audit_binding() -> None:
    async with isolated_session() as session:
        call = await _routed_call(session)
        with pytest.raises(DBAPIError, match="routed_model_call_delete_forbidden"):
            async with session.begin_nested():
                await session.delete(call)
                await session.flush()
