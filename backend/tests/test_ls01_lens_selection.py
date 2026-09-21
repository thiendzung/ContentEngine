from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_angle_approval import _bundle_fixture

from app.core.database import engine
from app.modules.content_engine.journal import angle as angle_module
from app.modules.content_engine.journal.angle import load_journal_input_bundle
from app.modules.content_engine.lens_selection import (
    LENS_ORDER,
    LensSelectionError,
    build_lens_candidate_payload,
    lens_selection_angle_context,
    lens_selection_evidence_context,
    persist_lens_candidates,
    persist_lens_selection,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentItem,
    ContentOpportunity,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    SettingsSnapshot,
    SettingsVersion,
    Signal,
)
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ModelCall,
    StepRun,
    ToolCall,
)
from app.modules.system.settings_service import create_settings_snapshot


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


async def _signal(
    session: AsyncSession,
    *,
    project_id: UUID,
    text: str,
) -> Signal:
    row = Signal(
        project_id=project_id,
        source_kind="MARKET",
        scope="market_web",
        observed_text=text,
        source_url=f"https://example.com/{uuid4().hex}",
        locale="en",
        context="LS-01 fixture",
        captured_at=datetime.now(UTC),
        fingerprint=uuid4().hex,
        provenance_json={"provider": "fixture", "method": "test"},
    )
    session.add(row)
    await session.flush()
    return row


