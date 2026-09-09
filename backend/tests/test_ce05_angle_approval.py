from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from evidence_set_helpers import create_locked_evidence_set
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_journal_research_handoff import (
    _approved_pack,
    _content_case,
    _evidence_row,
    _run_and_step,
)

from app.core.database import engine
from app.modules.content_engine.journal.angle import (
    AngleApproval,
    AngleApprovalError,
    AngleCandidate,
    AngleGenerationError,
    AngleGenerator,
    JournalInputBundle,
    angle_candidate_hash,
    approve_angle_candidate,
    handoff_approved_angle,
    load_journal_input_bundle,
)
from app.modules.content_engine.journal.research_handoff import (
    JournalResearchHandoff,
    ResearchDecision,
)
from app.modules.content_engine.models import ContentOpportunity
from app.modules.harness.models import Artifact, ContentRun, ToolCall
from app.modules.knowledge.models import EvidenceSet, OriginalityPack


@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


async def _bundle_fixture(
    session: AsyncSession,
) -> tuple[Artifact, JournalInputBundle, EvidenceSet, OriginalityPack]:
    project, content_case, opportunity, _need = await _content_case(session)
    evidence = await _evidence_row(session, project_id=project.id, suffix="angle")
    evidence_set = await create_locked_evidence_set(
        session,
        project_id=project.id,
        content_case_id=content_case.id,
        evidence_ids=[str(evidence.id)],
    )
    pack = await _approved_pack(session, content_case_id=content_case.id)
    run, step = await _run_and_step(session, project=project, content_case=content_case)
    handoff = JournalResearchHandoff()
    evidence_handoff = await handoff.handoff_evidence_set(
        session,
        project_id=project.id,
        content_case_id=content_case.id,
        evidence_set_id=evidence_set.id,
        expected_version=evidence_set.version,
        expected_content_hash=evidence_set.content_hash,
    )
    originality_handoff = await handoff.handoff_originality_pack(
        session,
        content_case_id=content_case.id,
        originality_pack_id=pack.id,
    )
    bundle = await handoff.persist_journal_input_bundle(
        session,
        run_id=run.id,
        step_run_id=step.id,
        research_decision=ResearchDecision.REUSE_EXISTING,
        opportunity_id=opportunity.id,
        evidence_set=evidence_handoff,
        originality_pack=originality_handoff,
        provider_calls=0,
        model_calls=0,
    )
    input_bundle = await load_journal_input_bundle(
        session,
        journal_input_bundle_id=bundle.id,
        expected_content_hash=bundle.content_hash,
    )
    return bundle, input_bundle, evidence_set, pack


def _candidate_payload(bundle: JournalInputBundle, index: int) -> dict[str, object]:
    return {
        "angle_id": f"angle-{index}",
        "working_title": f"Grounded title {index}",
        "reader_problem": "The reader lacks a grounded next question.",
        "central_question": "What should the reader examine before deciding?",
        "core_promise": "Leave with one grounded question to ask.",
        "point_of_view": "Use the work and evidence together, without invented certainty.",
        "why_now": "The reader is considering a decision now.",
        "evidence_refs": [str(bundle.evidence_ids[0])],
        "originality_refs": [bundle.originality_refs[0]],
        "excluded_claims": ["Do not claim a universal pricing formula."],
        "risks": ["The reader may mistake context for a guarantee."],
        "confidence": 0.8,
        "locale": bundle.locale,
    }


class FakeAngleModel:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = outputs
        self.calls = 0

    async def generate(self, *, input_bundle: dict[str, object], attempt: int) -> object:
        del input_bundle
        self.calls += 1
        return self.outputs[min(self.calls - 1, len(self.outputs) - 1)]


