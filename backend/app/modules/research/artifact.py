import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path

from app.modules.research.contracts import ResearchSpikeResult


def _json_default(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"unsupported_json_value:{type(value).__name__}")


def research_spike_json(result: ResearchSpikeResult) -> str:
    return json.dumps(
        asdict(result),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )


def write_research_spike_artifact(result: ResearchSpikeResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(research_spike_json(result), encoding="utf-8")
    return path