async def _fixture(
    session: AsyncSession,
    *,
    guard_config: dict[str, object] | None = None,
) -> tuple[
    Project,
    NeedHypothesis,
    ContentOpportunity,
    ContentCase,
    LocaleVariant,
    ContentRun,
]:
    project = Project(
        slug=f"ls01-{uuid4().hex[:8]}",
        name="LS-01",
        default_locale="en",
    )
    session.add(project)
    await session.flush()

    need = NeedHypothesis(
        project_id=project.id,
        audience_hypothesis_id=None,
        type="question",
        statement="How can a first-time buyer evaluate authenticity?",
        audience_scope="first-time buyer",
        situation="considering an original painting",
        origin="research",
        status="SUPPORTED",
        alternative_explanations_json=[],
        missing_evidence_json=[],
        version=1,
    )
    session.add(need)
    await session.flush()

    support = await _signal(
        session,
        project_id=project.id,
        text="Buyers ask how authenticity can be checked.",
    )
    contradiction = await _signal(
        session,
        project_id=project.id,
        text="Some buyers assume a signature alone proves authenticity.",
    )
    session.add_all(
        [
            NeedHypothesisSignal(
                need_hypothesis_id=need.id,
                signal_id=support.id,
                relation="supports",
            ),
            NeedHypothesisSignal(
                need_hypothesis_id=need.id,
                signal_id=contradiction.id,
                relation="contradicts",
            ),
        ]
    )
    await session.flush()

    opportunity = ContentOpportunity(
        project_id=project.id,
        need_hypothesis_id=need.id,
        locale="en",
        reader="first-time art buyer",
        situation="considering an original painting",
        need=need.statement,
        question="How should I evaluate authenticity before buying?",
        intent="evaluate",
        promise="Leave with grounded checks and questions.",
        motgu_material_refs_json=["motgu:method:authenticity-check"],
        material_gaps_json=[],
        existing_content_refs_json=[],
        what_is_actually_new="Connect customer doubt to practical checks.",
        next_discovery_step="Verify factual authenticity criteria.",
        decision="CREATE",
        priority="NOW",
        reasons_json=["documented buyer question"],
        suggested_content_type="journal",
        suggested_role="cluster",
        version=1,
        selected_by="founder",
        selected_at=datetime.now(UTC),
        selection_reason="Use this Need for LS-01.",
    )
    session.add(opportunity)
    await session.flush()
    human_selection = HumanSelection(
        content_opportunity_id=opportunity.id,
        selected_by="founder",
        reason="Use this Need for LS-01.",
        selected_at=opportunity.selected_at,
    )
    session.add(human_selection)
    await session.flush()

    content_case = ContentCase(
        project_id=project.id,
        content_type="journal",
        audience_hypothesis_id=None,
        need_hypothesis_id=need.id,
        content_opportunity_id=opportunity.id,
        desired_action="read",
        content_hypothesis="A grounded lens helps the reader decide.",
        originality_statement="Use MOTGU material without invented facts.",
        reader_before="uncertain",
        reader_after="able to ask better questions",
        status="draft",
    )
    session.add(content_case)
    await session.flush()

    variant = LocaleVariant(
        content_case_id=content_case.id,
        locale="en",
        content_role="cluster",
        primary_question=opportunity.question,
        primary_intent=opportunity.intent,
        status="draft",
    )
    session.add(variant)
    await session.flush()

    settings: dict[str, object] = {}
    refs: list[str] = []
    if guard_config is not None:
        settings = {"lens_selection": guard_config}
        version = SettingsVersion(
            project_id=project.id,
            scope_type="project",
            scope_key=project.slug,
            version=1,
            settings_json=settings,
            status="active",
            change_reason="LS-01 guard fixture",
            approved_by="founder",
        )
        session.add(version)
        await session.flush()
        refs = [f"settings_version:{version.id}:v{version.version}"]

    snapshot = await create_settings_snapshot(
        session,
        project_id=project.id,
        resolved_settings=settings,
        source_version_refs=refs,
    )
    run = ContentRun(
        project_id=project.id,
        content_case_id=content_case.id,
        locale_variant_id=variant.id,
        content_item_id=None,
        run_mode="create",
        status="running",
        current_step="lens_selection",
        settings_snapshot_id=snapshot.id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    return project, need, opportunity, content_case, variant, run


def _decisions(
    *,
    primary: str | None,
    merged: tuple[str, ...] = (),
) -> list[dict[str, object]]:
    return [
        {
            "lens": lens,
            "decision": (
                "SELECT"
                if lens == primary
                else "MERGE"
                if lens in merged
                else "HOLD"
            ),
            **(
                {"merge_into": primary}
                if lens in merged
                else {}
            ),
        }
        for lens in LENS_ORDER
    ]


def _candidate(
    payload: dict[str, object],
    lens: str,
) -> dict[str, object]:
    rows = payload["candidates"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        if row["lens"] == lens:
            return row
    raise AssertionError(f"missing lens {lens}")


@pytest.mark.asyncio
async def test_candidates_are_exactly_seven_and_do_not_run_ai() -> None:
    async with isolated_session() as session:
        _project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        before = (
            await session.scalar(select(func.count()).select_from(ModelCall)),
            await session.scalar(select(func.count()).select_from(ToolCall)),
        )

        first = await persist_lens_candidates(
            session,
            run_id=run.id,
        )
        replay = await persist_lens_candidates(
            session,
            run_id=run.id,
        )

        assert first.artifact.id == replay.artifact.id
        rows = first.payload["candidates"]
        assert isinstance(rows, list)
        assert [row["lens"] for row in rows] == list(LENS_ORDER)
        assert len(rows) == 7
        assert _candidate(first.payload, "DEFINITION")["eligible"] is True
        assert _candidate(first.payload, "MISCONCEPTION")["eligible"] is False
        assert _candidate(first.payload, "SIGNALS")["eligible"] is True
        assert _candidate(first.payload, "METHOD")["eligible"] is True
        assert _candidate(first.payload, "CAUSES")["eligible"] is False
        assert _candidate(first.payload, "CASE")["eligible"] is False
        assert _candidate(first.payload, "POV")["eligible"] is False

        after = (
            await session.scalar(select(func.count()).select_from(ModelCall)),
            await session.scalar(select(func.count()).select_from(ToolCall)),
        )
        assert after == before


@pytest.mark.asyncio
async def test_guarded_lenses_require_approved_guard_sources() -> None:
    async with isolated_session() as session:
        config = {
            "misconceptions": [
                {
                    "ref": "misconception:signature",
                    "need_hypothesis_id": None,
                    "statement": "A signature alone proves authenticity.",
                    "observation_ref": "signal:observed-belief-1",
                    "approval_ref": "approval:misconception:1",
                }
            ],
            "case_materials": [
                {
                    "ref": "case:authenticity-visit",
                    "need_hypothesis_id": None,
                    "summary": "Real customer authenticity consultation.",
                    "provenance_ref": "provenance:case-1",
                    "rights_ref": "rights:case-1",
                }
            ],
            "pov_positions": [
                {
                    "ref": "pov:authenticity",
                    "need_hypothesis_id": None,
                    "statement": "Authenticity should be checked through traceable facts.",
                    "approval_ref": "approval:pov:1",
                }
            ],
            "causal_evidence": [
                {
                    "ref": "causal:trust",
                    "need_hypothesis_id": None,
                    "statement": "Approved causal statement for fixture only.",
                    "source_ref": "evidence:causal:1",
                    "approval_ref": "approval:causal:1",
                }
            ],
        }
        _project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session, guard_config=config)
        )
        payload = await build_lens_candidate_payload(
            session,
            run_id=run.id,
        )

        for lens in ("MISCONCEPTION", "CASE", "POV", "CAUSES"):
            assert _candidate(payload, lens)["eligible"] is True

        pov = _candidate(payload, "POV")
        pov_context = pov["authority_context"]
        assert isinstance(pov_context, list)
        assert pov_context == [
            {
                "kind": "approved_motgu_position",
                "statement": (
                    "Authenticity should be checked through traceable facts."
                ),
                "approval_ref": "approval:pov:1",
            }
        ]

        candidates = await persist_lens_candidates(
            session,
            run_id=run.id,
        )
        await persist_lens_selection(
            session,
            candidate_artifact_id=candidates.artifact.id,
            decisions=_decisions(primary="POV"),
            selected_by="founder",
            reason="Use the explicitly approved MOTGU position.",
        )
        angle_context = await lens_selection_angle_context(
            session,
            run_id=run.id,
        )
        assert angle_context is not None
        authority = angle_context["authority"]
        assert isinstance(authority, list)
        assert authority[0]["lens"] == "POV"
        assert authority[0]["authority_context"] == pov_context


