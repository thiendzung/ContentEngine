"""LS-01 deterministic Lens candidates and versioned Lens Selection artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content_engine.content_coverage import (
    ContentCoverageError,
    build_content_coverage,
)
from app.modules.content_engine.models import (
    ContentCase,
    ContentOpportunity,
    HumanSelection,
    LocaleVariant,
    Project,
    SettingsSnapshot,
    SettingsVersion,
)
from app.modules.customer_intelligence.living_map import (
    CustomerMapError,
    customer_map_need_detail,
)
from app.modules.harness.models import Artifact, ContentRun, StepRun
from app.modules.system.settings_service import settings_hash

LENS_CANDIDATES_ARTIFACT_TYPE = "lens_candidates"
LENS_SELECTION_ARTIFACT_TYPE = "lens_selection"
LENS_SCHEMA_VERSION = 1
LENS_ORDER: tuple[str, ...] = (
    "DEFINITION",
    "MISCONCEPTION",
    "SIGNALS",
    "CAUSES",
    "METHOD",
    "CASE",
    "POV",
)
LensDecision = Literal["SELECT", "MERGE", "HOLD", "DROP"]
GuardStatus = Literal["PASS", "BLOCK"]
_ALLOWED_DECISIONS: frozenset[str] = frozenset(
    {"SELECT", "MERGE", "HOLD", "DROP"}
)
_SETTINGS_REF_RE = re.compile(
    r"^settings_version:([0-9a-fA-F-]{36}):v([1-9][0-9]*)$"
)
_UPSTREAM_BLOCKING_DECISIONS = {"MERGE", "LINK_ONLY", "DO_NOT_WRITE"}


class LensSelectionError(ValueError):
    """Fail-closed LS-01 error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class LensCandidateResult:
    artifact: Artifact
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class LensSelectionResult:
    artifact: Artifact
    payload: dict[str, object]


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clone(value: object) -> object:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LensSelectionError(code)
    return {str(key): item for key, item in value.items()}


