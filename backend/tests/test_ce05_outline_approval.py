from __future__ import annotations

import pytest
from test_ce05_outline import (
    FakeOutlineModel,
    _approved_fixture,
    _generate,
    _outline_payload,
    isolated_session,
)

from app.modules.content_engine.journal.outline import (
    load_outline_input,
    persist_journal_outline,
)
from app.modules.content_engine.journal.outline_approval import (
    OutlineApprovalError,
    approve_outline_artifact,
    handoff_approved_outline,
)
from app.modules.content_engine.journal.outline_semantic_quality import (
    persist_outline_semantic_quality,
    validate_outline_semantic_output,
)


@pytest.mark.asyncio
async def test_outline_approval_is_exact_idempotent_and_handoff_verified() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        result = await _generate(
            session,
            fixture,
            FakeOutlineModel([_outline_payload(fixture.bundle)]),
        )
        fixture.run.status = "waiting_approval"
        await session.flush()

        kwargs = {
            "session": session,
            "outline_artifact_id": result.artifact.id,
            "expected_artifact_version": result.artifact.version,
            "expected_artifact_hash": result.artifact.content_hash,
            "approved_by": "founder",
            "approval_reason": "Founder approved the exact persisted Outline after review.",
        }
        first = await approve_outline_artifact(**kwargs)
        second = await approve_outline_artifact(**kwargs)
        assert second.id == first.id

        handoff = await handoff_approved_outline(
            session,
            outline_artifact_id=result.artifact.id,
            expected_artifact_version=result.artifact.version,
            expected_artifact_hash=result.artifact.content_hash,
            expected_approval_id=first.id,
        )
        assert handoff.artifact.id == result.artifact.id
        assert handoff.approval.id == first.id
        assert handoff.approval.run_id == fixture.run.id


@pytest.mark.asyncio
async def test_pre_cq04_role_aware_outline_remains_approvable_without_semantic_artifact() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        current = await _generate(
            session,
            fixture,
            FakeOutlineModel([_outline_payload(fixture.bundle)]),
        )
        outline_input = await load_outline_input(
            session,
            angle_artifact_id=fixture.angle_result.artifact.id,
            expected_angle_artifact_version=fixture.angle_result.artifact.version,
            expected_angle_artifact_hash=fixture.angle_result.artifact.content_hash,
            selected_angle_id=fixture.selected.angle_id,
            expected_candidate_hash=fixture.candidate_hash,
            expected_approval_id=fixture.approval.id,
        )
        legacy = await persist_journal_outline(
            session,
            outline_input=outline_input,
            outline=current.outline,
            provider="fixture-provider",
            model="fixture-model",
            model_calls=1,
            prompt_version=fixture.prompt_version,
            recipe_version=fixture.recipe_version,
            context_manifest=fixture.manifest,
            generator_version="ce05.outline_generator.v2",
        )
        assert legacy.id != current.artifact.id
        fixture.run.status = "waiting_approval"
        await session.flush()

        approval = await approve_outline_artifact(
            session,
            outline_artifact_id=legacy.id,
            expected_artifact_version=legacy.version,
            expected_artifact_hash=legacy.content_hash,
            approved_by="founder",
            approval_reason="Preserve pre-CQ04 role-aware Outline compatibility.",
        )
        handed_off = await handoff_approved_outline(
            session,
            outline_artifact_id=legacy.id,
            expected_artifact_version=legacy.version,
            expected_artifact_hash=legacy.content_hash,
            expected_approval_id=approval.id,
        )
        assert handed_off.artifact.id == legacy.id
        assert handed_off.approval.id == approval.id


@pytest.mark.asyncio
async def test_outline_semantic_revision_blocks_founder_approval() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        payload = _outline_payload(fixture.bundle)
        semantic = payload["semantic_quality"]
        assert isinstance(semantic, dict)
        semantic["verdict"] = "revise"
        semantic["findings"] = [
            {
                "code": "outline_section_job_unclear",
                "subject_ref": "section:s2",
                "reason": "The section job overlaps the previous section.",
                "remediation": "Give section s2 one distinct reader job before approval.",
            }
        ]
        result = await _generate(
            session,
            fixture,
            FakeOutlineModel([payload]),
        )
        fixture.run.status = "waiting_approval"
        await session.flush()

        with pytest.raises(
            OutlineApprovalError,
            match="outline_semantic_revision_required",
        ):
            await approve_outline_artifact(
                session,
                outline_artifact_id=result.artifact.id,
                expected_artifact_version=result.artifact.version,
                expected_artifact_hash=result.artifact.content_hash,
                approved_by="founder",
                approval_reason="Must not approve a revise Outline.",
            )


