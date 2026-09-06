import argparse
from datetime import UTC, datetime
from pathlib import Path

from app.modules.research.contracts import utc_now_iso
from app.modules.research.keyword_plan.artifact import (
    load_research_spike_for_opportunity_map,
    write_opportunity_map_artifacts,
)
from app.modules.research.keyword_plan.contracts import (
    MotguMaterial,
    NeedType,
    SignalScope,
    SignalSourceKind,
)
from app.modules.research.keyword_plan.normalize import make_observed_signal
from app.modules.research.keyword_plan.service import OpportunityMapRequest, OpportunityMapService

DEFAULT_NEED = "First-time art buyer worries about choosing the wrong painting."
DEFAULT_AUDIENCE = "International first-time art buyer visiting or preparing to visit Hanoi"
DEFAULT_SITUATION = "Interested in original art but uncertain how to choose a first painting"
DEFAULT_PILLAR = "How can a first-time buyer choose an original painting with confidence?"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CE01 Opportunity Map from a PR-B artifact")
    parser.add_argument("research_artifact", type=Path)
    parser.add_argument("--project-id", default="motgu")
    parser.add_argument("--locale", default="en")
    parser.add_argument("--audience-scope", default=DEFAULT_AUDIENCE)
    parser.add_argument("--reader", default=DEFAULT_AUDIENCE)
    parser.add_argument("--situation", default=DEFAULT_SITUATION)
    parser.add_argument("--need-statement", default=DEFAULT_NEED)
    parser.add_argument("--need-type", choices=[item.value for item in NeedType], default="pain")
    parser.add_argument("--pillar-question", default=DEFAULT_PILLAR)
    parser.add_argument(
        "--motgu-material",
        action="append",
        default=[],
        metavar="REF|KIND|DESCRIPTION",
        help="Approved/project-known MOTGU material; repeat as needed.",
    )
    parser.add_argument(
        "--market-observation",
        action="append",
        default=[],
        metavar="URL|OBSERVATION",
        help="Literal reviewed observation from an external market source.",
    )
    parser.add_argument(
        "--motgu-observation",
        action="append",
        default=[],
        metavar="LOCATOR|OBSERVATION",
        help="Reviewed MOTGU-direct observation; do not include unnecessary personal data.",
    )
    parser.add_argument("--select-opportunity")
    parser.add_argument("--selected-by")
    parser.add_argument("--selection-reason")
    parser.add_argument("--output-dir", type=Path, default=Path("../artifacts/research"))
    return parser.parse_args()


def _parse_material(raw: str) -> MotguMaterial:
    parts = [part.strip() for part in raw.split("|", 2)]
    if len(parts) != 3 or not all(parts):
        raise ValueError("motgu_material_must_be_REF|KIND|DESCRIPTION")
    return MotguMaterial(ref=parts[0], kind=parts[1], description=parts[2])


def _parse_observation(raw: str) -> tuple[str, str]:
    parts = [part.strip() for part in raw.split("|", 1)]
    if len(parts) != 2 or not all(parts):
        raise ValueError("observation_must_be_LOCATOR|OBSERVATION")
    return parts[0], parts[1]


def main() -> None:
    args = parse_args()
    research = load_research_spike_for_opportunity_map(args.research_artifact)
    captured_at = research.created_at or utc_now_iso()
    extra_signals = []
    for raw in args.market_observation:
        url, observation = _parse_observation(raw)
        extra_signals.append(
            make_observed_signal(
                source_kind=SignalSourceKind.MARKET,
                scope=SignalScope.MARKET_WEB,
                observed_text=observation,
                locale=args.locale,
                provider="manual_review",
                method="literal_market_observation",
                context="CE01 Opportunity Map manual market observation",
                captured_at=captured_at,
                source_url=url,
                artifact_ref=str(args.research_artifact),
                locator=url,
            )
        )
    for raw in args.motgu_observation:
        locator, observation = _parse_observation(raw)
        extra_signals.append(
            make_observed_signal(
                source_kind=SignalSourceKind.MOTGU,
                scope=SignalScope.MOTGU_DIRECT,
                observed_text=observation,
                locale=args.locale,
                provider="manual_review",
                method="reviewed_motgu_direct_observation",
                context="CE01 Opportunity Map reviewed MOTGU observation",
                captured_at=captured_at,
                external_id=locator,
                artifact_ref=str(args.research_artifact),
                locator=locator,
            )
        )

    request = OpportunityMapRequest(
        project_id=args.project_id,
        locale=args.locale,
        audience_scope=args.audience_scope,
        situation=args.situation,
        reader=args.reader,
        need_statement=args.need_statement,
        need_type=NeedType(args.need_type),
        artifact_ref=str(args.research_artifact),
        motgu_materials=tuple(_parse_material(raw) for raw in args.motgu_material),
        extra_signals=tuple(extra_signals),
        pillar_question=args.pillar_question,
    )
    service = OpportunityMapService()
    result = service.build(research, request)

    if args.select_opportunity:
        if not args.selected_by or not args.selection_reason:
            raise ValueError("selection_requires_selected_by_and_selection_reason")
        result = service.select(
            result,
            opportunity_id=args.select_opportunity,
            selected_by=args.selected_by,
            reason=args.selection_reason,
        )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    base = args.output_dir / f"ce01-opportunity-map-{stamp}"
    json_path, markdown_path = write_opportunity_map_artifacts(
        result,
        json_path=base.with_suffix(".json"),
        markdown_path=base.with_suffix(".md"),
    )
    print(f"json={json_path}")
    print(f"markdown={markdown_path}")
    print(f"signals={len(result.signals)}")
    print(f"questions={len(result.questions)}")
    print(f"clusters={len(result.clusters)}")
    print(f"opportunities={len(result.opportunities)}")
    print(f"hypothesis_status={result.need_hypothesis.status.value}")
    if result.human_selection:
        print(f"selected_opportunity={result.human_selection.opportunity_id}")


if __name__ == "__main__":
    main()
