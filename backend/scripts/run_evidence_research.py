# ruff: noqa: E402

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
from app.modules.research.contracts import ProductionResearchRequest, ResearchDepth
from app.modules.research.evidence import EvidenceResearchRequest, EvidenceResearchWorkflow
from app.modules.research.evidence.artifact import write_evidence_workflow_artifact
from app.modules.research.production import ProductionSufficiencyPolicy, ResearchRouter
from app.modules.research.providers.exa import ExaProvider
from app.modules.research.providers.jina import JinaReader
from app.modules.research.providers.serper import SerperProvider
from app.modules.research.providers.tavily import TavilyProvider

DEFAULT_QUERY = "How do I know if an original artwork is fairly priced?"
DEFAULT_OPPORTUNITY_ID = "068991ab-de34-4787-9c38-8935c3f0e2da"
DEFAULT_NEED_ID = "530bdd27-f008-4910-9b3b-df83e007cfa2"


def _secret_value(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret is not None else None


def _default_output() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return repo_root / "artifacts" / "research" / f"ce04-evidence-research-v1-{timestamp}.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run CE04 Evidence Research for one human-selected ContentOpportunity."
    )
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--opportunity-id", default=DEFAULT_OPPORTUNITY_ID)
    parser.add_argument("--need-id", default=DEFAULT_NEED_ID)
    parser.add_argument("--locale", default="en")
    parser.add_argument("--country", default="us")
    parser.add_argument("--project", default="motgu")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--pages", type=int)
    parser.add_argument("--max-claims", type=int, default=8)
    parser.add_argument("--lock-by")
    parser.add_argument("--output", type=Path)
    return parser


async def _run(args: argparse.Namespace, settings: Settings) -> Path:
    serper_key = _secret_value(settings.serper_api_key)
    if not serper_key:
        raise RuntimeError("SERPER_API_KEY is required for CE04 Evidence Research")

    output = cast(Path | None, args.output) or _default_output()
    timeout = httpx.Timeout(settings.research_request_timeout_seconds)
    async with SessionLocal() as session:
        project = (
            await session.execute(
                select(Project).where(Project.slug == cast(str, args.project))
            )
        ).scalar_one_or_none()
        if project is None:
            raise RuntimeError(f"project_not_found:{args.project}")

        opportunity_id = UUID(cast(str, args.opportunity_id))
        need_id = UUID(cast(str, args.need_id))
        need = await session.get(NeedHypothesis, need_id)
        if need is None:
            raise RuntimeError(f"need_hypothesis_not_found:{need_id}")
        if need.status != "PROPOSED":
            raise RuntimeError(f"need_hypothesis_status_must_remain_PROPOSED:{need.status}")

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
                # Evidence Research still checks internal knowledge first, but cannot stop
                # there because external claims require successfully read source content.
                sufficiency=ProductionSufficiencyPolicy(min_internal_hits=1_000_000),
            )
            pages = cast(int | None, args.pages)
            lock_by = cast(str | None, args.lock_by)
            workflow = EvidenceResearchWorkflow(router=router)
            result = await workflow.run(
                session,
                request=EvidenceResearchRequest(
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
                    content_opportunity_id=opportunity_id,
                    need_hypothesis_id=need_id,
                    max_claims=cast(int, args.max_claims),
                    lock_evidence_set=lock_by is not None,
                    locked_by=lock_by,
                ),
            )

        write_evidence_workflow_artifact(result, output)
        await session.commit()

    summary = {
        "artifact": str(output),
        "artifact_type": result.artifact_type,
        "schema_version": 1,
        "evidence_eligible": result.evidence_eligible,
        "research_stop_reason": result.research.stop_reason,
        "research_sufficient": result.research.sufficient,
        "external_provider_calls": result.research.external_provider_calls,
        "content_case_id": str(result.content_case_id),
        "source_documents": len(result.source_document_ids),
        "claims": len(result.claim_ids),
        "evidence": len(result.evidence_ids),
        "relation_counts": result.relation_counts,
        "evidence_set_id": (
            str(result.evidence_set_id) if result.evidence_set_id is not None else None
        ),
        "evidence_set_version": result.evidence_set_version,
        "evidence_set_status": result.evidence_set_status,
        "originality_pack_id": (
            str(result.originality_pack_id) if result.originality_pack_id is not None else None
        ),
        "originality_item_count": result.originality_item_count,
        "research_gaps": len(result.research_gaps),
        "need_hypothesis_status": need.status,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return output


def main() -> None:
    args = _parser().parse_args()
    asyncio.run(_run(args, get_settings()))


if __name__ == "__main__":
    main()
