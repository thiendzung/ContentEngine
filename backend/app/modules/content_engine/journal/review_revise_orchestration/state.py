from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.review_revise import (
    ReviewReviseInput,
    load_review_revise_input,
)
from app.modules.content_engine.journal.review_revise_agent_bridge import (
    review_revise_registry_config,
)
from app.modules.content_engine.models import PromptDefinition, RecipeDefinition, SettingsSnapshot
from app.modules.harness.bounded_orchestration import BoundedOrchestrationResult
from app.modules.harness.delegation_models import DelegationExecution
from app.modules.harness.models import Artifact, ContentRun, ContextManifest, StepRun
from app.modules.harness.persistence import transition_run, transition_step_run
from app.modules.harness.repository_snapshot import RepositorySnapshotSpec
from app.modules.harness.runtime import ContextInputs, build_context_manifest
from app.modules.system.settings_service import (
    SettingsResolutionError,
    active_prompt_definition,
    active_recipe_definition,
)

REVIEW_REVISE_EN_TASK_KEY = "review_revise_en"
REVIEW_REVISE_EN_COORDINATOR_PROMPT_VERSION = "review-revise-en-orchestration:v1"
REVIEW_REVISE_EN_COORDINATOR_RECIPE_VERSION = "review-revise-en-orchestration:v1"
REVIEW_REVISE_EN_MAX_ATTEMPTS = 2
REVIEW_REVISE_EN_MAX_CYCLES = 2
HUMAN_GATE_STEPS = {"angle", "outline", "final_review"}


