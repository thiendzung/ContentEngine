from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_review_revise import isolated_session
from test_operator_start_to_angle import (
    ControlledCodexRunner,
    ControlledEvidenceWorkflow,
    ExplodingEvidenceWorkflow,
    _activate_seeded_angle_runtime,
    _intake_kwargs,
    _ready_preflight,
)

import app.modules.content_engine.journal.operator_vertical_slice as vertical_slice
from app.modules.content_engine.journal.operator_evidence_reuse import (
    ReusableEvidenceSetError,
    load_latest_reusable_evidence_set,
)
from app.modules.content_engine.journal.operator_manual_intake import (
    create_founder_journal_intake,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    get_operator_state_v45,
    submit_operator_command_v45,
)
from app.modules.content_engine.journal.operator_worker import (
    OperatorWorkerError,
    claim_next_operator_job,
    execute_start_to_angle_job,
)
from app.modules.content_engine.models import ContentCase
from app.modules.harness.agent_runner import AgentRunnerRegistry
from app.modules.harness.models import Artifact
from app.modules.knowledge.evidence_set_approval import approve_evidence_set
from app.modules.knowledge.models import Evidence, EvidenceSet, Source, SourceDocument
from app.modules.knowledge.persistence import content_hash, evidence_set_hash
from app.modules.research.evidence.contracts import EvidenceRelation
from app.modules.research.evidence.persistence import (
    create_or_reuse_evidence_set,
    lock_evidence_set,
)
from app.modules.research.evidence.reviewed_source import (
    persist_reviewed_existing_source_evidence,
)


async def _reviewed_support(
    session: AsyncSession,
    *,
    content_case: ContentCase,
    marker: str,
    relation: EvidenceRelation = EvidenceRelation.SUPPORTS,
) -> UUID:
    source = Source(
        project_id=content_case.project_id,
        source_type="editorial_or_unknown",
        title="Founder-reviewed source",
        canonical_url=f"https://example.test/reviewed/{marker}/{uuid4()}",
        locale="en",
        provenance_json={"fixture": "cq07-reuse"},
        captured_at=datetime.now(UTC),
        fingerprint=f"cq07-reuse-{uuid4().hex}",
    )
    session.add(source)
    await session.flush()

    excerpt = (
        "A careful buyer should inspect the exact work, its authorship information, "
        "and the documents supplied with the transaction."
    )
    document = SourceDocument(
        source_id=source.id,
        document_version=1,
        canonical_url=source.canonical_url,
        fetched_at=datetime.now(UTC),
        content_hash=content_hash(excerpt),
        content_markdown=excerpt,
        metadata_json={"fixture": "cq07-reuse"},
        reader="fixture",
        provider="fixture-reader",
    )
    session.add(document)
    await session.flush()

    link = await persist_reviewed_existing_source_evidence(
        session,
        content_case_id=content_case.id,
        source_document_id=document.id,
        statement=excerpt,
        excerpt=excerpt,
        relation=relation,
        reviewed_by="MG CONTENT ENGINE",
    )
    return link.evidence_id