def _bundle_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.mark.asyncio
async def test_valid_bundle_generates_typed_candidates_and_reuses_exact_artifact() -> None:
    async with isolated_session() as session:
        bundle_artifact, bundle, _evidence_set, _pack = await _bundle_fixture(session)
        output = [_candidate_payload(bundle, index) for index in range(1, 4)]
        model = FakeAngleModel([output, output])
        generator = AngleGenerator()

        first = await generator.generate_candidates(
            session,
            journal_input_bundle_id=bundle_artifact.id,
            model=model,
            provider="fixture-provider",
            model_name="fixture-model",
        )
        second = await generator.generate_candidates(
            session,
            journal_input_bundle_id=bundle_artifact.id,
            model=model,
            provider="fixture-provider",
            model_name="fixture-model",
        )

        assert len(first.candidates) == 3
        assert all(isinstance(candidate, AngleCandidate) for candidate in first.candidates)
        assert first.artifact.id == second.artifact.id
        assert first.artifact.content_hash == second.artifact.content_hash
        assert first.artifact.content_json["provider_calls"] == 0
        assert model.calls == 2
        assert (
            await session.scalar(select(ToolCall).where(ToolCall.run_id == bundle_artifact.run_id))
        ) is None


@pytest.mark.asyncio
async def test_invalid_upstream_originality_pack_blocks_angle_generation() -> None:
    async with isolated_session() as session:
        bundle_artifact, bundle, _evidence_set, _pack = await _bundle_fixture(session)
        run = await session.get(ContentRun, bundle_artifact.run_id)
        assert run is not None
        draft = OriginalityPack(
            content_case_id=run.content_case_id,
            item_refs_json=[],
            summary="Draft pack.",
            status="draft",
        )
        session.add(draft)
        await session.flush()
        payload = dict(bundle_artifact.content_json or {})
        payload["originality_pack"] = {
            "id": str(draft.id),
            "snapshot_hash": "0" * 64,
        }
        bundle_artifact.content_json = payload
        bundle_artifact.content_hash = _bundle_hash(payload)
        model = FakeAngleModel([[_candidate_payload(bundle, index) for index in range(1, 4)]])

        with pytest.raises(AngleGenerationError, match="originality_pack_approval_required"):
            with session.no_autoflush:
                await AngleGenerator(max_attempts=1).generate_candidates(
                    session,
                    journal_input_bundle_id=bundle_artifact.id,
                    model=model,
                    provider="fixture-provider",
                    model_name="fixture-model",
                )


@pytest.mark.asyncio
async def test_stale_evidence_set_bundle_and_do_not_write_fail_closed() -> None:
    async with isolated_session() as session:
        bundle_artifact, bundle, evidence_set, _pack = await _bundle_fixture(session)
        evidence_set.evidence_ids_json = [str(UUID(int=0))]
        model = FakeAngleModel([[_candidate_payload(bundle, index) for index in range(1, 4)]])
        with pytest.raises(AngleGenerationError, match="evidence_set_snapshot_stale"):
            with session.no_autoflush:
                await AngleGenerator(max_attempts=1).generate_candidates(
                    session,
                    journal_input_bundle_id=bundle_artifact.id,
                    model=model,
                    provider="fixture-provider",
                    model_name="fixture-model",
                )

    async with isolated_session() as session:
        bundle_artifact, bundle, _evidence_set, _pack = await _bundle_fixture(session)
        payload = dict(bundle_artifact.content_json or {})
        payload["research_decision"] = "RESEARCH_REQUIRED"
        # Keep the old hash so the immutable bundle cannot be silently changed.
        bundle_artifact.content_json = payload
        model = FakeAngleModel([[_candidate_payload(bundle, index) for index in range(1, 4)]])
        with pytest.raises(AngleGenerationError, match="journal_input_bundle_snapshot_stale"):
            with session.no_autoflush:
                await AngleGenerator(max_attempts=1).generate_candidates(
                    session,
                    journal_input_bundle_id=bundle_artifact.id,
                    model=model,
                    provider="fixture-provider",
                    model_name="fixture-model",
                )

    async with isolated_session() as session:
        bundle_artifact, bundle, _evidence_set, _pack = await _bundle_fixture(session)
        opportunity_id = UUID(str(bundle.opportunity["id"]))
        opportunity = await session.get(ContentOpportunity, opportunity_id)
        assert opportunity is not None
        opportunity.decision = "DO_NOT_WRITE"
        model = FakeAngleModel([[_candidate_payload(bundle, index) for index in range(1, 4)]])
        with pytest.raises(AngleGenerationError, match="angle_upstream_decision_blocked"):
            with session.no_autoflush:
                await AngleGenerator(max_attempts=1).generate_candidates(
                    session,
                    journal_input_bundle_id=bundle_artifact.id,
                    model=model,
                    provider="fixture-provider",
                    model_name="fixture-model",
                )


