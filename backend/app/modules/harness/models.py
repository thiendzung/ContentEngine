"""Persisted CE02 run records and the CE03 durable queue core."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> UUID:
    return uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class ContentRun(TimestampMixin, Base):
    __tablename__ = "content_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    content_case_id: Mapped[UUID] = mapped_column(ForeignKey("content_cases.id"), nullable=False)
    locale_variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("locale_variants.id"), nullable=False
    )
    content_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("content_items.id"))
    run_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    current_step: Mapped[str | None] = mapped_column(String(64))
    settings_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("settings_snapshots.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "run_mode in ('create','update','refresh','localize','eval')",
            name="ck_content_run_mode",
        ),
        CheckConstraint(
            "status in ('pending','running','waiting_approval','completed','failed','cancelled')",
            name="ck_content_run_status",
        ),
    )


class StepRun(TimestampMixin, Base):
    __tablename__ = "step_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    input_artifact_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    output_artifact_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_json: Mapped[dict[str, object] | None] = mapped_column(JSON)

    __table_args__ = (
        CheckConstraint("attempt > 0", name="ck_step_run_attempt_positive"),
        CheckConstraint(
            "status in ('pending','running','completed','failed','skipped')",
            name="ck_step_run_status",
        ),
        UniqueConstraint("run_id", "step_key", "attempt", name="uq_step_run_attempt"),
    )


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    step_run_id: Mapped[UUID] = mapped_column(ForeignKey("step_runs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lease_owner: Mapped[str | None] = mapped_column(String(200))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        CheckConstraint("attempt > 0", name="ck_job_attempt_positive"),
        CheckConstraint(
            "status in ('queued','leased','completed','failed','cancelled')",
            name="ck_job_status",
        ),
        UniqueConstraint("dedupe_key", name="uq_job_dedupe_key"),
    )


class Artifact(TimestampMixin, Base):
    __tablename__ = "artifacts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    step_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("step_runs.id"))
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    locale: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    external_ref: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        CheckConstraint("version > 0", name="ck_artifact_version_positive"),
        CheckConstraint(
            "content_json is not null or external_ref is not null",
            name="ck_artifact_has_content",
        ),
        UniqueConstraint("run_id", "artifact_type", "version", name="uq_artifact_run_type_version"),
    )


class Approval(TimestampMixin, Base):
    __tablename__ = "approvals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_id: Mapped[UUID] = mapped_column(ForeignKey("artifacts.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "decision in ('approved','rejected','changes_requested')",
            name="ck_approval_decision",
        ),
    )


class ContextManifest(TimestampMixin, Base):
    __tablename__ = "context_manifests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    step_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("step_runs.id"))
    settings_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("settings_snapshots.id"), nullable=False
    )
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    recipe_version: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_set_id: Mapped[UUID | None] = mapped_column(ForeignKey("evidence_sets.id"))
    originality_pack_id: Mapped[UUID | None] = mapped_column(ForeignKey("originality_packs.id"))
    context_artifact_id: Mapped[UUID | None] = mapped_column(ForeignKey("artifacts.id"))
    approved_knowledge_refs_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    knowledge_chunk_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    golden_example_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    tool_result_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ModelCall(TimestampMixin, Base):
    __tablename__ = "model_calls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    step_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("step_runs.id"))
    context_manifest_id: Mapped[UUID | None] = mapped_column(ForeignKey("context_manifests.id"))
    task_key: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    finish_reason: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_class: Mapped[str | None] = mapped_column(String(64))
    result_artifact_id: Mapped[UUID | None] = mapped_column(ForeignKey("artifacts.id"))

    __table_args__ = (
        CheckConstraint(
            "status in ('pending','running','completed','failed')", name="ck_model_call_status"
        ),
    )


class ToolCall(TimestampMixin, Base):
    __tablename__ = "tool_calls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    step_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("step_runs.id"))
    tool_key: Mapped[str] = mapped_column(String(100), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_ref: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_class: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint(
            "status in ('pending','running','completed','failed')", name="ck_tool_call_status"
        ),
    )


class QualityEvaluation(TimestampMixin, Base):
    __tablename__ = "quality_evaluations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    artifact_id: Mapped[UUID] = mapped_column(ForeignKey("artifacts.id"), nullable=False)
    evaluator_key: Mapped[str] = mapped_column(String(100), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(100), nullable=False)
    evaluator_type: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    severity: Mapped[str | None] = mapped_column(String(32))
    findings_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint("result in ('pass','fail','warn')", name="ck_quality_evaluation_result"),
        CheckConstraint(
            "evaluator_type in ('deterministic','model','human')",
            name="ck_quality_evaluation_type",
        ),
    )
