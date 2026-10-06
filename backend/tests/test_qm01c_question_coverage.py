from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    LocaleVariant,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.research.keyword_plan.classification_v2 import (
    CLASSIFIER_VERSION,
)
from app.modules.research.keyword_plan.clustering_v2 import CLUSTERING_VERSION
from app.modules.research.keyword_plan.question_coverage import (
    build_question_coverage,
    join_question_map_with_coverage,
)
from app.modules.research.keyword_plan.router import get_question_coverage


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


def _question_map_fixture() -> dict[str, object]:
    return {
        "schema_version": 2,
        "project": {"id": "project-1", "slug": "motgu"},
        "need": {
            "id": "need-1",
            "version": 1,
            "status": "SUPPORTED",
            "type": "question",
            "statement": "Buyer needs budget clarity.",
            "audience_hypothesis_id": None,
        },
        "locale": "en",
        "snapshot_hash": "q" * 64,
        "source_policy": {
            "classifier_version": CLASSIFIER_VERSION,
            "clustering_version": CLUSTERING_VERSION,
        },
        "clusters": [
            {
                "cluster_key": "cluster-budget",
                "intent": "evaluate",
                "audience_stage": "evaluating",
                "answer_job": "plan_budget",
                "primary_question_key": "question-budget",
                "primary_question": "How much should I spend on art?",
                "question_keys": ["question-budget"],
                "signal_refs": ["signal-1"],
                "topic_keys": ["price"],
                "question_count": 1,
            }
        ],
    }


def _coverage_fixture(
    *,
    items: list[dict[str, object]] | None = None,
    opportunities: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "project": {"id": "project-1", "slug": "motgu", "name": "MOTGU"},
        "needs": [
            {
                "need": {"id": "need-1"},
                "coverage_status": "MISSING",
                "reason_codes": [],
                "content_items": items or [],
                "selected_opportunities": opportunities or [],
                "duplicate_candidates": [],
                "invalid_update_target_refs": [],
            }
        ],
    }


def _version(version_no: int, status: str) -> dict[str, object]:
    return {
        "id": f"version-{version_no}",
        "version_no": version_no,
        "status": status,
        "created_at": "2026-10-05T00:00:00+00:00",
    }


def _item(
    *,
    item_id: str,
    need_role: str = "primary",
    question: str = "What budget should I set for a painting?",
    intent: str = "evaluate",
    published: bool = False,
    newer_draft: bool = False,
    locale: str = "en",
) -> dict[str, object]:
    published_version = _version(1, "published") if published else None
    latest = (
        _version(2, "draft")
        if newer_draft
        else published_version or _version(1, "draft")
    )
    return {
        "id": item_id,
        "canonical_key": f"journal:{item_id}",
        "content_case_id": f"case-{item_id}",
        "need_role": need_role,
        "locale": locale,
        "content_role": "cluster",
        "primary_question": question,
        "primary_intent": intent,
        "item_status": "draft",
        "latest_version": latest,
        "latest_published_version": published_version,
        "publication": None,
    }


def _opportunity(
    *,
    opportunity_id: str,
    decision: str = "CREATE",
    question: str = "What budget should I set for a painting?",
    intent: str = "evaluate",
    refs: list[str] | None = None,
    locale: str = "en",
) -> dict[str, object]:
    return {
        "id": opportunity_id,
        "locale": locale,
        "decision": decision,
        "priority": "NEXT",
        "question": question,
        "intent": intent,
        "existing_content_refs": refs or [],
    }


def _status(result: dict[str, object]) -> str:
    clusters = result["clusters"]
    assert isinstance(clusters, list)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert isinstance(cluster, dict)
    coverage = cluster["coverage"]
    assert isinstance(coverage, dict)
    status = coverage["status"]
    assert isinstance(status, str)
    return status


