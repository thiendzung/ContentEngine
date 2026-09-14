from __future__ import annotations

from datetime import UTC, datetime
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
from app.modules.content_engine.journal.operator_worker import (
    claim_next_operator_job,
    execute_start_to_angle_job,
    fail_start_to_angle_job,
    heartbeat_operator_job,
)
from app.modules.content_engine.journal.router import FounderJournalIntakeRequest
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    NeedHypothesisSignal,
    Signal,
)
from app.modules.harness.agent_runner import (
    AgentCapability,
    AgentRunRequest,
    AgentRunResult,
    AgentRunnerRegistry,
)
from app.modules.harness.models import Artifact, ContentRun, ContextManifest, Job, ModelCall, StepRun
from app.modules.harness.persistence import enqueue_job
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    EvidenceSet,
    EvidenceSetApproval,
    OriginalityPack,
    Source,
    SourceDocument,
)
from app.modules.knowledge.persistence import content_hash, evidence_set_hash
from app.modules.research.contracts import ProductionResearchResult
from app.modules.research.evidence.contracts import EvidenceResearchResult


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


class ControlledEvidenceWorkflow:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, session: object, **kwargs: object) -> EvidenceResearchResult:
        self.calls += 1
        request = kwargs["request"]
        content_opportunity_id = request.content_opportunity_id
        db = session
        content_case = await db.scalar(
            select(ContentCase).where(
                ContentCase.content_opportunity_id == content_opportunity_id
            )
        )
        assert content_case is not None
        source = Source(
            project_id=content_case.project_id,
            source_type="web",
            title="Controlled read-source evidence",
            canonical_url=f"https://example.test/pr45/{uuid4()}",
            locale="en",
            provenance_json={"fixture": "pr45-controlled-research"},
            captured_at=datetime.now(UTC),
            fingerprint=f"pr45-source-{uuid4().hex}",
        )
        db.add(source)
        await db.flush()
        text = "Relief artwork can be evaluated by inspecting materials and physical finish."
        document = SourceDocument(
            source_id=source.id,
            document_version=1,
            canonical_url=source.canonical_url,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash(text),
            content_markdown=text,
            metadata_json={"fixture": "pr45-controlled-research"},
            reader="fixture",
            provider="fixture-reader",
        )
        claim = Claim(
            project_id=content_case.project_id,
            statement="Physical materials and finish are inspectable evaluation inputs.",
            claim_type="fact",
            entity_refs_json=[],
        )
        db.add_all([document, claim])
        await db.flush()
        evidence = Evidence(
            claim_id=claim.id,
            source_document_id=document.id,
            locator="fixture:paragraph-1",
            excerpt=text,
            relation="supports",
            quality_metadata_json={"fixture": True},
            provenance_json={
                "method": "read_excerpt_link",
                "source_id": str(source.id),
                "source_document_id": str(document.id),
                "source_document_hash": document.content_hash,
                "reader": document.reader,
                "provider": document.provider,
            },
            verified_at=datetime.now(UTC),
        )
        db.add(evidence)
        await db.flush()
        member_ids = [str(evidence.id)]
        evidence_set = EvidenceSet(
            project_id=content_case.project_id,
            content_case_id=content_case.id,
            version=1,
            evidence_ids_json=member_ids,
            content_hash=evidence_set_hash(member_ids),
            status="draft",
        )
        db.add(evidence_set)
        await db.flush()
        production = ProductionResearchResult(
            request=request.research,
            stop_reason="controlled_fixture_sufficient",
            sufficient=True,
        )
        return EvidenceResearchResult(
            research=production,
            content_case_id=content_case.id,
            source_document_ids=[document.id],
            claim_ids=[claim.id],
            evidence_ids=[evidence.id],
            relation_counts={"supports": 1},
            evidence_set_id=evidence_set.id,
            evidence_set_version=evidence_set.version,
            evidence_set_content_hash=evidence_set.content_hash,
            evidence_set_status=evidence_set.status,
            research_gaps=[],
            evidence_eligible=True,
        )


