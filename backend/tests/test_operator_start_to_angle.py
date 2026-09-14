from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from test_ce05_review_revise import isolated_session

import app.modules.content_engine.journal.operator_vertical_slice as vertical_slice
from app.modules.content_engine.journal.models import (
    JournalIntakeSpec,
    JournalRequiredLocale,
    OperatorCommand,
)
from app.modules.content_engine.journal.operator_control import OperatorControlError
from app.modules.content_engine.journal.operator_manual_intake import (
    create_founder_journal_intake,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    get_operator_state_v45,
    submit_operator_command_v45,
)
from app.modules.content_engine.journal.operator_worker import claim_next_operator_job
from app.modules.content_engine.journal.router import FounderJournalIntakeRequest
from app.modules.content_engine.models import (
    ContentOpportunity,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    NeedHypothesisSignal,
    Signal,
)
from app.modules.harness.models import Job, StepRun
from app.modules.harness.persistence import enqueue_job
from app.modules.knowledge.models import OriginalityPack


async def _ready_preflight() -> dict[str, object]:
    return {"status": "READY", "checks": []}


def _intake_kwargs(*, key: str) -> dict[str, object]:
    return {
        "project_slug": "motgu",
        "source_locale": "en",
        "research_country": "vn",
        "required_locales": ["vi", "en"],
        "reader": "International visitor researching Vietnamese art",
        "situation": "Planning what to see and buy during a Vietnam trip",
        "need": "Understand how to evaluate locally made relief artwork",
        "question": "How can a visitor evaluate locally made relief artwork in Vietnam?",
        "intent": "learn",
        "promise": "Give a practical, evidence-backed evaluation framework.",
        "selection_reason": "Founder wants this Journal as a useful acquisition entry point.",
        "originality_material": (
            "MOTGU evaluates relief work by material honesty, surface depth, craft decisions, "
            "and how the work behaves in a real interior."
        ),
        "originality_writer_use": (
            "Use this as a first-party MOTGU perspective after factual claims are grounded."
        ),
        "originality_guardrails": (
            "Do not present this first-party perspective as independent market or customer "
            "evidence."
        ),
        "idempotency_key": key,
        "actor_id": "founder",
    }


