from __future__ import annotations

from typing import cast
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from test_ce05_review_revise import isolated_session
from test_operator_evidence_reuse import _reviewed_support
from test_operator_start_to_angle import _activate_seeded_angle_runtime, _intake_kwargs, _ready_preflight

import app.modules.content_engine.journal.operator_preflight as operator_preflight
import backend.scripts.run_operator_worker as run_operator_worker
from app.core.config import Settings
from app.modules.content_engine.journal.operator_evidence_reuse import (
    approve_reusable_evidence_set,
)
from app.modules.content_engine.journal.operator_manual_intake import (
    create_founder_journal_intake,
)
from app.modules.content_engine.journal.operator_vertical_slice import (
    get_operator_state_v45,
    submit_operator_command_v45,
)
from app.modules.content_engine.journal.operator_worker import OperatorWorkerError
from app.modules.content_engine.models import ContentCase
from app.modules.research.contracts import ProductionResearchRequest
from app.modules.research.evidence.persistence import (
    create_or_reuse_evidence_set,
    lock_evidence_set,
)


def _checks_by_key(result: dict[str, object]) -> dict[str, dict[str, object]]:
    raw = result["checks"]
    assert isinstance(raw, list)
    return {
        str(item["key"]): item
        for item in raw
        if isinstance(item, dict) and "key" in item
    }


@pytest.mark.asyncio
async def test_case_preflight_allows_reusable_evidence_without_serper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        operator_preflight,
        "build_operational_preflight",
        _ready_preflight,
    )
    monkeypatch.setattr(operator_preflight, "get_settings", lambda: Settings())

    async with isolated_session() as session:
        await _activate_seeded_angle_runtime(session)
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="pilot02-reusable-no-serper"),
        )
        content_case = await session.get(ContentCase, created.content_case_id)
        assert content_case is not None

        evidence_id = await _reviewed_support(
            session,
            content_case=content_case,
            marker="pilot02-no-serper",
        )
        evidence_set = await create_or_reuse_evidence_set(
            session,
            project_id=content_case.project_id,
            content_case_id=content_case.id,
            evidence_ids=[evidence_id],
        )
        approval = await approve_reusable_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            expected_version=evidence_set.version,
            expected_content_hash=evidence_set.content_hash,
            approved_by="founder-evidence-review",
            approval_reason="Reusable evidence should bypass fresh research capability.",
        )
        await lock_evidence_set(
            session,
            evidence_set_id=evidence_set.id,
            locked_by="founder-evidence-review",
            approval_id=approval.id,
        )

        preflight = await operator_preflight.build_journal_operator_preflight(
            session,
            content_case_id=content_case.id,
        )
        checks = _checks_by_key(preflight)
        assert preflight["status"] == "READY"
        assert checks["journal_research_serper"] == {
            "key": "journal_research_serper",
            "status": "READY",
            "detail": "not_required_reusable_evidence_set",
        }

        state = await get_operator_state_v45(
            session,
            content_case_id=content_case.id,
        )
        assert state.status == "READY"
        queued = await submit_operator_command_v45(
            session,
            content_case_id=content_case.id,
            intent="start",
            expected_state_version=state.state_version,
            idempotency_key="pilot02-reusable-no-serper-start",
        )
        assert queued.job_id is not None


@pytest.mark.asyncio
async def test_case_preflight_still_requires_serper_without_reusable_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        operator_preflight,
        "build_operational_preflight",
        _ready_preflight,
    )
    monkeypatch.setattr(operator_preflight, "get_settings", lambda: Settings())

    async with isolated_session() as session:
        await _activate_seeded_angle_runtime(session)
        created = await create_founder_journal_intake(
            session,
            **_intake_kwargs(key="pilot02-fresh-research-needs-serper"),
        )

        preflight = await operator_preflight.build_journal_operator_preflight(
            session,
            content_case_id=created.content_case_id,
        )
        checks = _checks_by_key(preflight)

    assert preflight["status"] == "BLOCKED"
    assert checks["journal_research_serper"]["detail"] == "operator_worker_serper_required"


@pytest.mark.asyncio
async def test_lazy_research_router_defers_serper_requirement_until_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def blocked_router(
        settings: Settings,
        client: httpx.AsyncClient,
    ) -> object:
        nonlocal calls
        calls += 1
        raise OperatorWorkerError("operator_worker_serper_required")

    monkeypatch.setattr(run_operator_worker, "_research_router", blocked_router)

    async with httpx.AsyncClient() as client:
        lazy = run_operator_worker._LazyResearchRouter(Settings(), client)
        assert calls == 0

        with pytest.raises(
            OperatorWorkerError,
            match="operator_worker_serper_required",
        ):
            await lazy.run(
                cast(AsyncSession, object()),
                request=ProductionResearchRequest(
                    project_id=uuid4(),
                    query="fresh research requires configured discovery",
                ),
            )

    assert calls == 1
