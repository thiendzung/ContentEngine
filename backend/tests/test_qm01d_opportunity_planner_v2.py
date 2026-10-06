from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentOpportunity,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.harness.models import ModelCall, ToolCall
from app.modules.research.keyword_plan.opportunity_planner_v2 import (
    OpportunityPlannerError,
    build_opportunity_plan_v2,
    plan_opportunity_projection,
)
from app.modules.research.keyword_plan.router import get_opportunity_plan_v2


@asynccontextmanager
async def isolated_session():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


def _need(
    *,
    status: str = "SUPPORTED",
    project_id: UUID | None = None,
    need_id: UUID | None = None,
    missing_evidence: list[str] | None = None,
) -> NeedHypothesis:
    return NeedHypothesis(
        id=need_id or uuid4(),
        project_id=project_id or uuid4(),
        type="question",
        statement="Buyer needs budget clarity.",
        audience_scope="first-time buyer",
        situation="considering an artwork",
        origin="customer_intelligence",
        status=status,
        alternative_explanations_json=[],
        missing_evidence_json=missing_evidence or [],
        version=2,
    )


def _motgu_signal(
    *,
    project_id: UUID,
    signal_id: UUID | None = None,
) -> Signal:
    return Signal(
        id=signal_id or uuid4(),
        project_id=project_id,
        source_kind="MOTGU",
        scope="motgu_direct",
        observed_text="Reviewed visitor question about choosing artwork.",
        source_url=None,
        locale="en",
        context="reviewed first-party planning signal",
        captured_at=datetime.now(UTC),
        fingerprint=uuid4().hex,
        independence_group=uuid4().hex,
        provenance_json={
            "provider": "manual_review",
            "method": "reviewed_motgu_direct_observation",
        },
    )


def _coverage_item(
    item_id: str,
    *,
    need_role: str = "primary",
) -> dict[str, object]:
    return {
        "id": item_id,
        "canonical_key": f"journal:{item_id}",
        "content_case_id": f"case-{item_id}",
        "need_role": need_role,
        "locale": "en",
        "content_role": "cluster",
        "primary_question": "What budget should I set for a painting?",
        "primary_intent": "evaluate",
        "latest_version": None,
        "latest_published_version": None,
        "publication": None,
        "stale": False,
        "stale_reason_codes": [],
    }


def _coverage_plan(plan_id: str) -> dict[str, object]:
    return {
        "id": plan_id,
        "locale": "en",
        "decision": "CREATE",
        "priority": "NEXT",
        "question": "What budget should I set for a painting?",
        "intent": "evaluate",
        "existing_content_refs": [],
    }


def _question_coverage(
    *,
    need: NeedHypothesis,
    coverage_status: str = "MISSING",
    content_refs: tuple[str, ...] = (),
    supporting_refs: tuple[str, ...] = (),
    plan_refs: tuple[str, ...] = (),
    do_not_write_refs: tuple[str, ...] = (),
    unresolved: bool = False,
    search_signal_count: int = 2,
) -> dict[str, object]:
    items = [_coverage_item(item_id) for item_id in content_refs]
    items.extend(
        _coverage_item(item_id, need_role="supporting")
        for item_id in supporting_refs
    )
    plans = [_coverage_plan(plan_id) for plan_id in plan_refs]
    return {
        "schema_version": 1,
        "project": {
            "id": str(need.project_id),
            "slug": "motgu",
        },
        "need": {
            "id": str(need.id),
            "version": need.version,
            "status": need.status,
            "type": need.type,
            "statement": need.statement,
            "audience_hypothesis_id": None,
        },
        "locale": "en",
        "snapshot_hash": "a" * 64,
        "clusters": [
            {
                "cluster_key": "cluster-budget",
                "intent": "evaluate",
                "audience_stage": "evaluating",
                "answer_job": "plan_budget",
                "primary_question_key": "question-budget",
                "primary_question": "How much should I spend on art?",
                "question_keys": ["question-budget"],
                "signal_refs": [
                    f"search-{index}"
                    for index in range(search_signal_count)
                ],
                "topic_keys": ["price"],
                "question_count": 1,
                "coverage": {
                    "status": coverage_status,
                    "reason_codes": [f"coverage:{coverage_status}"],
                    "matched_content_items": items,
                    "matched_selected_opportunities": plans,
                    "unresolved_candidates": (
                        [
                            {
                                "kind": "content_item",
                                "id": "unresolved-item",
                                "reason": "candidate_semantics_unresolved",
                            }
                        ]
                        if unresolved
                        else []
                    ),
                    "do_not_write_opportunity_refs": list(do_not_write_refs),
                },
            }
        ],
    }


