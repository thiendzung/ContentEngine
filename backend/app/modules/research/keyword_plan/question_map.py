"""Canonical Question Map derived read model for QM-01A."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import (
    NeedHypothesis,
    NeedHypothesisSignal,
    Project,
    Signal,
)
from app.modules.research.keyword_plan.normalize import normalize_text

QUESTION_MAP_SCHEMA_VERSION = 1


class QuestionMapError(ValueError):
    """Fail-closed Question Map error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


async def build_question_map(
    session: AsyncSession,
    *,
    project_id: UUID,
    need_id: UUID,
    locale: str,
) -> dict[str, object]:
    """Build a deterministic locale-specific projection from canonical state."""

    normalized_locale = locale.strip().casefold()
    if not normalized_locale:
        raise QuestionMapError("question_map_locale_required")

    project = await session.get(Project, project_id)
    if project is None:
        raise QuestionMapError("question_map_project_not_found")

    need = await session.get(NeedHypothesis, need_id)
    if need is None or need.project_id != project.id:
        raise QuestionMapError("question_map_need_not_found")

    rows = (
        await session.execute(
            select(NeedHypothesisSignal, Signal)
            .join(Signal, Signal.id == NeedHypothesisSignal.signal_id)
            .where(
                NeedHypothesisSignal.need_hypothesis_id == need.id,
                NeedHypothesisSignal.relation == "supports",
                Signal.project_id == project.id,
                Signal.source_kind == "SEARCH",
            )
            .order_by(Signal.id)
        )
    ).all()

    grouped: dict[str, list[Signal]] = defaultdict(list)
    for _link, signal in rows:
        if signal.locale.strip().casefold() != normalized_locale:
            continue
        normalized = normalize_text(signal.observed_text)
        if not normalized:
            continue
        grouped[normalized].append(signal)

    questions: list[dict[str, object]] = []
    all_signal_refs: list[str] = []
    for normalized in sorted(grouped):
        signals = sorted(
            grouped[normalized],
            key=lambda row: (
                row.observed_text.casefold(),
                row.observed_text,
                str(row.id),
            ),
        )
        representative = signals[0]
        refs = sorted(str(row.id) for row in signals)
        all_signal_refs.extend(refs)
        questions.append(
            {
                "question_key": hashlib.sha256(
                    (
                        f"{need.id}\x1f{normalized_locale}\x1f{normalized}"
                    ).encode()
                ).hexdigest()[:24],
                "text": representative.observed_text.strip(),
                "normalized_text": normalized,
                "signal_refs": refs,
                "source_count": len(refs),
            }
        )

    snapshot: dict[str, object] = {
        "schema_version": QUESTION_MAP_SCHEMA_VERSION,
        "project": {
            "id": str(project.id),
            "slug": project.slug,
        },
        "need": {
            "id": str(need.id),
            "version": need.version,
            "status": need.status,
            "type": need.type,
            "statement": need.statement,
            "audience_hypothesis_id": (
                str(need.audience_hypothesis_id)
                if need.audience_hypothesis_id is not None
                else None
            ),
        },
        "locale": normalized_locale,
        "source_policy": {
            "signal_source_kind": "SEARCH",
            "need_relation": "supports",
            "canonical_need": True,
        },
        "counts": {
            "questions": len(questions),
            "search_signals": len(all_signal_refs),
        },
        "questions": questions,
        "signal_refs": sorted(all_signal_refs),
    }

    return {
        **snapshot,
        "snapshot_hash": _stable_hash(snapshot),
    }


__all__ = [
    "QUESTION_MAP_SCHEMA_VERSION",
    "QuestionMapError",
    "build_question_map",
]
