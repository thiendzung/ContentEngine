from __future__ import annotations

import re
from pathlib import Path

from app.modules.research.keyword_plan.question_map import (
    QUESTION_MAP_SCHEMA_VERSION,
)

_FRONTEND_CLIENT = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "src"
    / "lib"
    / "api"
    / "question-map.ts"
)


def test_frontend_question_map_schema_matches_backend_contract() -> None:
    source = _FRONTEND_CLIENT.read_text(encoding="utf-8")

    version_match = re.search(
        r"export const QUESTION_MAP_SCHEMA_VERSION = (\d+);",
        source,
    )
    assert version_match is not None
    assert int(version_match.group(1)) == QUESTION_MAP_SCHEMA_VERSION

    assert re.search(
        r"assertSchema\(\s*"
        r"value\.schema_version,\s*"
        r"QUESTION_MAP_SCHEMA_VERSION,\s*"
        r'"question_map_schema_unsupported",?\s*'
        r"\)",
        source,
    )
