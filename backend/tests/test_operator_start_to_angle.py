from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_review_revise import isolated_session

import app.modules.content_engine.journal.operator_vertical_slice as vertical_slice
from app.modules.content_engine.journal.models import JournalRequiredLocale, OperatorCommand
from app.modules.content_engine.journal.operator_control import OperatorControlError
from app.modules.content_engine.journal.operator_manual_intake import create_founder_journal_intake
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
    PromptDefinition,
    RecipeDefinition,
    SettingsVersion,
    Signal,
)
from app.modules.harness.agent_runner import (
    AgentCapability,
    AgentRunnerRegistry,
    AgentRunRequest,
    AgentRunResult,
)
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ContextManifest,
    Job,
    ModelCall,
    StepRun,
)
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
        "selection_reason": "Founder selected this Journal as an acquisition entry point.",
        "originality_material": (
            "MOTGU evaluates relief work by material honesty and craft decisions."
        ),
        "originality_writer_use": (
            "Use as first-party MOTGU perspective after factual grounding."
        ),
        "originality_guardrails": (
            "Do not present first-party perspective as market evidence."
        ),
        "idempotency_key": key,
        "actor_id": "founder",
    }


async def _activate_seeded_angle_runtime(session: AsyncSession) -> None:
    settings = await session.scalar(
        select(SettingsVersion).where(
            SettingsVersion.scope_type == "content_type",
            SettingsVersion.scope_key == "journal",
            SettingsVersion.version == 1,
        )
    )
    prompt = await session.scalar(
        select(PromptDefinition).where(
            PromptDefinition.prompt_key == "journal_angle_candidates",
            PromptDefinition.version == 1,
        )
    )
    recipe = await session.scalar(
        select(RecipeDefinition).where(
            RecipeDefinition.recipe_key == "journal_angle_v1",
            RecipeDefinition.version == 1,
        )
    )
    assert settings is not None and settings.status == "draft"
    assert prompt is not None and prompt.status == "draft"
    assert recipe is not None and recipe.status == "draft"
    settings.status = "active"
    settings.approved_by = "test-founder"
    settings.change_reason = "Test-only activation of exact seeded Angle runtime."
    prompt.status = "active"
    prompt.approved_by = "test-founder"
    recipe.status = "active"
    recipe.approved_by = "test-founder"
    await session.flush()


