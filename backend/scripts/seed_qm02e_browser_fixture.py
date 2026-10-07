from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, make_url, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.content_engine.persistence import create_next_content_version
from app.modules.harness.models import ContentRun
from app.modules.research.keyword_plan.content_architecture import (
    build_content_architecture,
)

FIXTURE_VERSION = "qm02e-browser-v1"
SCENARIO_STATEMENTS = {
    "create": "[QM02E CREATE] Buyer needs a first-art budget decision.",
    "update": "[QM02E UPDATE] Buyer needs current first-art budget guidance.",
    "refresh": "[QM02E REFRESH] Buyer needs refreshed first-art budget guidance.",
    "merge": "[QM02E MERGE] Buyer needs one canonical first-art budget answer.",
}
EXPECTED_DECISIONS = {
    "create": "CREATE",
    "update": "UPDATE",
    "refresh": "REFRESH",
    "merge": "MERGE",
}


class Qm02eBrowserFixtureError(RuntimeError):
    """Raised when the dedicated browser fixture cannot be created safely."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed or mutate the dedicated QM-02E browser fixture"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("seed")
    drift = subparsers.add_parser("drift-target")
    drift.add_argument(
        "--scenario",
        choices=("update", "refresh", "merge"),
        required=True,
    )
    return parser.parse_args()


async def _require_test_database(session: AsyncSession) -> str:
    settings = get_settings()
    if settings.app_env.strip().lower() != "test":
        raise Qm02eBrowserFixtureError("qm02e_fixture_test_environment_required")

    target = make_url(settings.resolved_database_url)
    expected_name = target.database or ""
    if not expected_name or "test" not in expected_name.lower():
        raise Qm02eBrowserFixtureError("qm02e_fixture_unsafe_test_database")

    current_name = str(
        (await session.execute(text("select current_database()"))).scalar_one()
    )
    if current_name != expected_name:
        raise Qm02eBrowserFixtureError("qm02e_fixture_database_identity_mismatch")
    return current_name


async def _require_empty_fixture_state(session: AsyncSession) -> None:
    models = (
        NeedHypothesis,
        ContentOpportunity,
        ContentCase,
        ContentRun,
        HumanSelection,
    )
    for model in models:
        count = int(
            await session.scalar(select(func.count()).select_from(model)) or 0
        )
        if count != 0:
            raise Qm02eBrowserFixtureError(
                "qm02e_fixture_requires_reset_test_database"
            )


async def _project(session: AsyncSession) -> Project:
    existing = await session.scalar(select(Project).where(Project.slug == "motgu"))
    if existing is not None:
        return existing

    project = Project(
        slug="motgu",
        name="MOTGU",
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


async def _need(
    session: AsyncSession,
    *,
    project: Project,
    scenario: str,
) -> NeedHypothesis:
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement=SCENARIO_STATEMENTS[scenario],
        audience_scope="first-time art buyer",
        situation="considering a first original painting",
        origin="qm02e_browser_fixture",
        status="SUPPORTED",
        alternative_explanations_json=[],
        missing_evidence_json=[],
        version=1,
    )
    session.add(need)
    await session.flush()
    return need


async def _search_signal(
    session: AsyncSession,
    *,
    project: Project,
    need: NeedHypothesis,
    text_value: str,
) -> Signal:
    signal = Signal(
        project_id=project.id,
        source_kind="SEARCH",
        scope="market_web",
        observed_text=text_value,
        source_url=f"https://fixture.invalid/{uuid4().hex}",
        locale="en",
        context="QM-02E supported browser fixture",
        captured_at=datetime.now(UTC),
        fingerprint=uuid4().hex,
        independence_group=uuid4().hex,
        provenance_json={
            "provider": "fixture",
            "method": "people_also_ask",
            "question_eligible": True,
            "factual_evidence_eligible": False,
            "fixture_version": FIXTURE_VERSION,
        },
    )
    session.add(signal)
    await session.flush()
    session.add(
        NeedHypothesisSignal(
            need_hypothesis_id=need.id,
            signal_id=signal.id,
            relation="supports",
        )
    )
    await session.flush()
    return signal


async def _existing_target(
    session: AsyncSession,
    *,
    project: Project,
    need: NeedHypothesis,
    scenario: str,
    ordinal: int,
) -> ContentItem:
    source = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader=need.audience_scope,
        situation=need.situation,
        need=need.statement,
        question="How much should I spend on my first painting?",
        intent="evaluate",
        promise="Existing budget guidance.",
        coverage_requirements_json=[],
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Existing canonical fixture content.",
        next_discovery_step="None.",
        decision="CREATE",
        priority="NEXT",
        reasons_json=[f"{FIXTURE_VERSION}:{scenario}:source"],
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
    )
    session.add(source)
    await session.flush()

    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=source.id,
        desired_action="Keep first-art budget guidance useful.",
        content_hypothesis="Budget guidance helps the buyer decide.",
        originality_statement="QM-02E browser fixture.",
        reader_before="uncertain about budget",
        reader_after="has a practical budget frame",
        status="draft",
    )
    session.add(content_case)
    await session.flush()

    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="cluster",
        primary_question=source.question,
        primary_intent="evaluate",
        secondary_intent=None,
        primary_query=None,
        keyword_notes_json=[],
        emotion_arc_json=[],
        must_include_json=[],
        must_not_claim_json=[],
        status="draft",
    )
    session.add(variant)
    await session.flush()

    refresh = scenario == "refresh"
    item = ContentItem(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_type="journal",
        status="published" if refresh else "draft",
        canonical_key=(
            f"journal:qm02e:{scenario}:{ordinal}:{uuid4().hex[:12]}:en"
        ),
    )
    session.add(item)
    await session.flush()

    await create_next_content_version(
        session,
        content_item_id=item.id,
        change_reason="QM-02E fixture initial canonical answer.",
        content_json={
            "fixture": FIXTURE_VERSION,
            "scenario": scenario,
            "ordinal": ordinal,
            "body": "Existing first-art budget answer.",
        },
        status="published" if refresh else "draft",
    )
    if refresh:
        await create_next_content_version(
            session,
            content_item_id=item.id,
            change_reason="QM-02E fixture newer unpublished revision.",
            content_json={
                "fixture": FIXTURE_VERSION,
                "scenario": scenario,
                "ordinal": ordinal,
                "body": "Newer draft first-art budget answer.",
            },
            status="draft",
        )
    return item


async def _scenario(
    session: AsyncSession,
    *,
    project: Project,
    scenario: str,
) -> dict[str, object]:
    need = await _need(session, project=project, scenario=scenario)
    await _search_signal(
        session,
        project=project,
        need=need,
        text_value="How much should I spend on my first painting?",
    )
    await _search_signal(
        session,
        project=project,
        need=need,
        text_value="What budget should I set for my first painting?",
    )

    target_count = 0
    if scenario in {"update", "refresh"}:
        target_count = 1
    elif scenario == "merge":
        target_count = 2

    target_ids: list[str] = []
    for ordinal in range(1, target_count + 1):
        target = await _existing_target(
            session,
            project=project,
            need=need,
            scenario=scenario,
            ordinal=ordinal,
        )
        target_ids.append(str(target.id))

    architecture = await build_content_architecture(
        session,
        project_id=project.id,
        need_id=need.id,
        locale="en",
    )
    candidates = architecture.get("candidates")
    if not isinstance(candidates, list):
        raise Qm02eBrowserFixtureError("qm02e_fixture_architecture_invalid")

    expected_decision = EXPECTED_DECISIONS[scenario]
    matches = [
        row
        for row in candidates
        if isinstance(row, dict)
        and row.get("role") == "cluster"
        and row.get("decision") == expected_decision
    ]
    if len(matches) != 1:
        raise Qm02eBrowserFixtureError(
            f"qm02e_fixture_{scenario}_candidate_missing"
        )
    candidate = matches[0]
    if candidate.get("selection_readiness") != "READY_FOR_HUMAN_SELECTION":
        raise Qm02eBrowserFixtureError(
            f"qm02e_fixture_{scenario}_candidate_not_ready"
        )
    if sorted(str(value) for value in candidate.get("existing_content_refs", [])) != sorted(
        target_ids
    ):
        raise Qm02eBrowserFixtureError(
            f"qm02e_fixture_{scenario}_target_mismatch"
        )

    return {
        "scenario": scenario,
        "need_id": str(need.id),
        "need_statement": need.statement,
        "locale": "en",
        "expected_decision": expected_decision,
        "architecture_candidate_key": str(candidate["candidate_key"]),
        "architecture_snapshot_hash": str(architecture["snapshot_hash"]),
        "planner_snapshot_hash": str(architecture["planner_snapshot_hash"]),
        "target_content_item_ids": target_ids,
    }


async def seed_browser_fixture(session: AsyncSession) -> dict[str, object]:
    database_name = await _require_test_database(session)
    await _require_empty_fixture_state(session)
    project = await _project(session)

    scenarios = [
        await _scenario(session, project=project, scenario=scenario)
        for scenario in ("create", "update", "refresh", "merge")
    ]

    return {
        "schema_version": 1,
        "fixture_version": FIXTURE_VERSION,
        "database": database_name,
        "project": {
            "id": str(project.id),
            "slug": project.slug,
        },
        "scenarios": scenarios,
    }


async def drift_target(
    session: AsyncSession,
    *,
    scenario: str,
) -> dict[str, object]:
    database_name = await _require_test_database(session)
    statement = SCENARIO_STATEMENTS[scenario]
    need = await session.scalar(
        select(NeedHypothesis).where(NeedHypothesis.statement == statement)
    )
    if need is None:
        raise Qm02eBrowserFixtureError("qm02e_fixture_scenario_not_seeded")

    case_ids = list(
        (
            await session.scalars(
                select(ContentCase.id)
                .where(ContentCase.need_hypothesis_id == need.id)
                .order_by(ContentCase.id)
            )
        ).all()
    )
    if not case_ids:
        raise Qm02eBrowserFixtureError("qm02e_fixture_target_missing")

    target = await session.scalar(
        select(ContentItem)
        .where(ContentItem.content_case_id.in_(case_ids))
        .order_by(ContentItem.id)
    )
    if target is None:
        raise Qm02eBrowserFixtureError("qm02e_fixture_target_missing")

    version = await create_next_content_version(
        session,
        content_item_id=target.id,
        change_reason="QM-02E browser fixture target drift.",
        content_json={
            "fixture": FIXTURE_VERSION,
            "scenario": scenario,
            "drift": True,
        },
        status="draft",
    )
    return {
        "schema_version": 1,
        "fixture_version": FIXTURE_VERSION,
        "database": database_name,
        "scenario": scenario,
        "need_id": str(need.id),
        "content_item_id": str(target.id),
        "content_version_id": str(version.id),
        "content_version_no": version.version_no,
    }


async def _main() -> int:
    args = _parse_args()
    try:
        async with SessionLocal() as session:
            if args.command == "seed":
                result = await seed_browser_fixture(session)
            else:
                result = await drift_target(
                    session,
                    scenario=str(args.scenario),
                )
            await session.commit()
    except Qm02eBrowserFixtureError as exc:
        print(f"QM02E_BROWSER_FIXTURE: BLOCKED ({exc.code})")
        return 2
    except Exception:
        print("QM02E_BROWSER_FIXTURE: BLOCKED (unexpected_error)")
        return 2

    print(
        "QM02E_BROWSER_FIXTURE: READY "
        + json.dumps(result, sort_keys=True, separators=(",", ":"))
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