def test_question_coverage_fails_closed_on_projection_contract_mismatch() -> None:
    question_map = _question_map_fixture()
    coverage = _coverage_fixture()

    bad_schema = dict(question_map)
    bad_schema["schema_version"] = 999
    with pytest.raises(
        ValueError,
        match="question_coverage_question_map_schema_unsupported",
    ):
        join_question_map_with_coverage(
            question_map=bad_schema,
            content_coverage=coverage,
        )

    bad_project = _coverage_fixture()
    bad_project["project"] = {
        "id": "foreign-project",
        "slug": "foreign",
        "name": "Foreign",
    }
    with pytest.raises(
        ValueError,
        match="question_coverage_project_mismatch",
    ):
        join_question_map_with_coverage(
            question_map=question_map,
            content_coverage=bad_project,
        )

    bad_hash = _question_map_fixture()
    bad_hash["snapshot_hash"] = "not-a-hash"
    with pytest.raises(
        ValueError,
        match="question_coverage_question_map_hash_invalid",
    ):
        join_question_map_with_coverage(
            question_map=bad_hash,
            content_coverage=coverage,
        )

    stale_clustering = _question_map_fixture()
    source_policy = stale_clustering["source_policy"]
    assert isinstance(source_policy, dict)
    source_policy["clustering_version"] = "question-map-clustering-v2"
    with pytest.raises(
        ValueError,
        match="question_coverage_clustering_version_mismatch",
    ):
        join_question_map_with_coverage(
            question_map=stale_clustering,
            content_coverage=coverage,
        )


def test_question_coverage_answered_requires_primary_published_match() -> None:
    result = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            items=[_item(item_id="item-1", published=True)]
        ),
    )

    assert _status(result) == "ANSWERED"
    assert result["counts"]["ANSWERED"] == 1


def test_question_coverage_stale_when_matching_published_item_has_newer_revision() -> None:
    result = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            items=[
                _item(
                    item_id="item-1",
                    published=True,
                    newer_draft=True,
                )
            ]
        ),
    )

    assert _status(result) == "STALE"


def test_question_coverage_stale_when_selected_update_targets_match() -> None:
    result = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            items=[_item(item_id="item-1", published=True)],
            opportunities=[
                _opportunity(
                    opportunity_id="op-update",
                    decision="UPDATE",
                    refs=["item-1"],
                )
            ],
        ),
    )

    assert _status(result) == "STALE"


def test_question_coverage_fails_closed_when_update_target_misses_cluster_item() -> None:
    result = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            opportunities=[
                _opportunity(
                    opportunity_id="op-update",
                    decision="UPDATE",
                    refs=["missing-item"],
                )
            ],
        ),
    )

    assert _status(result) == "INSUFFICIENT_DATA"


def test_question_coverage_collision_for_multiple_primary_matches() -> None:
    result = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            items=[
                _item(item_id="item-1", published=True),
                _item(
                    item_id="item-2",
                    question="How much should I spend on my first painting?",
                ),
            ]
        ),
    )

    assert _status(result) == "COLLISION"


def test_question_coverage_partial_for_unpublished_or_supporting_match() -> None:
    draft = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            items=[_item(item_id="draft-item")]
        ),
    )
    supporting = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            items=[
                _item(
                    item_id="support-item",
                    need_role="supporting",
                    published=True,
                )
            ]
        ),
    )

    assert _status(draft) == "PARTIAL"
    assert _status(supporting) == "PARTIAL"


def test_question_coverage_selected_create_plan_is_partial_and_duplicate_plans_collide() -> None:
    one_plan = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            opportunities=[_opportunity(opportunity_id="op-1")]
        ),
    )
    duplicate_plans = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            opportunities=[
                _opportunity(opportunity_id="op-1"),
                _opportunity(
                    opportunity_id="op-2",
                    question="How much should I spend on art?",
                ),
            ]
        ),
    )

    assert _status(one_plan) == "PARTIAL"
    assert _status(duplicate_plans) == "COLLISION"


def test_question_coverage_missing_when_no_matching_candidate_exists() -> None:
    result = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            items=[
                _item(
                    item_id="trust-item",
                    question="How can I verify an original painting?",
                    intent="trust",
                    published=True,
                )
            ]
        ),
    )

    assert _status(result) == "MISSING"


def test_question_coverage_fails_closed_on_stored_vs_derived_intent_conflict() -> None:
    result = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            items=[
                _item(
                    item_id="conflict-item",
                    question="What budget should I set for a painting?",
                    intent="learn",
                )
            ]
        ),
    )

    assert _status(result) == "INSUFFICIENT_DATA"


def test_question_coverage_fails_closed_when_same_intent_candidate_is_unresolved() -> None:
    result = join_question_map_with_coverage(
        question_map=_question_map_fixture(),
        content_coverage=_coverage_fixture(
            items=[
                _item(
                    item_id="unknown-item",
                    question="beautiful paintings ideas",
                    intent="evaluate",
                )
            ]
        ),
    )

    assert _status(result) == "INSUFFICIENT_DATA"


