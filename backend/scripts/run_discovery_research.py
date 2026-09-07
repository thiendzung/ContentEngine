# ruff: noqa: E402

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import httpx
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.modules.content_engine.models import Project
from app.modules.harness.policy import BudgetLimits
from app.modules.research.contracts import ProductionResearchRequest, ResearchDepth
from app.modules.research.discovery import DiscoveryResearchWorkflow, DiscoveryWorkflowRequest
from app.modules.research.discovery.artifact import write_discovery_workflow_artifact
from app.modules.research.keyword_plan.artifact import opportunity_map_markdown
from app.modules.research.keyword_plan.contracts import NeedType
from app.modules.research.keyword_plan.service import OpportunityMapRequest
from app.modules.research.production import ResearchRouter
from app.modules.research.providers.exa import ExaProvider
from app.modules.research.providers.jina import JinaReader
from app.modules.research.providers.serper import SerperProvider
from app.modules.research.providers.tavily import TavilyProvider

DEFAULT_QUERY = "first-time art buyer understanding artwork price"
DEFAULT_NEED = (
    "A first-time art buyer wants to understand whether an original artwork price "
    "makes sense before deciding to buy."
)
DEFAULT_AUDIENCE = "international first-time art buyer"
DEFAULT_SITUATION = "considering an original artwork but uncertain how to evaluate the price"


def _secret_value(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret is not None else None


def _default_output() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return (
        repo_root
        / "artifacts"
        / "research"
        / f"ce04-discovery-research-v1-{timestamp}.json"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the CE04 pre-ContentCase Discovery Research workflow."
    )
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--need", default=DEFAULT_NEED)
    parser.add_argument("--audience", default=DEFAULT_AUDIENCE)
    parser.add_argument("--situation", default=DEFAULT_SITUATION)
    parser.add_argument("--reader", default=DEFAULT_AUDIENCE)
    parser.add_argument("--locale", default="en")
    parser.add_argument("--country", default="us")
    parser.add_argument("--project", default="motgu")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--pages", type=int)
    parser.add_argument("--output", type=Path)
    return parser


async def _run(args: argparse.Namespace, settings: Settings) -> Path:
    serper_key = _secret_value(settings.serper_api_key)
    if not serper_key:
        raise RuntimeError("SERPER_API_KEY is required for CE04 Discovery Research")

    output = cast(Path | None, args.output) or _default_output()
    repo_root = Path(__file__).resolve().parents[2]
    try:
        artifact_locator = output.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        artifact_locator = output.name
    artifact_ref = f"artifact-file:{artifact_locator}"

    timeout = httpx.Timeout(settings.research_request_timeout_seconds)
    async with SessionLocal() as session:
        project = (
            await session.execute(
                select(Project).where(Project.slug == cast(str, args.project))
            )
        ).scalar_one_or_none()
        if project is None:
            raise RuntimeError(f"project_not_found:{args.project}")

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            tavily_key = _secret_value(settings.tavily_api_key)
            exa_key = _secret_value(settings.exa_api_key)
            jina_key = _secret_value(settings.jina_api_key)
            raw_excerpt_chars = settings.research_max_raw_excerpt_chars
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
            )
            pages = cast(int | None, args.pages)
            workflow = DiscoveryResearchWorkflow(router=router)
            result = await workflow.run(
                session,
                request=DiscoveryWorkflowRequest(
                    research=ProductionResearchRequest(
                        project_id=project.id,
                        query=cast(str, args.query),
                        locale=cast(str, args.locale),
                        country=cast(str, args.country),
                        limit=cast(int, args.limit),
                        depth=ResearchDepth.STANDARD,
                        max_pages_to_read=(
                            settings.research_max_pages_read if pages is None else pages
                        ),
                    ),
                    opportunity=OpportunityMapRequest(
                        project_id=project.slug,
                        locale=cast(str, args.locale),
                        audience_scope=cast(str, args.audience),
                        situation=cast(str, args.situation),
                        reader=cast(str, args.reader),
                        need_statement=cast(str, args.need),
                        need_type=NeedType.QUESTION,
                        artifact_ref=artifact_ref,
                        missing_evidence=(
                            "Direct MOTGU customer observations are still needed before "
                            "treating external search demand as customer truth.",
                        ),
                    ),
                    artifact_ref=artifact_ref,
                ),
            )

    write_discovery_workflow_artifact(result, output)
    review_output = output.with_suffix(".md")
    review_output.write_text(
        opportunity_map_markdown(result.opportunity_map),
        encoding="utf-8",
    )
    summary = {
        "artifact": str(output),
        "review_markdown": str(review_output),
        "artifact_type": result.artifact_type,
        "schema_version": 1,
        "evidence_eligible": result.evidence_eligible,
        "research_stop_reason": result.research.stop_reason,
        "research_sufficient": result.research.sufficient,
        "hypothesis_status": result.opportunity_map.need_hypothesis.status.value,
        "search_signals": sum(
            1
            for signal in result.opportunity_map.signals
            if signal.source_kind.value == "SEARCH"
        ),
        "market_signals": sum(
            1
            for signal in result.opportunity_map.signals
            if signal.source_kind.value == "MARKET"
        ),
        "questions": len(result.opportunity_map.questions),
        "opportunities": len(result.opportunity_map.opportunities),
        "source_metadata": len(result.source_metadata),
        "research_gaps": len(result.research_gaps),
        "human_selection": result.opportunity_map.human_selection is not None,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return output


def main() -> None:
    args = _parser().parse_args()
    asyncio.run(_run(args, get_settings()))


if __name__ == "__main__":
    main()
