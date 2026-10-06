from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from app.modules.research.keyword_plan.content_architecture import (
    CONTENT_ARCHITECTURE_POLICY_VERSION,
    MIN_PILLAR_MEMBER_CLUSTERS,
    build_content_architecture_projection,
)


def _recommendation(
    *,
    cluster_key: str,
    answer_job: str,
    question: str,
    intent: str = "evaluate",
    audience_stage: str = "evaluating",
    decision: str = "CREATE",
    readiness: str = "READY_FOR_HUMAN_SELECTION",
    signal_suffix: str,
) -> dict[str, object]:
    return {
        "cluster_key": cluster_key,
        "intent": intent,
        "audience_stage": audience_stage,
        "answer_job": answer_job,
        "primary_question": question,
        "decision": decision,
        "priority": "NEXT" if decision != "DO_NOT_WRITE" else "NO",
        "selection_readiness": readiness,
        "existing_content_refs": [],
        "existing_plan_refs": [],
        "reason_codes": [],
        "dimensions": {
            "content_gap": {
                "status": "MISSING",
                "reason_codes": [],
            },
            "search_evidence": {
                "status": "REPEATED",
                "signal_count": 2,
                "question_count": 1,
                "signal_refs": [
                    f"00000000-0000-0000-0000-{signal_suffix}01",
                    f"00000000-0000-0000-0000-{signal_suffix}02",
                ],
            }
        },
    }


def _planner(
    *,
    need_id: str,
    locale: str,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "policy_version": "qm-opportunity-planner-v2.3",
        "project": {
            "id": "10000000-0000-0000-0000-000000000001",
            "slug": "motgu",
        },
        "need": {
            "id": need_id,
            "version": 1,
            "status": "PROPOSED",
            "type": "question",
            "statement": "Buy a first original artwork with confidence.",
            "audience_hypothesis_id": None,
        },
        "locale": locale,
        "question_coverage_snapshot_hash": "b" * 64,
        "recommendations": rows,
        "snapshot_hash": "a" * 64,
    }


def _coverage(
    *,
    need_id: str,
    locale: str,
    items: list[dict[str, object]] | None = None,
    opportunities: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "project": {
            "id": "10000000-0000-0000-0000-000000000001",
            "slug": "motgu",
            "name": "MOTGU",
        },
        "filters": {
            "locale": locale,
            "audience_id": None,
            "need_id": need_id,
        },
        "needs": [
            {
                "need": {
                    "id": need_id,
                    "type": "question",
                    "statement": "Buy a first original artwork with confidence.",
                    "status": "PROPOSED",
                    "audience_hypothesis_id": None,
                },
                "coverage_status": "MISSING",
                "reason_codes": [],
                "content_items": items or [],
                "selected_opportunities": opportunities or [],
                "duplicate_candidates": [],
                "invalid_update_target_refs": [],
            }
        ],
    }


def _canonical_rows() -> list[dict[str, object]]:
    return [
        _recommendation(
            cluster_key="authenticity",
            answer_job="verify_authenticity",
            question="How do I know if a painting is original?",
            intent="trust",
            signal_suffix="0000000001",
        ),
        _recommendation(
            cluster_key="questions-before-buying",
            answer_job="choose_with_confidence",
            question="What should I ask before buying my first artwork?",
            intent="evaluate",
            audience_stage="first_time_buyer",
            signal_suffix="0000000002",
        ),
        _recommendation(
            cluster_key="price-value",
            answer_job="understand_value",
            question="Why is original art expensive?",
            intent="understand",
            signal_suffix="0000000003",
        ),
        _recommendation(
            cluster_key="home-fit",
            answer_job="fit_space",
            question="How do I know if a painting fits my room?",
            signal_suffix="0000000004",
        ),
        _recommendation(
            cluster_key="take-home",
            answer_job="carry_home",
            question="Can I take a painting home on a flight?",
            intent="consider_purchase",
            signal_suffix="0000000005",
        ),
    ]


def test_content_architecture_is_deterministic_and_forms_one_pillar() -> None:
    need_id = str(uuid4())
    planner = _planner(
        need_id=need_id,
        locale="en",
        rows=_canonical_rows(),
    )
    coverage = _coverage(need_id=need_id, locale="en")

    first = build_content_architecture_projection(
        planner=planner,
        content_coverage=coverage,
    )
    second = build_content_architecture_projection(
        planner=deepcopy(planner),
        content_coverage=deepcopy(coverage),
    )

    assert first == second
    assert first["policy_version"] == CONTENT_ARCHITECTURE_POLICY_VERSION
    counts = first["counts"]
    assert isinstance(counts, dict)
    assert counts["cluster_candidates"] == 5
    assert counts["pillar_candidates"] == 1

    candidates = first["candidates"]
    assert isinstance(candidates, list)
    pillar = next(
        row
        for row in candidates
        if isinstance(row, dict) and row["role"] == "pillar"
    )
    assert pillar["decision"] == "CREATE"
    assert pillar["selectable"] is True
    assert pillar["member_cluster_keys"] == sorted(
        row["cluster_key"] for row in _canonical_rows()
    )
    assert len(pillar["member_clusters"]) == 5