@pytest.mark.asyncio
async def test_malformed_settings_version_provenance_fails_closed() -> None:
    async with isolated_session() as session:
        config = {
            "pov_positions": [
                {
                    "ref": "pov:authenticity",
                    "need_hypothesis_id": None,
                    "statement": (
                        "Authenticity should be checked through traceable facts."
                    ),
                    "approval_ref": "approval:pov:1",
                }
            ]
        }
        project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session, guard_config=config)
        )
        current_snapshot = await session.get(
            SettingsSnapshot,
            run.settings_snapshot_id,
        )
        assert current_snapshot is not None
        valid_refs = list(current_snapshot.source_version_refs_json)
        assert len(valid_refs) == 1

        malformed_snapshot = await create_settings_snapshot(
            session,
            project_id=project.id,
            resolved_settings={"lens_selection": config},
            source_version_refs=[
                valid_refs[0],
                "settings_version:fake:v1",
            ],
        )
        run.settings_snapshot_id = malformed_snapshot.id
        await session.flush()

        with pytest.raises(
            LensSelectionError,
            match="lens_settings_source_ref_invalid",
        ):
            await build_lens_candidate_payload(
                session,
                run_id=run.id,
            )


@pytest.mark.asyncio
async def test_run_override_cannot_self_approve_lens_guards() -> None:
    async with isolated_session() as session:
        project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        settings = {
            "lens_selection": {
                "pov_positions": [
                    {
                        "ref": "pov:fake",
                        "need_hypothesis_id": None,
                        "statement": "Unapproved position.",
                        "approval_ref": "run-override:self",
                    }
                ]
            }
        }
        snapshot = await create_settings_snapshot(
            session,
            project_id=project.id,
            resolved_settings=settings,
            source_version_refs=["run_override:fake"],
        )
        run.settings_snapshot_id = snapshot.id
        await session.flush()

        with pytest.raises(
            LensSelectionError,
            match="lens_guard_config_approved_source_required",
        ):
            await build_lens_candidate_payload(
                session,
                run_id=run.id,
            )


