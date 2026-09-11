"""Run the deterministic CE05 T05.15 English source-copy warning cleanup."""

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
from app.modules.content_engine.journal.source_copy_cleanup import (
    REPLACEMENT_TEXT,
    SOURCE_COPY_CLEANUP_GENERATOR_VERSION,
    SOURCE_COPY_CLEANUP_TASK_KEY,
    TARGET_SEGMENT_ID,
    TARGET_TEXT,
    SourceCopyCleanupGenerator,
    load_source_copy_cleanup_input,
)
from app.modules.content_engine.journal.writer import WriterGenerationError
from app.modules.harness.models import StepRun
from app.modules.harness.persistence import create_step_retry, transition_run, transition_step_run

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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministically replace the locked EN source-copy warning."
    )
    parser.add_argument("--writer-run-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-draft-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-draft-version", required=True, type=_positive_int)
    parser.add_argument("--source-draft-hash", required=True, type=_hash_arg)
    parser.add_argument("--assertion-audit-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--assertion-audit-version", required=True, type=_positive_int)
    parser.add_argument("--assertion-audit-hash", required=True, type=_hash_arg)
    parser.add_argument("--assertion-audit-quality-evaluation-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-copy-eval-run-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-copy-handoff-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-copy-handoff-hash", required=True, type=_hash_arg)
    parser.add_argument("--source-copy-step-run-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-copy-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-copy-artifact-version", required=True, type=_positive_int)
    parser.add_argument("--source-copy-artifact-hash", required=True, type=_hash_arg)
    parser.add_argument("--source-copy-quality-evaluation-id", required=True, type=_uuid_arg)
    parser.add_argument("--outline-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--outline-artifact-version", required=True, type=_positive_int)
    parser.add_argument("--outline-artifact-hash", required=True, type=_hash_arg)
    return parser


async def _step(
    session: AsyncSession,
    *,
    run_id: UUID,
    input_refs: list[str],
) -> tuple[StepRun, bool]:
    rows = list(
        (
            await session.scalars(
                select(StepRun)
                .where(
                    StepRun.run_id == run_id,
                    StepRun.step_key == SOURCE_COPY_CLEANUP_TASK_KEY,
                )
                .order_by(StepRun.attempt, StepRun.created_at, StepRun.id)
            )
        ).all()
    )
    if not rows:
        step = StepRun(
            run_id=run_id,
            step_key=SOURCE_COPY_CLEANUP_TASK_KEY,
            attempt=1,
            status="pending",
            input_artifact_refs_json=input_refs,
            output_artifact_refs_json=[],
        )
        session.add(step)
        await session.flush()
        return step, True
    attempts = [row.attempt for row in rows]
    if attempts != list(range(1, len(rows) + 1)):
        raise WriterGenerationError("source_copy_cleanup_step_attempt_conflict")
    latest = rows[-1]
    if not set(input_refs).issubset(set(latest.input_artifact_refs_json)):
        raise WriterGenerationError("source_copy_cleanup_step_input_mismatch")
    if latest.status == "completed":
        if any(row.status != "failed" for row in rows[:-1]):
            raise WriterGenerationError("source_copy_cleanup_step_history_conflict")
        return latest, False
    if latest.status == "failed":
        if any(row.status != "failed" for row in rows[:-1]):
            raise WriterGenerationError("source_copy_cleanup_step_history_conflict")
        return await create_step_retry(session, failed_step_run_id=latest.id), True
    raise WriterGenerationError(
        "source_copy_cleanup_step_existing_not_terminal",
        latest.status,
    )