def _plan(
    *,
    need: NeedHypothesis,
    coverage_status: str = "MISSING",
    content_refs: tuple[str, ...] = (),
    supporting_refs: tuple[str, ...] = (),
    plan_refs: tuple[str, ...] = (),
    do_not_write_refs: tuple[str, ...] = (),
    motgu: bool = False,
    unresolved: bool = False,
    search_signal_count: int = 2,
) -> dict[str, object]:
    signals = [_motgu_signal(project_id=need.project_id)] if motgu else []
    return plan_opportunity_projection(
        question_coverage=_question_coverage(
            need=need,
            coverage_status=coverage_status,
            content_refs=content_refs,
            supporting_refs=supporting_refs,
            plan_refs=plan_refs,
            do_not_write_refs=do_not_write_refs,
            unresolved=unresolved,
            search_signal_count=search_signal_count,
        ),
        need=need,
        supporting_motgu_signals=signals,
        support_refs=[],
        contradiction_refs=[],
    )


def _recommendation(plan: dict[str, object]) -> dict[str, object]:
    rows = plan["recommendations"]
    assert isinstance(rows, list)
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, dict)
    return row


def test_first_party_signal_does_not_claim_right_to_win_or_create_now() -> None:
    need = _need()
    plan = _plan(need=need, motgu=True)
    row = _recommendation(plan)

    assert row["decision"] == "CREATE"
    assert row["priority"] == "NEXT"
    assert row["selection_readiness"] == "READY_FOR_HUMAN_SELECTION"
    assert plan["right_to_win"]["status"] == "UNPROVEN_FIRST_PARTY_SIGNAL"
    assert plan["right_to_win"]["right_to_win_proven"] is False
    assert plan["right_to_win"]["planning_signal_available"] is True
    assert plan["semantics"]["does_not_authorize_drafting"] is True


def test_missing_without_right_to_win_stays_create_but_lower_priority() -> None:
    need = _need()
    row = _recommendation(
        _plan(
            need=need,
            motgu=False,
            search_signal_count=1,
        )
    )

    assert row["decision"] == "CREATE"
    assert row["priority"] == "LATER"


def test_answered_without_new_first_party_value_is_link_only() -> None:
    row = _recommendation(
        _plan(
            need=_need(),
            coverage_status="ANSWERED",
            content_refs=("item-1",),
        )
    )

    assert row["decision"] == "LINK_ONLY"
    assert row["existing_content_refs"] == ["item-1"]
    assert row["priority"] == "NEXT"


def test_answered_first_party_signal_alone_does_not_force_update() -> None:
    row = _recommendation(
        _plan(
            need=_need(),
            coverage_status="ANSWERED",
            content_refs=("item-1",),
            motgu=True,
        )
    )

    assert row["decision"] == "LINK_ONLY"
    assert row["existing_content_refs"] == ["item-1"]


def test_stale_maps_to_refresh_with_explicit_target() -> None:
    row = _recommendation(
        _plan(
            need=_need(),
            coverage_status="STALE",
            content_refs=("item-1",),
        )
    )

    assert row["decision"] == "REFRESH"
    assert row["existing_content_refs"] == ["item-1"]


def test_partial_content_maps_to_update_and_plan_only_reuses_create_direction() -> None:
    content = _recommendation(
        _plan(
            need=_need(),
            coverage_status="PARTIAL",
            content_refs=("item-1",),
        )
    )
    plan_only = _recommendation(
        _plan(
            need=_need(),
            coverage_status="PARTIAL",
            plan_refs=("plan-1",),
        )
    )

    assert content["decision"] == "UPDATE"
    assert content["existing_content_refs"] == ["item-1"]
    assert plan_only["decision"] == "CREATE"
    assert plan_only["existing_plan_refs"] == ["plan-1"]
    assert plan_only["selection_readiness"] == "REUSE_EXISTING_PLAN"
    assert plan_only["priority"] == "NEXT"


def test_supporting_only_partial_does_not_become_update_target() -> None:
    row = _recommendation(
        _plan(
            need=_need(),
            coverage_status="PARTIAL",
            supporting_refs=("support-item",),
        )
    )

    assert row["decision"] == "CREATE"
    assert row["existing_content_refs"] == []
    assert row["coverage_refs"]["all_matched_content_items"] == [
        "support-item"
    ]


