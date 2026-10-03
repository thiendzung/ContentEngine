from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.harness.agent_runner import AgentCapability, AgentRunResult
from scripts import ops_agy01_capability as agy01


class FakeRunner:
    def __init__(self) -> None:
        self.request = None

    async def preflight(self) -> AgentCapability:
        return AgentCapability(
            provider="antigravity_cli",
            executable="/tmp/agy",
            version="agy 1.0.0",
            authenticated=True,
            auth_mode="cached_session",
            model_selection=True,
        )

    async def run(self, request):
        self.request = request
        return AgentRunResult(
            provider="antigravity_cli",
            model=request.model,
            runner_version="agy 1.0.0",
            structured_output={
                "status": "ok",
                "echo": "agy01",
                "items": ["bounded", "schema"],
            },
            raw_output_hash="a" * 64,
            exit_code=0,
            usage=None,
            duration_ms=10,
            runner_executable="/tmp/agy",
            session_id=None,
            repository_revision=None,
            repository_tree_hash=None,
        )


@pytest.mark.asyncio
async def test_agy01_uses_no_repository_context_and_requires_schema() -> None:
    runner = FakeRunner()

    result = await agy01.audit_antigravity(
        model="test-gemini",
        executable="agy",
        timeout=30.0,
        runner=runner,  # type: ignore[arg-type]
    )

    assert result["status"] == "PASS_ANTIGRAVITY_CONTENT_EXECUTOR_CAPABILITY"
    assert result["repository_context_used"] is False
    assert runner.request is not None
    assert runner.request.repository is None
    assert runner.request.provider == "antigravity_cli"
    assert runner.request.model == "test-gemini"
    assert runner.request.structured_output_schema == agy01._SCHEMA
    assert runner.request.working_context["tools_allowed"] is False
    assert runner.request.working_context["repository_context_allowed"] is False


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ([], "agy01_output_not_object"),
        ({"status": "ok"}, "agy01_output_shape_invalid"),
        (
            {"status": "bad", "echo": "agy01", "items": ["bounded", "schema"]},
            "agy01_output_value_invalid",
        ),
        (
            {"status": "ok", "echo": "agy01", "items": ["bounded"]},
            "agy01_output_items_invalid",
        ),
    ],
)
def test_agy01_rejects_invalid_structured_output(value: object, code: str) -> None:
    with pytest.raises(agy01.Agy01AuditError, match=code):
        agy01._validate_output(value)


def test_agy01_source_has_no_polling_or_db_access() -> None:
    source = Path(agy01.__file__).read_text(encoding="utf-8")

    assert "asyncio.sleep(" not in source
    assert "time.sleep(" not in source
    assert "pgrep" not in source
    assert "ps " not in source
    assert "sqlalchemy" not in source
    assert "SessionLocal" not in source
    assert "database" not in source.casefold()


def test_agy01_blocked_payload_does_not_include_raw_provider_text() -> None:
    payload = agy01._blocked_payload(
        agy01.AgentRunnerError(
            "agent_nonzero_exit",
            diagnostic_code="agent_cli_model_unavailable",
            exit_code=1,
            stderr_hash="b" * 64,
            stdout_hash="c" * 64,
            diagnostic_source="stderr",
        )
    )

    assert payload["status"] == "BLOCKED_AGY01_AGENT_NONZERO_EXIT"
    assert payload["evidence"] == {
        "diagnostic_code": "agent_cli_model_unavailable",
        "exit_code": 1,
        "stderr_hash": "b" * 64,
        "stdout_hash": "c" * 64,
        "diagnostic_source": "stderr",
    }
