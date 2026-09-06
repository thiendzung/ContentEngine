import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from app.modules.research.contracts import (
    ResearchSignalKind,
    ResearchSpikeResult,
    SearchSignal,
)
from app.modules.research.keyword_plan.contracts import OpportunityMapResult


def _json_default(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"unsupported_json_value:{type(value).__name__}")


def opportunity_map_json(result: OpportunityMapResult) -> str:
    return json.dumps(
        asdict(result),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )


def opportunity_map_markdown(result: OpportunityMapResult) -> str:
    hypothesis = result.need_hypothesis
    lines = [
        "# Opportunity Map Mini",
        "",
        f"Seed: {result.seed}",
        f"Locale: {result.locale}",
        "",
        "## Need hypothesis",
        "",
        f"- Statement: {hypothesis.statement}",
        f"- Status: {hypothesis.status.value}",
        f"- Audience: {hypothesis.audience_scope}",
        f"- Situation: {hypothesis.situation}",
        f"- Support signals: {len(hypothesis.support_signal_refs)}",
        f"- Contradiction signals: {len(hypothesis.contradict_signal_refs)}",
        "",
        "### Alternative explanations",
        "",
    ]
    lines.extend(f"- {item}" for item in hypothesis.alternative_explanations)
    lines.extend(["", "### Missing evidence", ""])
    lines.extend(f"- {item}" for item in hypothesis.missing_evidence)
    lines.extend(["", "## Opportunities", ""])
    for index, opportunity in enumerate(result.opportunities, start=1):
        lines.extend(
            [
                f"### {index}. {opportunity.question}",
                "",
                f"- ID: `{opportunity.id}`",
                f"- Topic: {opportunity.topic_key}",
                f"- Intent: {opportunity.intent.value}",
                f"- Type: {opportunity.suggested_content_type.value}",
                f"- Role: {opportunity.suggested_role.value if opportunity.suggested_role else '-'}",
                f"- Decision: {opportunity.decision.value}",
                f"- Priority: {opportunity.priority.value}",
                f"- Search/signal refs: {len(opportunity.signal_refs)}",
                f"- MOTGU material refs: {len(opportunity.motgu_material_refs)}",
                f"- Promise: {opportunity.promise}",
                f"- New value: {opportunity.what_is_actually_new}",
                f"- Next step: {opportunity.next_discovery_step}",
                "- Reasons:",
            ]
        )
        lines.extend(f"  - {reason}" for reason in opportunity.reasons)
        if opportunity.material_gaps:
            lines.append("- Material gaps:")
            lines.extend(f"  - {gap}" for gap in opportunity.material_gaps)
        lines.append("")
    lines.extend(["## Research gaps", ""])
    lines.extend(f"- {gap}" for gap in result.research_gaps)
    if result.niche_candidates:
        lines.extend(["", "## Niche candidate", ""])
        for niche in result.niche_candidates:
            lines.extend(
                [
                    f"- Audience: {niche.audience}",
                    f"- Need: {niche.need}",
                    f"- Question pattern: {niche.question_pattern}",
                    f"- Content gap: {niche.content_gap}",
                    f"- Business path: {niche.business_path}",
                    "- MOTGU Right-to-Win:",
                ]
            )
            lines.extend(f"  - {item}" for item in niche.motgu_right_to_win)
    if result.human_selection:
        lines.extend(
            [
                "",
                "## Human selection",
                "",
                f"- Opportunity: `{result.human_selection.opportunity_id}`",
                f"- Selected by: {result.human_selection.selected_by}",
                f"- Reason: {result.human_selection.reason}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_opportunity_map_artifacts(
    result: OpportunityMapResult,
    *,
    json_path: Path,
    markdown_path: Path | None = None,
) -> tuple[Path, Path | None]:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(opportunity_map_json(result), encoding="utf-8")
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(opportunity_map_markdown(result), encoding="utf-8")
    return json_path, markdown_path


def load_research_spike_for_opportunity_map(path: Path) -> ResearchSpikeResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("research_artifact_object_required")
    seed = _required_string(payload, "seed")
    created_at = str(payload.get("created_at") or "")
    raw_signals = payload.get("signals")
    if not isinstance(raw_signals, list):
        raise ValueError("research_artifact_signals_required")
    signals: list[SearchSignal] = []
    for raw in raw_signals:
        if not isinstance(raw, dict):
            continue
        try:
            kind = ResearchSignalKind(str(raw.get("kind") or ""))
        except ValueError:
            continue
        text = str(raw.get("text") or "").strip()
        query = str(raw.get("query") or "").strip()
        provider = str(raw.get("provider") or "").strip()
        if not text or not query or not provider:
            continue
        position_value = raw.get("position")
        position = position_value if isinstance(position_value, int) else None
        signals.append(
            SearchSignal(
                provider=provider,
                query=query,
                kind=kind,
                text=text,
                title=_optional_string(raw.get("title")),
                url=_optional_string(raw.get("url")),
                snippet=_optional_string(raw.get("snippet")),
                position=position,
            )
        )
    if not signals:
        raise ValueError("research_artifact_has_no_usable_signals")
    return ResearchSpikeResult(
        seed=seed,
        seed_origin=str(payload.get("seed_origin") or "founder_proposed"),
        hypothesis_status=str(payload.get("hypothesis_status") or "PROPOSED"),
        created_at=created_at,
        signals=signals,
    )


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"research_artifact_{key}_required")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
