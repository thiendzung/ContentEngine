"""Run the real EN Journal review/revise stage through T05.22E orchestration."""

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

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from app.modules.content_engine.journal.review_revise_orchestration import (
    REVIEW_REVISE_EN_TASK_KEY,
    ReviewReviseEnRequest,
    run_review_revise_en_orchestration,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.controlled_delegation import SettingsDelegationRouter
from app.modules.harness.models import Artifact, ContentRun, StepRun
from app.modules.harness.repo_aware_agent_runner import repo_aware_agent_runner_registry
from app.modules.harness.repository_snapshot import RepositorySnapshotSpec

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


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


def _git_sha_arg(value: str) -> str:
    normalized = value.strip().lower()
    if _GIT_SHA_PATTERN.fullmatch(normalized) is None:
        raise argparse.ArgumentTypeError("must be an exact lowercase 40-character Git commit SHA")
    return normalized


def _non_empty(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return value.strip()


def _repository_root(value: str) -> str:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError("must be an existing repository directory")
    return str(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run only review_revise_en through the bounded repo-aware orchestration harness."
        )
    )
    parser.add_argument("--writer-run-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-draft-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--source-draft-version", required=True, type=_positive_int)
    parser.add_argument("--source-draft-hash", required=True, type=_hash_arg)
    parser.add_argument("--outline-artifact-id", required=True, type=_uuid_arg)
    parser.add_argument("--outline-artifact-version", required=True, type=_positive_int)
    parser.add_argument("--outline-artifact-hash", required=True, type=_hash_arg)
    parser.add_argument("--locale", required=True, choices=("en",))
    parser.add_argument("--expected-provider", required=True, type=_non_empty)
    parser.add_argument("--expected-model", required=True, type=_non_empty)
    parser.add_argument("--repository-root", required=True, type=_repository_root)
    parser.add_argument("--repository-revision", required=True, type=_git_sha_arg)
    return parser


async def _run(args: argparse.Namespace) -> None:
    request = ReviewReviseEnRequest(
        writer_run_id=cast(UUID, args.writer_run_id),
        source_draft_artifact_id=cast(UUID, args.source_draft_artifact_id),
        source_draft_version=cast(int, args.source_draft_version),
        source_draft_hash=cast(str, args.source_draft_hash),
        outline_artifact_id=cast(UUID, args.outline_artifact_id),
        outline_artifact_version=cast(int, args.outline_artifact_version),
        outline_artifact_hash=cast(str, args.outline_artifact_hash),
        repository=RepositorySnapshotSpec(
            repository_root=cast(str, args.repository_root),
            revision=cast(str, args.repository_revision),
        ),
    )
    expected_provider = cast(str, args.expected_provider)
    expected_model = cast(str, args.expected_model)

    async with SessionLocal() as session:
        writer_run = await session.get(ContentRun, request.writer_run_id)
        if writer_run is None:
            raise RuntimeError("review_revise_writer_run_not_found")
        snapshot = await session.get(SettingsSnapshot, writer_run.settings_snapshot_id)
        if snapshot is None:
            raise RuntimeError("review_revise_settings_snapshot_missing")
        route = SettingsDelegationRouter().resolve(
            task_key=REVIEW_REVISE_EN_TASK_KEY,
            settings_snapshot=snapshot,
        )
        if route.provider != expected_provider or route.model != expected_model:
            raise RuntimeError(
                "review_revise_delegation_route_mismatch: "
                f"resolved={route.provider}/{route.model}"
            )

        result = await run_review_revise_en_orchestration(
            session,
            request=request,
            runner_registry=repo_aware_agent_runner_registry(),
        )
        await session.commit()

        output: Artifact | None = None
        if result.revised_draft_artifact_id is not None:
            output = await session.get(Artifact, result.revised_draft_artifact_id)
        step = await session.scalar(
            select(StepRun).where(
                StepRun.run_id == request.writer_run_id,
                StepRun.step_key == REVIEW_REVISE_EN_TASK_KEY,
            )
        )
        print(
            json.dumps(
                {
                    "writer_run_id": str(request.writer_run_id),
                    "locale": "en",
                    "task_key": REVIEW_REVISE_EN_TASK_KEY,
                    "final_outcome": result.orchestration.final_outcome.value,
                    "error_code": result.orchestration.error_code,
                    "human_gate": result.orchestration.human_gate,
                    "cycles": [
                        {
                            "cycle": cycle.cycle,
                            "action_key": cycle.action_key,
                            "attempt": cycle.attempt,
                            "dedupe_key": cycle.dedupe_key,
                            "outcome": cycle.outcome.value,
                            "error_code": cycle.error_code,
                        }
                        for cycle in result.orchestration.cycles
                    ],
                    "step_run_id": str(step.id) if step is not None else None,
                    "step_status": step.status if step is not None else None,
                    "provider": route.provider,
                    "model": route.model,
                    "repository_revision": request.repository.revision,
                    "revised_draft_artifact_id": (
                        str(output.id) if output is not None else None
                    ),
                    "revised_draft_version": output.version if output is not None else None,
                    "revised_draft_hash": output.content_hash if output is not None else None,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