def test_selected_do_not_write_plan_blocks_new_create_recommendation() -> None:
    row = _recommendation(
        _plan(
            need=_need(),
            coverage_status="MISSING",
            do_not_write_refs=("plan-no",),
        )
    )

    assert row["decision"] == "DO_NOT_WRITE"
    assert row["selection_readiness"] == "BLOCKED"
    assert row["priority"] == "NO"
    assert row["existing_plan_refs"] == ["plan-no"]


def test_collision_with_content_maps_to_merge() -> None:
    row = _recommendation(
        _plan(
            need=_need(),
            coverage_status="COLLISION",
            content_refs=("item-1", "item-2"),
        )
    )

    assert row["decision"] == "MERGE"
    assert row["existing_content_refs"] == ["item-1", "item-2"]


def test_plan_only_collision_blocks_another_create_plan() -> None:
    row = _recommendation(
        _plan(
            need=_need(),
            coverage_status="COLLISION",
            plan_refs=("plan-1", "plan-2"),
        )
    )

    assert row["decision"] == "CREATE"
    assert row["selection_readiness"] == "BLOCKED"
    assert row["priority"] == "NO"
    assert "duplicate_selected_plans_require_reconciliation" in row["reason_codes"]


def test_insufficient_coverage_fails_closed_as_do_not_write_now() -> None:
    row = _recommendation(
        _plan(
            need=_need(),
            coverage_status="INSUFFICIENT_DATA",
            unresolved=True,
        )
    )

    assert row["decision"] == "DO_NOT_WRITE"
    assert row["selection_readiness"] == "RESEARCH_REQUIRED"
    assert row["priority"] == "NO"


def test_rejected_need_overrides_gap_and_is_do_not_write() -> None:
    need = _need(status="REJECTED")
    row = _recommendation(_plan(need=need, motgu=True))

    assert row["decision"] == "DO_NOT_WRITE"
    assert row["priority"] == "NO"
    assert row["selection_readiness"] == "BLOCKED"


def test_proposed_need_can_be_content_ready_without_truth_promotion() -> None:
    need = _need(
        status="PROPOSED",
        missing_evidence=["review direct buyer evidence"],
    )
    plan = _plan(need=need, motgu=True)
    row = _recommendation(plan)

    assert row["decision"] == "CREATE"
    assert row["selection_readiness"] == "READY_FOR_HUMAN_SELECTION"
    assert row["content_readiness"]["status"] == "READY_FOR_HUMAN_SELECTION"
    assert row["priority"] == "NEXT"
    assert plan["customer_truth"]["status"] == "PROPOSED"
    assert plan["customer_truth"]["separate_from_content_readiness"] is True
    assert plan["evidence_readiness"]["status"] == "RESEARCH_REQUIRED"
    assert plan["evidence_readiness"]["known_gaps"] == [
        "review direct buyer evidence"
    ]


def test_testing_need_can_be_content_ready_when_planning_gates_pass() -> None:
    need = _need(status="TESTING")
    plan = _plan(need=need)
    row = _recommendation(plan)

    assert row["decision"] == "CREATE"
    assert row["selection_readiness"] == "READY_FOR_HUMAN_SELECTION"
    assert row["priority"] == "NEXT"
    assert plan["customer_truth"]["status"] == "TESTING"


def test_insufficient_evidence_need_requires_research_even_with_search_gap() -> None:
    need = _need(status="INSUFFICIENT_EVIDENCE")
    plan = _plan(need=need)
    row = _recommendation(plan)

    assert row["decision"] == "CREATE"
    assert row["selection_readiness"] == "RESEARCH_REQUIRED"
    assert row["priority"] == "LATER"
    assert "canonical_need_evidence_insufficient" in row["reason_codes"]


def test_missing_search_lineage_requires_research_even_for_supported_need() -> None:
    row = _recommendation(
        _plan(
            need=_need(status="SUPPORTED"),
            search_signal_count=0,
        )
    )

    assert row["decision"] == "CREATE"
    assert row["selection_readiness"] == "RESEARCH_REQUIRED"
    assert row["priority"] == "LATER"
    assert "search_lineage_missing" in row["reason_codes"]