class ReviewReviseOrchestrationError(ValueError):
    """Fail-closed T05.22E error with one stable safe code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReviewReviseEnRequest:
    writer_run_id: UUID
    source_draft_artifact_id: UUID
    source_draft_version: int
    source_draft_hash: str
    outline_artifact_id: UUID
    outline_artifact_version: int
    outline_artifact_hash: str
    repository: RepositorySnapshotSpec


@dataclass(frozen=True, slots=True)
class ReviewReviseEnResult:
    orchestration: BoundedOrchestrationResult
    revised_draft_artifact_id: UUID | None


@dataclass(frozen=True, slots=True)
class PreparedStage:
    request: ReviewReviseEnRequest
    review_input: ReviewReviseInput
    run: ContentRun
    step: StepRun
    manifest: ContextManifest
    settings_snapshot: SettingsSnapshot
    prompt: PromptDefinition
    recipe: RecipeDefinition
    prompt_version: str
    recipe_version: str


def stable_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def human_gate(run: ContentRun) -> str | None:
    if run.status == "waiting_approval" and run.current_step in HUMAN_GATE_STEPS:
        return run.current_step
    return None


def state_version(prepared: PreparedStage) -> str:
    review_input = prepared.review_input
    run = prepared.run
    step = prepared.step
    return stable_hash(
        {
            "content_case_id": str(run.content_case_id),
            "content_run_id": str(run.id),
            "locale_variant_id": str(run.locale_variant_id),
            "run_status": run.status,
            "current_step": run.current_step,
            "step_run_id": str(step.id),
            "step_status": step.status,
            "settings_snapshot_id": str(prepared.settings_snapshot.id),
            "settings_snapshot_hash": prepared.settings_snapshot.content_hash,
            "context_manifest_id": str(prepared.manifest.id),
            "context_manifest_hash": prepared.manifest.content_hash,
            "source_draft_artifact_id": str(review_input.source_artifact.id),
            "source_draft_version": review_input.source_artifact.version,
            "source_draft_hash": review_input.source_artifact.content_hash,
            "outline_artifact_id": str(review_input.writer_input.outline_artifact.id),
            "outline_artifact_version": review_input.writer_input.outline_artifact.version,
            "outline_artifact_hash": review_input.writer_input.outline_artifact.content_hash,
            "output_artifact_refs": step.output_artifact_refs_json,
        }
    )


def retry_marker(step: StepRun) -> tuple[int, str] | None:
    error_json = step.error_json
    if not isinstance(error_json, dict):
        return None
    raw = error_json.get("orchestration")
    if not isinstance(raw, dict) or raw.get("status") != "retry_pending":
        return None
    attempt = raw.get("last_attempt")
    dedupe_key = raw.get("last_dedupe_key")
    if (
        not isinstance(attempt, int)
        or isinstance(attempt, bool)
        or attempt < 1
        or not isinstance(dedupe_key, str)
        or not dedupe_key
    ):
        raise ReviewReviseOrchestrationError("review_revise_retry_marker_invalid")
    return attempt, dedupe_key


async def delegation_attempts(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
) -> list[DelegationExecution]:
    return list(
        (
            await session.scalars(
                select(DelegationExecution)
                .where(
                    DelegationExecution.run_id == run_id,
                    DelegationExecution.step_run_id == step_run_id,
                    DelegationExecution.task_key == REVIEW_REVISE_EN_TASK_KEY,
                )
                .order_by(DelegationExecution.attempt)
            )
        ).all()
    )


async def expected_attempt(session: AsyncSession, *, prepared: PreparedStage) -> int:
    marker = retry_marker(prepared.step)
    if marker is not None:
        return marker[0] + 1
    attempts = await delegation_attempts(
        session,
        run_id=prepared.run.id,
        step_run_id=prepared.step.id,
    )
    if not attempts:
        return 1
    latest = attempts[-1]
    if latest.status == "completed":
        return latest.attempt
    if latest.status in {"failed", "cancelled"}:
        return latest.attempt + 1
    if latest.status in {"queued", "running"}:
        return latest.attempt
    raise ReviewReviseOrchestrationError("review_revise_delegation_status_invalid")


async def find_manifest(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID,
    prompt_version: str,
    recipe_version: str,
) -> ContextManifest | None:
    rows = list(
        (
            await session.scalars(
                select(ContextManifest).where(
                    ContextManifest.run_id == run_id,
                    ContextManifest.step_run_id == step_run_id,
                    ContextManifest.prompt_version == prompt_version,
                    ContextManifest.recipe_version == recipe_version,
                )
            )
        ).all()
    )
    if len(rows) > 1:
        raise ReviewReviseOrchestrationError("review_revise_context_manifest_duplicate")
    return rows[0] if rows else None


async def load_exact_stage(
    session: AsyncSession,
    *,
    prepared: PreparedStage,
) -> PreparedStage:
    review_input = await load_review_revise_input(
        session,
        writer_run_id=prepared.request.writer_run_id,
        source_draft_artifact_id=prepared.request.source_draft_artifact_id,
        expected_source_draft_version=prepared.request.source_draft_version,
        expected_source_draft_hash=prepared.request.source_draft_hash,
        outline_artifact_id=prepared.request.outline_artifact_id,
        expected_outline_version=prepared.request.outline_artifact_version,
        expected_outline_hash=prepared.request.outline_artifact_hash,
        locale="en",
    )
    run = await session.get(ContentRun, prepared.run.id)
    step = await session.get(StepRun, prepared.step.id)
    manifest = await session.get(ContextManifest, prepared.manifest.id)
    snapshot = await session.get(SettingsSnapshot, prepared.settings_snapshot.id)
    if run is None or run.id != review_input.writer_input.writer_run.id:
        raise ReviewReviseOrchestrationError("review_revise_run_stale")
    if step is None or step.run_id != run.id or step.step_key != REVIEW_REVISE_EN_TASK_KEY:
        raise ReviewReviseOrchestrationError("review_revise_step_stale")
    if manifest is None or manifest.run_id != run.id or manifest.step_run_id != step.id:
        raise ReviewReviseOrchestrationError("review_revise_manifest_stale")
    if snapshot is None or snapshot.id != run.settings_snapshot_id:
        raise ReviewReviseOrchestrationError("review_revise_settings_snapshot_stale")
    if manifest.settings_snapshot_id != snapshot.id:
        raise ReviewReviseOrchestrationError("review_revise_manifest_settings_mismatch")
    if manifest.prompt_version != prepared.prompt_version:
        raise ReviewReviseOrchestrationError("review_revise_prompt_snapshot_mismatch")
    if manifest.recipe_version != prepared.recipe_version:
        raise ReviewReviseOrchestrationError("review_revise_recipe_snapshot_mismatch")
    return PreparedStage(
        request=prepared.request,
        review_input=review_input,
        run=run,
        step=step,
        manifest=manifest,
        settings_snapshot=snapshot,
        prompt=prepared.prompt,
        recipe=prepared.recipe,
        prompt_version=prepared.prompt_version,
        recipe_version=prepared.recipe_version,
    )


async def prepare_review_revise_en_orchestration(
    session: AsyncSession,
    *,
    request: ReviewReviseEnRequest,
) -> PreparedStage:
    """Load exact lineage and create/reuse only the stage-owned StepRun/manifest."""

    review_input = await load_review_revise_input(
        session,
        writer_run_id=request.writer_run_id,
        source_draft_artifact_id=request.source_draft_artifact_id,
        expected_source_draft_version=request.source_draft_version,
        expected_source_draft_hash=request.source_draft_hash,
        outline_artifact_id=request.outline_artifact_id,
        expected_outline_version=request.outline_artifact_version,
        expected_outline_hash=request.outline_artifact_hash,
        locale="en",
    )
    run = review_input.writer_input.writer_run
    if review_input.writer_input.locale != "en":
        raise ReviewReviseOrchestrationError("review_revise_en_locale_required")
    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None:
        raise ReviewReviseOrchestrationError("review_revise_settings_snapshot_missing")

    config = review_revise_registry_config("en")
    try:
        prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=config.recipe_key,
            content_type="journal",
            locale="en",
            task_key=config.task_key,
        )
    except SettingsResolutionError as exc:
        raise ReviewReviseOrchestrationError("review_revise_registry_missing") from exc
    prompt_version = f"{prompt.prompt_key}:v{prompt.version}"
    recipe_version = f"{recipe.recipe_key}:v{recipe.version}"

    steps = list(
        (
            await session.scalars(
                select(StepRun)
                .where(
                    StepRun.run_id == run.id,
                    StepRun.step_key == REVIEW_REVISE_EN_TASK_KEY,
                )
                .order_by(StepRun.attempt)
            )
        ).all()
    )
    if len(steps) > 1:
        raise ReviewReviseOrchestrationError("review_revise_step_attempt_conflict")
    if steps:
        step = steps[0]
        if step.status in {"failed", "skipped"}:
            raise ReviewReviseOrchestrationError("review_revise_step_terminal_not_reusable")
    else:
        step = StepRun(
            run_id=run.id,
            step_key=REVIEW_REVISE_EN_TASK_KEY,
            attempt=1,
            status="pending",
            input_artifact_refs_json=[
                str(review_input.source_artifact.id),
                str(review_input.writer_input.handoff_artifact.id),
                str(review_input.writer_input.outline_artifact.id),
            ],
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()

    manifest = await find_manifest(
        session,
        run_id=run.id,
        step_run_id=step.id,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )
    if manifest is None:
        if step.status == "completed":
            raise ReviewReviseOrchestrationError("review_revise_context_manifest_missing")
        upstream = review_input.writer_input.outline_input.bundle.context_manifest
        manifest = await build_context_manifest(
            session,
            run_id=run.id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                evidence_set_id=review_input.writer_input.outline_input.bundle.evidence_set_id,
                originality_pack_id=(
                    review_input.writer_input.outline_input.bundle.originality_pack_id
                ),
                approved_knowledge_refs=(
                    tuple(upstream.approved_knowledge_refs_json) if upstream is not None else ()
                ),
                knowledge_chunk_refs=(
                    tuple(upstream.knowledge_chunk_refs_json) if upstream is not None else ()
                ),
                golden_example_refs=(
                    tuple(upstream.golden_example_refs_json) if upstream is not None else ()
                ),
                tool_result_refs=(
                    tuple(upstream.tool_result_refs_json) if upstream is not None else ()
                ),
            ),
        )

    gate = human_gate(run)
    if gate is None and step.status == "pending":
        if run.status not in {"pending", "waiting_approval"}:
            raise ReviewReviseOrchestrationError("review_revise_run_state_invalid")
        await transition_run(session, run_id=run.id, status="running")
        run.current_step = REVIEW_REVISE_EN_TASK_KEY
        await transition_step_run(session, step_run_id=step.id, status="running")
    elif gate is None and step.status == "running":
        if run.status != "running" or run.current_step != REVIEW_REVISE_EN_TASK_KEY:
            raise ReviewReviseOrchestrationError("review_revise_running_state_mismatch")
    elif gate is None and step.status == "completed" and not step.output_artifact_refs_json:
        raise ReviewReviseOrchestrationError("review_revise_completed_output_missing")

    await session.flush()
    return PreparedStage(
        request=request,
        review_input=review_input,
        run=run,
        step=step,
        manifest=manifest,
        settings_snapshot=snapshot,
        prompt=prompt,
        recipe=recipe,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )


async def completed_output_artifact_id(
    session: AsyncSession,
    *,
    prepared: PreparedStage,
) -> UUID | None:
    stage = await load_exact_stage(session, prepared=prepared)
    if stage.step.status != "completed" or len(stage.step.output_artifact_refs_json) != 1:
        return None
    try:
        artifact_id = UUID(stage.step.output_artifact_refs_json[0])
    except ValueError as exc:
        raise ReviewReviseOrchestrationError("review_revise_completed_output_invalid") from exc
    artifact = await session.get(Artifact, artifact_id)
    if (
        artifact is None
        or artifact.run_id != stage.run.id
        or artifact.artifact_type != "journal_draft"
        or artifact.locale != "en"
    ):
        raise ReviewReviseOrchestrationError("review_revise_completed_output_invalid")
    return artifact.id
