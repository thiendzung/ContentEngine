# ruff: noqa: E402

import argparse
import asyncio
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.modules.content_engine.models import ContentCase, NeedHypothesis
from app.modules.harness.models import ContentRun
from app.modules.research.discovery.artifact import load_discovery_selection_snapshot
from app.modules.research.discovery.persistence import persist_discovery_selection
from app.modules.research.keyword_plan.service import OpportunityMapService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Persist one explicit human selection from a completed CE04 Discovery "
            "artifact without re-running research providers or creating ContentCase."
        )
    )
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--opportunity", required=True)
    parser.add_argument("--selected-by", required=True)
    parser.add_argument("--reason", required=True)
    return parser


async def _count_rows(session: object, model: type[object]) -> int:
    scalar = await session.scalar(select(func.count()).select_from(model))  # type: ignore[attr-defined]
    return int(scalar or 0)


async def _run(args: argparse.Namespace) -> None:
    artifact = Path(args.artifact)
    opportunity_id = str(args.opportunity)
    selected_by = str(args.selected_by)
    reason = str(args.reason)

    opportunity_map, planning_refs = load_discovery_selection_snapshot(
        artifact,
        opportunity_id=opportunity_id,
    )
    service = OpportunityMapService()
    service.select(
        opportunity_map,
        opportunity_id=opportunity_id,
        selected_by=selected_by,
        reason=reason,
    )

    async with SessionLocal() as session:
        content_cases_before = await _count_rows(session, ContentCase)
        content_runs_before = await _count_rows(session, ContentRun)

        selection_refs = await persist_discovery_selection(
            session,
            result=opportunity_map,
            planning_refs=planning_refs,
        )
        hypothesis = await session.get(
            NeedHypothesis,
            planning_refs.need_hypothesis_id,
        )
        if hypothesis is None:
            raise RuntimeError("persisted_need_hypothesis_not_found")
        if hypothesis.status != "PROPOSED":
            raise RuntimeError("human_selection_must_not_promote_need_hypothesis")

        content_cases_after = await _count_rows(session, ContentCase)
        content_runs_after = await _count_rows(session, ContentRun)
        if content_cases_after != content_cases_before:
            raise RuntimeError("human_selection_must_not_create_content_case")
        if content_runs_after != content_runs_before:
            raise RuntimeError("human_selection_must_not_create_content_run")

        await session.commit()

    summary = {
        "artifact": str(artifact),
        "planning_opportunity_id": opportunity_id,
        "persisted_content_opportunity_id": str(selection_refs.content_opportunity_id),
        "human_selection_id": str(selection_refs.human_selection_id),
        "content_experiment_id": str(selection_refs.content_experiment_id),
        "need_hypothesis_id": str(planning_refs.need_hypothesis_id),
        "need_hypothesis_status": "PROPOSED",
        "selected_by": selected_by,
        "content_case_count_before": content_cases_before,
        "content_case_count_after": content_cases_after,
        "content_run_count_before": content_runs_before,
        "content_run_count_after": content_runs_after,
        "providers_called": 0,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def main() -> None:
    args = _parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
