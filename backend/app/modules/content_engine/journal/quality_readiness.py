"""QA-01 Reader Value and Search/AI readiness evaluation for Journal content.

The two evaluators are deliberately separate:
- Reader Value answers whether the exact revised draft helps the intended reader.
- Search/AI Readiness runs only after Reader Value is not FAIL and checks discovery hygiene.

Neither evaluator may override factual/source hard gates, publish content, or use a numeric
aggregate score as a routing decision.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.journal.source_copy import (
    SOURCE_COPY_EVALUATOR_KEY,
    SOURCE_COPY_EVALUATOR_VERSION,
)
from app.modules.content_engine.journal.writer import (
    JournalDraft,
    WriterGenerationError,
    WriterInput,
    _canonical_hash,
    _dict,
    _validate_model_output,
    load_writer_input,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    SettingsSnapshot,
)
from app.modules.harness.models import (
    Artifact,
    ContentRun,
    ContextManifest,
    QualityEvaluation,
    StepRun,
    utc_now,
)

QUALITY_READINESS_SCHEMA_VERSION = 1
QUALITY_READINESS_GENERATOR_VERSION = "qa01.journal_quality_readiness.v1"
READER_VALUE_EVALUATOR_KEY = "reader_value_gate"
READER_VALUE_EVALUATOR_VERSION = "qa01.reader_value.v1"
SEARCH_AI_EVALUATOR_KEY = "search_ai_readiness"
SEARCH_AI_EVALUATOR_VERSION = "qa01.search_ai_readiness.v1"

READER_VALUE_TASK_KEYS = {
    "vi-VN": "reader_value_vi",
    "en": "reader_value_en",
}
SEARCH_AI_TASK_KEYS = {
    "vi-VN": "search_ai_readiness_vi",
    "en": "search_ai_readiness_en",
}
READINESS_HANDOFF_TYPES = {
    "reader_value": "reader_value_handoff",
    "search_ai": "search_ai_readiness_handoff",
}
READINESS_ARTIFACT_TYPES = {
    "reader_value": "reader_value_evaluation",
    "search_ai": "search_ai_readiness_evaluation",
}
READINESS_CRITERIA = {
    "reader_value": (
        "primary_problem_answered",
        "reader_transformation",
        "practical_value",
        "non_generic",
        "originality_visible",
        "conversion_integrity",
    ),
    "search_ai": (
        "intent_match",
        "title_heading_coherence",
        "answer_passage",
        "entity_clarity",
        "internal_links",
        "metadata_readiness",
        "structured_data_fit",
        "freshness",
        "keyword_stuffing",
        "fake_faq",
    ),
}
_ALLOWED_RESULTS = {"pass", "warn", "fail"}


class QualityReadinessError(ValueError):
    """Stable fail-closed QA-01 error."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


class QualityReadinessModelPort(Protocol):
    async def generate(
        self,
        *,
        input_bundle: dict[str, object],
        attempt: int,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class ReadinessCriterion:
    key: str
    result: str
    finding: str
    repair_suggestion: str

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "result": self.result,
            "finding": self.finding,
            "repair_suggestion": self.repair_suggestion,
        }


@dataclass(frozen=True, slots=True)
class QualityReadinessInput:
    stage: str
    writer_input: WriterInput
    source_artifact: Artifact
    source_draft: JournalDraft
    content_case: ContentCase
    opportunity: ContentOpportunity
    source_copy_artifact: Artifact
    source_copy_evaluation: QualityEvaluation
    reader_value_artifact: Artifact | None
    reader_value_evaluation: QualityEvaluation | None
    model_input: dict[str, object]


@dataclass(frozen=True, slots=True)
class QualityReadinessResult:
    eval_run: ContentRun
    handoff: Artifact
    step_run: StepRun
    artifact: Artifact
    evaluation: QualityEvaluation
    result: str
    criteria: tuple[ReadinessCriterion, ...]
    summary: str
    model_attempts: int
    reused: bool


def readiness_task_key(stage: str, locale: str) -> str:
    mapping = READER_VALUE_TASK_KEYS if stage == "reader_value" else SEARCH_AI_TASK_KEYS
    if stage not in {"reader_value", "search_ai"} or locale not in mapping:
        raise QualityReadinessError("quality_readiness_stage_locale_invalid")
    return mapping[locale]


def _ref(artifact: Artifact) -> dict[str, object]:
    return {
        "id": str(artifact.id),
        "version": artifact.version,
        "content_hash": artifact.content_hash,
    }


def _quality_ref(evaluation: QualityEvaluation) -> dict[str, object]:
    return {
        "id": str(evaluation.id),
        "result": evaluation.result,
        "evaluator_key": evaluation.evaluator_key,
        "evaluator_version": evaluation.evaluator_version,
    }