@pytest.mark.asyncio
async def test_external_evidence_or_originality_refs_fail_closed() -> None:
    async with isolated_session() as session:
        bundle_artifact, bundle, _evidence_set, _pack = await _bundle_fixture(session)
        output = [_candidate_payload(bundle, index) for index in range(1, 4)]
        output[0]["evidence_refs"] = [str(UUID(int=0))]
        model = FakeAngleModel([output])
        with pytest.raises(AngleGenerationError, match="angle_model_output_invalid") as exc_info:
            await AngleGenerator(max_attempts=1).generate_candidates(
                session,
                journal_input_bundle_id=bundle_artifact.id,
                model=model,
                provider="fixture-provider",
                model_name="fixture-model",
            )
        assert isinstance(exc_info.value.__cause__, AngleGenerationError)
        assert exc_info.value.__cause__.code == "angle_evidence_ref_outside_evidence_set"

    async with isolated_session() as session:
        bundle_artifact, bundle, _evidence_set, _pack = await _bundle_fixture(session)
        output = [_candidate_payload(bundle, index) for index in range(1, 4)]
        output[0]["originality_refs"] = ["motgu:missing"]
        model = FakeAngleModel([output])
        with pytest.raises(AngleGenerationError, match="angle_model_output_invalid") as exc_info:
            await AngleGenerator(max_attempts=1).generate_candidates(
                session,
                journal_input_bundle_id=bundle_artifact.id,
                model=model,
                provider="fixture-provider",
                model_name="fixture-model",
            )
        assert isinstance(exc_info.value.__cause__, AngleGenerationError)
        assert exc_info.value.__cause__.code == "angle_originality_ref_outside_pack"


@pytest.mark.asyncio
async def test_malformed_model_output_retries_once_and_then_fails_bounded() -> None:
    async with isolated_session() as session:
        bundle_artifact, bundle, _evidence_set, _pack = await _bundle_fixture(session)
        invalid = [_candidate_payload(bundle, index) for index in range(1, 3)]
        valid = [_candidate_payload(bundle, index) for index in range(1, 4)]
        model = FakeAngleModel([invalid, valid])
        result = await AngleGenerator().generate_candidates(
            session,
            journal_input_bundle_id=bundle_artifact.id,
            model=model,
            provider="fixture-provider",
            model_name="fixture-model",
        )
        assert len(result.candidates) == 3
        assert result.model_attempts == 2
        assert model.calls == 2

        always_invalid = FakeAngleModel([invalid])
        with pytest.raises(AngleGenerationError, match="angle_model_output_invalid"):
            await AngleGenerator().generate_candidates(
                session,
                journal_input_bundle_id=bundle_artifact.id,
                model=always_invalid,
                provider="fixture-provider",
                model_name="fixture-model",
            )
        assert always_invalid.calls == 2


async def _generated_fixture(
    session: AsyncSession,
) -> tuple[Artifact, JournalInputBundle, tuple[AngleCandidate, ...]]:
    bundle_artifact, bundle, _evidence_set, _pack = await _bundle_fixture(session)
    output = [_candidate_payload(bundle, index) for index in range(1, 4)]
    result = await AngleGenerator().generate_candidates(
        session,
        journal_input_bundle_id=bundle_artifact.id,
        model=FakeAngleModel([output]),
        provider="fixture-provider",
        model_name="fixture-model",
    )
    return result.artifact, bundle, result.candidates


