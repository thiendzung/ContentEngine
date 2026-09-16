"""Claim and execute one allow-listed Journal operator job."""

# ruff: noqa: E402

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
from pathlib import Path
from uuid import UUID

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import httpx
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.modules.content_engine.journal.operator_outline_worker import (
    OperatorOutlineWorkerError,
    claim_or_reclaim_outline_job,
    execute_outline_job,
    fail_outline_job,
)
from app.modules.content_engine.journal.operator_recovery import claim_or_reclaim_operator_job
from app.modules.content_engine.journal.operator_runtime import START_TO_ANGLE_STAGE
from app.modules.content_engine.journal.operator_worker import (
    OperatorWorkerError,
    execute_start_to_angle_job,
    fail_start_to_angle_job,
    heartbeat_operator_job,
)
from app.modules.content_engine.journal.outline_agent_bridge import OUTLINE_TASK_KEY
from app.modules.harness.agent_runner import AgentRunnerRegistry, CodexCliRunner
from app.modules.harness.models import ContentRun, StepRun
from app.modules.harness.persistence import transition_run
from app.modules.harness.policy import BudgetLimits
from app.modules.research.evidence import EvidenceResearchWorkflow
from app.modules.research.production import ProductionSufficiencyPolicy, ResearchRouter
from app.modules.research.providers.exa import ExaProvider
from app.modules.research.providers.jina import JinaReader
from app.modules.research.providers.serper import SerperProvider
from app.modules.research.providers.tavily import TavilyProvider

_LEASE_SECONDS = 900
_HEARTBEAT_SECONDS = 240