def _exact_dict(value: object, keys: set[str], code: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise QualityReadinessError(code)
    return cast(dict[str, object], value)


def _nonempty_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualityReadinessError(code)
    return value.strip()


def _result(value: object, code: str) -> str:
    if not isinstance(value, str) or value not in _ALLOWED_RESULTS:
        raise QualityReadinessError(code)
    return value


def _aggregate_result(criteria: tuple[ReadinessCriterion, ...]) -> str:
    if any(item.result == "fail" for item in criteria):
        return "fail"
    if any(item.result == "warn" for item in criteria):
        return "warn"
    return "pass"


def validate_quality_readiness_output(
    raw: object,
    *,
    stage: str,
    locale: str,
) -> tuple[str, tuple[ReadinessCriterion, ...], str]:
    payload = _exact_dict(
        raw,
        {"locale", "result", "summary", "criteria"},
        "quality_readiness_output_schema_invalid",
    )
    if payload.get("locale") != locale:
        raise QualityReadinessError("quality_readiness_output_locale_mismatch")
    declared_result = _result(
        payload.get("result"),
        "quality_readiness_output_result_invalid",
    )
    summary = _nonempty_text(
        payload.get("summary"),
        "quality_readiness_output_summary_invalid",
    )
    raw_criteria = payload.get("criteria")
    expected = READINESS_CRITERIA.get(stage)
    if expected is None or not isinstance(raw_criteria, list):
        raise QualityReadinessError("quality_readiness_output_criteria_invalid")

    parsed: list[ReadinessCriterion] = []
    for raw_item in raw_criteria:
        item = _exact_dict(
            raw_item,
            {"key", "result", "finding", "repair_suggestion"},
            "quality_readiness_output_criterion_invalid",
        )
        key = _nonempty_text(item.get("key"), "quality_readiness_output_criterion_key_invalid")
        raw_repair = item.get("repair_suggestion")
        if not isinstance(raw_repair, str):
            raise QualityReadinessError(
                "quality_readiness_output_criterion_repair_invalid"
            )
        repair_suggestion = raw_repair.strip()
        criterion_result = _result(
            item.get("result"),
            "quality_readiness_output_criterion_result_invalid",
        )
        if criterion_result in {"warn", "fail"} and not repair_suggestion:
            raise QualityReadinessError(
                "quality_readiness_output_criterion_repair_required"
            )
        parsed.append(
            ReadinessCriterion(
                key=key,
                result=criterion_result,
                finding=_nonempty_text(
                    item.get("finding"),
                    "quality_readiness_output_criterion_finding_invalid",
                ),
                repair_suggestion=repair_suggestion,
            )
        )

    keys = tuple(item.key for item in parsed)
    if keys != expected or len(set(keys)) != len(keys):
        raise QualityReadinessError("quality_readiness_output_criteria_mismatch")
    criteria = tuple(parsed)
    deterministic_result = _aggregate_result(criteria)
    if declared_result != deterministic_result:
        raise QualityReadinessError("quality_readiness_output_result_mismatch")
    return deterministic_result, criteria, summary


def _source_payload(artifact: Artifact, writer_input: WriterInput) -> JournalDraft:
    if (
        artifact.artifact_type != "journal_draft"
        or artifact.run_id != writer_input.writer_run.id
        or artifact.locale != writer_input.locale
        or not isinstance(artifact.content_json, dict)
        or _canonical_hash(artifact.content_json) != artifact.content_hash
    ):
        raise QualityReadinessError("quality_readiness_source_draft_snapshot_invalid")
    draft_payload = _dict(
        artifact.content_json.get("draft"),
        "quality_readiness_source_draft_payload_invalid",
    )
    try:
        draft = _validate_model_output(draft_payload, writer_input=writer_input)
    except WriterGenerationError as exc:
        raise QualityReadinessError("quality_readiness_source_draft_invalid", exc.code) from exc
    if draft.to_dict() != draft_payload:
        raise QualityReadinessError("quality_readiness_source_draft_stale")
    return draft


async def _validated_evaluation(
    session: AsyncSession,
    *,
    artifact_id: UUID,
    evaluation_id: UUID,
    artifact_type: str,
    evaluator_key: str,
    source_artifact: Artifact,
    writer_input: WriterInput,
    allowed_results: set[str],
    evaluator_version: str | None = None,
) -> tuple[Artifact, QualityEvaluation]:
    artifact = await session.get(Artifact, artifact_id)
    evaluation = await session.get(QualityEvaluation, evaluation_id)
    if (
        artifact is None
        or artifact.artifact_type != artifact_type
        or artifact.locale != writer_input.locale
        or not isinstance(artifact.content_json, dict)
        or _canonical_hash(artifact.content_json) != artifact.content_hash
        or evaluation is None
        or evaluation.artifact_id != artifact.id
        or evaluation.run_id != artifact.run_id
        or evaluation.evaluator_key != evaluator_key
        or (evaluator_version is not None and evaluation.evaluator_version != evaluator_version)
        or evaluation.result not in allowed_results
    ):
        raise QualityReadinessError("quality_readiness_prerequisite_invalid")
    if artifact_type == "source_copy_check":
        summary = artifact.content_json.get("summary")
        if not isinstance(summary, dict) or summary.get("result") != evaluation.result:
            raise QualityReadinessError("quality_readiness_prerequisite_result_mismatch")
    elif artifact_type == READINESS_ARTIFACT_TYPES["reader_value"]:
        if (
            artifact.content_json.get("stage") != "reader_value"
            or artifact.content_json.get("result") != evaluation.result
        ):
            raise QualityReadinessError("quality_readiness_prerequisite_result_mismatch")

    eval_run = await session.get(ContentRun, artifact.run_id)
    if (
        eval_run is None
        or eval_run.run_mode != "eval"
        or eval_run.status != "completed"
        or eval_run.project_id != writer_input.writer_run.project_id
        or eval_run.content_case_id != writer_input.writer_run.content_case_id
        or eval_run.locale_variant_id != writer_input.locale_variant.id
        or eval_run.settings_snapshot_id != writer_input.writer_run.settings_snapshot_id
    ):
        raise QualityReadinessError("quality_readiness_prerequisite_run_invalid")
    payload_source = artifact.content_json.get("source_draft")
    if payload_source != _ref(source_artifact):
        raise QualityReadinessError("quality_readiness_prerequisite_source_mismatch")
    return artifact, evaluation


def _case_payload(case: ContentCase) -> dict[str, object]:
    return {
        "id": str(case.id),
        "audience_hypothesis_id": (
            str(case.audience_hypothesis_id) if case.audience_hypothesis_id else None
        ),
        "need_hypothesis_id": str(case.need_hypothesis_id),
        "content_opportunity_id": str(case.content_opportunity_id),
        "desired_action": case.desired_action,
        "content_hypothesis": case.content_hypothesis,
        "originality_statement": case.originality_statement,
        "reader_before": case.reader_before,
        "reader_after": case.reader_after,
    }


def _opportunity_payload(value: ContentOpportunity) -> dict[str, object]:
    return {
        "id": str(value.id),
        "reader": value.reader,
        "situation": value.situation,
        "need": value.need,
        "question": value.question,
        "intent": value.intent,
        "promise": value.promise,
        "what_is_actually_new": value.what_is_actually_new,
        "decision": value.decision,
        "priority": value.priority,
    }


def _variant_payload(writer_input: WriterInput) -> dict[str, object]:
    value = writer_input.locale_variant
    return {
        "id": str(value.id),
        "locale": value.locale,
        "content_role": value.content_role,
        "primary_question": value.primary_question,
        "primary_intent": value.primary_intent,
        "secondary_intent": value.secondary_intent,
        "primary_query": value.primary_query,
        "keyword_notes": copy.deepcopy(value.keyword_notes_json),
        "must_include": copy.deepcopy(value.must_include_json),
        "must_not_claim": copy.deepcopy(value.must_not_claim_json),
    }


def _editorial_context(writer_input: WriterInput) -> tuple[dict[str, object], dict[str, object]]:
    angle = writer_input.outline_input.approved_angle.candidate.to_dict()
    raw_pack = writer_input.outline_input.bundle.angle_model_input.get("originality_pack")
    if not isinstance(raw_pack, dict):
        raise QualityReadinessError("quality_readiness_originality_pack_missing")
    pack = copy.deepcopy(cast(dict[str, object], raw_pack))
    items = pack.get("items")
    if not isinstance(items, list) or not items:
        raise QualityReadinessError("quality_readiness_originality_pack_missing")
    return angle, pack


async def load_quality_readiness_input(
    session: AsyncSession,
    *,
    stage: str,
    writer_run_id: UUID,
    source_draft_artifact_id: UUID,
    expected_source_draft_version: int,
    expected_source_draft_hash: str,
    outline_artifact_id: UUID,
    expected_outline_version: int,
    expected_outline_hash: str,
    source_copy_artifact_id: UUID,
    source_copy_quality_evaluation_id: UUID,
    locale: str,
    reader_value_artifact_id: UUID | None = None,
    reader_value_quality_evaluation_id: UUID | None = None,
) -> QualityReadinessInput:
    if stage not in {"reader_value", "search_ai"}:
        raise QualityReadinessError("quality_readiness_stage_invalid")
    writer_input = await load_writer_input(
        session,
        writer_run_id=writer_run_id,
        outline_artifact_id=outline_artifact_id,
        expected_outline_version=expected_outline_version,
        expected_outline_hash=expected_outline_hash,
        locale=locale,
    )
    source = await session.get(Artifact, source_draft_artifact_id)
    if (
        source is None
        or source.version != expected_source_draft_version
        or source.content_hash != expected_source_draft_hash
    ):
        raise QualityReadinessError("quality_readiness_source_draft_snapshot_mismatch")
    draft = _source_payload(source, writer_input)
    case = await session.get(ContentCase, writer_input.writer_run.content_case_id)
    if case is None or case.content_type != "journal":
        raise QualityReadinessError("quality_readiness_content_case_missing")
    opportunity = await session.get(ContentOpportunity, case.content_opportunity_id)
    if opportunity is None or opportunity.project_id != case.project_id:
        raise QualityReadinessError("quality_readiness_opportunity_missing")

    approved_angle, originality_pack = _editorial_context(writer_input)

    source_copy, source_copy_eval = await _validated_evaluation(
        session,
        artifact_id=source_copy_artifact_id,
        evaluation_id=source_copy_quality_evaluation_id,
        artifact_type="source_copy_check",
        evaluator_key=SOURCE_COPY_EVALUATOR_KEY,
        source_artifact=source,
        writer_input=writer_input,
        allowed_results={"pass", "warn"},
        evaluator_version=SOURCE_COPY_EVALUATOR_VERSION,
    )

    reader_artifact: Artifact | None = None
    reader_eval: QualityEvaluation | None = None
    if stage == "search_ai":
        if reader_value_artifact_id is None or reader_value_quality_evaluation_id is None:
            raise QualityReadinessError("quality_readiness_reader_value_required")
        reader_artifact, reader_eval = await _validated_evaluation(
            session,
            artifact_id=reader_value_artifact_id,
            evaluation_id=reader_value_quality_evaluation_id,
            artifact_type=READINESS_ARTIFACT_TYPES["reader_value"],
            evaluator_key=READER_VALUE_EVALUATOR_KEY,
            source_artifact=source,
            writer_input=writer_input,
            allowed_results={"pass", "warn"},
            evaluator_version=READER_VALUE_EVALUATOR_VERSION,
        )
        expected_source_copy = {
            "artifact": _ref(source_copy),
            "quality_evaluation": _quality_ref(source_copy_eval),
        }
        reader_payload = reader_artifact.content_json
        if (
            not isinstance(reader_payload, dict)
            or reader_payload.get("source_copy") != expected_source_copy
        ):
            raise QualityReadinessError(
                "quality_readiness_reader_value_source_copy_mismatch"
            )
    elif reader_value_artifact_id is not None or reader_value_quality_evaluation_id is not None:
        raise QualityReadinessError("quality_readiness_reader_value_unexpected")

    model_input: dict[str, object] = {
        "locale": locale,
        "stage": stage,
        "source_draft_ref": _ref(source),
        "source_draft": draft.to_dict(),
        "content_case": _case_payload(case),
        "content_opportunity": _opportunity_payload(opportunity),
        "locale_variant": _variant_payload(writer_input),
        "approved_angle": approved_angle,
        "originality_pack": originality_pack,
        "source_copy": {
            "artifact": _ref(source_copy),
            "quality_evaluation": _quality_ref(source_copy_eval),
        },
        "evaluation_policy": {
            "criteria": list(READINESS_CRITERIA[stage]),
            "result_order": ["pass", "warn", "fail"],
            "no_numeric_score": True,
            "no_research": True,
            "no_rewrite": True,
            "reader_value_precedes_discovery": True,
            "seo_ai_cannot_override_reader_value": True,
        },
    }
    if reader_artifact is not None and reader_eval is not None:
        model_input["reader_value"] = {
            "artifact": _ref(reader_artifact),
            "quality_evaluation": _quality_ref(reader_eval),
        }

    return QualityReadinessInput(
        stage=stage,
        writer_input=writer_input,
        source_artifact=source,
        source_draft=draft,
        content_case=case,
        opportunity=opportunity,
        source_copy_artifact=source_copy,
        source_copy_evaluation=source_copy_eval,
        reader_value_artifact=reader_artifact,
        reader_value_evaluation=reader_eval,
        model_input=model_input,
    )


def _handoff_payload(
    value: QualityReadinessInput,
    *,
    task_key: str,
    settings_snapshot: SettingsSnapshot,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": QUALITY_READINESS_SCHEMA_VERSION,
        "artifact_type": READINESS_HANDOFF_TYPES[value.stage],
        "stage": value.stage,
        "task_key": task_key,
        "project_id": str(value.content_case.project_id),
        "content_case_id": str(value.content_case.id),
        "locale_variant": {
            "id": str(value.writer_input.locale_variant.id),
            "locale": value.writer_input.locale,
        },
        "source_writer_run_id": str(value.writer_input.writer_run.id),
        "source_draft": _ref(value.source_artifact),
        "journal_outline": _ref(value.writer_input.outline_artifact),
        "source_copy": {
            "artifact": _ref(value.source_copy_artifact),
            "quality_evaluation": _quality_ref(value.source_copy_evaluation),
        },
        "settings_snapshot": {
            "id": str(settings_snapshot.id),
            "content_hash": settings_snapshot.content_hash,
        },
    }
    if value.reader_value_artifact is not None and value.reader_value_evaluation is not None:
        payload["reader_value"] = {
            "artifact": _ref(value.reader_value_artifact),
            "quality_evaluation": _quality_ref(value.reader_value_evaluation),
        }
    return payload


async def ensure_quality_readiness_run(
    session: AsyncSession,
    *,
    source_input: QualityReadinessInput,
    task_key: str,
) -> tuple[ContentRun, Artifact, bool]:
    expected_task = readiness_task_key(source_input.stage, source_input.writer_input.locale)
    if task_key != expected_task:
        raise QualityReadinessError("quality_readiness_task_locale_mismatch")
    snapshot = await session.get(
        SettingsSnapshot,
        source_input.writer_input.writer_run.settings_snapshot_id,
    )
    if snapshot is None:
        raise QualityReadinessError("quality_readiness_settings_snapshot_missing")
    payload = _handoff_payload(source_input, task_key=task_key, settings_snapshot=snapshot)
    handoff_hash = _canonical_hash(payload)
    rows = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.artifact_type == READINESS_HANDOFF_TYPES[source_input.stage],
                    Artifact.content_hash == handoff_hash,
                    Artifact.locale == source_input.writer_input.locale,
                )
            )
        ).all()
    )
    reusable: list[tuple[ContentRun, Artifact]] = []
    for handoff in rows:
        if handoff.content_json != payload or handoff.step_run_id is not None:
            raise QualityReadinessError("quality_readiness_handoff_snapshot_invalid")
        run = await session.get(ContentRun, handoff.run_id)
        if (
            run is None
            or run.run_mode != "eval"
            or run.project_id != source_input.writer_input.writer_run.project_id
            or run.content_case_id != source_input.writer_input.writer_run.content_case_id
            or run.locale_variant_id != source_input.writer_input.locale_variant.id
            or run.settings_snapshot_id != source_input.writer_input.writer_run.settings_snapshot_id
        ):
            raise QualityReadinessError("quality_readiness_handoff_run_mismatch")
        if run.status not in {"failed", "cancelled"}:
            reusable.append((run, handoff))
    if len(reusable) > 1:
        raise QualityReadinessError("quality_readiness_reusable_run_duplicate")
    if reusable:
        return (*reusable[0], True)

    run = ContentRun(
        project_id=source_input.writer_input.writer_run.project_id,
        content_case_id=source_input.writer_input.writer_run.content_case_id,
        locale_variant_id=source_input.writer_input.locale_variant.id,
        content_item_id=source_input.writer_input.writer_run.content_item_id,
        run_mode="eval",
        status="pending",
        current_step=task_key,
        settings_snapshot_id=source_input.writer_input.writer_run.settings_snapshot_id,
        started_at=utc_now(),
    )
    session.add(run)
    await session.flush()
    handoff = Artifact(
        run_id=run.id,
        step_run_id=None,
        artifact_type=READINESS_HANDOFF_TYPES[source_input.stage],
        locale=source_input.writer_input.locale,
        version=1,
        content_json=payload,
        content_hash=handoff_hash,
    )
    session.add(handoff)
    await session.flush()
    return run, handoff, False