@pytest.mark.asyncio
async def test_start_to_angle_reuses_approved_locked_evidence_without_research(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vertical_slice,
        "build_journal_operator_preflight",
        _ready_preflight,
    )
    async with isolated_session() as session:
        await _activate_seeded_angle_runtime(session)
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="cq07-reuse-approved-evidence"),
        )
        content_case = await session.get(ContentCase, created.content_case_id)
        assert content_case is not None

        evidence_id = await _reviewed_support(
            session,
            content_case=content_case,
            marker="approved",
        )
        evidence_set = await create_or_reuse_evidence_set(
            session,
            project_id=content_case.project_id,
            content_case_id=content_case.id,
            evidence_ids=[evidence_id],
        )
        approval = await approve_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            expected_version=evidence_set.version,
            expected_content_hash=evidence_set.content_hash,
            approved_by="founder-evidence-review",
            approval_reason="Exact reviewed support approved for CQ07 reuse.",
        )
        evidence_set = await lock_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            locked_by="founder-evidence-review",
            approval_id=approval.id,
        )

        state = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="cq07-reuse-approved-evidence-start",
        )
        assert queued.job_id is not None
        leased = await claim_next_operator_job(
            session,
            worker_id="worker-cq07-reuse-approved",
            lease_seconds=900,
        )
        assert leased is not None

        runner = ControlledCodexRunner()
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", runner)

        result = await execute_start_to_angle_job(
            session,
            job_id=leased.id,
            worker_id="worker-cq07-reuse-approved",
            evidence_workflow=ExplodingEvidenceWorkflow(),  # type: ignore[arg-type]
            runner_registry=registry,
        )

        assert result.angle_artifact_id is not None
        assert runner.calls == 2
        refreshed = await session.get(EvidenceSet, evidence_set.id)
        assert refreshed is not None
        assert refreshed.status == "locked"
        assert refreshed.locked_by == "founder-evidence-review"

        bundle = await session.scalar(
            select(Artifact)
            .where(
                Artifact.run_id == created.bootstrap_run_id,
                Artifact.artifact_type == "journal_input_bundle",
            )
            .order_by(Artifact.version.desc())
            .limit(1)
        )
        assert bundle is not None
        assert isinstance(bundle.content_json, dict)
        audit = bundle.content_json["research_execution"]
        assert isinstance(audit, dict)
        assert audit["mode"] == "reuse_existing"
        assert audit["external_provider_calls"] == 0
        assert audit["pages_read"] == 0
        assert audit["stop_reason"] == "reused_locked_evidence_set"
        assert audit["evidence_count"] == 1


@pytest.mark.asyncio
async def test_start_to_angle_rejects_unapproved_locked_evidence_before_research(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vertical_slice,
        "build_journal_operator_preflight",
        _ready_preflight,
    )
    async with isolated_session() as session:
        await _activate_seeded_angle_runtime(session)
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="cq07-reuse-unapproved-evidence"),
        )
        content_case = await session.get(ContentCase, created.content_case_id)
        assert content_case is not None

        evidence_id = await _reviewed_support(
            session,
            content_case=content_case,
            marker="unapproved",
        )
        # Create through the real insert contract first: every EvidenceSet must start
        # as a clean draft. Then corrupt only the persisted approval invariant to
        # prove the reuse trust boundary fails closed on a locked legacy/out-of-band
        # snapshot that has no matching immutable EvidenceSetApproval.
        evidence_set = await create_or_reuse_evidence_set(
            session,
            project_id=content_case.project_id,
            content_case_id=content_case.id,
            evidence_ids=[evidence_id],
        )
        evidence_set.status = "locked"
        evidence_set.locked_at = datetime.now(UTC)
        evidence_set.locked_by = "malformed-fixture"
        await session.flush()

        state = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="cq07-reuse-unapproved-evidence-start",
        )
        assert queued.job_id is not None
        leased = await claim_next_operator_job(
            session,
            worker_id="worker-cq07-reuse-unapproved",
            lease_seconds=900,
        )
        assert leased is not None

        workflow = ControlledEvidenceWorkflow()
        runner = ControlledCodexRunner()
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", runner)

        with pytest.raises(
            OperatorWorkerError,
            match="operator_worker_reusable_evidence_approval_missing",
        ):
            await execute_start_to_angle_job(
                session,
                job_id=leased.id,
                worker_id="worker-cq07-reuse-unapproved",
                evidence_workflow=workflow,  # type: ignore[arg-type]
                runner_registry=registry,
            )

        assert workflow.calls == 0
        assert runner.calls == 0


