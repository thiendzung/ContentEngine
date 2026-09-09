"""Safe, provider-neutral adapters for locally authenticated CLI agents."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class AgentRunnerError(RuntimeError):
    """Raised when a local agent cannot be used safely."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AgentRunRequest:
    provider: str
    model: str
    prompt: str
    structured_output_schema: dict[str, object]
    working_context: dict[str, object]
    timeout: float


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    provider: str
    model: str
    runner_version: str
    structured_output: object
    raw_output_hash: str
    exit_code: int
    usage: dict[str, object] | None
    duration_ms: int
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class AgentCapability:
    provider: str
    executable: str
    version: str
    authenticated: bool
    auth_mode: str
    model_selection: bool = True


class AgentRunner(Protocol):
    async def preflight(self) -> AgentCapability: ...

    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...


class AgentRunnerRegistry:
    """Resolve only explicitly registered provider keys."""

    def __init__(self) -> None:
        self._runners: dict[str, AgentRunner] = {}

    def register(self, provider: str, runner: AgentRunner) -> None:
        if not provider.strip():
            raise ValueError("provider is required")
        self._runners[provider] = runner

    def get(self, provider: str) -> AgentRunner:
        try:
            return self._runners[provider]
        except KeyError as exc:
            raise AgentRunnerError("agent_provider_unregistered") from exc


_SAFE_ENV_KEYS = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "CODEX_HOME",
    "AGY_HOME",
)
_FORBIDDEN_CONTEXT_KEYS = {
    "raw_provider_payload",
    "provider_payload",
    "search_snippets",
    "raw_search_payload",
    "repository_context",
    "repo_context",
    "secrets",
    "environment",
    "env",
    "openai_api_key",
    "gemini_api_key",
}


def _safe_environment() -> dict[str, str]:
    """Pass only CLI process basics; API-key environment variables never cross the boundary."""

    return {
        key: value
        for key in _SAFE_ENV_KEYS
        if (value := os.environ.get(key)) is not None
    }


def _validate_request(request: AgentRunRequest, provider: str) -> None:
    if request.provider != provider:
        raise AgentRunnerError("agent_provider_mismatch")
    if not request.model.strip() or not request.prompt.strip():
        raise AgentRunnerError("agent_request_invalid")
    if (
        not isinstance(request.structured_output_schema, dict)
        or not request.structured_output_schema
    ):
        raise AgentRunnerError("agent_output_schema_required")
    if (
        isinstance(request.timeout, bool)
        or not isinstance(request.timeout, (int, float))
        or request.timeout <= 0
    ):
        raise AgentRunnerError("agent_timeout_invalid")
    _validate_sanitized_context(request.working_context)