async def load_quality_readiness_input_from_handoff(
    session: AsyncSession,
    *,
    handoff_artifact_id: UUID,
) -> QualityReadinessInput:
    handoff = await session.get(Artifact, handoff_artifact_id)
    if (
        handoff is None
        or handoff.artifact_type not in set(READINESS_HANDOFF_TYPES.values())
        or not isinstance(handoff.content_json, dict)
        or _canonical_hash(handoff.content_json) != handoff.content_hash
    ):
        raise QualityReadinessError("quality_readiness_handoff_invalid")
    payload = handoff.content_json
    stage = payload.get("stage")
    source = payload.get("source_draft")
    outline = payload.get("journal_outline")
    source_copy = payload.get("source_copy")
    if (
        not isinstance(stage, str)
        or not isinstance(source, dict)
        or not isinstance(outline, dict)
        or not isinstance(source_copy, dict)
    ):
        raise QualityReadinessError("quality_readiness_handoff_payload_invalid")
    source_copy_artifact = source_copy.get("artifact")
    source_copy_eval = source_copy.get("quality_evaluation")
    if not isinstance(source_copy_artifact, dict) or not isinstance(source_copy_eval, dict):
        raise QualityReadinessError("quality_readiness_handoff_source_copy_invalid")
    raw_writer = payload.get("source_writer_run_id")
    raw_locale = handoff.locale
    if not isinstance(raw_writer, str) or not isinstance(raw_locale, str):
        raise QualityReadinessError("quality_readiness_handoff_binding_invalid")

    reader_artifact_id: UUID | None = None
    reader_evaluation_id: UUID | None = None
    raw_reader = payload.get("reader_value")
    try:
        if raw_reader is not None:
            if not isinstance(raw_reader, dict):
                raise QualityReadinessError("quality_readiness_handoff_reader_value_invalid")
            raw_reader_artifact = raw_reader.get("artifact")
            raw_reader_eval = raw_reader.get("quality_evaluation")
            if not isinstance(raw_reader_artifact, dict) or not isinstance(raw_reader_eval, dict):
                raise QualityReadinessError("quality_readiness_handoff_reader_value_invalid")
            reader_artifact_id = UUID(cast(str, raw_reader_artifact["id"]))
            reader_evaluation_id = UUID(cast(str, raw_reader_eval["id"]))

        return await load_quality_readiness_input(
            session,
            stage=stage,
            writer_run_id=UUID(raw_writer),
            source_draft_artifact_id=UUID(cast(str, source["id"])),
            expected_source_draft_version=cast(int, source["version"]),
            expected_source_draft_hash=cast(str, source["content_hash"]),
            outline_artifact_id=UUID(cast(str, outline["id"])),
            expected_outline_version=cast(int, outline["version"]),
            expected_outline_hash=cast(str, outline["content_hash"]),
            source_copy_artifact_id=UUID(cast(str, source_copy_artifact["id"])),
            source_copy_quality_evaluation_id=UUID(cast(str, source_copy_eval["id"])),
            locale=raw_locale,
            reader_value_artifact_id=reader_artifact_id,
            reader_value_quality_evaluation_id=reader_evaluation_id,
        )
    except QualityReadinessError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise QualityReadinessError("quality_readiness_handoff_binding_invalid") from exc