@pytest.mark.asyncio
async def test_exact_angle_approval_is_durable_idempotent_and_handoff_gated() -> None:
    async with isolated_session() as session:
        artifact, _bundle, candidates = await _generated_fixture(session)
        selected = candidates[0]
        candidate_hash = angle_candidate_hash(selected)

        with pytest.raises(AngleApprovalError, match="angle_approval_required"):
            await handoff_approved_angle(
                session,
                angle_artifact_id=artifact.id,
                expected_artifact_version=artifact.version,
                expected_artifact_hash=artifact.content_hash,
                selected_angle_id=selected.angle_id,
                expected_candidate_hash=candidate_hash,
            )

        approval = await approve_angle_candidate(
            session,
            angle_artifact_id=artifact.id,
            expected_artifact_version=artifact.version,
            expected_artifact_hash=artifact.content_hash,
            selected_angle_id=selected.angle_id,
            expected_candidate_hash=candidate_hash,
            approved_by="founder",
            approval_reason="Approved exact Angle candidate snapshot.",
        )
        retry = await approve_angle_candidate(
            session,
            angle_artifact_id=artifact.id,
            expected_artifact_version=artifact.version,
            expected_artifact_hash=artifact.content_hash,
            selected_angle_id=selected.angle_id,
            expected_candidate_hash=candidate_hash,
            approved_by="founder",
            approval_reason="Approved exact Angle candidate snapshot.",
        )
        assert retry.id == approval.id
        assert retry.approved_at == approval.approved_at
        assert retry.selected_candidate_hash == candidate_hash

        handed_off = await handoff_approved_angle(
            session,
            angle_artifact_id=artifact.id,
            expected_artifact_version=artifact.version,
            expected_artifact_hash=artifact.content_hash,
            selected_angle_id=selected.angle_id,
            expected_candidate_hash=candidate_hash,
        )
        assert handed_off.candidate.angle_id == selected.angle_id
        assert handed_off.approval.approved_by == "founder"


@pytest.mark.asyncio
async def test_stale_or_conflicting_angle_approval_fails_closed() -> None:
    async with isolated_session() as session:
        artifact, bundle, candidates = await _generated_fixture(session)
        selected = candidates[0]
        with pytest.raises(AngleApprovalError, match="angle_candidate_snapshot_stale"):
            await approve_angle_candidate(
                session,
                angle_artifact_id=artifact.id,
                expected_artifact_version=artifact.version,
                expected_artifact_hash=artifact.content_hash,
                selected_angle_id=selected.angle_id,
                expected_candidate_hash="0" * 64,
                approved_by="founder",
                approval_reason="Approved exact Angle candidate snapshot.",
            )

        await approve_angle_candidate(
            session,
            angle_artifact_id=artifact.id,
            expected_artifact_version=artifact.version,
            expected_artifact_hash=artifact.content_hash,
            selected_angle_id=selected.angle_id,
            expected_candidate_hash=angle_candidate_hash(selected),
            approved_by="founder",
            approval_reason="Approved exact Angle candidate snapshot.",
        )
        different = candidates[1]
        with pytest.raises(AngleApprovalError, match="angle_approval_conflict"):
            await approve_angle_candidate(
                session,
                angle_artifact_id=artifact.id,
                expected_artifact_version=artifact.version,
                expected_artifact_hash=artifact.content_hash,
                selected_angle_id=different.angle_id,
                expected_candidate_hash=angle_candidate_hash(different),
                approved_by="another-reviewer",
                approval_reason="A conflicting snapshot decision.",
            )

        mutated_payload = dict(artifact.content_json or {})
        mutated_payload["candidates"] = copy.deepcopy(mutated_payload["candidates"])
        mutated_payload["candidates"][0]["working_title"] = "Mutated after approval"  # type: ignore[index]
        artifact.content_json = mutated_payload
        with pytest.raises(AngleApprovalError, match="angle_artifact_snapshot_stale"):
            with session.no_autoflush:
                await handoff_approved_angle(
                    session,
                    angle_artifact_id=artifact.id,
                    expected_artifact_version=artifact.version,
                    expected_artifact_hash=artifact.content_hash,
                    selected_angle_id=selected.angle_id,
                    expected_candidate_hash=angle_candidate_hash(selected),
                )


@pytest.mark.asyncio
async def test_angle_approval_row_is_immutable_at_database_boundary() -> None:
    async with isolated_session() as session:
        artifact, _bundle, candidates = await _generated_fixture(session)
        selected = candidates[0]
        approval = await approve_angle_candidate(
            session,
            angle_artifact_id=artifact.id,
            expected_artifact_version=artifact.version,
            expected_artifact_hash=artifact.content_hash,
            selected_angle_id=selected.angle_id,
            expected_candidate_hash=angle_candidate_hash(selected),
            approved_by="founder",
            approval_reason="Approved exact Angle candidate snapshot.",
        )
        with pytest.raises(DBAPIError, match="angle_approval_is_immutable"):
            async with session.begin_nested():
                await session.execute(
                    update(AngleApproval)
                    .where(AngleApproval.id == approval.id)
                    .values(approved_by="tampered")
                )
