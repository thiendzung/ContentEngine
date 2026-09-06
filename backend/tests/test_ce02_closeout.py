from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentExperiment,
    ContentItem,
    ContentOpportunity,
    ContentVersion,
    HumanSelection,
    LocaleVariant,
    NeedHypothesis,
    Project,
    SettingsSnapshot,
    Signal,
)
from app.modules.content_engine.persistence import create_next_content_version
from app.modules.harness.models import Approval, Artifact, ContentRun, ContextManifest, StepRun
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    EvidenceSet,
    MediaAsset,
    MediaObservation,
    OriginalityPack,
    Source,
    SourceDocument,
)
from app.modules.knowledge.persistence import content_hash


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


@pytest.mark.asyncio
async def test_ce02_persists_a_traceable_content_record_end_to_end() -> None:
    async with isolated_session() as session:
        project = Project(slug=f"motgu-{uuid4().hex[:8]}", name="MOTGU", default_locale="en")
        session.add(project)
        await session.flush()
        signal = Signal(
            project_id=project.id,
            source_kind="SEARCH",
            scope="market_web",
            observed_text="How do I choose an original painting?",
            source_url="https://example.test/question",
            locale="en",
            captured_at=datetime.now(UTC),
            fingerprint=f"signal-{uuid4().hex}",
            provenance_json={"provider": "test", "locator": "question:1"},
        )
        hypothesis = NeedHypothesis(
            project_id=project.id,
            type="question",
            statement="First-time buyers need grounded context.",
            audience_scope="first-time art buyer",
            situation="before choosing an artwork",
            origin="founder_proposed",
            status="PROPOSED",
            missing_evidence_json=["more direct MOTGU signals"],
        )
        session.add_all([signal, hypothesis])
        await session.flush()
        opportunity = ContentOpportunity(
            project_id=project.id,
            need_hypothesis_id=hypothesis.id,
            locale="en",
            reader="first-time art buyer",
            situation="before choosing an artwork",
            need="grounded context",
            question="How do I choose an original painting?",
            intent="evaluate",
            promise="Explain what can be checked.",
            motgu_material_refs_json=["motgu:artwork:1"],
            material_gaps_json=[],
            existing_content_refs_json=[],
            what_is_actually_new="MOTGU viewing context",
            next_discovery_step="verify first-party artwork facts",
            decision="CREATE",
            priority="NOW",
            reasons_json=["test"],
            suggested_content_type="journal",
        )
        session.add(opportunity)
        await session.flush()
        selection = HumanSelection(
            content_opportunity_id=opportunity.id,
            selected_by="founder",
            reason="Fits the first content case.",
        )
        experiment = ContentExperiment(
            project_id=project.id,
            content_opportunity_id=opportunity.id,
            need_hypothesis_id=hypothesis.id,
            hypothesis_version=hypothesis.version,
            expected_behaviour="Reader understands what to inspect.",
        )
        content_case = ContentCase(
            project_id=project.id,
            content_type="journal",
            need_hypothesis_id=hypothesis.id,
            content_opportunity_id=opportunity.id,
            desired_action="Look closer",
            content_hypothesis="Grounded context aids a first decision.",
            originality_statement="Use approved MOTGU material.",
            reader_before="uncertain",
            reader_after="prepared",
        )
        session.add_all([selection, experiment, content_case])
        await session.flush()
        en = LocaleVariant(
            content_case_id=content_case.id,
            locale="en",
            content_role="primary",
            primary_question="How do I choose an original painting?",
            primary_intent="evaluate",
            primary_query="choose original art Hanoi",
        )
        vi = LocaleVariant(
            content_case_id=content_case.id,
            locale="vi-VN",
            content_role="primary",
            primary_question="Tôi nên xem gì trước khi chọn tranh?",
            primary_intent="learn",
            primary_query="chọn tranh gốc Hà Nội",
        )
        session.add_all([en, vi])
        await session.flush()
        assert en.primary_question != vi.primary_question
        assert en.primary_query != vi.primary_query
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    LocaleVariant(
                        content_case_id=content_case.id,
                        locale="en",
                        content_role="duplicate",
                        primary_question="duplicate",
                        primary_intent="learn",
                    )
                )
                await session.flush()
        item = ContentItem(
            project_id=project.id,
            content_case_id=content_case.id,
            locale_variant_id=en.id,
            content_type="journal",
            canonical_key=f"journal:{uuid4().hex}:en",
        )
        snapshot = SettingsSnapshot(
            project_id=project.id,
            resolved_settings_json={"locale": "en"},
            source_version_refs_json=["settings:en:1"],
            content_hash=content_hash("settings"),
        )
        session.add_all([item, snapshot])
        await session.flush()
        run = ContentRun(
            project_id=project.id,
            content_case_id=content_case.id,
            locale_variant_id=en.id,
            content_item_id=item.id,
            run_mode="create",
            status="running",
            settings_snapshot_id=snapshot.id,
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()
        step = StepRun(run_id=run.id, step_key="research", attempt=1, status="completed")
        session.add(step)
        await session.flush()
        source = Source(
            project_id=project.id,
            source_type="manual_document",
            title="Approved MOTGU fact",
            canonical_url="https://example.test/motgu-fact",
            locator="fact:1",
            locale="en",
            provenance_json={"method": "manual"},
            captured_at=datetime.now(UTC),
            fingerprint=f"source-{uuid4().hex}",
        )
        session.add(source)
        await session.flush()
        document = SourceDocument(
            source_id=source.id,
            document_version=1,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash("approved MOTGU fact"),
            content_markdown="approved MOTGU fact",
            metadata_json={},
        )
        claim = Claim(
            project_id=project.id,
            statement="A traceable test fact.",
            claim_type="fact",
            entity_refs_json=[],
        )
        session.add_all([document, claim])
        await session.flush()
        evidence = Evidence(
            claim_id=claim.id,
            source_document_id=document.id,
            locator="fact:1",
            excerpt="approved MOTGU fact",
            relation="supports",
            quality_metadata_json={},
            provenance_json={"source_document_id": str(document.id)},
        )
        session.add(evidence)
        await session.flush()
        assert evidence.id is not None
        evidence_set = EvidenceSet(
            project_id=project.id,
            content_case_id=content_case.id,
            version=1,
            evidence_ids_json=[str(evidence.id)],
            content_hash=content_hash("evidence-set"),
            status="locked",
            locked_at=datetime.now(UTC),
            locked_by="founder",
        )
        originality = OriginalityPack(
            content_case_id=content_case.id,
            item_refs_json=[{"kind": "evidence", "id": str(evidence.id)}],
            summary="Approved MOTGU material.",
            status="approved",
            approved_at=datetime.now(UTC),
        )
        media = MediaAsset(
            project_id=project.id,
            source_id=source.id,
            content_hash=content_hash("image-bytes"),
            rights_status="approved",
            metadata_json={"kind": "image"},
        )
        session.add_all([evidence_set, originality, media])
        await session.flush()
        assert evidence_set.evidence_ids_json == [str(evidence.id)]
        assert originality.item_refs_json == [{"kind": "evidence", "id": str(evidence.id)}]
        observation = MediaObservation(
            media_asset_id=media.id,
            observation_text="A candidate visual observation.",
            method="model",
            confidence="low",
            status="candidate",
        )
        session.add(observation)
        await session.flush()
        assert observation.status == "candidate"
        with pytest.raises(
            DBAPIError, match="unapproved_media_observation_cannot_be_factual_evidence"
        ):
            async with session.begin_nested():
                session.add(
                    Evidence(
                        claim_id=claim.id,
                        media_observation_id=observation.id,
                        locator="media:1",
                        excerpt=observation.observation_text,
                        relation="supports",
                        quality_metadata_json={},
                        provenance_json={"media_observation_id": str(observation.id)},
                    )
                )
                await session.flush()
        approved_observation = MediaObservation(
            media_asset_id=media.id,
            observation_text="An approved visual observation.",
            method="model",
            confidence="reviewed",
            status="approved",
            approved_by="founder",
        )
        session.add(approved_observation)
        await session.flush()
        approved_media_evidence = Evidence(
            claim_id=claim.id,
            media_observation_id=approved_observation.id,
            locator="media:2",
            excerpt=approved_observation.observation_text,
            relation="supports",
            quality_metadata_json={},
            provenance_json={"media_observation_id": str(approved_observation.id)},
        )
        session.add(approved_media_evidence)
        await session.flush()
        manifest = ContextManifest(
            run_id=run.id,
            step_run_id=step.id,
            settings_snapshot_id=snapshot.id,
            prompt_version="journal:1",
            recipe_version="direct-answer:1",
            evidence_set_id=evidence_set.id,
            knowledge_chunk_refs_json=[],
            golden_example_refs_json=[],
            tool_result_refs_json=[],
            content_hash=content_hash("manifest"),
        )
        research = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="discovery_research_report",
            locale="en",
            version=1,
            content_json={"source_refs": [str(source.id)], "provenance_refs": ["manual:1"]},
            content_hash=content_hash("research-v1"),
        )
        research_two = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="discovery_research_report",
            locale="en",
            version=2,
            content_json={"source_refs": [str(source.id)], "provenance_refs": ["manual:2"]},
            content_hash=content_hash("research-v2"),
        )
        opportunity_map = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="opportunity_map",
            locale="en",
            version=1,
            content_json={
                "signals": [str(signal.id)],
                "need_hypotheses": [str(hypothesis.id)],
                "question_map": [opportunity.question],
                "opportunities": [str(opportunity.id)],
                "research_gaps": [],
                "human_selection": str(selection.id),
                "source_refs": [str(source.id)],
            },
            content_hash=content_hash("opportunity-map-v1"),
        )
        opportunity_map_two = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="opportunity_map",
            locale="en",
            version=2,
            content_json={"signals": [str(signal.id)], "source_refs": [str(source.id)]},
            content_hash=content_hash("opportunity-map-v2"),
        )
        final = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type="final_content",
            locale="en",
            version=1,
            content_json={"title": "A traceable draft"},
            content_hash=content_hash("final-v1"),
        )
        session.add_all(
            [manifest, research, research_two, opportunity_map, opportunity_map_two, final]
        )
        await session.flush()
        approval = Approval(
            run_id=run.id,
            step_key="final_review",
            artifact_id=final.id,
            decision="approved",
            actor_id="founder",
        )
        version_one = await create_next_content_version(
            session,
            content_item_id=item.id,
            change_reason="initial approved content",
            content_json={"title": "A traceable draft"},
            status="approved",
            created_by_run_id=run.id,
            final_artifact_id=final.id,
        )
        version_two = await create_next_content_version(
            session,
            content_item_id=item.id,
            change_reason="reviewed update",
            content_json={"title": "A traceable draft v2"},
            status="approved",
            created_by_run_id=run.id,
            final_artifact_id=final.id,
        )
        session.add(approval)
        await session.flush()
        assert hypothesis.status == "PROPOSED"
        assert experiment.result == "PENDING"
        assert version_one.content_item_id == version_two.content_item_id == item.id
        assert version_one.final_artifact_id == final.id
        assert version_one.created_by_run_id == run.id
        assert version_one.status == "approved"
        assert version_two.version_no == 2
        assert research.content_hash != research_two.content_hash
        assert opportunity_map.content_hash != opportunity_map_two.content_hash
        with pytest.raises(DBAPIError, match="content_version_is_immutable"):
            async with session.begin_nested():
                await session.execute(
                    update(ContentVersion)
                    .where(ContentVersion.id == version_one.id)
                    .values(change_reason="overwrite")
                )
        with pytest.raises(DBAPIError, match="content_version_is_immutable"):
            async with session.begin_nested():
                await session.delete(version_one)
                await session.flush()
