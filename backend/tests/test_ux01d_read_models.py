from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select
from test_ce05_review_console import isolated_session
from test_ll01c_learning_application import _need_candidate

from app.modules.content_engine.models import Project
from app.modules.harness.models import Artifact
from app.modules.learning.models import (
    LearningApplication,
    LearningCandidate,
    LearningCandidateReview,
    LearningResolution,
    LearningValidation,
)
from app.modules.learning.read_model import build_learning_overview


async def _counts(session) -> dict[str, int]:
    async def count(model: Any) -> int:
        return int(
            await session.scalar(select(func.count()).select_from(model)) or 0
        )

    return {
        "candidates": await count(LearningCandidate),
        "reviews": await count(LearningCandidateReview),
        "applications": await count(LearningApplication),
        "validations": await count(LearningValidation),
        "resolutions": await count(LearningResolution),
        "artifacts": await count(Artifact),
    }


@pytest.mark.asyncio
async def test_ux01d_learning_projection_is_project_scoped_read_only_and_separates_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with isolated_session() as session:
        _fixture, _mapping, signal, assessment, candidate = await _need_candidate(
            session,
            monkeypatch,
        )
        project = await session.get(Project, candidate.project_id)
        assert project is not None
        before = await _counts(session)

        overview = await build_learning_overview(
            session,
            project_slug=project.slug,
        )

        assert await _counts(session) == before
        assert overview.project_id == project.id
        assert overview.semantics["candidate_is_not_customer_truth"] is True
        assert overview.semantics["evidence_is_not_learning_rule"] is True
        assert (
            overview.semantics["application_receipt_required_for_truth_change"]
            is True
        )
        assert overview.semantics["validation_does_not_auto_promote"] is True

        row = next(item for item in overview.candidates if item.id == candidate.id)
        assert row.statement == candidate.statement
        assert row.application is None
        assert row.review is None
        assert {item.kind for item in row.evidence} >= {
            "signal",
            "assessment_artifact",
            "measurement_observation",
        }
        assert any(
            item.kind == "signal"
            and item.id == signal.id
            and item.relation == "supports"
            for item in row.evidence
        )
        assert any(
            item.kind == "assessment_artifact"
            and item.id == assessment.artifact.id
            for item in row.evidence
        )
