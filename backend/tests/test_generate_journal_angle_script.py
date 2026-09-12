from __future__ import annotations

from uuid import UUID

import pytest

from app.modules.content_engine.journal.angle import AngleGenerationError
from app.modules.harness.agent_runner import AntigravityCliRunner, CodexCliRunner
from scripts.generate_journal_angle import _parser, _runner


def test_generate_journal_angle_parser_requires_exact_runtime_identity() -> None:
    args = _parser().parse_args(
        [
            "--run-id",
            "a92f6f69-1c83-4aca-9a2f-e547dd15b85f",
            "--journal-input-bundle-id",
            "d65aa864-e2fe-4c94-92f3-8d73ea89a8db",
            "--journal-input-bundle-hash",
            "a" * 64,
            "--settings-snapshot-id",
            "1169921c-a649-4f93-bf1a-f8daa2f15338",
            "--settings-snapshot-hash",
            "b" * 64,
            "--expected-provider",
            "codex_cli",
            "--expected-model",
            "gpt-5.6-luna",
        ]
    )

    assert args.run_id == UUID("a92f6f69-1c83-4aca-9a2f-e547dd15b85f")
    assert args.journal_input_bundle_id == UUID("d65aa864-e2fe-4c94-92f3-8d73ea89a8db")
    assert args.settings_snapshot_id == UUID("1169921c-a649-4f93-bf1a-f8daa2f15338")
    assert args.expected_provider == "codex_cli"
    assert args.expected_model == "gpt-5.6-luna"


def test_generate_journal_angle_runner_is_allowlisted() -> None:
    assert isinstance(_runner("codex_cli"), CodexCliRunner)
    assert isinstance(_runner("antigravity_cli"), AntigravityCliRunner)
    with pytest.raises(AngleGenerationError, match="angle_agent_provider_unsupported"):
        _runner("unknown")
