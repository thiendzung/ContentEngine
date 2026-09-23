# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.content_engine.models import Project
from app.modules.customer_intelligence.insights import InsightType
from app.modules.customer_intelligence.intake import (
    CustomerInsightCandidateInput,
    persist_customer_insight_candidate,
)
from app.modules.customer_intelligence.living_map import InsightNeedRelation

_INSIGHT_TYPES = (
    "job",
    "pain",
    "desire",
    "question",
    "fear",
    "objection",
    "barrier",
    "trigger",
    "decision_factor",
    "trust_builder",
    "trust_breaker",
    "language",
    "behaviour",
    "expectation",
    "post_purchase_need",
    "referral_trigger",
    "repeat_purchase_trigger",
)


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected UUID") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Persist one explicit CustomerInsight CANDIDATE from exact durable Signals. "
            "This command does not research, review, promote, or publish."
        )
    )
    parser.add_argument("--project", default="motgu")
    parser.add_argument("--insight-type", required=True, choices=_INSIGHT_TYPES)
    parser.add_argument("--statement", required=True)
    parser.add_argument("--situation")
    parser.add_argument("--audience-id", type=_uuid)
    parser.add_argument("--support-signal", action="append", type=_uuid, default=[])
    parser.add_argument("--contradict-signal", action="append", type=_uuid, default=[])
    parser.add_argument("--context-signal", action="append", type=_uuid, default=[])
    parser.add_argument("--alternative-explanation", action="append", default=[])
    parser.add_argument("--missing-evidence", action="append", default=[])
    parser.add_argument("--need-id", type=_uuid)
    parser.add_argument(
        "--need-relation",
        choices=("supports", "contradicts", "context"),
    )
    parser.add_argument("--linked-by")
    parser.add_argument("--link-reason")
    return parser


async def _run(args: argparse.Namespace) -> dict[str, object]:
    async with SessionLocal() as session:
        project = await session.scalar(
            select(Project).where(Project.slug == cast(str, args.project).strip())
        )
        if project is None:
            raise RuntimeError("customer_insight_intake_project_not_found")

        result = await persist_customer_insight_candidate(
            session,
            project_id=project.id,
            request=CustomerInsightCandidateInput(
                insight_type=cast(InsightType, args.insight_type),
                statement=cast(str, args.statement),
                situation=cast(str | None, args.situation),
                audience_hypothesis_id=cast(UUID | None, args.audience_id),
                support_signal_ids=tuple(cast(list[UUID], args.support_signal)),
                contradict_signal_ids=tuple(cast(list[UUID], args.contradict_signal)),
                context_signal_ids=tuple(cast(list[UUID], args.context_signal)),
                alternative_explanations=tuple(
                    cast(list[str], args.alternative_explanation)
                ),
                missing_evidence=tuple(cast(list[str], args.missing_evidence)),
                need_hypothesis_id=cast(UUID | None, args.need_id),
                need_relation=cast(InsightNeedRelation | None, args.need_relation),
                linked_by=cast(str | None, args.linked_by),
                link_reason=cast(str | None, args.link_reason),
            ),
        )
        await session.commit()
        return {
            "customer_insight_id": str(result.insight.id),
            "insight_key": result.insight.insight_key,
            "version": result.insight.version,
            "status": result.insight.status,
            "replayed": result.replayed,
            "linked_signal_ids": [
                str(signal_id) for signal_id in result.linked_signal_ids
            ],
            "need_linked": result.need_linked,
        }


def main() -> None:
    args = _parser().parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