@pytest.mark.asyncio
async def test_selection_has_one_primary_and_merges_do_not_create_articles() -> None:
    async with isolated_session() as session:
        _project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        candidates = await persist_lens_candidates(
            session,
            run_id=run.id,
        )
        cases_before = await session.scalar(
            select(func.count()).select_from(ContentCase)
        )
        items_before = await session.scalar(
            select(func.count()).select_from(ContentItem)
        )

        selected = await persist_lens_selection(
            session,
            candidate_artifact_id=candidates.artifact.id,
            decisions=_decisions(
                primary="SIGNALS",
                merged=("METHOD",),
            ),
            selected_by="founder",
            reason="Use observed signals with MOTGU's practical method.",
        )
        replay = await persist_lens_selection(
            session,
            candidate_artifact_id=candidates.artifact.id,
            decisions=_decisions(
                primary="SIGNALS",
                merged=("METHOD",),
            ),
            selected_by="founder",
            reason="Use observed signals with MOTGU's practical method.",
        )

        assert replay.artifact.id == selected.artifact.id
        assert selected.payload["primary_lens"] == "SIGNALS"
        assert selected.payload["merged_lenses"] == ["METHOD"]
        contract = selected.payload["one_article_contract"]
        assert isinstance(contract, dict)
        assert contract["primary_lens_count"] == 1
        assert contract["merged_lenses_are_not_separate_articles"] is True

        cases_after = await session.scalar(
            select(func.count()).select_from(ContentCase)
        )
        items_after = await session.scalar(
            select(func.count()).select_from(ContentItem)
        )
        assert cases_after == cases_before
        assert items_after == items_before

        angle_context = await lens_selection_angle_context(
            session,
            run_id=run.id,
        )
        evidence_context = await lens_selection_evidence_context(
            session,
            run_id=run.id,
        )
        assert angle_context is not None
        assert evidence_context is not None
        assert angle_context["primary_lens"] == "SIGNALS"
        assert angle_context["supporting_lenses"] == ["METHOD"]


@pytest.mark.asyncio
async def test_blocked_candidate_cannot_be_selected_or_merged() -> None:
    async with isolated_session() as session:
        _project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        candidates = await persist_lens_candidates(
            session,
            run_id=run.id,
        )

        with pytest.raises(
            LensSelectionError,
            match="lens_ineligible_candidate_activated",
        ):
            await persist_lens_selection(
                session,
                candidate_artifact_id=candidates.artifact.id,
                decisions=_decisions(primary="CASE"),
                selected_by="founder",
                reason="Must not bypass CASE provenance/rights.",
            )


@pytest.mark.asyncio
async def test_merge_requires_one_selected_primary() -> None:
    async with isolated_session() as session:
        _project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        candidates = await persist_lens_candidates(
            session,
            run_id=run.id,
        )
        decisions = _decisions(primary=None)
        for row in decisions:
            if row["lens"] == "METHOD":
                row["decision"] = "MERGE"
                row["merge_into"] = "SIGNALS"

        with pytest.raises(
            LensSelectionError,
            match="lens_merge_requires_primary",
        ):
            await persist_lens_selection(
                session,
                candidate_artifact_id=candidates.artifact.id,
                decisions=decisions,
                selected_by="founder",
                reason="Invalid merge without a primary.",
            )


@pytest.mark.asyncio
async def test_all_hold_is_valid_but_cannot_feed_angle() -> None:
    async with isolated_session() as session:
        _project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        candidates = await persist_lens_candidates(
            session,
            run_id=run.id,
        )
        await persist_lens_selection(
            session,
            candidate_artifact_id=candidates.artifact.id,
            decisions=_decisions(primary=None),
            selected_by="founder",
            reason="Evidence is not sufficient to select a lens yet.",
        )

        evidence_context = await lens_selection_evidence_context(
            session,
            run_id=run.id,
        )
        assert evidence_context is not None
        assert evidence_context["active_lenses"] == []
        assert evidence_context["held_lenses"] == list(LENS_ORDER)
        held_requirements = evidence_context["held_requirements"]
        assert isinstance(held_requirements, list)
        assert len(held_requirements) == 7
        assert {row["lens"] for row in held_requirements} == set(LENS_ORDER)
        with pytest.raises(
            LensSelectionError,
            match="lens_selection_no_active_lens",
        ):
            await lens_selection_angle_context(
                session,
                run_id=run.id,
            )


