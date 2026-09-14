"""Claim and execute one allow-listed Journal operator job."""

# ruff: noqa: E402

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import httpx
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.modules.content_engine.journal.operator_worker import (
    OperatorWorkerError,
    claim_next_operator_job,
    execute_start_to_angle_job,
)
from app.modules.harness.agent_runner import AgentRunnerRegistry, CodexCliRunner
from app.modules.harness.models import ContentRun
from app.modules.harness.persistence import fail_job_and_maybe_retry, transition_run
from app.modules.harness.policy import BudgetLimits, RetryPolicy
from app.modules.research.evidence import EvidenceResearchWorkflow
from app.modules.research.production import ProductionSufficiencyPolicy, ResearchRouter
from app.modules.research.providers.exa import ExaProvider
from app.modules.research.providers.jina import JinaReader
from app.modules.research.providers.serper import SerperProvider
from app.modules.research.providers.tavily import TavilyProvider


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


async def _run() -> None:
    settings = get_settings()
    worker_id = _worker_id()
    async with SessionLocal() as session:
        async with session.begin():
            job = await claim_next_operator_job(session, worker_id=worker_id)
            if job is None:
                print(
                    json.dumps(
                        {"status": "idle", "worker_id": worker_id},
                        sort_keys=True,
                    )
                )
                return
            run = await session.get(ContentRun, job.run_id)
            if run is None:
                raise OperatorWorkerError("operator_worker_run_missing")
            if run.status == "pending":
                await transition_run(session, run_id=run.id, status="running")
            job_id = job.id

    timeout = httpx.Timeout(settings.research_request_timeout_seconds)
    registry = AgentRunnerRegistry()
    registry.register("codex_cli", CodexCliRunner())
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            workflow = EvidenceResearchWorkflow(
                router=_research_router(settings, client)
            )
            async with SessionLocal() as session:
                async with session.begin():
                    result = await execute_start_to_angle_job(
                        session,
                        job_id=job_id,
                        worker_id=worker_id,
                        evidence_workflow=workflow,
                        runner_registry=registry,
                    )
    except Exception as exc:
        failure_class = (
            "insufficient_evidence"
            if isinstance(exc, OperatorWorkerError) and "evidence" in exc.code
            else "internal_error"
        )
        async with SessionLocal() as session:
            async with session.begin():
                await fail_job_and_maybe_retry(
                    session,
                    job_id=job_id,
                    worker_id=worker_id,
                    failure_class=failure_class,
                    message=str(exc)[:2000],
                    retry_policy=RetryPolicy(max_step_attempts=1),
                )
        raise

    print(
        json.dumps(
            {
                "status": "completed",
                "worker_id": worker_id,
                "job_id": str(result.job_id),
                "run_id": str(result.run_id),
                "step_run_id": str(result.step_run_id),
                "angle_artifact_id": str(result.angle_artifact_id),
                "angle_artifact_hash": result.angle_artifact_hash,
                "state_version": result.state_version,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