def _secret_value(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret is not None else None


def _worker_id() -> str:
    return f"operator:{socket.gethostname()}:{os.getpid()}"


def _research_router(
    settings: Settings,
    client: httpx.AsyncClient,
) -> ResearchRouter:
    serper_key = _secret_value(settings.serper_api_key)
    if not serper_key:
        raise OperatorWorkerError("operator_worker_serper_required")
    tavily_key = _secret_value(settings.tavily_api_key)
    exa_key = _secret_value(settings.exa_api_key)
    jina_key = _secret_value(settings.jina_api_key)
    raw_excerpt_chars = settings.research_max_raw_excerpt_chars
    return ResearchRouter(
        serper=SerperProvider(
            serper_key,
            client,
            raw_excerpt_chars=raw_excerpt_chars,
        ),
        tavily=(
            TavilyProvider(
                tavily_key,
                client,
                raw_excerpt_chars=raw_excerpt_chars,
            )
            if tavily_key
            else None
        ),
        exa=(
            ExaProvider(
                exa_key,
                client,
                raw_excerpt_chars=raw_excerpt_chars,
            )
            if exa_key
            else None
        ),
        reader=JinaReader(
            client,
            jina_key,
            raw_excerpt_chars=raw_excerpt_chars,
            token_budget=settings.research_jina_token_budget,
            max_links=settings.research_jina_max_links,
        ),
        budget_limits=BudgetLimits(
            max_tool_calls=settings.research_max_provider_calls,
            max_research_sources=settings.research_max_selected_urls,
        ),
        sufficiency=ProductionSufficiencyPolicy(min_internal_hits=1_000_000),
    )


async def _heartbeat_loop(
    *,
    job_id: UUID,
    worker_id: str,
    stop: asyncio.Event,
) -> None:
    """Keep one durable lease alive while model/research work is in progress."""

    while True:
        try:
            await asyncio.wait_for(stop.wait(), timeout=_HEARTBEAT_SECONDS)
            return
        except TimeoutError:
            pass
        async with SessionLocal() as session:
            async with session.begin():
                await heartbeat_operator_job(
                    session,
                    job_id=job_id,
                    worker_id=worker_id,
                    lease_seconds=_LEASE_SECONDS,
                )


async def _stop_heartbeat(task: asyncio.Task[None], stop: asyncio.Event) -> None:
    stop.set()
    await task


async def _claim_job(*, worker_id: str) -> tuple[UUID, str] | None:
    async with SessionLocal() as session:
        async with session.begin():
            job = await claim_or_reclaim_operator_job(
                session,
                worker_id=worker_id,
                lease_seconds=_LEASE_SECONDS,
            )
            if job is None:
                job = await claim_or_reclaim_outline_job(
                    session,
                    worker_id=worker_id,
                    lease_seconds=_LEASE_SECONDS,
                )
            if job is None:
                return None
            run = await session.get(ContentRun, job.run_id)
            step = await session.get(StepRun, job.step_run_id)
            if run is None or step is None or step.run_id != run.id:
                raise OperatorWorkerError("operator_worker_binding_invalid")
            if step.step_key not in {START_TO_ANGLE_STAGE, OUTLINE_TASK_KEY}:
                raise OperatorWorkerError("operator_worker_stage_not_allowed")
            if run.status == "pending":
                await transition_run(session, run_id=run.id, status="running")
            return job.id, step.step_key


async def _run(*, emit_idle: bool = True) -> None:
    settings = get_settings()
    worker_id = _worker_id()
    claimed = await _claim_job(worker_id=worker_id)
    if claimed is None:
        if emit_idle:
            print(
                json.dumps(
                    {"status": "idle", "worker_id": worker_id},
                    sort_keys=True,
                )
            )
        return
    job_id, step_key = claimed

    registry = AgentRunnerRegistry()
    registry.register("codex_cli", CodexCliRunner())
    stop = asyncio.Event()
    heartbeat = asyncio.create_task(
        _heartbeat_loop(job_id=job_id, worker_id=worker_id, stop=stop)
    )
    try:
        if step_key == START_TO_ANGLE_STAGE:
            timeout = httpx.Timeout(settings.research_request_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                workflow = EvidenceResearchWorkflow(router=_research_router(settings, client))
                async with SessionLocal() as session:
                    async with session.begin():
                        result = await execute_start_to_angle_job(
                            session,
                            job_id=job_id,
                            worker_id=worker_id,
                            evidence_workflow=workflow,
                            runner_registry=registry,
                        )
        else:
            async with SessionLocal() as session:
                async with session.begin():
                    result = await execute_outline_job(
                        session,
                        job_id=job_id,
                        worker_id=worker_id,
                        runner_registry=registry,
                    )
    except Exception as exc:
        try:
            await _stop_heartbeat(heartbeat, stop)
        except Exception:
            pass
        if step_key == OUTLINE_TASK_KEY:
            failure_class = (
                exc.code
                if isinstance(exc, OperatorOutlineWorkerError)
                else "outline_generation_failed"
            )
            async with SessionLocal() as session:
                async with session.begin():
                    await fail_outline_job(
                        session,
                        job_id=job_id,
                        worker_id=worker_id,
                        failure_class=failure_class,
                        message=str(exc)[:2000],
                    )
        else:
            failure_class = (
                "insufficient_evidence"
                if isinstance(exc, OperatorWorkerError) and "evidence" in exc.code
                else "internal_error"
            )
            async with SessionLocal() as session:
                async with session.begin():
                    await fail_start_to_angle_job(
                        session,
                        job_id=job_id,
                        worker_id=worker_id,
                        failure_class=failure_class,
                        message=str(exc)[:2000],
                    )
        raise
    else:
        await _stop_heartbeat(heartbeat, stop)

    payload: dict[str, object] = {
        "status": "completed",
        "worker_id": worker_id,
        "job_id": str(result.job_id),
        "run_id": str(result.run_id),
        "step_run_id": str(result.step_run_id),
        "state_version": result.state_version,
    }
    if step_key == OUTLINE_TASK_KEY:
        payload.update(
            {
                "outline_artifact_id": str(result.outline_artifact_id),
                "outline_artifact_hash": result.outline_artifact_hash,
            }
        )
    else:
        payload.update(
            {
                "angle_artifact_id": str(result.angle_artifact_id),
                "angle_artifact_hash": result.angle_artifact_hash,
            }
        )
    print(json.dumps(payload, sort_keys=True))


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