def _evaluation_metadata(stage: str) -> tuple[str, str, str]:
    if stage == "reader_value":
        return (
            READER_VALUE_EVALUATOR_KEY,
            READER_VALUE_EVALUATOR_VERSION,
            READINESS_ARTIFACT_TYPES[stage],
        )
    if stage == "search_ai":
        return (
            SEARCH_AI_EVALUATOR_KEY,
            SEARCH_AI_EVALUATOR_VERSION,
            READINESS_ARTIFACT_TYPES[stage],
        )
    raise QualityReadinessError("quality_readiness_stage_invalid")


def _evaluation_payload(
    *,
    source_input: QualityReadinessInput,
    run: ContentRun,
    step: StepRun,
    criteria: tuple[ReadinessCriterion, ...],
    result: str,
    summary: str,
    provider: str,
    model_name: str,
    prompt_version: str,
    recipe_version: str,
) -> dict[str, object]:
    evaluator_key, evaluator_version, artifact_type = _evaluation_metadata(source_input.stage)
    return {
        "schema_version": QUALITY_READINESS_SCHEMA_VERSION,
        "artifact_type": artifact_type,
        "stage": source_input.stage,
        "locale": source_input.writer_input.locale,
        "source_writer_run_id": str(source_input.writer_input.writer_run.id),
        "source_draft": _ref(source_input.source_artifact),
        "journal_outline": _ref(source_input.writer_input.outline_artifact),
        "source_copy": {
            "artifact": _ref(source_input.source_copy_artifact),
            "quality_evaluation": _quality_ref(source_input.source_copy_evaluation),
        },
        "reader_value": (
            {
                "artifact": _ref(source_input.reader_value_artifact),
                "quality_evaluation": _quality_ref(source_input.reader_value_evaluation),
            }
            if source_input.reader_value_artifact is not None
            and source_input.reader_value_evaluation is not None
            else None
        ),
        "result": result,
        "summary": summary,
        "criteria": [item.to_dict() for item in criteria],
        "generator": {
            "version": QUALITY_READINESS_GENERATOR_VERSION,
            "evaluator_key": evaluator_key,
            "evaluator_version": evaluator_version,
            "schema_version": QUALITY_READINESS_SCHEMA_VERSION,
            "provider": provider,
            "model": model_name,
            "prompt_version": prompt_version,
            "recipe_version": recipe_version,
        },
        "execution_context": {
            "run_id": str(run.id),
            "step_run_id": str(step.id),
        },
        "routing_policy": {
            "numeric_score_used": False,
            "reader_value_precedes_discovery": True,
            "seo_ai_can_override_reader_value": False,
        },
    }


