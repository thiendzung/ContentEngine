from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PostgresToolCapability:
    mode: str
    detail: str


def _compose_project_name() -> str:
    return os.environ.get("COMPOSE_PROJECT_NAME", "contentengine")


def _container_tools_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            _compose_project_name(),
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            "command -v pg_dump >/dev/null && command -v pg_restore >/dev/null",
        ],
        capture_output=True,
        check=False,
        timeout=10,
    )
    return result.returncode == 0


def postgres_tool_capability() -> PostgresToolCapability | None:
    if shutil.which("pg_dump") and shutil.which("pg_restore"):
        return PostgresToolCapability("host", "pg_dump+pg_restore")
    if _container_tools_ready():
        return PostgresToolCapability("container", "postgres_service:pg_dump+pg_restore")
    return None


def postgres_tool_command(tool: str) -> list[str]:
    if tool not in {"pg_dump", "pg_restore"}:
        raise ValueError("unsupported_postgres_tool")
    capability = postgres_tool_capability()
    if capability is None:
        raise RuntimeError("postgres_tools_unavailable")
    if capability.mode == "host":
        return [tool]
    return [
        "docker",
        "compose",
        "-p",
        _compose_project_name(),
        "exec",
        "-T",
        "postgres",
        tool,
    ]
