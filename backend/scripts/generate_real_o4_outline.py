"""Generate or reuse the real O4 Journal Outline for one exact approved Angle."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from app.modules.content_engine.journal.outline import (
    OutlineGenerationError,
    OutlineGenerator,
    load_outline_input,
)
from app.modules.content_engine.journal.outline_agent_bridge import (
    OUTLINE_PROMPT_KEY,
    OUTLINE_RECIPE_KEY,
    OUTLINE_ROUTE_TASK_KEY,
    OUTLINE_TASK_KEY,
    create_cli_outline_model_port,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import (
    AgentRunner,
    AgentRunnerRegistry,
    AntigravityCliRunner,
    CodexCliRunner,
)
from app.modules.harness.models import ContentRun, ContextManifest, StepRun
from app.modules.harness.persistence import transition_run, transition_step_run
from app.modules.harness.runtime import ContextInputs, SettingsModelRouter, build_context_manifest
from app.modules.system.settings_service import active_prompt_definition, active_recipe_definition

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _hash_arg(value: str) -> str:
    normalized = value.strip().lower()
    if _HASH_PATTERN.fullmatch(normalized) is None:
        raise argparse.ArgumentTypeError("must be a lowercase SHA-256 hash")
    return normalized


def _non_empty(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return value.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate/reuse the real O4 Journal Outline from one exact approved Angle."
    )
    parser.add_argument("--run-id", required=True, type=_uuid_arg)
    parser.add_argument("--angle-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--angle-artifact-version", required=True, type=_positive_int)
    parser.add_argument("--angle-artifact-hash", required=True, type=_hash_arg)
    parser.add_argument("--selected-angle-id", required=True, type=_non_empty)
    parser.add_argument("--candidate-hash", required=True, type=_hash_arg)
    parser.add_argument("--approval-id", required=True, type=_uuid_arg)
    parser.add_argument("--expected-provider", required=True, type=_non_empty)
    parser.add_argument("--expected-model", required=True, type=_non_empty)
    return parser


def _runner(provider: str) -> AgentRunner:
    if provider == "codex_cli":
        return CodexCliRunner()
    if provider == "antigravity_cli":
        return AntigravityCliRunner()
    raise OutlineGenerationError("outline_agent_provider_unsupported", provider)


async def _outline_step(session: AsyncSession, *, run_id: UUID) -> StepRun | None:
    rows = list(
        (
            await session.scalars(
                select(StepRun)
                .where(StepRun.run_id == run_id, StepRun.step_key == OUTLINE_TASK_KEY)
                .order_by(StepRun.attempt)
            )
        ).all()
    )
    if not rows:
        return None
    if len(rows) != 1:
        raise OutlineGenerationError("outline_step_attempt_conflict")
    return rows[0]


async def _existing_manifest(
    session: AsyncSession,
    *,
    step: StepRun,
    prompt_version: str,
    recipe_version: str,
) -> ContextManifest | None:
    rows = list(
        (
            await session.scalars(
                select(ContextManifest).where(
                    ContextManifest.run_id == step.run_id,
                    ContextManifest.step_run_id == step.id,
                    ContextManifest.prompt_version == prompt_version,
                    ContextManifest.recipe_version == recipe_version,
                )
            )
        ).all()
    )
    if not rows:
        return None
    if len(rows) != 1:
        raise OutlineGenerationError("outline_context_manifest_duplicate")
    return rows[0]


async def _run(args: argparse.Namespace) -> None:
    run_id = cast(UUID, args.run_id)
    angle_artifact_id = cast(UUID, args.angle_artifact_id)
    approval_id = cast(UUID, args.approval_id)
    expected_provider = cast(str, args.expected_provider)
    expected_model = cast(str, args.expected_model)

    async with SessionLocal() as session:
        outline_input = await load_outline_input(
            session,
            angle_artifact_id=angle_artifact_id,
            expected_angle_artifact_version=cast(int, args.angle_artifact_version),
            expected_angle_artifact_hash=cast(str, args.angle_artifact_hash),
            selected_angle_id=cast(str, args.selected_angle_id),
            expected_candidate_hash=cast(str, args.candidate_hash),
            expected_approval_id=approval_id,
        )
        if outline_input.approved_angle.artifact.run_id != run_id:
            raise OutlineGenerationError("outline_run_mismatch")
        run = await session.get(ContentRun, run_id)
        if run is None:
            raise OutlineGenerationError("outline_run_not_found")
        if run.status not in {"waiting_approval", "running"}:
            raise OutlineGenerationError("outline_run_state_invalid", run.status)
        settings_snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
        if settings_snapshot is None:
            raise OutlineGenerationError("outline_settings_snapshot_missing")

        route = SettingsModelRouter().resolve(
            task_key=OUTLINE_ROUTE_TASK_KEY,
            settings_snapshot=settings_snapshot,
        )
        if route.primary.provider != expected_provider or route.primary.model != expected_model:
            raise OutlineGenerationError(
                "outline_model_route_mismatch",
                f"resolved={route.primary.provider}/{route.primary.model}",
            )

        prompt = await active_prompt_definition(session, prompt_key=OUTLINE_PROMPT_KEY)
        recipe = await active_recipe_definition(
            session,
            recipe_key=OUTLINE_RECIPE_KEY,
            content_type="journal",
            locale=outline_input.approved_angle.candidate.locale,
            task_key=OUTLINE_TASK_KEY,
        )
        prompt_version = f"{prompt.prompt_key}:v{prompt.version}"
        recipe_version = f"{recipe.recipe_key}:v{recipe.version}"

        selected_runner = _runner(route.primary.provider)
        capability = await selected_runner.preflight()
        if capability.provider != route.primary.provider:
            raise OutlineGenerationError("outline_agent_provider_mismatch")
        registry = AgentRunnerRegistry()
        registry.register(route.primary.provider, selected_runner)

        step = await _outline_step(session, run_id=run.id)
        is_new_step = step is None
        if step is None:
            step = StepRun(
                run_id=run.id,
                step_key=OUTLINE_TASK_KEY,
                attempt=1,
                status="pending",
                input_artifact_refs_json=[
                    str(outline_input.bundle.artifact.id),
                    str(outline_input.approved_angle.artifact.id),
                    f"angle_approval:{outline_input.approved_angle.approval.id}",
                ],
                output_artifact_refs_json=[],
            )
            session.add(step)
            await session.flush()
        elif step.status != "completed":
            raise OutlineGenerationError("outline_existing_step_not_reusable", step.status)

        manifest = await _existing_manifest(
            session,
            step=step,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
        )
        if manifest is None:
            if not is_new_step:
                raise OutlineGenerationError("outline_context_manifest_missing")
            upstream = outline_input.bundle.context_manifest
            manifest = await build_context_manifest(
                session,
                run_id=run.id,
                step_run_id=step.id,
                inputs=ContextInputs(
                    prompt_version=prompt_version,
                    recipe_version=recipe_version,
                    evidence_set_id=outline_input.bundle.evidence_set_id,
                    originality_pack_id=outline_input.bundle.originality_pack_id,
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

        port = await create_cli_outline_model_port(
            session,
            run_id=run.id,
            settings_snapshot=settings_snapshot,
            context_manifest_id=manifest.id,
            runner_registry=registry,
            locale=outline_input.approved_angle.candidate.locale,
        )
        if port.prompt_version != prompt_version or port.recipe_version != recipe_version:
            raise OutlineGenerationError("outline_registry_snapshot_mismatch")

        if is_new_step:
            if run.status != "waiting_approval":
                raise OutlineGenerationError("outline_new_step_requires_waiting_approval")
            await transition_run(session, run_id=run.id, status="running")
            run.current_step = OUTLINE_TASK_KEY
            await transition_step_run(session, step_run_id=step.id, status="running")

        try:
            result = await OutlineGenerator(max_attempts=2).generate_outline(
                session,
                angle_artifact_id=angle_artifact_id,
                expected_angle_artifact_version=cast(int, args.angle_artifact_version),
                expected_angle_artifact_hash=cast(str, args.angle_artifact_hash),
                selected_angle_id=cast(str, args.selected_angle_id),
                expected_candidate_hash=cast(str, args.candidate_hash),
                expected_approval_id=approval_id,
                model=port,
                provider=expected_provider,
                model_name=expected_model,
                context_manifest_id=manifest.id,
                prompt_version=prompt_version,
                recipe_version=recipe_version,
            )
        except Exception as exc:
            if is_new_step and step.status == "running":
                await transition_step_run(session, step_run_id=step.id, status="failed")
            if is_new_step and run.status == "running":
                run.failure_code = "outline_generation_failed"
                run.failure_message = str(exc)[:2000]
                await transition_run(session, run_id=run.id, status="failed")
            await session.commit()
            raise

        if is_new_step:
            await transition_step_run(session, step_run_id=step.id, status="completed")
            await transition_run(session, run_id=run.id, status="waiting_approval")
        await session.commit()

        print(
            json.dumps(
                {
                    "run_id": str(run.id),
                    "run_status": run.status,
                    "step_run_id": str(step.id),
                    "step_status": step.status,
                    "settings_snapshot_id": str(settings_snapshot.id),
                    "settings_snapshot_hash": settings_snapshot.content_hash,
                    "route_reused_from_task": OUTLINE_ROUTE_TASK_KEY,
                    "provider": expected_provider,
                    "model": expected_model,
                    "runner_version": capability.version,
                    "prompt_version": prompt_version,
                    "recipe_version": recipe_version,
                    "context_manifest_id": str(manifest.id),
                    "context_manifest_hash": manifest.content_hash,
                    "angle_artifact_id": str(outline_input.approved_angle.artifact.id),
                    "angle_approval_id": str(outline_input.approved_angle.approval.id),
                    "selected_angle_id": outline_input.approved_angle.candidate.angle_id,
                    "selected_candidate_hash": (
                        outline_input.approved_angle.approval.selected_candidate_hash
                    ),
                    "journal_input_bundle_id": str(outline_input.bundle.artifact.id),
                    "journal_input_bundle_hash": outline_input.bundle.artifact.content_hash,
                    "outline_artifact_id": str(result.artifact.id),
                    "outline_artifact_version": result.artifact.version,
                    "outline_artifact_hash": result.artifact.content_hash,
                    "model_attempts": result.model_attempts,
                    "reused": result.reused,
                    "outline": result.outline.to_dict(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
