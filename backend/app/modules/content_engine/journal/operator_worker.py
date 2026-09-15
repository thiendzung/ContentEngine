"""Allow-listed durable worker execution for Journal operator jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.content_engine.journal.agent_bridge import (
    ANGLE_PROMPT_KEY,
    ANGLE_RECIPE_KEY,
    ANGLE_TASK_KEY,
    create_cli_angle_model_port,
)
from app.modules.content_engine.journal.angle import AngleGenerator
from app.modules.content_engine.journal.context import (
    build_journal_context,
    persist_journal_context,
)
from app.modules.content_engine.journal.models import JournalIntakeSpec, OperatorCommand
from app.modules.content_engine.journal.operator_angle_bundle import (
    bind_bundle_context_manifest,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    START_TO_ANGLE_STAGE,
    get_operator_state_v45,
)
from app.modules.content_engine.journal.research_handoff import (
    JournalResearchHandoff,
    ResearchDecision,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    LocaleVariant,
    SettingsSnapshot,
)
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import ContentRun, Job, StepRun
from app.modules.harness.persistence import (
    complete_job,
    create_checkpoint,
    heartbeat_job,
    transition_run,
)
from app.modules.harness.runtime import (
    ContextInputs,
    SettingsModelRouter,
    build_context_manifest,
)
from app.modules.knowledge.brief_binding import (
    KnowledgeBriefBindingError,
    load_run_knowledge_brief_binding,
)
from app.modules.knowledge.evidence_set_approval import approve_evidence_set
from app.modules.knowledge.models import (
    Evidence,
    EvidenceSet,
    OriginalityPack,
    SourceDocument,
)
from app.modules.knowledge.originality_pack import originality_pack_snapshot_hash
from app.modules.knowledge.persistence import evidence_set_hash
from app.modules.research.contracts import ProductionResearchRequest, ResearchDepth
from app.modules.research.evidence import EvidenceResearchRequest, EvidenceResearchWorkflow
from app.modules.research.evidence.persistence import lock_evidence_set
from app.modules.system.settings_service import active_prompt_definition, active_recipe_definition


class OperatorWorkerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class WorkerExecutionResult:
    job_id: UUID
    run_id: UUID
    step_run_id: UUID
    angle_artifact_id: UUID
    angle_artifact_hash: str
    state_version: str


async def claim_next_operator_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int = 900,
) -> Job | None:
    """Claim only the allow-listed PR4.5 stage, skipping unrelated queued work."""

    if not worker_id.strip() or lease_seconds <= 0:
        raise OperatorWorkerError("operator_worker_lease_invalid")
    now = datetime.now(UTC)
    candidate = (
        select(Job.id)
        .join(StepRun, StepRun.id == Job.step_run_id)
        .where(
            Job.status == "queued",
            Job.available_at <= now,
            StepRun.step_key == START_TO_ANGLE_STAGE,
            StepRun.status.in_(("pending", "running")),
        )
        .order_by(Job.available_at, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .cte("next_operator_job")
    )
    statement = (
        update(Job)
        .where(Job.id == candidate.c.id)
        .values(
            status="leased",
            lease_owner=worker_id,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            updated_at=now,
        )
        .returning(Job)
    )
    job = (await session.execute(statement)).scalar_one_or_none()
    if job is None:
        return None
    await session.execute(
        update(StepRun)
        .where(StepRun.id == job.step_run_id, StepRun.status == "pending")
        .values(status="running", started_at=now, updated_at=now)
    )
    return job


async def heartbeat_operator_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    lease_seconds: int = 900,
) -> Job:
    """Extend an owned operator lease using the canonical harness primitive."""

    if not worker_id.strip() or lease_seconds <= 0:
        raise OperatorWorkerError("operator_worker_lease_invalid")
    return await heartbeat_job(
        session,
        job_id=job_id,
        worker_id=worker_id,
        extend_by=timedelta(seconds=lease_seconds),
    )


async def fail_start_to_angle_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    failure_class: str,
    message: str,
) -> Job:
    """Persist a failed attempt while keeping the exact stage explicitly retryable.

    The generic harness failure helper terminally fails the StepRun/ContentRun when no
    automatic retry is configured. PR4.5 deliberately has no autonomous retry: the
    operator must decide whether to retry. Therefore the durable failed Job is the
    attempt receipt, while the bounded StepRun and ContentRun remain active.
    """

    now = datetime.now(UTC)
    job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if (
        job is None
        or job.status != "leased"
        or job.lease_owner != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
    ):
        raise OperatorWorkerError("operator_worker_lease_not_owned")
    step = await session.scalar(
        select(StepRun).where(StepRun.id == job.step_run_id).with_for_update()
    )
    run = await session.scalar(
        select(ContentRun).where(ContentRun.id == job.run_id).with_for_update()
    )
    if step is None or run is None or step.run_id != run.id:
        raise OperatorWorkerError("operator_worker_binding_invalid")
    if step.step_key != START_TO_ANGLE_STAGE or step.status != "running":
        raise OperatorWorkerError("operator_worker_stage_not_allowed")
    if run.current_step != START_TO_ANGLE_STAGE or run.status not in {"pending", "running"}:
        raise OperatorWorkerError("operator_worker_run_state_invalid")

    safe_class = failure_class.strip()[:100] or "internal_error"
    safe_message = message.strip()[:2000] or safe_class
    job.status = "failed"
    job.lease_owner = None
    job.lease_expires_at = None
    job.updated_at = now
    step.error_json = {"class": safe_class, "message": safe_message}
    run.failure_code = safe_class
    run.failure_message = safe_message
    receipts = list(
        (
            await session.scalars(
                select(OperatorCommand).where(
                    OperatorCommand.job_id == job.id,
                    OperatorCommand.status == "queued",
                )
            )
        ).all()
    )
    await session.flush()
    state = await get_operator_state_v45(session, content_case_id=run.content_case_id)
    for command in receipts:
        command.status = "failed"
        command.error_code = safe_class
        command.state_after = state.state_version
    await session.flush()
    return job


async def _policy_lock_evidence_set(
    session: AsyncSession,
    *,
    evidence_set_id: UUID,
) -> EvidenceSet:
    """Attest and lock strict read-source evidence without adding a human gate."""

    policy_actor = "policy:strict_read_source_v1"
    evidence_set = await session.scalar(
        select(EvidenceSet).where(EvidenceSet.id == evidence_set_id).with_for_update()
    )
    if evidence_set is None:
        raise OperatorWorkerError("operator_worker_evidence_set_missing")
    if evidence_set.status == "locked":
        if evidence_set.locked_by != policy_actor:
            raise OperatorWorkerError("operator_worker_evidence_lock_owner_invalid")
        return evidence_set
    if evidence_set.status != "draft" or not evidence_set.evidence_ids_json:
        raise OperatorWorkerError("operator_worker_evidence_not_lockable")
    if evidence_set.content_hash != evidence_set_hash(evidence_set.evidence_ids_json):
        raise OperatorWorkerError("operator_worker_evidence_snapshot_invalid")
    try:
        evidence_ids = [UUID(value) for value in evidence_set.evidence_ids_json]
    except (TypeError, ValueError) as exc:
        raise OperatorWorkerError("operator_worker_evidence_snapshot_invalid") from exc
    if len(set(evidence_ids)) != len(evidence_ids):
        raise OperatorWorkerError("operator_worker_evidence_snapshot_invalid")
    evidence_rows = list(
        (await session.scalars(select(Evidence).where(Evidence.id.in_(evidence_ids)))).all()
    )
    if len(evidence_rows) != len(evidence_ids):
        raise OperatorWorkerError("operator_worker_evidence_member_missing")
    document_ids = {
        evidence.source_document_id
        for evidence in evidence_rows
        if evidence.source_document_id is not None
    }
    documents = list(
        (
            await session.scalars(
                select(SourceDocument).where(SourceDocument.id.in_(document_ids))
            )
        ).all()
    )
    documents_by_id = {document.id: document for document in documents}
    if len(documents_by_id) != len(document_ids):
        raise OperatorWorkerError("operator_worker_evidence_document_missing")
    for evidence in evidence_rows:
        provenance = evidence.provenance_json
        document = (
            documents_by_id.get(evidence.source_document_id)
            if evidence.source_document_id is not None
            else None
        )
        if (
            document is None
            or evidence.verified_at is None
            or not isinstance(provenance, dict)
            or provenance.get("method") != "read_excerpt_link"
            or provenance.get("source_document_id") != str(document.id)
            or provenance.get("source_document_hash") != document.content_hash
        ):
            raise OperatorWorkerError("operator_worker_evidence_policy_rejected")

    approval = await approve_evidence_set(
        session,
        evidence_set_id=evidence_set.id,
        expected_version=evidence_set.version,
        expected_content_hash=evidence_set.content_hash,
        approved_by=policy_actor,
        approval_reason=(
            "Machine policy attestation: every Evidence member is verified and bound "
            "to the exact read SourceDocument snapshot before Journal handoff."
        ),
    )
    return await lock_evidence_set(
        session,
        evidence_set_id=evidence_set.id,
        locked_by=policy_actor,
        approval_id=approval.id,
    )


async def execute_start_to_angle_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    evidence_workflow: EvidenceResearchWorkflow,
    runner_registry: AgentRunnerRegistry,
) -> WorkerExecutionResult:
    """Execute the exact leased Start-to-Angle job and stop at the Angle gate."""

    job = await session.get(Job, job_id)
    if (
        job is None
        or job.status != "leased"
        or job.lease_owner != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= datetime.now(UTC)
    ):
        raise OperatorWorkerError("operator_worker_lease_not_owned")
    step = await session.get(StepRun, job.step_run_id)
    run = await session.get(ContentRun, job.run_id)
    if step is None or run is None or step.run_id != run.id:
        raise OperatorWorkerError("operator_worker_binding_invalid")
    if step.step_key != START_TO_ANGLE_STAGE or step.status != "running":
        raise OperatorWorkerError("operator_worker_stage_not_allowed")
    if run.status not in {"pending", "running"} or run.current_step != START_TO_ANGLE_STAGE:
        raise OperatorWorkerError("operator_worker_run_state_invalid")

    content_case = await session.get(ContentCase, run.content_case_id)
    if content_case is None or content_case.content_type != "journal":
        raise OperatorWorkerError("operator_worker_case_invalid")
    opportunity = await session.get(ContentOpportunity, content_case.content_opportunity_id)
    variant = await session.get(LocaleVariant, run.locale_variant_id)
    spec = await session.scalar(
        select(JournalIntakeSpec).where(JournalIntakeSpec.content_case_id == content_case.id)
    )
    if opportunity is None or variant is None or spec is None:
        raise OperatorWorkerError("operator_worker_intake_incomplete")
    if variant.locale != spec.source_locale or opportunity.locale != spec.source_locale:
        raise OperatorWorkerError("operator_worker_source_locale_mismatch")

    originality = await session.scalar(
        select(OriginalityPack)
        .where(
            OriginalityPack.content_case_id == content_case.id,
            OriginalityPack.status == "approved",
        )
        .order_by(OriginalityPack.created_at.asc(), OriginalityPack.id.asc())
        .limit(1)
    )
    if (
        originality is None
        or originality.snapshot_hash != originality_pack_snapshot_hash(originality)
    ):
        raise OperatorWorkerError("operator_worker_originality_invalid")

    if run.status == "pending":
        await transition_run(session, run_id=run.id, status="running")

    try:
        brief_binding = await load_run_knowledge_brief_binding(session, run_id=run.id)
    except KnowledgeBriefBindingError as exc:
        raise OperatorWorkerError(exc.code) from exc
    context = await build_journal_context(
        session,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        knowledge_brief_id=(brief_binding.brief_id if brief_binding is not None else None),
    )
    persisted_context = await persist_journal_context(
        session,
        run_id=run.id,
        step_run_id=step.id,
        context=context,
    )

    settings = get_settings()
    research_result = await evidence_workflow.run(
        session,
        request=EvidenceResearchRequest(
            research=ProductionResearchRequest(
                project_id=content_case.project_id,
                query=opportunity.question,
                locale=variant.locale,
                country=spec.research_country,
                limit=10,
                depth=ResearchDepth.STANDARD,
                max_pages_to_read=settings.research_max_pages_read,
            ),
            content_opportunity_id=opportunity.id,
            need_hypothesis_id=content_case.need_hypothesis_id,
            max_claims=8,
        ),
        run_id=run.id,
        step_run_id=step.id,
    )
    if (
        not research_result.evidence_eligible
        or research_result.evidence_set_id is None
        or research_result.evidence_set_version is None
        or research_result.evidence_set_content_hash is None
    ):
        raise OperatorWorkerError("operator_worker_insufficient_evidence")

    evidence_set = await _policy_lock_evidence_set(
        session,
        evidence_set_id=research_result.evidence_set_id,
    )
    handoff = JournalResearchHandoff()
    evidence_handoff = await handoff.handoff_evidence_set(
        session,
        project_id=content_case.project_id,
        content_case_id=content_case.id,
        evidence_set_id=evidence_set.id,
        expected_version=evidence_set.version,
        expected_content_hash=evidence_set.content_hash,
    )
    originality_handoff = await handoff.handoff_originality_pack(
        session,
        content_case_id=content_case.id,
        originality_pack_id=originality.id,
        expected_snapshot_hash=originality.snapshot_hash,
    )

    settings_snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if settings_snapshot is None:
        raise OperatorWorkerError("operator_worker_settings_missing")
    prompt = await active_prompt_definition(session, prompt_key=ANGLE_PROMPT_KEY)
    recipe = await active_recipe_definition(
        session,
        recipe_key=ANGLE_RECIPE_KEY,
        content_type="journal",
        locale=variant.locale,
        task_key=ANGLE_TASK_KEY,
    )
    prompt_version = f"{prompt.prompt_key}:v{prompt.version}"
    recipe_version = f"{recipe.recipe_key}:v{recipe.version}"
    route = SettingsModelRouter().resolve(
        task_key=ANGLE_TASK_KEY,
        settings_snapshot=settings_snapshot,
    )
    if route.primary.provider != "codex_cli":
        raise OperatorWorkerError("operator_worker_unproven_angle_provider")
    runner = runner_registry.get(route.primary.provider)
    capability = await runner.preflight()
    if capability.provider != route.primary.provider or not capability.authenticated:
        raise OperatorWorkerError("operator_worker_runner_preflight_invalid")

    manifest = await build_context_manifest(
        session,
        run_id=run.id,
        step_run_id=step.id,
        inputs=ContextInputs(
            prompt_version=prompt_version,
            recipe_version=recipe_version,
            evidence_set_id=evidence_handoff.evidence_set_id,
            originality_pack_id=originality_handoff.originality_pack_id,
            context_artifact_id=persisted_context.journal_context_artifact.id,
            approved_knowledge_refs=context.approved_knowledge_refs,
            knowledge_chunk_refs=(
                (brief_binding.ref,) if brief_binding is not None else ()
            ),
        ),
    )
    base_bundle = await handoff.persist_journal_input_bundle(
        session,
        run_id=run.id,
        step_run_id=step.id,
        research_decision=ResearchDecision.REUSE_EXISTING,
        opportunity_id=opportunity.id,
        evidence_set=evidence_handoff,
        originality_pack=originality_handoff,
        provider_calls=0,
        model_calls=0,
    )
    bundle_artifact = await bind_bundle_context_manifest(
        session,
        base_bundle_artifact_id=base_bundle.id,
        context_manifest_id=manifest.id,
        research_execution={
            "executed_in_stage": START_TO_ANGLE_STAGE,
            "external_provider_calls": research_result.research.external_provider_calls,
            "pages_read": len(research_result.research.documents),
            "stop_reason": research_result.research.stop_reason,
            "sufficient": research_result.research.sufficient,
            "evidence_count": len(research_result.evidence_ids),
        },
    )
    port = await create_cli_angle_model_port(
        session,
        run_id=run.id,
        settings_snapshot=settings_snapshot,
        context_manifest_id=manifest.id,
        runner_registry=runner_registry,
        locale=variant.locale,
    )
    result = await AngleGenerator(max_attempts=2).generate_candidates(
        session,
        journal_input_bundle_id=bundle_artifact.id,
        expected_bundle_hash=bundle_artifact.content_hash,
        model=port,
        provider=route.primary.provider,
        model_name=route.primary.model,
        step_run_id=step.id,
    )

    await complete_job(session, job_id=job.id, worker_id=worker_id)
    run.current_step = "angle"
    run.failure_code = None
    run.failure_message = None
    await create_checkpoint(
        session,
        run_id=run.id,
        pending_approval={"step_key": "angle", "artifact_id": str(result.artifact.id)},
    )
    await transition_run(session, run_id=run.id, status="waiting_approval")
    state = await get_operator_state_v45(session, content_case_id=content_case.id)
    receipts = list(
        (
            await session.scalars(
                select(OperatorCommand).where(
                    OperatorCommand.job_id == job.id,
                    OperatorCommand.status == "queued",
                )
            )
        ).all()
    )
    for command in receipts:
        command.status = "completed"
        command.error_code = None
        command.state_after = state.state_version
    await session.flush()
    return WorkerExecutionResult(
        job_id=job.id,
        run_id=run.id,
        step_run_id=step.id,
        angle_artifact_id=result.artifact.id,
        angle_artifact_hash=result.artifact.content_hash,
        state_version=state.state_version,
    )


__all__ = [
    "OperatorWorkerError",
    "WorkerExecutionResult",
    "claim_next_operator_job",
    "execute_start_to_angle_job",
    "fail_start_to_angle_job",
    "heartbeat_operator_job",
]
