"""Generate one real Journal Angle candidate set from one exact frozen input bundle."""

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
from app.modules.content_engine.journal.agent_bridge import (
    ANGLE_PROMPT_KEY,
    ANGLE_RECIPE_KEY,
    ANGLE_TASK_KEY,
    create_cli_angle_model_port,
)
from app.modules.content_engine.journal.angle import (
    AngleGenerationError,
    AngleGenerator,
    load_journal_input_bundle,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import (
    AgentRunner,
    AgentRunnerRegistry,
    AntigravityCliRunner,
    CodexCliRunner,
)
from app.modules.harness.models import Artifact, ContentRun, StepRun
from app.modules.harness.persistence import transition_run, transition_step_run
from app.modules.harness.runtime import ContextInputs, SettingsModelRouter, build_context_manifest
from app.modules.system.settings_service import active_prompt_definition, active_recipe_definition

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


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
        description="Generate one Journal Angle set from an exact frozen runtime snapshot."
    )
    parser.add_argument("--run-id", required=True, type=_uuid_arg)
    parser.add_argument("--journal-input-bundle-id", required=True, type=_uuid_arg)
    parser.add_argument("--journal-input-bundle-hash", required=True, type=_hash_arg)
    parser.add_argument("--settings-snapshot-id", required=True, type=_uuid_arg)
    parser.add_argument("--settings-snapshot-hash", required=True, type=_hash_arg)
    parser.add_argument("--expected-provider", required=True, type=_non_empty)
    parser.add_argument("--expected-model", required=True, type=_non_empty)
    return parser


def _runner(provider: str) -> AgentRunner:
    if provider == "codex_cli":
        return CodexCliRunner()
    if provider == "antigravity_cli":
        return AntigravityCliRunner()
    raise AngleGenerationError("angle_agent_provider_unsupported", provider)


async def _existing_step(session: AsyncSession, *, run_id: UUID) -> StepRun | None:
    rows = list(
        (
            await session.scalars(
                select(StepRun)
                .where(StepRun.run_id == run_id, StepRun.step_key == ANGLE_TASK_KEY)
                .order_by(StepRun.attempt)
            )
        ).all()
    )
    if len(rows) > 1:
        raise AngleGenerationError("angle_step_attempt_conflict")
    return rows[0] if rows else None


