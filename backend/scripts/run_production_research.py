import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.modules.content_engine.models import Project
from app.modules.harness.policy import BudgetLimits
from app.modules.research.artifact import write_production_research_artifact
from app.modules.research.contracts import ProductionResearchRequest, ResearchDepth
from app.modules.research.production import ResearchRouter
from app.modules.research.providers.exa import ExaProvider
from app.modules.research.providers.jina import JinaReader
from app.modules.research.providers.serper import SerperProvider
from app.modules.research.providers.tavily import TavilyProvider

DEFAULT_QUERY = "first-time art buyer understanding artwork price"


def _secret_value(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret is not None else None


def _default_output() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return repo_root / "artifacts" / "research" / f"ce04-production-research-{timestamp}.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CE04 production ResearchRouter.")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--locale", default="en")
    parser.add_argument("--country", default="us")
    parser.add_argument("--project", default="motgu")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--pages", type=int)
    parser.add_argument(
        "--depth",
        choices=[ResearchDepth.STANDARD.value, ResearchDepth.DEEP.value],
        default=ResearchDepth.STANDARD.value,
    )
    parser.add_argument("--output", type=Path)
    return parser


async def _run(args: argparse.Namespace, settings: Settings) -> Path:
    serper_key = _secret_value(settings.serper_api_key)
    if not serper_key:
        raise RuntimeError("SERPER_API_KEY is required for CE04 production research")

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
            result = await router.run(
                session,
                request=ProductionResearchRequest(
                    project_id=project.id,
                    query=cast(str, args.query),
                    locale=cast(str, args.locale),
                    country=cast(str, args.country),
                    limit=cast(int, args.limit),
                    depth=ResearchDepth(cast(str, args.depth)),
                    max_pages_to_read=(
                        settings.research_max_pages_read if pages is None else pages
                    ),
                ),
            )

    output = cast(Path | None, args.output) or _default_output()
    return write_production_research_artifact(result, output)


def main() -> None:
    args = _parser().parse_args()
    output = asyncio.run(_run(args, get_settings()))
    print(output)


if __name__ == "__main__":
    main()
