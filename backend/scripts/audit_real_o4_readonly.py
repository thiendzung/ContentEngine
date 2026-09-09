"""Read-only manual audit for the persisted CE04 O4 records.

Run this script against the normal application database explicitly. It is not part of
the automated test suite because the dedicated test database intentionally has no O4
production fixture.
"""

from __future__ import annotations

import asyncio
import json
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
from app.modules.knowledge.models import (
    Evidence,
    EvidenceSet,
    EvidenceSetApproval,
    OriginalityPack,
)

O4_OPPORTUNITY_ID = UUID("068991ab-de34-4787-9c38-8935c3f0e2da")
O4_CONTENT_CASE_ID = UUID("9ec6133b-5f14-46d0-9866-e3b049e537b5")
O4_NEED_ID = UUID("530bdd27-f008-4910-9b3b-df83e007cfa2")
O4_EVIDENCE_SET_ID = UUID("c5d46edb-3557-4efb-a479-8dd5702ae6c9")
O4_ORIGINALITY_PACK_ID = UUID("6bd287ec-43f9-4d69-957c-2223f258f909")


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
        approval_count: int | None = None
        if await _table_exists(session, "evidence_set_approvals"):
            approval_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(EvidenceSetApproval)
                    .where(EvidenceSetApproval.evidence_set_id == O4_EVIDENCE_SET_ID)
                )
                or 0
            )
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
                "approval_count": approval_count,
            },
            "need_hypothesis": {"id": str(need.id), "status": need.status},
            "content_case": {
                "id": str(content_case.id),
                "project_id": str(content_case.project_id),
            },
            "originality_pack": {"id": str(originality_pack.id), "status": originality_pack.status},
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
