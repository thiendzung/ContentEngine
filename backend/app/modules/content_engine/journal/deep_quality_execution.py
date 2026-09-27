"""CQ-06 durable Deep Quality final-gate persistence.

This module binds one exact revised Journal draft and all validated upstream quality
artifacts to one immutable Deep Quality evaluation. Overall verdict remains
scoreless and is derived deterministically from the 12 canonical dimensions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.deep_quality import (
    DEEP_QUALITY_DIMENSIONS,
    DEEP_QUALITY_SCHEMA_VERSION,
    SEMANTIC_MODEL_DIMENSIONS,
    DeepQualityAssessment,
    DeepQualityDimension,
    DeepQualityError,
    build_deep_quality_assessment,
    validate_deep_quality_output,
)
from app.modules.content_engine.journal.deep_quality_authority import (
    AUTHORITATIVE_DEEP_QUALITY_DIMENSIONS,
    DeepQualityAuthorityError,
    derive_authoritative_deep_quality_dimensions,
)
from app.modules.content_engine.journal.deep_quality_input import (
    DeepQualityInput,
    DeepQualityInputError,
    load_deep_quality_input,
)
from app.modules.content_engine.journal.deep_quality_semantic import (
    DEEP_QUALITY_SEMANTIC_GENERATOR_VERSION,
    DeepQualitySemanticError,
    DeepQualitySemanticModelPort,
    evaluate_deep_quality_semantics,
)
from app.modules.content_engine.models import SettingsSnapshot
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ContextManifest,
    QualityEvaluation,
    StepRun,
    utc_now,
)

DEEP_QUALITY_ARTIFACT_TYPE = "deep_quality_evaluation"
DEEP_QUALITY_HANDOFF_ARTIFACT_TYPE = "deep_quality_handoff"
DEEP_QUALITY_GENERATOR_VERSION = "cq06.deep_quality_final_gate.v1"
DEEP_QUALITY_EVALUATOR_KEY = "deep_quality_final_gate"
DEEP_QUALITY_EVALUATOR_VERSION = "cq06.deep_quality_final_gate.v1"
DEEP_QUALITY_TASK_KEYS = {
    "vi-VN": "deep_quality_vi",
    "en": "deep_quality_en",
}


class DeepQualityExecutionError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True, slots=True)
class DeepQualityGateResult:
    eval_run: ContentRun
    handoff: Artifact
    step_run: StepRun
    artifact: Artifact
    evaluation: QualityEvaluation
    assessment: DeepQualityAssessment
    model_attempts: int
    reused: bool


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _artifact_ref(artifact: Artifact) -> dict[str, object]:
    return {
        "id": str(artifact.id),
        "version": artifact.version,
        "content_hash": artifact.content_hash,
    }


def _quality_ref(value: QualityEvaluation) -> dict[str, object]:
    return {
        "id": str(value.id),
        "result": value.result,
        "evaluator_key": value.evaluator_key,
        "evaluator_version": value.evaluator_version,
    }


def deep_quality_task_key(locale: str) -> str:
    key = DEEP_QUALITY_TASK_KEYS.get(locale)
    if key is None:
        raise DeepQualityExecutionError("deep_quality_locale_unsupported", locale)
    return key


def _lineage_payload(source: DeepQualityInput) -> dict[str, object]:
    support = source.coverage_support_depth
    return {
        "source_writer_run_id": str(source.writer_input.writer_run.id),
        "source_draft": _artifact_ref(source.source_artifact),
        "journal_outline": _artifact_ref(source.writer_input.outline_artifact),
        "coverage_support_depth": (
            _artifact_ref(support.artifact)
            if support is not None
            else None
        ),
        "angle_semantic": _artifact_ref(source.angle_semantic.artifact),
        "outline_semantic": _artifact_ref(source.outline_semantic.artifact),
        "human_voice_trace": _artifact_ref(source.human_voice_trace.artifact),
        "assertion_audit": {
            "artifact": _artifact_ref(
                source.source_copy_input.assertion_audit_artifact
            ),
            "quality_evaluation": _quality_ref(
                source.source_copy_input.assertion_audit_evaluation
            ),
        },
        "source_copy": {
            "artifact": _artifact_ref(source.source_copy.artifact),
            "quality_evaluation": _quality_ref(source.source_copy.evaluation),
        },
        "reader_value": {
            "artifact": _artifact_ref(source.reader_value.artifact),
            "quality_evaluation": _quality_ref(source.reader_value.evaluation),
        },
        "search_ai": {
            "artifact": _artifact_ref(source.search_ai.artifact),
            "quality_evaluation": _quality_ref(source.search_ai.evaluation),
        },
    }


def _handoff_payload(
    source: DeepQualityInput,
    *,
    settings_snapshot: SettingsSnapshot,
) -> dict[str, object]:
    return {
        "schema_version": DEEP_QUALITY_SCHEMA_VERSION,
        "artifact_type": DEEP_QUALITY_HANDOFF_ARTIFACT_TYPE,
        "task_key": deep_quality_task_key(source.writer_input.locale),
        "project_id": str(source.writer_input.writer_run.project_id),
        "content_case_id": str(source.writer_input.writer_run.content_case_id),
        "locale_variant": {
            "id": str(source.writer_input.locale_variant.id),
            "locale": source.writer_input.locale,
        },
        "lineage": _lineage_payload(source),
        "settings_snapshot": {
            "id": str(settings_snapshot.id),
            "content_hash": settings_snapshot.content_hash,
        },
    }


async def ensure_deep_quality_run(
    session: AsyncSession,
    *,
    source: DeepQualityInput,
) -> tuple[ContentRun, Artifact, bool]:
    snapshot = await session.get(
        SettingsSnapshot,
        source.writer_input.writer_run.settings_snapshot_id,
    )
    if snapshot is None:
        raise DeepQualityExecutionError("deep_quality_settings_snapshot_missing")
    payload = _handoff_payload(source, settings_snapshot=snapshot)
    handoff_hash = _hash(payload)
    rows = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.artifact_type == DEEP_QUALITY_HANDOFF_ARTIFACT_TYPE,
                    Artifact.content_hash == handoff_hash,
                    Artifact.locale == source.writer_input.locale,
                )
            )
        ).all()
    )
    reusable: list[tuple[ContentRun, Artifact]] = []
    for handoff in rows:
        if (
            handoff.version != 1
            or handoff.step_run_id is not None
            or handoff.content_json != payload
            or handoff.content_hash != handoff_hash
        ):
            raise DeepQualityExecutionError("deep_quality_handoff_snapshot_invalid")
        run = await session.get(ContentRun, handoff.run_id)
        if (
            run is None
            or run.run_mode != "eval"
            or run.project_id != source.writer_input.writer_run.project_id
            or run.content_case_id != source.writer_input.writer_run.content_case_id
            or run.locale_variant_id != source.writer_input.locale_variant.id
            or run.settings_snapshot_id
            != source.writer_input.writer_run.settings_snapshot_id
        ):
            raise DeepQualityExecutionError("deep_quality_handoff_run_mismatch")
        if run.status not in {"failed", "cancelled"}:
            reusable.append((run, handoff))
    if len(reusable) > 1:
        raise DeepQualityExecutionError("deep_quality_reusable_run_duplicate")
    if reusable:
        return (*reusable[0], True)

    run = ContentRun(
        project_id=source.writer_input.writer_run.project_id,
        content_case_id=source.writer_input.writer_run.content_case_id,
        locale_variant_id=source.writer_input.locale_variant.id,
        content_item_id=source.writer_input.writer_run.content_item_id,
        run_mode="eval",
        status="pending",
        current_step=deep_quality_task_key(source.writer_input.locale),
        settings_snapshot_id=source.writer_input.writer_run.settings_snapshot_id,
        started_at=utc_now(),
    )
    session.add(run)
    await session.flush()
    handoff = Artifact(
        run_id=run.id,
        step_run_id=None,
        artifact_type=DEEP_QUALITY_HANDOFF_ARTIFACT_TYPE,
        locale=source.writer_input.locale,
        version=1,
        content_json=payload,
        content_hash=handoff_hash,
    )
    session.add(handoff)
    await session.flush()
    return run, handoff, False


def _ref(value: object, code: str) -> tuple[UUID, int, str]:
    if not isinstance(value, dict) or set(value) != {
        "id",
        "version",
        "content_hash",
    }:
        raise DeepQualityExecutionError(code)
    raw_id = value.get("id")
    raw_version = value.get("version")
    raw_hash = value.get("content_hash")
    if (
        not isinstance(raw_id, str)
        or not isinstance(raw_version, int)
        or isinstance(raw_version, bool)
        or raw_version <= 0
        or not isinstance(raw_hash, str)
    ):
        raise DeepQualityExecutionError(code)
    try:
        artifact_id = UUID(raw_id)
    except ValueError as exc:
        raise DeepQualityExecutionError(code) from exc
    return artifact_id, raw_version, raw_hash


def _quality_id(value: object, code: str) -> UUID:
    if not isinstance(value, dict):
        raise DeepQualityExecutionError(code)
    raw_id = value.get("id")
    if not isinstance(raw_id, str):
        raise DeepQualityExecutionError(code)
    try:
        return UUID(raw_id)
    except ValueError as exc:
        raise DeepQualityExecutionError(code) from exc


async def load_deep_quality_input_from_handoff(
    session: AsyncSession,
    *,
    handoff_artifact_id: UUID,
) -> DeepQualityInput:
    handoff = await session.get(Artifact, handoff_artifact_id)
    if (
        handoff is None
        or handoff.artifact_type != DEEP_QUALITY_HANDOFF_ARTIFACT_TYPE
        or not isinstance(handoff.content_json, dict)
        or _hash(handoff.content_json) != handoff.content_hash
        or not isinstance(handoff.locale, str)
    ):
        raise DeepQualityExecutionError("deep_quality_handoff_invalid")
    payload = handoff.content_json
    lineage = payload.get("lineage")
    if not isinstance(lineage, dict):
        raise DeepQualityExecutionError("deep_quality_handoff_lineage_invalid")

    raw_writer_run_id = lineage.get("source_writer_run_id")
    if not isinstance(raw_writer_run_id, str):
        raise DeepQualityExecutionError("deep_quality_handoff_writer_invalid")
    try:
        writer_run_id = UUID(raw_writer_run_id)
    except ValueError as exc:
        raise DeepQualityExecutionError("deep_quality_handoff_writer_invalid") from exc

    source_id, source_version, source_hash = _ref(
        lineage.get("source_draft"),
        "deep_quality_handoff_source_invalid",
    )
    outline_id, outline_version, outline_hash = _ref(
        lineage.get("journal_outline"),
        "deep_quality_handoff_outline_invalid",
    )
    audit = lineage.get("assertion_audit")
    source_copy = lineage.get("source_copy")
    reader = lineage.get("reader_value")
    search_ai = lineage.get("search_ai")
    if not all(
        isinstance(value, dict)
        for value in (audit, source_copy, reader, search_ai)
    ):
        raise DeepQualityExecutionError("deep_quality_handoff_quality_refs_invalid")

    audit = cast(dict[str, object], audit)
    source_copy = cast(dict[str, object], source_copy)
    reader = cast(dict[str, object], reader)
    search_ai = cast(dict[str, object], search_ai)
    audit_id, audit_version, audit_hash = _ref(
        audit.get("artifact"),
        "deep_quality_handoff_audit_invalid",
    )
    source_copy_id, source_copy_version, source_copy_hash = _ref(
        source_copy.get("artifact"),
        "deep_quality_handoff_source_copy_invalid",
    )
    reader_id, reader_version, reader_hash = _ref(
        reader.get("artifact"),
        "deep_quality_handoff_reader_invalid",
    )
    search_id, search_version, search_hash = _ref(
        search_ai.get("artifact"),
        "deep_quality_handoff_search_invalid",
    )
    try:
        source = await load_deep_quality_input(
            session,
            writer_run_id=writer_run_id,
            source_draft_artifact_id=source_id,
            expected_source_draft_version=source_version,
            expected_source_draft_hash=source_hash,
            outline_artifact_id=outline_id,
            expected_outline_version=outline_version,
            expected_outline_hash=outline_hash,
            assertion_audit_artifact_id=audit_id,
            expected_assertion_audit_version=audit_version,
            expected_assertion_audit_hash=audit_hash,
            assertion_audit_quality_evaluation_id=_quality_id(
                audit.get("quality_evaluation"),
                "deep_quality_handoff_audit_eval_invalid",
            ),
            source_copy_artifact_id=source_copy_id,
            expected_source_copy_version=source_copy_version,
            expected_source_copy_hash=source_copy_hash,
            source_copy_quality_evaluation_id=_quality_id(
                source_copy.get("quality_evaluation"),
                "deep_quality_handoff_source_copy_eval_invalid",
            ),
            reader_value_artifact_id=reader_id,
            expected_reader_value_version=reader_version,
            expected_reader_value_hash=reader_hash,
            reader_value_quality_evaluation_id=_quality_id(
                reader.get("quality_evaluation"),
                "deep_quality_handoff_reader_eval_invalid",
            ),
            search_ai_artifact_id=search_id,
            expected_search_ai_version=search_version,
            expected_search_ai_hash=search_hash,
            search_ai_quality_evaluation_id=_quality_id(
                search_ai.get("quality_evaluation"),
                "deep_quality_handoff_search_eval_invalid",
            ),
            locale=handoff.locale,
        )
    except DeepQualityInputError as exc:
        raise DeepQualityExecutionError(
            "deep_quality_handoff_lineage_invalid",
            exc.code,
        ) from exc

    snapshot = await session.get(
        SettingsSnapshot,
        source.writer_input.writer_run.settings_snapshot_id,
    )
    if snapshot is None:
        raise DeepQualityExecutionError("deep_quality_settings_snapshot_missing")
    if payload != _handoff_payload(source, settings_snapshot=snapshot):
        raise DeepQualityExecutionError("deep_quality_handoff_snapshot_stale")
    return source


def _merge_dimensions(
    authoritative: dict[str, DeepQualityDimension],
    semantic: tuple[DeepQualityDimension, ...],
) -> tuple[DeepQualityDimension, ...]:
    if set(authoritative) != set(AUTHORITATIVE_DEEP_QUALITY_DIMENSIONS):
        raise DeepQualityExecutionError("deep_quality_authoritative_dimensions_invalid")
    if {item.key for item in semantic} != set(SEMANTIC_MODEL_DIMENSIONS):
        raise DeepQualityExecutionError("deep_quality_semantic_dimensions_invalid")
    by_key = {**authoritative, **{item.key: item for item in semantic}}
    try:
        return tuple(by_key[key] for key in DEEP_QUALITY_DIMENSIONS)
    except KeyError as exc:
        raise DeepQualityExecutionError(
            "deep_quality_combined_dimensions_incomplete"
        ) from exc


def _evaluation_findings(
    source: DeepQualityInput,
    assessment: DeepQualityAssessment,
) -> dict[str, object]:
    return {
        "source_draft_id": str(source.source_artifact.id),
        "source_draft_hash": source.source_artifact.content_hash,
        "verdict": assessment.verdict,
        "dimensions": [item.to_dict() for item in assessment.dimensions],
        "fail_count": sum(item.result == "fail" for item in assessment.dimensions),
        "warn_count": sum(item.result == "warn" for item in assessment.dimensions),
        "authoritative_dimension_count": len(AUTHORITATIVE_DEEP_QUALITY_DIMENSIONS),
        "semantic_dimension_count": len(SEMANTIC_MODEL_DIMENSIONS),
        "numeric_score_used": False,
    }


def _artifact_payload(
    *,
    source: DeepQualityInput,
    assessment: DeepQualityAssessment,
    run: ContentRun,
    step: StepRun,
    manifest: ContextManifest,
    provider: str,
    model_name: str,
    prompt_version: str,
    recipe_version: str,
) -> dict[str, object]:
    return {
        "schema_version": DEEP_QUALITY_SCHEMA_VERSION,
        "artifact_type": DEEP_QUALITY_ARTIFACT_TYPE,
        "generator_version": DEEP_QUALITY_GENERATOR_VERSION,
        "locale": source.writer_input.locale,
        "lineage": _lineage_payload(source),
        "assessment": assessment.to_dict(),
        "generator": {
            "semantic_generator_version": DEEP_QUALITY_SEMANTIC_GENERATOR_VERSION,
            "evaluator_key": DEEP_QUALITY_EVALUATOR_KEY,
            "evaluator_version": DEEP_QUALITY_EVALUATOR_VERSION,
            "provider": provider,
            "model": model_name,
            "prompt_version": prompt_version,
            "recipe_version": recipe_version,
        },
        "execution_context": {
            "run_id": str(run.id),
            "step_run_id": str(step.id),
            "context_manifest_id": str(manifest.id),
            "context_manifest_hash": manifest.content_hash,
        },
        "routing_policy": {
            "numeric_score_used": False,
            "semantic_model_can_override_authoritative_dimensions": False,
            "founder_final_approval_separate": True,
            "auto_publish": False,
        },
    }


async def _load_existing(
    session: AsyncSession,
    *,
    source: DeepQualityInput,
    run: ContentRun,
    handoff: Artifact,
    step: StepRun,
    manifest: ContextManifest,
    provider: str,
    model_name: str,
    prompt_version: str,
    recipe_version: str,
) -> DeepQualityGateResult | None:
    artifacts = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == run.id,
                    Artifact.step_run_id == step.id,
                    Artifact.artifact_type == DEEP_QUALITY_ARTIFACT_TYPE,
                    Artifact.locale == source.writer_input.locale,
                )
            )
        ).all()
    )
    if not artifacts:
        return None
    if len(artifacts) != 1:
        raise DeepQualityExecutionError("deep_quality_artifact_conflict")
    artifact = artifacts[0]
    payload = artifact.content_json
    if (
        not isinstance(payload, dict)
        or _hash(payload) != artifact.content_hash
        or payload.get("lineage") != _lineage_payload(source)
        or payload.get("generator_version") != DEEP_QUALITY_GENERATOR_VERSION
    ):
        raise DeepQualityExecutionError("deep_quality_artifact_stale")
    assessment_payload = payload.get("assessment")
    try:
        assessment = validate_deep_quality_output(
            assessment_payload,
            locale=source.writer_input.locale,
        )
    except DeepQualityError as exc:
        raise DeepQualityExecutionError(
            "deep_quality_artifact_assessment_invalid",
            exc.code,
        ) from exc

    try:
        authoritative = derive_authoritative_deep_quality_dimensions(source)
    except DeepQualityAuthorityError as exc:
        raise DeepQualityExecutionError(
            "deep_quality_authoritative_derivation_invalid",
            exc.code,
        ) from exc
    persisted_by_key = {item.key: item for item in assessment.dimensions}
    for key, expected in authoritative.items():
        if persisted_by_key.get(key) != expected:
            raise DeepQualityExecutionError(
                "deep_quality_authoritative_dimension_stale",
                key,
            )
    expected_payload = _artifact_payload(
        source=source,
        assessment=assessment,
        run=run,
        step=step,
        manifest=manifest,
        provider=provider,
        model_name=model_name,
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )
    if payload != expected_payload:
        raise DeepQualityExecutionError("deep_quality_artifact_snapshot_stale")

    evaluations = list(
        (
            await session.scalars(
                select(QualityEvaluation).where(
                    QualityEvaluation.run_id == run.id,
                    QualityEvaluation.artifact_id == artifact.id,
                    QualityEvaluation.evaluator_key == DEEP_QUALITY_EVALUATOR_KEY,
                )
            )
        ).all()
    )
    if len(evaluations) != 1:
        raise DeepQualityExecutionError("deep_quality_evaluation_conflict")
    evaluation = evaluations[0]
    if (
        evaluation.evaluator_version != DEEP_QUALITY_EVALUATOR_VERSION
        or evaluation.evaluator_type != "model"
        or evaluation.result != assessment.verdict
        or evaluation.score is not None
        or evaluation.findings_json != _evaluation_findings(source, assessment)
    ):
        raise DeepQualityExecutionError("deep_quality_evaluation_stale")
    return DeepQualityGateResult(
        eval_run=run,
        handoff=handoff,
        step_run=step,
        artifact=artifact,
        evaluation=evaluation,
        assessment=assessment,
        model_attempts=0,
        reused=True,
    )


async def load_persisted_deep_quality_result(
    session: AsyncSession,
    *,
    source: DeepQualityInput,
    artifact_id: UUID,
    evaluation_id: UUID,
) -> DeepQualityGateResult:
    artifact = await session.get(Artifact, artifact_id)
    evaluation = await session.get(QualityEvaluation, evaluation_id)
    if (
        artifact is None
        or evaluation is None
        or artifact.artifact_type != DEEP_QUALITY_ARTIFACT_TYPE
        or artifact.locale != source.writer_input.locale
        or artifact.version != 1
        or artifact.step_run_id is None
        or evaluation.run_id != artifact.run_id
        or evaluation.artifact_id != artifact.id
    ):
        raise DeepQualityExecutionError("deep_quality_persisted_binding_invalid")

    run = await session.get(ContentRun, artifact.run_id)
    step = await session.get(StepRun, artifact.step_run_id)
    task_key = deep_quality_task_key(source.writer_input.locale)
    if (
        run is None
        or step is None
        or step.run_id != run.id
        or run.run_mode != "eval"
        or run.project_id != source.writer_input.writer_run.project_id
        or run.content_case_id != source.writer_input.writer_run.content_case_id
        or run.locale_variant_id != source.writer_input.locale_variant.id
        or run.settings_snapshot_id
        != source.writer_input.writer_run.settings_snapshot_id
        or run.current_step != task_key
        or run.status not in {"running", "completed"}
        or step.step_key != task_key
        or step.status not in {"running", "completed"}
    ):
        raise DeepQualityExecutionError("deep_quality_persisted_execution_invalid")

    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None:
        raise DeepQualityExecutionError("deep_quality_settings_snapshot_missing")
    handoffs = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == run.id,
                    Artifact.artifact_type
                    == DEEP_QUALITY_HANDOFF_ARTIFACT_TYPE,
                    Artifact.locale == source.writer_input.locale,
                )
            )
        ).all()
    )
    if len(handoffs) != 1:
        raise DeepQualityExecutionError("deep_quality_handoff_conflict")
    handoff = handoffs[0]
    expected_handoff = _handoff_payload(
        source,
        settings_snapshot=snapshot,
    )
    if (
        handoff.version != 1
        or handoff.step_run_id is not None
        or handoff.content_json != expected_handoff
        or handoff.content_hash != _hash(expected_handoff)
    ):
        raise DeepQualityExecutionError("deep_quality_handoff_snapshot_invalid")

    payload = artifact.content_json
    if (
        not isinstance(payload, dict)
        or _hash(payload) != artifact.content_hash
        or payload.get("schema_version") != DEEP_QUALITY_SCHEMA_VERSION
        or payload.get("artifact_type") != DEEP_QUALITY_ARTIFACT_TYPE
        or payload.get("generator_version") != DEEP_QUALITY_GENERATOR_VERSION
        or payload.get("locale") != source.writer_input.locale
        or payload.get("lineage") != _lineage_payload(source)
    ):
        raise DeepQualityExecutionError("deep_quality_artifact_stale")

    generator = payload.get("generator")
    execution_context = payload.get("execution_context")
    routing_policy = payload.get("routing_policy")
    if (
        not isinstance(generator, dict)
        or generator.get("semantic_generator_version")
        != DEEP_QUALITY_SEMANTIC_GENERATOR_VERSION
        or generator.get("evaluator_key") != DEEP_QUALITY_EVALUATOR_KEY
        or generator.get("evaluator_version")
        != DEEP_QUALITY_EVALUATOR_VERSION
        or not isinstance(execution_context, dict)
        or routing_policy
        != {
            "numeric_score_used": False,
            "semantic_model_can_override_authoritative_dimensions": False,
            "founder_final_approval_separate": True,
            "auto_publish": False,
        }
    ):
        raise DeepQualityExecutionError("deep_quality_artifact_stale")

    provider = generator.get("provider")
    model_name = generator.get("model")
    prompt_version = generator.get("prompt_version")
    recipe_version = generator.get("recipe_version")
    context_manifest_id = execution_context.get("context_manifest_id")
    context_manifest_hash = execution_context.get("context_manifest_hash")
    if (
        not isinstance(provider, str)
        or not provider.strip()
        or not isinstance(model_name, str)
        or not model_name.strip()
        or not isinstance(prompt_version, str)
        or not prompt_version.strip()
        or not isinstance(recipe_version, str)
        or not recipe_version.strip()
        or not isinstance(context_manifest_id, str)
        or not isinstance(context_manifest_hash, str)
    ):
        raise DeepQualityExecutionError("deep_quality_artifact_generator_invalid")
    try:
        manifest_id = UUID(context_manifest_id)
    except ValueError as exc:
        raise DeepQualityExecutionError(
            "deep_quality_context_manifest_invalid"
        ) from exc
    manifest = await session.get(ContextManifest, manifest_id)
    bundle = source.writer_input.outline_input.bundle
    if (
        manifest is None
        or manifest.run_id != run.id
        or manifest.step_run_id != step.id
        or manifest.settings_snapshot_id != run.settings_snapshot_id
        or manifest.content_hash != context_manifest_hash
        or manifest.prompt_version != prompt_version
        or manifest.recipe_version != recipe_version
        or manifest.evidence_set_id != bundle.evidence_set_id
        or manifest.originality_pack_id != bundle.originality_pack_id
        or execution_context
        != {
            "run_id": str(run.id),
            "step_run_id": str(step.id),
            "context_manifest_id": str(manifest.id),
            "context_manifest_hash": manifest.content_hash,
        }
    ):
        raise DeepQualityExecutionError("deep_quality_context_manifest_mismatch")

    try:
        assessment = validate_deep_quality_output(
            payload.get("assessment"),
            locale=source.writer_input.locale,
        )
        authoritative = derive_authoritative_deep_quality_dimensions(source)
    except DeepQualityError as exc:
        raise DeepQualityExecutionError(
            "deep_quality_artifact_assessment_invalid",
            exc.code,
        ) from exc
    except DeepQualityAuthorityError as exc:
        raise DeepQualityExecutionError(
            "deep_quality_authoritative_derivation_invalid",
            exc.code,
        ) from exc

    persisted_by_key = {item.key: item for item in assessment.dimensions}
    for key, expected in authoritative.items():
        if persisted_by_key.get(key) != expected:
            raise DeepQualityExecutionError(
                "deep_quality_authoritative_dimension_stale",
                key,
            )

    expected_payload = _artifact_payload(
        source=source,
        assessment=assessment,
        run=run,
        step=step,
        manifest=manifest,
        provider=provider.strip(),
        model_name=model_name.strip(),
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )
    if payload != expected_payload:
        raise DeepQualityExecutionError("deep_quality_artifact_snapshot_stale")
    if (
        evaluation.evaluator_key != DEEP_QUALITY_EVALUATOR_KEY
        or evaluation.evaluator_version != DEEP_QUALITY_EVALUATOR_VERSION
        or evaluation.evaluator_type != "model"
        or evaluation.result != assessment.verdict
        or evaluation.score is not None
        or evaluation.findings_json
        != _evaluation_findings(source, assessment)
    ):
        raise DeepQualityExecutionError("deep_quality_evaluation_stale")

    return DeepQualityGateResult(
        eval_run=run,
        handoff=handoff,
        step_run=step,
        artifact=artifact,
        evaluation=evaluation,
        assessment=assessment,
        model_attempts=0,
        reused=True,
    )


async def evaluate_deep_quality(
    session: AsyncSession,
    *,
    source: DeepQualityInput,
    eval_run_id: UUID,
    step_run_id: UUID,
    handoff_artifact_id: UUID,
    model: DeepQualitySemanticModelPort,
    provider: str,
    model_name: str,
    context_manifest_id: UUID,
    prompt_version: str,
    recipe_version: str,
    max_attempts: int = 2,
) -> DeepQualityGateResult:
    run = await session.get(ContentRun, eval_run_id)
    step = await session.get(StepRun, step_run_id)
    handoff = await session.get(Artifact, handoff_artifact_id)
    manifest = await session.get(ContextManifest, context_manifest_id)
    task_key = deep_quality_task_key(source.writer_input.locale)
    if (
        run is None
        or step is None
        or handoff is None
        or manifest is None
        or step.run_id != run.id
        or handoff.run_id != run.id
        or handoff.step_run_id is not None
        or run.run_mode != "eval"
        or run.status not in {"running", "completed"}
        or run.current_step != task_key
        or step.step_key != task_key
        or step.status not in {"running", "completed"}
        or manifest.run_id != run.id
        or manifest.step_run_id != step.id
        or manifest.settings_snapshot_id != run.settings_snapshot_id
        or manifest.prompt_version != prompt_version
        or manifest.recipe_version != recipe_version
    ):
        raise DeepQualityExecutionError("deep_quality_execution_binding_invalid")

    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None:
        raise DeepQualityExecutionError("deep_quality_settings_snapshot_missing")
    expected_handoff = _handoff_payload(
        source,
        settings_snapshot=snapshot,
    )
    if (
        handoff.artifact_type != DEEP_QUALITY_HANDOFF_ARTIFACT_TYPE
        or handoff.locale != source.writer_input.locale
        or handoff.version != 1
        or handoff.content_json != expected_handoff
        or handoff.content_hash != _hash(expected_handoff)
    ):
        raise DeepQualityExecutionError("deep_quality_handoff_snapshot_invalid")
    bundle = source.writer_input.outline_input.bundle
    if (
        manifest.evidence_set_id != bundle.evidence_set_id
        or manifest.originality_pack_id != bundle.originality_pack_id
    ):
        raise DeepQualityExecutionError("deep_quality_context_manifest_mismatch")
    if not provider.strip() or not model_name.strip():
        raise DeepQualityExecutionError("deep_quality_model_metadata_required")
    identity_resolver = getattr(model, "resolved_model_identity", None)
    if callable(identity_resolver):
        identity = identity_resolver()
        if identity != (provider.strip(), model_name.strip()):
            raise DeepQualityExecutionError("deep_quality_model_route_mismatch")

    existing = await _load_existing(
        session,
        source=source,
        run=run,
        handoff=handoff,
        step=step,
        manifest=manifest,
        provider=provider.strip(),
        model_name=model_name.strip(),
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )
    if existing is not None:
        return existing

    try:
        authoritative = derive_authoritative_deep_quality_dimensions(source)
    except DeepQualityAuthorityError as exc:
        raise DeepQualityExecutionError(
            "deep_quality_authoritative_derivation_invalid",
            exc.code,
        ) from exc
    if any(item.result == "fail" for item in authoritative.values()):
        raise DeepQualityExecutionError("deep_quality_authoritative_blocked")

    try:
        semantic_result = await evaluate_deep_quality_semantics(
            source,
            model=model,
            max_attempts=max_attempts,
        )
        assessment = build_deep_quality_assessment(
            locale=source.writer_input.locale,
            dimensions=_merge_dimensions(
                authoritative,
                semantic_result.dimensions,
            ),
        )
    except (DeepQualitySemanticError, DeepQualityError) as exc:
        raise DeepQualityExecutionError(
            "deep_quality_semantic_evaluation_invalid",
            getattr(exc, "code", exc.__class__.__name__),
        ) from exc

    payload = _artifact_payload(
        source=source,
        assessment=assessment,
        run=run,
        step=step,
        manifest=manifest,
        provider=provider.strip(),
        model_name=model_name.strip(),
        prompt_version=prompt_version,
        recipe_version=recipe_version,
    )
    artifact = Artifact(
        run_id=run.id,
        step_run_id=step.id,
        artifact_type=DEEP_QUALITY_ARTIFACT_TYPE,
        locale=source.writer_input.locale,
        version=1,
        content_json=payload,
        content_hash=_hash(payload),
    )
    session.add(artifact)
    await session.flush()
    step.output_artifact_refs_json = [
        *step.output_artifact_refs_json,
        str(artifact.id),
    ]
    evaluation = QualityEvaluation(
        run_id=run.id,
        artifact_id=artifact.id,
        evaluator_key=DEEP_QUALITY_EVALUATOR_KEY,
        evaluator_version=DEEP_QUALITY_EVALUATOR_VERSION,
        evaluator_type="model",
        result=assessment.verdict,
        score=None,
        severity=(
            "high"
            if assessment.verdict == "fail"
            else "medium"
            if assessment.verdict == "warn"
            else None
        ),
        findings_json=_evaluation_findings(source, assessment),
    )
    session.add(evaluation)
    await session.flush()
    return DeepQualityGateResult(
        eval_run=run,
        handoff=handoff,
        step_run=step,
        artifact=artifact,
        evaluation=evaluation,
        assessment=assessment,
        model_attempts=semantic_result.model_attempts,
        reused=False,
    )


__all__ = [
    "DEEP_QUALITY_ARTIFACT_TYPE",
    "DEEP_QUALITY_EVALUATOR_KEY",
    "DEEP_QUALITY_EVALUATOR_VERSION",
    "DEEP_QUALITY_GENERATOR_VERSION",
    "DEEP_QUALITY_HANDOFF_ARTIFACT_TYPE",
    "DEEP_QUALITY_TASK_KEYS",
    "DeepQualityExecutionError",
    "DeepQualityGateResult",
    "deep_quality_task_key",
    "ensure_deep_quality_run",
    "evaluate_deep_quality",
    "load_deep_quality_input_from_handoff",
    "load_persisted_deep_quality_result",
]