def test_question_coverage_ignores_other_locale_and_hash_is_deterministic() -> None:
    question_map = _question_map_fixture()
    coverage = _coverage_fixture(
        items=[
            _item(
                item_id="vi-item",
                published=True,
                locale="vi",
            )
        ]
    )

    first = join_question_map_with_coverage(
        question_map=question_map,
        content_coverage=coverage,
    )
    replay = join_question_map_with_coverage(
        question_map=question_map,
        content_coverage=coverage,
    )

    assert first == replay
    assert _status(first) == "MISSING"
    assert len(str(first["snapshot_hash"])) == 64


async def _project(session: AsyncSession) -> Project:
    project = Project(
        slug=f"qm01c-{uuid4().hex[:8]}",
        name="QM-01C",
        default_locale="en",
    )
    session.add(project)
    await session.flush()
    return project


async def _need(session: AsyncSession, project: Project) -> NeedHypothesis:
    need = NeedHypothesis(
        project_id=project.id,
        type="question",
        statement="Buyer needs budget clarity.",
        audience_scope="first-time buyer",
        situation="considering an artwork",
        origin="customer_intelligence",
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
    project: Project,
    need: NeedHypothesis,
) -> None:
    signal = Signal(
        project_id=project.id,
        source_kind="SEARCH",
        scope="market_web",
        observed_text="How much should I spend on art?",
        source_url="https://example.com/qm01c",
        locale="en",
        context="QM-01C fixture",
        captured_at=datetime.now(UTC),
        fingerprint=uuid4().hex,
        provenance_json={"provider": "fixture", "method": "people_also_ask"},
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


async def _published_content(
    session: AsyncSession,
    project: Project,
    need: NeedHypothesis,
) -> None:
    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader="first-time buyer",
        situation=need.situation,
        need=need.statement,
        question="What budget should I set for a painting?",
        intent="evaluate",
        promise="Help the reader plan a budget.",
        motgu_material_refs_json=[],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Bounded QM-01C fixture.",
        next_discovery_step="None",
        decision="CREATE",
        priority="NEXT",
        reasons_json=["fixture"],
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
    )
    session.add(opportunity)
    await session.flush()

    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="read",
        content_hypothesis="Useful budget guidance improves confidence.",
        originality_statement="Fixture originality statement.",
        reader_before="uncertain",
        reader_after="better informed",
        status="draft",
    )
    session.add(content_case)
    await session.flush()

    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="cluster",
        primary_question="What budget should I set for a painting?",
        primary_intent="evaluate",
        status="draft",
    )
    session.add(variant)
    await session.flush()

    item = ContentItem(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_type="journal",
        status="published",
        canonical_key=f"journal:{content_case.id}:en",
    )
    session.add(item)
    await session.flush()

    session.add(
        ContentVersion(
            content_item_id=item.id,
            version_no=1,
            change_reason="QM-01C fixture",
            status="published",
            content_json={"title": "Budget guide"},
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_question_coverage_route_is_read_only_and_uses_canonical_sources() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project)
        await _search_signal(session, project, need)
        await _published_content(session, project, need)

        before = (
            await session.scalar(select(func.count()).select_from(NeedHypothesis)),
            await session.scalar(select(func.count()).select_from(Signal)),
            await session.scalar(
                select(func.count()).select_from(NeedHypothesisSignal)
            ),
            await session.scalar(select(func.count()).select_from(ContentItem)),
            await session.scalar(
                select(func.count()).select_from(ContentVersion)
            ),
        )

        payload = await get_question_coverage(
            need_id=need.id,
            locale="en",
            project_slug=project.slug,
            session=session,
        )

        assert payload["schema_version"] == 1
        assert payload["question_map_snapshot_hash"]
        assert _status(payload) == "ANSWERED"
        assert payload["semantics"]["read_only_join"] is True

        after = (
            await session.scalar(select(func.count()).select_from(NeedHypothesis)),
            await session.scalar(select(func.count()).select_from(Signal)),
            await session.scalar(
                select(func.count()).select_from(NeedHypothesisSignal)
            ),
            await session.scalar(select(func.count()).select_from(ContentItem)),
            await session.scalar(
                select(func.count()).select_from(ContentVersion)
            ),
        )
        assert after == before


@pytest.mark.asyncio
async def test_question_coverage_builder_matches_route_projection() -> None:
    async with isolated_session() as session:
        project = await _project(session)
        need = await _need(session, project)
        await _search_signal(session, project, need)

        payload = await build_question_coverage(
            session,
            project_id=project.id,
            need_id=need.id,
            locale="en",
        )

        assert _status(payload) == "MISSING"
        assert payload["counts"]["MISSING"] == 1
