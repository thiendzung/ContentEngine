"""Run the deterministic final English closing cleanup for CE05 T05.14."""

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
from app.modules.content_engine.journal.post_audit_cleanup import (
    POST_AUDIT_CLEANUP_TASK_KEY,
    PostAuditCleanupGenerator,
    load_post_audit_cleanup_input,
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
        description="Deterministically remove the locked unsupported EN closing sentence."
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
                    StepRun.step_key == POST_AUDIT_CLEANUP_TASK_KEY,
                )
                .order_by(StepRun.attempt, StepRun.created_at, StepRun.id)
            )
        ).all()
    )
    if not rows:
        step = StepRun(
            run_id=run_id,
            step_key=POST_AUDIT_CLEANUP_TASK_KEY,
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
        raise WriterGenerationError("post_audit_cleanup_step_attempt_conflict")
    latest = rows[-1]
    if latest.status == "completed":
        if any(row.status != "failed" for row in rows[:-1]):
            raise WriterGenerationError("post_audit_cleanup_step_history_conflict")
        return latest, False
    if latest.status == "failed":
        if any(row.status != "failed" for row in rows[:-1]):
            raise WriterGenerationError("post_audit_cleanup_step_history_conflict")
        return await create_step_retry(session, failed_step_run_id=latest.id), True
    raise WriterGenerationError(
        "post_audit_cleanup_step_existing_not_terminal",
        latest.status,
    )


async def _run(args: argparse.Namespace) -> None:
    async with SessionLocal() as session:
        cleanup_input = await load_post_audit_cleanup_input(
            session,
            writer_run_id=cast(UUID, args.writer_run_id),
            source_draft_artifact_id=cast(UUID, args.source_draft_artifact_id),
            expected_source_draft_version=cast(int, args.source_draft_version),
            expected_source_draft_hash=cast(str, args.source_draft_hash),
            failed_audit_artifact_id=cast(UUID, args.failed_audit_artifact_id),
            expected_failed_audit_version=cast(int, args.failed_audit_version),
            expected_failed_audit_hash=cast(str, args.failed_audit_hash),
            failed_quality_evaluation_id=cast(UUID, args.failed_quality_evaluation_id),
            outline_artifact_id=cast(UUID, args.outline_artifact_id),
            expected_outline_version=cast(int, args.outline_artifact_version),
            expected_outline_hash=cast(str, args.outline_artifact_hash),
        )
        run = cleanup_input.writer_input.writer_run
        input_refs = [
            str(cleanup_input.source_artifact.id),
            str(cleanup_input.failed_audit_artifact.id),
            str(cleanup_input.writer_input.handoff_artifact.id),
            str(cleanup_input.writer_input.outline_artifact.id),
        ]
        step, step_created = await _step(session, run_id=run.id, input_refs=input_refs)
        if step.step_key != POST_AUDIT_CLEANUP_TASK_KEY or not set(input_refs).issubset(
            set(step.input_artifact_refs_json)
        ):
            raise WriterGenerationError("post_audit_cleanup_step_input_mismatch")

        try:
            if step_created:
                if run.status != "waiting_approval":
                    raise WriterGenerationError(
                        "post_audit_cleanup_writer_run_state_invalid",
                        run.status,
                    )
                await transition_run(session, run_id=run.id, status="running")
                run.current_step = POST_AUDIT_CLEANUP_TASK_KEY
                await transition_step_run(session, step_run_id=step.id, status="running")
            result = await PostAuditCleanupGenerator().cleanup_draft(
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
                    "task_key": POST_AUDIT_CLEANUP_TASK_KEY,
                    "step_run_id": str(step.id),
                    "step_attempt": step.attempt,
                    "step_status": step.status,
                    "source_draft_artifact_id": str(cleanup_input.source_artifact.id),
                    "source_draft_version": cleanup_input.source_artifact.version,
                    "source_draft_hash": cleanup_input.source_artifact.content_hash,
                    "failed_audit_artifact_id": str(cleanup_input.failed_audit_artifact.id),
                    "failed_audit_artifact_version": cleanup_input.failed_audit_artifact.version,
                    "failed_audit_artifact_hash": cleanup_input.failed_audit_artifact.content_hash,
                    "failed_quality_evaluation_id": str(
                        cleanup_input.failed_quality_evaluation.id
                    ),
                    "removed_segment_id": "closing:3",
                    "removed_segment_text": (
                        "There is nothing formal about asking for a clearer answer."
                    ),
                    "cleanup_generator_version": (
                        "ce05.journal_post_audit_cleanup.v1"
                    ),
                    "cleanup_artifact_id": str(result.artifact.id),
                    "cleanup_artifact_version": result.artifact.version,
                    "cleanup_artifact_hash": result.artifact.content_hash,
                    "model_attempts": result.model_attempts,
                    "model_calls": 0,
                    "provider_calls": 0,
                    "tool_calls": 0,
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
