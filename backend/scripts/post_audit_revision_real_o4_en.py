"""Apply one bounded English post-Assertion-Audit revision to an exact draft."""

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
from app.modules.content_engine.journal.post_audit_revision import (
    POST_AUDIT_REVISION_TASK_KEY,
    PostAuditRevisionGenerator,
    PostAuditRevisionInput,
    load_post_audit_revision_input,
)
from app.modules.content_engine.journal.post_audit_revision_agent_bridge import (
    POST_AUDIT_REVISION_ROUTE_TASK_KEY,
    create_cli_post_audit_revision_model_port,
    post_audit_revision_registry_config,
)
from app.modules.content_engine.journal.writer import WriterGenerationError
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.agent_runner import (
    AgentRunner,
    AgentRunnerRegistry,
    AntigravityCliRunner,
    CodexCliRunner,
)
from app.modules.harness.models import ContextManifest, StepRun
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
        description="Apply the bounded English CE05 post-audit revision to one exact draft."
    )
    parser.add_argument("--writer-run-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-draft-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-draft-version", required=True, type=_positive_int)
    parser.add_argument("--source-draft-hash", required=True, type=_hash_arg)
    parser.add_argument("--failed-audit-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--failed-audit-version", required=True, type=_positive_int)
    parser.add_argument("--failed-audit-hash", required=True, type=_hash_arg)
    parser.add_argument("--failed-quality-evaluation-id", required=True, type=_uuid_arg)
    parser.add_argument("--outline-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--outline-artifact-version", required=True, type=_positive_int)
    parser.add_argument("--outline-artifact-hash", required=True, type=_hash_arg)
    parser.add_argument("--expected-provider", required=True, type=_non_empty)
    parser.add_argument("--expected-model", required=True, type=_non_empty)
    return parser


def _runner(provider: str) -> AgentRunner:
    if provider == "codex_cli":
        return CodexCliRunner()
    if provider == "antigravity_cli":
        return AntigravityCliRunner()
    raise WriterGenerationError("post_audit_revision_agent_provider_unsupported", provider)


async def _step(session: AsyncSession, *, run_id: UUID) -> StepRun | None:
    rows = list(
        (
            await session.scalars(
                select(StepRun)
                .where(
                    StepRun.run_id == run_id,
                    StepRun.step_key == POST_AUDIT_REVISION_TASK_KEY,
                )
                .order_by(StepRun.attempt)
            )
        ).all()
    )
    if len(rows) > 1:
        raise WriterGenerationError("post_audit_revision_step_attempt_conflict")
    return rows[0] if rows else None


async def _manifest(
    session: AsyncSession,
    *,
    step: StepRun,
    prompt_version: str,
    recipe_version: str,
    revision_input: PostAuditRevisionInput,
) -> ContextManifest | None:
    if (
        step.step_key != POST_AUDIT_REVISION_TASK_KEY
        or step.run_id != revision_input.writer_input.writer_run.id
    ):
        raise WriterGenerationError("post_audit_revision_step_ownership_mismatch")
    rows = list(
        (
            await session.scalars(
                select(ContextManifest).where(
                    ContextManifest.run_id == step.run_id,
                    ContextManifest.step_run_id == step.id,
                )
            )
        ).all()
    )
    if len(rows) > 1:
        raise WriterGenerationError("post_audit_revision_context_manifest_duplicate")
    if not rows:
        return None
    manifest = rows[0]
    if (
        manifest.prompt_version != prompt_version
        or manifest.recipe_version != recipe_version
        or manifest.settings_snapshot_id
        != revision_input.writer_input.writer_run.settings_snapshot_id
        or manifest.evidence_set_id
        != revision_input.writer_input.outline_input.bundle.evidence_set_id
        or manifest.originality_pack_id
        != revision_input.writer_input.outline_input.bundle.originality_pack_id
        or manifest.step_run_id != step.id
        or manifest.tool_result_refs_json
    ):
        raise WriterGenerationError("post_audit_revision_context_manifest_snapshot_mismatch")
    return manifest