@pytest.mark.asyncio
async def test_outline_handoff_revalidates_semantic_artifact_conflicts() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        result = await _generate(
            session,
            fixture,
            FakeOutlineModel([_outline_payload(fixture.bundle)]),
        )
        fixture.run.status = "waiting_approval"
        await session.flush()
        approval = await approve_outline_artifact(
            session,
            outline_artifact_id=result.artifact.id,
            expected_artifact_version=result.artifact.version,
            expected_artifact_hash=result.artifact.content_hash,
            approved_by="founder",
            approval_reason="Founder approved the exact persisted Outline after review.",
        )

        assert result.semantic_artifact is not None
        semantic_payload = result.semantic_artifact.content_json
        assert isinstance(semantic_payload, dict)
        role = semantic_payload.get("role")
        assert role in {"pillar", "cluster"}
        revised = validate_outline_semantic_output(
            {
                "semantic_quality": {
                    "schema_version": 1,
                    "stage": "outline",
                    "role": role,
                    "verdict": "revise",
                    "findings": [
                        {
                            "code": "outline_section_redundancy",
                            "subject_ref": "section:s3",
                            "reason": "The final section materially repeats prior work.",
                            "remediation": "Remove or give section s3 a distinct reader job.",
                        }
                    ],
                }
            },
            role=role,
            section_ids=tuple(section.section_id for section in result.outline.sections),
            coverage_requirement_ids=tuple(
                item.requirement_id
                for item in fixture.selected.coverage
                if item.status == "covered"
            ),
        )
        await persist_outline_semantic_quality(
            session,
            outline_artifact=result.artifact,
            role=role,
            assessment=revised,
        )

        with pytest.raises(
            OutlineApprovalError,
            match="outline_semantic_artifact_conflict",
        ):
            await handoff_approved_outline(
                session,
                outline_artifact_id=result.artifact.id,
                expected_artifact_version=result.artifact.version,
                expected_artifact_hash=result.artifact.content_hash,
                expected_approval_id=approval.id,
            )


@pytest.mark.asyncio
async def test_outline_approval_rejects_conflicting_human_decision() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        result = await _generate(
            session,
            fixture,
            FakeOutlineModel([_outline_payload(fixture.bundle)]),
        )
        fixture.run.status = "waiting_approval"
        await session.flush()

        await approve_outline_artifact(
            session,
            outline_artifact_id=result.artifact.id,
            expected_artifact_version=result.artifact.version,
            expected_artifact_hash=result.artifact.content_hash,
            approved_by="founder",
            approval_reason="Founder approved the exact persisted Outline after review.",
        )
        with pytest.raises(OutlineApprovalError, match="outline_approval_conflict"):
            await approve_outline_artifact(
                session,
                outline_artifact_id=result.artifact.id,
                expected_artifact_version=result.artifact.version,
                expected_artifact_hash=result.artifact.content_hash,
                approved_by="founder",
                approval_reason="Different decision text must not replace the immutable approval.",
            )


@pytest.mark.asyncio
async def test_outline_handoff_fails_without_or_with_stale_approval() -> None:
    async with isolated_session() as session:
        fixture = await _approved_fixture(session)
        result = await _generate(
            session,
            fixture,
            FakeOutlineModel([_outline_payload(fixture.bundle)]),
        )
        fixture.run.status = "waiting_approval"
        await session.flush()

        with pytest.raises(OutlineApprovalError, match="outline_approval_required"):
            await handoff_approved_outline(
                session,
                outline_artifact_id=result.artifact.id,
                expected_artifact_version=result.artifact.version,
                expected_artifact_hash=result.artifact.content_hash,
                expected_approval_id=fixture.approval.id,
            )

        approval = await approve_outline_artifact(
            session,
            outline_artifact_id=result.artifact.id,
            expected_artifact_version=result.artifact.version,
            expected_artifact_hash=result.artifact.content_hash,
            approved_by="founder",
            approval_reason="Founder approved the exact persisted Outline after review.",
        )
        with pytest.raises(OutlineApprovalError, match="outline_approval_snapshot_stale"):
            await handoff_approved_outline(
                session,
                outline_artifact_id=result.artifact.id,
                expected_artifact_version=result.artifact.version,
                expected_artifact_hash="0" * 64,
                expected_approval_id=approval.id,
            )
