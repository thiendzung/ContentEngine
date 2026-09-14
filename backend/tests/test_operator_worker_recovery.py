from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from test_ce05_review_revise import isolated_session
from test_operator_start_to_angle import _intake_kwargs, _ready_preflight

import app.modules.content_engine.journal.operator_vertical_slice as vertical_slice
from app.modules.content_engine.journal.operator_manual_intake import (
    create_founder_journal_intake,
)
from app.modules.content_engine.journal.operator_recovery import (
    claim_or_reclaim_operator_job,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    get_operator_state_v45,
    submit_operator_command_v45,
)
from app.modules.content_engine.journal.operator_worker import claim_next_operator_job
from app.modules.harness.models import Job, StepRun
from app.modules.harness.persistence import enqueue_job


@pytest.mark.asyncio
async def test_recovery_reclaims_only_expired_start_to_angle_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vertical_slice, "build_operational_preflight", _ready_preflight)
    async with isolated_session() as session:
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="pr45-recovery-create"),
        )
        state = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="pr45-recovery-start",
        )
        assert queued.job_id is not None
        claimed = await claim_next_operator_job(
            session,
            worker_id="dead-worker",
            lease_seconds=900,
        )
        assert claimed is not None
        previous_attempt = claimed.attempt
        claimed.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)

        unrelated_step = StepRun(
            run_id=created.bootstrap_run_id,
            step_key="review_revise_en",
            attempt=77,
            status="pending",
            input_artifact_refs_json=[],
            output_artifact_refs_json=[],
        )
        session.add(unrelated_step)
        await session.flush()
        unrelated_job = await enqueue_job(
            session,
            run_id=created.bootstrap_run_id,
            step_run_id=unrelated_step.id,
            dedupe_key=f"expired-unrelated:{uuid4()}",
        )
        unrelated_step.status = "running"
        unrelated_job.status = "leased"
        unrelated_job.lease_owner = "other-dead-worker"
        unrelated_job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=2)
        await session.flush()

        recovered = await claim_or_reclaim_operator_job(
            session,
            worker_id="replacement-worker",
            lease_seconds=900,
        )
        assert recovered is not None
        assert recovered.id == claimed.id
        assert recovered.attempt == previous_attempt + 1
        assert recovered.lease_owner == "replacement-worker"
        assert recovered.lease_expires_at is not None
        assert recovered.lease_expires_at > datetime.now(UTC)

        untouched = await session.get(Job, unrelated_job.id)
        assert untouched is not None
        assert untouched.status == "leased"
        assert untouched.lease_owner == "other-dead-worker"
        assert untouched.lease_expires_at is not None
        assert untouched.lease_expires_at < datetime.now(UTC)