async def evaluate_quality_readiness(
    session: AsyncSession,
    *,
    source_input: QualityReadinessInput,
    eval_run_id: UUID,
    step_run_id: UUID,
    handoff_artifact_id: UUID,
    model: QualityReadinessModelPort,
    provider: str,
    model_name: str,
    context_manifest_id: UUID,
    prompt_version: str,
    recipe_version: str,
    max_attempts: int = 2,
) -> QualityReadinessResult:
    if max_attempts < 1 or max_attempts > 2:
        raise QualityReadinessError("quality_readiness_attempts_invalid")
    run = await session.get(ContentRun, eval_run_id)
    step = await session.get(StepRun, step_run_id)
    handoff = await session.get(Artifact, handoff_artifact_id)
    manifest = await session.get(ContextManifest, context_manifest_id)
    if (
        run is None
        or step is None
        or handoff is None
        or step.run_id != run.id
        or handoff.run_id != run.id
        or handoff.step_run_id is not None
        or run.run_mode != "eval"
        or run.status not in {"running", "completed"}
        or run.current_step != readiness_task_key(
            source_input.stage,
            source_input.writer_input.locale,
        )
        or manifest is None
        or manifest.run_id != run.id
        or manifest.step_run_id != step.id
        or manifest.settings_snapshot_id != run.settings_snapshot_id
        or manifest.prompt_version != prompt_version
        or manifest.recipe_version != recipe_version
    ):
        raise QualityReadinessError("quality_readiness_execution_binding_invalid")
    if handoff.artifact_type != READINESS_HANDOFF_TYPES[source_input.stage]:
        raise QualityReadinessError("quality_readiness_handoff_type_mismatch")
    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None:
        raise QualityReadinessError("quality_readiness_settings_snapshot_missing")
    expected_handoff = _handoff_payload(
        source_input,
        task_key=readiness_task_key(
            source_input.stage,
            source_input.writer_input.locale,
        ),
        settings_snapshot=snapshot,
    )
    if (
        handoff.content_json != expected_handoff
        or handoff.content_hash != _canonical_hash(expected_handoff)
    ):
        raise QualityReadinessError("quality_readiness_handoff_snapshot_invalid")
    bundle = source_input.writer_input.outline_input.bundle
    if (
        manifest.evidence_set_id != bundle.evidence_set_id
        or manifest.originality_pack_id != bundle.originality_pack_id
    ):
        raise QualityReadinessError("quality_readiness_context_manifest_mismatch")
    if not provider.strip() or not model_name.strip():
        raise QualityReadinessError("quality_readiness_model_metadata_required")
    identity_resolver = getattr(model, "resolved_model_identity", None)
    if callable(identity_resolver):
        identity = identity_resolver()
        if (
            not isinstance(identity, tuple)
            or len(identity) != 2
            or identity != (provider.strip(), model_name.strip())
        ):
            raise QualityReadinessError("quality_readiness_model_route_mismatch")

    evaluator_key, evaluator_version, artifact_type = _evaluation_metadata(source_input.stage)
    existing = list(
        (
            await session.scalars(
                select(Artifact).where(
                    Artifact.run_id == run.id,
                    Artifact.step_run_id == step.id,
                    Artifact.artifact_type == artifact_type,
                    Artifact.locale == source_input.writer_input.locale,
                )
            )
        ).all()
    )
    if len(existing) > 1:
        raise QualityReadinessError("quality_readiness_artifact_conflict")
    if existing:
        artifact = existing[0]
        evaluations = list(
            (
                await session.scalars(
                    select(QualityEvaluation).where(
                        QualityEvaluation.run_id == run.id,
                        QualityEvaluation.artifact_id == artifact.id,
                        QualityEvaluation.evaluator_key == evaluator_key,
                    )
                )
            ).all()
        )
        if (
            len(evaluations) != 1
            or not isinstance(artifact.content_json, dict)
            or run.status != "completed"
            or step.status != "completed"
        ):
            raise QualityReadinessError("quality_readiness_evaluation_conflict")
        evaluation = evaluations[0]
        raw_criteria = artifact.content_json.get("criteria")
        if not isinstance(raw_criteria, list):
            raise QualityReadinessError("quality_readiness_artifact_invalid")
        validated = validate_quality_readiness_output(
            {
                "locale": source_input.writer_input.locale,
                "result": artifact.content_json.get("result"),
                "summary": artifact.content_json.get("summary"),
                "criteria": raw_criteria,
            },
            stage=source_input.stage,
            locale=source_input.writer_input.locale,
        )
        result, criteria, summary = validated
        if (
            artifact.content_hash != _canonical_hash(artifact.content_json)
            or artifact.content_json.get("source_draft") != _ref(source_input.source_artifact)
            or evaluation.result != result
            or evaluation.evaluator_version != evaluator_version
            or evaluation.score is not None
        ):
            raise QualityReadinessError("quality_readiness_artifact_stale")
        return QualityReadinessResult(
            eval_run=run,
            handoff=handoff,
            step_run=step,
            artifact=artifact,
            evaluation=evaluation,
            result=result,
            criteria=criteria,
            summary=summary,
            model_attempts=0,
            reused=True,
        )

    last_error: QualityReadinessError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            raw = await model.generate(
                input_bundle=copy.deepcopy(source_input.model_input),
                attempt=attempt,
            )
            result, criteria, summary = validate_quality_readiness_output(
                raw,
                stage=source_input.stage,
                locale=source_input.writer_input.locale,
            )
        except QualityReadinessError as exc:
            last_error = exc
            if attempt == max_attempts:
                raise QualityReadinessError(
                    "quality_readiness_model_output_invalid",
                    exc.code,
                ) from exc
            continue

        payload = _evaluation_payload(
            source_input=source_input,
            run=run,
            step=step,
            criteria=criteria,
            result=result,
            summary=summary,
            provider=provider.strip(),
            model_name=model_name.strip(),
            prompt_version=prompt_version,
            recipe_version=recipe_version,
        )
        artifact = Artifact(
            run_id=run.id,
            step_run_id=step.id,
            artifact_type=artifact_type,
            locale=source_input.writer_input.locale,
            version=1,
            content_json=payload,
            content_hash=_canonical_hash(payload),
        )
        session.add(artifact)
        await session.flush()
        fail_count = sum(item.result == "fail" for item in criteria)
        warn_count = sum(item.result == "warn" for item in criteria)
        evaluation = QualityEvaluation(
            run_id=run.id,
            artifact_id=artifact.id,
            evaluator_key=evaluator_key,
            evaluator_version=evaluator_version,
            evaluator_type="model",
            result=result,
            score=None,
            severity=("high" if result == "fail" else "medium" if result == "warn" else None),
            findings_json={
                "source_draft_id": str(source_input.source_artifact.id),
                "source_draft_hash": source_input.source_artifact.content_hash,
                "stage": source_input.stage,
                "summary": summary,
                "criteria": [item.to_dict() for item in criteria],
                "fail_count": fail_count,
                "warn_count": warn_count,
                "numeric_score_used": False,
            },
        )
        session.add(evaluation)
        await session.flush()
        return QualityReadinessResult(
            eval_run=run,
            handoff=handoff,
            step_run=step,
            artifact=artifact,
            evaluation=evaluation,
            result=result,
            criteria=criteria,
            summary=summary,
            model_attempts=attempt,
            reused=False,
        )
    raise QualityReadinessError("quality_readiness_model_output_invalid") from last_error