async def _run(args: argparse.Namespace) -> None:
    async with SessionLocal() as session:
        cleanup_input = await load_source_copy_cleanup_input(
            session,
            writer_run_id=cast(UUID, args.writer_run_id),
            source_draft_artifact_id=cast(UUID, args.source_draft_artifact_id),
            expected_source_draft_version=cast(int, args.source_draft_version),
            expected_source_draft_hash=cast(str, args.source_draft_hash),
            assertion_audit_artifact_id=cast(UUID, args.assertion_audit_artifact_id),
            expected_assertion_audit_version=cast(int, args.assertion_audit_version),
            expected_assertion_audit_hash=cast(str, args.assertion_audit_hash),
            assertion_audit_quality_evaluation_id=cast(
                UUID, args.assertion_audit_quality_evaluation_id
            ),
            source_copy_eval_run_id=cast(UUID, args.source_copy_eval_run_id),
            source_copy_handoff_id=cast(UUID, args.source_copy_handoff_id),
            source_copy_handoff_hash=cast(str, args.source_copy_handoff_hash),
            source_copy_step_run_id=cast(UUID, args.source_copy_step_run_id),
            source_copy_artifact_id=cast(UUID, args.source_copy_artifact_id),
            source_copy_artifact_version=cast(int, args.source_copy_artifact_version),
            source_copy_artifact_hash=cast(str, args.source_copy_artifact_hash),
            source_copy_quality_evaluation_id=cast(
                UUID, args.source_copy_quality_evaluation_id
            ),
            outline_artifact_id=cast(UUID, args.outline_artifact_id),
            expected_outline_version=cast(int, args.outline_artifact_version),
            expected_outline_hash=cast(str, args.outline_artifact_hash),
        )
        run = cleanup_input.writer_input.writer_run
        input_refs = [
            str(cleanup_input.source_artifact.id),
            str(cleanup_input.assertion_audit_artifact.id),
            str(cleanup_input.source_copy_handoff.id),
            str(cleanup_input.source_copy_artifact.id),
            str(cleanup_input.writer_input.outline_artifact.id),
        ]
        step, step_created = await _step(session, run_id=run.id, input_refs=input_refs)
        if not set(input_refs).issubset(set(step.input_artifact_refs_json)):
            raise WriterGenerationError("source_copy_cleanup_step_input_mismatch")

        try:
            if step_created:
                if run.status != "waiting_approval":
                    raise WriterGenerationError(
                        "source_copy_cleanup_writer_run_state_invalid",
                        run.status,
                    )
                await transition_run(session, run_id=run.id, status="running")
                run.current_step = SOURCE_COPY_CLEANUP_TASK_KEY
                await transition_step_run(session, step_run_id=step.id, status="running")
            result = await SourceCopyCleanupGenerator().cleanup_draft(
                session,
                cleanup_input=cleanup_input,
                step_run_id=step.id,
            )
        except Exception as exc:
            if step_created and step.status == "running":
                error_code = getattr(exc, "code", exc.__class__.__name__)
                step.error_json = {"code": str(error_code)}
                await transition_step_run(session, step_run_id=step.id, status="failed")
            if step_created and run.status == "running":
                await transition_run(session, run_id=run.id, status="waiting_approval")
            await session.commit()
            raise

        if step_created:
            await transition_step_run(session, step_run_id=step.id, status="completed")
            await transition_run(session, run_id=run.id, status="waiting_approval")
        await session.commit()
        print(
            json.dumps(
                {
                    "writer_run_id": str(run.id),
                    "writer_run_status": run.status,
                    "locale": "en",
                    "task_key": SOURCE_COPY_CLEANUP_TASK_KEY,
                    "step_run_id": str(step.id),
                    "step_attempt": step.attempt,
                    "step_status": step.status,
                    "source_draft_artifact_id": str(cleanup_input.source_artifact.id),
                    "source_draft_version": cleanup_input.source_artifact.version,
                    "source_draft_hash": cleanup_input.source_artifact.content_hash,
                    "assertion_audit_artifact_id": str(
                        cleanup_input.assertion_audit_artifact.id
                    ),
                    "assertion_audit_artifact_version": (
                        cleanup_input.assertion_audit_artifact.version
                    ),
                    "assertion_audit_artifact_hash": (
                        cleanup_input.assertion_audit_artifact.content_hash
                    ),
                    "assertion_audit_quality_evaluation_id": str(
                        cleanup_input.assertion_audit_evaluation.id
                    ),
                    "source_copy_eval_run_id": str(cleanup_input.source_copy_eval_run.id),
                    "source_copy_handoff_id": str(cleanup_input.source_copy_handoff.id),
                    "source_copy_handoff_hash": cleanup_input.source_copy_handoff.content_hash,
                    "source_copy_step_run_id": str(cleanup_input.source_copy_step.id),
                    "source_copy_artifact_id": str(cleanup_input.source_copy_artifact.id),
                    "source_copy_artifact_version": cleanup_input.source_copy_artifact.version,
                    "source_copy_artifact_hash": cleanup_input.source_copy_artifact.content_hash,
                    "source_copy_quality_evaluation_id": str(
                        cleanup_input.source_copy_evaluation.id
                    ),
                    "source_copy_warning": cleanup_input.warning.to_dict(),
                    "cleanup_generator_version": SOURCE_COPY_CLEANUP_GENERATOR_VERSION,
                    "target_segment_id": TARGET_SEGMENT_ID,
                    "target_text": TARGET_TEXT,
                    "replacement_text": REPLACEMENT_TEXT,
                    "cleanup_artifact_id": str(result.artifact.id),
                    "cleanup_artifact_version": result.artifact.version,
                    "cleanup_artifact_hash": result.artifact.content_hash,
                    "model_attempts": result.model_attempts,
                    "model_calls": 0,
                    "provider_calls": 0,
                    "tool_calls": 0,
                    "context_manifests": 0,
                    "prompt_version": None,
                    "recipe_version": None,
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
