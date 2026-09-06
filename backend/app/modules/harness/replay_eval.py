"""Replay/eval primitives for CE03 regression runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ContextManifest,
    ModelCall,
    QualityEvaluation,
    ToolCall,
    utc_now,
)
from app.modules.harness.runtime import ContextInputs


class ReplayEvalError(ValueError):
    """Raised when replay/eval lineage or frozen inputs are invalid."""


@dataclass(frozen=True)
class EvalRunFixture:
    run: ContentRun
    fixture: Artifact


async def create_eval_run(
    session: AsyncSession,
    *,
    baseline_run_id: UUID,
    candidate_settings_snapshot_id: UUID,
    baseline_artifact_id: UUID,
    baseline_context_manifest_id: UUID,
) -> EvalRunFixture:
    """Create an eval run plus immutable references to one completed baseline."""

    baseline = await session.get(ContentRun, baseline_run_id)
    if baseline is None:
        raise ReplayEvalError("baseline ContentRun not found")
    if baseline.status != "completed":
        raise ReplayEvalError("baseline ContentRun must be completed")
    if baseline.run_mode == "eval":
        raise ReplayEvalError("V1 replay baseline must be a non-eval ContentRun")

    baseline_artifact = await session.get(Artifact, baseline_artifact_id)
    if baseline_artifact is None or baseline_artifact.run_id != baseline.id:
        raise ReplayEvalError("baseline Artifact does not belong to baseline ContentRun")

    baseline_manifest = await session.get(ContextManifest, baseline_context_manifest_id)
    if baseline_manifest is None or baseline_manifest.run_id != baseline.id:
        raise ReplayEvalError("baseline ContextManifest does not belong to baseline ContentRun")

    candidate_snapshot = await session.get(SettingsSnapshot, candidate_settings_snapshot_id)
    if candidate_snapshot is None:
        raise ReplayEvalError("candidate SettingsSnapshot not found")
    if candidate_snapshot.project_id != baseline.project_id:
        raise ReplayEvalError("candidate SettingsSnapshot belongs to a different Project")

    eval_run = ContentRun(
        project_id=baseline.project_id,
        content_case_id=baseline.content_case_id,
        locale_variant_id=baseline.locale_variant_id,
        content_item_id=baseline.content_item_id,
        run_mode="eval",
        status="pending",
        current_step="eval",
        settings_snapshot_id=candidate_snapshot.id,
        started_at=utc_now(),
    )
    session.add(eval_run)
    await session.flush()

    payload: dict[str, object] = {
        "baseline_run_id": str(baseline.id),
        "baseline_run_mode": baseline.run_mode,
        "baseline_settings_snapshot_id": str(baseline.settings_snapshot_id),
        "candidate_settings_snapshot_id": str(candidate_snapshot.id),
        "baseline_artifact_id": str(baseline_artifact.id),
        "baseline_artifact_type": baseline_artifact.artifact_type,
        "baseline_artifact_hash": baseline_artifact.content_hash,
        "baseline_context_manifest_id": str(baseline_manifest.id),
        "baseline_context_hash": baseline_manifest.content_hash,
        "frozen": True,
    }
    fixture = Artifact(
        run_id=eval_run.id,
        artifact_type="replay_fixture",
        version=1,
        content_json=payload,
        content_hash=_stable_hash(payload),
    )
    session.add(fixture)
    await session.flush()
    return EvalRunFixture(run=eval_run, fixture=fixture)


async def frozen_context_inputs(
    session: AsyncSession,
    *,
    eval_run_id: UUID,
    prompt_version: str,
    recipe_version: str,
) -> ContextInputs:
    """Reuse exact baseline context refs while allowing candidate prompt/recipe versions."""

    _, payload = await _load_fixture(session, eval_run_id=eval_run_id)
    manifest_id = _uuid_field(payload, "baseline_context_manifest_id")
    manifest = await session.get(ContextManifest, manifest_id)
    if manifest is None:
        raise ReplayEvalError("frozen baseline ContextManifest no longer exists")
    if manifest.content_hash != _str_field(payload, "baseline_context_hash"):
        raise ReplayEvalError("frozen baseline ContextManifest hash changed")

    return ContextInputs(
        prompt_version=prompt_version,
        recipe_version=recipe_version,
        evidence_set_id=manifest.evidence_set_id,
        originality_pack_id=manifest.originality_pack_id,
        knowledge_chunk_refs=tuple(manifest.knowledge_chunk_refs_json),
        golden_example_refs=tuple(manifest.golden_example_refs_json),
        tool_result_refs=tuple(manifest.tool_result_refs_json),
    )


async def create_eval_report(
    session: AsyncSession,
    *,
    eval_run_id: UUID,
    candidate_artifact_id: UUID,
) -> Artifact:
    """Persist a deterministic candidate-vs-baseline report without promotion."""

    eval_run = await session.get(ContentRun, eval_run_id)
    if eval_run is None or eval_run.run_mode != "eval":
        raise ReplayEvalError("eval report requires an eval ContentRun")

    fixture, payload = await _load_fixture(session, eval_run_id=eval_run_id)
    baseline_run_id = _uuid_field(payload, "baseline_run_id")
    baseline_artifact_id = _uuid_field(payload, "baseline_artifact_id")

    baseline_run = await session.get(ContentRun, baseline_run_id)
    baseline_artifact = await session.get(Artifact, baseline_artifact_id)
    candidate_artifact = await session.get(Artifact, candidate_artifact_id)
    if baseline_run is None or baseline_run.status != "completed":
        raise ReplayEvalError("baseline ContentRun is no longer a completed run")
    if baseline_artifact is None or baseline_artifact.run_id != baseline_run.id:
        raise ReplayEvalError("frozen baseline Artifact no longer matches baseline run")
    if baseline_artifact.content_hash != _str_field(payload, "baseline_artifact_hash"):
        raise ReplayEvalError("frozen baseline Artifact hash changed")
    if candidate_artifact is None or candidate_artifact.run_id != eval_run.id:
        raise ReplayEvalError("candidate Artifact does not belong to eval run")
    if candidate_artifact.artifact_type != baseline_artifact.artifact_type:
        raise ReplayEvalError("candidate and baseline Artifact types must match")

    baseline_quality = await _quality_summary(
        session,
        run_id=baseline_run.id,
        artifact_id=baseline_artifact.id,
    )
    candidate_quality = await _quality_summary(
        session,
        run_id=eval_run.id,
        artifact_id=candidate_artifact.id,
    )
    baseline_model = await _model_summary(session, run_id=baseline_run.id)
    candidate_model = await _model_summary(session, run_id=eval_run.id)
    baseline_tool = await _tool_summary(session, run_id=baseline_run.id)
    candidate_tool = await _tool_summary(session, run_id=eval_run.id)

    baseline_cost = _decimal_field(baseline_model, "cost")
    candidate_cost = _decimal_field(candidate_model, "cost")
    report_payload: dict[str, object] = {
        "replay_fixture_id": str(fixture.id),
        "frozen_context_manifest_id": _str_field(
            payload, "baseline_context_manifest_id"
        ),
        "baseline": {
            "run_id": str(baseline_run.id),
            "artifact_id": str(baseline_artifact.id),
            "artifact_hash": baseline_artifact.content_hash,
            "settings_snapshot_id": str(baseline_run.settings_snapshot_id),
            "quality": baseline_quality,
            "model_usage": baseline_model,
            "tool_usage": baseline_tool,
        },
        "candidate": {
            "run_id": str(eval_run.id),
            "artifact_id": str(candidate_artifact.id),
            "artifact_hash": candidate_artifact.content_hash,
            "settings_snapshot_id": str(eval_run.settings_snapshot_id),
            "quality": candidate_quality,
            "model_usage": candidate_model,
            "tool_usage": candidate_tool,
        },
        "comparison": {
            "content_changed": baseline_artifact.content_hash
            != candidate_artifact.content_hash,
            "average_score_delta": _score_delta(
                baseline_quality.get("average_score"),
                candidate_quality.get("average_score"),
            ),
            "output_tokens_delta": _int_field(candidate_model, "output_tokens")
            - _int_field(baseline_model, "output_tokens"),
            "cost_delta": _decimal_text(candidate_cost - baseline_cost),
        },
        "promotion": {
            "mode": "manual_only",
            "auto_promoted": False,
        },
    }

    current_version = await session.scalar(
        select(func.coalesce(func.max(Artifact.version), 0)).where(
            Artifact.run_id == eval_run.id,
            Artifact.artifact_type == "eval_report",
        )
    )
    report = Artifact(
        run_id=eval_run.id,
        artifact_type="eval_report",
        version=int(current_version or 0) + 1,
        content_json=report_payload,
        content_hash=_stable_hash(report_payload),
    )
    session.add(report)
    await session.flush()
    return report


async def _load_fixture(
    session: AsyncSession,
    *,
    eval_run_id: UUID,
) -> tuple[Artifact, dict[str, object]]:
    eval_run = await session.get(ContentRun, eval_run_id)
    if eval_run is None or eval_run.run_mode != "eval":
        raise ReplayEvalError("replay fixture requires an eval ContentRun")

    fixture = await session.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == eval_run_id,
            Artifact.artifact_type == "replay_fixture",
        )
        .order_by(Artifact.version.desc())
        .limit(1)
    )
    if fixture is None or fixture.content_json is None:
        raise ReplayEvalError("replay fixture not found")
    if fixture.content_hash != _stable_hash(fixture.content_json):
        raise ReplayEvalError("replay fixture hash mismatch")
    if fixture.content_json.get("frozen") is not True:
        raise ReplayEvalError("replay fixture is not frozen")
    if fixture.content_json.get("candidate_settings_snapshot_id") != str(
        eval_run.settings_snapshot_id
    ):
        raise ReplayEvalError("eval run settings no longer match replay fixture")
    return fixture, fixture.content_json


async def _quality_summary(
    session: AsyncSession,
    *,
    run_id: UUID,
    artifact_id: UUID,
) -> dict[str, object]:
    rows = list(
        (
            await session.scalars(
                select(QualityEvaluation).where(
                    QualityEvaluation.run_id == run_id,
                    QualityEvaluation.artifact_id == artifact_id,
                )
            )
        ).all()
    )
    counts = {"pass": 0, "warn": 0, "fail": 0}
    scores: list[float] = []
    for row in rows:
        counts[row.result] = counts.get(row.result, 0) + 1
        if row.score is not None:
            scores.append(row.score)
    average_score = round(sum(scores) / len(scores), 6) if scores else None
    return {
        "evaluations": len(rows),
        "result_counts": counts,
        "average_score": average_score,
    }


async def _model_summary(session: AsyncSession, *, run_id: UUID) -> dict[str, object]:
    rows = list((await session.scalars(select(ModelCall).where(ModelCall.run_id == run_id))).all())
    cost = sum((row.cost or Decimal("0") for row in rows), Decimal("0"))
    return {
        "calls": len(rows),
        "completed_calls": sum(row.status == "completed" for row in rows),
        "failed_calls": sum(row.status == "failed" for row in rows),
        "input_tokens": sum(row.input_tokens or 0 for row in rows),
        "output_tokens": sum(row.output_tokens or 0 for row in rows),
        "cost": _decimal_text(cost),
        "models": sorted({f"{row.provider}:{row.model}" for row in rows}),
    }


async def _tool_summary(session: AsyncSession, *, run_id: UUID) -> dict[str, object]:
    rows = list((await session.scalars(select(ToolCall).where(ToolCall.run_id == run_id))).all())
    return {
        "calls": len(rows),
        "completed_calls": sum(row.status == "completed" for row in rows),
        "failed_calls": sum(row.status == "failed" for row in rows),
        "retry_count": sum(row.retry_count for row in rows),
        "tools": sorted({row.tool_key for row in rows}),
    }


def _score_delta(baseline: object, candidate: object) -> float | None:
    if not isinstance(baseline, (int, float)) or not isinstance(candidate, (int, float)):
        return None
    return round(float(candidate) - float(baseline), 6)


def _stable_hash(payload: dict[str, object]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _str_field(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ReplayEvalError(f"replay fixture missing {key}")
    return value


def _uuid_field(payload: dict[str, object], key: str) -> UUID:
    try:
        return UUID(_str_field(payload, key))
    except ValueError as exc:
        raise ReplayEvalError(f"replay fixture has invalid {key}") from exc


def _int_field(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ReplayEvalError(f"eval report summary missing integer {key}")
    return value


def _decimal_field(payload: dict[str, object], key: str) -> Decimal:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ReplayEvalError(f"eval report summary missing decimal {key}")
    try:
        return Decimal(value)
    except Exception as exc:
        raise ReplayEvalError(f"eval report summary has invalid decimal {key}") from exc


def _decimal_text(value: Decimal) -> str:
    return format(value, ".6f")