class ControlledCodexRunner:
    def __init__(self) -> None:
        self.calls = 0
        self.received_context: dict[str, object] | None = None

    async def preflight(self) -> AgentCapability:
        return AgentCapability(
            provider="codex_cli",
            executable="fixture-codex",
            version="codex-cli 0.154.0-alpha.6.2",
            authenticated=True,
            auth_mode="fixture",
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.calls += 1
        context = request.working_context
        self.received_context = context
        model_input = context["angle_model_input"]
        assert isinstance(model_input, dict)
        evidence_set = model_input["evidence_set"]
        originality_pack = model_input["originality_pack"]
        opportunity = model_input["opportunity"]
        context_input = model_input["context"]
        assert isinstance(evidence_set, dict)
        assert isinstance(originality_pack, dict)
        assert isinstance(opportunity, dict)
        assert isinstance(context_input, dict)
        evidence_items = evidence_set["evidence"]
        originality_items = originality_pack["items"]
        assert isinstance(evidence_items, list) and evidence_items
        assert isinstance(originality_items, list) and originality_items
        evidence_item = evidence_items[0]
        originality_item = originality_items[0]
        assert isinstance(evidence_item, dict)
        assert isinstance(originality_item, dict)
        evidence_ref = evidence_item["evidence_id"]
        originality_ref = originality_item["source_ref"]
        locale = opportunity["locale"]
        candidates = [
            {
                "angle_id": f"pr45-angle-{index}",
                "working_title": f"How to inspect relief artwork: angle {index}",
                "reader_problem": "The visitor needs a grounded evaluation method.",
                "central_question": "What can the visitor inspect before deciding?",
                "core_promise": "Use inspectable evidence and MOTGU first-party context.",
                "point_of_view": "Separate external facts from MOTGU editorial judgment.",
                "why_now": "The visitor is preparing to evaluate artwork in person.",
                "evidence_refs": [evidence_ref],
                "originality_refs": [originality_ref],
                "excluded_claims": ["Do not infer customer demand from the Founder brief."],
                "risks": ["Do not generalize one source into a universal rule."],
                "confidence": 0.8,
                "locale": locale,
            }
            for index in range(1, 4)
        ]
        return AgentRunResult(
            provider=request.provider,
            model=request.model,
            runner_version="fixture-codex",
            structured_output=candidates,
            raw_output_hash="a" * 64,
            exit_code=0,
            usage={"input_tokens": 100, "output_tokens": 50},
            duration_ms=5,
        )


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


@pytest.mark.asyncio
async def test_start_to_angle_worker_e2e_stops_at_angle_gate(
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
            **_intake_kwargs(key="pr45-e2e-create"),
        )
        ready = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=ready.state_version,
            idempotency_key="pr45-e2e-start",
        )
        assert queued.job_id is not None
        leased = await claim_next_operator_job(
            session,
            worker_id="worker-pr45-e2e",
            lease_seconds=900,
        )
        assert leased is not None
        assert leased.id == queued.job_id
        before_expiry = leased.lease_expires_at
        assert before_expiry is not None
        heartbeat = await heartbeat_operator_job(
            session,
            job_id=leased.id,
            worker_id="worker-pr45-e2e",
            lease_seconds=1200,
        )
        assert heartbeat.lease_expires_at is not None
        assert heartbeat.lease_expires_at > before_expiry

        workflow = ControlledEvidenceWorkflow()
        runner = ControlledCodexRunner()
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", runner)
        result = await execute_start_to_angle_job(
            session,
            job_id=leased.id,
            worker_id="worker-pr45-e2e",
            evidence_workflow=workflow,
            runner_registry=registry,
        )
        assert workflow.calls == 1
        assert runner.calls == 1
        assert result.job_id == leased.id

        job = await session.get(Job, leased.id)
        step = await session.get(StepRun, leased.step_run_id)
        run = await session.get(ContentRun, created.bootstrap_run_id)
        assert job is not None and job.status == "completed"
        assert job.lease_owner is None
        assert step is not None and step.status == "completed"
        assert run is not None
        assert run.status == "waiting_approval"
        assert run.current_step == "angle"

        state = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        assert state.status == "AWAITING_APPROVAL"
        assert state.human_gate == "angle"
        assert state.primary_intent is None
        assert state.allowed_intents == []

        angle = await session.get(Artifact, result.angle_artifact_id)
        assert angle is not None
        assert angle.artifact_type == "angle_candidates"
        bundles = list(
            (
                await session.scalars(
                    select(Artifact)
                    .where(
                        Artifact.run_id == run.id,
                        Artifact.artifact_type == "journal_input_bundle",
                    )
                    .order_by(Artifact.version.desc())
                )
            ).all()
        )
        assert bundles
        latest_bundle = bundles[0]
        assert latest_bundle.content_json is not None
        assert "context_manifest" in latest_bundle.content_json
        research_audit = latest_bundle.content_json.get("research_execution")
        assert isinstance(research_audit, dict)
        assert research_audit["executed_in_stage"] == "start_to_angle"
        assert research_audit["evidence_count"] == 1

        manifests = list(
            (
                await session.scalars(
                    select(ContextManifest).where(ContextManifest.run_id == run.id)
                )
            ).all()
        )
        assert len(manifests) == 1
        manifest = manifests[0]
        assert latest_bundle.content_json["context_manifest"] == {
            "id": str(manifest.id),
            "content_hash": manifest.content_hash,
        }
        assert runner.received_context is not None
        angle_model_input = runner.received_context["angle_model_input"]
        assert isinstance(angle_model_input, dict)
        context_input = angle_model_input.get("context")
        assert isinstance(context_input, dict)
        assert context_input["manifest_id"] == str(manifest.id)

        evidence_set = await session.scalar(
            select(EvidenceSet).where(EvidenceSet.content_case_id == created.content_case_id)
        )
        assert evidence_set is not None
        assert evidence_set.status == "locked"
        assert evidence_set.locked_by == "policy:strict_read_source_v1"
        assert (
            await session.scalar(
                select(func.count(EvidenceSetApproval.id)).where(
                    EvidenceSetApproval.evidence_set_id == evidence_set.id
                )
            )
            == 0
        )
        model_call = await session.scalar(
            select(ModelCall).where(ModelCall.run_id == run.id)
        )
        assert model_call is not None
        assert model_call.status == "completed"

        receipt = await session.get(OperatorCommand, queued.command_id)
        assert receipt is not None
        assert receipt.status == "completed"
        assert receipt.error_code is None
        assert receipt.state_after == state.state_version


