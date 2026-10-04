from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.system.recovery import (
    RecoverySafetyError,
    validate_operational_database_source,
)
from app.modules.system.runtime_maintenance import (
    RuntimeMaintenanceError,
    release_maintenance_exclusive,
    try_acquire_maintenance_exclusive,
)
from scripts import ops_release_lifecycle_0042 as release_lifecycle_0042
from scripts.ops_data02_rehearsal import (
    _EXPECTED_UPGRADE_CHAIN,
    _SOURCE_REVISION,
    _TARGET_REVISION,
    Data02RehearsalError,
    _alembic_script,
    _database_state,
    _expected_fingerprint,
    _full_data_fingerprint,
    _load_manifest,
    _manifest_source_revision,
    _sha256,
    _source_documents_fingerprint,
    _upgrade_chain,
)

_EXPECTED_SOURCE_DATABASE = "contentengine"
_RUNTIME_PORTS = (8000, 3000)
_FROZEN_TABLES = (
    "jobs",
    "step_runs",
    "model_calls",
    "tool_calls",
    "outbox_intents",
)
_PROMPT_KEYS = (
    "journal_coverage_support_depth_en",
    "journal_coverage_support_depth_vi",
)
_RECIPE_KEYS = (
    "journal_coverage_support_depth_en_v1",
    "journal_coverage_support_depth_vi_v1",
)
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OperationalMigration0044Error(RuntimeError):
    """Raised when the bounded 0034 -> 0044 operational contract is unsafe."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed operational migration from ContentEngine rev-0034 "
            "to rev-0044 using an exact fresh recovery point"
        )
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument("--manifest", type=Path)