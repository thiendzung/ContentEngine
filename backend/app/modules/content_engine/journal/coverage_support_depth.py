"""CQ-03 coverage support-depth contract before Angle generation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast

from app.modules.research.evidence.contracts import is_usable_originality_item

CoverageSupportStatus = Literal[
    "evidence_supported",
    "originality_supported",
    "mixed",
    "unresolved",
]
COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION = 1

_VALID_STATUSES = {
    "evidence_supported",
    "originality_supported",
    "mixed",
    "unresolved",
}
_CAVEAT_RELATIONS = {"qualifies", "contradicts", "context_only"}


class CoverageSupportDepthError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CoverageSupportItem:
    requirement_id: str
    status: CoverageSupportStatus
    evidence_refs: tuple[str, ...]
    caveat_evidence_refs: tuple[str, ...]
    originality_refs: tuple[str, ...]
    rationale: str
    gaps: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "requirement_id": self.requirement_id,
            "status": self.status,
            "evidence_refs": list(self.evidence_refs),
            "caveat_evidence_refs": list(self.caveat_evidence_refs),
            "originality_refs": list(self.originality_refs),
            "rationale": self.rationale,
            "gaps": list(self.gaps),
        }


@dataclass(frozen=True, slots=True)
class CoverageSupportDepthAssessment:
    schema_version: int
    items: tuple[CoverageSupportItem, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "items": [item.to_dict() for item in self.items],
        }


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CoverageSupportDepthError(code)
    return cast(dict[str, object], value)


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CoverageSupportDepthError(code)
    return value.strip()


def _strings(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CoverageSupportDepthError(code)
    output: list[str] = []
    seen: set[str] = set()
    for raw in value:
        item = _text(raw, code)
        if item in seen:
            raise CoverageSupportDepthError(f"{code}_duplicate")
        seen.add(item)
        output.append(item)
    return tuple(output)


def _coverage_ids(coverage_requirements: Sequence[object]) -> tuple[str, ...]:
    ids: list[str] = []
    seen: set[str] = set()
    for raw in coverage_requirements:
        item = _dict(raw, "coverage_support_requirement_invalid")
        requirement_id = _text(
            item.get("id"),
            "coverage_support_requirement_id_required",
        )
        _text(
            item.get("requirement"),
            "coverage_support_requirement_text_required",
        )
        if requirement_id in seen:
            raise CoverageSupportDepthError("coverage_support_requirement_id_duplicate")
        seen.add(requirement_id)
        ids.append(requirement_id)
    return tuple(ids)


def _evidence_relations(evidence_items: Sequence[object]) -> dict[str, str]:
    output: dict[str, str] = {}
    for raw in evidence_items:
        item = _dict(raw, "coverage_support_evidence_input_invalid")
        evidence_id = _text(
            item.get("evidence_id"),
            "coverage_support_evidence_id_required",
        )
        relation = _text(
            item.get("relation"),
            "coverage_support_evidence_relation_required",
        )
        if relation not in {"supports", *_CAVEAT_RELATIONS}:
            raise CoverageSupportDepthError("coverage_support_evidence_relation_invalid")
        if evidence_id in output:
            raise CoverageSupportDepthError("coverage_support_evidence_id_duplicate")
        output[evidence_id] = relation
    return output


def _originality_refs(originality_items: Sequence[object]) -> set[str]:
    refs: set[str] = set()
    for raw in originality_items:
        if not is_usable_originality_item(raw):
            continue
        item = cast(dict[str, object], raw)
        source_ref = _text(
            item.get("source_ref"),
            "coverage_support_originality_source_ref_required",
        )
        if source_ref in refs:
            raise CoverageSupportDepthError(
                "coverage_support_originality_source_ref_duplicate"
            )
        refs.add(source_ref)
    return refs


def validate_coverage_support_depth(
    raw: object,
    *,
    coverage_requirements: Sequence[object],
    evidence_items: Sequence[object],
    originality_items: Sequence[object],
) -> CoverageSupportDepthAssessment:
    """Validate one exact semantic support assessment against allowed snapshots.

    Semantic relevance may be model-assisted upstream. This validator remains the
    deterministic authority for exact coverage IDs, statuses, references and
    contradiction boundaries.
    """

    payload = _dict(raw, "coverage_support_payload_invalid")
    if payload.get("schema_version") != COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION:
        raise CoverageSupportDepthError("coverage_support_schema_invalid")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise CoverageSupportDepthError("coverage_support_items_invalid")

    required_ids = _coverage_ids(coverage_requirements)
    required_set = set(required_ids)
    evidence_relations = _evidence_relations(evidence_items)
    allowed_originality_refs = _originality_refs(originality_items)

    by_id: dict[str, CoverageSupportItem] = {}
    for raw_item in raw_items:
        item = _dict(raw_item, "coverage_support_item_invalid")
        requirement_id = _text(
            item.get("requirement_id"),
            "coverage_support_requirement_id_required",
        )
        if requirement_id not in required_set:
            raise CoverageSupportDepthError("coverage_support_requirement_unknown")
        if requirement_id in by_id:
            raise CoverageSupportDepthError("coverage_support_requirement_duplicate")

        status_raw = _text(item.get("status"), "coverage_support_status_required")
        if status_raw not in _VALID_STATUSES:
            raise CoverageSupportDepthError("coverage_support_status_invalid")
        status = cast(CoverageSupportStatus, status_raw)

        evidence_refs = _strings(
            item.get("evidence_refs"),
            "coverage_support_evidence_refs_invalid",
        )
        caveat_refs = _strings(
            item.get("caveat_evidence_refs"),
            "coverage_support_caveat_refs_invalid",
        )
        originality_refs = _strings(
            item.get("originality_refs"),
            "coverage_support_originality_refs_invalid",
        )
        rationale = _text(item.get("rationale"), "coverage_support_rationale_required")
        gaps = _strings(item.get("gaps"), "coverage_support_gaps_invalid")

        if set(evidence_refs).intersection(caveat_refs):
            raise CoverageSupportDepthError("coverage_support_evidence_ref_role_conflict")

        for ref in evidence_refs:
            relation = evidence_relations.get(ref)
            if relation is None:
                raise CoverageSupportDepthError("coverage_support_evidence_ref_unknown")
            if relation != "supports":
                raise CoverageSupportDepthError(
                    "coverage_support_non_support_evidence_as_support"
                )

        contradicts = False
        for ref in caveat_refs:
            relation = evidence_relations.get(ref)
            if relation is None:
                raise CoverageSupportDepthError("coverage_support_caveat_ref_unknown")
            if relation not in _CAVEAT_RELATIONS:
                raise CoverageSupportDepthError("coverage_support_support_as_caveat")
            if relation == "contradicts":
                contradicts = True

        for ref in originality_refs:
            if ref not in allowed_originality_refs:
                raise CoverageSupportDepthError("coverage_support_originality_ref_unknown")

        if contradicts and status != "unresolved":
            raise CoverageSupportDepthError(
                "coverage_support_contradiction_requires_unresolved"
            )

        if status == "evidence_supported":
            if not evidence_refs or originality_refs or gaps:
                raise CoverageSupportDepthError(
                    "coverage_support_evidence_supported_invalid"
                )
        elif status == "originality_supported":
            if not originality_refs or evidence_refs or gaps:
                raise CoverageSupportDepthError(
                    "coverage_support_originality_supported_invalid"
                )
        elif status == "mixed":
            if not evidence_refs or not originality_refs or gaps:
                raise CoverageSupportDepthError("coverage_support_mixed_invalid")
        else:
            if not gaps:
                raise CoverageSupportDepthError("coverage_support_unresolved_gap_required")

        by_id[requirement_id] = CoverageSupportItem(
            requirement_id=requirement_id,
            status=status,
            evidence_refs=evidence_refs,
            caveat_evidence_refs=caveat_refs,
            originality_refs=originality_refs,
            rationale=rationale,
            gaps=gaps,
        )

    if set(by_id) != required_set:
        raise CoverageSupportDepthError("coverage_support_incomplete")

    return CoverageSupportDepthAssessment(
        schema_version=COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION,
        items=tuple(by_id[requirement_id] for requirement_id in required_ids),
    )


__all__ = [
    "COVERAGE_SUPPORT_DEPTH_SCHEMA_VERSION",
    "CoverageSupportDepthAssessment",
    "CoverageSupportDepthError",
    "CoverageSupportItem",
    "CoverageSupportStatus",
    "validate_coverage_support_depth",
]