async def _existing_angle_artifacts(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> list[Artifact]:
    return list(
        (
            await session.scalars(
                select(Artifact)
                .where(
                    Artifact.run_id == run_id,
                    Artifact.artifact_type == "angle_candidates",
                )
                .order_by(Artifact.version)
            )
        ).all()
    )


async def _run(args: argparse.Namespace) -> None:
    run_id = cast(UUID, args.run_id)
    bundle_id = cast(UUID, args.journal_input_bundle_id)
    bundle_hash = cast(str, args.journal_input_bundle_hash)
    expected_snapshot_id = cast(UUID, args.settings_snapshot_id)
    expected_snapshot_hash = cast(str, args.settings_snapshot_hash)
    expected_provider = cast(str, args.expected_provider)
    expected_model = cast(str, args.expected_model)

    async with SessionLocal() as session:
        bundle = await load_journal_input_bundle(
            session,
            journal_input_bundle_id=bundle_id,
            expected_content_hash=bundle_hash,
        )
        if bundle.artifact.run_id != run_id:
            raise AngleGenerationError("angle_run_mismatch")

        run = await session.get(ContentRun, run_id)
        if run is None:
            raise AngleGenerationError("angle_run_not_found")
        if run.status != "waiting_approval":
            raise AngleGenerationError("angle_run_state_invalid", run.status)
        if run.settings_snapshot_id != expected_snapshot_id:
            raise AngleGenerationError("angle_settings_snapshot_mismatch")

        settings_snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
        if settings_snapshot is None:
            raise AngleGenerationError("angle_settings_snapshot_missing")
        if settings_snapshot.content_hash != expected_snapshot_hash:
            raise AngleGenerationError("angle_settings_snapshot_hash_mismatch")

        route = SettingsModelRouter().resolve(
            task_key=ANGLE_TASK_KEY,
            settings_snapshot=settings_snapshot,
        )
        if route.primary.provider != expected_provider or route.primary.model != expected_model:
            raise AngleGenerationError(
                "angle_model_route_mismatch",
                f"resolved={route.primary.provider}/{route.primary.model}",
            )

        existing_artifacts = await _existing_angle_artifacts(session, run_id=run.id)
        if existing_artifacts:
            raise AngleGenerationError("angle_existing_artifact_requires_review")
        if await _existing_step(session, run_id=run.id) is not None:
            raise AngleGenerationError("angle_existing_step_requires_review")

        prompt = await active_prompt_definition(session, prompt_key=ANGLE_PROMPT_KEY)
        recipe = await active_recipe_definition(
            session,
            recipe_key=ANGLE_RECIPE_KEY,
            content_type="journal",
            locale=bundle.locale,
            task_key=ANGLE_TASK_KEY,
        )
        prompt_version = f"{prompt.prompt_key}:v{prompt.version}"
        recipe_version = f"{recipe.recipe_key}:v{recipe.version}"

        selected_runner = _runner(route.primary.provider)
        capability = await selected_runner.preflight()
        if capability.provider != route.primary.provider:
            raise AngleGenerationError("angle_agent_provider_mismatch")
        registry = AgentRunnerRegistry()
        registry.register(route.primary.provider, selected_runner)

        step = StepRun(
            run_id=run.id,
            step_key=ANGLE_TASK_KEY,
            attempt=1,
            status="pending",
            input_artifact_refs_json=[str(bundle.artifact.id)],
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
        manifest = await build_context_manifest(
            session,
            run_id=run.id,
            step_run_id=step.id,
            inputs=ContextInputs(
                prompt_version=prompt_version,
                recipe_version=recipe_version,
                evidence_set_id=bundle.evidence_set_id,
                originality_pack_id=bundle.originality_pack_id,
            ),
        )
        port = await create_cli_angle_model_port(
            session,
            run_id=run.id,
            settings_snapshot=settings_snapshot,
            context_manifest_id=manifest.id,
            runner_registry=registry,
            locale=bundle.locale,
        )
        if port.prompt_version != prompt_version or port.recipe_version != recipe_version:
            raise AngleGenerationError("angle_registry_snapshot_mismatch")

        await transition_run(session, run_id=run.id, status="running")
        run.current_step = ANGLE_TASK_KEY
        await transition_step_run(session, step_run_id=step.id, status="running")

        try:
            result = await AngleGenerator(max_attempts=2).generate_candidates(
                session,
                journal_input_bundle_id=bundle.artifact.id,
                expected_bundle_hash=bundle.artifact.content_hash,
                model=port,
                provider=expected_provider,
                model_name=expected_model,
                step_run_id=step.id,
            )
        except Exception as exc:
            if step.status == "running":
                await transition_step_run(session, step_run_id=step.id, status="failed")
            if run.status == "running":
                run.failure_code = "angle_generation_failed"
                run.failure_message = str(exc)[:2000]
                await transition_run(session, run_id=run.id, status="failed")
            await session.commit()
            raise

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
                    "provider": expected_provider,
                    "model": expected_model,
                    "runner_version": capability.version,
                    "prompt_version": prompt_version,
                    "recipe_version": recipe_version,
                    "context_manifest_id": str(manifest.id),
                    "context_manifest_hash": manifest.content_hash,
                    "journal_input_bundle_id": str(bundle.artifact.id),
                    "journal_input_bundle_hash": bundle.artifact.content_hash,
                    "evidence_set_id": str(bundle.evidence_set_id),
                    "evidence_set_version": bundle.evidence_set_version,
                    "evidence_set_hash": bundle.evidence_set_hash,
                    "originality_pack_id": str(bundle.originality_pack_id),
                    "originality_pack_hash": bundle.originality_pack_hash,
                    "angle_artifact_id": str(result.artifact.id),
                    "angle_artifact_version": result.artifact.version,
                    "angle_artifact_hash": result.artifact.content_hash,
                    "model_attempts": result.model_attempts,
                    "candidates": [candidate.to_dict() for candidate in result.candidates],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