@pytest.mark.asyncio
async def test_failed_worker_attempt_is_manual_retryable(
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
            **_intake_kwargs(key="pr45-retry-create"),
        )
        ready = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        first = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=ready.state_version,
            idempotency_key="pr45-retry-start",
        )
        assert first.job_id is not None
        leased = await claim_next_operator_job(
            session,
            worker_id="worker-pr45-retry",
        )
        assert leased is not None
        await fail_start_to_angle_job(
            session,
            job_id=leased.id,
            worker_id="worker-pr45-retry",
            failure_class="insufficient_evidence",
            message="Controlled research did not produce enough evidence.",
        )

        failed = await session.get(Job, leased.id)
        step = await session.get(StepRun, leased.step_run_id)
        run = await session.get(ContentRun, created.bootstrap_run_id)
        assert failed is not None and failed.status == "failed"
        assert step is not None and step.status == "running"
        assert run is not None and run.status in {"pending", "running"}
        assert run.current_step == "start_to_angle"

        retry_state = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        assert retry_state.status == "BLOCKED"
        assert retry_state.primary_intent == "retry"
        assert retry_state.allowed_intents == ["retry"]
        retry = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="retry",
            expected_state_version=retry_state.state_version,
            idempotency_key="pr45-retry-command",
        )
        assert retry.job_id is not None
        assert retry.job_id != failed.id
        retry_job = await session.get(Job, retry.job_id)
        assert retry_job is not None
        assert retry_job.attempt == 2
        assert retry_job.step_run_id == step.id
        assert retry_job.status == "queued"
        claimed_retry = await claim_next_operator_job(
            session,
            worker_id="worker-pr45-retry-2",
        )
        assert claimed_retry is not None
        assert claimed_retry.id == retry_job.id

        first_receipt = await session.get(OperatorCommand, first.command_id)
        assert first_receipt is not None
        assert first_receipt.status == "failed"
        assert first_receipt.error_code == "insufficient_evidence"
