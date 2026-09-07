import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from uuid import UUID

from app.modules.research.contracts import ProductionResearchResult, ResearchSpikeResult


def _json_default(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"unsupported_json_value:{type(value).__name__}")


def _result_json(result: ResearchSpikeResult | ProductionResearchResult) -> str:
    return json.dumps(
        asdict(result),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )


def research_spike_json(result: ResearchSpikeResult) -> str:
    return _result_json(result)


def production_research_json(result: ProductionResearchResult) -> str:
    return _result_json(result)


def write_research_spike_artifact(result: ResearchSpikeResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(research_spike_json(result), encoding="utf-8")
    return path


def write_production_research_artifact(
    result: ProductionResearchResult,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(production_research_json(result), encoding="utf-8")
    return path