@pytest.mark.asyncio
async def test_candidate_becomes_stale_when_customer_evidence_changes() -> None:
    async with isolated_session() as session:
        project, need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        candidates = await persist_lens_candidates(
            session,
            run_id=run.id,
        )
        new_signal = await _signal(
            session,
            project_id=project.id,
            text="Another independent buyer asks about authenticity.",
        )
        session.add(
            NeedHypothesisSignal(
                need_hypothesis_id=need.id,
                signal_id=new_signal.id,
                relation="supports",
            )
        )
        await session.flush()

        with pytest.raises(
            LensSelectionError,
            match="lens_candidate_artifact_stale",
        ):
            await persist_lens_selection(
                session,
                candidate_artifact_id=candidates.artifact.id,
                decisions=_decisions(primary="SIGNALS"),
                selected_by="founder",
                reason="Stale candidate must not cross selection.",
            )


@pytest.mark.asyncio
async def test_changed_selection_creates_new_version_not_history_rewrite() -> None:
    async with isolated_session() as session:
        _project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        candidates = await persist_lens_candidates(
            session,
            run_id=run.id,
        )
        first = await persist_lens_selection(
            session,
            candidate_artifact_id=candidates.artifact.id,
            decisions=_decisions(primary="SIGNALS"),
            selected_by="founder",
            reason="First reviewed choice.",
        )
        second = await persist_lens_selection(
            session,
            candidate_artifact_id=candidates.artifact.id,
            decisions=_decisions(primary="DEFINITION"),
            selected_by="founder",
            reason="Second reviewed choice.",
        )

        assert first.artifact.id != second.artifact.id
        assert first.artifact.version == 1
        assert second.artifact.version == 2
        assert first.payload["primary_lens"] == "SIGNALS"
        assert second.payload["primary_lens"] == "DEFINITION"


@pytest.mark.asyncio
async def test_unrelated_retired_settings_ref_does_not_block_lens() -> None:
    async with isolated_session() as session:
        project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        unrelated = SettingsVersion(
            project_id=project.id,
            scope_type="project",
            scope_key=project.slug,
            version=9,
            settings_json={"unrelated_feature": {"enabled": True}},
            status="retired",
            change_reason="Unrelated historical setting.",
            approved_by=None,
        )
        session.add(unrelated)
        await session.flush()
        snapshot = await create_settings_snapshot(
            session,
            project_id=project.id,
            resolved_settings={"unrelated_feature": {"enabled": True}},
            source_version_refs=[
                f"settings_version:{unrelated.id}:v{unrelated.version}"
            ],
        )
        run.settings_snapshot_id = snapshot.id
        await session.flush()

        payload = await build_lens_candidate_payload(
            session,
            run_id=run.id,
        )
        assert len(payload["candidates"]) == 7


@pytest.mark.asyncio
async def test_opportunity_requires_matching_durable_human_selection() -> None:
    async with isolated_session() as session:
        _project, _need, opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        selection = await session.scalar(
            select(HumanSelection).where(
                HumanSelection.content_opportunity_id == opportunity.id
            )
        )
        assert selection is not None
        selection.reason = "Changed durable selection reason."
        await session.flush()

        with pytest.raises(
            LensSelectionError,
            match="lens_opportunity_human_selection_mismatch",
        ):
            await build_lens_candidate_payload(
                session,
                run_id=run.id,
            )


@pytest.mark.asyncio
async def test_contradicting_signal_alone_does_not_prove_misconception() -> None:
    async with isolated_session() as session:
        _project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        payload = await build_lens_candidate_payload(
            session,
            run_id=run.id,
        )
        misconception = _candidate(payload, "MISCONCEPTION")
        assert misconception["eligible"] is False
        guards = misconception["guards"]
        assert isinstance(guards, list)
        assert guards[0]["key"] == "misconception_observed"
        assert guards[0]["status"] == "BLOCK"


