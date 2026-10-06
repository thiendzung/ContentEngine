# ruff: noqa: E402

"""Run bounded QM-02F1R3 Search Discovery against one canonical Need."""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import httpx
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.modules.content_engine.models import NeedHypothesis, Project
from app.modules.harness.policy import BudgetLimits
from app.modules.research.keyword_plan.search_discovery import (
    SearchDiscoveryRequest,
    capture_hash,
    run_search_discovery,
)
from app.modules.research.production import ResearchRouter
from app.modules.research.providers.exa import ExaProvider
from app.modules.research.providers.serper import SerperProvider
from app.modules.research.providers.tavily import TavilyProvider


def _secret_value(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret is not None else None


def _default_output() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return (
        repo_root
        / "artifacts"
        / "research"
        / f"qm-search-discovery-v1-{timestamp}.json"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run bounded real Search Discovery into an existing canonical "
            "Question Map Need. No Founder selection or content materialization."
        )
    )
    parser.add_argument("--project", default="motgu")
    parser.add_argument("--need-id", required=True)
    parser.add_argument(
        "--seed",
        action="append",
        dest="seeds",
        required=True,
        help="Repeat for each bounded seed query.",
    )
    parser.add_argument("--locale", default="en")
    parser.add_argument("--country", default="us")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-hops", type=int, default=1)
    parser.add_argument("--max-expansions-per-hop", type=int, default=4)
    parser.add_argument("--max-total-queries", type=int, default=8)
    parser.add_argument("--output", type=Path)
    return parser


async def _run(args: argparse.Namespace, settings: Settings) -> Path:
    serper_key = _secret_value(settings.serper_api_key)
    if not serper_key:
        raise RuntimeError(
            "SERPER_API_KEY is required for QM Search Discovery"
        )

    output = cast(Path | None, args.output) or _default_output()
    repo_root = Path(__file__).resolve().parents[2]
    try:
        locator = output.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        locator = output.name
    artifact_ref = f"artifact-file:{locator}"

    try:
        need_id = UUID(cast(str, args.need_id))
    except ValueError as exc:
        raise RuntimeError("invalid_need_id") from exc

    timeout = httpx.Timeout(settings.research_request_timeout_seconds)
    async with SessionLocal() as session:
        project = await session.scalar(
            select(Project).where(Project.slug == cast(str, args.project))
        )
        if project is None:
            raise RuntimeError(f"project_not_found:{args.project}")
        need = await session.get(NeedHypothesis, need_id)
        if need is None or need.project_id != project.id:
            raise RuntimeError(f"need_not_found:{need_id}")

        tavily_key = _secret_value(settings.tavily_api_key)
        exa_key = _secret_value(settings.exa_api_key)
        raw_excerpt_chars = settings.research_max_raw_excerpt_chars

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            router = ResearchRouter(
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
                # F1R3 is search-language discovery, not factual source
                # reading. Jina remains downstream and is intentionally
                # absent from this bounded run.
                reader=None,
                budget_limits=BudgetLimits(
                    max_tool_calls=settings.research_max_provider_calls,
                    max_research_sources=settings.research_max_selected_urls,
                ),
            )
            result = await run_search_discovery(
                session,
                runner=router,
                request=SearchDiscoveryRequest(
                    project_id=project.id,
                    need_id=need.id,
                    locale=cast(str, args.locale),
                    country=cast(str, args.country),
                    seed_queries=tuple(cast(list[str], args.seeds)),
                    artifact_ref=artifact_ref,
                    result_limit=cast(int, args.limit),
                    max_hops=cast(int, args.max_hops),
                    max_expansions_per_hop=cast(
                        int,
                        args.max_expansions_per_hop,
                    ),
                    max_total_queries=cast(
                        int,
                        args.max_total_queries,
                    ),
                ),
            )

        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            **result.as_dict(),
            "capture_hash": capture_hash(result),
            "need": {
                "id": str(need.id),
                "status": need.status,
                "version": need.version,
                "statement": need.statement,
            },
        }
        try:
            with output.open("x", encoding="utf-8") as capture_file:
                capture_file.write(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        indent=2,
                        default=str,
                    )
                )
            await session.commit()
        except Exception:
            output.unlink(missing_ok=True)
            raise

    summary = {
        "artifact": str(output),
        "capture_hash": payload["capture_hash"],
        "need_id": str(need_id),
        "locale": result.locale,
        "seed_queries": len(result.seed_queries),
        "executed_queries": len(result.executed_queries),
        "observations": len(result.observations),
        "persisted_signals": len(result.persisted_signal_ids),
        "created_signals": len(result.created_signal_ids),
        "reused_signals": len(result.reused_signal_ids),
        "questions": result.question_count,
        "clusters": result.cluster_count,
        "pillar_candidates": result.pillar_candidate_count,
        "question_map_snapshot_hash": result.question_map_snapshot_hash,
        "architecture_snapshot_hash": result.architecture_snapshot_hash,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return output


def main() -> None:
    args = _parser().parse_args()
    asyncio.run(_run(args, get_settings()))


if __name__ == "__main__":
    main()
