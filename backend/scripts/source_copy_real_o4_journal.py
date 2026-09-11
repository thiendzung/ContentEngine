"""Run the deterministic CE05 T05.15 basic source-copy check."""

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

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from app.modules.content_engine.journal.source_copy import (
    SOURCE_COPY_EVALUATOR_KEY,
    SOURCE_COPY_EVALUATOR_VERSION,
    SOURCE_COPY_GENERATOR_VERSION,
    SOURCE_COPY_SCHEMA_VERSION,
    SOURCE_COPY_TASK_KEYS,
    execute_source_copy,
    load_source_copy_input,
)

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
        description="Run the deterministic bounded CE05 T05.15 source-copy check."
    )
    parser.add_argument("--locale", required=True, choices=sorted(SOURCE_COPY_TASK_KEYS))
    parser.add_argument("--writer-run-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-draft-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-draft-version", required=True, type=_positive_int)
    parser.add_argument("--source-draft-hash", required=True, type=_hash_arg)
    parser.add_argument("--assertion-audit-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--assertion-audit-version", required=True, type=_positive_int)
    parser.add_argument("--assertion-audit-hash", required=True, type=_hash_arg)
    parser.add_argument("--assertion-audit-quality-evaluation-id", required=True, type=_uuid_arg)
    parser.add_argument("--outline-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--outline-artifact-version", required=True, type=_positive_int)
    parser.add_argument("--outline-artifact-hash", required=True, type=_hash_arg)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate immutable T05.14/source-copy inputs without creating a run.",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    async with SessionLocal() as session:
        source_input = await load_source_copy_input(
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
            outline_artifact_id=cast(UUID, args.outline_artifact_id),
            expected_outline_version=cast(int, args.outline_artifact_version),
            expected_outline_hash=cast(str, args.outline_artifact_hash),
            locale=cast(str, args.locale),
        )
        if args.preflight_only:
            print(
                json.dumps(
                    {
                        "preflight": "pass",
                        "locale": source_input.writer_input.locale,
                        "writer_run_id": str(source_input.writer_input.writer_run.id),
                        "source_draft": {
                            "id": str(source_input.source_artifact.id),
                            "version": source_input.source_artifact.version,
                            "content_hash": source_input.source_artifact.content_hash,
                        },
                        "assertion_audit_artifact_id": str(
                            source_input.assertion_audit_artifact.id
                        ),
                        "assertion_audit_quality_evaluation_id": str(
                            source_input.assertion_audit_evaluation.id
                        ),
                        "source_corpus_count": len(source_input.sources),
                        "context_manifest_count": 0,
                        "model_calls": 0,
                        "tool_calls": 0,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return

        task_key = SOURCE_COPY_TASK_KEYS[source_input.writer_input.locale]
        try:
            result = await execute_source_copy(
                session,
                source_input=source_input,
                task_key=task_key,
            )
        except Exception:
            # The execution boundary preserves a failed eval run and its StepRun.
            await session.commit()
            raise
        await session.commit()
        print(
            json.dumps(
                {
                    "locale": source_input.writer_input.locale,
                    "task_key": task_key,
                    "source_copy_eval_run_id": str(result.eval_run.id),
                    "eval_run_status": result.eval_run.status,
                    "source_copy_handoff_id": str(result.handoff.id),
                    "source_copy_handoff_hash": result.handoff.content_hash,
                    "step_run_id": str(result.step_run.id),
                    "step_attempt": result.step_run.attempt,
                    "step_status": result.step_run.status,
                    "source_writer_run_id": str(source_input.writer_input.writer_run.id),
                    "source_draft_artifact_id": str(source_input.source_artifact.id),
                    "source_draft_version": source_input.source_artifact.version,
                    "source_draft_hash": source_input.source_artifact.content_hash,
                    "assertion_audit_artifact_id": str(
                        source_input.assertion_audit_artifact.id
                    ),
                    "assertion_audit_artifact_hash": (
                        source_input.assertion_audit_artifact.content_hash
                    ),
                    "assertion_audit_quality_evaluation_id": str(
                        source_input.assertion_audit_evaluation.id
                    ),
                    "source_copy_artifact_id": str(result.artifact.id),
                    "source_copy_artifact_version": result.artifact.version,
                    "source_copy_artifact_hash": result.artifact.content_hash,
                    "quality_evaluation_id": str(result.evaluation.id),
                    "quality_result": result.evaluation.result,
                    "algorithm": "exact_contiguous_normalized_token_overlap",
                    "generator_version": SOURCE_COPY_GENERATOR_VERSION,
                    "evaluator_key": SOURCE_COPY_EVALUATOR_KEY,
                    "evaluator_version": SOURCE_COPY_EVALUATOR_VERSION,
                    "schema_version": SOURCE_COPY_SCHEMA_VERSION,
                    "summary": result.check.summary(),
                    "findings": [finding.to_dict() for finding in result.check.findings],
                    "model_attempts": result.model_attempts,
                    "model_calls": 0,
                    "provider_calls": 0,
                    "tool_calls": 0,
                    "context_manifests": 0,
                    "reused": result.reused,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