@dataclass(frozen=True, slots=True)
class PairwiseReadinessDecision:
    eligible: bool
    preference: str
    reasons: tuple[str, ...]


def compare_readiness_pair(
    *,
    baseline_reader_value: str,
    candidate_reader_value: str,
    baseline_search_ai: str,
    candidate_search_ai: str,
    human_preference: str | None,
) -> PairwiseReadinessDecision:
    """Pairwise helper that never lets discovery quality override Reader Value."""

    for value in (
        baseline_reader_value,
        candidate_reader_value,
        baseline_search_ai,
        candidate_search_ai,
    ):
        _result(value, "quality_readiness_pair_result_invalid")
    if human_preference not in {None, "baseline", "candidate", "inconclusive"}:
        raise QualityReadinessError("quality_readiness_pair_preference_invalid")

    reasons: list[str] = []
    baseline_eligible = baseline_reader_value != "fail" and baseline_search_ai != "fail"
    candidate_eligible = candidate_reader_value != "fail" and candidate_search_ai != "fail"
    if not candidate_eligible:
        reasons.append("candidate_fails_hard_quality_route")
        return PairwiseReadinessDecision(
            eligible=False,
            preference="baseline" if baseline_eligible else "inconclusive",
            reasons=tuple(reasons),
        )
    if not baseline_eligible:
        reasons.append("baseline_fails_hard_quality_route")
        return PairwiseReadinessDecision(
            eligible=True,
            preference="candidate",
            reasons=tuple(reasons),
        )
    reasons.append("both_candidates_pass_hard_quality_route")
    return PairwiseReadinessDecision(
        eligible=True,
        preference=human_preference or "inconclusive",
        reasons=tuple(reasons),
    )


__all__ = [
    "QUALITY_READINESS_GENERATOR_VERSION",
    "QUALITY_READINESS_SCHEMA_VERSION",
    "READINESS_ARTIFACT_TYPES",
    "READINESS_CRITERIA",
    "READINESS_HANDOFF_TYPES",
    "READER_VALUE_EVALUATOR_KEY",
    "READER_VALUE_EVALUATOR_VERSION",
    "READER_VALUE_TASK_KEYS",
    "SEARCH_AI_EVALUATOR_KEY",
    "SEARCH_AI_EVALUATOR_VERSION",
    "SEARCH_AI_TASK_KEYS",
    "PairwiseReadinessDecision",
    "QualityReadinessError",
    "QualityReadinessInput",
    "QualityReadinessModelPort",
    "QualityReadinessResult",
    "ReadinessCriterion",
    "compare_readiness_pair",
    "ensure_quality_readiness_run",
    "evaluate_quality_readiness",
    "load_quality_readiness_input",
    "load_quality_readiness_input_from_handoff",
    "readiness_task_key",
    "validate_quality_readiness_output",
]