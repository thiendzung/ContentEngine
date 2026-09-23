from __future__ import annotations

from datetime import UTC, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from test_ce05_review_actions import _pending_fixture
from test_ce05_review_console import isolated_session
from test_ll01c_learning_application import _need_candidate

from app.modules.content_engine.models import Project, SettingsVersion
from app.modules.control_center.daily_digest import build_daily_digest
from app.modules.harness.models import Artifact, ModelCall
from app.modules.learning.models import (
    LearningApplication,
    LearningCandidate,
    LearningCandidateReview,
    LearningResolution,
    LearningValidation,
)
from app.modules.learning.read_model import build_learning_overview
from app.modules.system.read_model import build_system_overview


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
        "model_calls": await count(ModelCall),
        "settings_versions": await count(SettingsVersion),
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