def test_unusable_cluster_requires_research() -> None:
    need = _need(status="PROPOSED")
    coverage = _question_coverage(need=need)
    clusters = coverage["clusters"]
    assert isinstance(clusters, list)
    cluster = clusters[0]
    assert isinstance(cluster, dict)
    cluster["primary_question"] = ""

    plan = plan_opportunity_projection(
        question_coverage=coverage,
        need=need,
        supporting_motgu_signals=[],
        support_refs=[],
        contradiction_refs=[],
    )
    row = _recommendation(plan)

    assert row["selection_readiness"] == "RESEARCH_REQUIRED"
    assert "question_cluster_not_usable" in row["reason_codes"]


def test_projection_exposes_seven_dimensions_without_synthetic_score() -> None:
    row = _recommendation(_plan(need=_need(), motgu=True))
    dimensions = row["dimensions"]

    assert set(dimensions) == {
        "audience_fit",
        "problem_strength",
        "search_evidence",
        "content_gap",
        "motgu_right_to_win",
        "business_connection",
        "evidence_readiness",
    }
    assert "score" not in row
    assert dimensions["business_connection"]["status"] == "DERIVED_UNBOUND"
    assert dimensions["motgu_right_to_win"]["limitations"] == [
        "First-party signals support planning relevance only.",
        "They do not prove a MOTGU Right-to-Win.",
        "They are not a locked EvidenceSet.",
        "They are not an approved OriginalityPack.",
    ]


def test_right_to_win_filters_first_party_signals_by_locale() -> None:
    need = _need()
    en_signal = _motgu_signal(project_id=need.project_id)
    vi_signal = _motgu_signal(project_id=need.project_id)
    vi_signal.locale = "vi"

    plan = plan_opportunity_projection(
        question_coverage=_question_coverage(need=need),
        need=need,
        supporting_motgu_signals=[en_signal, vi_signal],
        support_refs=[str(en_signal.id), str(vi_signal.id)],
        contradiction_refs=[],
    )

    right_to_win = plan["right_to_win"]
    assert right_to_win["signal_refs"] == [str(en_signal.id)]
    assert right_to_win["locale"] == "en"
    assert right_to_win["right_to_win_proven"] is False


def test_projection_fails_closed_on_upstream_identity_and_hash_mismatch() -> None:
    need = _need()
    coverage = _question_coverage(need=need)

    wrong_project = dict(coverage)
    wrong_project["project"] = {"id": str(uuid4()), "slug": "foreign"}
    with pytest.raises(
        OpportunityPlannerError,
        match="opportunity_planner_project_mismatch",
    ):
        plan_opportunity_projection(
            question_coverage=wrong_project,
            need=need,
            supporting_motgu_signals=[],
            support_refs=[],
            contradiction_refs=[],
        )

    bad_hash = dict(coverage)
    bad_hash["snapshot_hash"] = "bad"
    with pytest.raises(
        OpportunityPlannerError,
        match="opportunity_planner_question_coverage_hash_invalid",
    ):
        plan_opportunity_projection(
            question_coverage=bad_hash,
            need=need,
            supporting_motgu_signals=[],
            support_refs=[],
            contradiction_refs=[],
        )

    bad_locale = dict(coverage)
    bad_locale["locale"] = ""
    with pytest.raises(
        OpportunityPlannerError,
        match="opportunity_planner_locale_invalid",
    ):
        plan_opportunity_projection(
            question_coverage=bad_locale,
            need=need,
            supporting_motgu_signals=[],
            support_refs=[],
            contradiction_refs=[],
        )

    foreign_signal = _motgu_signal(project_id=uuid4())
    with pytest.raises(
        OpportunityPlannerError,
        match="opportunity_planner_right_to_win_signal_invalid",
    ):
        plan_opportunity_projection(
            question_coverage=coverage,
            need=need,
            supporting_motgu_signals=[foreign_signal],
            support_refs=[str(foreign_signal.id)],
            contradiction_refs=[],
        )