def _validate_sanitized_context(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in _FORBIDDEN_CONTEXT_KEYS or "api_key" in normalized_key:
                raise AgentRunnerError("agent_context_not_sanitized")
            _validate_sanitized_context(child)
    elif isinstance(value, list):
        for child in value:
            _validate_sanitized_context(child)


def _prompt_with_context(request: AgentRunRequest) -> str:
    context = json.dumps(
        request.working_context,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{request.prompt.rstrip()}\n\nSANITIZED_WORKING_CONTEXT_JSON:\n{context}\n"


def _hash_output(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def _safe_usage(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    allowed = {
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cost",
    }
    result: dict[str, object] = {}
    for key in allowed:
        item = value.get(key)
        if isinstance(item, (str, int, float)) and not isinstance(item, bool):
            result[key] = item
    return result or None


def _safe_session_id(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        return None
    return value.strip()


def _nested_final_value(value: object) -> object | None:
    if isinstance(value, (list, str)):
        if isinstance(value, list):
            return value
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, (dict, list)) else None
    if not isinstance(value, dict):
        return None
    if "candidates" in value:
        return value
    for key in ("structured_output", "output", "last_message", "result"):
        if key in value:
            nested = _nested_final_value(value[key])
            if nested is not None:
                return nested
    item = value.get("item")
    if isinstance(item, dict) and item.get("type") in {"agent_message", "assistant_message"}:
        return _nested_final_value(item.get("text"))
    if "type" not in value:
        return value
    return None


def _parse_final_output(raw: bytes) -> tuple[object, dict[str, object] | None, str | None]:
    text = _decode(raw).strip()
    if not text:
        raise AgentRunnerError("agent_output_invalid")
    candidates: list[object] = []
    try:
        candidates.append(json.loads(text))
    except json.JSONDecodeError:
        candidates.extend(
            json.loads(line)
            for line in reversed(text.splitlines())
            if line.strip()
            and _is_json_line(line)
        )
    for item in candidates:
        final = _nested_final_value(item)
        if final is not None:
            usage = item.get("usage") if isinstance(item, dict) else None
            session_id = None
            if isinstance(item, dict):
                session_id = _safe_session_id(
                    item.get("session_id") or item.get("conversation_id")
                )
            return final, _safe_usage(usage), session_id
    raise AgentRunnerError("agent_output_invalid")


def _is_json_line(line: str) -> bool:
    try:
        json.loads(line)
    except json.JSONDecodeError:
        return False
    return True


@dataclass(frozen=True, slots=True)
class _CommandResult:
    stdout: bytes
    stderr: bytes
    exit_code: int


async def _run_command(argv: list[str], *, timeout: float) -> _CommandResult:
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_safe_environment(),
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except FileNotFoundError as exc:
        raise AgentRunnerError("agent_executable_missing") from exc
    except TimeoutError as exc:
        raise AgentRunnerError("agent_preflight_timeout") from exc
    return _CommandResult(stdout=stdout, stderr=stderr, exit_code=process.returncode or 0)


class _CliRunner:
    provider: str
    executable: str
    auth_args: tuple[str, ...]

    def __init__(self, *, executable: str, provider: str, auth_args: tuple[str, ...]) -> None:
        self.executable = executable
        self.provider = provider
        self.auth_args = auth_args

    def _ensure_executable(self) -> None:
        if shutil.which(self.executable) is None:
            raise AgentRunnerError("agent_executable_missing")

    def _auth_mode(self, output: bytes) -> str | None:
        text = _decode(output).lower()
        if "api key" in text or "api_key" in text:
            return None
        if any(
            marker in text
            for marker in ("logged in", "authenticated", "oauth", "google", "chatgpt")
        ):
            return "cached_session"
        return None

    async def preflight(self) -> AgentCapability:
        self._ensure_executable()
        version = await _run_command([self.executable, "--version"], timeout=10.0)
        if version.exit_code != 0:
            raise AgentRunnerError("agent_version_check_failed")
        version_text = (_decode(version.stdout) or _decode(version.stderr)).strip()
        if not version_text:
            raise AgentRunnerError("agent_version_check_failed")
        auth = await _run_command([self.executable, *self.auth_args], timeout=10.0)
        auth_mode = self._auth_mode(auth.stdout + b"\n" + auth.stderr)
        if auth.exit_code != 0 or auth_mode is None:
            raise AgentRunnerError("agent_auth_required")
        return AgentCapability(
            provider=self.provider,
            executable=self.executable,
            version=version_text.splitlines()[0][:200],
            authenticated=True,
            auth_mode=auth_mode,
        )

    async def _execute(
        self,
        request: AgentRunRequest,
        *,
        runner_version: str,
        argv_builder: Callable[[Path, Path], list[str]],
    ) -> AgentRunResult:
        _validate_request(request, self.provider)
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="ce05-agent-") as temp_dir:
            workdir = Path(temp_dir)
            schema_path = workdir / "output-schema.json"
            result_path = workdir / "final-output.json"
            schema_path.write_text(
                json.dumps(
                    request.structured_output_schema,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            argv = argv_builder(schema_path, result_path)
            try:
                process = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=temp_dir,
                    env=_safe_environment(),
                )
                if process.stdin is None:
                    raise AgentRunnerError("agent_stdin_unavailable")
                process.stdin.write(_prompt_with_context(request).encode("utf-8"))
                await process.stdin.drain()
                process.stdin.close()
                await process.stdin.wait_closed()
                stdout, _stderr = await asyncio.wait_for(
                    process.communicate(), timeout=request.timeout
                )
            except FileNotFoundError as exc:
                raise AgentRunnerError("agent_executable_missing") from exc
            except TimeoutError as exc:
                process.kill()
                await process.communicate()
                raise AgentRunnerError("agent_timeout") from exc
            duration_ms = int((time.monotonic() - started) * 1000)
            raw_output = result_path.read_bytes() if result_path.exists() else stdout
            raw_hash = _hash_output(raw_output)
            exit_code = process.returncode or 0
            if exit_code != 0:
                raise AgentRunnerError("agent_nonzero_exit")
            structured, usage, session_id = _parse_final_output(raw_output)
            return AgentRunResult(
                provider=request.provider,
                model=request.model,
                runner_version=runner_version,
                structured_output=structured,
                raw_output_hash=raw_hash,
                exit_code=exit_code,
                usage=usage,
                duration_ms=duration_ms,
                session_id=session_id,
            )


class CodexCliRunner(_CliRunner):
    """Run Codex using cached ChatGPT login and a read-only isolated process."""

    _NO_TOOL_FEATURES = (
        "shell_tool",
        "unified_exec",
        "code_mode",
        "apps",
        "plugins",
        "enable_mcp_apps",
    )

    def __init__(self, *, executable: str = "codex") -> None:
        super().__init__(
            executable=executable,
            provider="codex_cli",
            auth_args=("login", "status"),
        )

    async def _verify_no_tool_support(self) -> None:
        """Verify this installed CLI can explicitly disable every unsafe surface."""

        help_result = await _run_command(
            [self.executable, "exec", "--help"],
            timeout=10.0,
        )
        help_text = _decode(help_result.stdout + b"\n" + help_result.stderr)
        if help_result.exit_code != 0 or "--disable" not in help_text:
            raise AgentRunnerError("agent_tool_disable_unsupported")

        feature_result = await _run_command(
            [self.executable, "features", "list"],
            timeout=10.0,
        )
        if feature_result.exit_code != 0:
            raise AgentRunnerError("agent_tool_disable_unsupported")
        supported = {
            line.split()[0]
            for line in _decode(feature_result.stdout).splitlines()
            if len(line.split()) >= 3
        }
        if not set(self._NO_TOOL_FEATURES).issubset(supported):
            raise AgentRunnerError("agent_tool_disable_unsupported")

    async def preflight(self) -> AgentCapability:
        self._ensure_executable()
        version = await _run_command([self.executable, "--version"], timeout=10.0)
        if version.exit_code != 0:
            raise AgentRunnerError("agent_version_check_failed")
        version_text = (_decode(version.stdout) or _decode(version.stderr)).strip()
        if not version_text:
            raise AgentRunnerError("agent_version_check_failed")
        await self._verify_no_tool_support()
        auth = await _run_command([self.executable, *self.auth_args], timeout=10.0)
        auth_mode = self._auth_mode(auth.stdout + b"\n" + auth.stderr)
        if auth.exit_code != 0 or auth_mode is None:
            raise AgentRunnerError("agent_auth_required")
        return AgentCapability(
            provider=self.provider,
            executable=self.executable,
            version=version_text.splitlines()[0][:200],
            authenticated=True,
            auth_mode=auth_mode,
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        capability = await self.preflight()

        def argv(schema_path: Path, result_path: Path) -> list[str]:
            return [
                self.executable,
                "exec",
                "--model",
                request.model,
                "--json",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(result_path),
                "--sandbox",
                "read-only",
                "--disable",
                "shell_tool",
                "--disable",
                "unified_exec",
                "--disable",
                "code_mode",
                "--disable",
                "apps",
                "--disable",
                "plugins",
                "--disable",
                "enable_mcp_apps",
                "-c",
                'web_search="disabled"',
                "--skip-git-repo-check",
                "--ignore-user-config",
                "--ephemeral",
                "-",
            ]

        return await self._execute(
            request,
            runner_version=capability.version,
            argv_builder=argv,
        )


class AntigravityCliRunner(_CliRunner):
    """Run Antigravity headless with JSON-schema output and read-only isolation."""

    def __init__(self, *, executable: str = "agy") -> None:
        super().__init__(
            executable=executable,
            provider="antigravity_cli",
            auth_args=("auth", "status"),
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        capability = await self.preflight()

        def argv(schema_path: Path, _result_path: Path) -> list[str]:
            return [
                self.executable,
                "headless",
                "--model",
                request.model,
                "--output-format",
                "json",
                "--json-schema",
                str(schema_path),
                "--sandbox",
                "read-only",
                "-",
            ]

        return await self._execute(
            request,
            runner_version=capability.version,
            argv_builder=argv,
        )


def default_agent_runner_registry() -> AgentRunnerRegistry:
    registry = AgentRunnerRegistry()
    registry.register("codex_cli", CodexCliRunner())
    registry.register("antigravity_cli", AntigravityCliRunner())
    return registry


__all__ = [
    "AgentCapability",
    "AgentRunRequest",
    "AgentRunResult",
    "AgentRunner",
    "AgentRunnerError",
    "AgentRunnerRegistry",
    "AntigravityCliRunner",
    "CodexCliRunner",
    "default_agent_runner_registry",
]