async def _run(args: argparse.Namespace) -> None:
    writer_run_id = cast(UUID, args.writer_run_id)
    source_draft_id = cast(UUID, args.source_draft_artifact_id)
    source_draft_version = cast(int, args.source_draft_version)
    source_draft_hash = cast(str, args.source_draft_hash)
    failed_audit_id = cast(UUID, args.failed_audit_artifact_id)
    failed_audit_version = cast(int, args.failed_audit_version)
    failed_audit_hash = cast(str, args.failed_audit_hash)
    quality_evaluation_id = cast(UUID, args.failed_quality_evaluation_id)
    outline_id = cast(UUID, args.outline_artifact_id)
    outline_version = cast(int, args.outline_artifact_version)
    outline_hash = cast(str, args.outline_artifact_hash)
    expected_provider = cast(str, args.expected_provider)
    expected_model = cast(str, args.expected_model)

    async with SessionLocal() as session:
        revision_input = await load_post_audit_revision_input(
            session,
            writer_run_id=writer_run_id,
            source_draft_artifact_id=source_draft_id,
            expected_source_draft_version=source_draft_version,
            expected_source_draft_hash=source_draft_hash,
            failed_audit_artifact_id=failed_audit_id,
            expected_failed_audit_version=failed_audit_version,
            expected_failed_audit_hash=failed_audit_hash,
            failed_quality_evaluation_id=quality_evaluation_id,
            outline_artifact_id=outline_id,
            expected_outline_version=outline_version,
            expected_outline_hash=outline_hash,
        )
        run = revision_input.writer_input.writer_run
        settings_snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
        if settings_snapshot is None:
            raise WriterGenerationError("post_audit_revision_settings_snapshot_missing")
        route = SettingsModelRouter().resolve(
            task_key=POST_AUDIT_REVISION_ROUTE_TASK_KEY,
            settings_snapshot=settings_snapshot,
        )
        if route.primary.provider != expected_provider or route.primary.model != expected_model:
            raise WriterGenerationError(
                "post_audit_revision_model_route_mismatch",
                f"resolved={route.primary.provider}/{route.primary.model}",
            )
        config = post_audit_revision_registry_config("en")
        prompt = await active_prompt_definition(session, prompt_key=config.prompt_key)
        recipe = await active_recipe_definition(
            session,
            recipe_key=config.recipe_key,
            content_type="journal",
            locale="en",
            task_key=config.task_key,
        )
        prompt_version = f"{prompt.prompt_key}:v{prompt.version}"
        recipe_version = f"{recipe.recipe_key}:v{recipe.version}"
        selected_runner = _runner(route.primary.provider)
        capability = await selected_runner.preflight()
        if capability.provider != route.primary.provider:
            raise WriterGenerationError("post_audit_revision_agent_provider_mismatch")
        registry = AgentRunnerRegistry()
        registry.register(route.primary.provider, selected_runner)

        step = await _step(session, run_id=run.id)
        is_new_step = step is None
        if step is None:
            step = StepRun(
                run_id=run.id,
                step_key=POST_AUDIT_REVISION_TASK_KEY,
                attempt=1,
                status="pending",
                input_artifact_refs_json=[
                    str(revision_input.source_artifact.id),
                    str(revision_input.audit_artifact.id),
                    str(revision_input.writer_input.handoff_artifact.id),
                    str(revision_input.writer_input.outline_artifact.id),
                ],
                output_artifact_refs_json=[],
            )
            session.add(step)
            await session.flush()
        elif step.status != "completed":
            raise WriterGenerationError(
                "post_audit_revision_existing_step_not_reusable",
                step.status,
            )
        expected_refs = {
            str(revision_input.source_artifact.id),
            str(revision_input.audit_artifact.id),
            str(revision_input.writer_input.handoff_artifact.id),
            str(revision_input.writer_input.outline_artifact.id),
        }
        if (
            step.step_key != POST_AUDIT_REVISION_TASK_KEY
            or step.attempt != 1
            or not expected_refs.issubset(set(step.input_artifact_refs_json))
        ):
            raise WriterGenerationError("post_audit_revision_step_input_mismatch")

        manifest = await _manifest(
            session,
            step=step,
            prompt_version=prompt_version,
            recipe_version=recipe_version,
            revision_input=revision_input,
        )
        if manifest is None:
            if not is_new_step:
                raise WriterGenerationError("post_audit_revision_context_manifest_missing")
            upstream = revision_input.writer_input.outline_input.bundle.context_manifest
            manifest = await build_context_manifest(
                session,
                run_id=run.id,
                step_run_id=step.id,
                inputs=ContextInputs(
                    prompt_version=prompt_version,
                    recipe_version=recipe_version,
                    evidence_set_id=revision_input.writer_input.outline_input.bundle.evidence_set_id,
                    originality_pack_id=revision_input.writer_input.outline_input.bundle.originality_pack_id,
                    approved_knowledge_refs=(
                        tuple(upstream.approved_knowledge_refs_json) if upstream is not None else ()
                    ),
                    knowledge_chunk_refs=(
                        tuple(upstream.knowledge_chunk_refs_json) if upstream is not None else ()
                    ),
                    golden_example_refs=(
                        tuple(upstream.golden_example_refs_json) if upstream is not None else ()
                    ),
                    tool_result_refs=(),
                ),
            )

        port = await create_cli_post_audit_revision_model_port(
            session,
            run_id=run.id,
            settings_snapshot=settings_snapshot,
            context_manifest_id=manifest.id,
            runner_registry=registry,
            locale="en",
        )
        if port.prompt_version != prompt_version or port.recipe_version != recipe_version:
            raise WriterGenerationError("post_audit_revision_registry_snapshot_mismatch")
        if port.task_key != POST_AUDIT_REVISION_TASK_KEY:
            raise WriterGenerationError("post_audit_revision_task_key_mismatch")

        if is_new_step:
            await transition_run(session, run_id=run.id, status="running")
            run.current_step = POST_AUDIT_REVISION_TASK_KEY
            await transition_step_run(session, step_run_id=step.id, status="running")

        try:
            result = await PostAuditRevisionGenerator(max_attempts=2).revise_draft(
                session,
                revision_input=revision_input,
                model=port,
                provider=expected_provider,
                model_name=expected_model,
                context_manifest=manifest,
                prompt_version=prompt_version,
                recipe_version=recipe_version,
            )
        except Exception as exc:
            if is_new_step and step.status == "running":
                await transition_step_run(session, step_run_id=step.id, status="failed")
            if is_new_step and run.status == "running":
                run.failure_code = f"{POST_AUDIT_REVISION_TASK_KEY}_failed"
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
                    "writer_run_id": str(run.id),
                    "writer_run_status": run.status,
                    "locale": "en",
                    "task_key": POST_AUDIT_REVISION_TASK_KEY,
                    "step_run_id": str(step.id),
                    "step_status": step.status,
                    "settings_snapshot_id": str(settings_snapshot.id),
                    "settings_snapshot_hash": settings_snapshot.content_hash,
                    "route_reused_from_task": POST_AUDIT_REVISION_ROUTE_TASK_KEY,
                    "provider": expected_provider,
                    "model": expected_model,
                    "runner_version": capability.version,
                    "prompt_version": prompt_version,
                    "recipe_version": recipe_version,
                    "context_manifest_id": str(manifest.id),
                    "context_manifest_hash": manifest.content_hash,
                    "source_draft_artifact_id": str(revision_input.source_artifact.id),
                    "source_draft_version": revision_input.source_artifact.version,
                    "source_draft_hash": revision_input.source_artifact.content_hash,
                    "failed_audit_artifact_id": str(revision_input.audit_artifact.id),
                    "failed_audit_artifact_version": revision_input.audit_artifact.version,
                    "failed_audit_artifact_hash": revision_input.audit_artifact.content_hash,
                    "failed_quality_evaluation_id": str(revision_input.quality_evaluation.id),
                    "target_findings_hash": revision_input.findings_hash,
                    "revised_draft_artifact_id": str(result.artifact.id),
                    "revised_draft_version": result.artifact.version,
                    "revised_draft_hash": result.artifact.content_hash,
                    "model_attempts": result.model_attempts,
                    "reused": result.reused,
                    "draft": result.draft.to_dict(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
