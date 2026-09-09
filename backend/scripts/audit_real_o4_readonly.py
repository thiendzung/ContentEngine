"""Read-only manual audit for the persisted CE04 O4 records.

Run this script against the normal application database explicitly. It is not part of
the automated test suite because the dedicated test database intentionally has no O4
production fixture.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, engine
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunitySignal,
    NeedHypothesis,
    Signal,
)
from app.modules.harness.models import ContentRun
from app.modules.knowledge.admission import verify_candidate_snapshot_lineage
from app.modules.knowledge.models import (
    Claim,
    Evidence,
    EvidenceSet,
    EvidenceSetApproval,
    KnowledgeCandidate,
    OriginalityPack,
    Source,
    SourceDocument,
)
from app.modules.research.evidence.contracts import count_usable_originality_items

O4_OPPORTUNITY_ID = UUID("068991ab-de34-4787-9c38-8935c3f0e2da")
O4_CONTENT_CASE_ID = UUID("9ec6133b-5f14-46d0-9866-e3b049e537b5")
O4_NEED_ID = UUID("530bdd27-f008-4910-9b3b-df83e007cfa2")
O4_EVIDENCE_SET_ID = UUID("c5d46edb-3557-4efb-a479-8dd5702ae6c9")
O4_ORIGINALITY_PACK_ID = UUID("6bd287ec-43f9-4d69-957c-2223f258f909")
O4_CANDIDATE_IDS = (
    UUID("08693242-d5c5-51b2-bde9-141c2933417d"),
    UUID("1c9d6c34-91fe-5da2-af33-08a4dc39e2e2"),
    UUID("212f0c96-cb30-50ea-8759-8912580d0981"),
    UUID("da9a7cf5-9a74-522c-9ee9-52a1198aa194"),
)
EXPECTED_SOURCE_URLS = {
    O4_CANDIDATE_IDS[0]: "https://mci.si.edu/artifact-appraisals",
    O4_CANDIDATE_IDS[1]: "https://www.irs.gov/appeals/art-appraisal-services",
}
EXPECTED_EVIDENCE_SET_HASH = (
    "83d8ff62f639fc51e24072d194cdddfe01db467100f885ca1024e1597e14c71a"
)
EXPECTED_EVIDENCE_IDS = {
    "5e97ed0d-8989-47d3-af4e-b2f29a5110cd",
    "ae930468-0760-4e6c-b0d6-8346f5119912",
    "e4c31ee7-0627-4dcc-8e2a-db2ab8269b45",
    "fe1e11c2-1250-4c4a-ba50-0174b7b514bd",
}
EXPECTED_ORIGINALITY_SOURCE_REFS = {
    "docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-01",
    "docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-02",
    "docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-03",
    "docs/13-CE01-CONTENT-INPUT-PRICE.md#ORIG-04",
}


async def _trace_candidate(
    session: AsyncSession,
    *,
    candidate_id: UUID,
    evidence_set: EvidenceSet,
) -> dict[str, Any]:
    candidate = await session.get(KnowledgeCandidate, candidate_id)
    if candidate is None:
        raise RuntimeError(f"o4_candidate_missing:{candidate_id}")
    if candidate.status != "APPROVED" or candidate.reviewer != "MG CONTENT ENGINE":
        raise RuntimeError(f"o4_candidate_review_state_invalid:{candidate_id}")

    snapshot, recomputed_hash = await verify_candidate_snapshot_lineage(
        session,
        candidate=candidate,
    )
    provenance: dict[str, Any] = candidate.provenance_json
    evidence_set_data = provenance["evidence_set"]
    if not isinstance(evidence_set_data, dict):
        raise RuntimeError(f"o4_candidate_evidence_set_provenance_invalid:{candidate_id}")
    if (
        evidence_set_data.get("id") != str(evidence_set.id)
        or evidence_set_data.get("version") != evidence_set.version
        or evidence_set_data.get("content_hash") != evidence_set.content_hash
    ):
        raise RuntimeError(f"o4_candidate_evidence_set_link_invalid:{candidate_id}")

    claim_id = UUID(str(provenance["claim_id"]))
    claim = await session.get(Claim, claim_id)
    if claim is None or claim.project_id != candidate.project_id:
        raise RuntimeError(f"o4_candidate_claim_link_invalid:{candidate_id}")
    if claim.statement != candidate.statement:
        raise RuntimeError(f"o4_candidate_claim_statement_invalid:{candidate_id}")

    evidence_ids = [str(value) for value in provenance["evidence_ids"]]
    evidence_set_ids = {str(value) for value in evidence_set.evidence_ids_json}
    if not set(evidence_ids).issubset(evidence_set_ids):
        raise RuntimeError(f"o4_candidate_evidence_set_membership_invalid:{candidate_id}")
    evidence_refs = {
        str(ref["evidence_id"]): ref for ref in provenance["evidence_refs"]
    }
    resolved_document_ids: list[str] = []
    resolved_source_ids: list[str] = []
    evidence_trace: list[dict[str, Any]] = []
    source_documents: dict[str, dict[str, Any]] = {}
    sources: dict[str, dict[str, Any]] = {}

    for evidence_id in evidence_ids:
        evidence = await session.get(Evidence, UUID(evidence_id))
        if evidence is None or evidence.claim_id != claim.id:
            raise RuntimeError(f"o4_candidate_evidence_claim_invalid:{candidate_id}")
        evidence_ref = evidence_refs.get(evidence_id)
        if evidence_ref is None:
            raise RuntimeError(f"o4_candidate_evidence_ref_missing:{candidate_id}")
        if (
            evidence.relation != evidence_ref["relation"]
            or evidence.locator != evidence_ref["locator"]
        ):
            raise RuntimeError(f"o4_candidate_evidence_snapshot_invalid:{candidate_id}")
        document = await session.get(SourceDocument, evidence.source_document_id)
        if document is None or evidence.excerpt not in document.content_markdown:
            raise RuntimeError(f"o4_candidate_excerpt_lineage_invalid:{candidate_id}")
        source = await session.get(Source, document.source_id)
        if source is None or source.project_id != candidate.project_id:
            raise RuntimeError(f"o4_candidate_source_lineage_invalid:{candidate_id}")
        if document.canonical_url != source.canonical_url:
            raise RuntimeError(f"o4_candidate_canonical_url_mismatch:{candidate_id}")

        resolved_document_ids.append(str(document.id))
        resolved_source_ids.append(str(source.id))
        source_documents[str(document.id)] = {
            "id": str(document.id),
            "source_id": str(document.source_id),
            "canonical_url": document.canonical_url,
            "document_version": document.document_version,
            "content_hash": document.content_hash,
            "provider": document.provider,
        }
        sources[str(source.id)] = {
            "id": str(source.id),
            "title": source.title,
            "publisher": source.publisher,
            "canonical_url": source.canonical_url,
            "locator": source.locator,
            "source_type": source.source_type,
        }
        evidence_trace.append(
            {
                "id": str(evidence.id),
                "relation": evidence.relation,
                "locator": evidence.locator,
                "excerpt_match": True,
                "source_document_id": str(document.id),
                "source_id": str(source.id),
            }
        )

    resolved_document_ids = sorted(set(resolved_document_ids))
    resolved_source_ids = sorted(set(resolved_source_ids))
    if sorted(str(value) for value in provenance["source_document_ids"]) != resolved_document_ids:
        raise RuntimeError(f"o4_candidate_source_document_snapshot_invalid:{candidate_id}")
    if sorted(str(value) for value in provenance["source_ids"]) != resolved_source_ids:
        raise RuntimeError(f"o4_candidate_source_snapshot_invalid:{candidate_id}")
    if candidate.source_refs_json != [f"source:{value}" for value in resolved_source_ids]:
        raise RuntimeError(f"o4_candidate_source_refs_invalid:{candidate_id}")

    actual_urls = sorted(
        str(source["canonical_url"])
        for source in sources.values()
        if source["canonical_url"] is not None
    )
    expected_url = EXPECTED_SOURCE_URLS.get(candidate_id)
    if expected_url is None or actual_urls != [expected_url]:
        raise RuntimeError(f"o4_candidate_origin_invalid:{candidate_id}")

    return {
        "candidate_id": str(candidate.id),
        "status": candidate.status,
        "reviewer": candidate.reviewer,
        "stored_hash": provenance["candidate_content_hash"],
        "recomputed_hash": recomputed_hash,
        "lineage_verification": "PASS",
        "statement": candidate.statement,
        "claim_id": str(claim.id),
        "evidence": evidence_trace,
        "source_document_ids": resolved_document_ids,
        "source_ids": resolved_source_ids,
        "source_documents": list(source_documents.values()),
        "sources": list(sources.values()),
        "snapshot_field_count": len(snapshot),
    }


async def _table_exists(session: AsyncSession, table_name: str) -> bool:
    result = await session.execute(
        text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    )
    return result.scalar_one_or_none() is not None


async def audit() -> dict[str, object]:
    async with SessionLocal() as session:
        signal_rows = (
            await session.execute(
                select(Signal)
                .join(ContentOpportunitySignal, ContentOpportunitySignal.signal_id == Signal.id)
                .where(ContentOpportunitySignal.content_opportunity_id == O4_OPPORTUNITY_ID)
                .order_by(Signal.id)
            )
        ).scalars().all()
        evidence_set = await session.get(EvidenceSet, O4_EVIDENCE_SET_ID)
        need = await session.get(NeedHypothesis, O4_NEED_ID)
        content_case = await session.get(ContentCase, O4_CONTENT_CASE_ID)
        originality_pack = await session.get(OriginalityPack, O4_ORIGINALITY_PACK_ID)
        if not signal_rows:
            raise RuntimeError("manual_o4_fixture_missing")
        if evidence_set is None or need is None or content_case is None:
            raise RuntimeError("manual_o4_lineage_missing")
        if originality_pack is None:
            raise RuntimeError("manual_o4_originality_pack_missing")
        if evidence_set.content_hash != EXPECTED_EVIDENCE_SET_HASH:
            raise RuntimeError("manual_o4_evidence_set_hash_mismatch")
        if {str(value) for value in evidence_set.evidence_ids_json} != EXPECTED_EVIDENCE_IDS:
            raise RuntimeError("manual_o4_evidence_set_membership_mismatch")

        evidence_rows = (await session.execute(select(Evidence))).scalars().all()
        evidence_signal_column = Evidence.__table__.columns.get("signal_id") is not None
        evidence_signal_fk = any(
            foreign_key.column.table.name == "signals"
            for foreign_key in Evidence.__table__.foreign_keys
        )
        evidence_signal_provenance = any(
            "signal_id" in evidence.provenance_json
            or "planning_signal_id" in evidence.provenance_json
            for evidence in evidence_rows
        )
        approval_table_present = await _table_exists(session, "evidence_set_approvals")
        approval_count = 0
        if approval_table_present:
            approval_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(EvidenceSetApproval)
                    .where(EvidenceSetApproval.evidence_set_id == O4_EVIDENCE_SET_ID)
                )
                or 0
            )

        candidate_rows = (
            (await session.execute(select(KnowledgeCandidate))).scalars().all()
        )
        candidate_status_counts = {
            status: sum(candidate.status == status for candidate in candidate_rows)
            for status in ("APPROVED", "REJECTED", "CANDIDATE")
        }
        if len(candidate_rows) != len(O4_CANDIDATE_IDS):
            raise RuntimeError("manual_o4_candidate_count_mismatch")
        if {candidate.id for candidate in candidate_rows} != set(O4_CANDIDATE_IDS):
            raise RuntimeError("manual_o4_candidate_ids_mismatch")
        if any(candidate.reviewer != "MG CONTENT ENGINE" for candidate in candidate_rows):
            raise RuntimeError("manual_o4_candidate_reviewer_mismatch")
        if candidate_status_counts != {"APPROVED": 2, "REJECTED": 2, "CANDIDATE": 0}:
            raise RuntimeError("manual_o4_candidate_status_counts_mismatch")
        approved_traces = [
            await _trace_candidate(
                session,
                candidate_id=candidate_id,
                evidence_set=evidence_set,
            )
            for candidate_id in O4_CANDIDATE_IDS[:2]
        ]

        originality_items = originality_pack.item_refs_json
        if len(originality_items) != 4:
            raise RuntimeError("manual_o4_originality_item_count_mismatch")
        required_originality_fields = {
            "type",
            "source_ref",
            "material",
            "writer_use",
            "guardrails",
            "approval_ref",
        }
        originality_source_refs: list[str] = []
        for item in originality_items:
            if not isinstance(item, dict) or not required_originality_fields.issubset(item):
                raise RuntimeError("manual_o4_originality_structure_mismatch")
            if item["type"] != "motgu_owned_material":
                raise RuntimeError("manual_o4_originality_type_mismatch")
            originality_source_refs.append(str(item["source_ref"]))
        if set(originality_source_refs) != EXPECTED_ORIGINALITY_SOURCE_REFS:
            raise RuntimeError("manual_o4_originality_source_refs_mismatch")
        if originality_pack.content_case_id != content_case.id:
            raise RuntimeError("manual_o4_originality_content_case_mismatch")
        if count_usable_originality_items(originality_items) != 4:
            raise RuntimeError("manual_o4_originality_usable_count_mismatch")

        o4_run_count = int(
            await session.scalar(
                select(func.count())
                .select_from(ContentRun)
                .where(ContentRun.content_case_id == O4_CONTENT_CASE_ID)
            )
            or 0
        )
        assert evidence_set.status == "locked"
        assert evidence_set.version == 8
        assert need.status == "PROPOSED"
        assert content_case.project_id == evidence_set.project_id
        assert evidence_set.content_case_id == content_case.id
        assert not evidence_signal_column
        assert not evidence_signal_fk
        assert not evidence_signal_provenance

        return {
            "opportunity_id": str(O4_OPPORTUNITY_ID),
            "discovery_signal_count": len(signal_rows),
            "discovery_signal_ids": [str(signal.id) for signal in signal_rows],
            "direct_signal_to_evidence": False,
            "evidence_signal_column": evidence_signal_column,
            "evidence_signal_foreign_key": evidence_signal_fk,
            "evidence_signal_provenance": evidence_signal_provenance,
            "evidence_set": {
                "id": str(evidence_set.id),
                "version": evidence_set.version,
                "status": evidence_set.status,
                "content_hash": evidence_set.content_hash,
                "evidence_ids": sorted(str(value) for value in evidence_set.evidence_ids_json),
                "approval_table_present": approval_table_present,
                "approval_count": approval_count,
            },
            "need_hypothesis": {"id": str(need.id), "status": need.status},
            "content_case": {
                "id": str(content_case.id),
                "project_id": str(content_case.project_id),
            },
            "knowledge_candidates": {
                "total": len(candidate_rows),
                "status_counts": candidate_status_counts,
                "approved_ids": [str(value) for value in O4_CANDIDATE_IDS[:2]],
                "rejected_ids": [str(value) for value in O4_CANDIDATE_IDS[2:]],
                "approved_traces": approved_traces,
            },
            "originality_pack": {"id": str(originality_pack.id), "status": originality_pack.status},
            "originality_pack_structure": {
                "item_count": len(originality_items),
                "usable_item_count": count_usable_originality_items(originality_items),
                "source_refs": sorted(originality_source_refs),
                "required_fields_present": True,
            },
            "o4_content_run_count": o4_run_count,
            "mutation": "read_only",
            "provider_calls": 0,
        }


async def main() -> None:
    try:
        print(json.dumps(await audit(), indent=2, sort_keys=True, default=str))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
