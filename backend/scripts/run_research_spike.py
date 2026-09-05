import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.modules.research.artifact import write_research_spike_artifact
from app.modules.research.budget import ResearchBudget
from app.modules.research.contracts import ManualDeepResearchImport
from app.modules.research.providers.exa import ExaProvider
from app.modules.research.providers.jina import JinaReader
from app.modules.research.providers.serper import SerperProvider
from app.modules.research.providers.tavily import TavilyProvider
from app.modules.research.spike import ResearchSpikeService, import_manual_deep_research

DEFAULT_SEED = "First-time art buyer worries about choosing the wrong painting."


def _secret_value(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret is not None else None


def _default_output() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return repo_root / "artifacts" / "research" / f"ce01-research-spike-{timestamp}.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CE01 Research/Search spike.")
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--locale", default="en")
    parser.add_argument("--country", default="us")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manual-report-file", type=Path)
    parser.add_argument("--manual-source-url", action="append", default=[])
    return parser


def _manual_import(args: argparse.Namespace) -> ManualDeepResearchImport | None:
    report_file = cast(Path | None, args.manual_report_file)
    source_urls = cast(list[str], args.manual_source_url)
    if report_file is None:
        if source_urls:
            raise ValueError("manual_report_file_required_when_source_urls_are_provided")
        return None
    report = report_file.read_text(encoding="utf-8")
    return import_manual_deep_research(report, source_urls)


async def _run(args: argparse.Namespace, settings: Settings) -> Path:
    serper_key = _secret_value(settings.serper_api_key)
    if not serper_key:
        raise RuntimeError("SERPER_API_KEY is required for the CE01 Research Spike")

    timeout = httpx.Timeout(settings.research_request_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        tavily_key = _secret_value(settings.tavily_api_key)
        exa_key = _secret_value(settings.exa_api_key)
        jina_key = _secret_value(settings.jina_api_key)

        service = ResearchSpikeService(
            serper=SerperProvider(
                serper_key,
                client,
                raw_excerpt_chars=settings.research_max_raw_excerpt_chars,
            ),
            tavily=(
                TavilyProvider(
                    tavily_key,
                    client,
                    raw_excerpt_chars=settings.research_max_raw_excerpt_chars,
                )
                if tavily_key
                else None
            ),
            exa=(
                ExaProvider(
                    exa_key,
                    client,
                    raw_excerpt_chars=settings.research_max_raw_excerpt_chars,
                )
                if exa_key
                else None
            ),
            reader=JinaReader(
                client,
                jina_key,
                raw_excerpt_chars=settings.research_max_raw_excerpt_chars,
            ),
            budget=ResearchBudget(
                max_provider_calls=settings.research_max_provider_calls,
                max_selected_urls=settings.research_max_selected_urls,
                max_pages_read=settings.research_max_pages_read,
                max_second_hop_candidates=settings.research_max_second_hop_candidates,
                max_raw_excerpt_chars=settings.research_max_raw_excerpt_chars,
            ),
        )
        result = await service.run(
            cast(str, args.seed),
            locale=cast(str, args.locale),
            country=cast(str, args.country),
            manual_deep_research=_manual_import(args),
        )

    output = cast(Path | None, args.output) or _default_output()
    return write_research_spike_artifact(result, output)


def main() -> None:
    args = _parser().parse_args()
    output = asyncio.run(_run(args, get_settings()))
    print(output)


if __name__ == "__main__":
    main()