def test_pillar_is_not_forced_when_breadth_is_insufficient() -> None:
    need_id = str(uuid4())
    rows = _canonical_rows()[: MIN_PILLAR_MEMBER_CLUSTERS - 1]

    payload = build_content_architecture_projection(
        planner=_planner(need_id=need_id, locale="en", rows=rows),
        content_coverage=_coverage(need_id=need_id, locale="en"),
    )

    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    assert all(
        isinstance(row, dict) and row["role"] == "cluster"
        for row in candidates
    )


def test_do_not_write_cluster_does_not_create_false_pillar_breadth() -> None:
    need_id = str(uuid4())
    rows = _canonical_rows()[:2]
    rows.append(
        _recommendation(
            cluster_key="off-scope",
            answer_job="learn_art_making",
            question="How do I mix oil paint?",
            decision="DO_NOT_WRITE",
            readiness="BLOCKED",
            signal_suffix="0000000006",
        )
    )

    payload = build_content_architecture_projection(
        planner=_planner(need_id=need_id, locale="en", rows=rows),
        content_coverage=_coverage(need_id=need_id, locale="en"),
    )

    counts = payload["counts"]
    assert isinstance(counts, dict)
    assert counts["pillar_candidates"] == 0


def test_existing_pillar_content_blocks_new_pillar_selection() -> None:
    need_id = str(uuid4())
    item_id = str(uuid4())
    payload = build_content_architecture_projection(
        planner=_planner(
            need_id=need_id,
            locale="en",
            rows=_canonical_rows(),
        ),
        content_coverage=_coverage(
            need_id=need_id,
            locale="en",
            items=[
                {
                    "id": item_id,
                    "locale": "en",
                    "content_role": "pillar",
                }
            ],
        ),
    )

    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    pillar = next(
        row
        for row in candidates
        if isinstance(row, dict) and row["role"] == "pillar"
    )
    assert pillar["decision"] == "DO_NOT_WRITE"
    assert pillar["selection_readiness"] == "BLOCKED"
    assert pillar["selectable"] is False
    assert pillar["existing_content_refs"] == [item_id]


def test_selected_pillar_plan_blocks_second_pillar_candidate() -> None:
    need_id = str(uuid4())
    plan_id = str(uuid4())
    payload = build_content_architecture_projection(
        planner=_planner(
            need_id=need_id,
            locale="en",
            rows=_canonical_rows(),
        ),
        content_coverage=_coverage(
            need_id=need_id,
            locale="en",
            opportunities=[
                {
                    "id": plan_id,
                    "locale": "en",
                    "decision": "CREATE",
                    "priority": "NEXT",
                    "suggested_role": "pillar",
                    "question": "Buy a first original artwork with confidence.",
                    "intent": "mixed",
                    "existing_content_refs": [],
                    "selection_refs": [],
                }
            ],
        ),
    )

    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    pillar = next(
        row
        for row in candidates
        if isinstance(row, dict) and row["role"] == "pillar"
    )
    assert pillar["decision"] == "DO_NOT_WRITE"
    assert pillar["selection_readiness"] == "BLOCKED"
    assert pillar["selectable"] is False
    assert pillar["existing_plan_refs"] == [plan_id]


def test_candidate_identity_is_locale_specific() -> None:
    need_id = str(uuid4())
    rows = _canonical_rows()

    english = build_content_architecture_projection(
        planner=_planner(need_id=need_id, locale="en", rows=rows),
        content_coverage=_coverage(need_id=need_id, locale="en"),
    )
    vietnamese = build_content_architecture_projection(
        planner=_planner(need_id=need_id, locale="vi", rows=rows),
        content_coverage=_coverage(need_id=need_id, locale="vi"),
    )

    en_candidates = english["candidates"]
    vi_candidates = vietnamese["candidates"]
    assert isinstance(en_candidates, list)
    assert isinstance(vi_candidates, list)
    assert {
        row["candidate_key"]
        for row in en_candidates
        if isinstance(row, dict)
    }.isdisjoint(
        {
            row["candidate_key"]
            for row in vi_candidates
            if isinstance(row, dict)
        }
    )