@pytest.mark.asyncio
async def test_lens_artifacts_are_bound_to_step_outputs() -> None:
    async with isolated_session() as session:
        _project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        step = StepRun(
            run_id=run.id,
            step_key="lens_selection",
            attempt=1,
            status="running",
            input_artifact_refs_json=[],
            output_artifact_refs_json=[],
            started_at=datetime.now(UTC),
        )
        session.add(step)
        await session.flush()

        candidates = await persist_lens_candidates(
            session,
            run_id=run.id,
            step_run_id=step.id,
        )
        selection = await persist_lens_selection(
            session,
            candidate_artifact_id=candidates.artifact.id,
            decisions=_decisions(primary="SIGNALS"),
            selected_by="founder",
            reason="Bind exact LS-01 outputs to the step.",
        )
        await session.refresh(step)

        assert str(candidates.artifact.id) in step.output_artifact_refs_json
        assert str(selection.artifact.id) in step.output_artifact_refs_json

        retry_step = StepRun(
            run_id=run.id,
            step_key="lens_selection",
            attempt=2,
            status="running",
            input_artifact_refs_json=[],
            output_artifact_refs_json=[],
            started_at=datetime.now(UTC),
        )
        session.add(retry_step)
        await session.flush()
        retry_candidates = await persist_lens_candidates(
            session,
            run_id=run.id,
            step_run_id=retry_step.id,
        )
        assert retry_candidates.artifact.id != candidates.artifact.id
        assert retry_candidates.artifact.version == (
            candidates.artifact.version + 1
        )
        assert retry_candidates.payload["run_ref"]["step_run_id"] == str(
            retry_step.id
        )


@pytest.mark.asyncio
async def test_forged_selection_payload_fails_semantic_revalidation() -> None:
    async with isolated_session() as session:
        _project, _need, _opportunity, _case, _variant, run = (
            await _fixture(session)
        )
        candidates = await persist_lens_candidates(
            session,
            run_id=run.id,
        )
        valid = await persist_lens_selection(
            session,
            candidate_artifact_id=candidates.artifact.id,
            decisions=_decisions(primary="SIGNALS"),
            selected_by="founder",
            reason="Valid selection before direct-insert attack fixture.",
        )
        forged = json.loads(json.dumps(valid.payload))
        angle_context = forged["angle_context"]
        assert isinstance(angle_context, dict)
        angle_context["source_refs"] = ["forged:source"]
        encoded = json.dumps(
            forged,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        artifact = Artifact(
            run_id=run.id,
            step_run_id=None,
            artifact_type="lens_selection",
            locale="en",
            version=valid.artifact.version + 1,
            content_json=forged,
            content_hash=hashlib.sha256(encoded).hexdigest(),
        )
        session.add(artifact)
        await session.flush()

        with pytest.raises(
            LensSelectionError,
            match="lens_selection_artifact_semantic_mismatch",
        ):
            await lens_selection_angle_context(
                session,
                run_id=run.id,
            )


@pytest.mark.asyncio
async def test_angle_model_input_accepts_optional_validated_lens_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        bundle_artifact, _bundle, _evidence_set, _pack = await _bundle_fixture(
            session
        )
        expected = {
            "primary_lens": "SIGNALS",
            "supporting_lenses": ["METHOD"],
            "reader_need": "grounded reader need",
        }

        async def fake_lens_context(
            _session: AsyncSession,
            *,
            run_id: UUID,
        ) -> dict[str, object]:
            assert run_id == bundle_artifact.run_id
            return expected

        monkeypatch.setattr(
            angle_module,
            "lens_selection_angle_context",
            fake_lens_context,
        )
        loaded = await load_journal_input_bundle(
            session,
            journal_input_bundle_id=bundle_artifact.id,
            expected_content_hash=bundle_artifact.content_hash,
        )
        assert loaded.angle_model_input["lens_selection"] == expected
