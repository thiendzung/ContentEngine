from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from test_ce05_review_revise import isolated_session
from test_operator_start_to_angle import _intake_kwargs, _ready_preflight

import app.modules.content_engine.journal.operator_vertical_slice as vertical_slice
from app.modules.content_engine.journal.operator_history import get_operator_case_history
from app.modules.content_engine.journal.operator_manual_intake import (
    create_founder_journal_intake,
)
from app.modules.harness.models import (
    Approval,
    Artifact,
    ContentRun,
    ModelCall,
    QualityEvaluation,
    StepRun,
    ToolCall,
)


@pytest.mark.asyncio
async def test_operator_history_is_case_scoped_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vertical_slice,
        "build_journal_operator_preflight",
        _ready_preflight,
    )

    async with isolated_session() as session:
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="ux01d-sanitized-history"),
        )
        run = await session.get(ContentRun, created.bootstrap_run_id)
        assert run is not None

        run.failure_code = "safe_run_failure"
        run.failure_message = "SECRET raw run failure message"

        now = datetime.now(UTC)
        step = StepRun(
            run_id=run.id,
            step_key="ux_history_probe",
            attempt=1,
            status="failed",
            started_at=now,
            completed_at=now,
            error_json={
                "class": "safe_step_failure",
                "message": "SECRET raw step error",
                "request_body": "SECRET request body",
            },
        )
        session.add(step)
        await session.flush()

        artifact = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="ux_history_probe",
            locale="en",
            version=1,
            content_json={
                "secret": "SECRET artifact content",
                "raw_prompt": "SECRET prompt",
            },
            content_hash="a" * 64,
        )
        session.add(artifact)
        await session.flush()

        session.add_all(
            [
                ModelCall(
                    run_id=run.id,
                    step_run_id=step.id,
                    context_manifest_id=None,
                    task_key="ux_history_model",
                    provider="fixture-provider",
                    model="fixture-model",
                    purpose="quality",
                    prompt_version="fixture-v1",
                    started_at=now,
                    completed_at=now,
                    input_tokens=10,
                    output_tokens=20,
                    cost=Decimal("0.001000"),
                    latency_ms=100,
                    finish_reason="stop",
                    status="failed",
                    error_class="safe_model_failure",
                    result_artifact_id=artifact.id,
                    runtime_metadata_json={
                        "secret": "SECRET model metadata",
                        "raw_provider_payload": "SECRET provider payload",
                    },
                ),
                ToolCall(
                    run_id=run.id,
                    step_run_id=step.id,
                    tool_key="fixture_tool",
                    request_fingerprint="b" * 64,
                    started_at=now,
                    completed_at=now,
                    result_ref="private://SECRET-tool-result",
                    latency_ms=50,
                    status="failed",
                    retry_count=1,
                    error_class="safe_tool_failure",
                ),
                QualityEvaluation(
                    run_id=run.id,
                    artifact_id=artifact.id,
                    evaluator_key="fixture_quality",
                    evaluator_version="v1",
                    evaluator_type="deterministic",
                    result="warn",
                    severity="medium",
                    findings_json={"secret": "SECRET quality finding"},
                ),
                Approval(
                    run_id=run.id,
                    step_key="final_review",
                    artifact_id=artifact.id,
                    decision="approved",
                    actor_id="founder-private-id",
                    comment="SECRET private approval comment",
                ),
            ]
        )
        await session.flush()

        history = await get_operator_case_history(
            session,
            content_case_id=created.content_case_id,
        )

        payload = history.model_dump_json()
        assert "SECRET" not in payload
        assert "private://" not in payload
        assert "founder-private-id" not in payload
        assert "safe_run_failure" in payload
        assert "safe_step_failure" in payload
        assert "safe_model_failure" in payload
        assert "safe_tool_failure" in payload

        kinds = {event.kind for event in history.events}
        assert {
            "run",
            "step",
            "command",
            "approval",
            "quality",
            "model",
            "tool",
            "artifact",
        } <= kinds
        assert history.summary.failed_count >= 3
        assert history.summary.warning_count >= 1
        assert history.content_case_id == created.content_case_id
        assert history.truncated is False
