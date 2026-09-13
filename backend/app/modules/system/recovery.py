from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from app.modules.content_engine.models import ContentCase, ContentVersion
from app.modules.harness.models import Approval, Artifact, ContentRun


class RecoverySafetyError(RuntimeError):
    """Raised when backup/restore recovery boundaries are unsafe."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DatabaseFingerprint:
    content_cases: int
    content_runs: int
    approvals: int
    artifacts: int
    content_versions: int
    artifact_hash: str
    lineage_hash: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _identity(url: URL) -> tuple[str, int | None, str]:
    return ((url.host or "").lower(), url.port, (url.database or "").lower())


def validate_restore_target(*, source_url: str, restore_url: str) -> URL:
    source = make_url(source_url)
    target = make_url(restore_url)
    database_name = target.database or ""
    if target.get_backend_name() != "postgresql":
        raise RecoverySafetyError("restore_database_backend_unsupported")
    if "restore_test" not in database_name.lower():
        raise RecoverySafetyError("unsafe_restore_database_name")
    if _identity(source) == _identity(target):
        raise RecoverySafetyError("restore_database_matches_source")
    return target


def _digest(values: list[str]) -> str:
    payload = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def database_fingerprint(engine: AsyncEngine) -> DatabaseFingerprint:
    async with engine.connect() as connection:
        case_ids = [str(value) for value in (await connection.execute(select(ContentCase.id))).scalars()]
        run_rows = list(
            (
                await connection.execute(
                    select(
                        ContentRun.id,
                        ContentRun.content_case_id,
                        ContentRun.locale_variant_id,
                        ContentRun.status,
                    )
                )
            ).all()
        )
        approval_rows = list(
            (
                await connection.execute(
                    select(
                        Approval.id,
                        Approval.run_id,
                        Approval.artifact_id,
                        Approval.step_key,
                        Approval.decision,
                    )
                )
            ).all()
        )
        artifact_rows = list(
            (
                await connection.execute(
                    select(
                        Artifact.id,
                        Artifact.run_id,
                        Artifact.step_run_id,
                        Artifact.artifact_type,
                        Artifact.version,
                        Artifact.content_hash,
                    )
                )
            ).all()
        )
        version_rows = list(
            (
                await connection.execute(
                    select(
                        ContentVersion.id,
                        ContentVersion.content_item_id,
                        ContentVersion.final_artifact_id,
                        ContentVersion.created_by_run_id,
                        ContentVersion.version_no,
                        ContentVersion.status,
                    )
                )
            ).all()
        )

    artifact_values = [
        ":".join("" if value is None else str(value) for value in row)
        for row in artifact_rows
    ]
    lineage_values = [f"case:{value}" for value in case_ids]
    lineage_values.extend(
        "run:" + ":".join("" if value is None else str(value) for value in row)
        for row in run_rows
    )
    lineage_values.extend(
        "approval:" + ":".join("" if value is None else str(value) for value in row)
        for row in approval_rows
    )
    lineage_values.extend(
        "artifact:" + ":".join("" if value is None else str(value) for value in row)
        for row in artifact_rows
    )
    lineage_values.extend(
        "version:" + ":".join("" if value is None else str(value) for value in row)
        for row in version_rows
    )
    return DatabaseFingerprint(
        content_cases=len(case_ids),
        content_runs=len(run_rows),
        approvals=len(approval_rows),
        artifacts=len(artifact_rows),
        content_versions=len(version_rows),
        artifact_hash=_digest(artifact_values),
        lineage_hash=_digest(lineage_values),
    )