class ControlledEvidenceWorkflow:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, session: AsyncSession, **kwargs: object) -> EvidenceResearchResult:
        self.calls += 1
        request = kwargs["request"]
        opportunity_id = request.content_opportunity_id  # type: ignore[attr-defined]
        content_case = await session.scalar(
            select(ContentCase).where(ContentCase.content_opportunity_id == opportunity_id)
        )
        assert content_case is not None
        source = Source(
            project_id=content_case.project_id,
            source_type="web",
            title="Controlled read-source evidence",
            canonical_url=f"https://example.test/pr45/{uuid4()}",
            locale="en",
            provenance_json={"fixture": "pr45"},
            captured_at=datetime.now(UTC),
            fingerprint=f"pr45-source-{uuid4().hex}",
        )
        session.add(source)
        await session.flush()
        text = "Relief artwork can be evaluated by inspecting materials and physical finish."
        document = SourceDocument(
            source_id=source.id,
            document_version=1,
            canonical_url=source.canonical_url,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash(text),
            content_markdown=text,
            metadata_json={"fixture": "pr45"},
            reader="fixture",
            provider="fixture-reader",
        )
        claim = Claim(
            project_id=content_case.project_id,
            statement="Physical materials and finish are inspectable evaluation inputs.",
            claim_type="fact",
            entity_refs_json=[],
        )
        session.add_all([document, claim])
        await session.flush()
        evidence = Evidence(
            claim_id=claim.id,
            source_document_id=document.id,
            locator="fixture:paragraph-1",
            excerpt=text,
            relation="supports",
            quality_metadata_json={"fixture": True},
            provenance_json={
                "method": "read_excerpt_link",
                "source_document_id": str(document.id),
                "source_document_hash": document.content_hash,
            },
            verified_at=datetime.now(UTC),
        )
        session.add(evidence)
        await session.flush()
        members = [str(evidence.id)]
        evidence_set = EvidenceSet(
            project_id=content_case.project_id,
            content_case_id=content_case.id,
            version=1,
            evidence_ids_json=members,
            content_hash=evidence_set_hash(members),
            status="draft",
        )
        session.add(evidence_set)
        await session.flush()
        production = ProductionResearchResult(
            request=request.research,  # type: ignore[attr-defined]
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
            evidence_set_version=1,
            evidence_set_content_hash=evidence_set.content_hash,
            evidence_set_status="draft",
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
        self.received_context = request.working_context
        model_input = request.working_context["angle_model_input"]
        assert isinstance(model_input, dict)
        evidence_set = model_input["evidence_set"]
        originality_pack = model_input["originality_pack"]
        opportunity = model_input["opportunity"]
        assert isinstance(evidence_set, dict)
        assert isinstance(originality_pack, dict)
        assert isinstance(opportunity, dict)
        evidence = evidence_set["evidence"]
        originality = originality_pack["items"]
        assert isinstance(evidence, list) and evidence
        assert isinstance(originality, list) and originality
        evidence_item = evidence[0]
        originality_item = originality[0]
        assert isinstance(evidence_item, dict)
        assert isinstance(originality_item, dict)
        candidates = [
            {
                "angle_id": f"pr45-angle-{index}",
                "working_title": f"How to inspect relief artwork: angle {index}",
                "reader_problem": "The visitor needs a grounded evaluation method.",
                "central_question": "What can the visitor inspect before deciding?",
                "core_promise": "Use inspectable evidence and MOTGU context.",
                "point_of_view": (
                    "Separate external facts from MOTGU editorial judgment."
                ),
                "why_now": "The visitor is preparing to evaluate artwork in person.",
                "evidence_refs": [evidence_item["evidence_id"]],
                "originality_refs": [originality_item["source_ref"]],
                "excluded_claims": [
                    "Do not infer customer demand from Founder input."
                ],
                "risks": ["Do not generalize one source into a universal rule."],
                "confidence": 0.8,
                "locale": opportunity["locale"],
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
async def test_founder_intake_preserves_provenance_requirements_and_replay() -> None:
    async with isolated_session() as session:
        signals_before = int(await session.scalar(select(func.count(Signal.id))) or 0)
        first = await create_founder_journal_intake(
            session, **_intake_kwargs(key="pr45-intake")
        )
        replay = await create_founder_journal_intake(
            session, **_intake_kwargs(key="pr45-intake")
        )
        assert replay.replayed and replay.command_id == first.command_id
        assert first.required_locales == ["en", "vi"]
        assert first.state.status == "READY" and first.state.primary_intent == "start"
        need = await session.get(NeedHypothesis, first.need_hypothesis_id)
        opportunity = await session.get(ContentOpportunity, first.content_opportunity_id)
        assert need is not None and need.origin == "founder_manual" and need.status == "PROPOSED"
        assert opportunity is not None and opportunity.selected_by == "founder"
        assert int(await session.scalar(select(func.count(Signal.id))) or 0) == signals_before
        assert await session.scalar(
            select(func.count(NeedHypothesisSignal.need_hypothesis_id)).where(
                NeedHypothesisSignal.need_hypothesis_id == need.id
            )
        ) == 0
        assert await session.scalar(
            select(func.count(HumanSelection.id)).where(
                HumanSelection.content_opportunity_id == opportunity.id
            )
        ) == 1
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
        assert pack is not None and pack.status == "approved"
        assert pack.approved_by == "founder"


@pytest.mark.asyncio
async def test_intake_conflict_and_http_internal_selection_fail_closed() -> None:
    async with isolated_session() as session:
        await create_founder_journal_intake(
            session, **_intake_kwargs(key="pr45-conflict")
        )
        changed = _intake_kwargs(key="pr45-conflict")
        changed["need"] = "Changed brief"
        with pytest.raises(OperatorControlError, match="operator_idempotency_conflict"):
            await create_founder_journal_intake(session, **changed)
    payload = _intake_kwargs(key="pr45-http")
    payload.pop("actor_id")
    payload["stage_key"] = "start_to_angle"
    with pytest.raises(ValidationError):
        FounderJournalIntakeRequest.model_validate(payload)


@pytest.mark.asyncio
async def test_worker_claim_is_stage_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vertical_slice, "build_operational_preflight", _ready_preflight)
    async with isolated_session() as session:
        created = await create_founder_journal_intake(
            session, **_intake_kwargs(key="pr45-scope")
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
            session, content_case_id=created.content_case_id
        )
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="pr45-scope-start",
        )
        leased = await claim_next_operator_job(session, worker_id="worker-pr45")
        assert queued.job_id is not None and leased is not None
        assert leased.id == queued.job_id and leased.id != unrelated_job.id
        untouched = await session.get(Job, unrelated_job.id)
        assert untouched is not None and untouched.status == "queued"


@pytest.mark.asyncio
async def test_start_to_angle_worker_e2e_stops_at_angle_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vertical_slice, "build_operational_preflight", _ready_preflight)
    async with isolated_session() as session:
        await _activate_seeded_angle_runtime(session)
        created = await create_founder_journal_intake(
            session, **_intake_kwargs(key="pr45-e2e")
        )
        state = await get_operator_state_v45(
            session, content_case_id=created.content_case_id
        )
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="pr45-e2e-start",
        )
        assert queued.job_id is not None
        leased = await claim_next_operator_job(
            session,
            worker_id="worker-pr45-e2e",
            lease_seconds=900,
        )
        assert leased is not None
        expiry = leased.lease_expires_at
        heartbeat = await heartbeat_operator_job(
            session,
            job_id=leased.id,
            worker_id="worker-pr45-e2e",
            lease_seconds=1200,
        )
        assert expiry is not None and heartbeat.lease_expires_at is not None
        assert heartbeat.lease_expires_at > expiry
        workflow = ControlledEvidenceWorkflow()
        runner = ControlledCodexRunner()
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", runner)
        result = await execute_start_to_angle_job(
            session,
            job_id=leased.id,
            worker_id="worker-pr45-e2e",
            evidence_workflow=workflow,  # type: ignore[arg-type]
            runner_registry=registry,
        )
        assert workflow.calls == 1 and runner.calls == 1
        job = await session.get(Job, leased.id)
        step = await session.get(StepRun, leased.step_run_id)
        run = await session.get(ContentRun, created.bootstrap_run_id)
        assert job is not None and job.status == "completed" and job.lease_owner is None
        assert step is not None and step.status == "completed"
        assert run is not None and run.status == "waiting_approval"
        assert run.current_step == "angle"
        final_state = await get_operator_state_v45(
            session, content_case_id=created.content_case_id
        )
        assert final_state.status == "AWAITING_APPROVAL"
        assert final_state.human_gate == "angle"
        angle = await session.get(Artifact, result.angle_artifact_id)
        assert angle is not None and angle.artifact_type == "angle_candidates"
        bundle = await session.scalar(
            select(Artifact)
            .where(
                Artifact.run_id == run.id,
                Artifact.artifact_type == "journal_input_bundle",
            )
            .order_by(Artifact.version.desc())
            .limit(1)
        )
        assert bundle is not None and bundle.content_json is not None
        manifest_ref = bundle.content_json["context_manifest"]
        assert isinstance(manifest_ref, dict)
        manifest = await session.get(ContextManifest, manifest_ref["id"])
        assert manifest is not None
        assert manifest_ref["content_hash"] == manifest.content_hash
        assert manifest.evidence_set_id is not None
        assert manifest.originality_pack_id is not None
        assert runner.received_context is not None
        model_input = runner.received_context["angle_model_input"]
        assert isinstance(model_input, dict)
        context_input = model_input["context"]
        assert isinstance(context_input, dict)
        assert context_input["manifest_id"] == str(manifest.id)
        research_audit = bundle.content_json["research_execution"]
        assert isinstance(research_audit, dict)
        assert research_audit["evidence_count"] == 1
        evidence_set = await session.scalar(
            select(EvidenceSet).where(
                EvidenceSet.content_case_id == created.content_case_id
            )
        )
        assert evidence_set is not None and evidence_set.status == "locked"
        assert evidence_set.locked_by == "policy:strict_read_source_v1"
        approval = await session.scalar(
            select(EvidenceSetApproval).where(
                EvidenceSetApproval.evidence_set_id == evidence_set.id
            )
        )
        assert approval is not None
        assert approval.evidence_set_version == evidence_set.version
        assert approval.evidence_set_content_hash == evidence_set.content_hash
        assert approval.approved_by == "policy:strict_read_source_v1"
        assert "Machine policy attestation" in approval.approval_reason
        model_call = await session.scalar(
            select(ModelCall).where(ModelCall.run_id == run.id)
        )
        receipt = await session.get(OperatorCommand, queued.command_id)
        assert model_call is not None and model_call.status == "completed"
        assert receipt is not None and receipt.status == "completed"
        assert receipt.state_after == final_state.state_version