@pytest.mark.asyncio
async def test_start_to_angle_rejects_context_only_locked_evidence_before_research(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vertical_slice,
        "build_journal_operator_preflight",
        _ready_preflight,
    )
    async with isolated_session() as session:
        await _activate_seeded_angle_runtime(session)
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="cq07-reuse-context-only"),
        )
        content_case = await session.get(ContentCase, created.content_case_id)
        assert content_case is not None

        evidence_id = await _reviewed_support(
            session,
            content_case=content_case,
            marker="context-only",
            relation=EvidenceRelation.CONTEXT_ONLY,
        )
        evidence_set = await create_or_reuse_evidence_set(
            session,
            project_id=content_case.project_id,
            content_case_id=content_case.id,
            evidence_ids=[evidence_id],
        )
        approval = await approve_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            expected_version=evidence_set.version,
            expected_content_hash=evidence_set.content_hash,
            approved_by="founder-evidence-review",
            approval_reason="Context-only fixture approved for fail-closed proof.",
        )
        await lock_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            locked_by="founder-evidence-review",
            approval_id=approval.id,
        )

        state = await get_operator_state_v45(
            session,
            content_case_id=created.content_case_id,
        )
        queued = await submit_operator_command_v45(
            session,
            content_case_id=created.content_case_id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="cq07-reuse-context-only-start",
        )
        assert queued.job_id is not None
        leased = await claim_next_operator_job(
            session,
            worker_id="worker-cq07-reuse-context-only",
            lease_seconds=900,
        )
        assert leased is not None

        workflow = ControlledEvidenceWorkflow()
        runner = ControlledCodexRunner()
        registry = AgentRunnerRegistry()
        registry.register("codex_cli", runner)

        with pytest.raises(
            OperatorWorkerError,
            match="operator_worker_reusable_evidence_no_factual_support",
        ):
            await execute_start_to_angle_job(
                session,
                job_id=leased.id,
                worker_id="worker-cq07-reuse-context-only",
                evidence_workflow=workflow,  # type: ignore[arg-type]
                runner_registry=registry,
            )

        assert workflow.calls == 0
        assert runner.calls == 0


@pytest.mark.asyncio
async def test_reusable_evidence_rejects_stale_source_document_snapshot() -> None:
    async with isolated_session() as session:
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="cq07-reuse-stale-document"),
        )
        content_case = await session.get(ContentCase, created.content_case_id)
        assert content_case is not None

        evidence_id = await _reviewed_support(
            session,
            content_case=content_case,
            marker="stale-document",
        )
        evidence_set = await create_or_reuse_evidence_set(
            session,
            project_id=content_case.project_id,
            content_case_id=content_case.id,
            evidence_ids=[evidence_id],
        )
        approval = await approve_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            expected_version=evidence_set.version,
            expected_content_hash=evidence_set.content_hash,
            approved_by="founder-evidence-review",
            approval_reason="Exact reviewed support approved for stale-snapshot test.",
        )
        await lock_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            locked_by="founder-evidence-review",
            approval_id=approval.id,
        )

        evidence = await session.get(Evidence, evidence_id)
        assert evidence is not None and evidence.source_document_id is not None
        document = await session.get(SourceDocument, evidence.source_document_id)
        assert document is not None
        document.content_hash = "0" * 64
        await session.flush()

        with pytest.raises(
            ReusableEvidenceSetError,
            match="operator_worker_reusable_evidence_document_invalid",
        ):
            await load_latest_reusable_evidence_set(
                session,
                project_id=content_case.project_id,
                content_case_id=content_case.id,
            )


@pytest.mark.asyncio
async def test_reusable_evidence_rejects_bad_human_review_provenance() -> None:
    async with isolated_session() as session:
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="cq07-reuse-bad-review"),
        )
        content_case = await session.get(ContentCase, created.content_case_id)
        assert content_case is not None

        evidence_id = await _reviewed_support(
            session,
            content_case=content_case,
            marker="bad-review",
        )
        evidence_set = await create_or_reuse_evidence_set(
            session,
            project_id=content_case.project_id,
            content_case_id=content_case.id,
            evidence_ids=[evidence_id],
        )
        approval = await approve_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            expected_version=evidence_set.version,
            expected_content_hash=evidence_set.content_hash,
            approved_by="founder-evidence-review",
            approval_reason="Exact reviewed support approved for provenance test.",
        )
        await lock_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            locked_by="founder-evidence-review",
            approval_id=approval.id,
        )

        evidence = await session.get(Evidence, evidence_id)
        assert evidence is not None
        evidence.quality_metadata_json = {
            **evidence.quality_metadata_json,
            "reviewed_by": "different-reviewer",
        }
        await session.flush()

        with pytest.raises(
            ReusableEvidenceSetError,
            match="operator_worker_reusable_evidence_review_invalid",
        ):
            await load_latest_reusable_evidence_set(
                session,
                project_id=content_case.project_id,
                content_case_id=content_case.id,
            )