@pytest.mark.asyncio
async def test_founder_manual_intake_preserves_provenance_and_requirements() -> None:
    async with isolated_session() as session:
        signals_before = int(await session.scalar(select(func.count(Signal.id))) or 0)

        first = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="pr45-founder-intake"),
        )
        replay = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="pr45-founder-intake"),
        )

        assert first.replayed is False
        assert replay.replayed is True
        assert replay.command_id == first.command_id
        assert replay.content_case_id == first.content_case_id
        assert replay.bootstrap_run_id == first.bootstrap_run_id
        assert replay.originality_pack_id == first.originality_pack_id
        assert first.required_locales == ["en", "vi"]
        assert first.research_country == "vn"
        assert first.state.status == "READY"
        assert first.state.primary_intent == "start"

        need = await session.get(NeedHypothesis, first.need_hypothesis_id)
        opportunity = await session.get(ContentOpportunity, first.content_opportunity_id)
        assert need is not None
        assert opportunity is not None
        assert need.origin == "founder_manual"
        assert need.status == "PROPOSED"
        assert opportunity.decision == "CREATE"
        assert opportunity.selected_by == "founder"
        assert (
            await session.scalar(
                select(func.count(NeedHypothesisSignal.need_hypothesis_id)).where(
                    NeedHypothesisSignal.need_hypothesis_id == need.id
                )
            )
            == 0
        )
        assert int(await session.scalar(select(func.count(Signal.id))) or 0) == signals_before
        assert (
            await session.scalar(
                select(func.count(HumanSelection.id)).where(
                    HumanSelection.content_opportunity_id == opportunity.id
                )
            )
            == 1
        )

        spec = await session.scalar(
            select(JournalIntakeSpec).where(
                JournalIntakeSpec.content_case_id == first.content_case_id
            )
        )
        assert spec is not None
        assert spec.source_locale == "en"
        assert spec.research_country == "vn"

        requirements = list(
            (
                await session.scalars(
                    select(JournalRequiredLocale)
                    .where(JournalRequiredLocale.content_case_id == first.content_case_id)
                    .order_by(JournalRequiredLocale.locale)
                )
            ).all()
        )
        assert [(row.locale, row.role) for row in requirements] == [
            ("en", "source"),
            ("vi", "translation"),
        ]
        variants = list(
            (
                await session.scalars(
                    select(LocaleVariant).where(
                        LocaleVariant.content_case_id == first.content_case_id
                    )
                )
            ).all()
        )
        assert [row.locale for row in variants] == ["en"]

        pack = await session.get(OriginalityPack, first.originality_pack_id)
        assert pack is not None
        assert pack.status == "approved"
        assert pack.approved_by == "founder"
        assert pack.snapshot_hash is not None
        assert len(pack.item_refs_json) == 1
        item = pack.item_refs_json[0]
        assert item["type"] == "motgu_owned_material"
        assert str(item["source_ref"]).startswith("founder_manual_intake:")

        step = await session.get(StepRun, first.state.current_step_run_id)
        assert step is not None
        assert step.step_key == "start_to_angle"
        assert step.status == "pending"
        assert (
            await session.scalar(
                select(func.count(Job.id)).where(Job.run_id == first.bootstrap_run_id)
            )
            == 0
        )

        receipt = await session.get(OperatorCommand, first.command_id)
        assert receipt is not None
        assert receipt.resolved_action_key == "founder_manual_journal_intake"
        assert receipt.status == "completed"


@pytest.mark.asyncio
async def test_manual_intake_same_key_changed_payload_conflicts() -> None:
    async with isolated_session() as session:
        await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="pr45-founder-conflict"),
        )
        changed = _intake_kwargs(key="pr45-founder-conflict")
        changed["need"] = "A changed brief must not replay under the same key"
        with pytest.raises(OperatorControlError) as conflict:
            await create_founder_journal_intake(session, **changed)
        assert conflict.value.code == "operator_idempotency_conflict"


@pytest.mark.asyncio
async def test_intake_http_contract_forbids_internal_execution_selection() -> None:
    payload = _intake_kwargs(key="pr45-http-boundary")
    payload.pop("actor_id")
    payload["stage_key"] = "start_to_angle"
    payload["model"] = "gpt-5.6-sol"
    with pytest.raises(ValidationError):
        FounderJournalIntakeRequest.model_validate(payload)


@pytest.mark.asyncio
async def test_start_queue_replay_and_worker_claim_skip_unrelated_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vertical_slice,
        "build_operational_preflight",
        _ready_preflight,
    )
    async with isolated_session() as session:
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="pr45-queue-create"),
        )
        unrelated_step = StepRun(
            run_id=created.bootstrap_run_id,
            step_key="review_revise_en",
            attempt=99,
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
            dedupe_key=f"unrelated:{uuid4()}",
        )

        state = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        assert state.status == "READY"
        assert state.primary_intent == "start"
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="pr45-start-command",
        )
        replay = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="pr45-start-command",
        )
        assert queued.job_id is not None
        assert replay.replayed is True
        assert replay.command_id == queued.command_id
        assert replay.job_id == queued.job_id

        leased = await claim_next_operator_job(session, worker_id="worker-pr45")
        assert leased is not None
        assert leased.id == queued.job_id
        assert leased.id != unrelated_job.id
        untouched = await session.get(Job, unrelated_job.id)
        assert untouched is not None
        assert untouched.status == "queued"
        start_step = await session.get(StepRun, leased.step_run_id)
        assert start_step is not None
        assert start_step.step_key == "start_to_angle"
        assert start_step.status == "running"