@pytest.mark.asyncio
async def test_failed_attempt_remains_explicitly_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vertical_slice, "build_operational_preflight", _ready_preflight)
    async with isolated_session() as session:
        created = await create_founder_journal_intake(
            session, **_intake_kwargs(key="pr45-retry")
        )
        state = await get_operator_state_v45(
            session, content_case_id=created.content_case_id
        )
        first = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="pr45-retry-start",
        )
        leased = await claim_next_operator_job(
            session, worker_id="worker-pr45-retry"
        )
        assert first.job_id is not None and leased is not None
        await fail_start_to_angle_job(
            session,
            job_id=leased.id,
            worker_id="worker-pr45-retry",
            failure_class="insufficient_evidence",
            message="Controlled insufficient evidence.",
        )
        failed = await session.get(Job, leased.id)
        step = await session.get(StepRun, leased.step_run_id)
        assert failed is not None and failed.status == "failed"
        assert step is not None and step.status == "running"
        retry_state = await get_operator_state_v45(
            session, content_case_id=created.content_case_id
        )
        assert retry_state.allowed_intents == ["retry"]
        retry = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="retry",
            expected_state_version=retry_state.state_version,
            idempotency_key="pr45-retry-command",
        )
        retry_job = await session.get(Job, retry.job_id)
        first_receipt = await session.get(OperatorCommand, first.command_id)
        assert retry_job is not None
        assert retry_job.attempt == 2 and retry_job.step_run_id == step.id
        assert first_receipt is not None and first_receipt.status == "failed"
        assert first_receipt.error_code == "insufficient_evidence"
