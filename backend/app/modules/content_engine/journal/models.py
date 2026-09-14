"""Durable CE05 Journal approval and operator-control records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.harness.models import TimestampMixin, new_id


class AngleApproval(TimestampMixin, Base):
    """One immutable human decision for one exact Angle artifact snapshot."""

    __tablename__ = "angle_approvals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    angle_artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False
    )
    angle_artifact_version: Mapped[int] = mapped_column(nullable=False)
    angle_artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_angle_id: Mapped[str] = mapped_column(String(200), nullable=False)
    selected_candidate_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(200), nullable=False)
    approval_reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "angle_artifact_id",
            "angle_artifact_version",
            "angle_artifact_hash",
            name="uq_angle_approval_artifact_snapshot",
        ),
        CheckConstraint(
            "angle_artifact_version > 0",
            name="ck_angle_approval_artifact_version_positive",
        ),
        CheckConstraint(
            "angle_artifact_hash ~ '^[0-9a-f]{64}$'",
            name="ck_angle_approval_artifact_hash",
        ),
        CheckConstraint(
            "selected_candidate_hash ~ '^[0-9a-f]{64}$'",
            name="ck_angle_approval_candidate_hash",
        ),
        CheckConstraint("btrim(selected_angle_id) <> ''", name="ck_angle_approval_angle_id"),
        CheckConstraint("btrim(approved_by) <> ''", name="ck_angle_approval_approved_by"),
        CheckConstraint("btrim(approval_reason) <> ''", name="ck_angle_approval_reason"),
        Index("ix_angle_approvals_artifact", "angle_artifact_id"),
    )


class OutlineApproval(TimestampMixin, Base):
    """One immutable human decision for one exact Outline artifact snapshot."""

    __tablename__ = "outline_approvals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("content_runs.id"), nullable=False)
    outline_artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False
    )
    outline_artifact_version: Mapped[int] = mapped_column(nullable=False)
    outline_artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(200), nullable=False)
    approval_reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "outline_artifact_id",
            "outline_artifact_version",
            "outline_artifact_hash",
            name="uq_outline_approval_artifact_snapshot",
        ),
        CheckConstraint(
            "outline_artifact_version > 0",
            name="ck_outline_approval_artifact_version_positive",
        ),
        CheckConstraint(
            "outline_artifact_hash ~ '^[0-9a-f]{64}$'",
            name="ck_outline_approval_artifact_hash",
        ),
        CheckConstraint("btrim(approved_by) <> ''", name="ck_outline_approval_approved_by"),
        CheckConstraint("btrim(approval_reason) <> ''", name="ck_outline_approval_reason"),
        Index("ix_outline_approvals_artifact", "outline_artifact_id"),
    )


class JournalIntakeSpec(TimestampMixin, Base):
    """Immutable operational scope attached to one Founder-manual Journal case."""

    __tablename__ = "journal_intake_specs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    content_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_cases.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    source_locale: Mapped[str] = mapped_column(String(32), nullable=False)
    research_country: Mapped[str] = mapped_column(String(8), nullable=False)
    intake_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_by: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "btrim(source_locale) <> ''",
            name="ck_journal_intake_source_locale",
        ),
        CheckConstraint(
            "btrim(research_country) <> ''",
            name="ck_journal_intake_research_country",
        ),
        CheckConstraint(
            "intake_hash ~ '^[0-9a-f]{64}$'",
            name="ck_journal_intake_hash",
        ),
        CheckConstraint(
            "btrim(submitted_by) <> ''",
            name="ck_journal_intake_submitted_by",
        ),
        Index("ix_journal_intake_specs_case", "content_case_id"),
    )


class JournalRequiredLocale(TimestampMixin, Base):
    """Canonical locale requirement for one Journal case, independent of materialization."""

    __tablename__ = "journal_required_locales"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    content_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    declared_by: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "content_case_id",
            "locale",
            name="uq_journal_required_locale_case_locale",
        ),
        CheckConstraint(
            "role in ('source','translation')",
            name="ck_journal_required_locale_role",
        ),
        CheckConstraint(
            "btrim(locale) <> ''",
            name="ck_journal_required_locale_value",
        ),
        CheckConstraint(
            "btrim(declared_by) <> ''",
            name="ck_journal_required_locale_declared_by",
        ),
        Index("ix_journal_required_locales_case", "content_case_id"),
    )


class OperatorCommand(TimestampMixin, Base):
    """Durable operator intent; executable work still belongs to the Job queue."""

    __tablename__ = "operator_commands"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    content_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_cases.id"), nullable=False
    )
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("content_runs.id"))
    step_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("step_runs.id"))
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"))
    result_ref_id: Mapped[UUID | None] = mapped_column()
    intent: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_state_version: Mapped[str] = mapped_column(String(64), nullable=False)
    resolved_action_key: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="accepted")
    error_code: Mapped[str | None] = mapped_column(String(100))
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    state_before: Mapped[str] = mapped_column(String(64), nullable=False)
    state_after: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_operator_command_idempotency"),
        CheckConstraint(
            "intent in ('create','start','continue','resume','retry','cancel',"
            "'approve','request_changes','reject')",
            name="ck_operator_command_intent",
        ),
        CheckConstraint(
            "status in ('accepted','queued','completed','rejected','failed','cancelled')",
            name="ck_operator_command_status",
        ),
        CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'",
            name="ck_operator_command_request_hash",
        ),
        CheckConstraint(
            "expected_state_version ~ '^[0-9a-f]{64}$'",
            name="ck_operator_command_expected_state",
        ),
        CheckConstraint(
            "state_before ~ '^[0-9a-f]{64}$'",
            name="ck_operator_command_state_before",
        ),
        CheckConstraint(
            "state_after is null or state_after ~ '^[0-9a-f]{64}$'",
            name="ck_operator_command_state_after",
        ),
        Index("ix_operator_commands_case_status", "content_case_id", "status"),
        Index("ix_operator_commands_job", "job_id"),
    )


__all__ = [
    "AngleApproval",
    "JournalIntakeSpec",
    "JournalRequiredLocale",
    "OperatorCommand",
    "OutlineApproval",
]