async def _db_project(session: AsyncSession) -> Project:
    project = Project(
        slug=f"qm01d-{uuid4().hex[:8]}",
        name="QM-01D",
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


async def _db_need(
    session: AsyncSession,
    project: Project,
) -> NeedHypothesis:
    need = _need(project_id=project.id)
    session.add(need)
    await session.flush()
    return need


async def _db_signal(
    session: AsyncSession,
    project: Project,
    need: NeedHypothesis,
    *,
    text: str,
    source_kind: str,
    scope: str,
    relation: str = "supports",
) -> Signal:
    signal = Signal(
        project_id=project.id,
        source_kind=source_kind,
        scope=scope,
        observed_text=text,
        source_url=None,
        locale="en",
        context="QM-01D route fixture",
        captured_at=datetime.now(UTC),
        fingerprint=uuid4().hex,
        independence_group=uuid4().hex,
        provenance_json={
            "provider": "fixture",
            "method": (
                "people_also_ask"
                if source_kind == "SEARCH"
                else "reviewed_motgu_direct_observation"
            ),
        },
    )
    session.add(signal)
    await session.flush()
    session.add(
        NeedHypothesisSignal(
            need_hypothesis_id=need.id,
            signal_id=signal.id,
            relation=relation,
        )
    )
    await session.flush()
    return signal


@pytest.mark.asyncio
async def test_opportunity_planner_route_is_read_only_and_uses_only_supporting_motgu() -> None:
    async with isolated_session() as session:
        project = await _db_project(session)
        need = await _db_need(session, project)
        await _db_signal(
            session,
            project,
            need,
            text="How much should I spend on art?",
            source_kind="SEARCH",
            scope="market_web",
        )
        await _db_signal(
            session,
            project,
            need,
            text="What budget should I set for my first painting?",
            source_kind="SEARCH",
            scope="market_web",
        )
        motgu = await _db_signal(
            session,
            project,
            need,
            text="Reviewed visitor asks how to choose within a budget.",
            source_kind="MOTGU",
            scope="motgu_direct",
        )
        conflicted = await _db_signal(
            session,
            project,
            need,
            text="One reviewed observation has conflicting relation labels.",
            source_kind="MOTGU",
            scope="motgu_direct",
        )
        session.add(
            NeedHypothesisSignal(
                need_hypothesis_id=need.id,
                signal_id=conflicted.id,
                relation="contradicts",
            )
        )
        await session.flush()
        contradiction = await _db_signal(
            session,
            project,
            need,
            text="A different visitor says budget is not a concern.",
            source_kind="MOTGU",
            scope="motgu_direct",
            relation="contradicts",
        )

        before = (
            await session.scalar(select(func.count()).select_from(NeedHypothesis)),
            await session.scalar(select(func.count()).select_from(Signal)),
            await session.scalar(
                select(func.count()).select_from(NeedHypothesisSignal)
            ),
            await session.scalar(
                select(func.count()).select_from(ContentOpportunity)
            ),
            await session.scalar(select(func.count()).select_from(ModelCall)),
            await session.scalar(select(func.count()).select_from(ToolCall)),
        )

        payload = await get_opportunity_plan_v2(
            need_id=need.id,
            locale="en",
            project_slug=project.slug,
            session=session,
        )
        replay = await build_opportunity_plan_v2(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="EN",
        )

        assert payload == replay
        recommendations = payload["recommendations"]
        assert isinstance(recommendations, list)
        assert len(recommendations) == 2
        assert all(
            isinstance(row, dict)
            and row["decision"] == "CREATE"
            and row["priority"] == "LATER"
            for row in recommendations
        )
        assert {
            row["audience_stage"]
            for row in recommendations
            if isinstance(row, dict)
        } == {"evaluating", "first_time_buyer"}
        assert {
            row["answer_job"]
            for row in recommendations
            if isinstance(row, dict)
        } == {"plan_budget"}
        assert payload["right_to_win"]["right_to_win_proven"] is False
        assert str(motgu.id) in payload["right_to_win"]["signal_refs"]
        assert str(conflicted.id) not in payload["right_to_win"]["signal_refs"]
        assert str(conflicted.id) in (
            payload["need_signal_state"]["support_signal_refs"]
        )
        assert str(conflicted.id) in (
            payload["need_signal_state"]["contradiction_signal_refs"]
        )
        assert str(contradiction.id) not in payload["right_to_win"]["signal_refs"]
        assert str(contradiction.id) in (
            payload["need_signal_state"]["contradiction_signal_refs"]
        )

        after = (
            await session.scalar(select(func.count()).select_from(NeedHypothesis)),
            await session.scalar(select(func.count()).select_from(Signal)),
            await session.scalar(
                select(func.count()).select_from(NeedHypothesisSignal)
            ),
            await session.scalar(
                select(func.count()).select_from(ContentOpportunity)
            ),
            await session.scalar(select(func.count()).select_from(ModelCall)),
            await session.scalar(select(func.count()).select_from(ToolCall)),
        )
        assert after == before