def _records(value: object, code: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise LensSelectionError(code)
    output: list[dict[str, object]] = []
    for item in value:
        output.append(_dict(item, code))
    return output


def _strings(value: object, code: str) -> list[str]:
    if not isinstance(value, list):
        raise LensSelectionError(code)
    output: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise LensSelectionError(code)
        output.append(item.strip())
    return output


def _required_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LensSelectionError(code)
    return value.strip()


def _optional_uuid_text(value: object, code: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LensSelectionError(code)
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise LensSelectionError(code) from exc


def _settings_version_ref(row: SettingsVersion) -> str:
    return f"settings_version:{row.id}:v{row.version}"


def _merge_no_override(
    target: dict[str, object],
    incoming: dict[str, object],
    *,
    path: str = "lens_selection",
) -> None:
    for key in sorted(incoming):
        value = incoming[key]
        current_path = f"{path}.{key}"
        if key not in target:
            target[key] = copy.deepcopy(value)
            continue
        existing = target[key]
        if isinstance(existing, dict) and isinstance(value, dict):
            _merge_no_override(
                existing,
                value,
                path=current_path,
            )
            continue
        if existing != value:
            raise LensSelectionError("lens_settings_override_conflict")


def _scope_matches(
    row: SettingsVersion,
    *,
    project: Project,
    content_case: ContentCase,
    variant: LocaleVariant,
) -> bool:
    if row.scope_type == "system":
        return row.project_id is None
    if row.project_id != project.id:
        return False
    if row.scope_type == "project":
        return row.scope_key == project.slug
    if row.scope_type == "content_type":
        return row.scope_key == content_case.content_type
    if row.scope_type == "locale":
        return row.scope_key == variant.locale
    return False


def _validate_guard_entry_keys(
    item: dict[str, object],
    expected: set[str],
    code: str,
) -> None:
    if set(item) != expected:
        raise LensSelectionError(code)


def _parse_guard_config(
    raw: dict[str, object],
) -> dict[str, list[dict[str, object]]]:
    if not set(raw).issubset(
        {
            "misconceptions",
            "case_materials",
            "pov_positions",
            "causal_evidence",
        }
    ):
        raise LensSelectionError("lens_guard_config_unknown_key")

    misconceptions = _records(
        raw.get("misconceptions", []),
        "lens_misconceptions_invalid",
    )
    parsed_misconceptions: list[dict[str, object]] = []
    for item in misconceptions:
        _validate_guard_entry_keys(
            item,
            {
                "ref",
                "need_hypothesis_id",
                "statement",
                "observation_ref",
                "approval_ref",
            },
            "lens_misconception_invalid",
        )
        parsed_misconceptions.append(
            {
                "ref": _required_text(
                    item["ref"],
                    "lens_misconception_ref_required",
                ),
                "need_hypothesis_id": _optional_uuid_text(
                    item["need_hypothesis_id"],
                    "lens_misconception_need_invalid",
                ),
                "statement": _required_text(
                    item["statement"],
                    "lens_misconception_statement_required",
                ),
                "observation_ref": _required_text(
                    item["observation_ref"],
                    "lens_misconception_observation_required",
                ),
                "approval_ref": _required_text(
                    item["approval_ref"],
                    "lens_misconception_approval_required",
                ),
            }
        )

    cases = _records(
        raw.get("case_materials", []),
        "lens_case_materials_invalid",
    )
    parsed_cases: list[dict[str, object]] = []
    for item in cases:
        _validate_guard_entry_keys(
            item,
            {
                "ref",
                "need_hypothesis_id",
                "summary",
                "provenance_ref",
                "rights_ref",
            },
            "lens_case_material_invalid",
        )
        parsed_cases.append(
            {
                "ref": _required_text(
                    item["ref"],
                    "lens_case_material_ref_required",
                ),
                "need_hypothesis_id": _optional_uuid_text(
                    item["need_hypothesis_id"],
                    "lens_case_material_need_invalid",
                ),
                "summary": _required_text(
                    item["summary"],
                    "lens_case_material_summary_required",
                ),
                "provenance_ref": _required_text(
                    item["provenance_ref"],
                    "lens_case_material_provenance_required",
                ),
                "rights_ref": _required_text(
                    item["rights_ref"],
                    "lens_case_material_rights_required",
                ),
            }
        )

    positions = _records(
        raw.get("pov_positions", []),
        "lens_pov_positions_invalid",
    )
    parsed_positions: list[dict[str, object]] = []
    for item in positions:
        _validate_guard_entry_keys(
            item,
            {
                "ref",
                "need_hypothesis_id",
                "statement",
                "approval_ref",
            },
            "lens_pov_position_invalid",
        )
        parsed_positions.append(
            {
                "ref": _required_text(
                    item["ref"],
                    "lens_pov_position_ref_required",
                ),
                "need_hypothesis_id": _optional_uuid_text(
                    item["need_hypothesis_id"],
                    "lens_pov_position_need_invalid",
                ),
                "statement": _required_text(
                    item["statement"],
                    "lens_pov_position_statement_required",
                ),
                "approval_ref": _required_text(
                    item["approval_ref"],
                    "lens_pov_position_approval_required",
                ),
            }
        )

    causal = _records(
        raw.get("causal_evidence", []),
        "lens_causal_evidence_invalid",
    )
    parsed_causal: list[dict[str, object]] = []
    for item in causal:
        _validate_guard_entry_keys(
            item,
            {
                "ref",
                "need_hypothesis_id",
                "statement",
                "source_ref",
                "approval_ref",
            },
            "lens_causal_evidence_invalid",
        )
        parsed_causal.append(
            {
                "ref": _required_text(
                    item["ref"],
                    "lens_causal_ref_required",
                ),
                "need_hypothesis_id": _optional_uuid_text(
                    item["need_hypothesis_id"],
                    "lens_causal_need_invalid",
                ),
                "statement": _required_text(
                    item["statement"],
                    "lens_causal_statement_required",
                ),
                "source_ref": _required_text(
                    item["source_ref"],
                    "lens_causal_source_required",
                ),
                "approval_ref": _required_text(
                    item["approval_ref"],
                    "lens_causal_approval_required",
                ),
            }
        )

    return {
        "misconceptions": parsed_misconceptions,
        "case_materials": parsed_cases,
        "pov_positions": parsed_positions,
        "causal_evidence": parsed_causal,
    }


async def _approved_guard_config(
    session: AsyncSession,
    *,
    run: ContentRun,
    content_case: ContentCase,
    variant: LocaleVariant,
) -> tuple[dict[str, list[dict[str, object]]], list[str]]:
    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None or snapshot.project_id != run.project_id:
        raise LensSelectionError("lens_settings_snapshot_mismatch")
    if snapshot.content_hash != settings_hash(snapshot.resolved_settings_json):
        raise LensSelectionError("lens_settings_snapshot_hash_mismatch")

    effective_raw = snapshot.resolved_settings_json.get("lens_selection")
    if effective_raw is None:
        effective: dict[str, object] = {}
    else:
        effective = _dict(
            effective_raw,
            "lens_guard_config_invalid",
        )

    project = await session.get(Project, run.project_id)
    if project is None:
        raise LensSelectionError("lens_project_not_found")

    reconstructed: dict[str, object] = {}
    refs: list[str] = []
    for raw_ref in snapshot.source_version_refs_json:
        if not isinstance(raw_ref, str):
            raise LensSelectionError("lens_settings_source_ref_invalid")
        match = _SETTINGS_REF_RE.fullmatch(raw_ref)
        if match is None:
            continue
        try:
            row_id = UUID(match.group(1))
        except ValueError as exc:
            raise LensSelectionError(
                "lens_settings_source_ref_invalid"
            ) from exc
        row = await session.get(SettingsVersion, row_id)
        if row is None or row.version != int(match.group(2)):
            raise LensSelectionError(
                "lens_settings_source_ref_invalid"
            )
        source_lens = row.settings_json.get("lens_selection")
        if source_lens is None:
            continue
        if (
            row.status != "active"
            or not isinstance(row.approved_by, str)
            or not row.approved_by.strip()
            or not _scope_matches(
                row,
                project=project,
                content_case=content_case,
                variant=variant,
            )
        ):
            raise LensSelectionError(
                "lens_settings_source_not_approved"
            )
        source_lens_dict = _dict(
            source_lens,
            "lens_settings_source_invalid",
        )
        _merge_no_override(reconstructed, source_lens_dict)
        refs.append(_settings_version_ref(row))

    if effective and not refs:
        raise LensSelectionError(
            "lens_guard_config_approved_source_required"
        )
    if reconstructed != effective:
        raise LensSelectionError(
            "lens_guard_config_snapshot_source_mismatch"
        )

    return _parse_guard_config(effective), refs


def _matching_guard_entries(
    rows: list[dict[str, object]],
    *,
    need_id: UUID,
) -> list[dict[str, object]]:
    expected = str(need_id)
    return [
        row
        for row in rows
        if row["need_hypothesis_id"] in {None, expected}
    ]


async def _run_context(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
) -> tuple[
    ContentRun,
    StepRun | None,
    ContentCase,
    LocaleVariant,
    ContentOpportunity,
]:
    run = await session.get(ContentRun, run_id)
    if run is None:
        raise LensSelectionError("lens_run_not_found")
    step: StepRun | None = None
    if step_run_id is not None:
        step = await session.get(StepRun, step_run_id)
        if step is None or step.run_id != run.id:
            raise LensSelectionError("lens_step_mismatch")

    content_case = await session.get(ContentCase, run.content_case_id)
    if content_case is None or content_case.project_id != run.project_id:
        raise LensSelectionError("lens_content_case_mismatch")
    variant = await session.get(LocaleVariant, run.locale_variant_id)
    if (
        variant is None
        or variant.content_case_id != content_case.id
    ):
        raise LensSelectionError("lens_locale_variant_mismatch")
    opportunity = await session.get(
        ContentOpportunity,
        content_case.content_opportunity_id,
    )
    if (
        opportunity is None
        or opportunity.project_id != run.project_id
        or opportunity.need_hypothesis_id
        != content_case.need_hypothesis_id
        or opportunity.locale != variant.locale
    ):
        raise LensSelectionError("lens_opportunity_mismatch")
    if opportunity.decision in _UPSTREAM_BLOCKING_DECISIONS:
        raise LensSelectionError("lens_opportunity_not_writable")
    if (
        not isinstance(opportunity.selected_by, str)
        or not opportunity.selected_by.strip()
        or opportunity.selected_at is None
        or not isinstance(opportunity.selection_reason, str)
        or not opportunity.selection_reason.strip()
    ):
        raise LensSelectionError("lens_opportunity_selection_required")
    human_selections = list(
        (
            await session.scalars(
                select(HumanSelection)
                .where(
                    HumanSelection.content_opportunity_id
                    == opportunity.id
                )
                .order_by(
                    HumanSelection.selected_at,
                    HumanSelection.id,
                )
            )
        ).all()
    )
    matching_selection = [
        row
        for row in human_selections
        if (
            row.selected_by == opportunity.selected_by
            and row.reason == opportunity.selection_reason
            and row.selected_at == opportunity.selected_at
        )
    ]
    if len(human_selections) != 1 or len(matching_selection) != 1:
        raise LensSelectionError(
            "lens_opportunity_human_selection_mismatch"
        )
    return run, step, content_case, variant, opportunity


def _opportunity_payload(
    opportunity: ContentOpportunity,
) -> dict[str, object]:
    return {
        "id": str(opportunity.id),
        "project_id": str(opportunity.project_id),
        "need_hypothesis_id": str(opportunity.need_hypothesis_id),
        "locale": opportunity.locale,
        "reader": opportunity.reader,
        "situation": opportunity.situation,
        "need": opportunity.need,
        "question": opportunity.question,
        "intent": opportunity.intent,
        "promise": opportunity.promise,
        "motgu_material_refs": list(
            opportunity.motgu_material_refs_json
        ),
        "material_gaps": list(opportunity.material_gaps_json),
        "existing_content_refs": list(
            opportunity.existing_content_refs_json
        ),
        "what_is_actually_new": opportunity.what_is_actually_new,
        "next_discovery_step": opportunity.next_discovery_step,
        "decision": opportunity.decision,
        "priority": opportunity.priority,
        "reasons": list(opportunity.reasons_json),
        "suggested_content_type": opportunity.suggested_content_type,
        "suggested_role": opportunity.suggested_role,
        "version": opportunity.version,
        "selected_by": opportunity.selected_by,
        "selected_at": (
            opportunity.selected_at.isoformat()
            if opportunity.selected_at is not None
            else None
        ),
        "selection_reason": opportunity.selection_reason,
    }


def _coverage_lane(report: dict[str, object]) -> dict[str, object]:
    lanes = _records(
        report.get("needs"),
        "lens_coverage_needs_invalid",
    )
    if len(lanes) != 1:
        raise LensSelectionError("lens_coverage_need_ambiguous")
    return lanes[0]


def _customer_need_inputs(
    detail: dict[str, object],
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[str],
    list[str],
]:
    need = _dict(
        detail.get("need"),
        "lens_customer_need_invalid",
    )
    insights = _records(
        detail.get("insights"),
        "lens_customer_insights_invalid",
    )
    signal_refs = _dict(
        need.get("signal_refs"),
        "lens_customer_need_signal_refs_invalid",
    )
    supports = _strings(
        signal_refs.get("supports", []),
        "lens_customer_need_support_refs_invalid",
    )
    contradicts = _strings(
        signal_refs.get("contradicts", []),
        "lens_customer_need_contradict_refs_invalid",
    )

    for insight in insights:
        refs = _dict(
            insight.get("signal_refs"),
            "lens_customer_insight_signal_refs_invalid",
        )
        supports.extend(
            _strings(
                refs.get("supports", []),
                "lens_customer_insight_support_refs_invalid",
            )
        )
        contradicts.extend(
            _strings(
                refs.get("contradicts", []),
                "lens_customer_insight_contradict_refs_invalid",
            )
        )
    return (
        need,
        insights,
        sorted(set(supports)),
        sorted(set(contradicts)),
    )


def _guard(
    key: str,
    status: GuardStatus,
    reason: str,
    refs: list[str] | None = None,
) -> dict[str, object]:
    return {
        "key": key,
        "status": status,
        "reason": reason,
        "refs": sorted(set(refs or [])),
    }


def _candidate(
    *,
    lens: str,
    opportunity: ContentOpportunity,
    coverage: dict[str, object],
    source_refs: list[str],
    evidence_needed: list[str],
    authority: str,
    authority_context: list[dict[str, object]] | None = None,
    guards: list[dict[str, object]],
    added_value: str,
    reasons: list[str],
) -> dict[str, object]:
    eligible = not any(
        guard_row.get("status") == "BLOCK"
        for guard_row in guards
    )
    return {
        "lens": lens,
        "reader_need": opportunity.need,
        "primary_question": opportunity.question,
        "added_value": added_value,
        "evidence_needed": evidence_needed,
        "evidence_available": {
            "available": bool(source_refs),
            "refs": sorted(set(source_refs)),
        },
        "speaking_authority": authority,
        "authority_context": _clone(authority_context or []),
        "existing_coverage": _clone(coverage),
        "guards": guards,
        "reasons": reasons,
        "source_refs": sorted(set(source_refs)),
        "eligible": eligible,
    }


def _build_candidate_rows(
    *,
    opportunity: ContentOpportunity,
    need_id: UUID,
    supports: list[str],
    contradicts: list[str],
    insights: list[dict[str, object]],
    coverage_lane: dict[str, object],
    guard_config: dict[str, list[dict[str, object]]],
    guard_source_refs: list[str],
) -> list[dict[str, object]]:
    material_refs = sorted(
        set(opportunity.motgu_material_refs_json)
    )
    signal_refs = sorted(set([*supports, *contradicts]))
    base_refs = sorted(set([*signal_refs, *material_refs]))
    insight_types = sorted(
        {
            str(row["insight_type"])
            for row in insights
            if isinstance(row.get("insight_type"), str)
        }
    )
    coverage_status = str(
        coverage_lane.get("coverage_status", "UNKNOWN")
    )
    coverage_reason = f"existing_coverage={coverage_status}"

    misconception_rows = _matching_guard_entries(
        guard_config["misconceptions"],
        need_id=need_id,
    )
    case_rows = _matching_guard_entries(
        guard_config["case_materials"],
        need_id=need_id,
    )
    pov_rows = _matching_guard_entries(
        guard_config["pov_positions"],
        need_id=need_id,
    )
    causal_rows = _matching_guard_entries(
        guard_config["causal_evidence"],
        need_id=need_id,
    )

    misconception_refs = [
        str(value)
        for row in misconception_rows
        for value in (
            row["ref"],
            row["observation_ref"],
            row["approval_ref"],
        )
    ]
    case_refs = [
        str(value)
        for row in case_rows
        for value in (
            row["ref"],
            row["provenance_ref"],
            row["rights_ref"],
        )
    ]
    pov_refs = [
        str(value)
        for row in pov_rows
        for value in (row["ref"], row["approval_ref"])
    ]
    causal_refs = [
        str(value)
        for row in causal_rows
        for value in (
            row["ref"],
            row["source_ref"],
            row["approval_ref"],
        )
    ]

    misconception_context: list[dict[str, object]] = [
        {
            "kind": "approved_observed_misconception",
            "statement": row["statement"],
            "observation_ref": row["observation_ref"],
            "approval_ref": row["approval_ref"],
        }
        for row in misconception_rows
    ]
    signal_context: list[dict[str, object]] = [
        {
            "kind": "customer_insight",
            "insight_type": row.get("insight_type"),
            "statement": row.get("statement"),
            "status": row.get("status"),
            "signal_refs": _clone(row.get("signal_refs")),
        }
        for row in insights
    ]
    causal_context: list[dict[str, object]] = [
        {
            "kind": "approved_causal_statement",
            "statement": row["statement"],
            "source_ref": row["source_ref"],
            "approval_ref": row["approval_ref"],
        }
        for row in causal_rows
    ]
    method_context: list[dict[str, object]] = [
        {
            "kind": "motgu_material_ref",
            "material_ref": ref,
        }
        for ref in material_refs
    ]
    case_context: list[dict[str, object]] = [
        {
            "kind": "approved_case_material",
            "summary": row["summary"],
            "provenance_ref": row["provenance_ref"],
            "rights_ref": row["rights_ref"],
        }
        for row in case_rows
    ]
    pov_context: list[dict[str, object]] = [
        {
            "kind": "approved_motgu_position",
            "statement": row["statement"],
            "approval_ref": row["approval_ref"],
        }
        for row in pov_rows
    ]

    rows: list[dict[str, object]] = []

    rows.append(
        _candidate(
            lens="DEFINITION",
            opportunity=opportunity,
            coverage=coverage_lane,
            source_refs=base_refs,
            evidence_needed=[
                "authoritative definitions and boundary conditions",
                "examples that separate the concept from adjacent concepts",
            ],
            authority="EVIDENCE_LED",
            guards=[
                _guard(
                    "evidence_present",
                    "PASS" if base_refs else "BLOCK",
                    "Definition needs traceable source material before selection.",
                    base_refs,
                )
            ],
            added_value=(
                "Clarify the core term and boundaries behind the reader's "
                "question before asking the reader to act."
            ),
            reasons=[coverage_reason],
        )
    )

    rows.append(
        _candidate(
            lens="MISCONCEPTION",
            opportunity=opportunity,
            coverage=coverage_lane,
            source_refs=misconception_refs,
            evidence_needed=[
                "an observed customer belief tied to traceable evidence",
                "evidence that corrects or qualifies the belief",
            ],
            authority=(
                "APPROVED_MISCONCEPTION_OBSERVATION"
                if misconception_rows
                else "MISSING_OBSERVED_MISCONCEPTION"
            ),
            authority_context=misconception_context,
            guards=[
                _guard(
                    "misconception_observed",
                    "PASS" if misconception_rows else "BLOCK",
                    "Do not infer a misconception from contradictory evidence alone.",
                    [*misconception_refs, *guard_source_refs],
                )
            ],
            added_value=(
                "Correct a documented misunderstanding instead of inventing "
                "a belief the customer may not actually hold."
            ),
            reasons=[
                coverage_reason,
                f"insight_types={','.join(insight_types) or 'none'}",
            ],
        )
    )

    rows.append(
        _candidate(
            lens="SIGNALS",
            opportunity=opportunity,
            coverage=coverage_lane,
            source_refs=signal_refs,
            evidence_needed=[
                "observable indicators tied to traceable Signals",
                "explicit limits on what those indicators can prove",
            ],
            authority="OBSERVATION_LED",
            authority_context=signal_context,
            guards=[
                _guard(
                    "signals_present",
                    "PASS" if signal_refs else "BLOCK",
                    "Signals lens requires observed indicators.",
                    signal_refs,
                ),
                _guard(
                    "signals_not_conclusion",
                    "PASS",
                    "Indicators must not be rewritten as proof or diagnosis.",
                ),
            ],
            added_value=(
                "Help the reader notice observable indicators while keeping "
                "the distinction between signal and conclusion explicit."
            ),
            reasons=[coverage_reason],
        )
    )

    rows.append(
        _candidate(
            lens="CAUSES",
            opportunity=opportunity,
            coverage=coverage_lane,
            source_refs=causal_refs,
            evidence_needed=[
                "approved causal evidence specific to the claimed relationship",
                "alternative explanations and qualifying evidence",
            ],
            authority=(
                "APPROVED_CAUSAL_EVIDENCE"
                if causal_rows
                else "MISSING_CAUSAL_AUTHORITY"
            ),
            authority_context=causal_context,
            guards=[
                _guard(
                    "causal_evidence_approved",
                    "PASS" if causal_rows else "BLOCK",
                    "Correlation or repeated observation is not enough to claim causality.",
                    [*causal_refs, *guard_source_refs],
                ),
                _guard(
                    "correlation_not_causality",
                    "PASS",
                    "Causal language is limited to the approved causal proof.",
                ),
            ],
            added_value=(
                "Explain why something happens only when the causal link is "
                "supported rather than inferred from correlation."
            ),
            reasons=[coverage_reason],
        )
    )

    rows.append(
        _candidate(
            lens="METHOD",
            opportunity=opportunity,
            coverage=coverage_lane,
            source_refs=material_refs,
            evidence_needed=[
                "MOTGU-owned process or practical material",
                "steps, limits, and conditions needed to apply the method",
            ],
            authority=(
                "MOTGU_FIRST_PARTY_MATERIAL"
                if material_refs
                else "MISSING_FIRST_PARTY_METHOD"
            ),
            authority_context=method_context,
            guards=[
                _guard(
                    "first_party_method_material",
                    "PASS" if material_refs else "BLOCK",
                    "Method lens needs traceable MOTGU material, not generic synthesis.",
                    material_refs,
                )
            ],
            added_value=(
                "Turn MOTGU's own practical method into a useful sequence "
                "the reader can apply."
            ),
            reasons=[coverage_reason],
        )
    )

    rows.append(
        _candidate(
            lens="CASE",
            opportunity=opportunity,
            coverage=coverage_lane,
            source_refs=case_refs,
            evidence_needed=[
                "a real case tied to this Need",
                "provenance for the case",
                "explicit rights or permission to use it",
            ],
            authority=(
                "APPROVED_CASE_MATERIAL"
                if case_rows
                else "MISSING_CASE_PROVENANCE_OR_RIGHTS"
            ),
            authority_context=case_context,
            guards=[
                _guard(
                    "real_case_provenance_rights",
                    "PASS" if case_rows else "BLOCK",
                    "CASE requires a real case, provenance, and use-rights proof.",
                    [*case_refs, *guard_source_refs],
                )
            ],
            added_value=(
                "Show the Need through a real, permitted case instead of a "
                "fabricated illustrative story."
            ),
            reasons=[coverage_reason],
        )
    )

    rows.append(
        _candidate(
            lens="POV",
            opportunity=opportunity,
            coverage=coverage_lane,
            source_refs=pov_refs,
            evidence_needed=[
                "an approved MOTGU position",
                "the factual/evidentiary boundary for that position",
            ],
            authority=(
                "APPROVED_MOTGU_POSITION"
                if pov_rows
                else "MISSING_APPROVED_POSITION"
            ),
            authority_context=pov_context,
            guards=[
                _guard(
                    "motgu_position_approved",
                    "PASS" if pov_rows else "BLOCK",
                    "POV requires an explicitly approved MOTGU position.",
                    [*pov_refs, *guard_source_refs],
                )
            ],
            added_value=(
                "State a verified MOTGU point of view that helps the reader "
                "decide, without inventing a brand stance."
            ),
            reasons=[coverage_reason],
        )
    )

    if [row["lens"] for row in rows] != list(LENS_ORDER):
        raise LensSelectionError("lens_candidate_order_invalid")
    return rows


async def build_lens_candidate_payload(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None = None,
) -> dict[str, object]:
    (
        run,
        _step,
        content_case,
        variant,
        opportunity,
    ) = await _run_context(
        session,
        run_id=run_id,
        step_run_id=step_run_id,
    )
    try:
        map_detail = await customer_map_need_detail(
            session,
            project_id=run.project_id,
            need_id=content_case.need_hypothesis_id,
        )
        coverage = await build_content_coverage(
            session,
            project_id=run.project_id,
            locale=variant.locale,
            audience_id=content_case.audience_hypothesis_id,
            need_id=content_case.need_hypothesis_id,
        )
    except (CustomerMapError, ContentCoverageError) as exc:
        raise LensSelectionError(str(exc)) from exc

    need, insights, supports, contradicts = _customer_need_inputs(
        map_detail
    )
    if need.get("id") != str(content_case.need_hypothesis_id):
        raise LensSelectionError("lens_customer_need_mismatch")
    lane = _coverage_lane(coverage)
    lane_need = _dict(
        lane.get("need"),
        "lens_coverage_need_invalid",
    )
    if lane_need.get("id") != str(content_case.need_hypothesis_id):
        raise LensSelectionError("lens_coverage_need_mismatch")

    guard_config, guard_refs = await _approved_guard_config(
        session,
        run=run,
        content_case=content_case,
        variant=variant,
    )

    opportunity_payload = _opportunity_payload(opportunity)
    map_input = {
        "project": _clone(map_detail.get("project")),
        "journey": _clone(map_detail.get("journey")),
        "need": _clone(need),
        "audience": _clone(map_detail.get("audience")),
        "insights": _clone(insights),
    }
    coverage_input = {
        "project": _clone(coverage.get("project")),
        "filters": _clone(coverage.get("filters")),
        "journey": _clone(coverage.get("journey")),
        "need": _clone(lane),
    }
    candidates = _build_candidate_rows(
        opportunity=opportunity,
        need_id=content_case.need_hypothesis_id,
        supports=supports,
        contradicts=contradicts,
        insights=insights,
        coverage_lane=lane,
        guard_config=guard_config,
        guard_source_refs=guard_refs,
    )
    snapshot = await session.get(SettingsSnapshot, run.settings_snapshot_id)
    if snapshot is None:
        raise LensSelectionError("lens_settings_snapshot_missing")

    return {
        "schema_version": LENS_SCHEMA_VERSION,
        "artifact_type": LENS_CANDIDATES_ARTIFACT_TYPE,
        "run_ref": {
            "run_id": str(run.id),
            "step_run_id": (
                str(step_run_id)
                if step_run_id is not None
                else None
            ),
            "content_case_id": str(content_case.id),
            "locale_variant_id": str(variant.id),
            "locale": variant.locale,
        },
        "opportunity": {
            "snapshot": opportunity_payload,
            "snapshot_hash": _stable_hash(opportunity_payload),
        },
        "customer_map": {
            "snapshot": map_input,
            "snapshot_hash": _stable_hash(map_input),
        },
        "coverage": {
            "snapshot": coverage_input,
            "snapshot_hash": _stable_hash(coverage_input),
        },
        "settings": {
            "settings_snapshot_id": str(snapshot.id),
            "settings_snapshot_hash": snapshot.content_hash,
            "guard_source_refs": guard_refs,
        },
        "candidates": candidates,
        "selection_contract": {
            "decisions": ["SELECT", "MERGE", "HOLD", "DROP"],
            "max_primary_select": 1,
            "merge_requires_selected_target": True,
            "select_or_merge_requires_eligible_candidate": True,
            "all_hold_or_drop_is_allowed": True,
            "one_lens_does_not_equal_one_article": True,
        },
    }


async def _bind_step_output_artifact(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    artifact_id: UUID,
) -> None:
    if step_run_id is None:
        return
    step = await session.get(StepRun, step_run_id)
    if step is None or step.run_id != run_id:
        raise LensSelectionError("lens_step_mismatch")
    artifact_ref = str(artifact_id)
    if artifact_ref not in step.output_artifact_refs_json:
        step.output_artifact_refs_json = [
            *step.output_artifact_refs_json,
            artifact_ref,
        ]
        await session.flush()


async def _persist_payload_artifact(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None,
    artifact_type: str,
    locale: str,
    payload: dict[str, object],
) -> Artifact:
    content_hash = _stable_hash(payload)
    existing = await session.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == run_id,
            Artifact.step_run_id == step_run_id,
            Artifact.artifact_type == artifact_type,
            Artifact.content_hash == content_hash,
        )
        .order_by(Artifact.version, Artifact.id)
        .limit(1)
    )
    if existing is not None:
        if (
            existing.content_json != payload
            or existing.locale != locale
        ):
            raise LensSelectionError("lens_artifact_replay_conflict")
        await _bind_step_output_artifact(
            session,
            run_id=run_id,
            step_run_id=step_run_id,
            artifact_id=existing.id,
        )
        return existing

    latest_version = await session.scalar(
        select(func.coalesce(func.max(Artifact.version), 0)).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == artifact_type,
        )
    )
    artifact = Artifact(
        run_id=run_id,
        step_run_id=step_run_id,
        artifact_type=artifact_type,
        locale=locale,
        version=int(latest_version or 0) + 1,
        content_json=payload,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.flush()
    await _bind_step_output_artifact(
        session,
        run_id=run_id,
        step_run_id=step_run_id,
        artifact_id=artifact.id,
    )
    return artifact


async def persist_lens_candidates(
    session: AsyncSession,
    *,
    run_id: UUID,
    step_run_id: UUID | None = None,
) -> LensCandidateResult:
    run, _step, _case, variant, _opportunity = await _run_context(
        session,
        run_id=run_id,
        step_run_id=step_run_id,
    )
    payload = await build_lens_candidate_payload(
        session,
        run_id=run.id,
        step_run_id=step_run_id,
    )
    artifact = await _persist_payload_artifact(
        session,
        run_id=run.id,
        step_run_id=step_run_id,
        artifact_type=LENS_CANDIDATES_ARTIFACT_TYPE,
        locale=variant.locale,
        payload=payload,
    )
    return LensCandidateResult(artifact=artifact, payload=payload)


def _candidate_by_lens(
    payload: dict[str, object],
) -> dict[str, dict[str, object]]:
    candidates = _records(
        payload.get("candidates"),
        "lens_candidates_invalid",
    )
    if len(candidates) != len(LENS_ORDER):
        raise LensSelectionError("lens_candidate_count_invalid")
    by_lens: dict[str, dict[str, object]] = {}
    for candidate in candidates:
        lens = _required_text(
            candidate.get("lens"),
            "lens_candidate_name_invalid",
        )
        if lens not in LENS_ORDER or lens in by_lens:
            raise LensSelectionError("lens_candidate_identity_invalid")
        eligible = candidate.get("eligible")
        if not isinstance(eligible, bool):
            raise LensSelectionError("lens_candidate_eligibility_invalid")
        by_lens[lens] = candidate
    if set(by_lens) != set(LENS_ORDER):
        raise LensSelectionError("lens_candidate_set_invalid")
    return by_lens


def _validate_decisions(
    *,
    candidates: dict[str, dict[str, object]],
    decisions: list[dict[str, object]],
) -> tuple[list[dict[str, object]], str | None, list[str]]:
    if len(decisions) != len(LENS_ORDER):
        raise LensSelectionError("lens_decision_count_invalid")

    normalized: dict[str, dict[str, object]] = {}
    for raw in decisions:
        if not isinstance(raw, dict):
            raise LensSelectionError("lens_decision_invalid")
        if not set(raw).issubset({"lens", "decision", "merge_into"}):
            raise LensSelectionError("lens_decision_unknown_field")
        lens = _required_text(
            raw.get("lens"),
            "lens_decision_lens_required",
        )
        decision = _required_text(
            raw.get("decision"),
            "lens_decision_value_required",
        )
        if lens not in LENS_ORDER or lens in normalized:
            raise LensSelectionError("lens_decision_lens_invalid")
        if decision not in _ALLOWED_DECISIONS:
            raise LensSelectionError("lens_decision_value_invalid")
        merge_into = raw.get("merge_into")
        if merge_into is not None:
            if not isinstance(merge_into, str) or merge_into not in LENS_ORDER:
                raise LensSelectionError("lens_merge_target_invalid")
        if decision != "MERGE" and merge_into is not None:
            raise LensSelectionError("lens_merge_target_unexpected")
        normalized[lens] = {
            "lens": lens,
            "decision": decision,
            "merge_into": merge_into,
        }

    if set(normalized) != set(LENS_ORDER):
        raise LensSelectionError("lens_decision_set_invalid")
    selected = [
        lens
        for lens, row in normalized.items()
        if row["decision"] == "SELECT"
    ]
    if len(selected) > 1:
        raise LensSelectionError("lens_multiple_primary_selects")
    primary = selected[0] if selected else None

    merged: list[str] = []
    for lens in LENS_ORDER:
        row = normalized[lens]
        decision = _required_text(
            row.get("decision"),
            "lens_decision_value_required",
        )
        candidate = candidates[lens]
        if (
            decision in {"SELECT", "MERGE"}
            and not _candidate_eligible(candidate)
        ):
            raise LensSelectionError("lens_ineligible_candidate_activated")
        if decision == "MERGE":
            if primary is None:
                raise LensSelectionError("lens_merge_requires_primary")
            if row["merge_into"] != primary or lens == primary:
                raise LensSelectionError("lens_merge_target_invalid")
            merged.append(lens)

    ordered = [normalized[lens] for lens in LENS_ORDER]
    return ordered, primary, merged


async def _validate_step_output_binding(
    session: AsyncSession,
    *,
    artifact: Artifact,
) -> None:
    if artifact.step_run_id is None:
        return
    step = await session.get(StepRun, artifact.step_run_id)
    if (
        step is None
        or step.run_id != artifact.run_id
        or str(artifact.id) not in step.output_artifact_refs_json
    ):
        raise LensSelectionError("lens_artifact_step_binding_invalid")


async def _load_candidate_artifact(
    session: AsyncSession,
    *,
    artifact_id: UUID,
) -> Artifact:
    artifact = await session.get(Artifact, artifact_id)
    if (
        artifact is None
        or artifact.artifact_type
        != LENS_CANDIDATES_ARTIFACT_TYPE
        or artifact.content_json is None
    ):
        raise LensSelectionError("lens_candidate_artifact_invalid")
    if artifact.content_hash != _stable_hash(artifact.content_json):
        raise LensSelectionError("lens_candidate_artifact_hash_mismatch")
    await _validate_step_output_binding(
        session,
        artifact=artifact,
    )
    return artifact


async def _require_current_candidate(
    session: AsyncSession,
    *,
    artifact: Artifact,
) -> dict[str, object]:
    current = await build_lens_candidate_payload(
        session,
        run_id=artifact.run_id,
        step_run_id=artifact.step_run_id,
    )
    if (
        artifact.content_hash != _stable_hash(current)
        or artifact.content_json != current
    ):
        raise LensSelectionError("lens_candidate_artifact_stale")
    return current


def _candidate_eligible(
    candidate: dict[str, object],
) -> bool:
    value = candidate.get("eligible")
    if not isinstance(value, bool):
        raise LensSelectionError("lens_candidate_eligibility_invalid")
    return value


def _candidate_requirement(
    row: dict[str, object],
) -> dict[str, object]:
    lens = _required_text(
        row.get("lens"),
        "lens_candidate_name_invalid",
    )
    return {
        "lens": lens,
        "evidence_needed": _clone(row.get("evidence_needed")),
        "evidence_available": _clone(
            row.get("evidence_available")
        ),
        "speaking_authority": _clone(
            row.get("speaking_authority")
        ),
        "authority_context": _clone(
            row.get("authority_context")
        ),
        "guards": _clone(row.get("guards")),
        "source_refs": _clone(row.get("source_refs")),
    }


def _selection_contexts(
    *,
    candidates: dict[str, dict[str, object]],
    decisions: list[dict[str, object]],
    primary: str | None,
    merged: list[str],
) -> tuple[dict[str, object], dict[str, object]]:
    active = [primary, *merged] if primary is not None else []
    active_rows = [candidates[lens] for lens in active]
    held_lenses = [
        _required_text(
            row.get("lens"),
            "lens_decision_lens_required",
        )
        for row in decisions
        if row.get("decision") == "HOLD"
    ]
    held_rows = [candidates[lens] for lens in held_lenses]

    evidence_context: dict[str, object] = {
        "primary_lens": primary,
        "supporting_lenses": merged,
        "active_lenses": active,
        "held_lenses": held_lenses,
        "active_requirements": [
            _candidate_requirement(row) for row in active_rows
        ],
        "held_requirements": [
            _candidate_requirement(row) for row in held_rows
        ],
    }
    angle_context: dict[str, object] = {
        "primary_lens": primary,
        "supporting_lenses": merged,
        "reader_need": (
            active_rows[0].get("reader_need")
            if active_rows
            else None
        ),
        "primary_question": (
            active_rows[0].get("primary_question")
            if active_rows
            else None
        ),
        "authority": [
            {
                "lens": row.get("lens"),
                "speaking_authority": row.get(
                    "speaking_authority"
                ),
                "authority_context": _clone(
                    row.get("authority_context")
                ),
            }
            for row in active_rows
        ],
        "added_value": [
            {
                "lens": row.get("lens"),
                "value": row.get("added_value"),
            }
            for row in active_rows
        ],
        "guardrails": [
            {
                "lens": row.get("lens"),
                "guards": _clone(row.get("guards")),
            }
            for row in active_rows
        ],
        "source_refs": sorted(
            {
                ref
                for row in active_rows
                for ref in _strings(
                    row.get("source_refs"),
                    "lens_candidate_source_refs_invalid",
                )
            }
        ),
        "existing_coverage": (
            _clone(active_rows[0].get("existing_coverage"))
            if active_rows
            else None
        ),
    }
    return evidence_context, angle_context


def _build_selection_payload(
    *,
    candidate_artifact: Artifact,
    candidate_payload: dict[str, object],
    decisions: list[dict[str, object]],
    selected_by: str,
    reason: str,
) -> dict[str, object]:
    actor = _required_text(
        selected_by,
        "lens_selection_actor_required",
    )
    rationale = _required_text(
        reason,
        "lens_selection_reason_required",
    )
    candidates = _candidate_by_lens(candidate_payload)
    normalized_decisions, primary, merged = _validate_decisions(
        candidates=candidates,
        decisions=decisions,
    )
    evidence_context, angle_context = _selection_contexts(
        candidates=candidates,
        decisions=normalized_decisions,
        primary=primary,
        merged=merged,
    )
    return {
        "schema_version": LENS_SCHEMA_VERSION,
        "artifact_type": LENS_SELECTION_ARTIFACT_TYPE,
        "run_ref": _clone(candidate_payload["run_ref"]),
        "candidate_artifact_ref": {
            "id": str(candidate_artifact.id),
            "version": candidate_artifact.version,
            "content_hash": candidate_artifact.content_hash,
        },
        "selected_by": actor,
        "selection_reason": rationale,
        "decisions": normalized_decisions,
        "primary_lens": primary,
        "merged_lenses": merged,
        "evidence_context": evidence_context,
        "angle_context": angle_context,
        "one_article_contract": {
            "primary_lens_count": 1 if primary is not None else 0,
            "merged_lenses_are_not_separate_articles": True,
            "all_hold_or_drop_stops_before_angle": primary is None,
        },
    }


async def persist_lens_selection(
    session: AsyncSession,
    *,
    candidate_artifact_id: UUID,
    decisions: list[dict[str, object]],
    selected_by: str,
    reason: str,
) -> LensSelectionResult:
    candidate_artifact = await _load_candidate_artifact(
        session,
        artifact_id=candidate_artifact_id,
    )
    candidate_payload = await _require_current_candidate(
        session,
        artifact=candidate_artifact,
    )
    payload = _build_selection_payload(
        candidate_artifact=candidate_artifact,
        candidate_payload=candidate_payload,
        decisions=decisions,
        selected_by=selected_by,
        reason=reason,
    )
    run = await session.get(ContentRun, candidate_artifact.run_id)
    if run is None:
        raise LensSelectionError("lens_run_not_found")
    variant = await session.get(LocaleVariant, run.locale_variant_id)
    if variant is None:
        raise LensSelectionError("lens_locale_variant_mismatch")

    artifact = await _persist_payload_artifact(
        session,
        run_id=run.id,
        step_run_id=candidate_artifact.step_run_id,
        artifact_type=LENS_SELECTION_ARTIFACT_TYPE,
        locale=variant.locale,
        payload=payload,
    )
    return LensSelectionResult(artifact=artifact, payload=payload)


async def latest_lens_selection_artifact(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> Artifact | None:
    artifact = await session.scalar(
        select(Artifact)
        .where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == LENS_SELECTION_ARTIFACT_TYPE,
        )
        .order_by(Artifact.version.desc(), Artifact.id.desc())
        .limit(1)
    )
    if artifact is None:
        return None
    if artifact.content_json is None:
        raise LensSelectionError("lens_selection_artifact_invalid")
    if artifact.content_hash != _stable_hash(artifact.content_json):
        raise LensSelectionError("lens_selection_artifact_hash_mismatch")
    await _validate_step_output_binding(
        session,
        artifact=artifact,
    )
    return artifact


async def _validated_latest_selection_payload(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> dict[str, object] | None:
    artifact = await latest_lens_selection_artifact(
        session,
        run_id=run_id,
    )
    if artifact is None:
        return None
    payload = _dict(
        artifact.content_json,
        "lens_selection_artifact_invalid",
    )
    candidate_ref = _dict(
        payload.get("candidate_artifact_ref"),
        "lens_selection_candidate_ref_invalid",
    )
    candidate_id_raw = candidate_ref.get("id")
    if not isinstance(candidate_id_raw, str):
        raise LensSelectionError(
            "lens_selection_candidate_ref_invalid"
        )
    try:
        candidate_id = UUID(candidate_id_raw)
    except ValueError as exc:
        raise LensSelectionError(
            "lens_selection_candidate_ref_invalid"
        ) from exc
    candidate = await _load_candidate_artifact(
        session,
        artifact_id=candidate_id,
    )
    if candidate.run_id != run_id:
        raise LensSelectionError("lens_selection_run_mismatch")
    if (
        artifact.step_run_id != candidate.step_run_id
        or artifact.locale != candidate.locale
    ):
        raise LensSelectionError(
            "lens_selection_candidate_binding_mismatch"
        )
    if (
        candidate_ref.get("version") != candidate.version
        or candidate_ref.get("content_hash") != candidate.content_hash
    ):
        raise LensSelectionError(
            "lens_selection_candidate_ref_mismatch"
        )
    candidate_payload = await _require_current_candidate(
        session,
        artifact=candidate,
    )
    raw_decisions = payload.get("decisions")
    decisions = _records(
        raw_decisions,
        "lens_selection_decisions_invalid",
    )
    selected_by = _required_text(
        payload.get("selected_by"),
        "lens_selection_actor_required",
    )
    reason = _required_text(
        payload.get("selection_reason"),
        "lens_selection_reason_required",
    )
    expected = _build_selection_payload(
        candidate_artifact=candidate,
        candidate_payload=candidate_payload,
        decisions=decisions,
        selected_by=selected_by,
        reason=reason,
    )
    if expected != payload:
        raise LensSelectionError(
            "lens_selection_artifact_semantic_mismatch"
        )
    return payload


async def lens_selection_evidence_context(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> dict[str, object] | None:
    payload = await _validated_latest_selection_payload(
        session,
        run_id=run_id,
    )
    if payload is None:
        return None
    return _dict(
        _clone(payload.get("evidence_context")),
        "lens_evidence_context_invalid",
    )


async def lens_selection_angle_context(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> dict[str, object] | None:
    payload = await _validated_latest_selection_payload(
        session,
        run_id=run_id,
    )
    if payload is None:
        return None
    primary = payload.get("primary_lens")
    if primary is None:
        raise LensSelectionError("lens_selection_no_active_lens")
    if not isinstance(primary, str) or primary not in LENS_ORDER:
        raise LensSelectionError("lens_selection_primary_invalid")
    return _dict(
        _clone(payload.get("angle_context")),
        "lens_angle_context_invalid",
    )


__all__ = [
    "LENS_CANDIDATES_ARTIFACT_TYPE",
    "LENS_ORDER",
    "LENS_SCHEMA_VERSION",
    "LENS_SELECTION_ARTIFACT_TYPE",
    "LensCandidateResult",
    "LensDecision",
    "LensSelectionError",
    "LensSelectionResult",
    "build_lens_candidate_payload",
    "latest_lens_selection_artifact",
    "lens_selection_angle_context",
    "lens_selection_evidence_context",
    "persist_lens_candidates",
    "persist_lens_selection",
]
