from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from typing import Any

from app.modules.harness.agent_runner import (
    AgentRunRequest,
    AgentRunnerError,
    AntigravityCliRunner,
)

_PROVIDER = "antigravity_cli"
_AUDIT_MARKER = "agy01"
_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "echo", "items"],
    "properties": {
        "status": {"type": "string", "enum": ["ok"]},
        "echo": {"type": "string", "enum": [_AUDIT_MARKER]},
        "items": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {
                "type": "string",
                "enum": ["bounded", "schema"],
            },
        },
    },
}


class Agy01AuditError(RuntimeError):
    def __init__(self, code: str, *, evidence: dict[str, object] | None = None) -> None:
        self.code = code
        self.evidence = dict(evidence or {})
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Antigravity as a bounded schema-constrained content executor."
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--executable", default="agy")
    parser.add_argument("--timeout", type=float, default=90.0)
    return parser.parse_args()


def _validate_output(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise Agy01AuditError("agy01_output_not_object")
    if set(value) != {"status", "echo", "items"}:
        raise Agy01AuditError("agy01_output_shape_invalid")
    if value.get("status") != "ok" or value.get("echo") != _AUDIT_MARKER:
        raise Agy01AuditError("agy01_output_value_invalid")
    items = value.get("items")
    if (
        not isinstance(items, list)
        or len(items) != 2
        or set(items) != {"bounded", "schema"}
    ):
        raise Agy01AuditError("agy01_output_items_invalid")
    return value


async def audit_antigravity(
    *,
    model: str,
    executable: str,
    timeout: float,
    runner: AntigravityCliRunner | None = None,
) -> dict[str, object]:
    if not model.strip():
        raise Agy01AuditError("agy01_model_required")
    if timeout <= 0:
        raise Agy01AuditError("agy01_timeout_invalid")

    selected_runner = runner or AntigravityCliRunner(executable=executable)
    capability = await selected_runner.preflight()
    if (
        capability.provider != _PROVIDER
        or not capability.authenticated
        or not capability.model_selection
    ):
        raise Agy01AuditError("agy01_capability_invalid")

    request = AgentRunRequest(
        provider=_PROVIDER,
        model=model.strip(),
        prompt=(
            "Return only one JSON object matching the supplied schema. "
            "Use status=ok, echo=agy01, and exactly two items: bounded and schema."
        ),
        structured_output_schema=_SCHEMA,
        working_context={
            "audit": "AGY-01",
            "purpose": "content_executor_capability",
            "tools_allowed": False,
            "repository_context_allowed": False,
        },
        timeout=timeout,
        repository=None,
    )
    result = await selected_runner.run(request)
    output = _validate_output(result.structured_output)
    if result.provider != _PROVIDER or result.model != model.strip():
        raise Agy01AuditError("agy01_result_identity_mismatch")
    if result.exit_code != 0:
        raise Agy01AuditError("agy01_nonzero_result")

    capability_payload = asdict(capability)
    capability_payload.pop("model_selection", None)
    return {
        "status": "PASS_ANTIGRAVITY_CONTENT_EXECUTOR_CAPABILITY",
        "provider": result.provider,
        "model": result.model,
        "capability": capability_payload,
        "structured_output": output,
        "raw_output_hash": result.raw_output_hash,
        "duration_ms": result.duration_ms,
        "usage": result.usage,
        "repository_context_used": result.repository_revision is not None,
    }


def _blocked_payload(exc: Exception) -> dict[str, object]:
    if isinstance(exc, Agy01AuditError):
        return {
            "status": f"BLOCKED_AGY01_{exc.code.upper()}",
            "blocker": exc.code,
            "evidence": exc.evidence,
        }
    if isinstance(exc, AgentRunnerError):
        evidence: dict[str, Any] = {}
        for key in (
            "diagnostic_code",
            "exit_code",
            "stderr_hash",
            "stdout_hash",
            "diagnostic_source",
        ):
            value = getattr(exc, key, None)
            if value is not None:
                evidence[key] = value
        return {
            "status": f"BLOCKED_AGY01_{exc.code.upper()}",
            "blocker": exc.code,
            "evidence": evidence,
        }
    return {
        "status": "BLOCKED_AGY01_UNEXPECTED_FAILURE",
        "blocker": type(exc).__name__,
        "evidence": {},
    }


async def _main() -> int:
    args = _parse_args()
    try:
        result = await audit_antigravity(
            model=args.model,
            executable=args.executable,
            timeout=args.timeout,
        )
    except Exception as exc:
        print(json.dumps(_blocked_payload(exc), sort_keys=True, indent=2))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
